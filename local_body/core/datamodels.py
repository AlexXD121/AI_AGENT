"""Core data models for Sovereign-Doc document processing system.

This module defines the Pydantic models for representing documents, pages, regions,
conflicts, and related data structures used throughout the system.
"""

import gzip
import json
import os
import tempfile
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, Field, field_serializer, field_validator


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
    regions: List[Region] = Field(default_factory=list, description="Detected regions on this page")
    raw_image_bytes: Optional[bytes] = Field(default=None, description="Original page image as bytes")
    processed_image_bytes: Optional[bytes] = Field(
        default=None, 
        description="Optional preprocessed image (denoised, binarized)"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, 
        description="Additional page-level metadata"
    )
    
    @field_serializer('raw_image_bytes', 'processed_image_bytes', when_used='json')
    def serialize_bytes_as_base64(self, value: Optional[bytes]) -> Optional[str]:
        """Serialize bytes fields as base64 strings for JSON compatibility."""
        if value is None:
            return None
        import base64
        return base64.b64encode(value).decode('ascii')
    
    @field_validator('raw_image_bytes', 'processed_image_bytes', mode='before')
    @classmethod
    def deserialize_base64_to_bytes(cls, value: Union[str, bytes, None]) -> Optional[bytes]:
        """Deserialize base64 strings back to bytes when loading from JSON."""
        if value is None or isinstance(value, bytes):
            return value
        if isinstance(value, str):
            import base64
            return base64.b64decode(value)
        return value


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
    
    def save_to_json(self, path: str, compress: bool = True) -> None:
        """Save document to JSON file with atomic write and optional compression.
        
        Uses atomic write pattern (write to temp file, then replace) to prevent
        corruption during crashes. Optionally compresses with gzip.
        
        Args:
            path: File path to save the JSON document
            compress: If True, compress with gzip (default: True)
            
        Raises:
            PermissionError: If the file cannot be written due to permissions
            OSError: If the path is invalid or other IO errors occur
        """
        try:
            file_path = Path(path)
            # Ensure parent directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Serialize to JSON with proper formatting
            json_str = self.model_dump_json(indent=2)
            
            # Atomic write: write to temp file first, then replace
            # This prevents corruption if process crashes during write
            temp_fd, temp_path = tempfile.mkstemp(
                dir=file_path.parent,
                prefix=f".{file_path.name}.",
                suffix=".tmp"
            )
            
            try:
                if compress:
                    # Write compressed
                    with gzip.open(temp_path, 'wt', encoding='utf-8') as f:
                        f.write(json_str)
                else:
                    # Write uncompressed
                    with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                        f.write(json_str)
                        temp_fd = None  # Prevent double close
                
                # Atomic replace: this is atomic on POSIX and Windows
                os.replace(temp_path, str(file_path))
                
            finally:
                # Clean up temp file if something went wrong
                if temp_fd is not None:
                    os.close(temp_fd)
                if os.path.exists(temp_path):
                    try:
                        os.unlink(temp_path)
                    except OSError:
                        pass
            
        except PermissionError as e:
            raise PermissionError(
                f"Permission denied when writing to '{path}'. "
                f"Check file permissions and try again."
            ) from e
        except OSError as e:
            raise OSError(
                f"Failed to write document to '{path}': {e}"
            ) from e
    
    @classmethod
    def from_json(cls, path: str) -> 'Document':
        """Load document from JSON file with automatic gzip detection.
        
        Automatically detects and handles gzip-compressed files (*.gz extension).
        
        Args:
            path: File path to load the JSON document from
            
        Returns:
            Validated Document instance
            
        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If the JSON is invalid or doesn't match schema
            OSError: If other IO errors occur
        """
        file_path = Path(path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Document file not found: '{path}'")
        
        try:
            # Auto-detect gzip compression by file extension
            if str(file_path).endswith('.gz'):
                # Read gzip-compressed file
                with gzip.open(file_path, 'rt', encoding='utf-8') as f:
                    json_str = f.read()
            else:
                # Read uncompressed file
                json_str = file_path.read_text(encoding='utf-8')
            
            # Parse and validate against Pydantic schema
            data = json.loads(json_str)
            return cls(**data)
            
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Invalid JSON in file '{path}': {e}"
            ) from e
        except OSError as e:
            raise OSError(
                f"Failed to read document from '{path}': {e}"
            ) from e
    
    def validate_integrity(self) -> bool:
        """Validate document data integrity.
        
        Performs comprehensive integrity checks:
        1. Page count matches metadata
        2. All page numbers are unique
        3. All regions have valid bounding boxes
        
        Returns:
            True if all integrity checks pass
            
        Raises:
            ValueError: If any integrity check fails with descriptive message
        """
        # Check 1: Verify page count matches metadata
        actual_page_count = len(self.pages)
        expected_page_count = self.metadata.page_count
        
        if actual_page_count != expected_page_count:
            raise ValueError(
                f"Page count mismatch: metadata declares {expected_page_count} pages, "
                f"but document contains {actual_page_count} pages"
            )
        
        # Check 2: Verify all page numbers are unique
        page_numbers = [page.page_number for page in self.pages]
        if len(page_numbers) != len(set(page_numbers)):
            duplicates = [num for num in page_numbers if page_numbers.count(num) > 1]
            raise ValueError(
                f"Duplicate page numbers detected: {set(duplicates)}. "
                f"Each page must have a unique page_number."
            )
        
        # Check 3: Verify all regions have valid bounding boxes
        for page_idx, page in enumerate(self.pages, 1):
            for region_idx, region in enumerate(page.regions, 1):
                bbox = region.bbox
                
                if bbox.width <= 0:
                    raise ValueError(
                        f"Invalid bounding box on page {page_idx}, region {region_idx}: "
                        f"width must be > 0, got {bbox.width}"
                    )
                
                if bbox.height <= 0:
                    raise ValueError(
                        f"Invalid bounding box on page {page_idx}, region {region_idx}: "
                        f"height must be > 0, got {bbox.height}"
                    )
        
        return True


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
    
    @staticmethod
    def normalize_value(value: Any) -> float:
        """Normalize various value formats to standard float.
        
        Handles common financial and numeric formats:
        - Currency: "$5.2M", "$1,234.56"
        - Percentages: "15%", "0.15"
        - Large numbers: "5.2M", "1.5B", "3.4K"
        - Comma-separated: "1,234,567"
        
        Args:
            value: Value to normalize (str, int, float, or None)
            
        Returns:
            Normalized float value
            
        Raises:
            ValueError: If value cannot be converted to a number
        """
        import re
        
        # Handle None
        if value is None:
            return 0.0
        
        # Already a number
        if isinstance(value, (int, float)):
            return float(value)
        
        # Convert to string and clean
        value_str = str(value).strip()
        
        if not value_str:
            return 0.0
        
        # Remove currency symbols and whitespace
        value_str = re.sub(r'[$€£¥]', '', value_str)
        value_str = value_str.strip()
        
        # Handle percentages
        if '%' in value_str:
            value_str = value_str.replace('%', '')
            try:
                return float(value_str) / 100.0
            except ValueError:
                raise ValueError(f"Cannot convert percentage '{value}' to float")
        
        # Handle multipliers (M, B, K)
        multipliers = {
            'K': 1_000,
            'M': 1_000_000,
            'B': 1_000_000_000,
            'T': 1_000_000_000_000
        }
        
        for suffix, multiplier in multipliers.items():
            if value_str.upper().endswith(suffix):
                value_str = value_str[:-1].strip()
                try:
                    # Remove commas before conversion
                    value_str = value_str.replace(',', '')
                    return float(value_str) * multiplier
                except ValueError:
                    raise ValueError(f"Cannot convert '{value}' to float")
        
        # Handle comma-separated numbers
        value_str = value_str.replace(',', '')
        
        # Try direct conversion
        try:
            return float(value_str)
        except ValueError:
            raise ValueError(f"Cannot convert '{value}' to float")
    
    def update_impact_score(self, region_type: str) -> float:
        """Calculate and update the impact score for conflict prioritization.
        
        Impact score calculation logic (from design specification):
        1. Base impact: 1.0 for tables, 0.5 for other types
        2. Scale by discrepancy percentage (capped at 1.0)
        3. Boost by 1.5x if both text and vision confidence > 0.7
        
        Args:
            region_type: Type of region ("text", "table", "image", "chart")
            
        Returns:
            Calculated impact score (0.0 to 1.5)
        """
        # Higher priority for financial figures (tables)
        impact = 1.0 if region_type == "table" else 0.5
        
        # Scale by discrepancy magnitude (capped at 1.0)
        impact *= min(self.discrepancy_percentage, 1.0)
        
        # Boost if both confidences are high (genuine disagreement)
        text_conf = self.confidence_scores.get("text", 0.0)
        vision_conf = self.confidence_scores.get("vision", 0.0)
        
        if text_conf > 0.7 and vision_conf > 0.7:
            impact *= 1.5
        
        # Update the stored impact score
        self.impact_score = min(impact, 1.0)  # Cap at 1.0 for consistency
        
        return self.impact_score
    
    def calculate_impact(self) -> float:
        """Calculate conflict impact score using stored confidence scores.
        
        This is a convenience method that calculates impact without needing
        to specify region_type. Uses a default base impact of 0.75.
        
        Formula: (Base Impact * Discrepancy) * Confidence Boost
        - Base Impact: 0.75 (moderate priority)
        - Discrepancy: self.discrepancy_percentage
        - Confidence Boost: 1.5x if both confidences > 0.7, else 1.0x
        
        Returns:
            Calculated impact score (0.0 to 1.5)
        """
        # Base impact (moderate priority)
        base_impact = 0.75
        
        # Scale by discrepancy
        impact = base_impact * min(self.discrepancy_percentage, 1.0)
        
        # Apply confidence boost
        text_conf = self.confidence_scores.get("text", 0.0)
        vision_conf = self.confidence_scores.get("vision", 0.0)
        
        if text_conf > 0.7 and vision_conf > 0.7:
            impact *= 1.5
        
        # Update stored impact score
        self.impact_score = min(impact, 1.0)  # Cap at 1.0
        
        return self.impact_score
    
    def resolve(self, resolution: 'ConflictResolution') -> None:
        """Mark conflict as resolved with the given resolution.
        
        Updates the conflict status and resolution method based on the
        provided resolution. This creates an audit trail for conflict
        resolution history.
        
        Args:
            resolution: ConflictResolution instance with resolution details
        """
        self.resolution_status = ResolutionStatus.RESOLVED
        self.resolution_method = resolution.resolution_method
        
        # Note: The resolution timestamp is stored in the ConflictResolution object
        # This maintains separation of concerns and allows multiple resolution attempts
    
    def flag(self, reason: Optional[str] = None) -> None:
        """Flag conflict for manual review.
        
        Marks the conflict as requiring special attention, typically when
        automated resolution is not possible or confidence is too low.
        
        Args:
            reason: Optional reason for flagging the conflict
        """
        self.resolution_status = ResolutionStatus.FLAGGED
        
        # Note: The reason can be stored in a separate audit log or
        # in the ConflictResolution notes field when eventually resolved


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
