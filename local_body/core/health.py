"""Integrated health monitoring system for Sovereign-Doc.

This module provides comprehensive health monitoring across all system components:
- Hardware (CPU, RAM, GPU, Temperature) via SystemMonitor
- Database (Qdrant vector store) with auto-reconnect
- Network (Internet connectivity and tunnel latency)
- Models (Ollama availability)

Integrates with AlertSystem for structured alerting.
"""

import time
import socket
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

import httpx
from loguru import logger

from local_body.core.monitor import SystemMonitor, HealthStatus as HardwareHealthStatus
from local_body.core.alerts import AlertSystem, AlertSeverity, AlertComponent, Alert
from local_body.core.config_manager import SystemConfig


@dataclass
class ComponentHealth:
    """Health status for a single component."""
    name: str
    healthy: bool
    status: str  # "OK", "WARNING", "CRITICAL", "UNKNOWN"
    message: str
    last_check: datetime
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class SystemHealthReport:
    """Complete system health report."""
    timestamp: datetime
    overall_status: str  # "HEALTHY", "DEGRADED", "CRITICAL"
    components: Dict[str, ComponentHealth]
    active_alerts: List[Alert]
    critical_issues: List[str]


class HealthMonitor:
    """Singleton health monitoring system for all components.
    
    Features:
    - Hardware monitoring integration (SystemMonitor)
    - Qdrant database health with auto-reconnect
    - Network connectivity checks (internet + tunnel)
    - Ollama model availability
    - Structured alerting via AlertSystem
    - Comprehensive health reports
    
    Usage:
        monitor = HealthMonitor.get_instance(config)
        report = await monitor.get_health_report()
        
        if report.overall_status == "CRITICAL":
            print("System has critical issues!")
    """
    
    # Thresholds
    RAM_WARNING_THRESHOLD = 85.0  # percent
    RAM_CRITICAL_THRESHOLD = 90.0  # percent (more conservative than SystemMonitor's 95%)
    TUNNEL_LATENCY_WARNING = 1000.0  # ms
    TUNNEL_LATENCY_CRITICAL = 3000.0  # ms
    
    _instance: Optional['HealthMonitor'] = None
    
    def __init__(self, config: SystemConfig):
        """Initialize health monitor (use get_instance() instead).
        
        Args:
            config: SystemConfig instance
        """
        self.config = config
        
        # Get hardware monitor singleton
        self.system_monitor = SystemMonitor.get_instance()
        
        # Initialize alert system
        self.alerts = AlertSystem()
        
        # Lazy-loaded components (initialized on first health check)
        self._vector_store = None
        self._last_full_check: Optional[datetime] = None
        
        # Network check configuration
        self._internet_timeout = 5.0  # seconds
        self._tunnel_timeout = 10.0  # seconds
        
        logger.info("HealthMonitor initialized")
    
    @classmethod
    def get_instance(cls, config: Optional[SystemConfig] = None) -> 'HealthMonitor':
        """Get singleton instance of HealthMonitor.
        
        Args:
            config: SystemConfig (required on first call)
            
        Returns:
            HealthMonitor instance
            
        Raises:
            RuntimeError: If config not provided on first call
        """
        if cls._instance is None:
            if config is None:
                raise RuntimeError("Config required for first HealthMonitor initialization")
            cls._instance = cls(config)
        return cls._instance
    
    # =========================================================================
    # Hardware Health (via SystemMonitor)
    # =========================================================================
    
    def check_hardware_health(self) -> ComponentHealth:
        """Check hardware resource health.
        
        Uses SystemMonitor for CPU, RAM, GPU, and temperature metrics.
        
        Returns:
            ComponentHealth for hardware
        """
        try:
            metrics = self.system_monitor.get_current_metrics()
            
            # Determine status based on metrics
            issues = []
            status = "OK"
            
            # Check RAM
            if metrics.ram_percent >= self.RAM_CRITICAL_THRESHOLD:
                status = "CRITICAL"
                issues.append(f"RAM usage critical: {metrics.ram_percent:.1f}%")
                
                # Add alert
                self.alerts.add_alert(
                    AlertSeverity.CRITICAL,
                    AlertComponent.SYSTEM,
                    f"RAM usage critical: {metrics.ram_percent:.1f}% (threshold: {self.RAM_CRITICAL_THRESHOLD}%)",
                    metadata={"ram_percent": metrics.ram_percent}
                )
            elif metrics.ram_percent >= self.RAM_WARNING_THRESHOLD:
                if status != "CRITICAL":
                    status = "WARNING"
                issues.append(f"RAM usage high: {metrics.ram_percent:.1f}%")
                
                # Add alert
                self.alerts.add_alert(
                    AlertSeverity.WARNING,
                    AlertComponent.SYSTEM,
                    f"RAM usage high: {metrics.ram_percent:.1f}% (threshold: {self.RAM_WARNING_THRESHOLD}%)",
                    metadata={"ram_percent": metrics.ram_percent}
                )
            
            # Check temperature
            if metrics.cpu_temperature_c and metrics.cpu_temperature_c >= 80.0:
                status = "CRITICAL"
                issues.append(f"CPU temperature critical: {metrics.cpu_temperature_c:.1f}°C")
                
                self.alerts.add_alert(
                    AlertSeverity.CRITICAL,
                    AlertComponent.SYSTEM,
                    f"CPU overheating: {metrics.cpu_temperature_c:.1f}°C",
                    metadata={"temperature_c": metrics.cpu_temperature_c}
                )
            
            # Check cool-down mode
            if self.system_monitor.is_cooldown_active:
                status = "WARNING"
                issues.append("System in thermal cool-down mode")
                
                self.alerts.add_alert(
                    AlertSeverity.WARNING,
                    AlertComponent.SYSTEM,
                    "System in cool-down mode due to high temperature"
                )
            
            # If no issues, resolve previous alerts
            if not issues:
                self.alerts.resolve_alerts(component=AlertComponent.SYSTEM)
            
            message = "; ".join(issues) if issues else "All hardware resources normal"
            
            return ComponentHealth(
                name="Hardware",
                healthy=(status == "OK"),
                status=status,
                message=message,
                last_check=datetime.now(),
                metadata={
                    "cpu_percent": metrics.cpu_percent,
                    "ram_percent": metrics.ram_percent,
                    "ram_used_gb": metrics.ram_used_gb,
                    "ram_total_gb": metrics.ram_total_gb,
                    "temperature_c": metrics.cpu_temperature_c,
                    "cooldown_active": self.system_monitor.is_cooldown_active
                }
            )
        
        except Exception as e:
            logger.error(f"Hardware health check failed: {e}")
            return ComponentHealth(
                name="Hardware",
                healthy=False,
                status="UNKNOWN",
                message=f"Health check failed: {str(e)}",
                last_check=datetime.now()
            )
    
    # =========================================================================
    # Database Health (Qdrant)
    # =========================================================================
    
    async def check_database_health(self) -> ComponentHealth:
        """Check Qdrant vector database health with auto-reconnect.
        
        Performs lightweight connection test (get collections).
        On failure, attempts to reconnect with exponential backoff (3 retries).
        
        Returns:
            ComponentHealth for database
        """
        try:
            # Lazy-load vector store
            if self._vector_store is None:
                logger.debug("Initializing DocumentVectorStore for health check")
                from local_body.database.vector_store import DocumentVectorStore
                self._vector_store = DocumentVectorStore(self.config)
            
            # Attempt health check
            is_healthy = await self._check_qdrant_connection()
            
            if is_healthy:
                # Resolve previous database alerts
                self.alerts.resolve_alerts(component=AlertComponent.DATABASE)
                
                return ComponentHealth(
                    name="Database",
                    healthy=True,
                    status="OK",
                    message="Qdrant connection healthy",
                    last_check=datetime.now(),
                    metadata={
                        "qdrant_host": self.config.qdrant_host,
                        "qdrant_port": self.config.qdrant_port,
                        "collection": self.config.vector_collection
                    }
                )
            
            # Connection failed - attempt reconnection
            logger.warning("Qdrant connection unhealthy, attempting reconnection...")
            
            reconnect_success = await self._attempt_database_reconnect()
            
            if reconnect_success:
                logger.info("✓ Qdrant reconnection successful")
                
                # Resolve alerts
                self.alerts.resolve_alerts(component=AlertComponent.DATABASE)
                
                return ComponentHealth(
                    name="Database",
                    healthy=True,
                    status="OK",
                    message="Qdrant reconnected successfully",
                    last_check=datetime.now(),
                    metadata={"reconnected": True}
                )
            else:
                logger.error("✗ Qdrant reconnection failed after 3 attempts")
                
                # Add critical alert
                self.alerts.add_alert(
                    AlertSeverity.CRITICAL,
                    AlertComponent.DATABASE,
                    "Qdrant database unreachable after reconnection attempts"
                )
                
                return ComponentHealth(
                    name="Database",
                    healthy=False,
                    status="CRITICAL",
                    message="Qdrant database unreachable",
                    last_check=datetime.now(),
                    metadata={
                        "reconnect_attempts": 3,
                        "reconnect_failed": True
                    }
                )
        
        except Exception as e:
            logger.error(f"Database health check error: {e}")
            
            self.alerts.add_alert(
                AlertSeverity.CRITICAL,
                AlertComponent.DATABASE,
                f"Database health check failed: {str(e)}"
            )
            
            return ComponentHealth(
                name="Database",
                healthy=False,
                status="UNKNOWN",
                message=f"Health check error: {str(e)}",
                last_check=datetime.now()
            )
    
    async def _check_qdrant_connection(self) -> bool:
        """Lightweight Qdrant connection test.
        
        Returns:
            True if connection is healthy
        """
        try:
            # Use the check_health method from vector_store
            if hasattr(self._vector_store, 'check_health'):
                return await self._vector_store.check_health()
            else:
                # Fallback: try to get collections
                await self._vector_store.client.get_collections()
                return True
        except Exception as e:
            logger.debug(f"Qdrant connection test failed: {e}")
            return False
    
    async def _attempt_database_reconnect(self) -> bool:
        """Attempt to reconnect to Qdrant with exponential backoff.
        
        Retries: 3 attempts with delays of 1s, 2s, 4s
        
        Returns:
            True if reconnection successful
        """
        from local_body.database.vector_store import DocumentVectorStore
        
        max_retries = 3
        base_delay = 1.0  # seconds
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"Reconnection attempt {attempt}/{max_retries}")
                
                # Re-initialize vector store (creates new client)
                self._vector_store = DocumentVectorStore(self.config)
                
                # Test connection
                is_healthy = await self._check_qdrant_connection()
                
                if is_healthy:
                    logger.success(f"Reconnection successful on attempt {attempt}")
                    return True
                
                # Wait with exponential backoff
                if attempt < max_retries:
                    delay = base_delay * (2 ** (attempt - 1))
                    logger.debug(f"Waiting {delay}s before retry...")
                    await asyncio.sleep(delay)
            
            except Exception as e:
                logger.error(f"Reconnection attempt {attempt} failed: {e}")
                
                if attempt < max_retries:
                    delay = base_delay * (2 ** (attempt - 1))
                    await asyncio.sleep(delay)
        
        return False
    
    # =========================================================================
    # Network Health
    # =========================================================================
    
    def check_internet(self) -> ComponentHealth:
        """Check internet connectivity by pinging a reliable host.
        
        Pings 8.8.8.8 (Google DNS) as a connectivity indicator.
        
        Returns:
            ComponentHealth for internet
        """
        try:
            # Try to connect to Google DNS
            socket.setdefaulttimeout(self._internet_timeout)
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
            
            # Resolve previous network alerts
            self.alerts.resolve_alerts(
                component=AlertComponent.NETWORK,
                message_pattern="Internet connectivity"
            )
            
            return ComponentHealth(
                name="Internet",
                healthy=True,
                status="OK",
                message="Internet connectivity available",
                last_check=datetime.now()
            )
        
        except (socket.timeout, socket.error) as e:
            logger.warning(f"Internet connectivity check failed: {e}")
            
            # Add warning alert (not critical - can work offline)
            self.alerts.add_alert(
                AlertSeverity.WARNING,
                AlertComponent.NETWORK,
                "Internet connectivity unavailable - operating in offline mode"
            )
            
            return ComponentHealth(
                name="Internet",
                healthy=False,
                status="WARNING",
                message="No internet connection (offline mode)",
                last_check=datetime.now()
            )
        
        except Exception as e:
            logger.error(f"Internet check error: {e}")
            return ComponentHealth(
                name="Internet",
                healthy=False,
                status="UNKNOWN",
                message=f"Check error: {str(e)}",
                last_check=datetime.now()
            )
    
    async def check_tunnel_latency(self, tunnel_url: Optional[str] = None) -> ComponentHealth:
        """Measure HTTP latency to tunnel endpoint.
        
        Performs HTTP HEAD request to measure round-trip time.
        
        Args:
            tunnel_url: Optional tunnel URL (uses config.ngrok_url if not provided)
            
        Returns:
            ComponentHealth for tunnel
        """
        url = tunnel_url or self.config.ngrok_url
        
        if not url:
            return ComponentHealth(
                name="Tunnel",
                healthy=True,
                status="OK",
                message="No tunnel configured (not required)",
                last_check=datetime.now()
            )
        
        try:
            async with httpx.AsyncClient(timeout=self._tunnel_timeout) as client:
                start_time = time.perf_counter()
                response = await client.head(url)
                latency_ms = (time.perf_counter() - start_time) * 1000
                
                # Determine status based on latency
                if latency_ms >= self.TUNNEL_LATENCY_CRITICAL:
                    status = "CRITICAL"
                    message = f"Tunnel latency critical: {latency_ms:.0f}ms"
                    
                    self.alerts.add_alert(
                        AlertSeverity.CRITICAL,
                        AlertComponent.NETWORK,
                        message,
                        metadata={"latency_ms": latency_ms, "url": url}
                    )
                    
                elif latency_ms >= self.TUNNEL_LATENCY_WARNING:
                    status = "WARNING"
                    message = f"Tunnel latency high: {latency_ms:.0f}ms"
                    
                    self.alerts.add_alert(
                        AlertSeverity.WARNING,
                        AlertComponent.NETWORK,
                        message,
                        metadata={"latency_ms": latency_ms, "url": url}
                    )
                else:
                    status = "OK"
                    message = f"Tunnel healthy (latency: {latency_ms:.0f}ms)"
                    
                    # Resolve previous tunnel alerts
                    self.alerts.resolve_alerts(
                        component=AlertComponent.NETWORK,
                        message_pattern="Tunnel latency"
                    )
                
                return ComponentHealth(
                    name="Tunnel",
                    healthy=(status == "OK"),
                    status=status,
                    message=message,
                    last_check=datetime.now(),
                    metadata={
                        "latency_ms": latency_ms,
                        "url": url,
                        "status_code": response.status_code
                    }
                )
        
        except httpx.TimeoutException:
            logger.error(f"Tunnel check timeout: {url}")
            
            self.alerts.add_alert(
                AlertSeverity.CRITICAL,
                AlertComponent.NETWORK,
                "Tunnel connection timeout"
            )
            
            return ComponentHealth(
                name="Tunnel",
                healthy=False,
                status="CRITICAL",
                message="Tunnel connection timeout",
                last_check=datetime.now()
            )
        
        except Exception as e:
            logger.error(f"Tunnel check error: {e}")
            
            self.alerts.add_alert(
                AlertSeverity.WARNING,
                AlertComponent.NETWORK,
                f"Tunnel check failed: {str(e)}"
            )
            
            return ComponentHealth(
                name="Tunnel",
                healthy=False,
                status="WARNING",
                message=f"Tunnel check error: {str(e)}",
                last_check=datetime.now()
            )
    
    # =========================================================================
    # Comprehensive Health Report
    # =========================================================================
    
    async def get_health_report(self) -> SystemHealthReport:
        """Generate comprehensive system health report.
        
        Checks all components:
        - Hardware (CPU, RAM, temp)
        - Database (Qdrant)
        - Network (Internet, tunnel)
        
        Returns:
            SystemHealthReport with all component statuses
        """
        logger.debug("Generating system health report...")
        
        components = {}
        
        # Check hardware (synchronous)
        components["hardware"] = self.check_hardware_health()
        
        # Check database (async)
        components["database"] = await self.check_database_health()
        
        # Check network (mixed)
        components["internet"] = self.check_internet()
        components["tunnel"] = await self.check_tunnel_latency()
        
        # Determine overall status
        overall_status = self._calculate_overall_status(components)
        
        # Get active alerts
        active_alerts = self.alerts.get_active_alerts()
        
        # Extract critical issues
        critical_issues = []
        for alert in active_alerts:
            if alert.severity == AlertSeverity.CRITICAL:
                critical_issues.append(f"{alert.component.value}: {alert.message}")
        
        # Create report
        report = SystemHealthReport(
            timestamp=datetime.now(),
            overall_status=overall_status,
            components=components,
            active_alerts=active_alerts,
            critical_issues=critical_issues
        )
        
        # Log summary
        logger.info(
            f"Health Report: {overall_status} | "
            f"{len(active_alerts)} active alerts | "
            f"{len(critical_issues)} critical issues"
        )
        
        self._last_full_check = datetime.now()
        
        return report
    
    def _calculate_overall_status(self, components: Dict[str, ComponentHealth]) -> str:
        """Calculate overall system status from component statuses.
        
        Logic:
        - CRITICAL if any component is CRITICAL
        - DEGRADED if any component is WARNING or unhealthy
        - HEALTHY if all components are OK
        
        Args:
            components: Dictionary of component health statuses
            
        Returns:
            Overall status string
        """
        # Check for critical
        for component in components.values():
            if component.status == "CRITICAL":
                return "CRITICAL"
        
        # Check for degraded
        for component in components.values():
            if component.status in ("WARNING", "UNKNOWN") or not component.healthy:
                return "DEGRADED"
        
        return "HEALTHY"
    
    # =========================================================================
    # Convenience Methods
    # =========================================================================
    
    async def is_system_healthy(self) -> bool:
        """Quick check if system is overall healthy.
        
        Returns:
            True if no critical issues
        """
        report = await self.get_health_report()
        return report.overall_status != "CRITICAL"
    
    def get_alert_summary(self) -> Dict[str, int]:
        """Get alert statistics.
        
        Returns:
            Dictionary with alert counts
        """
        return self.alerts.get_alert_summary()
    
    async def run_health_check_cycle(self):
        """Run a complete health check cycle.
        
        This should be called periodically (e.g., every 30-60 seconds) to:
        - Update component health statuses
        - Generate/resolve alerts
        - Log health summary
        """
        report = await self.get_health_report()
        
        # Log summary based on status
        if report.overall_status == "CRITICAL":
            logger.error(
                f"🚨 System Status: CRITICAL | "
                f"Critical Issues: {', '.join(report.critical_issues)}"
            )
        elif report.overall_status == "DEGRADED":
            logger.warning(
                f"⚠️ System Status: DEGRADED | "
                f"Active Alerts: {len(report.active_alerts)}"
            )
        else:
            logger.debug(f"✓ System Status: HEALTHY")
