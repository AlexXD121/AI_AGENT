"""Alert system for tracking and managing system health alerts.

This module provides a structured approach to managing alerts from various
system components (hardware, services, network).
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict
from loguru import logger


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertComponent(Enum):
    """System components that can generate alerts."""
    SYSTEM = "system"  # Hardware: CPU, RAM, Temperature
    DATABASE = "database"  # Qdrant vector store
    NETWORK = "network"  # Internet and tunnel connectivity
    MODEL = "model"  # AI models (Ollama, Vision)
    STORAGE = "storage"  # Disk space


@dataclass
class Alert:
    """Represents a system alert with metadata.
    
    Attributes:
        severity: Alert severity level
        component: Component that generated the alert
        message: Human-readable alert description
        timestamp: When the alert was created
        alert_id: Unique identifier for the alert
        metadata: Additional context (optional)
        resolved: Whether the alert has been resolved
        resolved_at: When the alert was resolved
    """
    severity: AlertSeverity
    component: AlertComponent
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    alert_id: str = field(default="")
    metadata: Dict = field(default_factory=dict)
    resolved: bool = field(default=False)
    resolved_at: Optional[datetime] = field(default=None)
    
    def __post_init__(self):
        """Generate alert ID if not provided."""
        if not self.alert_id:
            # Create ID from timestamp + component + severity
            self.alert_id = (
                f"{self.component.value}:"
                f"{self.severity.value}:"
                f"{int(self.timestamp.timestamp())}"
            )
    
    def resolve(self):
        """Mark alert as resolved."""
        self.resolved = True
        self.resolved_at = datetime.now()
    
    def __str__(self) -> str:
        """String representation of alert."""
        status = "RESOLVED" if self.resolved else "ACTIVE"
        return (
            f"[{status}] {self.severity.value.upper()} | "
            f"{self.component.value.upper()} | "
            f"{self.message}"
        )


class AlertSystem:
    """Manages system health alerts with persistence and filtering.
    
    Features:
    - Add alerts with automatic deduplication
    - Track active and resolved alerts
    - Filter alerts by component, severity, or status
    - Clear alerts by criteria
    - Auto-resolve duplicate alerts
    
    Usage:
        alerts = AlertSystem()
        alerts.add_alert(
            AlertSeverity.CRITICAL,
            AlertComponent.DATABASE,
            "Qdrant connection failed"
        )
        active = alerts.get_active_alerts()
    """
    
    def __init__(self):
        """Initialize the alert system."""
        self._alerts: List[Alert] = []
        self._max_history = 1000  # Keep last 1000 alerts
        logger.debug("AlertSystem initialized")
    
    def add_alert(
        self,
        severity: AlertSeverity,
        component: AlertComponent,
        message: str,
        metadata: Optional[Dict] = None
    ) -> Alert:
        """Add a new alert to the system.
        
        Automatically deduplicates: if an identical active alert exists,
        it won't be added again.
        
        Args:
            severity: Alert severity level
            component: Component generating the alert
            message: Alert description
            metadata: Optional additional context
            
        Returns:
            Created Alert instance (or existing if duplicate)
        """
        # Check for duplicate active alerts
        existing = self._find_duplicate_active_alert(component, message, severity)
        
        if existing:
            logger.debug(
                f"Duplicate alert not added: {component.value} - {message}"
            )
            return existing
        
        # Create new alert
        alert = Alert(
            severity=severity,
            component=component,
            message=message,
            metadata=metadata or {}
        )
        
        self._alerts.append(alert)
        
        # Log based on severity
        log_msg = f"Alert added: {alert}"
        if severity == AlertSeverity.CRITICAL:
            logger.error(log_msg)
        elif severity == AlertSeverity.WARNING:
            logger.warning(log_msg)
        else:
            logger.info(log_msg)
        
        # Maintain history limit
        if len(self._alerts) > self._max_history:
            # Remove oldest resolved alerts
            self._alerts = [a for a in self._alerts if not a.resolved][-self._max_history:]
        
        return alert
    
    def _find_duplicate_active_alert(
        self,
        component: AlertComponent,
        message: str,
        severity: AlertSeverity
    ) -> Optional[Alert]:
        """Find an existing active alert with same component/message/severity.
        
        Args:
            component: Alert component
            message: Alert message
            severity: Alert severity
            
        Returns:
            Existing alert if found, None otherwise
        """
        for alert in self._alerts:
            if (
                not alert.resolved
                and alert.component == component
                and alert.message == message
                and alert.severity == severity
            ):
                return alert
        return None
    
    def get_active_alerts(
        self,
        component: Optional[AlertComponent] = None,
        severity: Optional[AlertSeverity] = None
    ) -> List[Alert]:
        """Get all active (unresolved) alerts.
        
        Args:
            component: Optional filter by component
            severity: Optional filter by severity
            
        Returns:
            List of active alerts matching criteria
        """
        active = [a for a in self._alerts if not a.resolved]
        
        # Apply filters
        if component:
            active = [a for a in active if a.component == component]
        
        if severity:
            active = [a for a in active if a.severity == severity]
        
        return active
    
    def get_all_alerts(
        self,
        component: Optional[AlertComponent] = None,
        severity: Optional[AlertSeverity] = None,
        resolved: Optional[bool] = None
    ) -> List[Alert]:
        """Get all alerts with optional filtering.
        
        Args:
            component: Optional filter by component
            severity: Optional filter by severity
            resolved: Optional filter by resolution status
            
        Returns:
            List of alerts matching criteria
        """
        alerts = self._alerts.copy()
        
        # Apply filters
        if component:
            alerts = [a for a in alerts if a.component == component]
        
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        
        if resolved is not None:
            alerts = [a for a in alerts if a.resolved == resolved]
        
        return alerts
    
    def resolve_alerts(
        self,
        component: Optional[AlertComponent] = None,
        message_pattern: Optional[str] = None
    ):
        """Resolve alerts matching criteria.
        
        Args:
            component: Resolve all alerts for this component
            message_pattern: Resolve alerts containing this pattern
        """
        resolved_count = 0
        
        for alert in self._alerts:
            if alert.resolved:
                continue
            
            should_resolve = True
            
            if component and alert.component != component:
                should_resolve = False
            
            if message_pattern and message_pattern not in alert.message:
                should_resolve = False
            
            if should_resolve:
                alert.resolve()
                resolved_count += 1
                logger.debug(f"Resolved alert: {alert}")
        
        if resolved_count > 0:
            logger.info(f"Resolved {resolved_count} alert(s)")
    
    def clear_alerts(
        self,
        component: Optional[AlertComponent] = None
    ):
        """Clear (delete) alerts from the system.
        
        Args:
            component: Optional filter - only clear alerts for this component
        """
        if component:
            initial_count = len(self._alerts)
            self._alerts = [a for a in self._alerts if a.component != component]
            cleared = initial_count - len(self._alerts)
            logger.info(f"Cleared {cleared} alert(s) for component {component.value}")
        else:
            cleared = len(self._alerts)
            self._alerts.clear()
            logger.info(f"Cleared all {cleared} alert(s)")
    
    def get_alert_summary(self) -> Dict[str, int]:
        """Get summary statistics of current alerts.
        
        Returns:
            Dictionary with counts by severity and status
        """
        active = self.get_active_alerts()
        
        return {
            "total_alerts": len(self._alerts),
            "active_alerts": len(active),
            "resolved_alerts": len([a for a in self._alerts if a.resolved]),
            "critical_active": len([a for a in active if a.severity == AlertSeverity.CRITICAL]),
            "warning_active": len([a for a in active if a.severity == AlertSeverity.WARNING]),
            "info_active": len([a for a in active if a.severity == AlertSeverity.INFO])
        }
    
    def get_critical_alerts(self) -> List[Alert]:
        """Get all active critical alerts (convenience method).
        
        Returns:
            List of active critical alerts
        """
        return self.get_active_alerts(severity=AlertSeverity.CRITICAL)
    
    def has_critical_alerts(self) -> bool:
        """Check if there are any active critical alerts.
        
        Returns:
            True if any critical alerts are active
        """
        return len(self.get_critical_alerts()) > 0
