"""Logging setup with PII redaction and privacy protection.

Configures Loguru logger with:
- Console output for development
- File output with PII redaction
- Structured JSON logging
- Audit trail separation
"""

import sys
from pathlib import Path
from loguru import logger

from local_body.core.privacy import get_privacy_manager


def redact_pii_filter(record: dict) -> bool:
    """Loguru filter to redact PII from log messages.
    
    Args:
        record: Loguru record dictionary
        
    Returns:
        True to keep the record (always, but message is modified)
    """
    # Get privacy manager
    privacy_manager = get_privacy_manager()
    
    # Redact PII from message
    if 'message' in record:
        record['message'] = privacy_manager.redact_pii(record['message'])
    
    # Redact PII from extra fields
    if 'extra' in record:
        for key, value in record['extra'].items():
            if isinstance(value, str):
                record['extra'][key] = privacy_manager.redact_pii(value)
    
    return True


def setup_logging(
    log_level: str = "INFO",
    log_dir: Path = Path("logs"),
    enable_file_logging: bool = True,
    enable_pii_redaction: bool = True
) -> None:
    """Configure application logging with privacy protection.
    
    Args:
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR)
        log_dir: Directory for log files
        enable_file_logging: Whether to write logs to files
        enable_pii_redaction: Whether to redact PII in logs
    """
    # Remove default handler
    logger.remove()
    
    # Console handler (verbose for debugging, can show more detail)
    console_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )
    
    logger.add(
        sys.stderr,
        format=console_format,
        level=log_level,
        colorize=True,
        backtrace=True,
        diagnose=True
    )
    
    if enable_file_logging:
        # Create log directory
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # File handler with PII redaction (CRITICAL for privacy)
        file_format = (
            "{time:YYYY-MM-DD HH:mm:ss} | "
            "{level: <8} | "
            "{name}:{function}:{line} - "
            "{message}"
        )
        
        # Main application log (with PII redaction)
        log_file = log_dir / "application.log"
        
        if enable_pii_redaction:
            logger.add(
                log_file,
                format=file_format,
                level=log_level,
                rotation="10 MB",  # Rotate when file reaches 10MB
                retention="30 days",  # Keep logs for 30 days
                compression="zip",  # Compress rotated logs
                backtrace=False,  # Don't include full traceback for privacy
                diagnose=False,  # Don't include variable values
                filter=redact_pii_filter,  # Apply PII redaction
                enqueue=True  # Thread-safe
            )
        else:
            # No redaction (use only in secure dev environments)
            logger.add(
                log_file,
                format=file_format,
                level=log_level,
                rotation="10 MB",
                retention="30 days",
                compression="zip",
                enqueue=True
            )
        
        # Error log (separate file for errors only - FULL TRACEBACKS for debugging)
        error_log = log_dir / "errors.log"
        logger.add(
            error_log,
            format=file_format,
            level="ERROR",
            rotation="5 MB",
            retention="60 days",
            compression="zip",
            backtrace=True,  # ENABLED: Full traceback for debugging
            diagnose=True,   # ENABLED: Include variable values 
            filter=redact_pii_filter if enable_pii_redaction else None,
            enqueue=True
        )
        
        # Structured JSON log (for automated parsing)
        json_log = log_dir / "structured.jsonl"
        logger.add(
            json_log,
            format="{message}",
            level=log_level,
            rotation="20 MB",
            retention="30 days",
            compression="zip",
            serialize=True,  # Output as JSON
            filter=redact_pii_filter if enable_pii_redaction else None,
            enqueue=True
        )
    
    logger.info(f"Logging configured: level={log_level}, file_logging={enable_file_logging}, pii_redaction={enable_pii_redaction}")


def get_sanitized_logger():
    """Get logger instance with PII redaction enabled.
    
    This is a convenience function that returns the global logger
    with redaction already configured.
    
    Returns:
        Configured logger instance
    """
    return logger


# Convenience function to log with explicit PII redaction
def log_info_safe(message: str, **kwargs) -> None:
    """Log info message with automatic PII redaction.
    
    Args:
        message: Log message (may contain PII)
        **kwargs: Additional context (will be redacted)
    """
    privacy_manager = get_privacy_manager()
    safe_message = privacy_manager.redact_pii(message)
    
    # Redact kwargs
    safe_kwargs = {}
    for key, value in kwargs.items():
        if isinstance(value, str):
            safe_kwargs[key] = privacy_manager.redact_pii(value)
        else:
            safe_kwargs[key] = value
    
    logger.info(safe_message, **safe_kwargs)


def log_error_safe(message: str, exception: Exception = None, **kwargs) -> None:
    """Log error message with automatic PII redaction.
    
    Args:
        message: Error message (may contain PII)
        exception: Exception object (if applicable)
        **kwargs: Additional context
    """
    privacy_manager = get_privacy_manager()
    safe_message = privacy_manager.redact_pii(message)
    
    if exception:
        # Log exception type but redact message
        exc_type = type(exception).__name__
        exc_message = privacy_manager.redact_pii(str(exception))
        safe_message = f"{safe_message} | {exc_type}: {exc_message}"
    
    logger.error(safe_message, **kwargs)


# Initialize logging on module import with safe defaults
setup_logging(
    log_level="INFO",
    enable_file_logging=True,
    enable_pii_redaction=True  # ALWAYS redact PII in production
)
