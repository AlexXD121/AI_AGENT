"""Unit tests for ModelManager.

These tests use mocking to avoid requiring actual Ollama installation.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from local_body.utils.model_manager import ModelManager


@pytest.fixture
def model_manager():
    """Create a ModelManager instance for testing."""
    return ModelManager(base_url="http://localhost:11434")


class TestModelManager:
    """Test suite for ModelManager class."""
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, model_manager):
        """Test 1: Health check returns True when Ollama is running."""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": []}
        
        with patch.object(model_manager.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            
            result = await model_manager.check_health()
            
            assert result is True
            mock_get.assert_called_once_with("http://localhost:11434/api/tags")
    
    @pytest.mark.asyncio
    async def test_health_check_connection_error(self, model_manager):
        """Test: Health check returns False when Ollama is not running."""
        with patch.object(model_manager.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.ConnectError("Connection refused")
            
            result = await model_manager.check_health()
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_ensure_models_exist_auto_pull(self, model_manager):
        """Test 2: Auto-pull calls pull endpoint for missing models."""
        # Mock /api/tags returning empty list (no models installed)
        mock_tags_response = MagicMock()
        mock_tags_response.status_code = 200
        mock_tags_response.json.return_value = {"models": []}
        
        # Mock /api/pull streaming response
        mock_pull_response = MagicMock()
        mock_pull_response.status_code = 200
        
        # Create async iterator for streaming response
        async def mock_aiter_lines():
            yield '{"status": "pulling", "total": 1000, "completed": 500}'
            yield '{"status": "success"}'
        
        mock_pull_response.aiter_lines = mock_aiter_lines
        
        # Create async context manager for stream
        mock_stream = AsyncMock()
        mock_stream.__aenter__.return_value = mock_pull_response
        mock_stream.__aexit__.return_value = None
        
        with patch.object(model_manager.client, 'get', new_callable=AsyncMock) as mock_get, \
             patch.object(model_manager.client, 'stream') as mock_stream_method:
            
            mock_get.return_value = mock_tags_response
            mock_stream_method.return_value = mock_stream
            
            result = await model_manager.ensure_models_exist()
            
            # Should return True (all models pulled successfully)
            assert result is True
            
            # Should have called stream for both required models
            assert mock_stream_method.call_count == 2
            
            # Verify the calls were for the correct models
            calls = mock_stream_method.call_args_list
            pulled_models = [call.kwargs['json']['name'] for call in calls]
            assert "llama3.2" in pulled_models
            assert "llama3.2-vision" in pulled_models
    
    @pytest.mark.asyncio
    async def test_ensure_models_exist_already_installed(self, model_manager):
        """Test: No pull needed when models are already installed."""
        # Mock /api/tags returning both required models
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {"name": "llama3.2"},
                {"name": "llama3.2-vision"}
            ]
        }
        
        with patch.object(model_manager.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            
            result = await model_manager.ensure_models_exist()
            
            # Should return True (all models available)
            assert result is True
            
            # Should only have called get (no pull needed)
            assert mock_get.call_count == 1
    
    @pytest.mark.asyncio
    async def test_unload_models(self, model_manager):
        """Test 3: Unload models sends correct JSON payload with keep_alive=0."""
        # Mock successful unload response
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        with patch.object(model_manager.client, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            
            result = await model_manager.unload_models()
            
            # Should return True (all models unloaded)
            assert result is True
            
            # Should have called post for both required models
            assert mock_post.call_count == 2
            
            # Verify the payload contains keep_alive=0
            for call in mock_post.call_args_list:
                payload = call.kwargs['json']
                assert payload['keep_alive'] == 0
                assert payload['model'] in ["llama3.2", "llama3.2-vision"]
                assert 'prompt' in payload
    
    @pytest.mark.asyncio
    async def test_get_model_status(self, model_manager):
        """Test: Get model status returns loaded models information."""
        # Mock /api/ps response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {"name": "llama3.2", "size": 2000000000},
                {"name": "llama3.2-vision", "size": 5000000000}
            ]
        }
        
        with patch.object(model_manager.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            
            status = await model_manager.get_model_status()
            
            assert status['model_count'] == 2
            assert "llama3.2" in status['loaded_models']
            assert "llama3.2-vision" in status['loaded_models']
            assert len(status['details']) == 2
    
    @pytest.mark.asyncio
    async def test_close(self, model_manager):
        """Test: Close method closes the HTTP client."""
        with patch.object(model_manager.client, 'aclose', new_callable=AsyncMock) as mock_close:
            await model_manager.close()
            mock_close.assert_called_once()
