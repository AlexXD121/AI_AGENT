"""Test suite for Conflict models and methods.

This module tests the Conflict class's value normalization, impact score
calculation, and state transition methods.
"""

import pytest
from datetime import datetime

from local_body.core.datamodels import (
    Conflict, ConflictType, ConflictResolution, ResolutionStatus, ResolutionMethod
)


class TestConflictNormalization:
    """Test value normalization functionality."""
    
    def test_normalize_currency_with_millions(self):
        """Test normalization of currency values with M suffix."""
        assert Conflict.normalize_value("$1.5M") == 1_500_000.0
        assert Conflict.normalize_value("$5.2M") == 5_200_000.0
        assert Conflict.normalize_value("€3.7M") == 3_700_000.0
    
    def test_normalize_currency_with_billions(self):
        """Test normalization of currency values with B suffix."""
        assert Conflict.normalize_value("$1.5B") == 1_500_000_000.0
        assert Conflict.normalize_value("£2.3B") == 2_300_000_000.0
    
    def test_normalize_currency_with_thousands(self):
        """Test normalization of currency values with K suffix."""
        assert Conflict.normalize_value("$50K") == 50_000.0
        assert Conflict.normalize_value("25k") == 25_000.0
    
    def test_normalize_comma_separated_numbers(self):
        """Test normalization of comma-separated numbers."""
        assert Conflict.normalize_value("1,234,567") == 1_234_567.0
        assert Conflict.normalize_value("$1,234.56") == 1_234.56
        assert Conflict.normalize_value("5,200,000") == 5_200_000.0
    
    def test_normalize_percentages(self):
        """Test normalization of percentage values."""
        assert Conflict.normalize_value("15%") == 0.15
        assert Conflict.normalize_value("100%") == 1.0
        assert Conflict.normalize_value("0.5%") == 0.005
    
    def test_normalize_plain_numbers(self):
        """Test normalization of plain numeric values."""
        assert Conflict.normalize_value(1234) == 1234.0
        assert Conflict.normalize_value(56.78) == 56.78
        assert Conflict.normalize_value("9876") == 9876.0
        assert Conflict.normalize_value("123.45") == 123.45
    
    def test_normalize_none_and_empty(self):
        """Test normalization of None and empty strings."""
        assert Conflict.normalize_value(None) == 0.0
        assert Conflict.normalize_value("") == 0.0
        assert Conflict.normalize_value("   ") == 0.0
    
    def test_normalize_invalid_value(self):
        """Test that invalid values raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            Conflict.normalize_value("not a number")
        assert "Cannot convert" in str(exc_info.value)
        
        with pytest.raises(ValueError):
            Conflict.normalize_value("abc%")
    
    def test_normalize_mixed_formats(self):
        """Test normalization of various mixed formats."""
        assert Conflict.normalize_value("$5.2M") == 5_200_000.0
        assert Conflict.normalize_value("  $1,234.56  ") == 1_234.56
        assert Conflict.normalize_value("¥100K") == 100_000.0


class TestConflictImpactScore:
    """Test impact score calculation."""
    
    def test_impact_score_table_high_discrepancy_high_confidence(self):
        """Test impact score for table with high discrepancy and confidence."""
        conflict = Conflict(
            region_id="region-1",
            conflict_type=ConflictType.VALUE_MISMATCH,
            text_value=100,
            vision_value=120,
            discrepancy_percentage=0.20,  # 20% discrepancy
            confidence_scores={"text": 0.85, "vision": 0.90}  # Both > 0.7
        )
        
        # Base: 1.0 (table) * 0.20 (discrepancy) * 1.5 (high confidence) = 0.30
        impact = conflict.update_impact_score("table")
        assert impact == pytest.approx(0.30, rel=0.01)
        assert conflict.impact_score == pytest.approx(0.30, rel=0.01)
    
    def test_impact_score_text_region_low_confidence(self):
        """Test impact score for text region with low confidence."""
        conflict = Conflict(
            region_id="region-2",
            conflict_type=ConflictType.VALUE_MISMATCH,
            text_value=50,
            vision_value=55,
            discrepancy_percentage=0.10,  # 10% discrepancy
            confidence_scores={"text": 0.60, "vision": 0.65}  # Both < 0.7
        )
        
        # Base: 0.5 (text) * 0.10 (discrepancy) * 1.0 (no boost) = 0.05
        impact = conflict.update_impact_score("text")
        assert impact == pytest.approx(0.05, rel=0.01)
    
    def test_impact_score_chart_high_confidence(self):
        """Test impact score for chart with high confidence."""
        conflict = Conflict(
            region_id="region-3",
            conflict_type=ConflictType.VALUE_MISMATCH,
            text_value=1000,
            vision_value=1150,
            discrepancy_percentage=0.15,  # 15% discrepancy
            confidence_scores={"text": 0.75, "vision": 0.80}  # Both > 0.7
        )
        
        # Base: 0.5 (chart) * 0.15 (discrepancy) * 1.5 (high confidence) = 0.1125
        impact = conflict.update_impact_score("chart")
        assert impact == pytest.approx(0.1125, rel=0.01)
    
    def test_impact_score_table_full_discrepancy(self):
        """Test impact score with 100% discrepancy."""
        conflict = Conflict(
            region_id="region-4",
            conflict_type=ConflictType.VALUE_MISMATCH,
            text_value=100,
            vision_value=200,
            discrepancy_percentage=1.0,  # 100% discrepancy
            confidence_scores={"text": 0.90, "vision": 0.95}
        )
        
        # Base: 1.0 (table) * 1.0 (discrepancy) * 1.5 (high confidence) = 1.5
        # But capped at 1.0
        impact = conflict.update_impact_score("table")
        assert impact == 1.0  # Capped
        assert conflict.impact_score == 1.0
    
    def test_impact_score_mixed_confidence(self):
        """Test impact score when only one confidence is high."""
        conflict = Conflict(
            region_id="region-5",
            conflict_type=ConflictType.VALUE_MISMATCH,
            text_value=75,
            vision_value=90,
            discrepancy_percentage=0.20,
            confidence_scores={"text": 0.80, "vision": 0.60}  # Only text > 0.7
        )
        
        # Base: 0.5 * 0.20 * 1.0 (no boost) = 0.10
        impact = conflict.update_impact_score("image")
        assert impact == pytest.approx(0.10, rel=0.01)
    
    def test_impact_score_updates_field(self):
        """Test that impact score is stored in the conflict object."""
        conflict = Conflict(
            region_id="region-6",
            conflict_type=ConflictType.VALUE_MISMATCH,
            text_value=100,
            vision_value=110,
            discrepancy_percentage=0.10,
            confidence_scores={"text": 0.70, "vision": 0.65}
        )
        
        # Initial impact score should be 0.0
        assert conflict.impact_score == 0.0
        
        # After update, should be calculated
        conflict.update_impact_score("table")
        assert conflict.impact_score > 0.0


class TestConflictStateTransitions:
    """Test conflict state transition methods."""
    
    def test_resolve_conflict(self):
        """Test resolving a conflict."""
        conflict = Conflict(
            region_id="region-1",
            conflict_type=ConflictType.VALUE_MISMATCH,
            text_value=100,
            vision_value=105,
            discrepancy_percentage=0.05,
            confidence_scores={"text": 0.80, "vision": 0.85}
        )
        
        # Initially pending
        assert conflict.resolution_status == ResolutionStatus.PENDING
        assert conflict.resolution_method is None
        
        # Create resolution
        resolution = ConflictResolution(
            conflict_id=conflict.id,
            chosen_value=105,
            resolution_method=ResolutionMethod.AUTO,
            confidence=0.85
        )
        
        # Resolve the conflict
        conflict.resolve(resolution)
        
        # Check status updated
        assert conflict.resolution_status == ResolutionStatus.RESOLVED
        assert conflict.resolution_method == ResolutionMethod.AUTO
    
    def test_resolve_with_manual_override(self):
        """Test resolving with manual user override."""
        conflict = Conflict(
            region_id="region-2",
            conflict_type=ConflictType.VALUE_MISMATCH,
            text_value=50,
            vision_value=60,
            discrepancy_percentage=0.20,
            confidence_scores={"text": 0.70, "vision": 0.75}
        )
        
        resolution = ConflictResolution(
            conflict_id=conflict.id,
            chosen_value=55,  # User chose different value
            resolution_method=ResolutionMethod.USER_OVERRIDE,
            user_id="user-123",
            confidence=1.0,
            notes="User manually verified the correct value"
        )
        
        conflict.resolve(resolution)
        
        assert conflict.resolution_status == ResolutionStatus.RESOLVED
        assert conflict.resolution_method == ResolutionMethod.USER_OVERRIDE
    
    def test_flag_conflict(self):
        """Test flagging a conflict for manual review."""
        conflict = Conflict(
            region_id="region-3",
            conflict_type=ConflictType.CONFIDENCE_LOW,
            text_value=100,
            vision_value=150,
            discrepancy_percentage=0.50,
            confidence_scores={"text": 0.40, "vision": 0.45}  # Low confidence
        )
        
        # Initially pending
        assert conflict.resolution_status == ResolutionStatus.PENDING
        
        # Flag for review
        conflict.flag(reason="Both confidence scores too low")
        
        # Check status updated
        assert conflict.resolution_status == ResolutionStatus.FLAGGED
    
    def test_flag_without_reason(self):
        """Test flagging without providing a reason."""
        conflict = Conflict(
            region_id="region-4",
            conflict_type=ConflictType.METHOD_DISAGREEMENT,
            text_value=200,
            vision_value=250,
            discrepancy_percentage=0.25,
            confidence_scores={"text": 0.65, "vision": 0.70}
        )
        
        conflict.flag()  # No reason provided
        
        assert conflict.resolution_status == ResolutionStatus.FLAGGED
    
    def test_multiple_state_transitions(self):
        """Test that conflicts can transition between states."""
        conflict = Conflict(
            region_id="region-5",
            conflict_type=ConflictType.VALUE_MISMATCH,
            text_value=100,
            vision_value=110,
            discrepancy_percentage=0.10,
            confidence_scores={"text": 0.80, "vision": 0.85}
        )
        
        # Start as pending
        assert conflict.resolution_status == ResolutionStatus.PENDING
        
        # Flag it first
        conflict.flag()
        assert conflict.resolution_status == ResolutionStatus.FLAGGED
        
        # Then resolve it
        resolution = ConflictResolution(
            conflict_id=conflict.id,
            chosen_value=110,
            resolution_method=ResolutionMethod.MANUAL,
            confidence=0.90
        )
        conflict.resolve(resolution)
        assert conflict.resolution_status == ResolutionStatus.RESOLVED


class TestConflictIntegration:
    """Integration tests combining multiple conflict features."""
    
    def test_complete_conflict_workflow(self):
        """Test a complete conflict detection and resolution workflow."""
        # Create conflict with normalized values
        text_val = Conflict.normalize_value("$5.2M")
        vision_val = Conflict.normalize_value("$5.0M")
        
        # Calculate discrepancy
        discrepancy = abs(text_val - vision_val) / max(text_val, vision_val)
        
        conflict = Conflict(
            region_id="financial-table-1",
            conflict_type=ConflictType.VALUE_MISMATCH,
            text_value=text_val,
            vision_value=vision_val,
            discrepancy_percentage=discrepancy,
            confidence_scores={"text": 0.88, "vision": 0.92}
        )
        
        # Calculate impact score
        impact = conflict.update_impact_score("table")
        assert impact > 0.0
        
        # Resolve the conflict
        resolution = ConflictResolution(
            conflict_id=conflict.id,
            chosen_value=vision_val,
            resolution_method=ResolutionMethod.AUTO,
            confidence=0.92,
            notes="Vision model had higher confidence"
        )
        
        conflict.resolve(resolution)
        
        # Verify final state
        assert conflict.resolution_status == ResolutionStatus.RESOLVED
        assert conflict.impact_score > 0.0
        assert conflict.text_value == 5_200_000.0
        assert conflict.vision_value == 5_000_000.0
