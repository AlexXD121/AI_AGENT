"""Tests for state management and checkpoint persistence."""

import pytest
import tempfile
import shutil
from pathlib import Path

from local_body.core.datamodels import (
    Document, DocumentMetadata, Page, Region, 
    Conflict, ConflictResolution, BoundingBox,
    RegionType, TextContent
)
from local_body.orchestration.state import DocumentProcessingState, ProcessingStage
from local_body.orchestration.checkpoint import CheckpointManager


@pytest.fixture
def temp_checkpoint_dir():
    """Create temporary directory for checkpoints."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def checkpoint_manager(temp_checkpoint_dir):
    """Create CheckpointManager with temp directory."""
    return CheckpointManager(checkpoint_dir=temp_checkpoint_dir)


@pytest.fixture
def sample_document():
    """Create sample document for testing."""
    return Document(
        file_path="/test/test.pdf",
        metadata=DocumentMetadata(
            page_count=2,
            file_size_bytes=1024
        ),
        pages=[Page(page_number=1), Page(page_number=2)]
    )


@pytest.fixture
def sample_state(sample_document):
    """Create sample DocumentProcessingState."""
    state: DocumentProcessingState = {
        'document': sample_document,
        'file_path': '/test/test.pdf',
        'processing_stage': ProcessingStage.LAYOUT,
        'layout_regions': [
            Region(
                bbox=BoundingBox(x=10, y=10, width=100, height=100),
                region_type=RegionType.TEXT,
                content=TextContent(text="Sample", confidence=0.95),
                confidence=0.95,
                extraction_method="ocr"
            )
        ],
        'ocr_results': {'page_1': 'Sample text'},
        'vision_results': {},
        'conflicts': [],
        'resolutions': [],
        'error_log': []
    }
    return state


class TestCheckpointSaveLoad:
    """Test checkpoint save and load functionality."""
    
    def test_save_checkpoint(self, checkpoint_manager, sample_state):
        """Test 1: Save checkpoint to disk"""
        doc_id = sample_state['document'].id
        
        success = checkpoint_manager.save_checkpoint(doc_id, sample_state)
        
        assert success is True
        
        # Verify file exists
        checkpoint_path = Path(checkpoint_manager.checkpoint_dir) / f"{doc_id}.json"
        assert checkpoint_path.exists()
    
    def test_load_checkpoint(self, checkpoint_manager, sample_state):
        """Test 2: Load checkpoint from disk"""
        doc_id = sample_state['document'].id
        
        # Save first
        checkpoint_manager.save_checkpoint(doc_id, sample_state)
        
        # Load it back
        loaded_state = checkpoint_manager.load_checkpoint(doc_id)
        
        assert loaded_state is not None
        assert loaded_state['document'].id == sample_state['document'].id
        assert loaded_state['processing_stage'] == ProcessingStage.LAYOUT
        assert loaded_state['file_path'] == '/test/test.pdf'
    
    def test_pydantic_object_reconstruction(self, checkpoint_manager, sample_state):
        """Test 3: Verify Pydantic objects are reconstructed correctly"""
        doc_id = sample_state['document'].id
        
        # Save and load
        checkpoint_manager.save_checkpoint(doc_id, sample_state)
        loaded_state = checkpoint_manager.load_checkpoint(doc_id)
        
        # Verify types are correct (not dicts)
        assert isinstance(loaded_state['document'], Document)
        assert isinstance(loaded_state['layout_regions'][0], Region)
        
        # Verify data integrity
        assert loaded_state['layout_regions'][0].confidence == 0.95


class TestCheckpointRecovery:
    """Test crash recovery scenarios."""
    
    def test_list_interrupted_jobs(self, checkpoint_manager, sample_state):
        """Test 4: List all interrupted jobs"""
        # Create multiple checkpoints
        checkpoint_manager.save_checkpoint("doc_001", sample_state)
        checkpoint_manager.save_checkpoint("doc_002", sample_state)
        checkpoint_manager.save_checkpoint("doc_003", sample_state)
        
        interrupted = checkpoint_manager.list_interrupted_jobs()
        
        assert len(interrupted) == 3
        assert "doc_001" in interrupted
        assert "doc_002" in interrupted
        assert "doc_003" in interrupted
    
    def test_crash_recovery_simulation(self, checkpoint_manager, sample_state):
        """Test 5: Simulate crash and recovery"""
        doc_id = "crash_test_doc"
        
        # Simulate crash at layout stage
        sample_state['processing_stage'] = ProcessingStage.LAYOUT
        checkpoint_manager.save_checkpoint(doc_id, sample_state)
        
        # System "restarts" - list interrupted jobs
        interrupted = checkpoint_manager.list_interrupted_jobs()
        assert doc_id in interrupted
        
        # Resume from checkpoint
        resumed_state = checkpoint_manager.load_checkpoint(doc_id)
        assert resumed_state['processing_stage'] == ProcessingStage.LAYOUT
    
    def test_clear_checkpoint(self, checkpoint_manager, sample_state):
        """Test 6: Clear checkpoint after completion"""
        doc_id = sample_state['document'].id
        
        # Save checkpoint
        checkpoint_manager.save_checkpoint(doc_id, sample_state)
        assert checkpoint_manager.load_checkpoint(doc_id) is not None
        
        # Clear it
        cleared = checkpoint_manager.clear_checkpoint(doc_id)
        assert cleared is True
        
        # Verify it's gone
        assert checkpoint_manager.load_checkpoint(doc_id) is None


class TestErrorHandling:
    """Test error handling in checkpoint operations."""
    
    def test_load_nonexistent_checkpoint(self, checkpoint_manager):
        """Test 7: Loading non-existent checkpoint returns None"""
        loaded = checkpoint_manager.load_checkpoint("nonexistent_doc")
        assert loaded is None
    
    def test_clear_nonexistent_checkpoint(self, checkpoint_manager):
        """Test 8: Clearing non-existent checkpoint returns False"""
        cleared = checkpoint_manager.clear_checkpoint("nonexistent_doc")
        assert cleared is False
