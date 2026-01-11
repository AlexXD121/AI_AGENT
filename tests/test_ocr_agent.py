"""Unit tests for OCRAgent.

These tests use mocking to avoid requiring actual PaddleOCR model downloads.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from uuid import uuid4
import io
from PIL import Image

from local_body.agents.ocr_agent import OCRAgent
from local_body.core.datamodels import (
    Document,
    DocumentMetadata,
    Page,
    Region,
    RegionType,
    BoundingBox,
    ProcessingStatus,
    TextContent,
    TableContent,
    ImageContent,
)


@pytest.fixture
def mock_config():
    """Create mock configuration for OCRAgent."""
    return {
        "confidence_threshold": 0.85,
        "lang": "en",
        "use_angle_cls": True
    }


@pytest.fixture
def sample_document_with_regions():
    """Create a sample document with image and regions."""
    # Create a simple 100x100 RGB image
    img = Image.new('RGB', (100, 100), color=(255, 255, 255))
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes_value = img_bytes.getvalue()
    
    doc = Document(
        id=str(uuid4()),
        file_path="/test/document.pdf",
        metadata=DocumentMetadata(
            title="Test Document",
            page_count=1,
            file_size_bytes=1024
        ),
        pages=[
            Page(
                page_number=1,
                raw_image_bytes=img_bytes_value,
                regions=[
                    Region(
                        bbox=BoundingBox(x=10, y=10, width=80, height=20),
                        region_type=RegionType.TEXT,
                        content=ImageContent(description="", confidence=0.0),
                        confidence=0.9,
                        extraction_method="yolov8"
                    )
                ]
            )
        ],
        processing_status=ProcessingStatus.IN_PROGRESS
    )
    return doc


@pytest.fixture
def mock_paddleocr():
    """Create a mock PaddleOCR instance."""
    mock_ocr = MagicMock()
    
    def create_ocr_result(text: str, confidence: float):
        """Create mock OCR result in PaddleOCR format."""
        # PaddleOCR format: [[[bbox], (text, confidence)], ...]
        return [[
            [[[0, 0], [100, 0], [100, 20], [0, 20]], (text, confidence)]
        ]]
    
    mock_ocr.create_ocr_result = create_ocr_result
    mock_ocr.ocr.return_value = create_ocr_result("Revenue: $5M", 0.99)
    
    return mock_ocr


class TestOCRAgent:
    """Test suite for OCRAgent class."""
    
    @pytest.mark.asyncio
    @patch('local_body.agents.ocr_agent.PaddleOCR')
    async def test_normal_flow_high_confidence(
        self,
        mock_paddle_class,
        mock_paddleocr,
        mock_config,
        sample_document_with_regions
    ):
        """Test 1: Normal flow with high confidence (no retry)."""
        # Configure mock
        mock_paddle_class.return_value = mock_paddleocr
        
        # Create agent and process
        agent = OCRAgent(mock_config)
        result = await agent.process(sample_document_with_regions)
        
        # Assert text extracted
        region = result.pages[0].regions[0]
        assert isinstance(region.content, TextContent)
        assert "Revenue" in region.content.text
        assert "$5M" in region.content.text
        assert region.content.confidence == 0.99
        
        # Assert OCR called once (no retry)
        assert mock_paddleocr.ocr.call_count == 1
    
    @pytest.mark.asyncio
    @patch('local_body.agents.ocr_agent.PaddleOCR')
    async def test_retry_logic_low_to_high_confidence(
        self,
        mock_paddle_class,
        mock_config,
        sample_document_with_regions
    ):
        """Test 2: Retry logic shows OCR called twice when confidence is low."""
        # Setup mock OCR with side_effect
        # Create mock PaddleOCR instance
        mock_ocr = MagicMock()
        
        # Mock: First attempt returns low-confidence result (below threshold 0.85)
        # PaddleOCR returns: [page_results] where page_results = [line_results]
        # Each line_result = [bbox, (text, confidence)]
        bad_result = [[
            [[[0, 0], [100, 0], [100, 20], [0, 20]], ("LowConfText", 0.70)]
        ]]
        
        # Mock: Second attempt (after preprocessing) returns better result (above threshold)
        better_result = [[
            [[[0, 0], [100, 0], [100, 20], [0, 20]], ("BetterText", 0.92)]
        ]]
        
        # Configure mock to return different results
        mock_ocr.ocr.side_effect = [bad_result, better_result]
        mock_paddle_class.return_value = mock_ocr
        
        # Create agent AFTER mock is configured
        agent = OCRAgent(mock_config)
        
        # Process document
        result = await agent.process(sample_document_with_regions)
        
        # ASSERT: OCR was called twice (original + retry)
        assert mock_ocr.ocr.call_count == 2, "OCR should be called twice for retry logic"
        
        # ASSERT: Better result used (higher confidence from second attempt)
        region = result.pages[0].regions[0]
        assert isinstance(region.content, TextContent)
        assert region.content.text == "BetterText", f"Expected 'BetterText' but got '{region.content.text}'"
        assert region.content.confidence == 0.92
    
    @pytest.mark.asyncio
    @patch('local_body.agents.ocr_agent.PaddleOCR')
    async def test_table_region_handling(
        self,
        mock_paddle_class,
        mock_paddleocr,
        mock_config,
        sample_document_with_regions
    ):
        """Test 3: Table region creates TableContent."""
        # Change region type to TABLE
        sample_document_with_regions.pages[0].regions[0].region_type = RegionType.TABLE
        
        # Mock table-like text
        table_result = [[
            [[[0, 0], [50, 0], [50, 10], [0, 10]], ("Name", 0.95)],
            [[[50, 0], [100, 0], [100, 10], [50, 10]], ("Amount", 0.95)],
            [[[0, 10], [50, 10], [50, 20], [0, 20]], ("Item A", 0.92)],
            [[[50, 10], [100, 10], [100, 20], [50, 20]], ("$100", 0.92)]
        ]]
        mock_paddleocr.ocr.return_value = table_result
        mock_paddle_class.return_value = mock_paddleocr
        
        # Create agent and process
        agent = OCRAgent(mock_config)
        result = await agent.process(sample_document_with_regions)
        
        # Assert TableContent created
        region = result.pages[0].regions[0]
        assert isinstance(region.content, TableContent)
        assert len(region.content.rows) > 0
        assert region.content.confidence > 0.9
    
    @pytest.mark.asyncio
    @patch('local_body.agents.ocr_agent.PaddleOCR')
    async def test_skip_non_text_regions(
        self,
        mock_paddle_class,
        mock_paddleocr,
        mock_config,
        sample_document_with_regions
    ):
        """Test 4: Non-text/table regions are skipped."""
        # Change region type to IMAGE
        sample_document_with_regions.pages[0].regions[0].region_type = RegionType.IMAGE
        mock_paddle_class.return_value = mock_paddleocr
        
        # Create agent and process
        agent = OCRAgent(mock_config)
        result = await agent.process(sample_document_with_regions)
        
        # Assert OCR not called (region skipped)
        assert mock_paddleocr.ocr.call_count == 0
        
        # Assert content unchanged
        region = result.pages[0].regions[0]
        assert isinstance(region.content, ImageContent)
    
    def test_extract_numeric_value_millions(self, mock_config):
        """Test 5: Numeric extraction handles millions."""
        with patch('local_body.agents.ocr_agent.PaddleOCR'):
            agent = OCRAgent(mock_config)
            
            # Test various million formats
            assert agent._extract_numeric_value("$1.5M") == 1_500_000.0
            assert agent._extract_numeric_value("2.3M") == 2_300_000.0
            assert agent._extract_numeric_value("5M") == 5_000_000.0
    
    def test_extract_numeric_value_billions(self, mock_config):
        """Test 6: Numeric extraction handles billions."""
        with patch('local_body.agents.ocr_agent.PaddleOCR'):
            agent = OCRAgent(mock_config)
            
            # Test billion formats
            assert agent._extract_numeric_value("$1.5B") == 1_500_000_000.0
            assert agent._extract_numeric_value("2B") == 2_000_000_000.0
    
    def test_extract_numeric_value_thousands(self, mock_config):
        """Test 7: Numeric extraction handles thousands."""
        with patch('local_body.agents.ocr_agent.PaddleOCR'):
            agent = OCRAgent(mock_config)
            
            # Test thousand formats
            assert agent._extract_numeric_value("$5,200.00") == 5200.0
            assert agent._extract_numeric_value("1.5K") == 1500.0
            assert agent._extract_numeric_value("250K") == 250_000.0
    
    def test_extract_numeric_value_simple_numbers(self, mock_config):
        """Test 8: Numeric extraction handles simple numbers."""
        with patch('local_body.agents.ocr_agent.PaddleOCR'):
            agent = OCRAgent(mock_config)
            
            # Test simple formats
            assert agent._extract_numeric_value("$100.50") == 100.5
            assert agent._extract_numeric_value("42") == 42.0
            assert agent._extract_numeric_value("3.14") == 3.14
    
    def test_extract_numeric_value_invalid(self, mock_config):
        """Test 9: Numeric extraction returns None for invalid input."""
        with patch('local_body.agents.ocr_agent.PaddleOCR'):
            agent = OCRAgent(mock_config)
            
            # Test invalid inputs
            assert agent._extract_numeric_value("No numbers here") is None
            assert agent._extract_numeric_value("") is None
            assert agent._extract_numeric_value("ABC") is None
    
    @pytest.mark.asyncio
    @patch('local_body.agents.ocr_agent.PaddleOCR')
    async def test_empty_ocr_result(
        self,
        mock_paddle_class,
        mock_config,
        sample_document_with_regions
    ):
        """Test 10: Empty OCR result handled gracefully."""
        # Mock empty OCR result
        mock_ocr = MagicMock()
        mock_ocr.ocr.return_value = [[]]  # Empty result
        mock_paddle_class.return_value = mock_ocr
        
        # Create agent and process
        agent = OCRAgent(mock_config)
        result = await agent.process(sample_document_with_regions)
        
        # Assert empty text with zero confidence
        region = result.pages[0].regions[0]
        assert isinstance(region.content, TextContent)
        assert region.content.text == ""
        assert region.content.confidence == 0.0
