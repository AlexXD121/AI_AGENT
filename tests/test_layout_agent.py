"""Unit tests for LayoutAgent.

These tests use mocking to avoid requiring actual YOLOv8 model downloads.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from uuid import uuid4
import numpy as np

from local_body.agents.layout_agent import LayoutAgent
from local_body.core.datamodels import (
    Document,
    DocumentMetadata,
    Page,
    Region,
    RegionType,
    BoundingBox,
    ProcessingStatus,
    TextContent,
    ImageContent,
)


@pytest.fixture
def mock_config():
    """Create mock configuration for LayoutAgent."""
    return {
        "confidence_threshold": 0.5,
        "model_path": "yolov8n.pt",
        "device": "cpu"
    }


@pytest.fixture
def sample_document_with_image():
    """Create a sample document with raw image bytes."""
    # Create a simple 100x100 RGB image as bytes
    import io
    from PIL import Image
    
    # Create solid color image
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
                regions=[]
            )
        ],
        processing_status=ProcessingStatus.IN_PROGRESS
    )
    return doc


@pytest.fixture
def mock_yolo_model():
    """Create a mock YOLO model with detection results."""
    mock_model = MagicMock()
    
    def create_mock_results(num_detections=2):
        """Create mock YOLO results with specified number of detections."""
        mock_result = MagicMock()
        mock_boxes = MagicMock()
        
        if num_detections == 0:
            mock_boxes.__len__ = lambda self: 0
            mock_boxes.__iter__ = lambda self: iter([])
            mock_result.boxes = None
        else:
            # Create mock boxes
            boxes_list = []
            for i in range(num_detections):
                mock_box = MagicMock()
                
                # Bounding box coordinates (x1, y1, x2, y2)
                if i == 0:
                    # First detection: Table at (10, 10, 50, 50)
                    coords = np.array([[10.0, 10.0, 50.0, 50.0]])
                    cls_id = 0  # Maps to IMAGE in placeholder
                    conf = 0.85
                else:
                    # Second detection: Text at (60, 60, 90, 90)
                    coords = np.array([[60.0, 60.0, 90.0, 90.0]])
                    cls_id = 0  # Maps to IMAGE in placeholder
                    conf = 0.75
                
                mock_box.xyxy = [MagicMock(cpu=lambda: MagicMock(numpy=lambda: coords[0]))]
                mock_box.conf = [MagicMock(cpu=lambda: MagicMock(numpy=lambda: conf))]
                mock_box.cls = [MagicMock(cpu=lambda: MagicMock(numpy=lambda: cls_id))]
                
                boxes_list.append(mock_box)
            
            mock_boxes.__len__ = lambda self: num_detections
            mock_boxes.__iter__ = lambda self: iter(boxes_list)
            mock_result.boxes = mock_boxes
        
        return [mock_result]
    
    # Default: return 2 detections
    mock_model.return_value = create_mock_results(2)
    mock_model.create_mock_results = create_mock_results
    mock_model.to = MagicMock(return_value=mock_model)
    
    return mock_model


class TestLayoutAgent:
    """Test suite for LayoutAgent class."""
    
    @pytest.mark.asyncio
    @patch('local_body.agents.layout_agent.YOLO')
    async def test_empty_page_no_detections(
        self,
        mock_yolo_class,
        mock_yolo_model,
        mock_config,
        sample_document_with_image
    ):
        """Test 1: Empty page with no detections returns empty regions list."""
        # Configure mock to return no detections
        mock_yolo_model.return_value = mock_yolo_model.create_mock_results(0)
        mock_yolo_class.return_value = mock_yolo_model
        
        # Create agent and process
        agent = LayoutAgent(mock_config)
        result = await agent.process(sample_document_with_image)
        
        # Assert no regions detected
        assert len(result.pages[0].regions) == 0
    
    @pytest.mark.asyncio
    @patch('local_body.agents.layout_agent.YOLO')
    async def test_single_detection(
        self,
        mock_yolo_class,
        mock_yolo_model,
        mock_config,
        sample_document_with_image
    ):
        """Test 2: Single detection creates one region."""
        # Configure mock to return 1 detection
        mock_yolo_model.return_value = mock_yolo_model.create_mock_results(1)
        mock_yolo_class.return_value = mock_yolo_model
        
        # Create agent and process
        agent = LayoutAgent(mock_config)
        result = await agent.process(sample_document_with_image)
        
        # Assert one region detected
        assert len(result.pages[0].regions) == 1
        
        # Verify region properties
        region = result.pages[0].regions[0]
        assert region.region_type == RegionType.IMAGE  # Placeholder mapping
        assert region.confidence >= 0.5
        assert region.extraction_method == "yolov8"
    
    @pytest.mark.asyncio
    @patch('local_body.agents.layout_agent.YOLO')
    async def test_multiple_detections(
        self,
        mock_yolo_class,
        mock_yolo_model,
        mock_config,
        sample_document_with_image
    ):
        """Test 3: Multiple detections create multiple regions."""
        # Configure mock to return 2 detections
        mock_yolo_model.return_value = mock_yolo_model.create_mock_results(2)
        mock_yolo_class.return_value = mock_yolo_model
        
        # Create agent and process
        agent = LayoutAgent(mock_config)
        result = await agent.process(sample_document_with_image)
        
        # Assert two regions detected
        assert len(result.pages[0].regions) == 2
        
        # Verify both regions have valid properties
        for region in result.pages[0].regions:
            assert region.region_type in [RegionType.TEXT, RegionType.TABLE, RegionType.IMAGE, RegionType.CHART]
            assert 0.0 <= region.confidence <= 1.0
            assert region.bbox.width > 0
            assert region.bbox.height > 0
    
    @pytest.mark.asyncio
    @patch('local_body.agents.layout_agent.YOLO')
    async def test_confidence_filtering(
        self,
        mock_yolo_class,
        mock_config,
        sample_document_with_image
    ):
        """Test 4: Low confidence detections are filtered out."""
        # Create mock with low confidence detection
        mock_model = MagicMock()
        mock_result = MagicMock()
        mock_box = MagicMock()
        
        # Low confidence detection (below 0.5 threshold)
        coords = np.array([[10.0, 10.0, 50.0, 50.0]])
        mock_box.xyxy = [MagicMock(cpu=lambda: MagicMock(numpy=lambda: coords[0]))]
        mock_box.conf = [MagicMock(cpu=lambda: MagicMock(numpy=lambda: 0.3))]  # Low confidence
        mock_box.cls = [MagicMock(cpu=lambda: MagicMock(numpy=lambda: 0))]
        
        mock_boxes = MagicMock()
        mock_boxes.__len__ = lambda self: 1
        mock_boxes.__iter__ = lambda self: iter([mock_box])
        mock_result.boxes = mock_boxes
        
        mock_model.return_value = [mock_result]
        mock_model.to = MagicMock(return_value=mock_model)
        mock_yolo_class.return_value = mock_model
        
        # Create agent and process
        agent = LayoutAgent(mock_config)
        result = await agent.process(sample_document_with_image)
        
        # Assert detection was filtered out
        assert len(result.pages[0].regions) == 0
    
    @pytest.mark.asyncio
    @patch('local_body.agents.layout_agent.YOLO')
    async def test_page_without_image_bytes(
        self,
        mock_yolo_class,
        mock_yolo_model,
        mock_config
    ):
        """Test 5: Page without raw_image_bytes is skipped gracefully."""
        mock_yolo_class.return_value = mock_yolo_model
        
        # Create document without raw_image_bytes
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
                    raw_image_bytes=None,  # No image bytes
                    regions=[]
                )
            ],
            processing_status=ProcessingStatus.IN_PROGRESS
        )
        
        # Create agent and process
        agent = LayoutAgent(mock_config)
        result = await agent.process(doc)
        
        # Assert page was skipped, no regions added
        assert len(result.pages[0].regions) == 0
    
    @pytest.mark.asyncio
    @patch('local_body.agents.layout_agent.YOLO')
    async def test_draw_layout_visualization(
        self,
        mock_yolo_class,
        mock_yolo_model,
        mock_config,
        sample_document_with_image
    ):
        """Test 6: draw_layout produces image bytes with bounding boxes."""
        mock_yolo_class.return_value = mock_yolo_model
        
        # Create agent
        agent = LayoutAgent(mock_config)
        
        # Create test regions manually with proper content
        regions = [
            Region(
                bbox=BoundingBox(x=10, y=10, width=40, height=40),
                region_type=RegionType.TABLE,
                content=ImageContent(description="test table", confidence=0.9),
                confidence=0.9,
                extraction_method="yolov8"
            ),
            Region(
                bbox=BoundingBox(x=60, y=60, width=30, height=30),
                region_type=RegionType.TEXT,
                content=TextContent(text="", confidence=0.85),
                confidence=0.85,
                extraction_method="yolov8"
            )
        ]
        
        # Draw layout
        result_bytes = agent.draw_layout(
            sample_document_with_image.pages[0].raw_image_bytes,
            regions
        )
        
        # Assert result is bytes
        assert isinstance(result_bytes, bytes)
        assert len(result_bytes) > 0
