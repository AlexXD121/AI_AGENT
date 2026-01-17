"""Layout analysis agent using YOLOv8-Nano for document region detection.

This module implements the LayoutAgent class for detecting and classifying
document regions (text, table, image, chart) using YOLOv8-Nano object detection.
"""

import io
from typing import Any, Dict, List, Optional

import cv2
import numpy as np
from loguru import logger
from PIL import Image

try:
    from ultralytics import YOLO
except ImportError:
    logger.warning("ultralytics not installed. LayoutAgent will not work without it.")
    YOLO = None

from local_body.agents.base import BaseAgent
from local_body.core.datamodels import (
    Document,
    Page,
    Region,
    RegionType,
    BoundingBox,
    TextContent,
    ImageContent,
)


class LayoutAgent(BaseAgent):
    """Agent for document layout analysis using YOLOv8-Nano.
    
    Detects and classifies document regions into:
    - Text blocks
    - Tables
    - Images/Figures
    - Charts
    
    Uses YOLOv8n for efficient CPU-based inference.
    """
    
    # Placeholder mapping for standard YOLOv8n (COCO dataset)
    # For production, use a document-layout fine-tuned model (PublayNet, DocBank)
    YOLO_TO_REGION_TYPE = {
        0: RegionType.IMAGE,    # person -> image (placeholder)
        16: RegionType.IMAGE,   # dog -> image (placeholder)
        17: RegionType.IMAGE,   # cat -> image (placeholder)
        # For doc-layout model mapping:
        # 0: RegionType.TEXT,
        # 1: RegionType.TABLE,
        # 2: RegionType.IMAGE,
        # 3: RegionType.CHART,
    }
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the layout agent.
        
        Args:
            config: Configuration dictionary with:
                - confidence_threshold: Minimum confidence for detections (default 0.5)
                - model_path: Path to YOLOv8 model (default 'yolov8n.pt')
                - device: Device for inference (default 'cpu')
        """
        super().__init__(agent_type="layout", config=config)
        
        if YOLO is None:
            raise ImportError(
                "ultralytics package is required for LayoutAgent. "
                "Install with: pip install ultralytics"
            )
        
        # Get configuration
        self.confidence_threshold = self.get_config("confidence_threshold", 0.5)
        self.model_path = self.get_config("model_path", "yolov8n.pt")
        self.device = self.get_config("device", "cpu")
        
        # Load YOLOv8 model
        logger.info(f"Loading YOLOv8 model: {self.model_path} on device: {self.device}")
        try:
            self.model = YOLO(self.model_path)
            self.model.to(self.device)
            logger.success(f"YOLOv8 model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load YOLOv8 model: {e}")
            raise
    
    async def process(self, document: Document) -> Document:
        """Process document to detect and classify layout regions.
        
        Args:
            document: Document with pages containing raw_image_bytes
            
        Returns:
            Document with updated page.regions for each page
        """
        logger.info(f"Processing document {document.id} for layout analysis")
        
        for page_idx, page in enumerate(document.pages):
            logger.debug(f"Processing page {page.page_number}")
            
            # Skip pages without images
            if not page.raw_image_bytes:
                logger.warning(f"Page {page.page_number} has no raw_image_bytes, skipping")
                continue
            
            # Convert raw bytes to image
            try:
                image = self._bytes_to_image(page.raw_image_bytes)
            except Exception as e:
                logger.error(f"Failed to convert page {page.page_number} image: {e}")
                continue
            
            # Run YOLO inference
            try:
                results = self.model(image, verbose=False)
                regions = self._extract_regions(results[0], page.page_number, image.shape)
                
                # Full-page fallback if no regions detected
                if len(regions) == 0:
                    logger.warning(f"No layout regions detected on page {page.page_number}. Falling back to full-page processing.")
                    regions = self._create_full_page_region(image.shape, page.page_number)
                
                # Update page regions
                page.regions.extend(regions)
                logger.info(f"Detected {len(regions)} regions on page {page.page_number}")
                
            except Exception as e:
                logger.error(f"YOLO inference failed on page {page.page_number}: {e}")
                continue
        
        return document
    
    def _bytes_to_image(self, image_bytes: bytes) -> np.ndarray:
        """Convert raw image bytes to numpy array for YOLO.
        
        Args:
            image_bytes: Raw image bytes (PNG, JPEG, etc.)
            
        Returns:
            Numpy array in BGR format (OpenCV)
        """
        # Convert bytes to PIL Image
        pil_image = Image.open(io.BytesIO(image_bytes))
        
        # Convert to RGB if needed
        if pil_image.mode != 'RGB':
            pil_image = pil_image.convert('RGB')
        
        # Convert to numpy array (RGB)
        image_np = np.array(pil_image)
        
        # Convert RGB to BGR for OpenCV/YOLO
        image_bgr = cv2.cvtColor(image_np, cv2.COLOR_RGB2BGR)
        
        return image_bgr
    
    def _extract_regions(self, result, page_number: int, image_shape: tuple) -> List[Region]:
        """Extract regions from YOLO detection results.
        
        Args:
            result: YOLO Results object
            page_number: Current page number for logging
            
        Returns:
            List of detected Region objects
        """
        regions = []
        
        # Get detections
        boxes = result.boxes
        
        if boxes is None or len(boxes) == 0:
            logger.debug(f"No detections on page {page_number}")
            return regions
        
        for box in boxes:
            # Extract box coordinates (xyxy format)
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
            
            # Extract confidence and class
            confidence = float(box.conf[0].cpu().numpy())
            cls_id = int(box.cls[0].cpu().numpy())
            
            # Filter by confidence threshold
            if confidence < self.confidence_threshold:
                logger.debug(f"Skipping detection with low confidence: {confidence:.2f}")
                continue
            
            # Map YOLO class to RegionType
            region_type = self.YOLO_TO_REGION_TYPE.get(cls_id, RegionType.IMAGE)
            
            # Calculate bounding box
            bbox = BoundingBox(
                x=float(x1),
                y=float(y1),
                width=float(x2 - x1),
                height=float(y2 - y1)
            )
            
            # Validate bounding box (non-zero area)
            if bbox.width <= 0 or bbox.height <= 0:
                logger.warning(f"Invalid bounding box with zero area, skipping")
                continue
            
            # Create placeholder content based on region type
            # (Real content extraction happens in OCRAgent/VisionAgent)
            if region_type == RegionType.TEXT:
                content = TextContent(text="", confidence=confidence)
            else:
                content = ImageContent(
                    description="",  # Placeholder
                    confidence=confidence
                )
            
            # Create Region object
            region = Region(
                bbox=bbox,
                region_type=region_type,
                content=content,
                confidence=confidence,
                extraction_method="yolov8"
            )
            
            regions.append(region)
            logger.debug(
                f"Detected {region_type.value} region at ({x1:.0f},{y1:.0f}) "
                f"with confidence {confidence:.2f}"
            )
        
        return regions
    
    def _create_full_page_region(self, image_shape: tuple, page_number: int) -> List[Region]:
        """Create a full-page TEXT region as fallback when no regions detected.
        
        Args:
            image_shape: Shape of the image (height, width, channels)
            page_number: Page number for logging
            
        Returns:
            List containing a single full-page region
        """
        height, width = image_shape[:2]
        
        bbox = BoundingBox(
            x=0.0,
            y=0.0,
            width=float(width),
            height=float(height)
        )
        
        content = TextContent(text="", confidence=1.0)
        
        region = Region(
            bbox=bbox,
            region_type=RegionType.TEXT,
            content=content,
            confidence=1.0,
            extraction_method="fullpage_fallback"
        )
        
        logger.info(f"Created full-page region for page {page_number} ({width}x{height})")
        return [region]
    
    def draw_layout(self, image_bytes: bytes, regions: List[Region]) -> bytes:
        """Draw bounding boxes on image for visualization.
        
        Args:
            image_bytes: Original image bytes
            regions: List of detected regions
            
        Returns:
            Image bytes with bounding boxes drawn
        """
        # Convert to OpenCV image
        image = self._bytes_to_image(image_bytes)
        
        # Color mapping for region types
        color_map = {
            RegionType.TEXT: (255, 0, 0),      # Blue
            RegionType.TABLE: (0, 0, 255),     # Red
            RegionType.IMAGE: (0, 255, 0),     # Green
            RegionType.CHART: (255, 255, 0),   # Cyan
        }
        
        # Draw each region
        for region in regions:
            color = color_map.get(region.region_type, (128, 128, 128))
            
            # Get coordinates
            x1 = int(region.bbox.x)
            y1 = int(region.bbox.y)
            x2 = int(region.bbox.x + region.bbox.width)
            y2 = int(region.bbox.y + region.bbox.height)
            
            # Draw rectangle
            cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
            
            # Draw label
            label = f"{region.region_type.value} {region.confidence:.2f}"
            cv2.putText(
                image, label, (x1, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2
            )
        
        # Convert back to bytes
        _, buffer = cv2.imencode('.png', image)
        return buffer.tobytes()
