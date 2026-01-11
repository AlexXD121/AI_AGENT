"""Checkpoint management for workflow persistence and recovery.

This module provides checkpoint persistence to enable crash recovery
during document processing. If processing fails at document #25 out of 50,
the system can resume from #25 upon restart.

Requirements: 5.3 (State Persistence), 15.7 (Workflow Resumption)
"""

import json
import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from loguru import logger

from local_body.core.datamodels import Document, Region, Conflict, ConflictResolution
from local_body.orchestration.state import DocumentProcessingState


class CheckpointManager:
    """Manages checkpoint persistence for document processing workflows.
    
    Handles serialization and deserialization of DocumentProcessingState,
    including proper reconstruction of Pydantic models.
    """
    
    def __init__(self, checkpoint_dir: str = "./data/checkpoints"):
        """Initialize checkpoint manager.
        
        Args:
            checkpoint_dir: Directory to store checkpoint files
        """
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"CheckpointManager initialized: {self.checkpoint_dir}")
    
    def save_checkpoint(self, doc_id: str, state: DocumentProcessingState) -> bool:
        """Save processing state to disk.
        
        Args:
            doc_id: Document identifier
            state: Current processing state
            
        Returns:
            True if save successful, False otherwise
        """
        try:
            checkpoint_path = self.checkpoint_dir / f"{doc_id}.json"
            
            # Convert Pydantic models to dicts for JSON serialization
            serializable_state = self._serialize_state(state)
            
            # Write to file with pretty formatting
            with open(checkpoint_path, 'w', encoding='utf-8') as f:
                json.dump(serializable_state, f, indent=2, ensure_ascii=False)
            
            logger.debug(f"Checkpoint saved: {doc_id} (stage: {state['processing_stage']})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save checkpoint for {doc_id}: {e}")
            return False
    
    def load_checkpoint(self, doc_id: str) -> Optional[DocumentProcessingState]:
        """Load processing state from disk.
        
        Args:
            doc_id: Document identifier
            
        Returns:
            DocumentProcessingState if found, None otherwise
        """
        try:
            checkpoint_path = self.checkpoint_dir / f"{doc_id}.json"
            
            if not checkpoint_path.exists():
                logger.warning(f"No checkpoint found for {doc_id}")
                return None
            
            # Read JSON file
            with open(checkpoint_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Reconstruct Pydantic objects
            state = self._deserialize_state(data)
            
            logger.info(f"Checkpoint loaded: {doc_id} (stage: {state['processing_stage']})")
            return state
            
        except Exception as e:
            logger.error(f"Failed to load checkpoint for {doc_id}: {e}")
            return None
    
    def list_interrupted_jobs(self) -> List[str]:
        """List all document IDs with saved checkpoints.
        
        Returns:
            List of document IDs that have checkpoints
        """
        try:
            checkpoint_files = list(self.checkpoint_dir.glob("*.json"))
            doc_ids = [f.stem for f in checkpoint_files]
            
            if doc_ids:
                logger.info(f"Found {len(doc_ids)} interrupted jobs")
            
            return doc_ids
            
        except Exception as e:
            logger.error(f"Failed to list interrupted jobs: {e}")
            return []
    
    def clear_checkpoint(self, doc_id: str) -> bool:
        """Remove checkpoint file after successful completion.
        
        Args:
            doc_id: Document identifier
            
        Returns:
            True if removal successful, False otherwise
        """
        try:
            checkpoint_path = self.checkpoint_dir / f"{doc_id}.json"
            
            if checkpoint_path.exists():
                checkpoint_path.unlink()
                logger.debug(f"Checkpoint cleared: {doc_id}")
                return True
            else:
                logger.warning(f"No checkpoint to clear for {doc_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to clear checkpoint for {doc_id}: {e}")
            return False
    
    def _serialize_state(self, state: DocumentProcessingState) -> Dict[str, Any]:
        """Convert state to JSON-serializable format.
        
        Args:
            state: Processing state with Pydantic objects
            
        Returns:
            Dictionary with all Pydantic objects converted to dicts
        """
        serialized = {
            'document': state['document'].model_dump(mode='json'),
            'file_path': state['file_path'],
            'processing_stage': state['processing_stage'],
            'layout_regions': [region.model_dump(mode='json') for region in state['layout_regions']],
            'ocr_results': state['ocr_results'],
            'vision_results': state['vision_results'],
            'conflicts': [conflict.model_dump(mode='json') for conflict in state['conflicts']],
            'resolutions': [res.model_dump(mode='json') for res in state['resolutions']],
            'error_log': state['error_log']
        }
        
        return serialized
    
    def _deserialize_state(self, data: Dict[str, Any]) -> DocumentProcessingState:
        """Reconstruct state from JSON data.
        
        Args:
            data: Dictionary loaded from JSON
            
        Returns:
            DocumentProcessingState with reconstructed Pydantic objects
        """
        state: DocumentProcessingState = {
            'document': Document(**data['document']),
            'file_path': data['file_path'],
            'processing_stage': data['processing_stage'],
            'layout_regions': [Region(**region) for region in data['layout_regions']],
            'ocr_results': data['ocr_results'],
            'vision_results': data['vision_results'],
            'conflicts': [Conflict(**conflict) for conflict in data['conflicts']],
            'resolutions': [ConflictResolution(**res) for res in data['resolutions']],
            'error_log': data['error_log']
        }
        
        return state
