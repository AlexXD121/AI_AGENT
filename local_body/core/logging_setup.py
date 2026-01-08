"""Logging setup and configuration for Sovereign-Doc.

This module configures the loguru logger with console and file outputs,
rotation, and structured logging for agent activities.
"""

import sys
from pathlib import Path
from typing import Optional

from loguru import logger


def setup_logging(
    log_level: str = "INFO",
    log_file_path: str = "data/logs/sovereign.log",
    log_rotation: str = "500 MB",
    enable_console: bool = True,
    enable_file: bool = True
) -> None:
    """Set up logging configuration for the Sovereign-Doc system.
    
    Configures loguru with two sinks:
    1. Console output (stderr) with colored formatting
    2. File output with rotation and retention
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file_path: Path to the log file
        log_rotation: Rotation size (e.g., "500 MB", "1 GB")
        enable_console: Whether to enable console logging
        enable_file: Whether to enable file logging
    """
    # Remove default logger
    logger.remove()
    
    # Console sink with colored output
    if enable_console:
        logger.add(
            sys.stderr,
            level=log_level,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                   "<level>{level: <8}</level> | "
                   "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                   "<level>{message}</level>",
            colorize=True,
            backtrace=True,
            diagnose=True
        )
    
    # File sink with rotation
    if enable_file:
        # Ensure log directory exists
        log_path = Path(log_file_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        logger.add(
            log_file_path,
            level=log_level,
            format="{time:YYYY-MM-DD HH:mm:ss} | "
                   "{level: <8} | "
                   "{name}:{function}:{line} | "
                   "{message}",
            rotation=log_rotation,
            retention="10 days",
            compression="zip",
            backtrace=True,
            diagnose=True,
            enqueue=True  # Thread-safe logging
        )
    
    logger.info(f"Logging initialized at level {log_level}")
    if enable_file:
        logger.info(f"Log file: {log_file_path} (rotation: {log_rotation})")


def get_logger(name: Optional[str] = None):
    """Get a logger instance for a specific module.
    
    Args:
        name: Name of the module/component requesting the logger
        
    Returns:
        Configured logger instance
    """
    if name:
        return logger.bind(name=name)
    return logger


def log_agent_activity(
    agent_type: str,
    action: str,
    document_id: Optional[str] = None,
    details: Optional[dict] = None
) -> None:
    """Log structured agent activity for monitoring and debugging.
    
    Args:
        agent_type: Type of agent (ocr, vision, layout, validator, resolver)
        action: Action being performed (e.g., "processing_started", "conflict_detected")
        document_id: Optional document ID being processed
        details: Optional dictionary of additional details
    """
    log_data = {
        "agent_type": agent_type,
        "action": action,
    }
    
    if document_id:
        log_data["document_id"] = document_id
    
    if details:
        log_data.update(details)
    
    logger.info(f"Agent Activity: {agent_type} - {action}", **log_data)


def log_performance_metric(
    metric_name: str,
    value: float,
    unit: str = "",
    context: Optional[dict] = None
) -> None:
    """Log performance metrics for monitoring system performance.
    
    Args:
        metric_name: Name of the metric (e.g., "processing_time", "memory_usage")
        value: Metric value
        unit: Unit of measurement (e.g., "seconds", "MB", "%")
        context: Optional context information
    """
    log_data = {
        "metric": metric_name,
        "value": value,
        "unit": unit
    }
    
    if context:
        log_data.update(context)
    
    logger.debug(f"Performance: {metric_name} = {value} {unit}", **log_data)


def log_error_with_context(
    error: Exception,
    context: str,
    additional_info: Optional[dict] = None
) -> None:
    """Log errors with contextual information for debugging.
    
    Args:
        error: The exception that occurred
        context: Description of what was being done when error occurred
        additional_info: Optional additional debugging information
    """
    log_data = {
        "error_type": type(error).__name__,
        "error_message": str(error),
        "context": context
    }
    
    if additional_info:
        log_data.update(additional_info)
    
    logger.error(f"Error in {context}: {error}", **log_data)
    logger.exception(error)
