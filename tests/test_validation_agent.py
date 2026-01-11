"""Tests for ValidationAgent conflict detection."""

import pytest
from local_body.agents.validation_agent import ValidationAgent
from local_body.core.datamodels import (
    Document, DocumentMetadata, Page, Region,
    BoundingBox, RegionType, TextContent
)


@pytest.fixture
def validation_agent():
    """Create ValidationAgent with default config."""
    return ValidationAgent(config={'conflict_threshold': 0.15})


@pytest.fixture
def sample_document_with_conflict():
    """Create document with OCR text showing $100M."""
    return Document(
        file_path="/test/test.pdf",
        metadata=DocumentMetadata(
            page_count=1,
            file_size_bytes=1024
        ),
        pages=[
            Page(
                page_number=1,
                regions=[
                    Region(
                        bbox=BoundingBox(x=10, y=10, width=100, height=100),
                        region_type=RegionType.TABLE,
                        content=TextContent(
                            text="Revenue: $100M",
                            confidence=0.95
                        ),
                        confidence=0.95,
                        extraction_method="ocr"
                    )
                ]
            )
        ]
    )


class TestNumericExtraction:
    """Test numeric value extraction from text."""
    
    def test_extract_currency(self, validation_agent):
        """Test 1: Extract currency values"""
        assert validation_agent.extract_numeric_value("$100M") == 100_000_000
        assert validation_agent.extract_numeric_value("$5.2M") == 5_200_000
        assert validation_agent.extract_numeric_value("$1,234.56") == 1234.56
    
    def test_extract_percentage(self, validation_agent):
        """Test 2: Extract percentages"""
        assert validation_agent.extract_numeric_value("15%") == 0.15
        assert validation_agent.extract_numeric_value("99.9%") == pytest.approx(0.999)
    
    def test_extract_large_numbers(self, validation_agent):
        """Test 3: Extract K/M/B suffixes"""
        assert validation_agent.extract_numeric_value("5.2M") == 5_200_000
        assert validation_agent.extract_numeric_value("1.5B") == 1_500_000_000
        assert validation_agent.extract_numeric_value("3.4K") == 3_400
    
    def test_extract_from_sentence(self, validation_agent):
        """Test 4: Extract from natural text"""
        result = validation_agent.extract_numeric_value("Revenue appears to be $50M")
        assert result == 50_000_000


class TestConflictDetection:
    """Test conflict detection logic."""
    
    def test_high_discrepancy_creates_conflict(self, validation_agent, sample_document_with_conflict):
        """Test 5: High discrepancy (50%) creates conflict"""
        # Vision says $50M, OCR says $100M -> 50% discrepancy
        vision_results = {
            sample_document_with_conflict.pages[0].regions[0].id: "Revenue appears to be approximately $50M"
        }
        
        conflicts = validation_agent.validate(sample_document_with_conflict, vision_results)
        
        assert len(conflicts) == 1
        assert conflicts[0].text_value == 100_000_000
        assert conflicts[0].vision_value == 50_000_000
        assert conflicts[0].discrepancy_percentage == pytest.approx(0.5, rel=0.01)
    
    def test_low_discrepancy_no_conflict(self, validation_agent, sample_document_with_conflict):
        """Test 6: Low discrepancy (1%) does not create conflict"""
        # Vision says $99M, OCR says $100M -> 1% discrepancy (< 15% threshold)
        vision_results = {
            sample_document_with_conflict.pages[0].regions[0].id: "The revenue is $99M"
        }
        
        conflicts = validation_agent.validate(sample_document_with_conflict, vision_results)
        
        assert len(conflicts) == 0
    
    def test_no_vision_results(self, validation_agent, sample_document_with_conflict):
        """Test 7: No vision results returns empty conflicts"""
        conflicts = validation_agent.validate(sample_document_with_conflict, None)
        assert len(conflicts) == 0
    
    def test_empty_vision_results(self, validation_agent, sample_document_with_conflict):
        """Test 8: Empty vision results dict returns empty conflicts"""
        conflicts = validation_agent.validate(sample_document_with_conflict, {})
        assert len(conflicts) == 0
    
    def test_non_numeric_text_no_conflict(self, validation_agent):
        """Test 9: Non-numeric text does not create conflicts"""
        doc = Document(
            file_path="/test/test.pdf",
            metadata=DocumentMetadata(page_count=1, file_size_bytes=1024),
            pages=[
                Page(
                    page_number=1,
                    regions=[
                        Region(
                            bbox=BoundingBox(x=10, y=10, width=100, height=100),
                            region_type=RegionType.TEXT,
                            content=TextContent(text="Hello World", confidence=0.95),
                            confidence=0.95,
                            extraction_method="ocr"
                        )
                    ]
                )
            ]
        )
        
        vision_results = {
            doc.pages[0].regions[0].id: "This is a greeting"
        }
        
        conflicts = validation_agent.validate(doc, vision_results)
        assert len(conflicts) == 0
