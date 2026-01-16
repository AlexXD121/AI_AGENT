"""Invoice Batch Processing Demo.

Demonstrates robust batch processing with error handling and recovery.
Processes multiple invoices sequentially and generates a summary report.

Usage:
    python demos/demo_invoices.py [path/to/invoices/folder]
"""

import sys
import time
from pathlib import Path

from utils import (
    setup_demo_env,
    print_header,
    run_workflow,
    print_batch_report
)

from loguru import logger


def process_batch(invoice_dir: Path) -> list:
    """Process all PDFs in a directory.
    
    Args:
        invoice_dir: Directory containing PDF invoices
        
    Returns:
        List of processing results
    """
    # Find all PDFs
    pdf_files = list(invoice_dir.glob("*.pdf"))
    
    if not pdf_files:
        logger.warning(f"No PDF files found in {invoice_dir}")
        return []
    
    logger.info(f"Found {len(pdf_files)} invoice(s) to process")
    
    results = []
    
    for idx, pdf_path in enumerate(pdf_files, 1):
        logger.info(f"\n[{idx}/{len(pdf_files)}] Processing: {pdf_path.name}")
        
        start_time = time.time()
        
        try:
            # Process invoice
            result_state = run_workflow(str(pdf_path))
            
            # Calculate processing time
            processing_time = time.time() - start_time
            
            # Extract confidence
            ocr_conf = result_state.get('ocr_results', {}).get('avg_confidence', 0.0)
            vision_conf = result_state.get('vision_results', {}).get('avg_confidence', 0.0)
            avg_conf = (ocr_conf + vision_conf) / 2 if (ocr_conf or vision_conf) else 0.0
            
            # Record success
            results.append({
                'filename': pdf_path.name,
                'status': 'Success',
                'time': processing_time,
                'confidence': avg_conf,
                'conflicts': len(result_state.get('conflicts', []))
            })
            
            logger.success(f"✓ Processed {pdf_path.name} in {processing_time:.1f}s")
            
        except Exception as e:
            # Record failure but continue
            processing_time = time.time() - start_time
            
            results.append({
                'filename': pdf_path.name,
                'status': f'Failed: {str(e)[:50]}',
                'time': processing_time,
                'confidence': 0.0,
                'conflicts': 0
            })
            
            logger.error(f"✗ Failed to process {pdf_path.name}: {e}")
            # Continue to next file instead of crashing
    
    return results


def main():
    """Run invoice batch processing demo."""
    
    # Setup
    env = setup_demo_env()
    print_header("INVOICE BATCH PROCESSING DEMO")
    
    # Get directory path
    if len(sys.argv) > 1:
        invoice_dir = Path(sys.argv[1])
    else:
        invoice_dir = Path(env['project_root']) / "test_data" / "invoices"
    
    if not invoice_dir.exists():
        logger.error(f"Directory not found: {invoice_dir}")
        logger.info("Usage: python demos/demo_invoices.py <directory_path>")
        logger.info("Or place invoice PDFs in: test_data/invoices/")
        return 1
    
    logger.info(f"Processing invoices from: {invoice_dir}")
    
    print("""
📦 Batch Processing Features:
  ✓ Sequential processing of multiple documents
  ✓ Error isolation - one failure doesn't stop the batch
  ✓ Detailed progress logging
  ✓ Comprehensive summary report
  ✓ Performance metrics per document
""")
    
    try:
        # Process all invoices
        results = process_batch(invoice_dir)
        
        if not results:
            logger.warning("No documents were processed")
            return 1
        
        # Print batch report
        print_batch_report(results)
        
        # Highlight conflict detection across batch
        total_conflicts = sum(r.get('conflicts', 0) for r in results if r['status'] == 'Success')
        if total_conflicts > 0:
            print(f"⚠️  Total Conflicts Detected Across Batch: {total_conflicts}")
            print("   → Review high-impact conflicts for data accuracy\n")
        
        # Success rate
        success_count = sum(1 for r in results if r['status'] == 'Success')
        success_rate = success_count / len(results) * 100
        
        print(f"📊 Success Rate: {success_rate:.1f}% ({success_count}/{len(results)})")
        
        if success_rate == 100:
            print("   ✅ Perfect! All invoices processed successfully")
        elif success_rate >= 80:
            print("   ✓ Good - Most invoices processed successfully")
        else:
            print("   ⚠️  Some invoices failed - review errors above")
        
        print()
        logger.success("Batch processing demo complete!")
        return 0
        
    except Exception as e:
        logger.error(f"Batch processing failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
