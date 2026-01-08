"""Configuration management system for Sovereign-Doc.

This module handles loading, validation, and management of system configuration
from YAML files and environment variables.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from pydantic import BaseModel, Field, field_validator


class SystemConfig(BaseModel):
    """System configuration model matching the design specification.
    
    This configuration can be loaded from config.yaml and overridden
    by environment variables prefixed with SOVEREIGN_.
    """
    
    # Processing settings
    processing_mode: str = Field(
        default="hybrid",
        description="Processing mode: local, hybrid, or remote"
    )
    conflict_threshold: float = Field(
        default=0.15,
        ge=0.05,
        le=0.30,
        description="Threshold for conflict detection (5-30%)"
    )
    batch_size: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Number of documents to process in a batch"
    )
    max_memory_usage: float = Field(
        default=0.85,
        ge=0.5,
        le=0.95,
        description="Maximum memory usage threshold (50-95%)"
    )
    
    # Hardware-specific settings
    cpu_cores: int = Field(
        default=4,
        ge=1,
        description="Number of CPU cores to use"
    )
    available_ram_gb: int = Field(
        default=8,
        ge=4,
        description="Available RAM in GB"
    )
    has_gpu: bool = Field(
        default=False,
        description="Whether GPU is available"
    )
    
    # Model settings
    ocr_confidence_threshold: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Minimum OCR confidence threshold"
    )
    vision_confidence_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum vision model confidence threshold"
    )
    
    # Colab settings
    ngrok_url: Optional[str] = Field(
        default=None,
        description="ngrok tunnel URL for Colab connection"
    )
    tunnel_timeout: int = Field(
        default=30,
        ge=5,
        le=120,
        description="Tunnel connection timeout in seconds"
    )
    
    # Qdrant settings
    vector_collection: str = Field(
        default="documents",
        description="Qdrant collection name for document vectors"
    )
    embedding_model: str = Field(
        default="BGE-small-en-v1.5",
        description="Embedding model for text vectorization"
    )
    qdrant_host: str = Field(
        default="localhost",
        description="Qdrant server host"
    )
    qdrant_port: int = Field(
        default=6333,
        ge=1,
        le=65535,
        description="Qdrant server port"
    )
    
    # Logging settings
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR)"
    )
    log_file_path: str = Field(
        default="data/logs/sovereign.log",
        description="Path to log file"
    )
    log_rotation: str = Field(
        default="500 MB",
        description="Log file rotation size"
    )
    
    @field_validator('processing_mode')
    @classmethod
    def validate_processing_mode(cls, v: str) -> str:
        """Validate processing mode is one of the allowed values."""
        allowed = ["local", "hybrid", "remote"]
        if v not in allowed:
            raise ValueError(f"processing_mode must be one of {allowed}, got '{v}'")
        return v
    
    @field_validator('log_level')
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is one of the allowed values."""
        allowed = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in allowed:
            raise ValueError(f"log_level must be one of {allowed}, got '{v}'")
        return v_upper
    
    class Config:
        validate_assignment = True


class ConfigManager:
    """Manages system configuration with support for YAML files and environment variables.
    
    Configuration priority (highest to lowest):
    1. Environment variables (SOVEREIGN_*)
    2. config.yaml file
    3. Default values from SystemConfig
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize the configuration manager.
        
        Args:
            config_path: Path to config.yaml file. If None, looks for config.yaml
                        in the current directory or uses defaults.
        """
        self.config_path = config_path or "config.yaml"
        self._config: Optional[SystemConfig] = None
    
    def load_config(self) -> SystemConfig:
        """Load configuration from file and environment variables.
        
        Returns:
            Loaded and validated SystemConfig instance
        """
        # Start with default values
        config_dict: Dict[str, Any] = {}
        
        # Load from YAML file if it exists
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                yaml_config = yaml.safe_load(f)
                if yaml_config:
                    config_dict.update(yaml_config)
        
        # Override with environment variables
        env_overrides = self._load_from_env()
        config_dict.update(env_overrides)
        
        # Create and validate config
        self._config = SystemConfig(**config_dict)
        return self._config
    
    def _load_from_env(self) -> Dict[str, Any]:
        """Load configuration overrides from environment variables.
        
        Environment variables should be prefixed with SOVEREIGN_ and use
        uppercase with underscores (e.g., SOVEREIGN_NGROK_URL).
        
        Returns:
            Dictionary of configuration overrides from environment
        """
        env_config = {}
        prefix = "SOVEREIGN_"
        
        # Map of environment variable names to config keys
        env_mappings = {
            f"{prefix}PROCESSING_MODE": "processing_mode",
            f"{prefix}CONFLICT_THRESHOLD": ("conflict_threshold", float),
            f"{prefix}BATCH_SIZE": ("batch_size", int),
            f"{prefix}MAX_MEMORY_USAGE": ("max_memory_usage", float),
            f"{prefix}CPU_CORES": ("cpu_cores", int),
            f"{prefix}AVAILABLE_RAM_GB": ("available_ram_gb", int),
            f"{prefix}HAS_GPU": ("has_gpu", lambda x: x.lower() in ['true', '1', 'yes']),
            f"{prefix}OCR_CONFIDENCE_THRESHOLD": ("ocr_confidence_threshold", float),
            f"{prefix}VISION_CONFIDENCE_THRESHOLD": ("vision_confidence_threshold", float),
            f"{prefix}NGROK_URL": "ngrok_url",
            f"{prefix}TUNNEL_TIMEOUT": ("tunnel_timeout", int),
            f"{prefix}VECTOR_COLLECTION": "vector_collection",
            f"{prefix}EMBEDDING_MODEL": "embedding_model",
            f"{prefix}QDRANT_HOST": "qdrant_host",
            f"{prefix}QDRANT_PORT": ("qdrant_port", int),
            f"{prefix}LOG_LEVEL": "log_level",
            f"{prefix}LOG_FILE_PATH": "log_file_path",
            f"{prefix}LOG_ROTATION": "log_rotation",
        }
        
        for env_var, mapping in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                if isinstance(mapping, tuple):
                    config_key, converter = mapping
                    try:
                        env_config[config_key] = converter(value)
                    except (ValueError, TypeError) as e:
                        print(f"Warning: Failed to convert {env_var}={value}: {e}")
                else:
                    env_config[mapping] = value
        
        return env_config
    
    def get_config(self) -> SystemConfig:
        """Get the current configuration.
        
        Returns:
            Current SystemConfig instance
            
        Raises:
            RuntimeError: If configuration hasn't been loaded yet
        """
        if self._config is None:
            raise RuntimeError("Configuration not loaded. Call load_config() first.")
        return self._config
    
    def save_config(self, path: Optional[str] = None) -> None:
        """Save current configuration to YAML file.
        
        Args:
            path: Path to save config file. If None, uses self.config_path
        """
        if self._config is None:
            raise RuntimeError("No configuration to save. Load or create config first.")
        
        save_path = path or self.config_path
        config_dict = self._config.model_dump(exclude_none=True)
        
        # Ensure directory exists
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(save_path, 'w') as f:
            yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)
    
    def update_config(self, updates: Dict[str, Any]) -> SystemConfig:
        """Update configuration with new values.
        
        Args:
            updates: Dictionary of configuration updates
            
        Returns:
            Updated SystemConfig instance
        """
        if self._config is None:
            self._config = SystemConfig(**updates)
        else:
            current_dict = self._config.model_dump()
            current_dict.update(updates)
            self._config = SystemConfig(**current_dict)
        
        return self._config
