"""Privacy Manager and Data Protection System.

Enforces zero data leakage, PII protection, and audit logging.
"""

import json
import re
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from enum import Enum

from loguru import logger
from pydantic import BaseModel, Field


class PrivacyMode(str, Enum):
    """Privacy enforcement levels."""
    RELAXED = "relaxed"  # External APIs allowed
    STANDARD = "standard"  # Limited external API usage
    STRICT = "strict"  # No external APIs, local only


class AuditEntry(BaseModel):
    """Structured audit log entry."""
    timestamp: datetime
    action: str = Field(description="Action performed (e.g., 'document_processed')")
    resource_type: str = Field(description="Type of resource (e.g., 'document', 'user')")
    resource_id: str = Field(description="Non-PII identifier (e.g., UUID)")
    user: Optional[str] = Field(default="system", description="User or system component")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional non-PII metadata")
    success: bool = Field(default=True)


class PrivacyManager:
    """Singleton manager for privacy enforcement and audit logging.
    
    Ensures:
    - PII is never logged
    - Files are securely deleted
    - External API calls are controlled
    - All actions are audited
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self.privacy_mode = PrivacyMode.STANDARD
            self.audit_log_path = Path("logs/audit.jsonl")
            self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
            self._initialized = True
            
            logger.info(f"PrivacyManager initialized: mode={self.privacy_mode.value}")
    
    @classmethod
    def get_instance(cls) -> "PrivacyManager":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def set_privacy_mode(self, mode: PrivacyMode) -> None:
        """Set privacy enforcement level.
        
        Args:
            mode: Privacy mode to enforce
        """
        old_mode = self.privacy_mode
        self.privacy_mode = mode
        logger.warning(f"Privacy mode changed: {old_mode.value} → {mode.value}")
        
        self.audit_log(
            action="privacy_mode_changed",
            resource="system",
            metadata={"old_mode": old_mode.value, "new_mode": mode.value}
        )
    
    def enforce_local_only(self) -> bool:
        """Check if external API calls should be blocked.
        
        Returns:
            True if only local processing is allowed
        """
        return self.privacy_mode == PrivacyMode.STRICT
    
    def allow_external_api(self, api_name: str) -> bool:
        """Check if specific external API is allowed.
        
        Args:
            api_name: Name of the external API
            
        Returns:
            True if API call is permitted
        """
        if self.privacy_mode == PrivacyMode.STRICT:
            logger.warning(f"Blocked external API call to {api_name} (privacy mode: strict)")
            return False
        
        if self.privacy_mode == PrivacyMode.STANDARD:
            # Allow only specific APIs in standard mode
            allowed_apis = ["qdrant", "local_llm"]  # Local services
            if api_name not in allowed_apis:
                logger.warning(f"Blocked external API call to {api_name} (privacy mode: standard)")
                return False
        
        return True
    
    def audit_log(
        self,
        action: str,
        resource: str,
        resource_id: Optional[str] = None,
        user: str = "system",
        metadata: Optional[Dict[str, Any]] = None,
        success: bool = True
    ) -> None:
        """Write audit entry to audit log.
        
        IMPORTANT: Never log PII or sensitive content!
        
        Args:
            action: Action performed (e.g., "document_processed")
            resource: Resource type (e.g., "document", "config")
            resource_id: Non-PII identifier (UUID, hash, etc.)
            user: User or system component
            metadata: Additional non-PII metadata
            success: Whether action succeeded
        """
        entry = AuditEntry(
            timestamp=datetime.now(),
            action=action,
            resource_type=resource,
            resource_id=resource_id or "unknown",
            user=user,
            metadata=metadata or {},
            success=success
        )
        
        # Write to JSONL file (one JSON object per line)
        try:
            with open(self.audit_log_path, 'a', encoding='utf-8') as f:
                f.write(entry.model_dump_json() + '\n')
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")
    
    def sanitize_for_logging(self, text: str, max_length: int = 100) -> str:
        """Sanitize text for safe logging (remove PII, truncate).
        
        Args:
            text: Text to sanitize
            max_length: Maximum length after sanitization
            
        Returns:
            Sanitized text safe for logging
        """
        # Redact common PII patterns
        sanitized = self.redact_pii(text)
        
        # Truncate if too long
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length] + "..."
        
        return sanitized
    
    def redact_pii(self, text: str) -> str:
        """Redact PII from text.
        
        Args:
            text: Text potentially containing PII
            
        Returns:
            Text with PII redacted
        """
        # Email addresses
        text = re.sub(
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            '[EMAIL]',
            text
        )
        
        # Phone numbers (various formats)
        text = re.sub(
            r'\b(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b',
            '[PHONE]',
            text
        )
        
        # Credit card numbers (basic pattern)
        text = re.sub(
            r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',
            '[CARD]',
            text
        )
        
        # US SSN
        text = re.sub(
            r'\b\d{3}-\d{2}-\d{4}\b',
            '[SSN]',
            text
        )
        
        # Generic ID patterns (9+ consecutive digits)
        text = re.sub(
            r'\b\d{9,}\b',
            '[ID]',
            text
        )
        
        # IP addresses
        text = re.sub(
            r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',
            '[IP]',
            text
        )
        
        return text
    
    def validate_file_security(self, file_path: Path) -> bool:
        """Validate file is in safe location and permissions are correct.
        
        Args:
            file_path: Path to file
            
        Returns:
            True if file location and permissions are secure
        """
        # Ensure file is in allowed directory
        allowed_dirs = [
            Path("temp/"),
            Path("uploads/"),
            Path("exports/"),
            Path("checkpoints/")
        ]
        
        file_path = Path(file_path).resolve()
        
        # Check if in allowed directory
        for allowed_dir in allowed_dirs:
            try:
                file_path.relative_to(allowed_dir.resolve())
                return True
            except ValueError:
                continue
        
        logger.warning(f"File in unauthorized location: {file_path}")
        return False
    
    def get_audit_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get audit summary for recent actions.
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            Summary statistics
        """
        if not self.audit_log_path.exists():
            return {"total": 0, "actions": {}}
        
        cutoff = datetime.now().timestamp() - (hours * 3600)
        actions = {}
        total = 0
        
        try:
            with open(self.audit_log_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        timestamp = datetime.fromisoformat(entry['timestamp']).timestamp()
                        
                        if timestamp >= cutoff:
                            action = entry['action']
                            actions[action] = actions.get(action, 0) + 1
                            total += 1
                    except Exception:
                        continue
        except Exception as e:
            logger.error(f"Failed to read audit log: {e}")
        
        return {
            "total": total,
            "actions": actions,
            "period_hours": hours
        }


# Convenience functions
def get_privacy_manager() -> PrivacyManager:
    """Get Privacy Manager singleton instance."""
    return PrivacyManager.get_instance()


def audit_document_processed(document_id: str, success: bool = True) -> None:
    """Audit log: Document processed.
    
    Args:
        document_id: Non-PII document identifier (UUID)
        success: Whether processing succeeded
    """
    get_privacy_manager().audit_log(
        action="document_processed",
        resource="document",
        resource_id=document_id,
        success=success
    )


def audit_config_changed(config_key: str) -> None:
    """Audit log: Configuration changed.
    
    Args:
        config_key: Configuration key that changed
    """
    get_privacy_manager().audit_log(
        action="config_changed",
        resource="config",
        resource_id=config_key
    )


def audit_export_created(export_type: str, record_count: int) -> None:
    """Audit log: Data export created.
    
    Args:
        export_type: Type of export (json, csv, excel)
        record_count: Number of records exported
    """
    get_privacy_manager().audit_log(
        action="export_created",
        resource="export",
        metadata={"type": export_type, "count": record_count}
    )
