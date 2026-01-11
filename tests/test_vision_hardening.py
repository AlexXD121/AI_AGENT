"""Tests for VisionAgent security and performance hardening."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from io import BytesIO
from PIL import Image

from local_body.agents.vision_agent import VisionAgent


@pytest.fixture
def vision_agent():
    """Create VisionAgent with test config."""
    config = {
        'brain_secret': 'test-secret-key',
        'vision_max_retries': 3,
        'vision_timeout': 30
    }
    
    # Mock tunnel
    mock_tunnel = MagicMock()
    mock_tunnel.get_public_url = AsyncMock(return_value="http://test-tunnel.ngrok.io")
    
    return VisionAgent(config, mock_tunnel)


@pytest.fixture
def large_image_bytes():
    """Create a large test image (2000x2000)."""
    img = Image.new('RGB', (2000, 2000), color='red')
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    return buffer.getvalue()


@pytest.fixture
def rgba_image_bytes():
    """Create an RGBA test image for conversion testing."""
    img = Image.new('RGBA', (1500, 1500), color=(255, 0, 0, 128))
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    return buffer.getvalue()


class TestImageCompression:
    """Test image compression functionality."""
    
    def test_large_image_compression(self, vision_agent, large_image_bytes):
        """Test 1: Large images are compressed and resized"""
        original_size = len(large_image_bytes)
        
        compressed = vision_agent._compress_image(large_image_bytes)
        
        # Verify compression
        assert len(compressed) < original_size
        
        # Verify dimensions
        img = Image.open(BytesIO(compressed))
        assert img.width <= 1024
        assert img.height <= 1024
        assert img.format == 'JPEG'
    
    def test_small_image_compression(self, vision_agent):
        """Test 2: Small images are still optimized"""
        # Create small image (500x500)
        img = Image.new('RGB', (500, 500), color='blue')
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        original_bytes = buffer.getvalue()
        
        compressed = vision_agent._compress_image(original_bytes)
        
        # Should still compress (PNG to JPEG)
        assert len(compressed) < len(original_bytes)
        
        # Dimensions should remain same
        compressed_img = Image.open(BytesIO(compressed))
        assert compressed_img.width == 500
        assert compressed_img.height == 500
    
    def test_rgba_to_rgb_conversion(self, vision_agent, rgba_image_bytes):
        """Test 3: RGBA images are converted to RGB"""
        compressed = vision_agent._compress_image(rgba_image_bytes)
        
        # Load and verify RGB conversion
        img = Image.open(BytesIO(compressed))
        assert img.mode == 'RGB'
        assert img.format == 'JPEG'
    
    def test_aspect_ratio_maintained(self, vision_agent):
        """Test 4: Aspect ratio is maintained during resize"""
        # Create wide image (3000x1000)
        img = Image.new('RGB', (3000, 1000), color='green')
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        original_bytes = buffer.getvalue()
        
        compressed = vision_agent._compress_image(original_bytes)
        
        # Check dimensions
        compressed_img = Image.open(BytesIO(compressed))
        assert compressed_img.width == 1024
        # Height should be proportional: 1024 * (1000/3000) = 341
        assert 340 <= compressed_img.height <= 342
    
    def test_compression_failure_fallback(self, vision_agent):
        """Test 5: Compression failure returns original bytes"""
        invalid_bytes = b"not an image"
        
        result = vision_agent._compress_image(invalid_bytes)
        
        # Should return original bytes on failure
        assert result == invalid_bytes


class TestAPIAuthentication:
    """Test API key authentication."""
    
    @patch('local_body.agents.vision_agent.httpx.AsyncClient')
    async def test_api_key_in_headers(self, mock_client_class, vision_agent):
        """Test 6: API key is sent in Authorization header"""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'analysis': 'test result'}
        
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client
        
        # Create test image
        img = Image.new('RGB', (100, 100), color='white')
        buffer = BytesIO()
        img.save(buffer, format='JPEG')
        image_bytes = buffer.getvalue()
        
        # Call analyze
        result = await vision_agent.analyze_image_remote(image_bytes, "test query")
        
        # Verify API key was sent
        assert mock_client.post.called
        call_args = mock_client.post.call_args
        assert 'headers' in call_args.kwargs
        assert 'Authorization' in call_args.kwargs['headers']
        assert call_args.kwargs['headers']['Authorization'] == 'Bearer test-secret-key'
    
    @patch('local_body.agents.vision_agent.httpx.AsyncClient')
    async def test_compressed_image_sent(self, mock_client_class, vision_agent, large_image_bytes):
        """Test 7: Compressed image is sent, not original"""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'analysis': 'test result'}
        
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client
        
        # Call analyze with large image
        await vision_agent.analyze_image_remote(large_image_bytes, "test query")
        
        # Verify compressed image was sent (smaller than original)
        call_args = mock_client.post.call_args
        assert 'files' in call_args.kwargs
        sent_bytes = call_args.kwargs['files']['file'][1]
        
        # Compressed should be smaller than original
        assert len(sent_bytes) < len(large_image_bytes)
        
        # Verify it's a valid JPEG
        img = Image.open(BytesIO(sent_bytes))
        assert img.format == 'JPEG'
        assert img.width <= 1024
        assert img.height <= 1024
