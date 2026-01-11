"""OCR agent using PaddleOCR and TrOCR for robust text extraction.

This module implements the OCRAgent class with a 3-stage adaptive retry pipeline:
1. Standard OCR (Paddle)
2. Enhanced OCR (Sharpen/Denoise + Paddle)
3. Handwriting Fallback (TrOCR)
"""

import io
import re
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from loguru import logger
from PIL import Image

try:
    from paddleocr import PaddleOCR
except ImportError:
    logger.warning("paddleocr not installed. OCRAgent will not work without it.")
    PaddleOCR = None

from local_body.agents.base import BaseAgent
from local_body.core.datamodels import (
    Document, Page, Region, RegionType, BoundingBox, TextContent, TableContent
)
from local_body.utils.preprocessing import ImagePreprocessor


class TrOCRHandler:
    """Lazy-loaded TrOCR handler for handwriting recognition fallback."""
    
    def __init__(self):
        self._model = None
        self._processor = None
        self._device = "cpu"
        logger.debug("TrOCRHandler initialized (models not loaded)")
    
    def _load_model(self):
        if self._model is not None:
            return
        
        logger.info("Loading TrOCR model (microsoft/trocr-base-handwritten)...")
        try:
            from transformers import VisionEncoderDecoderModel, TrOCRProcessor
            
            self._processor = TrOCRProcessor.from_pretrained("microsoft/trocr-base-handwritten")
            self._model = VisionEncoderDecoderModel.from_pretrained("microsoft/trocr-base-handwritten")
            self._model.to(self._device)
            self._model.eval()
            logger.success("TrOCR model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load TrOCR: {e}")
            raise
    
    def recognize_handwriting(self, image_bytes: bytes) -> str:
        """Extract text from handwritten image using Transformer model."""
        if self._model is None:
            self._load_model()
        
        try:
            pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            pixel_values = self._processor(images=pil_image, return_tensors="pt").pixel_values.to(self._device)
            
            generated_ids = self._model.generate(pixel_values)
            text = self._processor.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()
            return text
        except Exception as e:
            logger.error(f"TrOCR failed: {e}")
            return ""


class OCRAgent(BaseAgent):
    """Agent for OCR text/table extraction with 3-stage adaptive retry."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(agent_type="ocr", config=config)
        
        if PaddleOCR is None:
            raise ImportError("paddleocr package is required. Install with: pip install paddleocr paddlepaddle")
        
        self.confidence_threshold = self.get_config("confidence_threshold", 0.85)
        self.fallback_threshold = self.get_config("fallback_threshold", 0.60)
        
        # Initialize PaddleOCR
        lang = self.get_config("lang", "en")
        use_angle_cls = self.get_config("use_angle_cls", True)
        try:
            self.ocr = PaddleOCR(use_angle_cls=use_angle_cls, lang=lang)
            logger.success(f"PaddleOCR loaded (lang={lang})")
        except Exception as e:
            logger.error(f"Failed to load PaddleOCR: {e}")
            raise
        
        self.preprocessor = ImagePreprocessor()
        
        # Initialize TrOCR (Lazy)
        self.enable_trocr = self.get_config("enable_trocr", True)
        self.trocr_handler = TrOCRHandler() if self.enable_trocr else None

    async def process(self, document: Document) -> Document:
        """Process document regions."""
        logger.info(f"Processing document {document.id} for OCR extraction")
        
        for page in document.pages:
            if not page.raw_image_bytes:
                continue
            
            for region in page.regions:
                if region.region_type not in [RegionType.TEXT, RegionType.TABLE]:
                    continue
                
                try:
                    # Crop
                    crop_bytes = self._crop_region(page.raw_image_bytes, region.bbox)
                    
                    # Run 3-Stage Pipeline
                    text, confidence = await self._process_single_region(crop_bytes, region.id)
                    
                    # Store Result
                    if region.region_type == RegionType.TEXT:
                        region.content = TextContent(text=text, confidence=confidence)
                    else:
                        rows = self._parse_table_structure(text)
                        region.content = TableContent(rows=rows, confidence=confidence)
                        
                    logger.debug(f"Region {region.id} extracted: {confidence:.1%}")
                    
                except Exception as e:
                    logger.error(f"Region {region.id} failed: {e}")
                    region.content = TextContent(text="", confidence=0.0)
        
        return document

    async def _process_single_region(self, crop_bytes: bytes, region_id: str) -> Tuple[str, float]:
        """Execute 3-Stage Adaptive Retry Pipeline."""
        
        # --- Stage 1: Standard OCR ---
        result1 = self._run_ocr(crop_bytes)
        text, conf = self._parse_ocr_result(result1)
        
        if conf >= self.confidence_threshold:
            return text, conf
            
        # --- Stage 2: Enhanced OCR ---
        try:
            # Decode for quality assessment
            nparr = np.frombuffer(crop_bytes, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if image is not None:
                quality = self.preprocessor.assess_image_quality(image)
                is_blurry = quality.get('is_blurry', False)
                
                logger.info(f"Region {region_id}: Low conf ({conf:.1%}). Blurry: {is_blurry}. Enhancing...")
                
                enhanced = image
                if is_blurry:
                    enhanced = self.preprocessor.sharpen(image, strength=1.0)
                
                # Encode back
                success, encoded = cv2.imencode('.png', enhanced)
                if success:
                    enhanced_bytes = self.preprocessor.preprocess_for_ocr(
                        encoded.tobytes(), denoise_strength=12, apply_binarization=True
                    )
                    
                    result2 = self._run_ocr(enhanced_bytes)
                    text2, conf2 = self._parse_ocr_result(result2)
                    
                    if conf2 > conf:
                        text, conf = text2, conf2
                        logger.debug(f"Region {region_id}: Enhanced OCR improved to {conf:.1%}")
        except Exception as e:
            logger.error(f"Region {region_id}: Enhancement failed: {e}")
        
        # --- Stage 3: TrOCR Fallback ---
        if conf < self.fallback_threshold and self.trocr_handler and text.strip():
            logger.warning(f"Region {region_id}: Low conf ({conf:.1%}). Attempting TrOCR fallback...")
            try:
                trocr_text = self.trocr_handler.recognize_handwriting(crop_bytes)
                if trocr_text and len(trocr_text) > 2:
                    logger.success(f"Region {region_id}: TrOCR recovered: '{trocr_text}'")
                    return trocr_text, 0.95
            except Exception as e:
                logger.error(f"Region {region_id}: TrOCR failed: {e}")
                
        return text, conf

    def _crop_region(self, image_bytes: bytes, bbox: BoundingBox) -> bytes:
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if image is None: 
            raise ValueError("Decode failed")
        h, w = image.shape[:2]
        x1, y1 = max(0, int(bbox.x)), max(0, int(bbox.y))
        x2, y2 = min(w, int(bbox.x + bbox.width)), min(h, int(bbox.y + bbox.height))
        cropped = image[y1:y2, x1:x2]
        success, encoded = cv2.imencode('.png', cropped)
        return encoded.tobytes()

    def _run_ocr(self, image_bytes: bytes) -> List:
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return self.ocr.ocr(image, cls=True)

    def _parse_ocr_result(self, ocr_result: List) -> Tuple[str, float]:
        if not ocr_result or not ocr_result[0]: 
            return "", 0.0
        texts, confs = [], []
        for line in ocr_result[0]:
            if line and len(line) >= 2:
                texts.append(line[1][0])
                confs.append(line[1][1])
        return "\n".join(texts), (sum(confs)/len(confs) if confs else 0.0)

    def _parse_table_structure(self, text: str) -> List[List[str]]:
        if not text: 
            return [[]]
        return [re.split(r'\s{2,}', line.strip()) for line in text.split('\n')]
    
    def _extract_numeric_value(self, text: str) -> Optional[float]:
        """Extract and normalize numeric values from text.
        
        Handles: $1,500.00 → 1500.0, 1.5M → 1,500,000.0
        """
        text = text.strip().replace('$', '').replace(',', '')
        pattern = r'([\d.]+)\s*([KMB])?'
        match = re.search(pattern, text, re.IGNORECASE)
        
        if not match:
            return None
        
        try:
            value = float(match.group(1))
            suffix = match.group(2)
            
            if suffix:
                suffix = suffix.upper()
                if suffix == 'K':
                    value *= 1_000
                elif suffix == 'M':
                    value *= 1_000_000
                elif suffix == 'B':
                    value *= 1_000_000_000
            
            return value
        except (ValueError, AttributeError):
            return None
