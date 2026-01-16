# Demo Scripts - Sovereign-Doc

This directory contains demonstration scripts showcasing various capabilities of the Sovereign-Doc system.

## Available Demos

### 1. Financial Report Analysis (`demo_financial.py`)
Demonstrates conflict detection between OCR and Vision agents when analyzing financial statements.

**Features:**
- Processes financial documents (10-K reports, balance sheets, etc.)
- Highlights conflicts in numeric values
- Shows impact scoring for financial accuracy
- Demonstrates auto-resolution vs. manual review decisions

**Usage:**
```bash
python demos/demo_financial.py path/to/financial_report.pdf
```

### 2. Academic Paper Analysis (`demo_academic.py`)
Showcases vision agent capabilities in analyzing charts, figures, and diagrams.

**Features:**
- Extracts visual summaries from research papers
- Analyzes charts and figures
- Shows region type breakdown (text, image, chart, table)
- Demonstrates text extraction quality metrics

**Usage:**
```bash
python demos/demo_academic.py path/to/research_paper.pdf
```

### 3. Invoice Batch Processing (`demo_invoices.py`)
Demonstrates robust batch processing with error handling and recovery.

**Features:**
- Sequential processing of multiple invoices
- Error isolation (one failure doesn't stop the batch)
- Comprehensive batch summary report
- Performance metrics per document

**Usage:**
```bash
python demos/demo_invoices.py path/to/invoices/folder
```

### 4. Comparative Document Analysis (`demo_comparison.py`)
Shows multi-document querying and cross-document analysis using RAG.

**Features:**
- Processes two documents independently
- Indexes both to vector database
- Runs comparative queries across documents
- Shows synthesized answers with citations

**Usage:**
```bash
python demos/demo_comparison.py doc1.pdf doc2.pdf "Compare revenue between Q3 and Q4"
```

## Setup

All demos use the shared utilities in `utils.py` which provides:
- Environment setup with logging
- Workflow execution wrapper
- Result formatting with tabulate
- Error handling

## Sample Data

Place sample PDFs in `test_data/` directory:
```
test_data/
  ├── sample_financial.pdf
  ├── sample_paper.pdf
  ├── invoices/
  │   ├── invoice_001.pdf
  │   ├── invoice_002.pdf
  │   └── invoice_003.pdf
  └── quarterly_reports/
      ├── q3_report.pdf
      └── q4_report.pdf
```

## Requirements

All demos require:
- `tabulate` - For formatted console output
- `loguru` - For logging
- All core Sovereign-Doc dependencies

Install with:
```bash
pip install -r requirements.txt
```

## Output Examples

All demos produce professionally formatted console output using `tabulate` for tables and clear section headers.

Example output structure:
1. Header banner
2. Processing progress with Loguru logging
3. Summary statistics table
4. Detailed results (conflicts, vision insights, etc.)
5. Final status and recommendations
