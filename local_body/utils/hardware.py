"""Hardware detection and system resource monitoring.

This module provides utilities for detecting system hardware capabilities
and validating resource availability for document processing.
"""

import platform
from typing import Dict, Optional

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


class HardwareDetector:
    """Detects and validates system hardware capabilities.
    
    Uses psutil for CPU/RAM detection and torch for GPU detection.
    Gracefully handles missing dependencies.
    """
    
    def __init__(self):
        """Initialize hardware detector."""
        if not PSUTIL_AVAILABLE:
            print("Warning: psutil not installed. Hardware detection will use fallback values.")
    
    def get_total_ram_gb(self) -> float:
        """Get total system RAM in gigabytes.
        
        Returns:
            Total RAM in GB, or 8.0 as fallback if psutil unavailable
        """
        if not PSUTIL_AVAILABLE:
            return 8.0  # Fallback default
        
        try:
            total_bytes = psutil.virtual_memory().total
            total_gb = total_bytes / (1024 ** 3)
            return round(total_gb, 2)
        except Exception as e:
            print(f"Warning: Failed to detect RAM: {e}")
            return 8.0
    
    def get_available_ram_gb(self) -> float:
        """Get currently available RAM in gigabytes.
        
        Returns:
            Available RAM in GB
        """
        if not PSUTIL_AVAILABLE:
            return 6.0  # Fallback: assume 75% of 8GB available
        
        try:
            available_bytes = psutil.virtual_memory().available
            available_gb = available_bytes / (1024 ** 3)
            return round(available_gb, 2)
        except Exception as e:
            print(f"Warning: Failed to detect available RAM: {e}")
            return 6.0
    
    def get_cpu_cores(self) -> int:
        """Get number of physical CPU cores.
        
        Returns:
            Number of physical cores, or 4 as fallback
        """
        if not PSUTIL_AVAILABLE:
            return 4  # Fallback default
        
        try:
            # Get physical cores (not logical/hyperthreaded)
            cores = psutil.cpu_count(logical=False)
            return cores if cores else 4
        except Exception as e:
            print(f"Warning: Failed to detect CPU cores: {e}")
            return 4
    
    def has_gpu(self) -> bool:
        """Check if GPU (CUDA or MPS) is available.
        
        Returns:
            True if CUDA or MPS (Mac) GPU is available, False otherwise
        """
        if not TORCH_AVAILABLE:
            return False
        
        try:
            # Check for NVIDIA CUDA
            if torch.cuda.is_available():
                return True
            
            # Check for Apple Metal Performance Shaders (MPS)
            if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                return True
            
            return False
        except Exception as e:
            print(f"Warning: Failed to detect GPU: {e}")
            return False
    
    def get_gpu_info(self) -> Optional[Dict[str, str]]:
        """Get GPU information if available.
        
        Returns:
            Dictionary with GPU type and name, or None if no GPU
        """
        if not self.has_gpu():
            return None
        
        try:
            if TORCH_AVAILABLE and torch.cuda.is_available():
                return {
                    "type": "CUDA",
                    "name": torch.cuda.get_device_name(0),
                    "count": torch.cuda.device_count()
                }
            elif TORCH_AVAILABLE and hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                return {
                    "type": "MPS",
                    "name": "Apple Metal",
                    "count": 1
                }
        except Exception as e:
            print(f"Warning: Failed to get GPU info: {e}")
        
        return None
    
    def validate_resource_availability(self, required_ram_gb: float) -> bool:
        """Validate that system has sufficient RAM available.
        
        Args:
            required_ram_gb: Minimum required RAM in GB
            
        Returns:
            True if system has sufficient RAM, False otherwise
        """
        total_ram = self.get_total_ram_gb()
        return total_ram >= required_ram_gb
    
    def get_system_info(self) -> Dict[str, any]:
        """Get comprehensive system information.
        
        Returns:
            Dictionary with system specs
        """
        info = {
            "platform": platform.system(),
            "platform_version": platform.version(),
            "processor": platform.processor(),
            "total_ram_gb": self.get_total_ram_gb(),
            "available_ram_gb": self.get_available_ram_gb(),
            "cpu_cores": self.get_cpu_cores(),
            "has_gpu": self.has_gpu(),
            "gpu_info": self.get_gpu_info()
        }
        
        return info
    
    def recommend_batch_size(self, available_ram_gb: Optional[float] = None) -> int:
        """Recommend optimal batch size based on available RAM.
        
        Args:
            available_ram_gb: Available RAM in GB (auto-detected if None)
            
        Returns:
            Recommended batch size
        """
        if available_ram_gb is None:
            available_ram_gb = self.get_total_ram_gb()
        
        # Conservative estimates: ~500MB per document in memory
        # Leave 2GB for OS and other processes
        usable_ram = max(available_ram_gb - 2.0, 1.0)
        estimated_batch_size = int(usable_ram / 0.5)
        
        # Clamp between 1 and 20
        return max(1, min(estimated_batch_size, 20))
    
    def check_system_health(self, required_ram_gb: int = 8) -> bool:
        """Check if system meets minimum hardware requirements.
        
        Validates system has sufficient RAM and logs hardware stats on startup.
        This is typically called during application initialization.
        
        Args:
            required_ram_gb: Minimum required RAM in GB (default: 8)
            
        Returns:
            True if system meets requirements, False otherwise
        """
        from loguru import logger
        
        # Get system info
        total_ram = self.get_total_ram_gb()
        available_ram = self.get_available_ram_gb()
        cpu_cores = self.get_cpu_cores()
        has_gpu = self.has_gpu()
        
        # Log hardware stats on startup
        logger.info(f"System Hardware Detection:")
        logger.info(f"  - Total RAM: {total_ram:.1f}GB")
        logger.info(f"  - Available RAM: {available_ram:.1f}GB")
        logger.info(f"  - CPU Cores: {cpu_cores}")
        logger.info(f"  - GPU Available: {has_gpu}")
        
        if has_gpu:
            gpu_info = self.get_gpu_info()
            if gpu_info:
                logger.info(f"  - GPU Type: {gpu_info.get('type', 'Unknown')}")
                logger.info(f"  - GPU Name: {gpu_info.get('name', 'Unknown')}")
        
        # Check if system meets minimum requirements
        if total_ram < required_ram_gb:
            logger.warning(
                f"System has {total_ram:.1f}GB RAM, which is below the "
                f"recommended minimum of {required_ram_gb}GB. "
                f"Performance may be degraded. Consider reducing batch sizes "
                f"or upgrading hardware."
            )
            return False
        
        logger.info(f"✓ System meets minimum hardware requirements ({required_ram_gb}GB RAM)")
        return True
