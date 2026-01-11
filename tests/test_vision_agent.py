"""Tests for VisionAgent with simplified async mocking."""

import pytest
from unittest.mock import Mock, patch
import httpx

from local_body.agents.vision_agent import VisionAgent
from local_body.tunnel.secure_tunnel import SecureTunnel


@pytest.fixture
def mock_config():
    """Create mock configuration."""
    return {
        "max_retries": 3,
        "timeout": 30,
        "enable_cache": True,
        "fallback_model": "llama3.2-vision"
    }


@pytest.fixture
def mock_tunnel():
    """Create mock SecureTunnel."""
    tunnel = Mock(spec=SecureTunnel)
    tunnel.get_status.return_value = {
        'active': True,
        'public_url': 'https://test.ngrok.io'
    }
    return tunnel


@pytest.fixture
def vision_agent(mock_config, mock_tunnel):
    """Create VisionAgent instance."""
    return VisionAgent(mock_config, mock_tunnel)


class TestVisionAgentCache:
    """Test caching functionality"""
    
    @pytest.mark.asyncio
    async def test_cache_key_generation(self, vision_agent):
        """Test 1: Cache keys are consistent"""
        image = b"test_image"
        query = "test_query"
        
        key1 = vision_agent._generate_cache_key(image, query)
        key2 = vision_agent._generate_cache_key(image, query)
        
        assert key1 == key2
        assert len(key1) == 32  # MD5 hash length
    
    @pytest.mark.asyncio
    async def test_different_inputs_different_keys(self, vision_agent):
        """Test 2: Different inputs produce different keys"""
        key1 = vision_agent._generate_cache_key(b"image1", "query1")
        key2 = vision_agent._generate_cache_key(b"image2", "query2")
        
        assert key1 != key2


class TestVisionAgentRemote:
    """Test remote inference functionality"""
    
    @pytest.mark.asyncio
    async def test_tunnel_not_active(self, vision_agent, mock_tunnel):
        """Test 3: Raises error when tunnel inactive"""
        mock_tunnel.get_status.return_value = {'active': False, 'public_url': None}
        
        with pytest.raises(ConnectionError, match="tunnel not active"):
            await vision_agent.analyze_image_remote(b"test", "query")


class TestVisionAgentFallback:
    """Test local fallback functionality"""
    
    def test_agent_initialization(self, vision_agent, mock_tunnel):
        """Test 4: VisionAgent initializes with correct settings"""
        assert vision_agent.tunnel == mock_tunnel
        assert vision_agent.max_retries == 3
        assert vision_agent.timeout == 30
        assert vision_agent.enable_cache is True
        assert vision_agent.fallback_model == "llama3.2-vision"
        assert len(vision_agent._cache) == 0
    
    @pytest.mark.asyncio
    async def test_local_fallback_error_handling(self, vision_agent):
        """Test 5: Local fallback handles errors gracefully"""
        # Simulate error in local analysis
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.side_effect = Exception("Local error")
            
            result = await vision_agent._analyze_local(b"test", "query")
            
            # Should return error message, not raise
            assert "LOCAL_FALLBACK_ERROR" in result


class TestVisionAgentIntegration:
    """Integration tests"""
    
    def test_cache_stats(self, vision_agent):
        """Test 6: Cache statistics tracking"""
        stats = vision_agent.get_cache_stats()
        
        assert 'entries' in stats
        assert 'hits' in stats
        assert 'misses' in stats
        assert stats['entries'] == 0  # Empty cache initially
    
    def test_clear_cache(self, vision_agent):
        """Test 7: Cache clearing"""
        # Add fake cache entry
        vision_agent._cache['test_key'] = 'test_value'
        assert len(vision_agent._cache) == 1
        
        # Clear cache
        vision_agent.clear_cache()
        
        assert len(vision_agent._cache) == 0
