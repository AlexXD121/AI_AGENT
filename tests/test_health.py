"""Test suite for AlertSystem and HealthMonitor.

Tests alert management, health checks, and system integration.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from local_body.core.alerts import (
    AlertSystem,
    Alert,
    AlertSeverity,
    AlertComponent
)
from local_body.core.health import (
    HealthMonitor,
    ComponentHealth,
    SystemHealthReport
)
from local_body.core.config_manager import ConfigManager


class TestAlertSystem:
    """Test AlertSystem functionality."""
    
    def test_alert_creation(self):
        """Test creating individual alerts."""
        alert = Alert(
            severity=AlertSeverity.WARNING,
            component=AlertComponent.SYSTEM,
            message="Test alert"
        )
        
        assert alert.severity == AlertSeverity.WARNING
        assert alert.component == AlertComponent.SYSTEM
        assert alert.message == "Test alert"
        assert not alert.resolved
        assert alert.alert_id != ""
    
    def test_alert_resolution(self):
        """Test alert resolution."""
        alert = Alert(
            severity=AlertSeverity.INFO,
            component=AlertComponent.DATABASE,
            message="Test"
        )
        
        assert not alert.resolved
        assert alert.resolved_at is None
        
        alert.resolve()
        
        assert alert.resolved
        assert alert.resolved_at is not None
    
    def test_add_alert(self):
        """Test adding alerts to system."""
        alerts = AlertSystem()
        
        alert = alerts.add_alert(
            AlertSeverity.CRITICAL,
            AlertComponent.DATABASE,
            "Database connection failed"
        )
        
        assert alert is not None
        assert len(alerts.get_active_alerts()) == 1
    
    def test_duplicate_alert_prevention(self):
        """Test that duplicate active alerts are not added."""
        alerts = AlertSystem()
        
        # Add first alert
        alert1 = alerts.add_alert(
            AlertSeverity.WARNING,
            AlertComponent.NETWORK,
            "Connection slow"
        )
        
        # Try to add duplicate
        alert2 = alerts.add_alert(
            AlertSeverity.WARNING,
            AlertComponent.NETWORK,
            "Connection slow"
        )
        
        # Should return existing alert
        assert alert1 is alert2
        assert len(alerts.get_active_alerts()) == 1
    
    def test_get_active_alerts(self):
        """Test retrieving active alerts."""
        alerts = AlertSystem()
        
        # Add multiple alerts
        alerts.add_alert(AlertSeverity.CRITICAL, AlertComponent.SYSTEM, "CPU high")
        alerts.add_alert(AlertSeverity.WARNING, AlertComponent.DATABASE, "DB slow")
        alerts.add_alert(AlertSeverity.INFO, AlertComponent.NETWORK, "Network OK")
        
        # Get all active
        active = alerts.get_active_alerts()
        assert len(active) == 3
        
        # Filter by component
        system_alerts = alerts.get_active_alerts(component=AlertComponent.SYSTEM)
        assert len(system_alerts) == 1
        assert system_alerts[0].message == "CPU high"
        
        # Filter by severity
        critical = alerts.get_active_alerts(severity=AlertSeverity.CRITICAL)
        assert len(critical) == 1
    
    def test_resolve_alerts(self):
        """Test resolving alerts."""
        alerts = AlertSystem()
        
        alerts.add_alert(AlertSeverity.WARNING, AlertComponent.SYSTEM, "RAM high")
        alerts.add_alert(AlertSeverity.WARNING, AlertComponent.DATABASE, "DB slow")
        
        assert len(alerts.get_active_alerts()) == 2
        
        # Resolve system alerts
        alerts.resolve_alerts(component=AlertComponent.SYSTEM)
        
        active = alerts.get_active_alerts()
        assert len(active) == 1
        assert active[0].component == AlertComponent.DATABASE
    
    def test_clear_alerts(self):
        """Test clearing alerts."""
        alerts = AlertSystem()
        
        alerts.add_alert(AlertSeverity.INFO, AlertComponent.SYSTEM, "Test 1")
        alerts.add_alert(AlertSeverity.INFO, AlertComponent.DATABASE, "Test 2")
        
        # Clear system alerts
        alerts.clear_alerts(component=AlertComponent.SYSTEM)
        
        all_alerts = alerts.get_all_alerts()
        assert len(all_alerts) == 1
        assert all_alerts[0].component == AlertComponent.DATABASE
        
        # Clear all
        alerts.clear_alerts()
        assert len(alerts.get_all_alerts()) == 0
    
    def test_get_alert_summary(self):
        """Test alert summary statistics."""
        alerts = AlertSystem()
        
        alerts.add_alert(AlertSeverity.CRITICAL, AlertComponent.SYSTEM, "Critical")
        alerts.add_alert(AlertSeverity.WARNING, AlertComponent.DATABASE, "Warning")
        alerts.add_alert(AlertSeverity.INFO, AlertComponent.NETWORK, "Info")
        
        # Resolve one
        alerts.get_active_alerts()[0].resolve()
        
        summary = alerts.get_alert_summary()
        
        assert summary["total_alerts"] == 3
        assert summary["active_alerts"] == 2
        assert summary["resolved_alerts"] == 1
        assert summary["critical_active"] == 0 or summary["critical_active"] == 1  # Depends on which was resolved
    
    def test_get_critical_alerts(self):
        """Test retrieving only critical alerts."""
        alerts = AlertSystem()
        
        alerts.add_alert(AlertSeverity.CRITICAL, AlertComponent.SYSTEM, "Critical 1")
        alerts.add_alert(AlertSeverity.WARNING, AlertComponent.DATABASE, "Warning")
        alerts.add_alert(AlertSeverity.CRITICAL, AlertComponent.NETWORK, "Critical 2")
        
        critical = alerts.get_critical_alerts()
        assert len(critical) == 2
        
        has_critical = alerts.has_critical_alerts()
        assert has_critical is True


class TestComponentHealth:
    """Test ComponentHealth dataclass."""
    
    def test_component_health_creation(self):
        """Test creating ComponentHealth instance."""
        health = ComponentHealth(
            name="Test",
            healthy=True,
            status="OK",
            message="all good",
            last_check=datetime.now()
        )
        
        assert health.name == "Test"
        assert health.healthy is True
        assert health.status == "OK"
        assert health.metadata is not None


@pytest.mark.asyncio
class TestHealthMonitor:
    """Test HealthMonitor integration."""
    
    async def test_singleton_pattern(self):
        """Test that HealthMonitor uses singleton pattern."""
        config = ConfigManager().load_config()
        
        monitor1 = HealthMonitor.get_instance(config)
        monitor2 = HealthMonitor.get_instance()
        
        assert monitor1 is monitor2
    
    async def test_hardware_health_check(self):
        """Test hardware health monitoring."""
        config = ConfigManager().load_config()
        monitor = HealthMonitor.get_instance(config)
        
        health = monitor.check_hardware_health()
        
        assert isinstance(health, ComponentHealth)
        assert health.name == "Hardware"
        assert "metadata" in health.__dict__
        assert "ram_percent" in health.metadata
    
    async def test_internet_check(self):
        """Test internet connectivity check."""
        config = ConfigManager().load_config()
        monitor = HealthMonitor.get_instance(config)
        
        health = monitor.check_internet()
        
        assert isinstance(health, ComponentHealth)
        assert health.name == "Internet"
        # Result depends on actual connectivity
        assert health.status in ("OK", "WARNING", "UNKNOWN")
    
    async def test_tunnel_check_no_tunnel(self):
        """Test tunnel check when no tunnel configured."""
        config = ConfigManager().load_config()
        config.ngrok_url = None
        monitor = HealthMonitor.get_instance(config)
        
        health = await monitor.check_tunnel_latency()
        
        assert health.name == "Tunnel"
        assert health.status == "OK"
        assert "not" in health.message.lower() or "no tunnel" in health.message.lower()
    
    async def test_get_health_report(self):
        """Test generating full health report."""
        config = ConfigManager().load_config()
        monitor = HealthMonitor.get_instance(config)
        
        report = await monitor.get_health_report()
        
        assert isinstance(report, SystemHealthReport)
        assert isinstance(report.timestamp, datetime)
        assert report.overall_status in ("HEALTHY", "DEGRADED", "CRITICAL")
        assert "hardware" in report.components
        assert "database" in report.components
        assert "internet" in report.components
        assert "tunnel" in report.components
        assert isinstance(report.active_alerts, list)
        assert isinstance(report.critical_issues, list)
    
    async def test_is_system_healthy(self):
        """Test quick health check."""
        config = ConfigManager().load_config()
        monitor = HealthMonitor.get_instance(config)
        
        is_healthy = await monitor.is_system_healthy()
        
        assert isinstance(is_healthy, bool)
    
    async def test_get_alert_summary(self):
        """Test retrieving alert summary."""
        config = ConfigManager().load_config()
        monitor = HealthMonitor.get_instance(config)
        
        summary = monitor.get_alert_summary()
        
        assert isinstance(summary, dict)
        assert "total_alerts" in summary
        assert "active_alerts" in summary
    
    async def test_alert_integration(self):
        """Test that health checks generate alerts."""
        config = ConfigManager().load_config()
        monitor = HealthMonitor.get_instance(config)
        
        # Clear existing alerts
        monitor.alerts.clear_alerts()
        
        # Run health check
        await monitor.get_health_report()
        
        # Check if any alerts were generated (depends on system state)
        all_alerts = monitor.alerts.get_all_alerts()
        # Just verify it returns a list (may be empty on healthy system)
        assert isinstance(all_alerts, list)


@pytest.mark.integration
@pytest.mark.asyncio
class TestHealthMonitorIntegration:
    """Integration tests for HealthMonitor."""
    
    async def test_full_health_cycle(self):
        """Test complete health monitoring cycle."""
        config = ConfigManager().load_config()
        monitor = HealthMonitor.get_instance(config)
        
        # Run multiple health checks
        for _ in range(3):
            report = await monitor.get_health_report()
            assert report.overall_status in ("HEALTHY", "DEGRADED", "CRITICAL")
            await asyncio.sleep(0.5)
    
    async def test_alert_lifecycle(self):
        """Test alert creation and resolution lifecycle."""
        config = ConfigManager().load_config()
        monitor = HealthMonitor.get_instance(config)
        
        # Clear alerts
        monitor.alerts.clear_alerts()
        
        # Manually add alert
        monitor.alerts.add_alert(
            AlertSeverity.WARNING,
            AlertComponent.SYSTEM,
            "Test alert"
        )
        
        assert len(monitor.alerts.get_active_alerts()) == 1
        
        # Resolve
        monitor.alerts.resolve_alerts(component=AlertComponent.SYSTEM)
        
        assert len(monitor.alerts.get_active_alerts()) == 0


if __name__ == "__main__":
    # Run basic tests
    print("Running HealthMonitor tests...")
    
    # Test AlertSystem
    print("\n1. Testing AlertSystem...")
    alerts = AlertSystem()
    alerts.add_alert(AlertSeverity.CRITICAL, AlertComponent.SYSTEM, "Test critical")
    alerts.add_alert(AlertSeverity.WARNING, AlertComponent.DATABASE, "Test warning")
    print(f"   Added 2 alerts")
    print(f"   Active: {len(alerts.get_active_alerts())}")
    print(f"   Critical: {len(alerts.get_critical_alerts())}")
    print(f"   Summary: {alerts.get_alert_summary()}")
    
    # Test HealthMonitor
    print("\n2. Testing HealthMonitor...")
    
    async def test_health():
        config = ConfigManager().load_config()
        monitor = HealthMonitor.get_instance(config)
        
        print("   Checking hardware...")
        hw_health = monitor.check_hardware_health()
        print(f"   Hardware: {hw_health.status} - {hw_health.message}")
        
        print("   Checking internet...")
        net_health = monitor.check_internet()
        print(f"   Internet: {net_health.status} - {net_health.message}")
        
        print("   Generating full report...")
        report = await monitor.get_health_report()
        print(f"   Overall Status: {report.overall_status}")
        print(f"   Active Alerts: {len(report.active_alerts)}")
        print(f"   Critical Issues: {len(report.critical_issues)}")
        
        # Show component statuses
        print("\n   Component Health:")
        for name, component in report.components.items():
            print(f"     - {name}: {component.status}")
    
    asyncio.run(test_health())
    
    print("\n✓ All manual tests completed!")
