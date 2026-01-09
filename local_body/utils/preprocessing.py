"""Image preprocessing utilities for document processing.

This module provides image enhancement and preprocessing functions
to improve OCR accuracy and document analysis quality.
"""

import io
from typing import Optional

import cv2
import numpy as np
from loguru import logger
from PIL import Image


class ImagePreprocessor:
    """Preprocessor for document images to improve OCR quality.
    
    This class implements various image enhancement techniques including:
    - Grayscale conversion
    - Noise reduction (Requirement 15.2)
    - Binarization for better text extraction
    - Skew correction
    """
    
    def __init__(self):
        """Initialize the image preprocessor."""
        pass
    
    def to_grayscale(self, image: np.ndarray) -> np.ndarray:
        """Convert image to grayscale.
        
        Args:
            image: Input image as numpy array (BGR or RGB)
            
        Returns:
            Grayscale image as numpy array
        """
        if len(image.shape) == 2:
            # Already grayscale
            return image
        
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        logger.debug("Converted image to grayscale")
        return gray
    
    def denoise(self, image: np.ndarray, strength: int = 10) -> np.ndarray:
        """Remove noise from image using Non-Local Means Denoising.
        
        This improves OCR accuracy on scanned documents (Requirement 15.2).
        
        Args:
            image: Input grayscale image
            strength: Denoising strength (higher = more denoising)
            
        Returns:
            Denoised image
        """
        # Ensure image is grayscale
        if len(image.shape) == 3:
            image = self.to_grayscale(image)
        
        # Apply Non-Local Means Denoising
        denoised = cv2.fastNlMeansDenoising(
            image,
            None,
            h=strength,
            templateWindowSize=7,
            searchWindowSize=21
        )
        
        logger.debug(f"Applied denoising with strength={strength}")
        return denoised
    
    def binarize(
        self, 
        image: np.ndarray, 
        block_size: int = 11, 
        c: int = 2
    ) -> np.ndarray:
        """Binarize image using adaptive thresholding.
        
        Adaptive thresholding handles uneven lighting better than
        simple global thresholding.
        
        Args:
            image: Input grayscale image
            block_size: Size of pixel neighborhood (must be odd)
            c: Constant subtracted from weighted mean
            
        Returns:
            Binary image (black and white)
        """
        # Ensure image is grayscale
        if len(image.shape) == 3:
            image = self.to_grayscale(image)
        
        # Apply adaptive Gaussian thresholding
        binary = cv2.adaptiveThreshold(
            image,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            block_size,
            c
        )
        
        logger.debug(f"Applied adaptive binarization (block_size={block_size})")
        return binary
    
    def correct_skew(self, image: np.ndarray) -> np.ndarray:
        """Correct skew/rotation in scanned documents.
        
        Detects text angle and rotates image to align horizontally.
        
        Args:
            image: Input grayscale image
            
        Returns:
            Deskewed image
        """
        # Ensure image is grayscale
        if len(image.shape) == 3:
            image = self.to_grayscale(image)
        
        # Detect edges
        edges = cv2.Canny(image, 50, 150, apertureSize=3)
        
        # Detect lines using Hough transform
        lines = cv2.HoughLines(edges, 1, np.pi / 180, 200)
        
        if lines is None:
            logger.debug("No lines detected for skew correction")
            return image
        
        # Calculate average angle
        angles = []
        for rho, theta in lines[:, 0]:
            angle = (theta * 180 / np.pi) - 90
            angles.append(angle)
        
        median_angle = np.median(angles)
        
        # Only correct if skew is significant (> 0.5 degrees)
        if abs(median_angle) < 0.5:
            logger.debug("Skew angle too small, skipping correction")
            return image
        
        # Rotate image
        (h, w) = image.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
        rotated = cv2.warpAffine(
            image,
            M,
            (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE
        )
        
        logger.debug(f"Corrected skew by {median_angle:.2f} degrees")
        return rotated
    
    def preprocess_for_ocr(
        self, 
        image_bytes: bytes,
        denoise_strength: int = 10,
        apply_binarization: bool = True,
        correct_skew: bool = False
    ) -> bytes:
        """Complete preprocessing pipeline for OCR.
        
        Applies grayscale conversion, denoising, and binarization
        to prepare image for OCR processing.
        
        Args:
            image_bytes: Input image as bytes
            denoise_strength: Strength of denoising (0 to skip)
            apply_binarization: Whether to binarize the image
            correct_skew: Whether to correct document skew
            
        Returns:
            Preprocessed image as PNG bytes
        """
        logger.debug("Starting OCR preprocessing pipeline")
        
        # Decode image from bytes
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            raise ValueError("Failed to decode image from bytes")
        
        # Convert to grayscale
        image = self.to_grayscale(image)
        
        # Apply denoising if requested
        if denoise_strength > 0:
            image = self.denoise(image, strength=denoise_strength)
        
        # Correct skew if requested
        if correct_skew:
            image = self.correct_skew(image)
        
        # Apply binarization if requested
        if apply_binarization:
            image = self.binarize(image)
        
        # Encode back to bytes (PNG format)
        success, encoded = cv2.imencode('.png', image)
        if not success:
            raise ValueError("Failed to encode preprocessed image")
        
        result_bytes = encoded.tobytes()
        logger.debug(f"Preprocessing complete. Output size: {len(result_bytes)} bytes")
        
        return result_bytes
