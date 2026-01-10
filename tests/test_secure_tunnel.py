"""Unit tests for SecureTunnel class.

These tests mock pyngrok to avoid actual ngrok connections during testing.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
import time

from local_body.tunnel.secure_tunnel import SecureTunnel
from local_body.core.config_manager import SystemConfig


@pytest.fixture
def mock_config():
    """Create mock configuration for SecureTunnel."""
    config = MagicMock(spec=SystemConfig)
    config.ngrok_token = None  # Will use environment variable
    return config


@pytest.fixture
def mock_ngrok():
    """Mock pyngrok to prevent actual connections."""
    with patch('local_body.tunnel.secure_tunnel.ngrok') as mock:
        # Create mock tunnel object
        mock_tunnel = MagicMock()
        mock_tunnel.public_url = "https://abc123.ngrok.io"
        mock.connect.return_value = mock_tunnel
        mock.get_tunnels.return_value = [mock_tunnel]
        
        yield mock


class TestSecureTunnel:
    """Test suite for SecureTunnel class."""
    
    def test_initialization(self, mock_config, mock_ngrok):
        """Test 1: SecureTunnel initializes correctly."""
        tunnel = SecureTunnel(mock_config)
        
        assert tunnel.tunnel is None
        assert tunnel.public_url is None
        assert tunnel.port == 8000
    
    def test_start_returns_url(self, mock_config, mock_ngrok):
        """Test 2: start() returns public HTTPS URL."""
        tunnel = SecureTunnel(mock_config)
        url = tunnel.start()
        
        # Verify URL returned
        assert url == "https://abc123.ngrok.io"
        assert tunnel.public_url == "https://abc123.ngrok.io"
        
        # Verify connect was called
        mock_ngrok.connect.assert_called_once()
    
    def test_enforces_https(self, mock_config, mock_ngrok):
        """Test 3: start() enforces HTTPS via bind_tls=True."""
        tunnel = SecureTunnel(mock_config)
        tunnel.start()
        
        # Verify bind_tls=True was passed
        args, kwargs = mock_ngrok.connect.call_args
        assert kwargs.get('bind_tls') is True
    
    def test_start_with_custom_port(self, mock_config, mock_ngrok):
        """Test 4: start() accepts custom port."""
        tunnel = SecureTunnel(mock_config)
        tunnel.start(port=5000)
        
        # Verify correct port used
        args, kwargs = mock_ngrok.connect.call_args
        assert args[0] == 5000
        assert tunnel.port == 5000
    
    def test_stop_disconnects_tunnel(self, mock_config, mock_ngrok):
        """Test 5: stop() disconnects tunnel and kills process."""
        tunnel = SecureTunnel(mock_config)
        tunnel.start()
        tunnel.stop()
        
        # Verify disconnect called with URL
        mock_ngrok.disconnect.assert_called_once_with("https://abc123.ngrok.io")
        
        # Verify kill called to cleanup
        mock_ngrok.kill.assert_called_once()
        
        # Verify state cleared
        assert tunnel.tunnel is None
        assert tunnel.public_url is None
    
    def test_health_monitor_detects_failure(self, mock_config, mock_ngrok):
        """Test 6: monitor_health() detects when tunnel is down."""
        tunnel = SecureTunnel(mock_config)
        tunnel.start()
        
        # Simulate tunnel disconnection
        mock_ngrok.get_tunnels.return_value = []
        
        # Mock restart to avoid recursion
        with patch.object(tunnel, 'restart') as mock_restart:
            result = tunnel.monitor_health()
            
            # Should detect failure and attempt restart
            assert result is False
            mock_restart.assert_called_once()
    
    def test_health_monitor_success(self, mock_config, mock_ngrok):
        """Test 7: monitor_health() returns True when tunnel is healthy."""
        tunnel = SecureTunnel(mock_config)
        tunnel.start()
        
        # Tunnel is active (from fixture)
        result = tunnel.monitor_health()
        
        assert result is True
    
    def test_restart_reconnects_tunnel(self, mock_config, mock_ngrok):
        """Test 8: restart() stops and starts tunnel again."""
        tunnel = SecureTunnel(mock_config)
        tunnel.start()
        
        # Mock time.sleep to speed up test
        with patch('local_body.tunnel.secure_tunnel.time.sleep'):
            tunnel.restart()
        
        # Verify disconnect called
        assert mock_ngrok.disconnect.call_count >= 1
        
        # Verify reconnect attempted
        assert mock_ngrok.connect.call_count >= 2
    
    def test_validate_request_with_signature(self, mock_config, mock_ngrok):
        """Test 9: validate_request_signature() accepts valid header."""
        tunnel = SecureTunnel(mock_config)
        
        headers = {'X-Sovereign-Signature': 'test_signature_value'}
        result = tunnel.validate_request_signature(headers)
        
        assert result is True
    
    def test_validate_request_without_signature(self, mock_config, mock_ngrok):
        """Test 10: validate_request_signature() rejects missing header."""
        tunnel = SecureTunnel(mock_config)
        
        headers = {}
        result = tunnel.validate_request_signature(headers)
        
        assert result is False
    
    def test_get_status(self, mock_config, mock_ngrok):
        """Test 11: get_status() returns current tunnel information."""
        tunnel = SecureTunnel(mock_config)
        
        # Before starting
        status = tunnel.get_status()
        assert status['active'] is False
        assert status['public_url'] is None
        
        # After starting
        tunnel.start()
        status = tunnel.get_status()
        assert status['active'] is True
        assert status['public_url'] == "https://abc123.ngrok.io"
        assert status['port'] == 8000
    
    def test_cleanup_on_exit(self, mock_config, mock_ngrok):
        """Test 12: Cleanup handler stops tunnel on exit."""
        tunnel = SecureTunnel(mock_config)
        tunnel.start()
        
        # Call cleanup manually (simulating atexit)
        tunnel._cleanup()
        
        # Verify tunnel stopped
        mock_ngrok.disconnect.assert_called()
        mock_ngrok.kill.assert_called()
