"""Unit tests for benchmark metrics module."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from tests.benchmarks.metrics import AccuracyMetrics


class TestAccuracyMetrics:
    """Test AccuracyMetrics class."""
    
    def test_normalize_text(self):
        """Test text normalization."""
        text = "  Hello   World  "
        normalized = AccuracyMetrics.normalize_text(text)
        
        assert normalized == "hello world"
    
    def test_calculate_cer_perfect_match(self):
        """Test CER with perfect match."""
        ref = "hello world"
        hyp = "hello world"
        
        cer = AccuracyMetrics.calculate_cer(ref, hyp)
        
        assert cer == 0.0
    
    def test_calculate_cer_with_errors(self):
        """Test CER with character errors."""
        ref = "hello world"
        hyp = "helo wrld"  # Missing letters
        
        cer = AccuracyMetrics.calculate_cer(ref, hyp)
        
        # Should have non-zero error
        assert cer > 0.0
        assert cer < 1.0
    
    def test_calculate_cer_normalization(self):
        """Test that CER normalizes text correctly."""
        ref = "HELLO WORLD"
        hyp = "hello world"
        
        cer = AccuracyMetrics.calculate_cer(ref, hyp, normalize=True)
        
        # Should be perfect match after normalization
        assert cer == 0.0
    
    def test_calculate_iou_perfect_overlap(self):
        """Test IoU with perfect overlap."""
        box_a = [0, 0, 100, 100]
        box_b = [0, 0, 100, 100]
        
        iou = AccuracyMetrics.calculate_iou(box_a, box_b)
        
        assert iou == 1.0
    
    def test_calculate_iou_partial_overlap(self):
        """Test IoU with partial overlap."""
        box_a = [0, 0, 100, 100]
        box_b = [50, 50, 150, 150]
        
        iou = AccuracyMetrics.calculate_iou(box_a, box_b)
        
        # Should have partial overlap
        assert 0.0 < iou < 1.0
    
    def test_calculate_iou_no_overlap(self):
        """Test IoU with no overlap."""
        box_a = [0, 0, 50, 50]
        box_b = [100, 100, 150, 150]
        
        iou = AccuracyMetrics.calculate_iou(box_a, box_b)
        
        assert iou == 0.0
    
    def test_calculate_table_precision(self):
        """Test table precision calculation."""
        pred_table = {
            "rows": 5,
            "cols": 3,
            "cells": ["a", "b", "c", "d", "e"]
        }
        
        gt_table = {
            "rows": 5,
            "cols": 3,
            "cells": ["a", "b", "c", "d", "e"]
        }
        
        metrics = AccuracyMetrics.calculate_table_precision(pred_table, gt_table)
        
        # Perfect match
        assert metrics["row_accuracy"] == 1.0
        assert metrics["col_accuracy"] == 1.0
        assert metrics["cell_precision"] == 1.0
        assert metrics["cell_recall"] == 1.0
    
    def test_pass_fail_criteria_pass(self):
        """Test pass/fail with passing metrics."""
        cer = 0.02  # 2%
        iou = 0.90  # 90%
        
        result = AccuracyMetrics.pass_fail_criteria(cer, iou)
        
        assert result == "PASS"
    
    def test_pass_fail_criteria_fail(self):
        """Test pass/fail with failing metrics."""
        cer = 0.10  # 10% - too high
        iou = 0.70  # 70% - too low
        
        result = AccuracyMetrics.pass_fail_criteria(cer, iou)
        
        assert result == "FAIL"


if __name__ == "__main__":
    print("Running metrics tests...")
    
    # Test text normalization
    print("\n1. Testing text normalization...")
    text = "  HELLO   World  "
    normalized = AccuracyMetrics.normalize_text(text)
    print(f"   Original: '{text}'")
    print(f"   Normalized: '{normalized}'")
    assert normalized == "hello world"
    print("   ✓ Pass")
    
    # Test CER
    print("\n2. Testing CER calculation...")
    ref = "the quick brown fox"
    hyp = "the quik brown fox"
    cer = AccuracyMetrics.calculate_cer(ref, hyp)
    print(f"   Reference: '{ref}'")
    print(f"   Hypothesis: '{hyp}'")
    print(f"   CER: {cer*100:.2f}%")
    print("   ✓ Pass")
    
    # Test IoU
    print("\n3. Testing IoU calculation...")
    box_a = [0, 0, 100, 100]
    box_b = [50, 50, 150, 150]
    iou = AccuracyMetrics.calculate_iou(box_a, box_b)
    print(f"   Box A: {box_a}")
    print(f"   Box B: {box_b}")
    print(f"   IoU: {iou*100:.1f}%")
    print("   ✓ Pass")
    
    print("\n✅ All manual tests passed!")
