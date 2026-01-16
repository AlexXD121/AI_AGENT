"""Financial Report Analysis Demo.

Demonstrates conflict detection between OCR and Vision agents when analyzing
financial statements and tables.

Usage:
    python demos/demo_financial.py [path/to/financial_report.pdf]
"""

import sys
from pathlib import Path

# Import demo utilities
from utils import (
    setup_demo_env,
    print_header,
    print_result_summary,
    run_workflow,
    print_conflicts_report
)

from loguru import logger


def main():
    """Run financial report analysis demo."""
    
    # Setup
    env = setup_demo_env()
    print_header("FINANCIAL REPORT ANALYSIS DEMO")
    
    # Get file path from argument or use sample
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        # Use sample file if exists
        sample_path = Path(env['project_root']) / "test_data" / "sample_financial.pdf"
        if sample_path.exists():
            file_path = str(sample_path)
        else:
            logger.error("No file provided. Usage: python demos/demo_financial.py <pdf_path>")
            logger.info("Or place a sample PDF at: test_data/sample_financial.pdf")
            return 1
    
    logger.info(f"Analyzing financial report: {file_path}")
    
    try:
        # Run workflow
        result_state = run_workflow(file_path)
        
        # Print summary
        print_result_summary(result_state)
        
        # Highlight: Financial documents often have conflicts in numeric values
        conflicts = result_state.get('conflicts', [])
        
        print("\n" + "="*80)
        print("🔍 CONFLICT ANALYSIS - Critical for Financial Accuracy")
        print("="*80)
        
        if conflicts:
            print(f"""
In financial documents, even small discrepancies can be significant.
The system detected {len(conflicts)} conflict(s) where OCR and Vision disagree.

Common causes:
  - Handwritten annotations vs. printed text
  - Similar-looking numbers (5 vs S, 0 vs O)
  - Table cell alignment issues
  - Currency symbols near numbers
""")
            
            print_conflicts_report(conflicts)
            
            # Show specific examples
            print("\n💡 Example Scenarios:\n")
            for idx, conflict in enumerate(conflicts[:3], 1):  # Show first 3
                source_a = getattr(conflict, 'source_a', 'OCR')
                source_b = getattr(conflict, 'source_b', 'Vision')
                value_a = getattr(conflict, 'value_a', 'N/A')
                value_b = getattr(conflict, 'value_b', 'N/A')
                impact = getattr(conflict, 'impact_score', 0.0)
                
                print(f"  Conflict #{idx}:")
                print(f"    {source_a} read: '{value_a}'")
                print(f"    {source_b} saw: '{value_b}'")
                print(f"    Impact: {'HIGH' if impact > 0.7 else 'MEDIUM' if impact > 0.4 else 'LOW'}")
                print(f"    → Recommendation: {'Manual review required' if impact > 0.7 else 'Auto-resolve with higher confidence'}")
                print()
        else:
            print("""
✅ No conflicts detected!

All OCR and Vision extractions matched perfectly.
This indicates:
  - High-quality document scan
  - Clear printing/typography
  - No ambiguous characters
  - Consistent table formatting
""")
        
        # Show resolution status
        resolutions = result_state.get('resolutions', [])
        if resolutions:
            print(f"\n✅ {len(resolutions)} conflict(s) automatically resolved\n")
        
        logger.success("Financial analysis demo complete!")
        return 0
        
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
