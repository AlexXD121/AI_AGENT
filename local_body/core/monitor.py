"""System Resource Monitor - Real-time tracking and management.

This module provides comprehensive system resource monitoring with:
- Real-time CPU, RAM, and GPU metrics
- Thermal monitoring and throttling
- Automatic memory cleanup and model unloading
- Cool-down mode for thermal protection
- Streaming mode decision logic for large documents

Requirements: psutil (CPU/RAM), GPUtil or pynvml (GPU - optional)
"""

import gc
import platform
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Optional, Tuple
from loguru import logger

# Core dependencies
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logger.warning("psutil not available - system monitoring will be limited")

# GPU monitoring (optional)
try:
    import GPUtil
    GPUTIL_AVAILABLE = True
except ImportError:
    GPUTIL_AVAILABLE = False
    # Try pynvml as fallback
    try:
        import pynvml
        PYNVML_AVAILABLE = True
        pynvml.nvmlInit()
    except (ImportError, Exception):
        PYNVML_AVAILABLE = False
        logger.info("No GPU monitoring library available (GPUtil/pynvml) - GPU metrics disabled")

# PyTorch/Paddle for cache clearing
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    import paddle
    PADDLE_AVAILABLE = True
except ImportError:
    PADDLE_AVAILABLE = False


class HealthStatus(Enum):
    """System health status levels."""
    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class SystemMetrics:
    """Container for system resource metrics."""
    timestamp: datetime
    
    # CPU
    cpu_percent: float
    cpu_count: int
    
    # RAM
    ram_total_gb: float
    ram_used_gb: float
    ram_available_gb: float
    ram_percent: float
    
    # GPU (optional)
    gpu_available: bool
    gpu_vram_used_mb: Optional[float] = None
    gpu_vram_total_mb: Optional[float] = None
    gpu_temperature_c: Optional[float] = None
    gpu_utilization_percent: Optional[float] = None
    
    # Temperature
    cpu_temperature_c: Optional[float] = None
    
    # Health
    health_status: HealthStatus = HealthStatus.OK


class SystemMonitor:
    """Singleton class for system resource monitoring and management.
    
    Features:
    - Real-time CPU, RAM, GPU metrics
    - Temperature monitoring with thermal throttling
    - Automatic memory cleanup on high usage
    - Cool-down mode for thermal protection
    - Streaming mode decision logic
    
    Usage:
        monitor = SystemMonitor.get_instance()
        metrics = monitor.get_current_metrics()
        if monitor.should_use_streaming(file_size_mb=75, page_count=30):
            # Use streaming mode
    """
    
    # Thresholds (configurable)
    RAM_WARNING_THRESHOLD = 85.0  # percent
    RAM_CRITICAL_THRESHOLD = 95.0  # percent
    TEMP_CRITICAL = 80.0  # Celsius
    TEMP_COOLDOWN_EXIT = 70.0  # Celsius
    
    _instance: Optional['SystemMonitor'] = None
    
    def __init__(self):
        """Initialize system monitor (use get_instance() instead)."""
        if not PSUTIL_AVAILABLE:
            logger.warning("System monitoring initialized without psutil - limited functionality")
        
        self._is_cooldown_active = False
        self._cooldown_start_time: Optional[datetime] = None
        self._last_cleanup_time: Optional[datetime] = None
        self._cleanup_cooldown = timedelta(seconds=30)  # Minimum time between cleanups
        
        logger.info("SystemMonitor initialized")
    
    @classmethod
    def get_instance(cls) -> 'SystemMonitor':
        """Get singleton instance of SystemMonitor.
        
        Returns:
            SystemMonitor instance
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    # =========================================================================
    # Real-time Metrics
    # =========================================================================
    
    def get_cpu_usage(self, interval: float = 1.0) -> float:
        """Get average CPU usage percentage.
        
        Args:
            interval: Measurement interval in seconds
            
        Returns:
            CPU usage percentage (0-100)
        """
        if not PSUTIL_AVAILABLE:
            return 0.0
        
        try:
            return psutil.cpu_percent(interval=interval)
        except Exception as e:
            logger.debug(f"Failed to get CPU usage: {e}")
            return 0.0
    
    def get_ram_usage(self) -> Tuple[float, float]:
        """Get RAM usage statistics.
        
        Returns:
            Tuple of (used_gb, percent_used)
        """
        if not PSUTIL_AVAILABLE:
            return (0.0, 0.0)
        
        try:
            mem = psutil.virtual_memory()
            used_gb = mem.used / (1024 ** 3)
            return (used_gb, mem.percent)
        except Exception as e:
            logger.debug(f"Failed to get RAM usage: {e}")
            return (0.0, 0.0)
    
    def get_gpu_metrics(self) -> Dict[str, Optional[float]]:
        """Get GPU metrics (VRAM usage, temperature, utilization).
        
        Returns:
            Dictionary with GPU metrics or None values if unavailable
        """
        metrics = {
            "vram_used_mb": None,
            "vram_total_mb": None,
            "temperature_c": None,
            "utilization_percent": None
        }
        
        # Try GPUtil first
        if GPUTIL_AVAILABLE:
            try:
                gpus = GPUtil.getGPUs()
                if gpus:
                    gpu = gpus[0]  # Use first GPU
                    metrics["vram_used_mb"] = gpu.memoryUsed
                    metrics["vram_total_mb"] = gpu.memoryTotal
                    metrics["temperature_c"] = gpu.temperature
                    metrics["utilization_percent"] = gpu.load * 100
                    return metrics
            except Exception as e:
                logger.debug(f"GPUtil failed: {e}")
        
        # Try pynvml as fallback
        if PYNVML_AVAILABLE:
            try:
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                
                # VRAM usage
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                metrics["vram_used_mb"] = mem_info.used / (1024 ** 2)
                metrics["vram_total_mb"] = mem_info.total / (1024 ** 2)
                
                # Temperature
                try:
                    temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                    metrics["temperature_c"] = float(temp)
                except:
                    pass
                
                # Utilization
                try:
                    util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                    metrics["utilization_percent"] = float(util.gpu)
                except:
                    pass
                
                return metrics
            except Exception as e:
                logger.debug(f"pynvml failed: {e}")
        
        return metrics
    
    def get_system_temperature(self) -> Optional[float]:
        """Get system temperature (CPU cores).
        
        Handles OS differences. Returns average core temperature if available.
        
        Returns:
            Temperature in Celsius or None if unavailable
        """
        if not PSUTIL_AVAILABLE:
            return None
        
        try:
            # Get sensor temperatures
            temps = psutil.sensors_temperatures()
            
            if not temps:
                return None
            
            # Different sensors on different platforms
            # Linux: 'coretemp', 'k10temp', 'cpu_thermal'
            # Windows: May not have sensors (requires admin)
            # macOS: 'TC0P', 'TC0E', etc. (requires admin/root)
            
            # Try common sensor names
            for sensor_name in ['coretemp', 'k10temp', 'cpu-thermal', 'cpu_thermal']:
                if sensor_name in temps:
                    readings = temps[sensor_name]
                    # Average all core temperatures
                    core_temps = [entry.current for entry in readings if entry.current > 0]
                    if core_temps:
                        return sum(core_temps) / len(core_temps)
            
            # Fallback: use first available sensor
            for sensor_name, entries in temps.items():
                core_temps = [entry.current for entry in entries if entry.current > 0]
                if core_temps:
                    logger.debug(f"Using temperature sensor: {sensor_name}")
                    return sum(core_temps) / len(core_temps)
        
        except (AttributeError, Exception) as e:
            # sensors_temperatures() not supported on this platform
            logger.debug(f"Temperature monitoring not available: {e}")
        
        return None
    
    def get_current_metrics(self) -> SystemMetrics:
        """Get comprehensive current system metrics.
        
        Returns:
            SystemMetrics object with all current readings
        """
        # CPU
        cpu_percent = self.get_cpu_usage(interval=0.1)  # Quick sample
        cpu_count = psutil.cpu_count() if PSUTIL_AVAILABLE else 0
        
        # RAM
        ram_used_gb, ram_percent = self.get_ram_usage()
        if PSUTIL_AVAILABLE:
            mem = psutil.virtual_memory()
            ram_total_gb = mem.total / (1024 ** 3)
            ram_available_gb = mem.available / (1024 ** 3)
        else:
            ram_total_gb = 0.0
            ram_available_gb = 0.0
        
        # GPU
        gpu_metrics = self.get_gpu_metrics()
        gpu_available = any(v is not None for v in gpu_metrics.values())
        
        # Temperature
        cpu_temp = self.get_system_temperature()
        
        # Determine health status
        health_status = self._calculate_health_status(
            ram_percent, cpu_temp, gpu_metrics.get("temperature_c")
        )
        
        return SystemMetrics(
            timestamp=datetime.now(),
            cpu_percent=cpu_percent,
            cpu_count=cpu_count,
            ram_total_gb=ram_total_gb,
            ram_used_gb=ram_used_gb,
            ram_available_gb=ram_available_gb,
            ram_percent=ram_percent,
            gpu_available=gpu_available,
            gpu_vram_used_mb=gpu_metrics.get("vram_used_mb"),
            gpu_vram_total_mb=gpu_metrics.get("vram_total_mb"),
            gpu_temperature_c=gpu_metrics.get("temperature_c"),
            gpu_utilization_percent=gpu_metrics.get("utilization_percent"),
            cpu_temperature_c=cpu_temp,
            health_status=health_status
        )
    
    # =========================================================================
    # Health Checks
    # =========================================================================
    
    def _calculate_health_status(
        self,
        ram_percent: float,
        cpu_temp: Optional[float],
        gpu_temp: Optional[float]
    ) -> HealthStatus:
        """Calculate overall system health status.
        
        Args:
            ram_percent: RAM usage percentage
            cpu_temp: CPU temperature in Celsius (optional)
            gpu_temp: GPU temperature in Celsius (optional)
            
        Returns:
            HealthStatus enum value
        """
        # Check RAM
        if ram_percent >= self.RAM_CRITICAL_THRESHOLD:
            return HealthStatus.CRITICAL
        
        # Check temperatures
        max_temp = 0.0
        if cpu_temp:
            max_temp = max(max_temp, cpu_temp)
        if gpu_temp:
            max_temp = max(max_temp, gpu_temp)
        
        if max_temp >= self.TEMP_CRITICAL:
            return HealthStatus.CRITICAL
        
        # Check warning thresholds
        if ram_percent >= self.RAM_WARNING_THRESHOLD:
            return HealthStatus.WARNING
        
        if max_temp >= (self.TEMP_CRITICAL - 10):  # Within 10°C of critical
            return HealthStatus.WARNING
        
        return HealthStatus.OK
    
    def check_health(self) -> HealthStatus:
        """Check current system health status.
        
        Returns:
            HealthStatus enum value
        """
        metrics = self.get_current_metrics()
        return metrics.health_status
    
    # =========================================================================
    # Automatic Memory Cleanup
    # =========================================================================
    
    def attempt_memory_cleanup(self, force: bool = False) -> bool:
        """Attempt to free up memory through garbage collection and cache clearing.
        
        Args:
            force: If True, bypass cooldown period
            
        Returns:
            True if cleanup was performed, False if skipped
        """
        # Check cooldown
        if not force and self._last_cleanup_time:
            time_since_cleanup = datetime.now() - self._last_cleanup_time
            if time_since_cleanup < self._cleanup_cooldown:
                logger.debug("Cleanup skipped - in cooldown period")
                return False
        
        logger.info("🧹 Attempting memory cleanup...")
        
        # Get metrics before cleanup
        _, ram_before = self.get_ram_usage()
        
        # 1. Python garbage collection
        collected = gc.collect()
        logger.debug(f"Garbage collector: {collected} objects collected")
        
        # 2. Clear PyTorch cache
        if TORCH_AVAILABLE:
            try:
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    logger.debug("PyTorch CUDA cache cleared")
            except Exception as e:
                logger.debug(f"PyTorch cache clear failed: {e}")
        
        # 3. Clear Paddle cache
        if PADDLE_AVAILABLE:
            try:
                paddle.device.cuda.empty_cache()
                logger.debug("Paddle CUDA cache cleared")
            except Exception as e:
                logger.debug(f"Paddle cache clear failed: {e}")
        
        # 4. TODO: Signal ModelManager to unload unused models
        # This would require integration with your model management system:
        # from local_body.agents.model_manager import ModelManager
        # ModelManager.unload_unused_models()
        
        # Get metrics after cleanup
        time.sleep(0.5)  # Give system time to update
        _, ram_after = self.get_ram_usage()
        
        freed_percent = ram_before - ram_after
        logger.info(f"✓ Memory cleanup complete - freed {freed_percent:.1f}% RAM")
        
        self._last_cleanup_time = datetime.now()
        return True
    
    def _check_and_cleanup_memory(self):
        """Automatically cleanup memory if critical threshold reached."""
        _, ram_percent = self.get_ram_usage()
        
        if ram_percent >= self.RAM_CRITICAL_THRESHOLD:
            logger.warning(
                f"⚠️ RAM usage critical ({ram_percent:.1f}%) - triggering automatic cleanup"
            )
            self.attempt_memory_cleanup(force=True)
    
    # =========================================================================
    # Cool-down Mode (Thermal Protection)
    # =========================================================================
    
    @property
    def is_cooldown_active(self) -> bool:
        """Check if system is in cool-down mode."""
        return self._is_cooldown_active
    
    def _check_thermal_throttling(self):
        """Check temperature and manage cool-down mode."""
        cpu_temp = self.get_system_temperature()
        gpu_metrics = self.get_gpu_metrics()
        gpu_temp = gpu_metrics.get("temperature_c")
        
        max_temp = 0.0
        if cpu_temp:
            max_temp = max(max_temp, cpu_temp)
        if gpu_temp:
            max_temp = max(max_temp, gpu_temp)
        
        if not self._is_cooldown_active:
            # Check if we need to enter cool-down
            if max_temp >= self.TEMP_CRITICAL:
                self._is_cooldown_active = True
                self._cooldown_start_time = datetime.now()
                logger.warning(
                    f"🌡️ System overheating ({max_temp:.1f}°C) - "
                    f"COOL-DOWN MODE ACTIVATED. Pausing new tasks..."
                )
        else:
            # Check if we can exit cool-down
            if max_temp < self.TEMP_COOLDOWN_EXIT:
                duration = datetime.now() - self._cooldown_start_time
                self._is_cooldown_active = False
                self._cooldown_start_time = None
                logger.info(
                    f"✓ Temperature normalized ({max_temp:.1f}°C) - "
                    f"cool-down ended after {duration.total_seconds():.0f}s"
                )
    
    def can_process_new_task(self) -> bool:
        """Check if system can accept new processing tasks.
        
        Returns:
            False if in cool-down mode, True otherwise
        """
        self._check_thermal_throttling()
        return not self._is_cooldown_active
    
    # =========================================================================
    # Streaming Mode Decision Logic
    # =========================================================================
    
    def should_use_streaming(
        self,
        file_size_mb: float,
        page_count: int,
        ram_threshold_percent: float = 70.0
    ) -> bool:
        """Determine if streaming mode should be used for a document.
        
        Decision factors:
        - File size > 50MB
        - Page count > 20
        - Current RAM usage > threshold
        
        Args:
            file_size_mb: Document file size in megabytes
            page_count: Number of pages in document
            ram_threshold_percent: RAM usage threshold for streaming (default: 70%)
            
        Returns:
            True if streaming mode is recommended
        """
        # Check file size
        if file_size_mb > 50:
            logger.info(f"Streaming mode: File size ({file_size_mb:.1f}MB) exceeds 50MB threshold")
            return True
        
        # Check page count
        if page_count > 20:
            logger.info(f"Streaming mode: Page count ({page_count}) exceeds 20 pages")
            return True
        
        # Check current RAM usage
        _, ram_percent = self.get_ram_usage()
        if ram_percent > ram_threshold_percent:
            logger.info(
                f"Streaming mode: RAM usage ({ram_percent:.1f}%) exceeds "
                f"{ram_threshold_percent}% threshold"
            )
            return True
        
        logger.debug(
            f"Normal mode: file={file_size_mb:.1f}MB, pages={page_count}, "
            f"RAM={ram_percent:.1f}%"
        )
        return False
    
    # =========================================================================
    # Monitoring Loop
    # =========================================================================
    
    def run_health_check_cycle(self):
        """Run a complete health check cycle.
        
        This should be called periodically (e.g., every 5-10 seconds) to:
        - Update health status
        - Trigger automatic cleanup if needed
        - Manage thermal throttling
        """
        self._check_and_cleanup_memory()
        self._check_thermal_throttling()
        
        metrics = self.get_current_metrics()
        
        # Log warnings
        if metrics.health_status == HealthStatus.WARNING:
            logger.warning(
                f"⚠️ System health: WARNING - RAM: {metrics.ram_percent:.1f}%, "
                f"CPU Temp: {metrics.cpu_temperature_c or 'N/A'}°C"
            )
        elif metrics.health_status == HealthStatus.CRITICAL:
            logger.error(
                f"🚨 System health: CRITICAL - RAM: {metrics.ram_percent:.1f}%, "
                f"CPU Temp: {metrics.cpu_temperature_c or 'N/A'}°C"
            )
