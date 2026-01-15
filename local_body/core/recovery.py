"""Page-level checkpoint recovery system for resilient document processing.

This module provides fine-grained recovery capabilities for document processing,
allowing resume from specific pages after crashes or failures.

Complements orchestration/checkpoint.py (document-level) with page-level granularity.

Features:
- Page-by-page progress tracking
- Resume interrupted processing from last completed page
- Atomic checkpoint writes for crash safety
- Listing of pending/incomplete jobs
"""

import json
import time
from pathlib import Path
from typing import Optional, List, Dict, Any, Set, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
from loguru import logger


@dataclass
class RecoveryState:
    """Page-level recovery state for a document.
    
    Attributes:
        doc_id: Document identifier
        total_pages: Total number of pages in document
        completed_pages: Set of successfully processed page numbers
        failed_pages: Set of pages that failed processing
        status: Processing status (IN_PROGRESS, COMPLETED, FAILED)
        last_updated: Timestamp of last checkpoint save
        processing_mode: Mode used for processing (for audit)
        metadata: Additional context (file_path, etc.)
    """
    doc_id: str
    total_pages: int
    completed_pages: Set[int] = field(default_factory=set)
    failed_pages: Set[int] = field(default_factory=set)
    status: str = "IN_PROGRESS"  # IN_PROGRESS, COMPLETED, FAILED
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())
    processing_mode: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "doc_id": self.doc_id,
            "total_pages": self.total_pages,
            "completed_pages": sorted(list(self.completed_pages)),  # List for JSON
            "failed_pages": sorted(list(self.failed_pages)),
            "status": self.status,
            "last_updated": self.last_updated,
            "processing_mode": self.processing_mode,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RecoveryState':
        """Create RecoveryState from dictionary."""
        return cls(
            doc_id=data["doc_id"],
            total_pages=data["total_pages"],
            completed_pages=set(data.get("completed_pages", [])),
            failed_pages=set(data.get("failed_pages", [])),
            status=data.get("status", "IN_PROGRESS"),
            last_updated=data.get("last_updated", datetime.now().isoformat()),
            processing_mode=data.get("processing_mode"),
            metadata=data.get("metadata", {})
        )


class RecoveryManager:
    """Manager for page-level checkpoint and recovery.
    
    Provides fine-grained recovery for document processing with page-level tracking.
    
    Features:
    - Save checkpoint after each page
    - Load previous state to resume
    - Atomic writes for crash safety
    - List pending/incomplete jobs
    
    Usage:
        recovery = RecoveryManager()
        
        # Start new document
        state = recovery.load_checkpoint(doc_id) or RecoveryState(doc_id, total_pages=50)
        
        # Get resume point
        next_page, completed = recovery.get_resume_point(doc_id)
        
        # Process pages
        for page_num in range(next_page, total_pages + 1):
            process_page(page_num)
            recovery.save_checkpoint(doc_id, page_num, status="completed")
        
        # Mark complete
        recovery.mark_completed(doc_id)
    """
    
    def __init__(self, recovery_dir: str = "./data/recovery"):
        """Initialize recovery manager.
        
        Args:
            recovery_dir: Directory to store recovery state files
        """
        self.recovery_dir = Path(recovery_dir)
        self.recovery_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"RecoveryManager initialized: {self.recovery_dir}")
    
    def save_checkpoint(
        self,
        doc_id: str,
        page_num: int,
        status: str = "completed",
        total_pages: Optional[int] = None,
        processing_mode: Optional[str] = None
    ) -> bool:
        """Save page progress checkpoint.
        
        Args:
            doc_id: Document identifier
            page_num: Page number that was just processed
            status: "completed" or "failed"
            total_pages: Total pages (required for new checkpoints)
            processing_mode: Processing mode used (for audit)
            
        Returns:
            True if save successful
        """
        try:
            # Load existing state or create new
            state = self.load_checkpoint(doc_id)
            
            if state is None:
                if total_pages is None:
                    logger.error(f"total_pages required for new checkpoint: {doc_id}")
                    return False
                
                state = RecoveryState(
                    doc_id=doc_id,
                    total_pages=total_pages,
                    processing_mode=processing_mode
                )
            
            # Update state
            if status == "completed":
                state.completed_pages.add(page_num)
                # Remove from failed if it was retried successfully
                state.failed_pages.discard(page_num)
            elif status == "failed":
                state.failed_pages.add(page_num)
            
            # Update timestamp and mode
            state.last_updated = datetime.now().isoformat()
            if processing_mode:
                state.processing_mode = processing_mode
            
            # Write to disk atomically
            success = self._write_state_atomic(state)
            
            if success:
                logger.debug(
                    f"Checkpoint saved: {doc_id} page {page_num} "
                    f"({len(state.completed_pages)}/{state.total_pages})"
                )
            
            return success
        
        except Exception as e:
            logger.error(f"Failed to save checkpoint for {doc_id}: {e}")
            return False
    
    def load_checkpoint(self, doc_id: str) -> Optional[RecoveryState]:
        """Load recovery state from disk.
        
        Args:
            doc_id: Document identifier
            
        Returns:
            RecoveryState if found, None otherwise
        """
        try:
            checkpoint_path = self._get_checkpoint_path(doc_id)
            
            if not checkpoint_path.exists():
                logger.debug(f"No recovery checkpoint found for {doc_id}")
                return None
            
            # Read JSON
            with open(checkpoint_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            state = RecoveryState.from_dict(data)
            
            logger.debug(
                f"Recovery checkpoint loaded: {doc_id} "
                f"({len(state.completed_pages)}/{state.total_pages} pages)"
            )
            
            return state
        
        except Exception as e:
            logger.error(f"Failed to load checkpoint for {doc_id}: {e}")
            return None
    
    def get_resume_point(self, doc_id: str) -> Tuple[int, List[int]]:
        """Get the next page number to process and list of completed pages.
        
        Args:
            doc_id: Document identifier
            
        Returns:
            Tuple of (next_page_to_process, list_of_completed_pages)
            - If no checkpoint: (1, [])
            - If checkpoint exists: (next_unprocessed_page, completed_pages)
        """
        state = self.load_checkpoint(doc_id)
        
        if state is None:
            # No checkpoint - start from page 1
            return (1, [])
        
        # Find the next page that hasn't been completed
        completed = sorted(list(state.completed_pages))
        
        # Find first gap in completed pages
        next_page = 1
        for page_num in range(1, state.total_pages + 1):
            if page_num not in state.completed_pages:
                next_page = page_num
                break
        else:
            # All pages completed
            next_page = state.total_pages + 1
        
        logger.info(
            f"Resume point for {doc_id}: page {next_page} "
            f"({len(completed)} pages already completed)"
        )
        
        return (next_page, completed)
    
    def mark_completed(self, doc_id: str) -> bool:
        """Mark document processing as completed.
        
        Args:
            doc_id: Document identifier
            
        Returns:
            True if marked successfully
        """
        try:
            state = self.load_checkpoint(doc_id)
            
            if state is None:
                logger.warning(f"No checkpoint to mark completed: {doc_id}")
                return False
            
            # Update status
            state.status = "COMPLETED"
            state.last_updated = datetime.now().isoformat()
            
            # Write final state
            success = self._write_state_atomic(state)
            
            if success:
                logger.info(
                    f"Document marked complete: {doc_id} "
                    f"({len(state.completed_pages)}/{state.total_pages} pages)"
                )
            
            return success
        
        except Exception as e:
            logger.error(f"Failed to mark {doc_id} as completed: {e}")
            return False
    
    def mark_failed(self, doc_id: str, reason: Optional[str] = None) -> bool:
        """Mark document processing as failed.
        
        Args:
            doc_id: Document identifier
            reason: Optional failure reason
            
        Returns:
            True if marked successfully
        """
        try:
            state = self.load_checkpoint(doc_id)
            
            if state is None:
                logger.warning(f"No checkpoint to mark failed: {doc_id}")
                return False
            
            # Update status
            state.status = "FAILED"
            state.last_updated = datetime.now().isoformat()
            
            if reason:
                state.metadata["failure_reason"] = reason
            
            # Write final state
            success = self._write_state_atomic(state)
            
            if success:
                logger.warning(f"Document marked failed: {doc_id} - {reason}")
            
            return success
        
        except Exception as e:
            logger.error(f"Failed to mark {doc_id} as failed: {e}")
            return False
    
    def list_pending_jobs(self) -> List[RecoveryState]:
        """List all documents with IN_PROGRESS status.
        
        Returns:
            List of RecoveryState for pending jobs
        """
        try:
            checkpoint_files = list(self.recovery_dir.glob("*.json"))
            pending_jobs = []
            
            for checkpoint_file in checkpoint_files:
                try:
                    with open(checkpoint_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    state = RecoveryState.from_dict(data)
                    
                    if state.status == "IN_PROGRESS":
                        pending_jobs.append(state)
                
                except Exception as e:
                    logger.warning(f"Error reading {checkpoint_file.name}: {e}")
                    continue
            
            if pending_jobs:
                logger.info(f"Found {len(pending_jobs)} pending jobs")
            
            return pending_jobs
        
        except Exception as e:
            logger.error(f"Failed to list pending jobs: {e}")
            return []
    
    def clear_checkpoint(self, doc_id: str) -> bool:
        """Remove recovery checkpoint (after successful completion).
        
        Args:
            doc_id: Document identifier
            
        Returns:
            True if removal successful
        """
        try:
            checkpoint_path = self._get_checkpoint_path(doc_id)
            
            if checkpoint_path.exists():
                checkpoint_path.unlink()
                logger.debug(f"Recovery checkpoint cleared: {doc_id}")
                return True
            else:
                logger.warning(f"No checkpoint to clear: {doc_id}")
                return False
        
        except Exception as e:
            logger.error(f"Failed to clear checkpoint for {doc_id}: {e}")
            return False
    
    def get_progress_stats(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get processing progress statistics.
        
        Args:
            doc_id: Document identifier
            
        Returns:
            Dictionary with progress stats or None
        """
        state = self.load_checkpoint(doc_id)
        
        if state is None:
            return None
        
        completed_count = len(state.completed_pages)
        failed_count = len(state.failed_pages)
        remaining = state.total_pages - completed_count
        
        progress_percent = (completed_count / state.total_pages * 100) if state.total_pages > 0 else 0
        
        return {
            "doc_id": doc_id,
            "total_pages": state.total_pages,
            "completed": completed_count,
            "failed": failed_count,
            "remaining": remaining,
            "progress_percent": progress_percent,
            "status": state.status,
            "processing_mode": state.processing_mode,
            "last_updated": state.last_updated
        }
    
    def _get_checkpoint_path(self, doc_id: str) -> Path:
        """Get checkpoint file path for document.
        
        Args:
            doc_id: Document identifier
            
        Returns:
            Path to checkpoint file
        """
        # Sanitize doc_id to make safe filename
        safe_doc_id = "".join(c if c.isalnum() or c in ("_", "-") else "_" 
                             for c in doc_id)
        return self.recovery_dir / f"{safe_doc_id}.json"
    
    def _write_state_atomic(self, state: RecoveryState) -> bool:
        """Write recovery state with atomic operation (temp file + rename).
        
        Ensures checkpoint is never corrupted even if process crashes mid-write.
        
        Args:
            state: RecoveryState to write
            
        Returns:
            True if write successful
        """
        try:
            checkpoint_path = self._get_checkpoint_path(state.doc_id)
            temp_path = checkpoint_path.with_suffix(".tmp")
            
            # Write to temp file
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(state.to_dict(), f, indent=2, ensure_ascii=False)
            
            # Atomic rename (overwrites existing file)
            temp_path.replace(checkpoint_path)
            
            return True
        
        except Exception as e:
            logger.error(f"Atomic write failed for {state.doc_id}: {e}")
            
            # Clean up temp file if it exists
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except:
                    pass
            
            return False
