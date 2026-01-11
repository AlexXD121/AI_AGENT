"""Tests for LangGraph workflow orchestration."""

import pytest
from unittest.mock import patch, MagicMock

from local_body.orchestration.workflow import (
    DocumentWorkflow,
    route_after_validation,
    auto_resolution_node,
    human_review_node
)
from local_body.orchestration.state import DocumentProcessingState, ProcessingStage
from local_body.core.datamodels import (
    Document, DocumentMetadata, Page, Conflict,
    ConflictType, ResolutionStatus
)


@pytest.fixture
def sample_document():
    """Create sample document for testing."""
    return Document(
        file_path="/test/test.pdf",
        metadata=DocumentMetadata(
            page_count=1,
            file_size_bytes=1024
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


@pytest.fixture
def low_impact_conflict():
    """Create low-impact conflict (discrepancy < 0.7)."""
    return Conflict(
        region_id="test_region",
        conflict_type=ConflictType.VALUE_MISMATCH,
        text_value=100.0,
        vision_value=110.0,
        discrepancy_percentage=0.1,
        confidence_scores={'text': 0.9, 'vision': 0.8},
        impact_score=0.3  # Low impact
    )


@pytest.fixture
def high_impact_conflict():
    """Create high-impact conflict (impact >= 0.7)."""
    return Conflict(
        region_id="test_region",
        conflict_type=ConflictType.VALUE_MISMATCH,
        text_value=100.0,
        vision_value=200.0,
        discrepancy_percentage=0.5,
        confidence_scores={'text': 0.95, 'vision': 0.95},
        impact_score=0.8  # High impact
    )


class TestRouting:
    """Test routing logic."""
    
    def test_route_no_conflicts(self, base_state):
        """Test 1: No conflicts routes to END"""
        route = route_after_validation(base_state)
        assert route == "end"
    
    def test_route_low_impact(self, base_state, low_impact_conflict):
        """Test 2: Low-impact conflicts route to auto_resolve"""
        base_state['conflicts'] = [low_impact_conflict]
        route = route_after_validation(base_state)
        assert route == "auto_resolve"
    
    def test_route_high_impact(self, base_state, high_impact_conflict):
        """Test 3: High-impact conflicts route to human_review"""
        base_state['conflicts'] = [high_impact_conflict]
        route = route_after_validation(base_state)
        assert route == "human_review"


class TestNodes:
    """Test workflow nodes."""
    
    def test_auto_resolution_low_discrepancy(self, base_state):
        """Test 4: Auto-resolution chooses OCR for low discrepancy"""
        conflict = Conflict(
            region_id="test",
            conflict_type=ConflictType.VALUE_MISMATCH,
            text_value=100.0,
            vision_value=110.0,
            discrepancy_percentage=0.1,  # < 0.20
            confidence_scores={'text': 0.9, 'vision': 0.8}
        )
        base_state['conflicts'] = [conflict]
        
        result = auto_resolution_node(base_state)
        
        assert len(result['resolutions']) == 1
        assert result['resolutions'][0].chosen_value == 100.0
        assert result['processing_stage'] == ProcessingStage.COMPLETE
    
    def test_auto_resolution_high_discrepancy(self, base_state):
        """Test 5: Auto-resolution flags high discrepancy"""
        conflict = Conflict(
            region_id="test",
            conflict_type=ConflictType.VALUE_MISMATCH,
            text_value=100.0,
            vision_value=150.0,
            discrepancy_percentage=0.33,  # >= 0.20
            confidence_scores={'text': 0.9, 'vision': 0.8}
        )
        base_state['conflicts'] = [conflict]
        
        result = auto_resolution_node(base_state)
        
        assert len(result['resolutions']) == 0
        assert base_state['conflicts'][0].resolution_status == ResolutionStatus.FLAGGED
        assert result['processing_stage'] == ProcessingStage.CONFLICT
    
    def test_human_review_node(self, base_state):
        """Test 6: Human review node sets correct state"""
        result = human_review_node(base_state)
        
        assert result['processing_stage'] == ProcessingStage.CONFLICT
        assert "Waiting for human review" in result['error_log'][0]


class TestWorkflowGraph:
    """Test workflow graph structure (simplified tests without agent execution)."""
    
    def test_graph_initialization(self, tmp_path):
        """Test 7: Workflow graph initializes correctly"""
        workflow = DocumentWorkflow(checkpoint_dir=str(tmp_path))
        
        assert workflow.graph is not None
        assert workflow.checkpoint_manager is not None
    
    def test_routing_logic_integration(self, base_state, low_impact_conflict, high_impact_conflict):
        """Test 8: Routing logic correctly identifies paths"""
        # No conflicts → end
        assert route_after_validation(base_state) == "end"
        
        # Low impact → auto_resolve
        base_state['conflicts'] = [low_impact_conflict]
        assert route_after_validation(base_state) == "auto_resolve"
        
        # High impact → human_review
        base_state['conflicts'] = [high_impact_conflict]
        assert route_after_validation(base_state) == "human_review"
    
    def test_auto_resolution_workflow(self, base_state):
        """Test 9: Auto-resolution integrates correctly"""
        conflict = Conflict(
            region_id="test",
            conflict_type=ConflictType.VALUE_MISMATCH,
            text_value=100.0,
            vision_value=105.0,
            discrepancy_percentage=0.05,
            confidence_scores={'text': 0.9, 'vision': 0.8},
            impact_score=0.3
        )
        base_state['conflicts'] = [conflict]
        
        # Simulated workflow: validation → auto_resolve
        route = route_after_validation(base_state)
        assert route == "auto_resolve"
        
        result = auto_resolution_node(base_state)
        assert result['processing_stage'] == ProcessingStage.COMPLETE
        assert len(result['resolutions']) == 1
    
    def test_human_review_workflow(self, base_state, high_impact_conflict):
        """Test 10: Human review workflow triggers correctly"""
        base_state['conflicts'] = [high_impact_conflict]
        
        # Simulated workflow: validation → human_review
        route = route_after_validation(base_state)
        assert route == "human_review"
        
        result = human_review_node(base_state)
        assert result['processing_stage'] == ProcessingStage.CONFLICT
        assert "Waiting for human review" in str(result['error_log'])
