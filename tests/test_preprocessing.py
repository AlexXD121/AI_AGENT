"""Unit tests for document preprocessing utilities.

These tests verify temporary file management, image preprocessing,
and document loading functionality.
"""

import pytest
import numpy as np
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path
import tempfile
import shutil

from local_body.utils.file_utils import TempFileManager
from local_body.utils.preprocessing import ImagePreprocessor
from local_body.utils.document_loader import DocumentLoader, DocumentLoadError
from local_body.core.datamodels import Document


class TestTempFileManager:
    """Test suite for TempFileManager."""
    
    def test_temp_dir_cleanup(self):
        """Test 1: Temporary directory is created and cleaned up automatically."""
        manager = TempFileManager()
        temp_dir_path = None
        
        # Use context manager
        with manager.get_temp_dir() as temp_dir:
            temp_dir_path = temp_dir
            # Assert directory exists inside context
            assert temp_dir.exists()
            assert temp_dir.is_dir()
            
            # Create a test file inside
            test_file = temp_dir / "test.txt"
            test_file.write_text("test content")
            assert test_file.exists()
        
        # Assert directory is deleted after context
        assert not temp_dir_path.exists()
    
    def test_temp_dir_cleanup_on_exception(self):
        """Test: Temporary directory is cleaned up even when exception occurs."""
        manager = TempFileManager()
        temp_dir_path = None
        
        try:
            with manager.get_temp_dir() as temp_dir:
                temp_dir_path = temp_dir
                assert temp_dir.exists()
                # Raise exception
                raise ValueError("Test exception")
        except ValueError:
            pass
        
        # Assert directory is still deleted despite exception
        assert not temp_dir_path.exists()
    
    def test_temp_file_cleanup(self):
        """Test: Temporary file is created and cleaned up automatically."""
        manager = TempFileManager()
        temp_file_path = None
        
        with manager.get_temp_file(suffix=".txt") as temp_file:
            temp_file_path = temp_file
            assert temp_file.exists()
            
            # Write some content
            temp_file.write_text("test")
            assert temp_file.read_text() == "test"
        
        # Assert file is deleted
        assert not temp_file_path.exists()


class TestImagePreprocessor:
    """Test suite for ImagePreprocessor."""
    
    def test_to_grayscale(self):
        """Test: Color image is converted to grayscale."""
        preprocessor = ImagePreprocessor()
        
        # Create a color image (BGR)
        color_image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        
        # Convert to grayscale
        gray_image = preprocessor.to_grayscale(color_image)
        
        # Assert output is grayscale (2D array)
        assert len(gray_image.shape) == 2
        assert gray_image.shape == (100, 100)
    
    def test_denoise_reduces_variance(self):
        """Test 2: Denoising reduces image variance (removes noise)."""
        preprocessor = ImagePreprocessor()
        
        # Create a noisy grayscale image
        clean_image = np.ones((100, 100), dtype=np.uint8) * 128
        noise = np.random.randint(-30, 30, (100, 100), dtype=np.int16)
        noisy_image = np.clip(clean_image.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        
        # Calculate variance before denoising
        variance_before = np.var(noisy_image)
        
        # Apply denoising
        denoised = preprocessor.denoise(noisy_image, strength=10)
        
        # Calculate variance after denoising
        variance_after = np.var(denoised)
        
        # Assert variance is reduced (noise is removed)
        assert variance_after < variance_before
    
    def test_binarize(self):
        """Test: Binarization produces binary image (only 0 and 255)."""
        preprocessor = ImagePreprocessor()
        
        # Create a grayscale image with various intensities
        gray_image = np.random.randint(0, 255, (100, 100), dtype=np.uint8)
        
        # Apply binarization
        binary = preprocessor.binarize(gray_image)
        
        # Assert output contains only 0 and 255
        unique_values = np.unique(binary)
        assert len(unique_values) <= 2
        assert all(v in [0, 255] for v in unique_values)
    
    def test_preprocess_for_ocr(self):
        """Test: Complete OCR preprocessing pipeline works."""
        preprocessor = ImagePreprocessor()
        
        # Create a simple test image
        import cv2
        test_image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        
        # Encode to bytes
        success, encoded = cv2.imencode('.png', test_image)
        assert success
        image_bytes = encoded.tobytes()
        
        # Preprocess
        result_bytes = preprocessor.preprocess_for_ocr(image_bytes)
        
        # Assert result is valid bytes
        assert isinstance(result_bytes, bytes)
        assert len(result_bytes) > 0
        
        # Decode and verify it's a valid image
        nparr = np.frombuffer(result_bytes, np.uint8)
        result_image = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
        assert result_image is not None
        assert len(result_image.shape) == 2  # Grayscale


class TestDocumentLoader:
    """Test suite for DocumentLoader."""
    
    def test_load_document_file_not_found(self):
        """Test: DocumentLoadError raised when file doesn't exist."""
        loader = DocumentLoader()
        
        with pytest.raises(DocumentLoadError, match="File not found"):
            loader.load_document("/nonexistent/file.pdf")
    
    def test_load_document_invalid_type(self):
        """Test: DocumentLoadError raised for non-PDF files."""
        loader = DocumentLoader()
        
        # Create a temporary non-PDF file
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            temp_file = Path(f.name)
        
        try:
            with pytest.raises(DocumentLoadError, match="Invalid file type"):
                loader.load_document(str(temp_file))
        finally:
            temp_file.unlink()
    
    @patch('local_body.utils.document_loader.convert_from_path')
    @patch('local_body.utils.document_loader.PdfReader')
    def test_load_document_success(self, mock_pdf_reader, mock_convert):
        """Test 3: Document is loaded successfully with correct metadata."""
        # Create a temporary PDF file
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            temp_pdf = Path(f.name)
            f.write(b"%PDF-1.4\n")  # Minimal PDF header
        
        try:
            # Mock PdfReader
            mock_reader_instance = MagicMock()
            mock_reader_instance.metadata = {
                '/Title': 'Test Document',
                '/Author': 'Test Author'
            }
            mock_reader_instance.pages = [MagicMock(), MagicMock()]  # 2 pages
            mock_pdf_reader.return_value = mock_reader_instance
            
            # Mock convert_from_path to return PIL images
            from PIL import Image
            mock_image_1 = Image.new('RGB', (100, 100), color='white')
            mock_image_2 = Image.new('RGB', (100, 100), color='gray')
            mock_convert.return_value = [mock_image_1, mock_image_2]
            
            # Load document
            loader = DocumentLoader(dpi=300)
            document = loader.load_document(str(temp_pdf))
            
            # Assert document is valid
            assert isinstance(document, Document)
            assert document.metadata.title == 'Test Document'
            assert document.metadata.author == 'Test Author'
            assert document.metadata.page_count == 2
            assert len(document.pages) == 2
            
            # Assert pages have raw image bytes
            for page in document.pages:
                assert page.raw_image_bytes is not None
                assert len(page.raw_image_bytes) > 0
            
            # Verify convert_from_path was called with correct DPI
            mock_convert.assert_called_once()
            call_kwargs = mock_convert.call_args.kwargs
            assert call_kwargs['dpi'] == 300
            
        finally:
            temp_pdf.unlink()
    
    @patch('local_body.utils.document_loader.PdfReader')
    def test_load_document_corrupted_pdf(self, mock_pdf_reader):
        """Test: DocumentLoadError raised for corrupted PDF."""
        # Create a temporary corrupted PDF
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            temp_pdf = Path(f.name)
            f.write(b"corrupted data")
        
        try:
            # Mock PdfReader to raise PdfReadError
            from pypdf.errors import PdfReadError
            mock_pdf_reader.side_effect = PdfReadError("Invalid PDF")
            
            loader = DocumentLoader()
            
            with pytest.raises(DocumentLoadError, match="Corrupted or invalid PDF"):
                loader.load_document(str(temp_pdf))
                
        finally:
            temp_pdf.unlink()
