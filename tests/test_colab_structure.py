"""Mock tests for Cloud Brain structure (no GPU required).

These tests verify the code structure and API flow without requiring
actual vLLM or GPU hardware.

CRITICAL: vLLM must be mocked BEFORE importing any colab_brain modules.
"""

import sys
from unittest.mock import MagicMock, patch
from PIL import Image
import io
import pytest

# ========================================
# STEP 1: Mock vLLM BEFORE any imports
# ========================================
mock_vllm = MagicMock()
mock_llm_class = MagicMock()
mock_sampling_params = MagicMock()

# Mock the vLLM module structure
sys.modules['vllm'] = mock_vllm
sys.modules['vllm.engine'] = MagicMock()
sys.modules['vllm.engine.arg_utils'] = MagicMock()

# Set up mock classes
mock_vllm.LLM = mock_llm_class
mock_vllm.SamplingParams = mock_sampling_params

# ========================================
# STEP 2: Now safe to import app modules
# ========================================
from fastapi.testclient import TestClient
from colab_brain.server import app
from colab_brain.inference import VisionModelEngine


class TestColabStructure:
    """Test Cloud Brain structure without GPU"""
    
    def test_imports(self):
        """Test 1: Module imports work"""
        import colab_brain
        # Modules should import without errors
        assert colab_brain is not None
    
    def test_engine_initialization_mock(self):
        """Test 2: VisionModelEngine initializes with mocked vLLM"""
        # Configure mock to return instance
        mock_instance = MagicMock()
        mock_llm_class.return_value = mock_instance
        
        # Create engine
        engine = VisionModelEngine()
        
        # Verify vLLM.LLM was called
        assert mock_llm_class.called
        
        # Verify initialization parameters
        call_kwargs = mock_llm_class.call_args.kwargs
        assert call_kwargs['quantization'] == 'awq'
        assert call_kwargs['gpu_memory_utilization'] == 0.9
        assert call_kwargs['trust_remote_code'] is True
    
    def test_process_request_mock(self):
        """Test 3: process_request generates response"""
        # Setup mocks
        mock_output = MagicMock()
        mock_output.outputs = [MagicMock(text="Test response from vision model")]
        mock_instance = MagicMock()
        mock_instance.generate.return_value = [mock_output]
        mock_llm_class.return_value = mock_instance
        
        # Create engine
        engine = VisionModelEngine()
        
        # Create test image
        test_image = Image.new('RGB', (100, 100), color='red')
        
        # Process request
        result = engine.process_request("What is this?", test_image)
        
        # Verify response
        assert result == "Test response from vision model"
        assert mock_instance.generate.called
    
    def test_server_endpoints_exist(self):
        """Test 4: FastAPI server has required endpoints"""
        # Check routes exist
        routes = [route.path for route in app.routes]
        
        assert "/" in routes
        assert "/health" in routes
        assert "/analyze" in routes
        assert "/shutdown" in routes
    
    def test_health_endpoint(self):
        """Test 5: /health endpoint returns status"""
        # Mock the global engine
        with patch('colab_brain.server.engine') as mock_engine:
            mock_engine.model_name = "test-model"
            
            # Create test client
            with TestClient(app) as client:
                # Call health endpoint
                response = client.get("/health")
                
                # Verify response
                assert response.status_code == 200
                data = response.json()
                assert 'status' in data
                assert 'model' in data
    
    def test_analyze_endpoint_structure(self):
        """Test 6: /analyze endpoint accepts multipart data"""
        # Mock the global engine
        with patch('colab_brain.server.engine') as mock_engine:
            mock_engine.process_request.return_value = "Mocked analysis result"
            
            # Create test image
            test_image = Image.new('RGB', (100, 100), color='blue')
            buffer = io.BytesIO()
            test_image.save(buffer, format='PNG')
            buffer.seek(0)
            
            # Create test client
            with TestClient(app) as client:
                # Send POST request
                response = client.post(
                    "/analyze",
                    files={"file": ("test.png", buffer, "image/png")},
                    data={"query": "What is in this image?"}
                )
                
                # Verify response structure
                assert response.status_code == 200
                data = response.json()
                assert 'response' in data
                assert data['response'] == "Mocked analysis result"


class TestVisionModelEngine:
    """Additional tests for VisionModelEngine"""
    
    def test_image_to_base64(self):
        """Test 7: Image conversion to base64"""
        # Setup mock
        mock_instance = MagicMock()
        mock_llm_class.return_value = mock_instance
        
        # Create engine
        engine = VisionModelEngine()
        
        # Create test image
        test_image = Image.new('RGB', (50, 50), color='green')
        
        # Convert to base64
        b64_result = engine._image_to_base64(test_image)
        
        # Verify it's a string
        assert isinstance(b64_result, str)
        assert len(b64_result) > 0
