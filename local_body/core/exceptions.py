"""Unified exception hierarchy for Sovereign-Doc.

Provides categorized exceptions for different failure scenarios,
enabling appropriate error handling and user feedback.
"""

from typing import Optional, Dict, Any


class SovereignError(Exception):
    """Base exception for all Sovereign-Doc errors.
    
    All custom exceptions inherit from this to enable
    catch-all error handling when needed.
    """
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        recoverable: bool = True
    ):
        """Initialize error.
        
        Args:
            message: Human-readable error message
            details: Additional context (optional)
            recoverable: Whether the error can be recovered from
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.recoverable = recoverable
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for logging/display.
        
        Returns:
            Dictionary with error details
        """
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "recoverable": self.recoverable,
            "details": self.details
        }


class ResourceError(SovereignError):
    """Hardware or system resource errors.
    
    Raised when:
    - Insufficient RAM/CPU
    - Disk space too low
    - GPU unavailable when required
    - System temperature critical
    
    UI Response: Show fallback options, reduce processing mode
    """
    
    def __init__(
        self,
        message: str,
        resource_type: str = "unknown",
        required: Optional[str] = None,
        available: Optional[str] = None,
        **kwargs
    ):
        """Initialize resource error.
        
        Args:
            message: Error description
            resource_type: Type of resource (ram, cpu, gpu, disk)
            required: Required amount/state
            available: Currently available
            **kwargs: Additional details
        """
        details = {
            "resource_type": resource_type,
            "required": required,
            "available": available,
            **kwargs
        }
        super().__init__(message, details=details, recoverable=True)


class DependencyError(SovereignError):
    """External dependency or service errors.
    
    Raised when:
    - Qdrant not accessible
    - Colab Brain disconnected
    - Required model not found
    - External API unavailable
    
    UI Response: Show setup guide, offer local-only mode
    """
    
    def __init__(
        self,
        message: str,
        dependency: str = "unknown",
        setup_guide_url: Optional[str] = None,
        **kwargs
    ):
        """Initialize dependency error.
        
        Args:
            message: Error description
            dependency: Name of missing dependency
            setup_guide_url: Link to setup instructions
            **kwargs: Additional details
        """
        details = {
            "dependency": dependency,
            "setup_guide": setup_guide_url,
            **kwargs
        }
        super().__init__(message, details=details, recoverable=True)


class ProcessingError(SovereignError):
    """Document processing or agent errors.
    
    Raised when:
    - OCR fails on a page
    - Vision model produces invalid output
    - Validation detects corruption
    - Workflow state becomes invalid
    
    UI Response: Offer retry, show partial results
    """
    
    def __init__(
        self,
        message: str,
        stage: str = "unknown",
        document_id: Optional[str] = None,
        page_number: Optional[int] = None,
        **kwargs
    ):
        """Initialize processing error.
        
        Args:
            message: Error description
            stage: Processing stage where error occurred
            document_id: Document being processed
            page_number: Page number if applicable
            **kwargs: Additional details
        """
        details = {
            "stage": stage,
            "document_id": document_id,
            "page_number": page_number,
            **kwargs
        }
        super().__init__(message, details=details, recoverable=True)


class ConfigurationError(SovereignError):
    """Configuration or settings errors.
    
    Raised when:
    - config.yaml invalid or missing
    - Environment variables not set
    - Incompatible settings combinations
    
    UI Response: Show configuration guide
    """
    
    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        expected_value: Optional[str] = None,
        **kwargs
    ):
        """Initialize configuration error.
        
        Args:
            message: Error description
            config_key: Configuration key with issue
            expected_value: What the value should be
            **kwargs: Additional details
        """
        details = {
            "config_key": config_key,
            "expected_value": expected_value,
            **kwargs
        }
        super().__init__(message, details=details, recoverable=True)


class SecurityError(SovereignError):
    """Security or authentication errors.
    
    Raised when:
    - Access token invalid
    - Tunnel compromised
    - Authentication failures exceed threshold
    
    UI Response: Show security alert, block operations
    """
    
    def __init__(
        self,
        message: str,
        threat_level: str = "medium",
        **kwargs
    ):
        """Initialize security error.
        
        Args:
            message: Error description
            threat_level: Severity (low, medium, high, critical)
            **kwargs: Additional details
        """
        details = {
            "threat_level": threat_level,
            **kwargs
        }
        super().__init__(message, details=details, recoverable=False)


class StartupError(SovereignError):
    """System startup or bootstrap errors.
    
    Raised when:
    - Critical initialization fails
    - Incompatible system state
    - Required components unavailable
    
    UI Response: Show maintenance screen, prevent app launch
    """
    
    def __init__(
        self,
        message: str,
        startup_stage: str = "unknown",
        **kwargs
    ):
        """Initialize startup error.
        
        Args:
            message: Error description
            startup_stage: Which startup stage failed
            **kwargs: Additional details
        """
        details = {
            "startup_stage": startup_stage,
            **kwargs
        }
        super().__init__(message, details=details, recoverable=True)
