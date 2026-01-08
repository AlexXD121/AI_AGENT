"""Test suite for data models persistence and validation.

This module tests the Document class's JSON serialization/deserialization
and data integrity validation methods.
"""

import json
import pytest
from pathlib import Path
from datetime import datetime

from local_body.core.datamodels import (
    Document, DocumentMetadata, Page, Region, RegionType,
    BoundingBox, TextContent, ProcessingStatus
)


class TestDocumentPersistence:
    """Test JSON serialization and deserialization."""
    
    def test_save_and_load_document(self, tmp_path):
        """Test saving a document to JSON and loading it back."""
        # Create a test document
        metadata = DocumentMetadata(
            title="Test Document",
            page_count=2,
            file_size_bytes=1024,
            document_type="pdf"
        )
        
        bbox1 = BoundingBox(x=10.0, y=20.0, width=100.0, height=50.0)
        text_content1 = TextContent(text="Sample text page 1", confidence=0.95)
        region1 = Region(
            bbox=bbox1,
            region_type=RegionType.TEXT,
            content=text_content1,
            confidence=0.9,
            extraction_method="ocr"
        )
        
        bbox2 = BoundingBox(x=15.0, y=25.0, width=120.0, height=60.0)
        text_content2 = TextContent(text="Sample text page 2", confidence=0.92)
        region2 = Region(
            bbox=bbox2,
            region_type=RegionType.TEXT,
            content=text_content2,
            confidence=0.88,
            extraction_method="ocr"
        )
        
        page1 = Page(page_number=1, regions=[region1])
        page2 = Page(page_number=2, regions=[region2])
        
        doc_original = Document(
            file_path="test.pdf",
            pages=[page1, page2],
            metadata=metadata
        )
        
        # Save to JSON
        json_path = tmp_path / "test_document.json"
        doc_original.save_to_json(str(json_path))
        
        # Verify file exists and is valid JSON
        assert json_path.exists()
        with open(json_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
            assert json_data['file_path'] == "test.pdf"
            assert len(json_data['pages']) == 2
        
        # Load from JSON
        doc_loaded = Document.from_json(str(json_path))
        
        # Verify loaded document matches original
        assert doc_loaded.file_path == doc_original.file_path
        assert len(doc_loaded.pages) == len(doc_original.pages)
        assert doc_loaded.metadata.title == doc_original.metadata.title
        assert doc_loaded.metadata.page_count == doc_original.metadata.page_count
        assert doc_loaded.processing_status == doc_original.processing_status
        
        # Verify pages match
        for orig_page, loaded_page in zip(doc_original.pages, doc_loaded.pages):
            assert loaded_page.page_number == orig_page.page_number
            assert len(loaded_page.regions) == len(orig_page.regions)
    
    def test_save_creates_parent_directory(self, tmp_path):
        """Test that save_to_json creates parent directories if needed."""
        metadata = DocumentMetadata(
            page_count=0,
            file_size_bytes=100
        )
        doc = Document(file_path="test.pdf", metadata=metadata)
        
        # Save to nested path that doesn't exist
        nested_path = tmp_path / "nested" / "dir" / "test.json"
        doc.save_to_json(str(nested_path))
        
        assert nested_path.exists()
        assert nested_path.parent.exists()
    
    def test_save_utf8_encoding(self, tmp_path):
        """Test that documents are saved with UTF-8 encoding."""
        metadata = DocumentMetadata(
            title="Test with émojis 🎉 and spëcial çhars",
            page_count=0,
            file_size_bytes=100
        )
        doc = Document(file_path="test.pdf", metadata=metadata)
        
        json_path = tmp_path / "utf8_test.json"
        doc.save_to_json(str(json_path))
        
        # Verify UTF-8 encoding
        content = json_path.read_text(encoding='utf-8')
        assert "émojis 🎉" in content
        assert "spëcial çhars" in content
    
    def test_load_nonexistent_file(self):
        """Test loading from a file that doesn't exist."""
        with pytest.raises(FileNotFoundError) as exc_info:
            Document.from_json("nonexistent_file.json")
        
        assert "not found" in str(exc_info.value).lower()
    
    def test_load_invalid_json(self, tmp_path):
        """Test loading from a file with invalid JSON."""
        invalid_json_path = tmp_path / "invalid.json"
        invalid_json_path.write_text("{ invalid json }", encoding='utf-8')
        
        with pytest.raises(ValueError) as exc_info:
            Document.from_json(str(invalid_json_path))
        
        assert "Invalid JSON" in str(exc_info.value)
    
    def test_load_json_missing_required_fields(self, tmp_path):
        """Test loading JSON that's missing required fields."""
        incomplete_json = tmp_path / "incomplete.json"
        incomplete_json.write_text('{"id": "test-123"}', encoding='utf-8')
        
        with pytest.raises(Exception):  # Pydantic validation error
            Document.from_json(str(incomplete_json))


class TestDocumentIntegrity:
    """Test data integrity validation."""
    
    def test_validate_integrity_success(self):
        """Test that a valid document passes integrity checks."""
        metadata = DocumentMetadata(
            page_count=2,
            file_size_bytes=1024
        )
        
        bbox1 = BoundingBox(x=10.0, y=20.0, width=100.0, height=50.0)
        text_content1 = TextContent(text="Page 1", confidence=0.9)
        region1 = Region(
            bbox=bbox1,
            region_type=RegionType.TEXT,
            content=text_content1,
            confidence=0.9,
            extraction_method="ocr"
        )
        
        bbox2 = BoundingBox(x=15.0, y=25.0, width=120.0, height=60.0)
        text_content2 = TextContent(text="Page 2", confidence=0.85)
        region2 = Region(
            bbox=bbox2,
            region_type=RegionType.TEXT,
            content=text_content2,
            confidence=0.85,
            extraction_method="ocr"
        )
        
        page1 = Page(page_number=1, regions=[region1])
        page2 = Page(page_number=2, regions=[region2])
        
        doc = Document(
            file_path="test.pdf",
            pages=[page1, page2],
            metadata=metadata
        )
        
        # Should return True without raising
        assert doc.validate_integrity() is True
    
    def test_validate_integrity_page_count_mismatch(self):
        """Test that page count mismatch raises ValueError."""
        metadata = DocumentMetadata(
            page_count=5,  # Says 5 pages
            file_size_bytes=1024
        )
        
        page1 = Page(page_number=1, regions=[])
        
        doc = Document(
            file_path="test.pdf",
            pages=[page1],  # But only has 1 page
            metadata=metadata
        )
        
        with pytest.raises(ValueError) as exc_info:
            doc.validate_integrity()
        
        error_msg = str(exc_info.value)
        assert "Page count mismatch" in error_msg
        assert "5 pages" in error_msg
        assert "1 pages" in error_msg
    
    def test_validate_integrity_duplicate_page_numbers(self):
        """Test that duplicate page numbers raise ValueError."""
        metadata = DocumentMetadata(
            page_count=2,
            file_size_bytes=1024
        )
        
        page1 = Page(page_number=1, regions=[])
        page2 = Page(page_number=1, regions=[])  # Duplicate page number!
        
        doc = Document(
            file_path="test.pdf",
            pages=[page1, page2],
            metadata=metadata
        )
        
        with pytest.raises(ValueError) as exc_info:
            doc.validate_integrity()
        
        error_msg = str(exc_info.value)
        assert "Duplicate page numbers" in error_msg
        assert "1" in error_msg
    
    def test_validate_integrity_negative_bbox_width(self):
        """Test that negative bounding box width is caught by Pydantic validation."""
        from pydantic import ValidationError
        
        metadata = DocumentMetadata(
            page_count=1,
            file_size_bytes=1024
        )
        
        text_content = TextContent(text="Test", confidence=0.9)
        
        # This should fail at Pydantic validation level
        # because BoundingBox has ge=0 constraint
        with pytest.raises(ValidationError):
            # Attempting to create BoundingBox with negative width
            bbox = BoundingBox(x=10.0, y=20.0, width=-50.0, height=50.0)
    
    def test_validate_integrity_zero_bbox_width(self):
        """Test that zero bounding box width raises ValueError."""
        metadata = DocumentMetadata(
            page_count=1,
            file_size_bytes=1024
        )
        
        # Create region with zero width (passes Pydantic ge=0, but fails integrity)
        bbox = BoundingBox(x=10.0, y=20.0, width=0.0, height=50.0)
        text_content = TextContent(text="Test", confidence=0.9)
        region = Region(
            bbox=bbox,
            region_type=RegionType.TEXT,
            content=text_content,
            confidence=0.9,
            extraction_method="ocr"
        )
        
        page = Page(page_number=1, regions=[region])
        
        doc = Document(
            file_path="test.pdf",
            pages=[page],
            metadata=metadata
        )
        
        with pytest.raises(ValueError) as exc_info:
            doc.validate_integrity()
        
        error_msg = str(exc_info.value)
        assert "Invalid bounding box" in error_msg
        assert "width must be > 0" in error_msg
    
    def test_validate_integrity_zero_bbox_height(self):
        """Test that zero bounding box height raises ValueError."""
        metadata = DocumentMetadata(
            page_count=1,
            file_size_bytes=1024
        )
        
        # Create region with zero height
        bbox = BoundingBox(x=10.0, y=20.0, width=100.0, height=0.0)
        text_content = TextContent(text="Test", confidence=0.9)
        region = Region(
            bbox=bbox,
            region_type=RegionType.TEXT,
            content=text_content,
            confidence=0.9,
            extraction_method="ocr"
        )
        
        page = Page(page_number=1, regions=[region])
        
        doc = Document(
            file_path="test.pdf",
            pages=[page],
            metadata=metadata
        )
        
        with pytest.raises(ValueError) as exc_info:
            doc.validate_integrity()
        
        error_msg = str(exc_info.value)
        assert "Invalid bounding box" in error_msg
        assert "height must be > 0" in error_msg
    
    def test_validate_integrity_empty_document(self):
        """Test that an empty document (0 pages) passes validation."""
        metadata = DocumentMetadata(
            page_count=0,
            file_size_bytes=100
        )
        
        doc = Document(
            file_path="empty.pdf",
            pages=[],
            metadata=metadata
        )
        
        # Should pass validation
        assert doc.validate_integrity() is True
