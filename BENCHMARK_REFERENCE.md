# Benchmark System - Quick Reference

## Overview
Comprehensive accuracy and performance benchmarking system for document processing validation.

## Components

### 1. Metrics Engine (`tests/benchmarks/metrics.py`)
**AccuracyMetrics class** with static methods:

**Text Metrics:**
- `calculate_cer(reference, hypothesis)` - Character Error Rate with normalization
- `calculate_wer(reference, hypothesis)` - Word Error Rate

**Layout Metrics:**
- `calculate_iou(box_a, box_b)` - Intersection over Union (shapely-based)
- `calculate_polygon_iou()` - For rotated bounding boxes

**Table Metrics:**
- `calculate_table_precision(pred, gt)` - Row/col accuracy, cell precision/recall

**Utilities:**
- `normalize_text()` - Lowercase, single spaces, trimmed
- `calculate_batch_statistics()` - Mean, median, std, min, max
- `pass_fail_criteria(cer, iou)` - Default thresholds: CER<5%, IoU>80%

### 2. Dataset Loader (`tests/benchmarks/dataset.py`)
**BenchmarkDataset class:**

**Data Structure:**
```
tests/data/ground_truth/
├── dataset_manifest.json    # Optional file list
├── invoice_001.pdf          # Test document
├── invoice_001.json         # Ground truth
└── ...
```

**Ground Truth JSON Format:**
```json
{
  "file_id": "invoice_001",
  "doc_type": "invoice",
  "text": "Full extracted text...",
  "bounding_boxes": [
    {"text": "...", "box": [x1, y1, x2, y2]}
  ],
  "tables": [{"rows": 5, "cols": 3, "cells": [...]}],
  "metadata": {
    "chart_values": [100, 200, 300],
    "tesseract_cer": 0.08
  }
}
```

**Methods:**
- `load_test_cases(doc_types=None)` - Load all or filtered test cases
- `create_sample_manifest()` - Generate example manifest
- `create_sample_ground_truth(file_id, doc_type)` - Create sample data

### 3. Validation Runner (`tests/benchmarks/run_validation.py`)
**BenchmarkRunner class:**

**Features:**
- WorkflowManager integration for document processing
- Real-time console progress table (tabulate)
- Comprehensive error handling (traceback without stop)
- **Chart validation** with ±10% tolerance
- **Baseline comparison** (Tesseract CER)
- Performance timing (total + per-page)

**Output Reports:**
- `tests/benchmarks/reports/summary_YYYYMMDD_HHMMSS.csv`
- `tests/benchmarks/reports/summary_YYYYMMDD_HHMMSS.json`
- `tests/benchmarks/reports/latest_summary.csv` (overwritten)
- `tests/benchmarks/reports/latest_detailed.json` (overwritten)

**Metrics Tracked:**
| Column | Description |
|--------|-------------|
| file_name | Test document name |
| doc_type | invoice/research_paper/financial |
| page_count | Number of pages |
| processing_time | Total seconds |
| time_per_page | Average per page |
| cer | Character Error Rate (0-1) |
| wer | Word Error Rate|
| iou_mean | Average IoU score (0-1) |
| table_accuracy | Table structure score |
| chart_accuracy | Chart value accuracy (±10%) |
| tesseract_cer | Baseline CER |
| improvement_over_baseline | % improvement vs Tesseract |
| status | PASS/FAIL/ERROR |
| error_message | Error details if failed |

## Usage

### Running Benchmarks
```bash
# Run all test cases
python tests/benchmarks/run_validation.py

# Programmatic usage
from tests.benchmarks import BenchmarkRunner

runner = BenchmarkRunner()
results = runner.run_benchmark(doc_types=["invoice"], max_cases=5)
runner.save_report(results, format="csv")
```

### Console Output Example
```
File                      Type            Time (s)   CER (%)    IoU (%)    Status    
-------------------------------------------------------------------------------------------------
invoice_001.pdf           invoice         2.45       1.20       94.0       ✅ PASS      
research_001.pdf          research_paper  5.12       3.45       87.5       ✅ PASS      
financial_001.pdf         financial       3.89       ERROR      N/A        ⚠️ ERROR     
-------------------------------------------------------------------------------------------------

BENCHMARK SUMMARY
==============================================================================
Total Cases:     3
Passed:          2 (66.7%)
Failed:          0
Errors:          1

Average CER:     2.33%
Average IoU:     90.8%
Average Time:    3.82s per document
Total Time:      11.46s
==============================================================================
```

## Dependencies
```txt
jiwer>=3.0.0         # CER/WER calculation
shapely>=2.0.0       # IoU geometry
scipy>=1.10.0        # Linear sum assignment
pandas>=2.0.0        # Report generation
tabulate>=0.9.0      # Console tables
```

Install: `pip install -r tests/requirements-test.txt`

## Integration with Workflow

The runner automatically:
1. Initializes `WorkflowManager`
2. Calls `workflow.process_document(pdf_path)` for each test case
3. Extracts results (text, layout, tables, charts)
4. Compares against ground truth
5. Generates comprehensive reports

## Special Features

### Chart Validation (±10% Tolerance)
```python
# Ground truth
"chart_values": [100.0, 200.0, 300.0]

# Extracted (simulated): [98.0, 205.0, 295.0]
# Validation: 100±10, 200±20, 300±30
# Result: All within tolerance → 100% accuracy
```

### Baseline Comparison
```python
# If ground truth includes:
"tesseract_cer": 0.08  # 8% CER from Tesseract

# Our system achieves:
cer = 0.05  # 5% CER

# Improvement calculation:
improvement = (0.08 - 0.05) / 0.08 * 100 = 37.5% better
```

## Task Status
- ✅ Task 11.1: Accuracy Testing Suite - **COMPLETE**
- ✅ Task 11.2: Performance Benchmarking - **COMPLETE**

Both marked complete in `.kiro/specs/sovereign-doc/tasks.md`
