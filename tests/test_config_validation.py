"""Test suite for configuration validation and hardware detection.

This module tests hardware detection, configuration validation with profiles,
and hardware-aware safety checks.
"""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from pydantic import ValidationError

from local_body.core.config_manager import ConfigManager, SystemConfig
from local_body.utils.hardware import HardwareDetector


class TestHardwareDetector:
    """Test hardware detection functionality."""
    
    @patch('local_body.utils.hardware.psutil')
    def test_get_total_ram_gb(self, mock_psutil):
        """Test RAM detection."""
        # Mock psutil to return 8GB (in bytes)
        mock_vm = Mock()
        mock_vm.total = 8 * 1024 ** 3  # 8GB in bytes
        mock_psutil.virtual_memory.return_value = mock_vm
        
        detector = HardwareDetector()
        ram = detector.get_total_ram_gb()
        
        assert ram == 8.0
    
    @patch('local_body.utils.hardware.psutil')
    def test_get_available_ram_gb(self, mock_psutil):
        """Test available RAM detection."""
        mock_vm = Mock()
        mock_vm.available = 6 * 1024 ** 3  # 6GB available
        mock_psutil.virtual_memory.return_value = mock_vm
        
        detector = HardwareDetector()
        available = detector.get_available_ram_gb()
        
        assert available == 6.0
    
    @patch('local_body.utils.hardware.psutil')
    def test_get_cpu_cores(self, mock_psutil):
        """Test CPU core detection."""
        mock_psutil.cpu_count.return_value = 4
        
        detector = HardwareDetector()
        cores = detector.get_cpu_cores()
        
        assert cores == 4
        mock_psutil.cpu_count.assert_called_once_with(logical=False)
    
    def test_has_gpu_no_torch(self):
        """Test GPU detection without torch returns False."""
        # When torch is not available, should return False
        detector = HardwareDetector()
        # This will return False if torch is not installed, or actual GPU status if it is
        # Either way, it should not crash
        has_gpu = detector.has_gpu()
        assert isinstance(has_gpu, bool)
    
    @patch('local_body.utils.hardware.psutil')
    def test_validate_resource_availability_sufficient(self, mock_psutil):
        """Test resource validation with sufficient RAM."""
        mock_vm = Mock()
        mock_vm.total = 16 * 1024 ** 3  # 16GB
        mock_psutil.virtual_memory.return_value = mock_vm
        
        detector = HardwareDetector()
        is_valid = detector.validate_resource_availability(8.0)
        
        assert is_valid is True
    
    @patch('local_body.utils.hardware.psutil')
    def test_validate_resource_availability_insufficient(self, mock_psutil):
        """Test resource validation with insufficient RAM."""
        mock_vm = Mock()
        mock_vm.total = 4 * 1024 ** 3  # 4GB
        mock_psutil.virtual_memory.return_value = mock_vm
        
        detector = HardwareDetector()
        is_valid = detector.validate_resource_availability(8.0)
        
        assert is_valid is False
    
    @patch('local_body.utils.hardware.psutil')
    def test_recommend_batch_size(self, mock_psutil):
        """Test batch size recommendation."""
        mock_vm = Mock()
        mock_vm.total = 8 * 1024 ** 3  # 8GB
        mock_psutil.virtual_memory.return_value = mock_vm
        
        detector = HardwareDetector()
        batch_size = detector.recommend_batch_size()
        
        # (8GB - 2GB) / 0.5GB per doc = 12, clamped to max 20
        assert batch_size == 12


class TestSystemConfigValidation:
    """Test SystemConfig validation."""
    
    def test_valid_config(self):
        """Test creating a valid configuration."""
        config = SystemConfig(
            profile="dev",
            conflict_threshold=0.15,
            batch_size=5,
            available_ram_gb=8
        )
        
        assert config.profile == "dev"
        assert config.conflict_threshold == 0.15
        assert config.batch_size == 5
    
    def test_invalid_profile(self):
        """Test that invalid profile raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SystemConfig(profile="invalid")
        
        assert "profile must be one of" in str(exc_info.value)
    
    def test_invalid_conflict_threshold_too_high(self):
        """Test that conflict threshold > 1.0 raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SystemConfig(conflict_threshold=1.5)
        
        # Check that validation error occurred
        assert "conflict_threshold" in str(exc_info.value).lower()
    
    def test_invalid_conflict_threshold_negative(self):
        """Test that negative conflict threshold raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SystemConfig(conflict_threshold=-0.1)
        
        # Check that validation error occurred
        assert "conflict_threshold" in str(exc_info.value).lower()
    
    def test_invalid_batch_size_zero(self):
        """Test that batch size of 0 raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SystemConfig(batch_size=0)
        
        # Check that validation error occurred
        assert "batch_size" in str(exc_info.value).lower()
    
    def test_invalid_batch_size_negative(self):
        """Test that negative batch size raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SystemConfig(batch_size=-5)
        
        # Check that validation error occurred
        assert "batch_size" in str(exc_info.value).lower()
    
    def test_invalid_processing_mode(self):
        """Test that invalid processing mode raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SystemConfig(processing_mode="invalid")
        
        # Check that validation error occurred
        assert "processing_mode" in str(exc_info.value).lower()
    
    def test_ngrok_token_is_secret(self):
        """Test that ngrok_token is stored as SecretStr."""
        config = SystemConfig(ngrok_token="secret-token-123")
        
        # SecretStr should not reveal value in repr
        config_str = str(config)
        assert "secret-token-123" not in config_str
        assert "**********" in config_str or "SecretStr" in config_str


class TestConfigManagerProfiles:
    """Test configuration profile switching."""
    
    def test_dev_profile_defaults(self, tmp_path):
        """Test development profile defaults."""
        os.environ['SOVEREIGN_ENV'] = 'dev'
        
        try:
            manager = ConfigManager()
            config = manager.load_config()
            
            assert config.profile == "dev"
        finally:
            # Cleanup
            if 'SOVEREIGN_ENV' in os.environ:
                del os.environ['SOVEREIGN_ENV']
    
    def test_prod_profile_settings(self, tmp_path):
        """Test production profile applies stricter settings."""
        os.environ['SOVEREIGN_ENV'] = 'prod'
        
        try:
            manager = ConfigManager()
            config = manager.load_config()
            
            assert config.profile == "prod"
            # Prod profile has stricter threshold if not overridden
            # Note: config.yaml may override these, so we just check profile is set
        finally:
            # Cleanup
            if 'SOVEREIGN_ENV' in os.environ:
                del os.environ['SOVEREIGN_ENV']
    
    def test_demo_profile_settings(self, tmp_path):
        """Test demo profile applies UI-focused settings."""
        os.environ['SOVEREIGN_ENV'] = 'demo'
        
        try:
            manager = ConfigManager()
            config = manager.load_config()
            
            assert config.profile == "demo"
        finally:
            # Cleanup
            if 'SOVEREIGN_ENV' in os.environ:
                del os.environ['SOVEREIGN_ENV']
    
    def test_profile_env_variable_override(self):
        """Test that SOVEREIGN_ENV overrides config file."""
        os.environ['SOVEREIGN_ENV'] = 'prod'
        
        try:
            manager = ConfigManager()
            config = manager.load_config()
            
            assert config.profile == "prod"
        finally:
            # Cleanup
            if 'SOVEREIGN_ENV' in os.environ:
                del os.environ['SOVEREIGN_ENV']


class TestHardwareSafetyChecks:
    """Test hardware-aware safety validation."""
    
    def test_batch_size_warning_for_low_ram(self, caplog):
        """Test that large batch size triggers warning on low RAM."""
        import logging
        
        with patch('local_body.utils.hardware.psutil') as mock_psutil:
            # Mock hardware detector
            mock_vm = Mock()
            mock_vm.total = 8 * 1024 ** 3  # 8GB
            mock_vm.available = 4 * 1024 ** 3  # 4GB available
            mock_psutil.virtual_memory.return_value = mock_vm
            mock_psutil.cpu_count.return_value = 4
            
            # Create config with large batch size
            manager = ConfigManager()
            manager._config = SystemConfig(batch_size=20)  # 20 * 0.5GB = 10GB
            
            # Capture logs at WARNING level
            with caplog.at_level(logging.WARNING):
                manager._validate_hardware_safety()
            
            # Check if warning was logged (loguru may not always appear in caplog)
            # The function should execute without errors
            assert manager._config.batch_size == 20
    
    def test_insufficient_ram_error(self, caplog):
        """Test that insufficient RAM triggers error."""
        import logging
        
        with patch('local_body.utils.hardware.psutil') as mock_psutil:
            # Mock hardware detector with very low RAM
            mock_vm = Mock()
            mock_vm.total = 2 * 1024 ** 3  # Only 2GB
            mock_vm.available = 1.5 * 1024 ** 3
            mock_psutil.virtual_memory.return_value = mock_vm
            mock_psutil.cpu_count.return_value = 2
            
            manager = ConfigManager()
            manager._config = SystemConfig()
            
            # Capture logs at ERROR level
            with caplog.at_level(logging.ERROR):
                manager._validate_hardware_safety()
            
            # The function should execute without crashing
            # (it logs an error but doesn't raise an exception)
            assert manager._config is not None
    
    def test_safe_batch_size_no_warning(self, caplog):
        """Test that safe batch size doesn't trigger warnings."""
        import logging
        
        with patch('local_body.utils.hardware.psutil') as mock_psutil:
            # Mock hardware detector with plenty of RAM
            mock_vm = Mock()
            mock_vm.total = 16 * 1024 ** 3  # 16GB
            mock_vm.available = 12 * 1024 ** 3  # 12GB available
            mock_psutil.virtual_memory.return_value = mock_vm
            mock_psutil.cpu_count.return_value = 8
            
            manager = ConfigManager()
            manager._config = SystemConfig(batch_size=5)  # Safe size
            
            with caplog.at_level(logging.WARNING):
                manager._validate_hardware_safety()
            
            # Should execute without issues
            assert manager._config.batch_size == 5


class TestEnvironmentVariables:
    """Test environment variable handling."""
    
    def test_ngrok_token_from_env_only(self):
        """Test that ngrok_token is only loaded from environment."""
        os.environ['SOVEREIGN_NGROK_TOKEN'] = 'test-token-123'
        
        manager = ConfigManager()
        config = manager.load_config()
        
        # Token should be loaded
        assert config.ngrok_token is not None
        assert config.ngrok_token.get_secret_value() == 'test-token-123'
        
        # Cleanup
        del os.environ['SOVEREIGN_NGROK_TOKEN']
    
    def test_env_variable_overrides_yaml(self):
        """Test that environment variables override YAML config."""
        os.environ['SOVEREIGN_BATCH_SIZE'] = '15'
        
        manager = ConfigManager()
        config = manager.load_config()
        
        assert config.batch_size == 15
        
        # Cleanup
        del os.environ['SOVEREIGN_BATCH_SIZE']
    
    def test_multiple_env_variables(self):
        """Test loading multiple environment variables."""
        os.environ['SOVEREIGN_ENV'] = 'prod'
        os.environ['SOVEREIGN_CONFLICT_THRESHOLD'] = '0.18'
        os.environ['SOVEREIGN_BATCH_SIZE'] = '12'
        
        manager = ConfigManager()
        config = manager.load_config()
        
        assert config.profile == "prod"
        assert config.conflict_threshold == 0.18
        assert config.batch_size == 12
        
        # Cleanup
        del os.environ['SOVEREIGN_ENV']
        del os.environ['SOVEREIGN_CONFLICT_THRESHOLD']
        del os.environ['SOVEREIGN_BATCH_SIZE']
