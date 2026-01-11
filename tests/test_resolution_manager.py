"""Tests for ManualResolutionManager backend service."""

import pytest
from datetime import datetime
from pathlib import Path
import io
from PIL import Image

from local_body.orchestration.resolution_manager import ManualResolutionManager
from local_body.orchestration.checkpoint import CheckpointManager
from local_body.core.datamodels import (
    Document,
    Page,
    Region,
    BoundingBox,
    TextContent,
    Conflict,
    ConflictType,
    ConflictResolution,
    ResolutionStatus,
    ResolutionMethod,
    RegionType,
    DocumentMetadata,
    ProcessingStatus
)


# ==================== Fixtures ====================

@pytest.fixture
def temp_checkpoint_dir(tmp_path):
    """Create temporary checkpoint directory."""
    return tmp_path / "checkpoints"


@pytest.fixture
def checkpoint_manager(temp_checkpoint_dir):
    """Create CheckpointManager with temp directory."""
    return CheckpointManager(checkpoint_dir=str(temp_checkpoint_dir))


@pytest.fixture
def resolution_manager(checkpoint_manager):
    """Create ManualResolutionManager."""
    return ManualResolutionManager(checkpoint_manager)


@pytest.fixture
def dummy_image_bytes():
    """Create a simple test image."""
    # Create a 200x200 red image
    image = Image.new('RGB', (200, 200), color='red')
    buffer = io.BytesIO()
    image.save(buffer, format='JPEG')
    return buffer.getvalue()


@pytest.fixture
def test_document(dummy_image_bytes):
    """Create a test document with conflicts."""
    return Document(
        id="test-doc-123",
        file_path="/tmp/test.pdf",
        pages=[
            Page(
                page_number=1,
                raw_image_bytes=dummy_image_bytes,
                regions=[
                    Region(
                        id="region-1",
                        region_type=RegionType.TABLE,
                        bbox=BoundingBox(x=10, y=10, width=80, height=40),
                        content=TextContent(text="Table data", language="en", confidence=0.9),
                        confidence=0.9,
                        extraction_method="ocr"
                    ),
                    Region(
                        id="region-2",
                        region_type=RegionType.CHART,
                        bbox=BoundingBox(x=110, y=110, width=60, height=60),
                        content=TextContent(text="Chart data", language="en", confidence=0.85),
                        confidence=0.85,
                        extraction_method="vision"
                    )
                ]
            )
        ],
        metadata=DocumentMetadata(
            file_size_bytes=1000,
            page_count=1,
            created_date=datetime.now()
        ),
        processing_status=ProcessingStatus.PENDING,
        created_at=datetime.now()
    )


@pytest.fixture
def test_conflicts():
    """Create test conflicts with different impact scores."""
    return [
        Conflict(
            id="conflict-low",
            region_id="region-1",
            conflict_type=ConflictType.VALUE_MISMATCH,
            text_value="$100",
            vision_value="$105",
            discrepancy_percentage=0.05,
            confidence_scores={"text": 0.8, "vision": 0.75},
            resolution_status=ResolutionStatus.PENDING,
            impact_score=0.1  # Low priority
        ),
        Conflict(
            id="conflict-high",
            region_id="region-1",
            conflict_type=ConflictType.VALUE_MISMATCH,
            text_value="$1000",
            vision_value="$2000",
            discrepancy_percentage=0.50,
            confidence_scores={"text": 0.9, "vision": 0.88},
            resolution_status=ResolutionStatus.PENDING,
            impact_score=0.9  # High priority
        ),
        Conflict(
            id="conflict-medium",
            region_id="region-2",
            conflict_type=ConflictType.VALUE_MISMATCH,
            text_value="45%",
            vision_value="50%",
            discrepancy_percentage=0.10,
            confidence_scores={"text": 0.85, "vision": 0.82},
            resolution_status=ResolutionStatus.PENDING,
            impact_score=0.5  # Medium priority
        ),
        Conflict(
            id="conflict-resolved",
            region_id="region-1",
            conflict_type=ConflictType.VALUE_MISMATCH,
            text_value="$500",
            vision_value="$550",
            discrepancy_percentage=0.09,
            confidence_scores={"text": 0.9, "vision": 0.85},
            resolution_status=ResolutionStatus.RESOLVED,  # Already resolved
            impact_score=0.7
        )
    ]


# ==================== Test Cases ====================

class TestManualResolutionManager:
    """Test ManualResolutionManager functionality."""
    
    def test_get_pending_conflicts_sorting(
        self, 
        resolution_manager, 
        checkpoint_manager,
        test_document,
        test_conflicts
    ):
        """Test 1: Pending conflicts are sorted by impact score (descending)."""
        # Create state with conflicts
        state = {
            'document': test_document,
            'file_path': '/tmp/test.pdf',
            'processing_stage': 'CONFLICT',  # Use string value
            'layout_regions': [],
            'ocr_results': {},
            'vision_results': {},
            'conflicts': test_conflicts,
            'resolutions': [],
            'error_log': []
        }
        
        # Save checkpoint
        checkpoint_manager.save_checkpoint(test_document.id, state)
        
        # Get pending conflicts
        pending = resolution_manager.get_pending_conflicts(test_document.id)
        
        # Should have 3 pending (excluding the resolved one)
        assert len(pending) == 3
        
        # Should be sorted by impact score (descending)
        assert pending[0].impact_score == 0.9  # High priority first
        assert pending[1].impact_score == 0.5  # Medium
        assert pending[2].impact_score == 0.1  # Low last
        
        # Check IDs are correct
        assert pending[0].id == "conflict-high"
        assert pending[1].id == "conflict-medium"
        assert pending[2].id == "conflict-low"
    
    def test_get_conflict_visual_context(
        self,
        resolution_manager,
        checkpoint_manager,
        test_document,
        test_conflicts
    ):
        """Test 2: Visual context extraction returns cropped image bytes."""
        # Create state
        state = {
            'document': test_document,
            'file_path': '/tmp/test.pdf',
            'processing_stage': 'CONFLICT',
            'layout_regions': [],
            'ocr_results': {},
            'vision_results': {},
            'conflicts': test_conflicts,
            'resolutions': [],
            'error_log': []
        }
        
        checkpoint_manager.save_checkpoint(test_document.id, state)
        
        # Get visual context for conflict
        visual_bytes = resolution_manager.get_conflict_visual_context(
            test_document.id,
            "conflict-high"
        )
        
        # Should return bytes
        assert visual_bytes is not None
        assert isinstance(visual_bytes, bytes)
        assert len(visual_bytes) > 0
        
        # Should be a valid image
        cropped_image = Image.open(io.BytesIO(visual_bytes))
        assert cropped_image.format == 'JPEG'
        # Should be cropped to bbox size (roughly, with JPEG compression)
        assert cropped_image.width <= 80 + 5  # Allow small margin
        assert cropped_image.height <= 40 + 5
    
    def test_get_conflict_visual_context_not_found(
        self,
        resolution_manager,
        checkpoint_manager,
        test_document,
        test_conflicts
    ):
        """Test visual context returns None for non-existent conflict."""
        state = {
            'document': test_document,
            'file_path': '/tmp/test.pdf',
            'processing_stage': 'CONFLICT',
            'layout_regions': [],
            'ocr_results': {},
            'vision_results': {},
            'conflicts': test_conflicts,
            'resolutions': [],
            'error_log': []
        }
        
        checkpoint_manager.save_checkpoint(test_document.id, state)
        
        # Try to get context for non-existent conflict
        visual_bytes = resolution_manager.get_conflict_visual_context(
            test_document.id,
            "nonexistent-conflict-id"
        )
        
        assert visual_bytes is None
    
    def test_apply_manual_resolution(
        self,
        resolution_manager,
        checkpoint_manager,
        test_document,
        test_conflicts
    ):
        """Test 3: Manual resolution is applied and persisted."""
        # Create state
        state = {
            'document': test_document,
            'file_path': '/tmp/test.pdf',
            'processing_stage': 'CONFLICT',
            'layout_regions': [],
            'ocr_results': {},
            'vision_results': {},
            'conflicts': test_conflicts,
            'resolutions': [],
            'error_log': []
        }
        
        checkpoint_manager.save_checkpoint(test_document.id, state)
        
        # Apply manual resolution
        success = resolution_manager.apply_manual_resolution(
            doc_id=test_document.id,
            conflict_id="conflict-high",
            resolution_value="$1500",  # User's choice
            strategy="user_override",
            user_id="analyst-42",
            notes="Verified with original invoice"
        )
        
        assert success is True
        
        # Reload checkpoint
        updated_state = checkpoint_manager.load_checkpoint(test_document.id)
        
        # Find the conflict
        conflict = None
        for c in updated_state['conflicts']:
            if c.id == "conflict-high":
                conflict = c
                break
        
        # Conflict status should be updated
        assert conflict is not None
        assert conflict.resolution_status == ResolutionStatus.RESOLVED
        assert conflict.resolution_method == ResolutionMethod.MANUAL
        
        # Resolution should be in history
        resolutions = updated_state['resolutions']
        assert len(resolutions) == 1
        
        resolution = resolutions[0]
        assert resolution.conflict_id == "conflict-high"
        assert resolution.chosen_value == "$1500"
        assert resolution.resolution_method == ResolutionMethod.MANUAL
        assert resolution.user_id == "analyst-42"
        assert "Verified with original invoice" in resolution.notes
    
    def test_get_resolution_history(
        self,
        resolution_manager,
        checkpoint_manager,
        test_document,
        test_conflicts
    ):
        """Test resolution history retrieval."""
        # Create state with some resolutions
        resolutions = [
            ConflictResolution(
                conflict_id="conflict-low",
                chosen_value="$100",
                resolution_method=ResolutionMethod.AUTO,
                confidence=0.95,
                notes="Auto-resolved: confidence_dominance"
            ),
            ConflictResolution(
                conflict_id="conflict-high",
                chosen_value="$1500",
                resolution_method=ResolutionMethod.MANUAL,
                user_id="analyst-42",
                confidence=1.0,
                notes="Manual override"
            )
        ]
        
        state = {
            'document': test_document,
            'file_path': '/tmp/test.pdf',
            'processing_stage': 'COMPLETE',
            'layout_regions': [],
            'ocr_results': {},
            'vision_results': {},
            'conflicts': test_conflicts,
            'resolutions': resolutions,
            'error_log': []
        }
        
        checkpoint_manager.save_checkpoint(test_document.id, state)
        
        # Get history
        history = resolution_manager.get_resolution_history(test_document.id)
        
        assert len(history) == 2
        assert history[0].conflict_id == "conflict-low"
        assert history[1].conflict_id == "conflict-high"
        assert history[0].resolution_method == ResolutionMethod.AUTO
        assert history[1].resolution_method == ResolutionMethod.MANUAL
    
    def test_get_pending_conflicts_no_checkpoint(self, resolution_manager):
        """Test handling of missing checkpoint."""
        pending = resolution_manager.get_pending_conflicts("nonexistent-doc")
        assert pending == []
    
    def test_apply_manual_resolution_missing_conflict(
        self,
        resolution_manager,
        checkpoint_manager,
        test_document,
        test_conflicts
    ):
        """Test applying resolution to non-existent conflict fails gracefully."""
        state = {
            'document': test_document,
            'file_path': '/tmp/test.pdf',
            'processing_stage': 'CONFLICT',
            'layout_regions': [],
            'ocr_results': {},
            'vision_results': {},
            'conflicts': test_conflicts,
            'resolutions': [],
            'error_log': []
        }
        
        checkpoint_manager.save_checkpoint(test_document.id, state)
        
        success = resolution_manager.apply_manual_resolution(
            doc_id=test_document.id,
            conflict_id="nonexistent-conflict",
            resolution_value="$999",
            strategy="user_override"
        )
        
        assert success is False
