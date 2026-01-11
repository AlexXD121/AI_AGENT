"""Manual Resolution Manager for human-in-the-loop conflict resolution.

This module provides backend services for the manual resolution UI,
including conflict prioritization, visual context extraction, and
resolution persistence.

Requirements: 11.5 (Priority Queue), 12.3 (Visual Comparison), 12.4 (Audit Trail)
"""

import io
from typing import List, Optional, Any, Dict
from PIL import Image
from loguru import logger

from local_body.orchestration.checkpoint import CheckpointManager
from local_body.core.datamodels import (
    Conflict,
    ConflictResolution,
    ResolutionMethod,
    ResolutionStatus,
    Document,
    Region
)


class ManualResolutionManager:
    """Backend service for manual conflict resolution.
    
    Provides prioritized conflict queues, visual context extraction,
    and persistence for human resolution decisions.
    """
    
    def __init__(self, checkpoint_manager: Optional[CheckpointManager] = None):
        """Initialize manual resolution manager.
        
        Args:
            checkpoint_manager: CheckpointManager instance (creates default if None)
        """
        self.checkpoint_manager = checkpoint_manager or CheckpointManager()
        logger.info("ManualResolutionManager initialized")
    
    def get_pending_conflicts(self, doc_id: str) -> List[Conflict]:
        """Get all unresolved conflicts sorted by priority (impact score).
        
        Args:
            doc_id: Document identifier
            
        Returns:
            List of conflicts sorted by impact_score (descending)
        """
        state = self.checkpoint_manager.load_checkpoint(doc_id)
        
        if not state:
            logger.warning(f"No checkpoint found for document {doc_id}")
            return []
        
        conflicts = state.get('conflicts', [])
        
        # Filter for pending conflicts (not resolved)
        pending = [
            c for c in conflicts 
            if c.resolution_status == ResolutionStatus.PENDING
        ]
        
        # Sort by impact score (descending - highest priority first)
        sorted_conflicts = sorted(
            pending,
            key=lambda c: c.impact_score,
            reverse=True
        )
        
        logger.info(
            f"Retrieved {len(sorted_conflicts)} pending conflicts for {doc_id} "
            f"(from {len(conflicts)} total)"
        )
        
        return sorted_conflicts
    
    def get_conflict_visual_context(
        self,
        doc_id: str,
        conflict_id: str
    ) -> Optional[bytes]:
        """Extract cropped image region for visual conflict comparison.
        
        This allows the UI to show a side-by-side comparison of the
        specific region where OCR and Vision disagree.
        
        Args:
            doc_id: Document identifier
            conflict_id: Conflict identifier
            
        Returns:
            JPEG bytes of cropped region, or None if not found
        """
        state = self.checkpoint_manager.load_checkpoint(doc_id)
        
        if not state:
            logger.warning(f"No checkpoint found for document {doc_id}")
            return None
        
        # Find the conflict
        conflict = None
        for c in state.get('conflicts', []):
            if c.id == conflict_id:
                conflict = c
                break
        
        if not conflict:
            logger.warning(f"Conflict {conflict_id} not found in document {doc_id}")
            return None
        
        # Find the region and page
        document = state['document']
        region = self._find_region(document, conflict.region_id)
        
        if not region:
            logger.warning(f"Region {conflict.region_id} not found")
            return None
        
        # Find the page containing this region
        page = None
        for p in document.pages:
            for r in p.regions:
                if r.id == conflict.region_id:
                    page = p
                    break
            if page:
                break
        
        if not page or not page.raw_image_bytes:
            logger.warning(f"Page or image data not found for region {conflict.region_id}")
            return None
        
        # Crop the image to the bounding box
        try:
            cropped_bytes = self._crop_image_to_bbox(
                page.raw_image_bytes,
                region.bbox
            )
            
            logger.debug(
                f"Extracted visual context for conflict {conflict_id[:8]} "
                f"(region {conflict.region_id[:8]})"
            )
            
            return cropped_bytes
            
        except Exception as e:
            logger.error(f"Failed to crop image for conflict {conflict_id}: {e}")
            return None
    
    def apply_manual_resolution(
        self,
        doc_id: str,
        conflict_id: str,
        resolution_value: Any,
        strategy: str,
        user_id: Optional[str] = None,
        notes: Optional[str] = None
    ) -> bool:
        """Apply a manual resolution decision and persist it.
        
        Args:
            doc_id: Document identifier
            conflict_id: Conflict identifier
            resolution_value: The value chosen by the user
            strategy: Resolution strategy used
            user_id: Optional user identifier for audit trail
            notes: Optional notes about the decision
            
        Returns:
            True if successful, False otherwise
        """
        state = self.checkpoint_manager.load_checkpoint(doc_id)
        
        if not state:
            logger.error(f"No checkpoint found for document {doc_id}")
            return False
        
        # Find the conflict
        conflict = None
        conflict_index = None
        for idx, c in enumerate(state.get('conflicts', [])):
            if c.id == conflict_id:
                conflict = c
                conflict_index = idx
                break
        
        if not conflict:
            logger.error(f"Conflict {conflict_id} not found in document {doc_id}")
            return False
        
        # Create resolution record
        resolution = ConflictResolution(
            conflict_id=conflict_id,
            chosen_value=resolution_value,
            resolution_method=ResolutionMethod.MANUAL,
            user_id=user_id,
            confidence=1.0,  # User decision is 100% confident
            notes=notes or f"Manual resolution: {strategy}"
        )
        
        # Update conflict status
        conflict.resolution_status = ResolutionStatus.RESOLVED
        conflict.resolution_method = ResolutionMethod.MANUAL
        
        # Update conflict in state (replace with modified version)
        state['conflicts'][conflict_index] = conflict
        
        # Add resolution to history
        if 'resolutions' not in state:
            state['resolutions'] = []
        state['resolutions'].append(resolution)
        
        # Persist to checkpoint
        success = self.checkpoint_manager.save_checkpoint(doc_id, state)
        
        if success:
            logger.info(
                f"Manual resolution applied for conflict {conflict_id[:8]} "
                f"in document {doc_id[:8]}: {resolution_value}"
            )
        else:
            logger.error(f"Failed to save checkpoint for {doc_id}")
        
        return success
    
    def get_resolution_history(self, doc_id: str) -> List[ConflictResolution]:
        """Get all resolutions for audit trail.
        
        Args:
            doc_id: Document identifier
            
        Returns:
            List of all conflict resolutions (auto and manual)
        """
        state = self.checkpoint_manager.load_checkpoint(doc_id)
        
        if not state:
            logger.warning(f"No checkpoint found for document {doc_id}")
            return []
        
        resolutions = state.get('resolutions', [])
        
        logger.info(f"Retrieved {len(resolutions)} resolutions for {doc_id}")
        
        return resolutions
    
    def _find_region(self, document: Document, region_id: str) -> Optional[Region]:
        """Find a region by ID in the document.
        
        Args:
            document: Document to search
            region_id: Region identifier
            
        Returns:
            Region if found, None otherwise
        """
        for page in document.pages:
            for region in page.regions:
                if region.id == region_id:
                    return region
        return None
    
    def _crop_image_to_bbox(
        self,
        image_bytes: bytes,
        bbox: Any  # BoundingBox
    ) -> bytes:
        """Crop image to bounding box coordinates.
        
        Args:
            image_bytes: Original image bytes
            bbox: BoundingBox with x, y, width, height
            
        Returns:
            JPEG bytes of cropped region
        """
        # Load image
        image = Image.open(io.BytesIO(image_bytes))
        
        # Calculate crop coordinates (PIL uses left, upper, right, lower)
        left = int(bbox.x)
        upper = int(bbox.y)
        right = int(bbox.x + bbox.width)
        lower = int(bbox.y + bbox.height)
        
        # Ensure coordinates are within image bounds
        left = max(0, min(left, image.width))
        upper = max(0, min(upper, image.height))
        right = max(0, min(right, image.width))
        lower = max(0, min(lower, image.height))
        
        # Crop the image
        cropped = image.crop((left, upper, right, lower))
        
        # Convert to JPEG bytes
        output = io.BytesIO()
        cropped.convert('RGB').save(output, format='JPEG', quality=95)
        
        return output.getvalue()
