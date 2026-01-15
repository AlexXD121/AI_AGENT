"""Document loader for PDF files with validation and preprocessing.

Handles PDF loading, metadata extraction, and page image conversion
with robust error handling for corrupted files.
"""

import io
from pathlib import Path
from typing import List

from loguru import logger
from PIL import Image

# PDF reading
from pypdf import PdfReader
from pypdf.errors import PdfReadError

# Try pdf2image first (requires poppler), fallback to PyMuPDF
try:
    from pdf2image import convert_from_path
    from pdf2image.exceptions import (
        PDFInfoNotInstalledError,
        PDFPageCountError
    )
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False
    logger.warning("pdf2image not available, will use PyMuPDF fallback")

# PyMuPDF fallback (no system dependencies)
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    logger.warning("PyMuPDF not available")

from local_body.core.datamodels import (
    Document,
    DocumentMetadata,
    Page,
    ProcessingStatus
)


class DocumentLoadError(Exception):
    """Custom exception for document loading errors."""
    pass


class DocumentLoader:
    """Loader for PDF documents with metadata extraction and image conversion.
    
    This class handles:
    - PDF validation and error handling (Requirement 15.1)
    - Metadata extraction (title, author, page count)
    - High-quality image conversion (DPI=300)
    - Structured Document object creation
    """
    
    def __init__(self, dpi: int = 300):
        """Initialize the document loader.
        
        Args:
            dpi: DPI for PDF to image conversion (default: 300)
        """
        self.dpi = dpi
    
    def load_document(self, file_path: str) -> Document:
        """Load a PDF document and convert to Document object.
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            Document object with metadata and page images
            
        Raises:
            DocumentLoadError: If file is invalid, corrupted, or cannot be processed
        """
        file_path = Path(file_path)
        
        # Validation: Check file exists
        if not file_path.exists():
            raise DocumentLoadError(f"File not found: {file_path}")
        
        # Validation: Check file is PDF
        if file_path.suffix.lower() != '.pdf':
            raise DocumentLoadError(
                f"Invalid file type: {file_path.suffix}. Expected .pdf"
            )
        
        logger.info(f"Loading document: {file_path}")
        
        try:
            # Extract metadata using pypdf
            metadata = self._extract_metadata(file_path)
            
            # Convert PDF pages to images
            page_images = self._convert_to_images(file_path)
            
            # Create Page objects
            pages = []
            for page_num, pil_image in enumerate(page_images, start=1):
                # Convert PIL image to bytes
                img_bytes = io.BytesIO()
                pil_image.save(img_bytes, format='PNG')
                raw_image_bytes = img_bytes.getvalue()
                
                # Create Page object
                page = Page(
                    page_number=page_num,
                    regions=[],  # Will be populated by layout analysis
                    raw_image_bytes=raw_image_bytes,
                    processed_image_bytes=None  # Will be set after preprocessing
                )
                pages.append(page)
            
            # Create Document object
            document = Document(
                file_path=str(file_path),
                pages=pages,
                metadata=metadata,
                processing_status=ProcessingStatus.PENDING
            )
            
            logger.success(
                f"Successfully loaded document: {file_path.name} "
                f"({len(pages)} pages)"
            )
            
            return document
            
        except (PdfReadError, PDFPageCountError) as e:
            error_msg = f"Corrupted or invalid PDF file: {file_path}. Error: {e}"
            logger.error(error_msg)
            raise DocumentLoadError(error_msg) from e
            
        except PDFInfoNotInstalledError as e:
            error_msg = (
                "Poppler is not installed. Please install poppler-utils:\n"
                "  Ubuntu/Debian: sudo apt-get install poppler-utils\n"
                "  macOS: brew install poppler\n"
                "  Windows: Download from https://github.com/oschwartz10612/poppler-windows/releases"
            )
            logger.error(error_msg)
            raise DocumentLoadError(error_msg) from e
            
        except Exception as e:
            error_msg = f"Failed to load document {file_path}: {e}"
            logger.error(error_msg)
            raise DocumentLoadError(error_msg) from e
    
    def _extract_metadata(self, file_path: Path) -> DocumentMetadata:
        """Extract metadata from PDF file.
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            DocumentMetadata object
        """
        try:
            reader = PdfReader(str(file_path))
            
            # Extract metadata
            info = reader.metadata
            title = info.get('/Title', None) if info else None
            author = info.get('/Author', None) if info else None
            
            # Get page count
            page_count = len(reader.pages)
            
            # Get file size
            file_size_bytes = file_path.stat().st_size
            
            metadata = DocumentMetadata(
                title=title,
                author=author,
                created_date=None,  # Can be extracted if needed
                page_count=page_count,
                file_size_bytes=file_size_bytes,
                document_type="pdf"
            )
            
            logger.debug(
                f"Extracted metadata: title={title}, author={author}, "
                f"pages={page_count}, size={file_size_bytes} bytes"
            )
            
            return metadata
            
        except PdfReadError:
            # Re-raise PDF corruption errors - don't swallow them
            raise
            
        except Exception as e:
            logger.warning(f"Failed to extract full metadata: {e}")
            # Return minimal metadata for other errors
            return DocumentMetadata(
                title=file_path.stem,
                author=None,
                page_count=0,  # Will be updated after conversion
                file_size_bytes=file_path.stat().st_size,
                document_type="pdf"
            )
    
    def _convert_to_images(self, file_path: Path) -> List[Image.Image]:
        """Convert PDF pages to PIL Images.
        
        Tries pdf2image first, falls back to PyMuPDF if poppler not available.
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            List of PIL Image objects (one per page)
        """
        logger.debug(f"Converting PDF to images at {self.dpi} DPI...")
        
        # Use PyMuPDF as primary (no Poppler needed, faster)
        if PYMUPDF_AVAILABLE:
            return self._convert_to_images_pymupdf(file_path)
        
        # Only try pdf2image if PyMuPDF not available
        if PDF2IMAGE_AVAILABLE:
            try:
                images = convert_from_path(
                    str(file_path),
                    dpi=self.dpi,
                    fmt='PNG'
                )
                logger.debug(f"Converted {len(images)} pages using pdf2image")
                return images
            except (PDFInfoNotInstalledError, Exception) as e:
                logger.error(f"pdf2image failed: {e}")
        
        # No PDF conversion available
        raise DocumentLoadError(
            "No PDF conversion library available. Install PyMuPDF: pip install PyMuPDF"
        )
    
    def _convert_to_images_pymupdf(self, file_path: Path) -> List[Image.Image]:
        """Convert PDF to images using PyMuPDF (fallback method).
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            List of PIL Image objects
        """
        logger.debug("Using PyMuPDF for PDF conversion (Poppler not available)")
        
        images = []
        pdf_document = fitz.open(str(file_path))
        
        try:
            # Convert DPI to zoom factor (72 DPI is default)
            zoom = self.dpi / 72
            mat = fitz.Matrix(zoom, zoom)
            
            for page_num in range(len(pdf_document)):
                page = pdf_document[page_num]
                
                # Render page to pixmap
                pix = page.get_pixmap(matrix=mat)
                
                # Convert pixmap to PIL Image
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))
                images.append(img)
            
            logger.debug(f"Converted {len(images)} pages using PyMuPDF")
            return images
        
        finally:
            pdf_document.close()
