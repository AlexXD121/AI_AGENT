"""Document viewer component for PDF rendering with bounding boxes.

Displays PDF pages as images with overlaid region annotations.
"""

from io import BytesIO
from typing import List, Optional

import streamlit as st
from PIL import Image, ImageDraw, ImageFont
from loguru import logger

# Try pdf2image first, fallback to PyMuPDF
try:
    from pdf2image import convert_from_path
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False

# PyMuPDF fallback
try:
    import fitz
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

from local_body.core.datamodels import Region, BoundingBox


class DocumentViewer:
    """Streamlit component for rendering PDF pages with bounding boxes.
    
    Features:
    - PDF to image conversion
    - Confidence-based color coding (green/yellow/red)
    - Region type labels
    - Responsive scaling
    """
    
    # Professional fintech color palette
    COLORS = {
        "high": "#10B981",      # Emerald green (high confidence >90%)
        "medium": "#F59E0B",    # Amber (medium confidence 70-90%)
        "low": "#EF4444"        # Red (low confidence <70%)
    }
    
    # Thinner, more elegant stroke
    BOX_STROKE_WIDTH = 2
    
    def __init__(self):
        """Initialize DocumentViewer."""
        if convert_from_path is None:
            logger.warning(
                "pdf2image not available. Install with: pip install pdf2image. "
                "Also requires poppler-utils: brew install poppler (Mac) or "
                "apt-get install poppler-utils (Linux)"
            )
    
    def _get_confidence_color(self, confidence: float) -> str:
        """Get color based on confidence score.
        
        Args:
            confidence: Confidence score (0.0-1.0)
        
        Returns:
            Hex color string
        """
        if confidence > 0.90:
            return self.COLORS["high"]
        elif confidence > 0.70:
            return self.COLORS["medium"]
        else:
            return self.COLORS["low"]
    
    def _draw_bounding_boxes(
        self,
        image: Image.Image,
        regions: List[Region]
    ) -> Image.Image:
        """Draw bounding boxes on image with confidence-based colors.
        
        Args:
            image: PIL Image to draw on
            regions: List of detected regions with bounding boxes
        
        Returns:
            Image with bounding boxes drawn
        """
        draw = ImageDraw.Draw(image)
        img_width, img_height = image.size
        
        # Try to load a font (fallback to default if not available)
        try:
            font = ImageFont.truetype("arial.ttf", 12)
        except:
            font = ImageFont.load_default()
        
        for region in regions:
            if not region.bbox:
                continue
            
            bbox = region.bbox
            confidence = region.confidence if hasattr(region, 'confidence') else 0.8
            color = self._get_confidence_color(confidence)
            
            # Convert bbox coordinates to pixel coordinates
            # Assuming bbox is in absolute pixel coordinates
            # If your bbox uses normalized coordinates (0-1), multiply by image dimensions
            x1 = int(bbox.x)
            y1 = int(bbox.y)
            x2 = int(bbox.x + bbox.width)
            y2 = int(bbox.y + bbox.height)
            
            # Draw rectangle
            draw.rectangle(
                [(x1, y1), (x2, y2)],
                outline=color,
                width=3
            )
            
            # Draw label (region type + confidence)
            region_type = region.region_type.value if hasattr(region, 'region_type') else "unknown"
            label = f"{region_type} ({confidence:.2f})"
            
            # Draw label background
            text_bbox = draw.textbbox((x1, y1 - 20), label, font=font)
            draw.rectangle(text_bbox, fill=color)
            draw.text((x1, y1 - 20), label, fill="#000000", font=font)
        
        return image
    
    def _render_pdf_page(
        self,
        pdf_path: str,
        page_number: int
    ) -> Image.Image:
        """Render a PDF page as PIL Image.
        
        Uses PyMuPDF by default (no system dependencies needed).
        Falls back to pdf2image only if explicitly available.
        
        Args:
            pdf_path: Path to PDF file
            page_number: Page number (1-indexed)
            
        Returns:
            PIL Image of the rendered page
        """
        # Use PyMuPDF as primary (no Poppler needed!)
        if PYMUPDF_AVAILABLE:
            return self._render_pdf_page_pymupdf(pdf_path, page_number)
        
        # Only try pdf2image if PyMuPDF not available
        if PDF2IMAGE_AVAILABLE:
            try:
                pages = convert_from_path(
                    pdf_path,
                    first_page=page_number,
                    last_page=page_number,
                    dpi=150
                )
                if pages:
                    return pages[0]
            except Exception as e:
                logger.error(f"pdf2image failed: {e}")
        
        # No renderer available
        raise RuntimeError(
            "No PDF renderer available. Install PyMuPDF: pip install PyMuPDF"
        )
    
    def _render_pdf_page_pymupdf(
        self,
        pdf_path: str,
        page_number: int
    ) -> Image.Image:
        """Render PDF page using PyMuPDF (fallback).
        
        Args:
            pdf_path: Path to PDF file
            page_number: Page number (1-indexed)
            
        Returns:
            PIL Image of the rendered page
        """
        pdf_doc = fitz.open(pdf_path)
        try:
            # PyMuPDF uses 0-indexed pages
            page = pdf_doc[page_number - 1]
            
            # Render at 150 DPI (zoom factor 2.08)
            zoom = 150 / 72
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            
            # Convert to PIL Image
            img_data = pix.tobytes("png")
            img = Image.open(BytesIO(img_data))
            
            return img
        finally:
            pdf_doc.close()
    
    def render_page(
        self,
        pdf_path: str,
        page_number: int,
        regions: Optional[List[Region]] = None
    ) -> None:
        """Render a PDF page with bounding boxes in Streamlit.
        
        Args:
            pdf_path: Path to PDF file
            page_number: Page number to render (1-indexed)
            regions: Optional list of regions to draw bounding boxes for
        """
        try:
            # Convert PDF page to image
            with st.spinner(f"Loading page {page_number}..."):
                image = self._render_pdf_page(pdf_path, page_number)
            
            # Draw bounding boxes if provided
            if regions:
                # Filter regions for this page
                page_regions = [r for r in regions if hasattr(r, 'page_number') and r.page_number == page_number]
                
                if page_regions:
                    image = self._draw_bounding_boxes(image, page_regions)
                    st.caption(f"{len(page_regions)} regions detected")
                else:
                    st.caption("No regions detected on this page")
            
            # Display image
            st.image(image, width="stretch")
            
            # Show confidence legend
            if regions:
                with st.expander("🎨 Confidence Color Legend"):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.markdown(f"**🟢 High** (>90%)")
                    with col2:
                        st.markdown(f"**🟡 Medium** (70-90%)")
                    with col3:
                        st.markdown(f"**🔴 Low** (< 70%)")
        
        except Exception as e:
            logger.error(f"Error rendering page {page_number}: {e}")
            st.error(f"Failed to render page: {str(e)}")
    
    def render_from_bytes(
        self,
        image_bytes: bytes,
        regions: Optional[List[Region]] = None
    ) -> None:
        """Render an image from bytes with bounding boxes.
        
        Useful when the image is already in memory (e.g., from document.pages[i].raw_image_bytes).
        
        Args:
            image_bytes: Image data as bytes
            regions: Optional list of regions to draw bounding boxes for
        """
        try:
            # Load image from bytes
            image = Image.open(BytesIO(image_bytes))
            
            # Draw bounding boxes if provided
            if regions:
                image = self._draw_bounding_boxes(image, regions)
                st.caption(f"📊 {len(regions)} regions detected")
            
            # Display image
            st.image(image, width="stretch")
            
            # Show confidence legend
            if regions:
                with st.expander("🎨 Confidence Color Legend"):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.markdown("**🟢 High** (>90%)")
                    with col2:
                        st.markdown("**🟡 Medium** (70-90%)")
                    with col3:
                        st.markdown("**🔴 Low** (<70%)")
        
        except Exception as e:
            logger.error(f"Error rendering image from bytes: {e}")
            st.error(f"Failed to render image: {str(e)}")
