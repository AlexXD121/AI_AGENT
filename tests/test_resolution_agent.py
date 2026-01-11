"""Tests for ResolutionAgent conflict resolution logic."""

import pytest
from datetime import datetime

from local_body.agents.resolution_agent import ResolutionAgent, ResolutionStrategy
from local_body.core.datamodels import (
    Document, 
    Page, 
    Region,
    BoundingBox,
    TextContent,
    Conflict, 
    ConflictType,
    RegionType,
    DocumentMetadata,
    ProcessingStatus,
    ResolutionMethod
)


# ==================== Fixtures ====================

@pytest.fixture
def base_document():
    """Create a basic document for testing."""
    return Document(
        id="test-doc-123",
        file_path="/tmp/test.pdf",
        pages=[
            Page(
                page_number=1,
                raw_image_bytes=b"fake_image",
                regions=[
                    Region(
                        id="region-table-1",
                        region_type=RegionType.TABLE,
                        bbox=BoundingBox(x=10, y=10, width=100, height=50),
                        content=TextContent(text="Sample table text", language="en", confidence=0.9),
                        confidence=0.9,
                        extraction_method="ocr"
                    ),
                    Region(
                        id="region-chart-1",
                        region_type=RegionType.CHART,
                        bbox=BoundingBox(x=10, y=70, width=100, height=50),
                        content=TextContent(text="Sample chart text", language="en", confidence=0.85),
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
def resolution_agent():
    """Create a ResolutionAgent for testing."""
    config = {
        "high_confidence_threshold": 0.90,
        "low_confidence_threshold": 0.60,
        "reasonable_confidence": 0.80,
        "massive_discrepancy": 0.50
    }
    return ResolutionAgent(config)


# ==================== Test Cases ====================

class TestResolutionAgent:
    """Test ResolutionAgent resolution strategies."""
    
    def test_empty_conflicts_list(self, resolution_agent, base_document):
        """Test handling of empty conflicts list."""
        resolutions = resolution_agent.resolve(base_document, [])
        assert resolutions == []
    
    def test_strategy_confidence_dominance_ocr_wins(self, resolution_agent, base_document):
        """Test Strategy A: High OCR confidence dominates low vision."""
        conflict = Conflict(
            region_id="region-table-1",
            conflict_type=ConflictType.VALUE_MISMATCH,
            text_value="$5.2M",
            vision_value="$10M",
            discrepancy_percentage=0.48,
            confidence_scores={
                "text": 0.95,  # High OCR
                "vision": 0.40  # Low Vision
            }
        )
        
        resolutions = resolution_agent.resolve(base_document, [conflict])
        
        assert len(resolutions) == 1
        resolution = resolutions[0]
        assert resolution.chosen_value == "$5.2M"
        assert resolution.resolution_method == ResolutionMethod.AUTO
        assert resolution.confidence == 0.95
        assert ResolutionStrategy.CONFIDENCE_DOMINANCE in resolution.notes
    
    def test_strategy_confidence_dominance_vision_wins(self, resolution_agent, base_document):
        """Test Strategy A: High Vision confidence dominates low OCR."""
        conflict = Conflict(
            region_id="region-chart-1",
            conflict_type=ConflictType.VALUE_MISMATCH,
            text_value="15%",
            vision_value="25%",
            discrepancy_percentage=0.40,
            confidence_scores={
                "text": 0.50,  # Low OCR
                "vision": 0.92  # High Vision
            }
        )
        
        resolutions = resolution_agent.resolve(base_document, [conflict])
        
        assert len(resolutions) == 1
        resolution = resolutions[0]
        assert resolution.chosen_value == "25%"
        assert resolution.resolution_method == ResolutionMethod.AUTO
        assert resolution.confidence == 0.92
        assert ResolutionStrategy.CONFIDENCE_DOMINANCE in resolution.notes
    
    def test_strategy_region_bias_table_prefers_ocr(self, resolution_agent, base_document):
        """Test Strategy B: TABLE regions prefer OCR when both confident."""
        conflict = Conflict(
            region_id="region-table-1",
            conflict_type=ConflictType.VALUE_MISMATCH,
            text_value="$1,234,567",
            vision_value="$1.2M",
            discrepancy_percentage=0.03,
            confidence_scores={
                "text": 0.85,  # Reasonable
                "vision": 0.82  # Reasonable
            }
        )
        
        resolutions = resolution_agent.resolve(base_document, [conflict])
        
        assert len(resolutions) == 1
        resolution = resolutions[0]
        assert resolution.chosen_value == "$1,234,567"
        assert resolution.resolution_method == ResolutionMethod.AUTO
        assert ResolutionStrategy.REGION_BIAS_TABLE in resolution.notes
        assert "TABLE region" in resolution.notes
    
    def test_strategy_region_bias_chart_prefers_vision(self, resolution_agent, base_document):
        """Test Strategy B: CHART regions prefer Vision when both confident."""
        conflict = Conflict(
            region_id="region-chart-1",
            conflict_type=ConflictType.VALUE_MISMATCH,
            text_value="42%",
            vision_value="45%",
            discrepancy_percentage=0.07,
            confidence_scores={
                "text": 0.83,  # Reasonable
                "vision": 0.87  # Reasonable
            }
        )
        
        resolutions = resolution_agent.resolve(base_document, [conflict])
        
        assert len(resolutions) == 1
        resolution = resolutions[0]
        assert resolution.chosen_value == "45%"
        assert resolution.resolution_method == ResolutionMethod.AUTO
        assert ResolutionStrategy.REGION_BIAS_CHART in resolution.notes
        assert "CHART region" in resolution.notes
    
    def test_strategy_manual_review_both_low_confidence(self, resolution_agent, base_document):
        """Test Strategy D: Manual review when both confidences are low."""
        conflict = Conflict(
            region_id="region-table-1",
            conflict_type=ConflictType.VALUE_MISMATCH,
            text_value="$7M",
            vision_value="$9M",
            discrepancy_percentage=0.22,
            confidence_scores={
                "text": 0.70,  # Below reasonable threshold
                "vision": 0.65  # Below reasonable threshold
            }
        )
        
        resolutions = resolution_agent.resolve(base_document, [conflict])
        
        assert len(resolutions) == 1
        resolution = resolutions[0]
        assert resolution.chosen_value is None  # No automatic choice
        assert resolution.resolution_method == ResolutionMethod.MANUAL
        assert resolution.confidence == 0.0
        assert ResolutionStrategy.MANUAL_REVIEW_REQUIRED in resolution.notes
    
    def test_strategy_manual_review_massive_discrepancy(self, resolution_agent, base_document):
        """Test Strategy D: Manual review for massive discrepancy."""
        conflict = Conflict(
            region_id="region-table-1",
            conflict_type=ConflictType.VALUE_MISMATCH,
            text_value="$5M",
            vision_value="$15M",
            discrepancy_percentage=0.67,  # > 50% threshold
            confidence_scores={
                "text": 0.85,
                "vision": 0.83
            }
        )
        
        resolutions = resolution_agent.resolve(base_document, [conflict])
        
        assert len(resolutions) == 1
        resolution = resolutions[0]
        assert resolution.chosen_value is None
        assert resolution.resolution_method == ResolutionMethod.MANUAL
        assert "Massive discrepancy" in resolution.notes
    
    def test_multiple_conflicts_different_strategies(self, resolution_agent, base_document):
        """Test resolving multiple conflicts with different strategies."""
        conflicts = [
            # Confidence dominance -> Auto OCR
            Conflict(
                region_id="region-table-1",
                conflict_type=ConflictType.VALUE_MISMATCH,
                text_value="$10M",
                vision_value="$8M",
                discrepancy_percentage=0.20,
                confidence_scores={"text": 0.94, "vision": 0.55}
            ),
            # Manual review -> Low confidence
            Conflict(
                region_id="region-chart-1",
                conflict_type=ConflictType.VALUE_MISMATCH,
                text_value="30%",
                vision_value="35%",
                discrepancy_percentage=0.14,
                confidence_scores={"text": 0.72, "vision": 0.68}
            )
        ]
        
        resolutions = resolution_agent.resolve(base_document, conflicts)
        
        assert len(resolutions) == 2
        # First should be auto-resolved
        assert resolutions[0].resolution_method == ResolutionMethod.AUTO
        assert resolutions[0].chosen_value == "$10M"
        # Second should need manual review
        assert resolutions[1].resolution_method == ResolutionMethod.MANUAL
        assert resolutions[1].chosen_value is None
    
    def test_unknown_region_type_defaults_to_manual(self, resolution_agent, base_document):
        """Test that unknown region types default to manual review when ambiguous."""
        conflict = Conflict(
            region_id="unknown-region-999",  # Non-existent region
            conflict_type=ConflictType.VALUE_MISMATCH,
            text_value="$100",
            vision_value="$120",
            discrepancy_percentage=0.17,
            confidence_scores={
                "text": 0.82,
                "vision": 0.84
            }
        )
        
        resolutions = resolution_agent.resolve(base_document, [conflict])
        
        assert len(resolutions) == 1
        resolution = resolutions[0]
        # No region bias can be applied, both conf reasonable but not high enough for dominance
        assert resolution.resolution_method == ResolutionMethod.MANUAL
