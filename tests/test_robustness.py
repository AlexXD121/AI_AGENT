"""Tests for workflow robustness and error handling."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

from local_body.orchestration.checkpoint import CheckpointManager
from local_body.orchestration.nodes import layout_node, ocr_node, vision_node, validation_node
from local_body.orchestration.state import DocumentProcessingState, ProcessingStage
from local_body.core.datamodels import Document, DocumentMetadata, Page


@pytest.fixture
def sample_document():
    """Create document with datetime for serialization testing."""
    return Document(
        file_path="/test/test.pdf",
        metadata=DocumentMetadata(
            page_count=1,
            file_size_bytes=1024,
            created_date=datetime.now()  # Test datetime serialization
        ),
        pages=[Page(page_number=1)]
    )


@pytest.fixture
def base_state(sample_document):
    """Create base processing state."""
    state: DocumentProcessingState = {
        'document': sample_document,
        'file_path': '/test/test.pdf',
        'processing_stage': ProcessingStage.INGEST,
        'layout_regions': [],
        'ocr_results': {},
        'vision_results': {},
        'conflicts': [],
        'resolutions': [],
        'error_log': []
    }
    return state


class TestSerialization:
    """Test checkpoint serialization edge cases."""
    
    def test_checkpoint_saves_with_datetime(self, base_state, tmp_path):
        """Test 1: CheckpointManager saves state with datetime successfully"""
        manager = CheckpointManager(checkpoint_dir=str(tmp_path))
        doc_id = base_state['document'].id
        
        # Should not raise TypeError (model_dump(mode='json') handles datetime)
        success = manager.save_checkpoint(doc_id, base_state)
        assert success is True
        
        # Verify file exists
        checkpoint_file = tmp_path / f"{doc_id}.json"
        assert checkpoint_file.exists()
    
    def test_checkpoint_roundtrip_with_datetime(self, base_state, tmp_path):
        """Test 2: DateTime survives save/load cycle"""
        manager = CheckpointManager(checkpoint_dir=str(tmp_path))
        doc_id = base_state['document'].id
        
        # Save
        manager.save_checkpoint(doc_id, base_state)
        
        # Load
        loaded_state = manager.load_checkpoint(doc_id)
        
        assert loaded_state is not None
        assert loaded_state['document'].id == doc_id
        # Pydantic should reconstruct datetime from ISO string
        assert loaded_state['document'].metadata.created_date is not None


class TestNodeErrorHandling:
    """Test node error recovery and graceful degradation."""
    
    @patch('local_body.orchestration.nodes._get_agent')
    def test_layout_node_handles_exception(self, mock_get_agent, base_state):
        """Test 3: layout_node doesn't crash on agent failure"""
        # Mock agent to raise exception
        mock_agent = MagicMock()
        mock_agent.process = AsyncMock(side_effect=ValueError("Simulated Layout Crash"))
        mock_get_agent.return_value = mock_agent
        
        # Call node - should not raise
        result = layout_node(base_state)
        
        # Assert node returned error state instead of crashing
        assert result['processing_stage'] == ProcessingStage.FAILED
        assert len(result['error_log']) == 1
        assert "Simulated Layout Crash" in result['error_log'][0]
    
    @patch('local_body.orchestration.nodes._get_agent')
    def test_ocr_node_handles_exception(self, mock_get_agent, base_state):
        """Test 4: ocr_node doesn't crash on agent failure"""
        mock_agent = MagicMock()
        mock_agent.process = AsyncMock(side_effect=RuntimeError("Simulated OCR Crash"))
        mock_get_agent.return_value = mock_agent
        
        result = ocr_node(base_state)
        
        assert 'ocr_results' in result
        assert result['ocr_results'] == {}
        assert len(result['error_log']) == 1
        assert "Simulated OCR Crash" in result['error_log'][0]
    
    @patch('local_body.orchestration.nodes._get_agent')
    def test_vision_node_handles_exception(self, mock_get_agent, base_state):
        """Test 5: vision_node doesn't crash on agent failure"""
        mock_agent = MagicMock()
        mock_agent.process = AsyncMock(side_effect=ConnectionError("Simulated Vision Crash"))
        mock_get_agent.return_value = mock_agent
        
        result = vision_node(base_state)
        
        assert 'vision_results' in result
        assert result['vision_results'] == {}
        assert len(result['error_log']) == 1
        assert "Simulated Vision Crash" in result['error_log'][0]
    
    @patch('local_body.orchestration.nodes._get_agent')
    def test_validation_node_handles_missing_vision_results(self, mock_get_agent, base_state):
        """Test 6: validation_node handles missing vision_results gracefully"""
        mock_agent = MagicMock()
        mock_agent.validate.return_value = []
        mock_get_agent.return_value = mock_agent
        
        # Remove vision_results
        base_state['vision_results'] = {}
        
        result = validation_node(base_state)
        
        # Should complete successfully with no conflicts
        assert result['processing_stage'] == ProcessingStage.COMPLETE
        assert result['conflicts'] == []
    
    @patch('local_body.orchestration.nodes._get_agent')
    def test_validation_node_handles_exception(self, mock_get_agent, base_state):
        """Test 7: validation_node doesn't crash on agent failure"""
        mock_agent = MagicMock()
        mock_agent.validate.side_effect = Exception("Simulated Validation Crash")
        mock_get_agent.return_value = mock_agent
        
        result = validation_node(base_state)
        
        # Should return empty conflicts to allow workflow to continue
        assert result['conflicts'] == []
        assert result['processing_stage'] == ProcessingStage.COMPLETE
        assert len(result['error_log']) == 1
        assert "Simulated Validation Crash" in result['error_log'][0]


class TestWorkflowResilience:
    """Test workflow continues despite node failures."""
    
    @patch('local_body.orchestration.nodes._get_agent')
    def test_partial_failure_workflow(self, mock_get_agent, base_state):
        """Test 8: Workflow can complete even if some nodes fail"""
        # Mock layout success (use AsyncMock for async process method)
        mock_layout_agent = MagicMock()
        mock_layout_agent.process = AsyncMock(return_value=base_state['document'])
        
        # Mock OCR failure
        mock_ocr_agent = MagicMock()
        mock_ocr_agent.process = AsyncMock(side_effect=ValueError("OCR Failed"))
        
        # Mock vision success
        mock_vision_agent = MagicMock()
        mock_vision_agent.process = AsyncMock(return_value=base_state['document'])
        
        # Mock validation success (validate is sync)
        mock_validation_agent = MagicMock()
        mock_validation_agent.validate.return_value = []
        
        def get_agent_side_effect(agent_type, config):
            if agent_type == "layout":
                return mock_layout_agent
            elif agent_type == "ocr":
                return mock_ocr_agent
            elif agent_type == "vision":
                return mock_vision_agent
            elif agent_type == "validation":
                return mock_validation_agent
        
        mock_get_agent.side_effect = get_agent_side_effect
        
        # Run nodes sequentially
        result1 = layout_node(base_state)
        assert result1['processing_stage'] == ProcessingStage.LAYOUT
        
        # OCR should fail gracefully
        result2 = ocr_node({**base_state, **result1})
        assert result2['ocr_results'] == {}
        assert "OCR Failed" in result2['error_log'][0]
        
        # Vision should succeed
        result3 = vision_node({**base_state, **result1, **result2})
        assert 'vision_results' in result3
        
        # Validation should succeed despite OCR failure
        result4 = validation_node({**base_state, **result1, **result2, **result3})
        assert result4['processing_stage'] == ProcessingStage.COMPLETE
