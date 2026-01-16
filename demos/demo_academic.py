"""Academic Paper Analysis Demo.

Demonstrates vision agent capabilities in analyzing charts, figures, and
diagrams in research papers.

Usage:
    python demos/demo_academic.py [path/to/research_paper.pdf]
"""

import sys
from pathlib import Path

from utils import (
    setup_demo_env,
    print_header,
    print_result_summary,
    run_workflow,
    print_vision_insights
)

from loguru import logger


def main():
    """Run academic paper analysis demo."""
    
    # Setup
    env = setup_demo_env()
    print_header("ACADEMIC PAPER ANALYSIS DEMO")
    
    # Get file path
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        sample_path = Path(env['project_root']) / "test_data" / "sample_paper.pdf"
        if sample_path.exists():
            file_path = str(sample_path)
        else:
            logger.error("No file provided. Usage: python demos/demo_academic.py <pdf_path>")
            logger.info("Or place a sample PDF at: test_data/sample_paper.pdf")
            return 1
    
    logger.info(f"Analyzing research paper: {file_path}")
    
    try:
        # Run workflow
        result_state = run_workflow(file_path)
        
        # Print summary
        print_result_summary(result_state)
        
        # Highlight: Vision analysis for charts and figures
        vision_results = result_state.get('vision_results', {})
        
        print("\n" + "="*80)
        print("👁️  VISION AGENT ANALYSIS - Charts & Figures")
        print("="*80)
        
        print("""
Academic papers often contain complex visual elements:
  - Line charts showing trends
  - Bar graphs comparing results
  - Diagrams illustrating concepts
  - Tables with experimental data

The Vision Agent analyzes these elements and extracts:
  - Descriptions of what the visual shows
  - Numeric values from axes and data points
  - Relationships between elements
""")
        
        print_vision_insights(vision_results)
        
        # Show region breakdown
        layout_regions = result_state.get('layout_regions', [])
        
        if layout_regions:
            print("\n📐 Layout Analysis:")
            print("="*60)
            
            # Count region types
            region_counts = {}
            for region in layout_regions:
                region_type = getattr(region, 'region_type', 'unknown')
                region_type = region_type.value if hasattr(region_type, 'value') else str(region_type)
                region_counts[region_type] = region_counts.get(region_type, 0) + 1
            
            for region_type, count in region_counts.items():
                print(f"  {region_type.title()}: {count}")
            print()
        
        # OCR confidence for text regions
        ocr_results = result_state.get('ocr_results', {})
        ocr_conf = ocr_results.get('avg_confidence', 0.0)
        
        if ocr_conf > 0:
            print(f"📖 Text Extraction Quality: {ocr_conf:.1%} confidence")
            if ocr_conf > 0.9:
                print("   ✅ Excellent - High-quality text extraction")
            elif ocr_conf > 0.7:
                print("   ⚠️  Good - Minor improvements possible")
            else:
                print("   ❌ Fair - Consider rescanning document")
            print()
        
        logger.success("Academic paper analysis demo complete!")
        return 0
        
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
