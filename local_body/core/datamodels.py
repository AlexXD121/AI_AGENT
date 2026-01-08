"""Core data models for Sovereign-Doc document processing system.

This module defines the Pydantic models for representing documents, pages, regions,
conflicts, and related data structures used throughout the system.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class BoundingBox(BaseModel):
    """Represents a rectangular bounding box in a document."""
    
    x: float = Field(..., description="X coordinate of top-left corner")
    y: float = Field(..., description="Y coordinate of top-left corner")
    width: float = Field(..., ge=0, description="Width of the bounding box")
    height: float = Field(..., ge=0, description="Height of the bounding box")
    
    @field_validator('x', 'y')
    @classmethod
    def validate_coordinates(cls, v: float) -> float:
        """Ensure coordinates are non-negative."""
        if v < 0:
            raise ValueError("Coordinates must be non-negative")
        return v


class RegionType(str, Enum):
    """Types of regions that can be detected in a document."""
    
    TEXT = "text"
    TABLE = "table"
    IMAGE = "image"
    CHART = "chart"


class TextContent(BaseModel):
    """Represents extracted text content from a region."""
    
    text: str = Field(..., description="Extracted text content")
    language: Optional[str] = Field(default="en", description="Detected language code")
    confidence: float = Field(..., ge=0.0, le=1.0, description="OCR confidence score")


class TableContent(BaseModel):
    """Represents extracted table content with structure preservation."""
    
    rows: List[List[str]] = Field(..., description="Table data as 2D array")
    headers: Optional[List[str]] = Field(default=None, description="Table column headers")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Table detection confidence")


class ImageContent(BaseModel):
    """Represents image or chart content with vision analysis."""
    
    description: str = Field(..., description="Vision model description of the image")
    extracted_values: Optional[Dict[str, Any]] = Field(
        default=None, 
        description="Numeric values extracted from charts/diagrams"
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="Vision analysis confidence")


class Region(BaseModel):
    """Represents a detected region within a document page."""
    
    id: str = Field(default_factory=lambda: str(uuid4()), description="Unique region identifier")
    bbox: BoundingBox = Field(..., description="Bounding box coordinates")
    region_type: RegionType = Field(..., description="Type of region content")
    content: Union[TextContent, TableContent, ImageContent] = Field(
        ..., 
        description="Extracted content based on region type"
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall region confidence")
    extraction_method: str = Field(
        ..., 
        description="Method used for extraction (ocr, vision, hybrid)"
    )


class Page(BaseModel):
    """Represents a single page in a document."""
    
    page_number: int = Field(..., ge=1, description="Page number (1-indexed)")
    regions: List[Region] = Field(default_factory=list, description="Detected regions on page")
    raw_image_bytes: Optional[bytes] = Field(
        default=None, 
        description="Raw page image data"
    )
    processed_image_bytes: Optional[bytes] = Field(
        default=None, 
        description="Preprocessed page image data"
    )
    
    class Config:
        arbitrary_types_allowed = True


class DocumentMetadata(BaseModel):
    """Metadata associated with a document."""
    
    title: Optional[str] = Field(default=None, description="Document title")
    author: Optional[str] = Field(default=None, description="Document author")
    created_date: Optional[datetime] = Field(default=None, description="Document creation date")
    page_count: int = Field(..., ge=0, description="Total number of pages")
    file_size_bytes: int = Field(..., ge=0, description="File size in bytes")
    document_type: Optional[str] = Field(
        default=None, 
        description="Document type (pdf, image, scan)"
    )


class ProcessingStatus(str, Enum):
    """Status of document processing."""
    
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CONFLICT_DETECTED = "conflict_detected"


class Document(BaseModel):
    """Represents a complete document with all pages and metadata."""
    
    id: str = Field(default_factory=lambda: str(uuid4()), description="Unique document identifier")
    file_path: str = Field(..., description="Path to source document file")
    pages: List[Page] = Field(default_factory=list, description="Document pages")
    metadata: DocumentMetadata = Field(..., description="Document metadata")
    processing_status: ProcessingStatus = Field(
        default=ProcessingStatus.PENDING, 
        description="Current processing status"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow, 
        description="Timestamp when document was added"
    )
    
    @field_validator('file_path')
    @classmethod
    def validate_file_path(cls, v: str) -> str:
        """Ensure file path is not empty."""
        if not v or not v.strip():
            raise ValueError("File path cannot be empty")
        return v


class ConflictType(str, Enum):
    """Types of conflicts that can be detected."""
    
    VALUE_MISMATCH = "value_mismatch"
    CONFIDENCE_LOW = "confidence_low"
    METHOD_DISAGREEMENT = "method_disagreement"


class ResolutionStatus(str, Enum):
    """Status of conflict resolution."""
    
    PENDING = "pending"
    RESOLVED = "resolved"
    FLAGGED = "flagged"


class ResolutionMethod(str, Enum):
    """Method used to resolve a conflict."""
    
    AUTO = "auto"
    MANUAL = "manual"
    USER_OVERRIDE = "user_override"


class Conflict(BaseModel):
    """Represents a detected conflict between extraction methods."""
    
    id: str = Field(default_factory=lambda: str(uuid4()), description="Unique conflict identifier")
    region_id: str = Field(..., description="ID of the region with conflict")
    conflict_type: ConflictType = Field(..., description="Type of conflict detected")
    text_value: Any = Field(..., description="Value extracted via OCR/text method")
    vision_value: Any = Field(..., description="Value extracted via vision method")
    discrepancy_percentage: float = Field(
        ..., 
        ge=0.0, 
        le=1.0, 
        description="Percentage discrepancy between values"
    )
    confidence_scores: Dict[str, float] = Field(
        ..., 
        description="Confidence scores for each extraction method"
    )
    resolution_status: ResolutionStatus = Field(
        default=ResolutionStatus.PENDING, 
        description="Current resolution status"
    )
    resolution_method: Optional[ResolutionMethod] = Field(
        default=None, 
        description="Method used to resolve conflict"
    )
    impact_score: float = Field(
        default=0.0, 
        ge=0.0, 
        le=1.0, 
        description="Calculated impact score for prioritization"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow, 
        description="Timestamp when conflict was detected"
    )


class ConflictResolution(BaseModel):
    """Represents the resolution of a conflict."""
    
    conflict_id: str = Field(..., description="ID of the resolved conflict")
    chosen_value: Any = Field(..., description="Final value chosen after resolution")
    resolution_method: ResolutionMethod = Field(..., description="Method used for resolution")
    user_id: Optional[str] = Field(default=None, description="User who resolved the conflict")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, 
        description="Timestamp of resolution"
    )
    confidence: float = Field(
        ..., 
        ge=0.0, 
        le=1.0, 
        description="Confidence in the resolution"
    )
    notes: Optional[str] = Field(default=None, description="Additional notes about resolution")
