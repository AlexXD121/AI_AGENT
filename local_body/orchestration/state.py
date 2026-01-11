"""State definitions for LangGraph workflow system.

This module defines the DocumentProcessingState TypedDict that flows
through the multi-agent processing pipeline.
"""

from typing import TypedDict, List, Dict, Any, Optional, Annotated
from operator import add

from local_body.core.datamodels import Document, Region, Conflict, ConflictResolution


# Use Annotated with add reducer for fields that multiple nodes update
class DocumentProcessingState(TypedDict):
    """State structure for document processing workflow.
    
    This state flows through the multi-agent pipeline and tracks
    all intermediate results, conflicts, and resolutions.
    
    Attributes:
        document: The Document object being processed
        file_path: Original file path
        processing_stage: Current pipeline stage (single writer)
        layout_regions: YOLO-detected layout regions
        ocr_results: Raw OCR extraction results
        vision_results: Raw vision model results
        conflicts: Detected conflicts between sources
        resolutions: Applied conflict resolutions
        error_log: Processing error audit trail (reducer: concatenate)
    """
    
    # Core document
    document: Document
    file_path: str
    
    # Processing state (single value - last writer wins)
    processing_stage: str
    
    # Agent results (reducers allow multiple writes)
    layout_regions: Annotated[List[Region], add]  # Concatenate regions
    ocr_results: Dict[str, Any]
    vision_results: Dict[str, Any]
    
    # Conflict management (reducers)
    conflicts: Annotated[List[Conflict], add]  # Concatenate conflicts
    resolutions: Annotated[List[ConflictResolution], add]  # Concatenate resolutions
    
    # Error tracking (reducer)
    error_log: Annotated[List[str], add]  # Concatenate errors


# Processing stage constants
class ProcessingStage:
    """Constants for processing stages."""
    INGEST = "ingest"
    LAYOUT = "layout"
    OCR = "ocr"
    VISION = "vision"
    CONFLICT = "conflict"
    AUTO_RESOLVED = "auto_resolved"
    HUMAN_REVIEW = "human_review"
    COMPLETE = "complete"
    FAILED = "failed"
