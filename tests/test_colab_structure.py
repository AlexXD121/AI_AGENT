"""Optimized Cloud Brain structure tests with proper vLLM mocking.

These tests verify API structure without requiring GPU or vLLM installation.

CRITICAL: vLLM must be mocked BEFORE importing colab_brain modules.
"""

import sys
from unittest.mock import MagicMock, patch
from PIL import Image
import io
import pytest

# ========================================
# STEP 1: Mock vLLM GLOBALLY BEFORE IMPORTS
# ========================================
# This prevents ImportError when colab_brain.inference tries to import vllm
mock_vllm = MagicMock()
sys.modules['vllm'] = mock_vllm
sys.modules['vllm.engine'] = MagicMock()
sys.modules['vllm.engine.arg_utils'] = MagicMock()

# Configure mock LLM class
mock_llm_class = MagicMock()
mock_vllm.LLM = mock_llm_class
mock_vllm.SamplingParams = MagicMock()

# ========================================
# STEP 2: Now safe to import app modules
# ========================================
from fastapi.testclient import TestClient
from colab_brain.server import app

# Create test client
client = TestClient(app)


class TestCloudBrainAPI:
    """Test Cloud Brain FastAPI endpoints"""
    
    def test_health_endpoint(self):
        """Test 1: /health returns correct structure"""
        # Mock the global engine
        with patch('colab_brain.server.engine') as mock_engine:
            mock_engine.model_name = "Qwen/Qwen2.5-VL-7B-Instruct-AWQ"
            
            response = client.get("/health")
            
            assert response.status_code == 200
            data = response.json()
            assert 'status' in data
            assert 'model' in data
            assert data['model'] == "Qwen/Qwen2.5-VL-7B-Instruct-AWQ"
    
    def test_root_endpoint(self):
        """Test 2: / returns service info"""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert 'service' in data
        assert 'Sovereign-Doc' in data['service']
    
    def test_analyze_endpoint_structure(self):
        """Test 3: /analyze accepts multipart data"""
        # Mock the global engine
        with patch('colab_brain.server.engine') as mock_engine:
            mock_engine.process_request.return_value = "Mocked vision analysis result"
            
            # Create fake image file
            test_image = Image.new('RGB', (100, 100), color='red')
            buffer = io.BytesIO()
            test_image.save(buffer, format='JPEG')
            buffer.seek(0)
            
            # Send POST request
            files = {'file': ('test.jpg', buffer, 'image/jpeg')}
            data = {'query': 'What is in this image?'}
            
            response = client.post("/analyze", files=files, data=data)
            
            assert response.status_code == 200
            result = response.json()
            assert 'response' in result
            assert result['response'] == "Mocked vision analysis result"
    
    def test_analyze_requires_file(self):
        """Test 4: /analyze validates required fields"""
        # Missing file
        data = {'query': 'test'}
        response = client.post("/analyze", data=data)
        
        # Should fail validation
        assert response.status_code == 422
    
    def test_analyze_requires_query(self):
        """Test 5: /analyze validates query field"""
        # Missing query
        test_image = Image.new('RGB', (50, 50))
        buffer = io.BytesIO()
        test_image.save(buffer, format='PNG')
        buffer.seek(0)
        
        files = {'file': ('test.png', buffer, 'image/png')}
        response = client.post("/analyze", files=files)
        
        # Should fail validation
        assert response.status_code == 422


class TestVisionModelEngine:
    """Test VisionModelEngine with mocked vLLM"""
    
    def test_engine_initialization(self):
        """Test 6: Engine initializes with mocked vLLM"""
        from colab_brain.inference import VisionModelEngine
        
        # Configure mock
        mock_instance = MagicMock()
        mock_llm_class.return_value = mock_instance
        
        # Create engine
        engine = VisionModelEngine()
        
        # Verify LLM was called
        assert mock_llm_class.called
        
        # Verify correct parameters
        call_kwargs = mock_llm_class.call_args.kwargs
        assert call_kwargs['quantization'] == 'awq'
        assert call_kwargs['gpu_memory_utilization'] == 0.9
        assert call_kwargs['trust_remote_code'] is True
    
    def test_process_request(self):
        """Test 7: process_request generates response"""
        from colab_brain.inference import VisionModelEngine
        
        # Setup mock output
        mock_output = MagicMock()
        mock_output.outputs = [MagicMock(text="Generated text response")]
        mock_instance = MagicMock()
        mock_instance.generate.return_value = [mock_output]
        mock_llm_class.return_value = mock_instance
        
        # Create engine
        engine = VisionModelEngine()
        
        # Create test image
        test_image = Image.new('RGB', (100, 100), color='blue')
        
        # Process request
        result = engine.process_request("Test query", test_image)
        
        # Verify result
        assert result == "Generated text response"
        assert mock_instance.generate.called
