"""Benchmarking and accuracy validation module.

Provides tools for measuring:
- Text accuracy (CER, WER)
- Layout accuracy (IoU)
- Table structure precision
- Performance benchmarks
"""

from tests.benchmarks.metrics import AccuracyMetrics
from tests.benchmarks.dataset import BenchmarkDataset, TestCase, GroundTruth
from tests.benchmarks.run_validation import BenchmarkRunner, BenchmarkResult

__all__ = [
    "AccuracyMetrics",
    "BenchmarkDataset",
    "TestCase",
    "GroundTruth",
    "BenchmarkRunner",
    "BenchmarkResult",
]
