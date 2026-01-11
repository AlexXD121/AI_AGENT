"""Tests for workflow robustness and error handling."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime

from local_body.orchestration.state import DocumentProcessingState, ProcessingStage
from local_body.core.datamodels import Document, Page, DocumentMetadata, ProcessingStatus
from local_body.orchestration.checkpoint import CheckpointManager
from local_body.orchestration.nodes import layout_node, ocr_node, vision_node, validation_node


# --- Test Data Helpers ---

def create_dummy_document():
    """Create a minimal test document."""
    return Document(
        id="test-doc-123",
        file_path="/tmp/test.pdf",
        pages=[Page(page_number=1, raw_image_bytes=b"fake_image")],
        metadata=DocumentMetadata(
            file_size_bytes=1000,
            page_count=1,
            created_date=datetime.now()  # Test datetime serialization
        ),
        processing_status=ProcessingStatus.PENDING,
        created_at=datetime.now()
    )


def create_dummy_state():
    """Create a minimal test state."""
    return {
        'document': create_dummy_document(),
        'file_path': '/tmp/test.pdf',
        'processing_stage': ProcessingStage.INGEST,
        'layout_regions': [],
        'ocr_results': {},
        'vision_results': {},
        'conflicts': [],
        'resolutions': [],
        'error_log': []
    }


# --- 1. Serialization Tests (Sync) ---

class TestSerialization:
    """Test checkpoint serialization edge cases."""
    
    def test_checkpoint_saves_with_datetime(self, tmp_path):
        """Test that CheckpointManager can save state containing datetime objects."""
        checkpoint_dir = tmp_path / "checkpoints"
        manager = CheckpointManager(checkpoint_dir=str(checkpoint_dir))
        
        state = create_dummy_state()
        
        # Verify datetime presence
        assert isinstance(state['document'].created_at, datetime)
        
        # Should not raise TypeError
        success = manager.save_checkpoint(state['document'].id, state)
        assert success is True
        assert (checkpoint_dir / f"{state['document'].id}.json").exists()

    def test_checkpoint_roundtrip_with_datetime(self, tmp_path):
        """Test saving and loading back restores the state correctly."""
        checkpoint_dir = tmp_path / "checkpoints"
        manager = CheckpointManager(checkpoint_dir=str(checkpoint_dir))
        state = create_dummy_state()
        doc_id = state['document'].id
        
        manager.save_checkpoint(doc_id, state)
        loaded_state = manager.load_checkpoint(doc_id)
        
        assert loaded_state is not None
        # Pydantic handles the string -> datetime conversion automatically
        assert isinstance(loaded_state['document'].created_at, datetime)
        assert loaded_state['document'].id == doc_id


# --- 2. Node Robustness Tests (Async) ---

@pytest.mark.asyncio
class TestNodeErrorHandling:
    """Test node error recovery and graceful degradation."""
    
    async def test_layout_node_handles_exception(self):
        """Ensure layout_node catches exceptions and returns error state."""
        state = create_dummy_state()
        
        # Mock _get_agent to return an agent that raises an exception
        with patch('local_body.orchestration.nodes._get_agent') as mock_get_agent:
            mock_agent = MagicMock()
            # process is async, so we mock it as an AsyncMock that raises
            mock_agent.process = AsyncMock(side_effect=ValueError("Simulated Layout Crash"))
            mock_get_agent.return_value = mock_agent
            
            # CALL ASYNC NODE
            result = await layout_node(state)
            
            # Assertions
            assert result['processing_stage'] == ProcessingStage.FAILED
            assert 'error_log' in result
            assert len(result['error_log']) > 0
            assert "Simulated Layout Crash" in result['error_log'][0]

    async def test_ocr_node_handles_exception(self):
        """Ensure ocr_node catches exceptions and returns error state."""
        state = create_dummy_state()
        
        with patch('local_body.orchestration.nodes._get_agent') as mock_get_agent:
            mock_agent = MagicMock()
            mock_agent.process = AsyncMock(side_effect=RuntimeError("OCR Engine Failure"))
            mock_get_agent.return_value = mock_agent
            
            # CALL ASYNC NODE
            result = await ocr_node(state)
            
            assert 'error_log' in result
            assert len(result['error_log']) > 0
            assert "OCR Engine Failure" in result['error_log'][0]
            # OCR node returns partial results on failure, usually empty
            assert result['ocr_results'] == {}

    async def test_vision_node_handles_exception(self):
        """Ensure vision_node catches exceptions."""
        state = create_dummy_state()
        
        with patch('local_body.orchestration.nodes._get_agent') as mock_get_agent:
            mock_agent = MagicMock()
            mock_agent.process = AsyncMock(side_effect=ConnectionError("Cloud Brain Down"))
            mock_get_agent.return_value = mock_agent
            
            # CALL ASYNC NODE
            result = await vision_node(state)
            
            assert 'error_log' in result
            assert len(result['error_log']) > 0
            assert "Cloud Brain Down" in result['error_log'][0]

    def test_validation_node_handles_missing_vision_results(self):
        """Validation node should skip gracefully if vision results are missing."""
        state = create_dummy_state()
        state['vision_results'] = {}  # Empty
        
        with patch('local_body.orchestration.nodes._get_agent') as mock_get_agent:
            mock_agent = MagicMock()
            # Setup a real-ish validate return to prove it ran
            mock_agent.validate.return_value = []
            mock_get_agent.return_value = mock_agent
            
            # Validation node is SYNC (CPU bound)
            result = validation_node(state)
            
            assert result['processing_stage'] == ProcessingStage.COMPLETE
            # With empty vision results, it should still complete
            assert result['conflicts'] == []

    def test_validation_node_handles_exception(self):
        """Ensure validation node catches exceptions."""
        state = create_dummy_state()
        state['vision_results'] = {'page_0': 'some result'}  # Add vision results
        
        with patch('local_body.orchestration.nodes._get_agent') as mock_get_agent:
            mock_agent = MagicMock()
            # validate is sync
            mock_agent.validate.side_effect = TypeError("Comparison Error")
            mock_get_agent.return_value = mock_agent
            
            # SYNC Call
            result = validation_node(state)
            
            assert 'error_log' in result
            assert len(result['error_log']) > 0
            assert "Comparison Error" in result['error_log'][0]
            # Should still complete, returning empty conflicts
            assert result['processing_stage'] == ProcessingStage.COMPLETE


# --- 3. Workflow Integration Tests (Async) ---

@pytest.mark.asyncio
class TestWorkflowResilience:
    """Test workflow continues despite node failures."""
    
    async def test_partial_failure_workflow(self):
        """
        Simulate a workflow where Layout works, but OCR fails.
        The state should reflect the error but contain layout info.
        """
        state = create_dummy_state()
        
        # We manually call the nodes to simulate the graph flow
        
        # 1. Layout Succeeds
        with patch('local_body.orchestration.nodes._get_agent') as mock_get:
            layout_agent = MagicMock()
            # Return doc with regions
            doc_with_regions = state['document'].model_copy()
            layout_agent.process = AsyncMock(return_value=doc_with_regions)
            mock_get.return_value = layout_agent
            
            layout_result = await layout_node(state)
            # Merge result into state
            state = {**state, **layout_result}
        
        # Verify layout succeeded
        assert state['processing_stage'] == ProcessingStage.LAYOUT
        
        # 2. OCR Fails
        with patch('local_body.orchestration.nodes._get_agent') as mock_get:
            ocr_agent = MagicMock()
            ocr_agent.process = AsyncMock(side_effect=Exception("OCR Crash"))
            mock_get.return_value = ocr_agent
            
            ocr_result = await ocr_node(state)
            # Update state with error
            if 'error_log' in ocr_result:
                state['error_log'].extend(ocr_result['error_log'])
            state = {**state, **ocr_result}
        
        # Assertions
        assert len(state['error_log']) > 0
        assert "OCR Crash" in state['error_log'][0]
        assert state['ocr_results'] == {}  # Empty due to failure
