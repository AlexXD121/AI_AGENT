"""Security Manager for Access Control and Authentication.

Implements token-based authentication, security monitoring, and threat detection.
"""

import time
import secrets
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import deque

from loguru import logger
from pydantic import BaseModel, Field

from local_body.core.privacy import get_privacy_manager


class AuthFailure(BaseModel):
    """Record of authentication failure."""
    timestamp: datetime
    endpoint: str
    error_code: int
    ip_address: Optional[str] = None


class SecurityManager:
    """Manages authentication, access control, and security monitoring.
    
    Features:
    - Token-based authentication for Colab Brain
    - Failed authentication tracking
    - Automatic threat detection
    - Security alerts
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self.access_token: Optional[str] = None
            self.auth_failures: deque = deque(maxlen=100)  # Keep last 100 failures
            self.blocked_ips: set = set()
            self.tunnel_compromised = False
            
            # Security thresholds
            self.max_failures_per_minute = 3
            self.failure_window_seconds = 60
            
            self._initialized = True
            logger.info("SecurityManager initialized")
    
    @classmethod
    def get_instance(cls) -> "SecurityManager":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def set_access_token(self, token: str) -> None:
        """Set the access token for Colab Brain authentication.
        
        Args:
            token: Access token (should be strong random string)
        """
        if not token or len(token) < 16:
            raise ValueError("Access token must be at least 16 characters")
        
        self.access_token = token
        logger.info("Access token configured (length: {})".format(len(token)))
        
        # Audit log (never log actual token!)
        get_privacy_manager().audit_log(
            action="access_token_set",
            resource="security",
            metadata={"token_length": len(token)}
        )
    
    def generate_access_token(self, length: int = 32) -> str:
        """Generate a cryptographically secure access token.
        
        Args:
            length: Token length in characters (default: 32)
            
        Returns:
            Secure random token string
        """
        token = secrets.token_urlsafe(length)
        logger.warning(
            f"Generated new access token (length: {len(token)}). "
            "Copy this to your Colab Brain environment!"
        )
        
        # Audit
        get_privacy_manager().audit_log(
            action="access_token_generated",
            resource="security",
            metadata={"token_length": len(token)}
        )
        
        return token
    
    def validate_token(self, provided_token: str) -> bool:
        """Validate provided token against configured token.
        
        Args:
            provided_token: Token to validate
            
        Returns:
            True if token matches
        """
        if not self.access_token:
            logger.error("No access token configured!")
            return False
        
        # Use secrets.compare_digest to prevent timing attacks
        is_valid = secrets.compare_digest(self.access_token, provided_token)
        
        if not is_valid:
            logger.warning("Token validation failed")
            self.record_auth_failure("token_validation", 401)
        
        return is_valid
    
    def record_auth_failure(
        self,
        endpoint: str,
        error_code: int = 401,
        ip_address: Optional[str] = None
    ) -> None:
        """Record an authentication failure.
        
        Args:
            endpoint: Endpoint where failure occurred
            error_code: HTTP error code
            ip_address: Optional IP address of requester
        """
        failure = AuthFailure(
            timestamp=datetime.now(),
            endpoint=endpoint,
            error_code=error_code,
            ip_address=ip_address
        )
        
        self.auth_failures.append(failure)
        
        logger.warning(
            f"Auth failure recorded: {endpoint} "
            f"(code: {error_code}, total recent: {len(self.auth_failures)})"
        )
        
        # Check for attack pattern
        self.check_for_attacks()
        
        # Audit
        get_privacy_manager().audit_log(
            action="auth_failure",
            resource="security",
            metadata={
                "endpoint": endpoint,
                "error_code": error_code,
                "recent_failures": len(self.auth_failures)
            },
            success=False
        )
    
    def check_for_attacks(self) -> bool:
        """Check if there's a potential security attack in progress.
        
        Returns:
            True if attack pattern detected
        """
        if len(self.auth_failures) < self.max_failures_per_minute:
            return False
        
        # Count failures in last minute
        cutoff = datetime.now() - timedelta(seconds=self.failure_window_seconds)
        recent_failures = [
            f for f in self.auth_failures
            if f.timestamp >= cutoff
        ]
        
        if len(recent_failures) >= self.max_failures_per_minute:
            logger.critical(
                f"SECURITY ALERT: {len(recent_failures)} auth failures "
                f"in last {self.failure_window_seconds}s - Potential attack!"
            )
            
            self.tunnel_compromised = True
            
            # Trigger security alert
            self.trigger_security_alert(
                severity="CRITICAL",
                message=f"Potential Tunnel Compromise - {len(recent_failures)} auth failures detected",
                failures=len(recent_failures)
            )
            
            return True
        
        return False
    
    def trigger_security_alert(
        self,
        severity: str,
        message: str,
        **kwargs
    ) -> None:
        """Trigger a security alert.
        
        Args:
            severity: Alert severity (WARNING, CRITICAL)
            message: Alert message
            **kwargs: Additional context
        """
        try:
            from local_body.core.alerts import AlertManager, AlertSeverity, AlertComponent
            
            alert_mgr = AlertManager.get_instance()
            
            # Map severity string to enum
            sev = AlertSeverity.CRITICAL if severity == "CRITICAL" else AlertSeverity.WARNING
            
            alert_mgr.create_alert(
                component=AlertComponent.SECURITY,
                severity=sev,
                message=message,
                metadata=kwargs
            )
            
            logger.critical(f"Security Alert Triggered: {message}")
            
        except Exception as e:
            logger.error(f"Failed to trigger security alert: {e}")
    
    def reset_tunnel_status(self) -> None:
        """Reset tunnel compromised status (after restart/reauth)."""
        self.tunnel_compromised = False
        self.auth_failures.clear()
        logger.info("Tunnel security status reset")
        
        get_privacy_manager().audit_log(
            action="tunnel_security_reset",
            resource="security"
        )
    
    def should_block_request(self) -> bool:
        """Check if requests should be blocked due to security concerns.
        
        Returns:
            True if requests should be blocked
        """
        return self.tunnel_compromised
    
    def get_security_status(self) -> Dict[str, any]:
        """Get current security status.
        
        Returns:
            Dictionary with security metrics
        """
        recent_cutoff = datetime.now() - timedelta(minutes=5)
        recent_failures = [
            f for f in self.auth_failures
            if f.timestamp >= recent_cutoff
        ]
        
        return {
            "access_token_configured": self.access_token is not None,
            "total_auth_failures": len(self.auth_failures),
            "recent_failures_5min": len(recent_failures),
            "tunnel_compromised": self.tunnel_compromised,
            "blocked_ips": len(self.blocked_ips)
        }
    
    def get_auth_header(self) -> Dict[str, str]:
        """Get authentication header for Colab Brain requests.
        
        Returns:
            Dictionary with X-Sovereign-Token header
            
        Raises:
            ValueError: If access token not configured
        """
        if not self.access_token:
            raise ValueError("Access token not configured. Cannot authenticate to Colab Brain.")
        
        return {
            "X-Sovereign-Token": self.access_token
        }


# Convenience functions
def get_security_manager() -> SecurityManager:
    """Get Security Manager singleton instance."""
    return SecurityManager.get_instance()


def verify_access_token(token: str) -> bool:
    """Verify provided access token.
    
    Args:
        token: Token to verify
        
    Returns:
        True if valid
    """
    return get_security_manager().validate_token(token)


def generate_access_token() -> str:
    """Generate a new access token.
    
    Returns:
        Secure random token
    """
    return get_security_manager().generate_access_token()
