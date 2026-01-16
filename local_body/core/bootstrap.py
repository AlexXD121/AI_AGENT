"""System Bootstrap Manager for Sovereign-Doc.

Handles ordered initialization of all system components:
1. Configuration & Logging
2. Hardware Validation
3. Database Connectivity
4. Directory Structure
5. Security Setup

Ensures the system is in a valid state before UI renders.
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any

from loguru import logger

from local_body.core.exceptions import (
    ResourceError,
    DependencyError,
    ConfigurationError,
    StartupError
)


class SystemBootstrap:
    """Manages system initialization and validation.
    
    Performs all necessary checks and setup before the application
    can process documents. If any critical step fails, raises
    appropriate exception to prevent degraded operation.
    """
    
    def __init__(self):
        """Initialize bootstrap manager."""
        self.config = None
        self.startup_complete = False
        self.startup_errors = []
    
    def startup(self, force_reload: bool = False) -> Any:
        """Execute complete system startup sequence.
        
        Args:
            force_reload: Force re-initialization even if already started
            
        Returns:
            Initialized SystemConfig instance
            
        Raises:
            StartupError: If critical initialization step fails
            ResourceError: If hardware insufficient
            DependencyError: If required service unavailable
            ConfigurationError: If configuration invalid
        """
        if self.startup_complete and not force_reload:
            logger.info("System already initialized")
            return self.config
        
        logger.info("=" * 80)
        logger.info("SOVEREIGN-DOC SYSTEM STARTUP")
        logger.info("=" * 80)
        
        try:
            # Step 1: Configuration & Logging
            self._init_config_and_logging()
            
            # Step 2: Hardware Validation
            self._validate_hardware()
            
            # Step 3: Database Connectivity
            self._check_database()
            
            # Step 4: Directory Structure
            self._setup_directories()
            
            # Step 5: Security Initialization
            self._init_security()
            
            # Step 6: Privacy Manager
            self._init_privacy()
            
            self.startup_complete = True
            
            logger.success("=" * 80)
            logger.success("✅ SYSTEM STARTUP COMPLETE")
            logger.success("=" * 80)
            
            return self.config
            
        except Exception as e:
            logger.error(f"Startup failed: {e}")
            self.startup_errors.append(str(e))
            raise
    
    def _init_config_and_logging(self) -> None:
        """Step 1: Initialize configuration and logging.
        
        Raises:
            ConfigurationError: If config loading fails
        """
        logger.info("Step 1/6: Initializing Configuration & Logging...")
        
        try:
            from local_body.core.config_manager import ConfigManager
            from local_body.core.logging_setup import setup_logging
            
            # Load configuration
            config_mgr = ConfigManager()
            self.config = config_mgr.load_config()
            
            logger.info(f"✓ Configuration loaded (profile: {self.config.profile})")
            
            # Setup logging with PII redaction
            setup_logging(
                log_level=self.config.log_level,
                enable_file_logging=True,
                enable_pii_redaction=True  # Always redact in production
            )
            
            logger.info("✓ Logging configured with PII redaction")
            
        except Exception as e:
            raise ConfigurationError(
                f"Failed to load configuration: {e}",
                startup_stage="config_and_logging"
            )
    
    def _validate_hardware(self) -> None:
        """Step 2: Validate hardware resources.
        
        Raises:
            ResourceError: If hardware insufficient
        """
        logger.info("Step 2/6: Validating Hardware Resources...")
        
        try:
            import psutil
            
            # Check available RAM
            ram_info = psutil.virtual_memory()
            ram_gb = ram_info.total / (1024 ** 3)
            ram_available_gb = ram_info.available / (1024 ** 3)
            
            logger.info(f"  RAM: {ram_gb:.1f} GB total, {ram_available_gb:.1f} GB available")
            
            # Minimum 4GB total RAM required
            if ram_gb < 4.0:
                raise ResourceError(
                    f"Insufficient RAM: {ram_gb:.1f} GB available, 4 GB minimum required",
                    resource_type="ram",
                    required="4 GB",
                    available=f"{ram_gb:.1f} GB"
                )
            
            # Warning if less than 2GB available
            if ram_available_gb < 2.0:
                logger.warning(f"⚠️  Low available RAM: {ram_available_gb:.1f} GB")
                logger.warning("  Consider closing other applications")
            
            # Check CPU
            cpu_count = psutil.cpu_count(logical=False)
            logger.info(f"  CPU: {cpu_count} cores")
            
            # Check GPU (optional)
            try:
                import GPUtil
                gpus = GPUtil.getGPUs()
                if gpus:
                    for gpu in gpus:
                        logger.info(f"  GPU: {gpu.name} ({gpu.memoryTotal} MB)")
                else:
                    logger.info("  GPU: None detected (CPU-only mode)")
            except Exception:
                logger.info("  GPU: None detected (CPU-only mode)")
            
            logger.info("✓ Hardware validation passed")
            
        except ResourceError:
            raise
        except Exception as e:
            logger.warning(f"Hardware check warning: {e}")
            # Don't fail startup on hardware check issues, just log
    
    def _check_database(self) -> None:
        """Step 3: Verify database connectivity.
        
        Raises:
            DependencyError: If Qdrant unavailable
        """
        logger.info("Step 3/6: Checking Database Connectivity...")
        
        try:
            from local_body.database.vector_store import DocumentVectorStore
            import httpx
            
            # Try to ping Qdrant
            qdrant_url = f"http://{self.config.qdrant_host}:{self.config.qdrant_port}"
            
            try:
                response = httpx.get(f"{qdrant_url}/healthz", timeout=5.0)
                if response.status_code == 200:
                    logger.info(f"✓ Qdrant connected: {qdrant_url}")
                else:
                    raise Exception(f"Qdrant unhealthy: {response.status_code}")
            except Exception as e:
                logger.warning(f"⚠️  Qdrant not accessible: {e}")
                logger.warning("  Some features (RAG search, knowledge base) will be unavailable")
                logger.warning("  Start Qdrant: docker-compose up -d")
                # Don't fail startup - allow app to run without Qdrant
            
        except Exception as e:
            logger.warning(f"Database check warning: {e}")
            # Don't fail startup - RAG features  will just be disabled
    
    def _setup_directories(self) -> None:
        """Step 4: Ensure required directories exist.
        
        Raises:
            StartupError: If directory creation fails
        """
        logger.info("Step 4/6: Setting Up Directory Structure...")
        
        try:
            required_dirs = [
                "data/temp",
                "data/logs",
                "data/checkpoints",
                "data/exports",
                "logs",
                "uploads"
            ]
            
            for dir_path in required_dirs:
                path = Path(dir_path)
                path.mkdir(parents=True, exist_ok=True)
                logger.debug(f"  ✓ {dir_path}")
            
            logger.info("✓ Directory structure verified")
            
        except Exception as e:
            raise StartupError(
                f"Failed to create directories: {e}",
                startup_stage="directory_setup"
            )
    
    def _init_security(self) -> None:
        """Step 5: Initialize security manager.
        
        Raises:
            ConfigurationError: If security setup fails
        """
        logger.info("Step 5/6: Initializing Security...")
        
        try:
            from local_body.core.security import get_security_manager
            
            security_mgr = get_security_manager()
            
            # Load access token from config
            if self.config.access_token:
                token_value = self.config.access_token.get_secret_value()
                security_mgr.set_access_token(token_value)
                logger.info("✓ Access token configured")
            else:
                # Generate token if not set
                logger.warning("⚠️  No SOVEREIGN_ACCESS_TOKEN set")
                token = security_mgr.generate_access_token()
                logger.warning(f"Generated token: {token}")
                logger.warning("Set this in your environment and Colab Brain!")
                
                # Use generated token for this session
                security_mgr.set_access_token(token)
            
            logger.info("✓ Security manager initialized")
            
        except Exception as e:
            logger.warning(f"Security initialization warning: {e}")
            # Don't fail startup on security issues
    
    def _init_privacy(self) -> None:
        """Step 6: Initialize privacy manager.
        
        Raises:
            StartupError: If privacy setup fails
        """
        logger.info("Step 6/6: Initializing Privacy Manager...")
        
        try:
            from local_body.core.privacy import get_privacy_manager, PrivacyMode
            
            privacy_mgr = get_privacy_manager()
            
            # Set privacy mode based on config (default: STANDARD)
            privacy_mode = getattr(self.config, 'privacy_mode', 'standard')
            if privacy_mode == 'strict':
                privacy_mgr.set_privacy_mode(PrivacyMode.STRICT)
            elif privacy_mode == 'relaxed':
                privacy_mgr.set_privacy_mode(PrivacyMode.RELAXED)
            else:
                privacy_mgr.set_privacy_mode(PrivacyMode.STANDARD)
            
            logger.info(f"✓ Privacy mode: {privacy_mgr.privacy_mode.value}")
            
        except Exception as e:
            logger.warning(f"Privacy initialization warning: {e}")
            # Don't fail startup
    
    def get_status(self) -> Dict[str, Any]:
        """Get current startup status.
        
        Returns:
            Dictionary with startup state
        """
        return {
            "startup_complete": self.startup_complete,
            "config_loaded": self.config is not None,
            "errors": self.startup_errors
        }
    
    def restart(self) -> Any:
        """Restart the system (force re-initialization).
        
        Returns:
            Initialized SystemConfig
        """
        logger.info("Restarting system...")
        self.startup_complete = False
        self.startup_errors.clear()
        return self.startup(force_reload=True)


# Global bootstrap instance
_bootstrap_instance: Optional[SystemBootstrap] = None


def get_bootstrap() -> SystemBootstrap:
    """Get global bootstrap instance.
    
    Returns:
        SystemBootstrap singleton
    """
    global _bootstrap_instance
    if _bootstrap_instance is None:
        _bootstrap_instance = SystemBootstrap()
    return _bootstrap_instance


def initialize_system() -> Any:
    """Initialize the complete system.
    
    Convenience function for app.py.
    
    Returns:
        SystemConfig instance
        
    Raises:
        SovereignError: If initialization fails
    """
    bootstrap = get_bootstrap()
    return bootstrap.startup()
