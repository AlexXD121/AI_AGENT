"""Demo utilities for Sovereign-Doc demonstration scripts.

This module provides helper functions to reduce boilerplate in demo scripts.
"""

import sys
from pathlib import Path
from typing import Dict, Any

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger
from tabulate import tabulate

from local_body.core.config_manager import ConfigManager
from local_body.utils.document_loader import DocumentLoader
from local_body.orchestration.workflow import DocumentWorkflow
from local_body.orchestration.state import ProcessingStage


def setup_demo_env() -> Dict[str, Any]:
    """Initialize demo environment with logging and configuration.
    
    Returns:
        Dictionary containing config and other setup data
    """
    # Configure logger for demos
    logger.remove()  # Remove default handler
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO"
    )
    
    # Load system configuration
    config = ConfigManager().load_config()
    
    logger.info("Demo environment initialized")
    
    return {
        "config": config,
        "project_root": project_root
    }


def print_header(title: str, width: int = 80) -> None:
    """Print a formatted header for demo output.
    
    Args:
        title: Header title text
        width: Total width of header (default: 80)
    """
    border = "=" * width
    padding = (width - len(title) - 2) // 2
    header = f"{border}\n{' ' * padding} {title}\n{border}"
    
    print("\n" + header + "\n")


def print_result_summary(state: Dict[str, Any]) -> None:
    """Print a summary of workflow results using tabulate.
    
    Args:
        state: DocumentProcessingState dictionary
    """
    print("\n📊 Processing Summary:")
    print("=" * 60)
    
    # Extract key metrics
    document = state.get('document')
    ocr_results = state.get('ocr_results', {})
    vision_results = state.get('vision_results', {})
    conflicts = state.get('conflicts', [])
    resolutions = state.get('resolutions', [])
    layout_regions = state.get('layout_regions', [])
    
    # Calculate confidence scores
    ocr_conf = ocr_results.get('avg_confidence', 0.0)
    vision_conf = vision_results.get('avg_confidence', 0.0)
    avg_conf = (ocr_conf + vision_conf) / 2 if (ocr_conf or vision_conf) else 0.0
    
    # Create summary table
    summary_data = [
        ["Document", document.file_path if document else "N/A"],
        ["Pages Processed", len(document.pages) if document and hasattr(document, 'pages') else 0],
        ["Processing Stage", state.get('processing_stage', 'unknown')],
        ["Average Confidence", f"{avg_conf:.1%}"],
        ["Layout Regions Detected", len(layout_regions)],
        ["Conflicts Detected", len(conflicts)],
        ["Conflicts Resolved", len(resolutions)],
        ["Errors", len(state.get('error_log', []))]
    ]
    
    print(tabulate(summary_data, headers=["Metric", "Value"], tablefmt="grid"))
    print()


def run_workflow(file_path: str) -> Dict[str, Any]:
    """Execute the complete document processing workflow.
    
    This is a convenience wrapper that handles:
    - Document loading
    - State initialization
    - Workflow execution
    - Error handling
    
    Args:
        file_path: Path to PDF document
        
    Returns:
        Final DocumentProcessingState dictionary
        
    Raises:
        FileNotFoundError: If file doesn't exist
        Exception: If workflow fails
    """
    logger.info(f"Starting workflow for: {file_path}")
    
    # Verify file exists
    if not Path(file_path).exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    # Load document
    logger.info("Loading document...")
    loader = DocumentLoader()
    document = loader.load_document(file_path)
    
    # Create initial state
    initial_state = {
        'document': document,
        'file_path': file_path,
        'processing_stage': ProcessingStage.INGEST,
        'layout_regions': [],
        'ocr_results': {},
        'vision_results': {},
        'conflicts': [],
        'resolutions': [],
        'error_log': []
    }
    
    # Execute workflow
    logger.info("Executing multi-agent workflow...")
    workflow = DocumentWorkflow()
    
    try:
        result_state = workflow.run(initial_state)
        logger.success(f"Workflow completed: {result_state.get('processing_stage')}")
        return result_state
        
    except Exception as e:
        logger.error(f"Workflow failed: {e}")
        raise


def print_conflicts_report(conflicts: list) -> None:
    """Print a detailed conflict resolution report.
    
    Args:
        conflicts: List of Conflict objects
    """
    if not conflicts:
        print("\n✅ No conflicts detected - all extractions matched!\n")
        return
    
    print(f"\n⚠️  Conflict Resolution Report ({len(conflicts)} conflicts):")
    print("=" * 80)
    
    conflict_data = []
    for idx, conflict in enumerate(conflicts, 1):
        # Extract conflict details
        conflict_type = getattr(conflict, 'conflict_type', 'Unknown')
        source_a = getattr(conflict, 'source_a', 'OCR')
        source_b = getattr(conflict, 'source_b', 'Vision')
        value_a = getattr(conflict, 'value_a', 'N/A')
        value_b = getattr(conflict, 'value_b', 'N/A')
        impact = getattr(conflict, 'impact_score', 0.0)
        
        conflict_data.append([
            f"#{idx}",
            conflict_type,
            f"{source_a}: {value_a}",
            f"{source_b}: {value_b}",
            f"{impact:.2f}"
        ])
    
    print(tabulate(
        conflict_data,
        headers=["ID", "Type", "Source A", "Source B", "Impact"],
        tablefmt="grid"
    ))
    print()


def print_vision_insights(vision_results: Dict[str, Any]) -> None:
    """Print vision analysis insights.
    
    Args:
        vision_results: Vision results dictionary
    """
    print("\n👁️  Vision Analysis Insights:")
    print("=" * 60)
    
    if not vision_results:
        print("No vision analysis available.\n")
        return
    
    # Extract visual summaries
    summaries = vision_results.get('visual_summaries', [])
    
    if summaries:
        for idx, summary in enumerate(summaries, 1):
            print(f"\nFigure {idx}:")
            print(f"  Description: {summary.get('description', 'N/A')}")
            print(f"  Confidence: {summary.get('confidence', 0.0):.1%}")
            
            # Show extracted values if available
            values = summary.get('extracted_values', {})
            if values:
                print("  Extracted Values:")
                for key, val in values.items():
                    print(f"    - {key}: {val}")
    else:
        print("No visual elements analyzed.\n")


def print_batch_report(results: list) -> None:
    """Print a batch processing report.
    
    Args:
        results: List of dicts with keys: filename, status, time, confidence
    """
    print("\n📦 Batch Processing Report:")
    print("=" * 80)
    
    # Prepare data for table
    table_data = []
    total_time = 0
    success_count = 0
    
    for result in results:
        table_data.append([
            result['filename'],
            result['status'],
            f"{result['time']:.1f}s",
            f"{result.get('confidence', 0.0):.1%}" if result['status'] == 'Success' else 'N/A'
        ])
        
        total_time += result['time']
        if result['status'] == 'Success':
            success_count += 1
    
    print(tabulate(
        table_data,
        headers=["Filename", "Status", "Time", "Confidence"],
        tablefmt="grid"
    ))
    
    # Print summary stats
    print(f"\n📊 Batch Summary:")
    print(f"  Total Documents: {len(results)}")
    print(f"  Successful: {success_count}")
    print(f"  Failed: {len(results) - success_count}")
    print(f"  Total Time: {total_time:.1f}s")
    print(f"  Average Time: {total_time / len(results):.1f}s per document\n")
