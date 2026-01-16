"""Accuracy metrics for document processing benchmarking.

Provides quantitative measurements for:
- Text Accuracy: Character Error Rate (CER)
- Layout Accuracy: Intersection over Union (IoU)
- Table Structure: Row/column precision and recall
"""

import re
from typing import List, Tuple, Dict, Any, Optional
import jiwer
from shapely.geometry import box as shapely_box
from shapely.geometry import Polygon
from loguru import logger


class AccuracyMetrics:
    """Static methods for calculating document processing accuracy metrics."""
    
    @staticmethod
    def normalize_text(text: str) -> str:
        """Normalize text for fair comparison.
        
        Args:
            text: Input text string
            
        Returns:
            Normalized text (lowercase, single spaces, trimmed)
        """
        # Convert to lowercase
        normalized = text.lower()
        
        # Replace multiple spaces with single space
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # Strip leading/trailing whitespace
        normalized = normalized.strip()
        
        return normalized
    
    @staticmethod
    def calculate_cer(reference: str, hypothesis: str, normalize: bool = True) -> float:
        """Calculate Character Error Rate between reference and hypothesis.
        
        CER measures the minimum edit distance (insertions, deletions, substitutions)
        normalized by the length of the reference text.
        
        Args:
            reference: Ground truth text
            hypothesis: Predicted/extracted text
            normalize: Whether to normalize both texts before comparison
            
        Returns:
            CER as a float between 0.0 (perfect) and 1.0+ (very poor)
        """
        if not reference and not hypothesis:
            return 0.0  # Both empty = perfect match
        
        if not reference:
            return 1.0  # No reference = max error
        
        # Normalize if requested
        if normalize:
            reference = AccuracyMetrics.normalize_text(reference)
            hypothesis = AccuracyMetrics.normalize_text(hypothesis)
        
        # Calculate CER using jiwer
        try:
            cer = jiwer.cer(reference, hypothesis)
            return float(cer)
        except Exception as e:
            logger.error(f"CER calculation failed: {e}")
            return 1.0
    
    @staticmethod
    def calculate_wer(reference: str, hypothesis: str, normalize: bool = True) -> float:
        """Calculate Word Error Rate between reference and hypothesis.
        
        Args:
            reference: Ground truth text
            hypothesis: Predicted/extracted text
            normalize: Whether to normalize both texts
            
        Returns:
            WER as a float
        """
        if not reference and not hypothesis:
            return 0.0
        
        if not reference:
            return 1.0
        
        # Normalize if requested
        if normalize:
            reference = AccuracyMetrics.normalize_text(reference)
            hypothesis = AccuracyMetrics.normalize_text(hypothesis)
        
        try:
            wer = jiwer.wer(reference, hypothesis)
            return float(wer)
        except Exception as e:
            logger.error(f"WER calculation failed: {e}")
            return 1.0
    
    @staticmethod
    def calculate_iou(box_a: List[float], box_b: List[float]) -> float:
        """Calculate Intersection over Union for two bounding boxes.
        
        Args:
            box_a: Bounding box [x1, y1, x2, y2]
            box_b: Bounding box [x1, y1, x2, y2]
            
        Returns:
            IoU score between 0.0 (no overlap) and 1.0 (perfect match)
        """
        if len(box_a) != 4 or len(box_b) != 4:
            logger.error(f"Invalid bounding boxes: {box_a}, {box_b}")
            return 0.0
        
        try:
            # Create shapely box objects
            poly_a = shapely_box(box_a[0], box_a[1], box_a[2], box_a[3])
            poly_b = shapely_box(box_b[0], box_b[1], box_b[2], box_b[3])
            
            # Calculate intersection and union
            intersection = poly_a.intersection(poly_b).area
            union = poly_a.union(poly_b).area
            
            if union == 0:
                return 0.0
            
            iou = intersection / union
            return float(iou)
        
        except Exception as e:
            logger.error(f"IoU calculation failed: {e}")
            return 0.0
    
    @staticmethod
    def calculate_polygon_iou(polygon_a: List[Tuple[float, float]], 
                            polygon_b: List[Tuple[float, float]]) -> float:
        """Calculate IoU for polygons (for rotated bounding boxes).
        
        Args:
            polygon_a: List of (x, y) points
            polygon_b: List of (x, y) points
            
        Returns:
            IoU score
        """
        try:
            poly_a = Polygon(polygon_a)
            poly_b = Polygon(polygon_b)
            
            if not poly_a.is_valid or not poly_b.is_valid:
                logger.warning("Invalid polygon detected")
                return 0.0
            
            intersection = poly_a.intersection(poly_b).area
            union = poly_a.union(poly_b).area
            
            if union == 0:
                return 0.0
            
            return float(intersection / union)
        
        except Exception as e:
            logger.error(f"Polygon IoU calculation failed: {e}")
            return 0.0
    
    @staticmethod
    def calculate_table_precision(
        predicted_table: Dict[str, Any],
        ground_truth_table: Dict[str, Any]
    ) -> Dict[str, float]:
        """Calculate table structure accuracy metrics.
        
        Compares:
        - Number of rows detected
        - Number of columns detected
        - Cell-level precision/recall
        
        Args:
            predicted_table: Predicted table structure
                Format: {"rows": int, "cols": int, "cells": List[str]}
            ground_truth_table: Ground truth table structure
                Same format as predicted_table
                
        Returns:
            Dictionary with metrics:
                - row_accuracy: Row count accuracy
                - col_accuracy: Column count accuracy
                - cell_precision: Precision of cell detection
                - cell_recall: Recall of cell detection
                - overall_score: Average of all metrics
        """
        metrics = {
            "row_accuracy": 0.0,
            "col_accuracy": 0.0,
            "cell_precision": 0.0,
            "cell_recall": 0.0,
            "overall_score": 0.0
        }
        
        try:
            # Extract row and column counts
            pred_rows = predicted_table.get("rows", 0)
            pred_cols = predicted_table.get("cols", 0)
            gt_rows = ground_truth_table.get("rows", 0)
            gt_cols = ground_truth_table.get("cols", 0)
            
            # Row accuracy (1 if exact match, scaled by difference otherwise)
            if gt_rows > 0:
                row_diff = abs(pred_rows - gt_rows)
                metrics["row_accuracy"] = max(0.0, 1.0 - (row_diff / gt_rows))
            
            # Column accuracy
            if gt_cols > 0:
                col_diff = abs(pred_cols - gt_cols)
                metrics["col_accuracy"] = max(0.0, 1.0 - (col_diff / gt_cols))
            
            # Cell-level precision/recall
            pred_cells = set(predicted_table.get("cells", []))
            gt_cells = set(ground_truth_table.get("cells", []))
            
            if pred_cells:
                true_positives = len(pred_cells & gt_cells)
                metrics["cell_precision"] = true_positives / len(pred_cells)
            
            if gt_cells:
                true_positives = len(pred_cells & gt_cells)
                metrics["cell_recall"] = true_positives / len(gt_cells)
            
            # Overall score (average of all metrics)
            all_scores = [
                metrics["row_accuracy"],
                metrics["col_accuracy"],
                metrics["cell_precision"],
                metrics["cell_recall"]
            ]
            metrics["overall_score"] = sum(all_scores) / len(all_scores)
            
        except Exception as e:
            logger.error(f"Table precision calculation failed: {e}")
        
        return metrics
    
    @staticmethod
    def calculate_batch_statistics(
        cer_scores: List[float],
        iou_scores: List[float]
    ) -> Dict[str, float]:
        """Calculate aggregate statistics for a batch of documents.
        
        Args:
            cer_scores: List of CER scores
            iou_scores: List of IoU scores
            
        Returns:
            Dictionary with mean, median, std, min, max for each metric
        """
        import statistics
        
        stats = {}
        
        # CER statistics
        if cer_scores:
            stats["cer_mean"] = statistics.mean(cer_scores)
            stats["cer_median"] = statistics.median(cer_scores)
            stats["cer_std"] = statistics.stdev(cer_scores) if len(cer_scores) > 1 else 0.0
            stats["cer_min"] = min(cer_scores)
            stats["cer_max"] = max(cer_scores)
        else:
            stats["cer_mean"] = 0.0
            stats["cer_median"] = 0.0
            stats["cer_std"] = 0.0
            stats["cer_min"] = 0.0
            stats["cer_max"] = 0.0
        
        # IoU statistics
        if iou_scores:
            stats["iou_mean"] = statistics.mean(iou_scores)
            stats["iou_median"] = statistics.median(iou_scores)
            stats["iou_std"] = statistics.stdev(iou_scores) if len(iou_scores) > 1 else 0.0
            stats["iou_min"] = min(iou_scores)
            stats["iou_max"] = max(iou_scores)
        else:
            stats["iou_mean"] = 0.0
            stats["iou_median"] = 0.0
            stats["iou_std"] = 0.0
            stats["iou_min"] = 0.0
            stats["iou_max"] = 0.0
        
        return stats
    
    @staticmethod
    def pass_fail_criteria(cer: float, iou: float, 
                          cer_threshold: float = 0.05,
                          iou_threshold: float = 0.80) -> str:
        """Determine if metrics pass quality thresholds.
        
        Args:
            cer: Character Error Rate
            iou: Intersection over Union
            cer_threshold: Maximum acceptable CER (default: 5%)
            iou_threshold: Minimum acceptable IoU (default: 80%)
            
        Returns:
            "PASS" or "FAIL"
        """
        if cer <= cer_threshold and iou >= iou_threshold:
            return "PASS"
        return "FAIL"
