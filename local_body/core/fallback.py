"""Graceful degradation and fallback system for robust document processing.

This module provides intelligent mode selection based on system resources and
automatic retry logic with degradation for resilient processing under constraints.

Features:
- ProcessingMode hierarchy (HYBRID → LOCAL_GPU → LOCAL_CPU → OCR_ONLY)
- FallbackManager for dynamic mode selection based on HealthMonitor
- Retry decorator with automatic downgrade on persistent failures
- Integration with system health monitoring
"""

import gc
import time
import functools
from enum import Enum
from typing import Optional, Callable, Any, List, Tuple
from dataclasses import dataclass
from loguru import logger

from local_body.core.health import HealthMonitor
from local_body.core.monitor import SystemMonitor
from local_body.core.config_manager import SystemConfig
from local_body.core.alerts import AlertSeverity, AlertComponent


class ProcessingMode(Enum):
    """Processing mode hierarchy from highest to lowest capability.
    
    Modes are ordered by resource requirements and capabilities:
    - HYBRID: Maximum performance (GPU + external APIs)
    - LOCAL_GPU: Full local processing with GPU acceleration
    - LOCAL_CPU: CPU-only fallback (slower but stable)
    - OCR_ONLY: Safe mode - text extraction only, no embeddings/vision
    """
    HYBRID = 0      # Level 0: Highest - GPU + External APIs (if available)
    LOCAL_GPU = 1   # Level 1: Full local with CUDA/MPS
    LOCAL_CPU = 2   # Level 2: CPU-only (stable fallback)
    OCR_ONLY = 3    # Level 3: Lowest - Safe mode, text only
    
    def __lt__(self, other):
        """Enable comparison for mode hierarchy."""
        if not isinstance(other, ProcessingMode):
            return NotImplemented
        return self.value < other.value
    
    def __le__(self, other):
        if not isinstance(other, ProcessingMode):
            return NotImplemented
        return self.value <= other.value


@dataclass
class ModeRequirements:
    """Resource requirements for a processing mode."""
    min_ram_gb: float
    needs_gpu: bool
    needs_database: bool
    needs_network: bool
    description: str


class FallbackManager:
    """Singleton manager for intelligent processing mode selection and degradation.
    
    Integrates with HealthMonitor to determine optimal processing mode based on:
    - System resource availability (RAM, GPU)
    - Service health (database, network)
    - Active alerts and critical issues
    
    Features:
    - Automatic mode downgrading based on resource constraints
    - Mode validation before use
    - Integration with retry logic for failure handling
    
    Usage:
        manager = FallbackManager.get_instance(config)
        mode = manager.determine_optimal_mode()
        
        if not manager.can_use_mode(mode):
            mode = manager.downgrade_mode(mode)
    """
    
    # Resource requirements for each mode
    MODE_REQUIREMENTS = {
        ProcessingMode.HYBRID: ModeRequirements(
            min_ram_gb=8.0,
            needs_gpu=False,  # Optional but preferred
            needs_database=True,  # Needs vector store
            needs_network=True,   # Needs tunnel for vision API
            description="GPU + External APIs (maximum performance)"
        ),
        ProcessingMode.LOCAL_GPU: ModeRequirements(
            min_ram_gb=6.0,
            needs_gpu=True,
            needs_database=True,
            needs_network=False,
            description="Local GPU processing (high performance)"
        ),
        ProcessingMode.LOCAL_CPU: ModeRequirements(
            min_ram_gb=4.0,
            needs_gpu=False,
            needs_database=True,
            needs_network=False,
            description="CPU-only processing (stable fallback)"
        ),
        ProcessingMode.OCR_ONLY: ModeRequirements(
            min_ram_gb=2.0,
            needs_gpu=False,
            needs_database=False,
            needs_network=False,
            description="Safe mode - text extraction only"
        )
    }
    
    # Thresholds for mode selection
    RAM_CRITICAL_THRESHOLD = 90.0  # percent
    GPU_VRAM_MIN_GB = 2.0         # GB
    
    _instance: Optional['FallbackManager'] = None
    
    def __init__(self, config: SystemConfig):
        """Initialize fallback manager (use get_instance() instead).
        
        Args:
            config: SystemConfig instance
        """
        self.config = config
        
        # Get health monitor instance
        try:
            self.health_monitor = HealthMonitor.get_instance(config)
        except RuntimeError:
            # HealthMonitor not initialized yet
            self.health_monitor = None
            logger.warning("HealthMonitor not available - mode selection will be limited")
        
        # Get system monitor
        self.system_monitor = SystemMonitor.get_instance()
        
        # Track current mode
        self._current_mode: Optional[ProcessingMode] = None
        
        logger.info("FallbackManager initialized")
    
    @classmethod
    def get_instance(cls, config: Optional[SystemConfig] = None) -> 'FallbackManager':
        """Get singleton instance of FallbackManager.
        
        Args:
            config: SystemConfig (required on first call)
            
        Returns:
            FallbackManager instance
        """
        if cls._instance is None:
            if config is None:
                raise RuntimeError("Config required for first FallbackManager initialization")
            cls._instance = cls(config)
        return cls._instance
    
    def determine_optimal_mode(self) -> ProcessingMode:
        """Determine the optimal processing mode based on current system state.
        
        Logic:
        1. Check for critical alerts (DB down, OOM risk)
        2. Check resource availability (RAM, GPU VRAM)
        3. Return highest mode that satisfies constraints
        
        Returns:
            Recommended ProcessingMode
        """
        logger.debug("Determining optimal processing mode...")
        
        # Default to configured mode or HYBRID
        target_mode = self._parse_config_mode()
        
        # Check critical alerts first
        if self.health_monitor:
            try:
                # Check if database is down
                if self._has_critical_alert("database"):
                    logger.warning("Database critical - downgrading to OCR_ONLY")
                    return ProcessingMode.OCR_ONLY
                
                # Check for OOM risk
                if self._has_critical_alert("system", "RAM"):
                    logger.warning("RAM critical - downgrading to OCR_ONLY and triggering GC")
                    # Force garbage collection
                    collected = gc.collect()
                    logger.info(f"Garbage collected {collected} objects")
                    return ProcessingMode.OCR_ONLY
            
            except Exception as e:
                logger.debug(f"Could not check health alerts: {e}")
        
        # Check resource availability
        metrics = self.system_monitor.get_current_metrics()
        
        # Check RAM
        if metrics.ram_percent >= self.RAM_CRITICAL_THRESHOLD:
            logger.warning(
                f"RAM usage critical ({metrics.ram_percent:.1f}%) - "
                "downgrading to OCR_ONLY"
            )
            # Trigger GC
            gc.collect()
            return ProcessingMode.OCR_ONLY
        
        # Check GPU VRAM
        if target_mode in (ProcessingMode.HYBRID, ProcessingMode.LOCAL_GPU):
            if metrics.gpu_available and metrics.gpu_vram_total_mb:
                vram_available_gb = (
                    metrics.gpu_vram_total_mb - metrics.gpu_vram_used_mb
                ) / 1024
                
                if vram_available_gb < self.GPU_VRAM_MIN_GB:
                    logger.warning(
                        f"GPU VRAM low ({vram_available_gb:.1f}GB) - "
                        "downgrading to LOCAL_CPU"
                    )
                    target_mode = ProcessingMode.LOCAL_CPU
            elif target_mode == ProcessingMode.LOCAL_GPU:
                # No GPU available but mode requires it
                logger.info("No GPU available - downgrading to LOCAL_CPU")
                target_mode = ProcessingMode.LOCAL_CPU
        
        # Validate the target mode can actually be used
        if not self.can_use_mode(target_mode):
            logger.warning(f"Cannot use {target_mode.name} - searching for fallback")
            target_mode = self._find_best_available_mode()
        
        logger.info(f"Selected processing mode: {target_mode.name}")
        self._current_mode = target_mode
        
        return target_mode
    
    def can_use_mode(self, mode: ProcessingMode) -> bool:
        """Check if a processing mode can be used with current resources.
        
        Args:
            mode: ProcessingMode to validate
            
        Returns:
            True if mode is usable
        """
        requirements = self.MODE_REQUIREMENTS[mode]
        
        # Check RAM (with small epsilon for edge cases)
        metrics = self.system_monitor.get_current_metrics()
        epsilon = 0.05  # 50MB tolerance
        if metrics.ram_available_gb < (requirements.min_ram_gb - epsilon):
            logger.debug(
                f"Insufficient RAM for {mode.name}: "
                f"need {requirements.min_ram_gb}GB, have {metrics.ram_available_gb:.1f}GB"
            )
            return False
        
        # Check GPU
        if requirements.needs_gpu and not metrics.gpu_available:
            logger.debug(f"GPU required for {mode.name} but not available")
            return False
        
        # Check database (if health monitor available)
        if requirements.needs_database and self.health_monitor:
            try:
       # Quick check if database alert is critical
                if self._has_critical_alert("database"):
                    logger.debug(f"Database required for {mode.name} but critical")
                    return False
            except:
                pass  # If check fails, assume database is available
        
        return True
    
    def downgrade_mode(self, current_mode: ProcessingMode) -> ProcessingMode:
        """Get the next lower processing mode in the hierarchy.
        
        Args:
            current_mode: Current processing mode
            
        Returns:
            Next lower mode, or OCR_ONLY if already at lowest
        """
        if current_mode == ProcessingMode.HYBRID:
            return ProcessingMode.LOCAL_GPU
        elif current_mode == ProcessingMode.LOCAL_GPU:
            return ProcessingMode.LOCAL_CPU
        elif current_mode == ProcessingMode.LOCAL_CPU:
            return ProcessingMode.OCR_ONLY
        else:
            # Already at lowest mode
            return ProcessingMode.OCR_ONLY
    
    def get_current_mode(self) -> Optional[ProcessingMode]:
        """Get the currently active processing mode.
        
        Returns:
            Current mode or None if not set
        """
        return self._current_mode
    
    def _parse_config_mode(self) -> ProcessingMode:
        """Parse processing mode from config.
        
        Returns:
            ProcessingMode from config or default
        """
        config_mode = self.config.processing_mode.lower()
        
        mode_map = {
            "hybrid": ProcessingMode.HYBRID,
            "local": ProcessingMode.LOCAL_GPU,  # Assume GPU if not specified
            "local_gpu": ProcessingMode.LOCAL_GPU,
            "local_cpu": ProcessingMode.LOCAL_CPU,
            "ocr_only": ProcessingMode.OCR_ONLY,
            "safe": ProcessingMode.OCR_ONLY
        }
        
        return mode_map.get(config_mode, ProcessingMode.HYBRID)
    
    def _has_critical_alert(self, component: str, keyword: Optional[str] = None) -> bool:
        """Check if there are critical alerts for a component.
        
        Args:
            component: Component name (e.g., "database", "system")
            keyword: Optional keyword to filter alerts
            
        Returns:
            True if critical alerts found
        """
        if not self.health_monitor:
            return False
        
        try:
            from local_body.core.alerts import AlertComponent, AlertSeverity
            
            # Map string to enum
            component_map = {
                "database": AlertComponent.DATABASE,
                "system": AlertComponent.SYSTEM,
                "network": AlertComponent.NETWORK,
                "model": AlertComponent.MODEL
            }
            
            component_enum = component_map.get(component)
            if not component_enum:
                return False
            
            # Get critical alerts for component
            critical_alerts = self.health_monitor.alerts.get_active_alerts(
                component=component_enum,
                severity=AlertSeverity.CRITICAL
            )
            
            if not critical_alerts:
                return False
            
            # Filter by keyword if provided
            if keyword:
                return any(keyword.lower() in alert.message.lower() for alert in critical_alerts)
            
            return True
        
        except Exception as e:
            logger.debug(f"Error checking critical alerts: {e}")
            return False
    
    def _find_best_available_mode(self) -> ProcessingMode:
        """Find the best available mode by checking each in order.
        
        Returns:
            Best available ProcessingMode
        """
        # Try modes in order from best to worst
        for mode in [ProcessingMode.HYBRID, ProcessingMode.LOCAL_GPU, 
                     ProcessingMode.LOCAL_CPU, ProcessingMode.OCR_ONLY]:
            if self.can_use_mode(mode):
                return mode
        
        # Fallback to safe mode (should always work)
        return ProcessingMode.OCR_ONLY


def with_retry(
    max_retries: int = 3,
    backoff_delays: Optional[List[float]] = None,
    on_failure_downgrade: bool = False,
    retry_on_exceptions: Optional[Tuple[type, ...]] = None
):
    """Decorator to add retry logic with optional mode downgrade on persistent failure.
    
    Args:
        max_retries: Maximum number of retry attempts
        backoff_delays: List of delays in seconds between retries (default: [1, 2, 5])
        on_failure_downgrade: If True, request mode downgrade on final retry
        retry_on_exceptions: Tuple of exception types to retry on (default: all)
    
    Usage:
        @with_retry(max_retries=3, on_failure_downgrade=True)
        def risky_operation():
            # May fail due to OOM, timeout, etc.
            pass
    """
    if backoff_delays is None:
        backoff_delays = [1.0, 2.0, 5.0]
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(1, max_retries + 1):
                try:
                    result = func(*args, **kwargs)
                    
                    # Success - log if this was a retry
                    if attempt > 1:
                        logger.success(
                            f"{func.__name__} succeeded on attempt {attempt}/{max_retries}"
                        )
                    
                    return result
                
                except Exception as e:
                    last_exception = e
                    
                    # Check if we should retry this exception
                    if retry_on_exceptions and not isinstance(e, retry_on_exceptions):
                        # Don't retry this type of exception
                        logger.warning(
                            f"{func.__name__} failed with non-retryable exception: {type(e).__name__}"
                        )
                        raise
                    
                    # Log the failure
                    if attempt < max_retries:
                        # Calculate delay
                        delay_index = min(attempt - 1, len(backoff_delays) - 1)
                        delay = backoff_delays[delay_index]
                        
                        logger.warning(
                            f"{func.__name__} failed (attempt {attempt}/{max_retries}): {type(e).__name__}: {str(e)}"
                        )
                        logger.info(f"Retrying in {delay}s...")
                        
                        time.sleep(delay)
                    else:
                        # Final attempt failed
                        logger.error(
                            f"{func.__name__} failed after {max_retries} attempts: {type(e).__name__}: {str(e)}"
                        )
                        
                        # Request mode downgrade if enabled
                        if on_failure_downgrade:
                            try:
                                from local_body.core.fallback import FallbackManager
                                manager = FallbackManager.get_instance()
                                current_mode = manager.get_current_mode()
                                
                                if current_mode:
                                    downgraded_mode = manager.downgrade_mode(current_mode)
                                    logger.warning(
                                        f"Requesting mode downgrade: {current_mode.name} → {downgraded_mode.name}"
                                    )
                                    # Note: Actual mode change must be handled by caller
                            except Exception as downgrade_error:
                                logger.debug(f"Could not request downgrade: {downgrade_error}")
            
            # All retries exhausted - raise last exception
            raise last_exception
        
        return wrapper
    return decorator
