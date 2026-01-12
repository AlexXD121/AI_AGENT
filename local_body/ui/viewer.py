"""Document viewer component with bounding box visualization.

This module provides PDF page rendering with confidence-based color-coded
bounding boxes for detected regions.
"""

from typing import List, Optional
from io import BytesIO

import streamlit as st
from PIL import Image, ImageDraw, ImageFont
try:
    from pdf2image import convert_from_path
except ImportError:
    convert_from_path = None

from loguru import logger

from local_body.core.datamodels import Region, BoundingBox


class DocumentViewer:
    """Streamlit component for rendering PDF pages with bounding boxes.
    
    Features:
    - PDF to image conversion
    - Confidence-based color coding (green/yellow/red)
    - Region type labels
    - Responsive scaling
    """
    
    # Color scheme based on confidence
    COLORS = {
        "high": "#00FF00",      # Green for confidence > 0.90
        "medium": "#FFFF00",    # Yellow for 0.70 < confidence <= 0.90
        "low": "#FF0000"        # Red for confidence <= 0.70
    }
    
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
            # Check if pdf2image is available
            if convert_from_path is None:
                st.error(
                    "⚠️ PDF viewer requires pdf2image. "
                    "Install: `pip install pdf2image` and poppler-utils"
                )
                return
            
            # Convert PDF page to image
            with st.spinner(f"Loading page {page_number}..."):
                images = convert_from_path(
                    pdf_path,
                    first_page=page_number,
                    last_page=page_number,
                    dpi=150  # Balance between quality and performance
                )
                
                if not images:
                    st.error(f"Could not load page {page_number}")
                    return
                
                image = images[0]
            
            # Draw bounding boxes if provided
            if regions:
                # Filter regions for this page
                page_regions = [r for r in regions if hasattr(r, 'page_number') and r.page_number == page_number]
                
                if page_regions:
                    image = self._draw_bounding_boxes(image, page_regions)
                    st.caption(f"📊 {len(page_regions)} regions detected")
                else:
                    st.caption("No regions detected on this page")
            
            # Display image
            st.image(image, use_column_width=True)
            
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
            st.image(image, use_column_width=True)
            
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
