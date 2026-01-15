"""Demo script for HealthMonitor system.

Demonstrates health monitoring, alert management, and system integration.
"""

import asyncio
import time
from loguru import logger
from local_body.core.config_manager import ConfigManager
from local_body.core.health import HealthMonitor
from local_body.core.alerts import AlertSeverity, AlertComponent


def print_separator(title: str = ""):
    """Print a visual separator."""
    if title:
        print(f"\n{'='*70}")
        print(f"  {title}")
        print('='*70)
    else:
        print('-'*70)


async def demo_basic_health_checks():
    """Demo: Basic component health checks."""
    print_separator("DEMO 1: Basic Health Checks")
    
    config = ConfigManager().load_config()
    monitor = HealthMonitor.get_instance(config)
    
    print("\n🔍 Checking individual components...\n")
    
    # Hardware
    print("1. Hardware Health:")
    hw_health = monitor.check_hardware_health()
    status_icon = "✅" if hw_health.healthy else "⚠️"
    print(f"   {status_icon} Status: {hw_health.status}")
    print(f"   Message: {hw_health.message}")
    if hw_health.metadata:
        print(f"   RAM: {hw_health.metadata.get('ram_percent', 0):.1f}%")
        print(f"   CPU: {hw_health.metadata.get('cpu_percent', 0):.1f}%")
    print()
    
    # Internet
    print("2. Internet Connectivity:")
    net_health = monitor.check_internet()
    status_icon = "✅" if net_health.healthy else "⚠️"
    print(f"   {status_icon} Status: {net_health.status}")
    print(f"   Message: {net_health.message}")
    print()
    
    # Database
    print("3. Database (Qdrant):")
    db_health = await monitor.check_database_health()
    status_icon = "✅" if db_health.healthy else "⚠️"
    print(f"   {status_icon} Status: {db_health.status}")
    print(f"   Message: {db_health.message}")
    print()
    
    # Tunnel
    print("4. Tunnel:")
    tunnel_health = await monitor.check_tunnel_latency()
    status_icon = "✅" if tunnel_health.healthy else "ℹ️"
    print(f"   {status_icon} Status: {tunnel_health.status}")
    print(f"   Message: {tunnel_health.message}")
    if tunnel_health.metadata and "latency_ms" in tunnel_health.metadata:
        print(f"   Latency: {tunnel_health.metadata['latency_ms']:.0f}ms")


async def demo_comprehensive_report():
    """Demo: Full system health report."""
    print_separator("DEMO 2: Comprehensive Health Report")
    
    config = ConfigManager().load_config()
    monitor = HealthMonitor.get_instance(config)
    
    print("\n📊 Generating full system health report...\n")
    
    report = await monitor.get_health_report()
    
    # Overall status
    status_icons = {
        "HEALTHY": "✅",
        "DEGRADED": "⚠️",
        "CRITICAL": "🚨"
    }
    icon = status_icons.get(report.overall_status, "❓")
    
    print(f"Overall Status: {icon} {report.overall_status}")
    print(f"Timestamp: {report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Component breakdown
    print("Component Health:")
    for name, component in report.components.items():
        status_icon = "✅" if component.healthy else "⚠️"
        print(f"  {status_icon} {name.capitalize():15} {component.status:10} {component.message}")
    print()
    
    # Alerts
    print(f"Active Alerts: {len(report.active_alerts)}")
    if report.active_alerts:
        for alert in report.active_alerts:
            severity_icon = {
                AlertSeverity.INFO: "ℹ️",
                AlertSeverity.WARNING: "⚠️",
                AlertSeverity.CRITICAL: "🚨"
            }.get(alert.severity, "")
            print(f"  {severity_icon} [{alert.component.value}] {alert.message}")
    print()
    
    # Critical issues
    if report.critical_issues:
        print(f"🚨 Critical Issues ({len(report.critical_issues)}):")
        for issue in report.critical_issues:
            print(f"  - {issue}")
    else:
        print("✅ No critical issues")


async def demo_alert_management():
    """Demo: Alert system features."""
    print_separator("DEMO 3: Alert Management")
    
    config = ConfigManager().load_config()
    monitor = HealthMonitor.get_instance(config)
    
    print("\n📢 Alert System Demonstration\n")
    
    # Clear previous alerts
    monitor.alerts.clear_alerts()
    print("1. Cleared previous alerts")
    
    # Add sample alerts
    print("\n2. Adding sample alerts...")
    monitor.alerts.add_alert(
        AlertSeverity.WARNING,
        AlertComponent.SYSTEM,
        "CPU usage at 75%"
    )
    monitor.alerts.add_alert(
        AlertSeverity.CRITICAL,
        AlertComponent.DATABASE,
        "Connection timeout"
    )
    monitor.alerts.add_alert(
        AlertSeverity.INFO,
        AlertComponent.NETWORK,
        "Latency slightly elevated"
    )
    
    # Show summary
    summary = monitor.get_alert_summary()
    print(f"\n   Total Alerts: {summary['total_alerts']}")
    print(f"   Active: {summary['active_alerts']}")
    print(f"   Critical: {summary['critical_active']}")
    print(f"   Warnings: {summary['warning_active']}")
    print(f"   Info: {summary['info_active']}")
    
    # Show active alerts
    print("\n3. Active Alerts:")
    for alert in monitor.alerts.get_active_alerts():
        severity_badge = alert.severity.value.upper()
        print(f"   [{severity_badge:8}] {alert.component.value:10} {alert.message}")
    
    # Show critical only
    critical = monitor.alerts.get_critical_alerts()
    print(f"\n4. Critical Alerts Only ({len(critical)}):")
    for alert in critical:
        print(f"   🚨 {alert.message}")
    
    # Resolve alerts
    print("\n5. Resolving system alerts...")
    monitor.alerts.resolve_alerts(component=AlertComponent.SYSTEM)
    
    print(f"   Active alerts after resolution: {len(monitor.alerts.get_active_alerts())}")


async def demo_monitoring_cycle():
    """Demo: Continuous monitoring."""
    print_separator("DEMO 4: Continuous Monitoring (5 seconds)")
    
    config = ConfigManager().load_config()
    monitor = HealthMonitor.get_instance(config)
    
    print("\n⏱️  Running health checks every second...\n")
    print("   Time     | Status    | Alerts | RAM%  | Components")
    print("   " + "-" * 65)
    
    for i in range(5):
        report = await monitor.get_health_report()
        
        timestamp = report.timestamp.strftime('%H:%M:%S')
        status = report.overall_status[:8]
        alerts_count = len(report.active_alerts)
        
        # Get RAM from hardware component
        hw = report.components.get("hardware")
        ram_pct = hw.metadata.get("ram_percent", 0) if hw and hw.metadata else 0
        
        # Count healthy components
        healthy_count = sum(1 for c in report.components.values() if c.healthy)
        total_count = len(report.components)
        
        print(f"   {timestamp} | {status:9} | {alerts_count:6} | {ram_pct:5.1f} | {healthy_count}/{total_count}")
        
        if i < 4:
            await asyncio.sleep(1)
    
    print()


async def demo_database_reconnect():
    """Demo: Database reconnection logic."""
    print_separator("DEMO 5: Database Connection Test")
    
    config = ConfigManager().load_config()
    monitor = HealthMonitor.get_instance(config)
    
    print("\n🔌 Testing database connection and reconnection...\n")
    
    # Attempt connection
    print("1. Checking database health...")
    db_health = await monitor.check_database_health()
    
    print(f"   Status: {db_health.status}")
    print(f"   Message: {db_health.message}")
    
    if not db_health.healthy:
        print("\n   ℹ️  Database check failed - this is expected if Qdrant is not running")
        print("   To test full functionality, start Qdrant:")
        print("   docker compose up -d")
    else:
        print("\n   ✅ Database connection healthy")
        
        # Show metadata
        if db_health.metadata:
            print(f"   Host: {db_health.metadata.get('qdrant_host')}")
            print(f"   Port: {db_health.metadata.get('qdrant_port')}")


async def demo_health_status_thresholds():
    """Demo: Show health status thresholds."""
    print_separator("DEMO 6: Health Thresholds & Alerts")
    
    config = ConfigManager().load_config()
    monitor = HealthMonitor.get_instance(config)
    
    print("\n📏 System Health Thresholds:\n")
    
    print("Hardware (RAM):")
    print(f"   Warning:  ≥ {monitor.RAM_WARNING_THRESHOLD}%")
    print(f"   Critical: ≥ {monitor.RAM_CRITICAL_THRESHOLD}%")
    print()
    
    print("Tunnel Latency:")
    print(f"   Warning:  ≥ {monitor.TUNNEL_LATENCY_WARNING:.0f}ms")
    print(f"   Critical: ≥ {monitor.TUNNEL_LATENCY_CRITICAL:.0f}ms")
    print()
    
    print("Current System State:")
    hw_health = monitor.check_hardware_health()
    if hw_health.metadata:
        ram_pct = hw_health.metadata.get("ram_percent", 0)
        print(f"   Current RAM: {ram_pct:.1f}%")
        
        if ram_pct >= monitor.RAM_CRITICAL_THRESHOLD:
            print(f"   ⚠️  Above CRITICAL threshold!")
        elif ram_pct >= monitor.RAM_WARNING_THRESHOLD:
            print(f"   ⚠️  Above WARNING threshold")
        else:
            print(f"   ✅ Within normal range")


async def main():
    """Run all demos."""
    print("\n" + "="*70)
    print("  HEALTH MONITORING SYSTEM DEMONSTRATION")
    print("  Sovereign Doc - Service & Network Health Monitoring")
    print("="*70)
    
    try:
        # Run all demos
        await demo_basic_health_checks()
        await asyncio.sleep(1)
        
        await demo_comprehensive_report()
        await asyncio.sleep(1)
        
        await demo_alert_management()
        await asyncio.sleep(1)
        
        await demo_monitoring_cycle()
        await asyncio.sleep(1)
        
        await demo_database_reconnect()
        await asyncio.sleep(1)
        
        await demo_health_status_thresholds()
        
        # Final summary
        print_separator()
        print("\n✅ All demonstrations completed successfully!")
        print("\nTo integrate into your app:")
        print("   1. Import: from local_body.core.health import HealthMonitor")
        print("   2. Initialize: monitor = HealthMonitor.get_instance(config)")
        print("   3. Check health: report = await monitor.get_health_report()")
        print("   4. Run periodic cycle: await monitor.run_health_check_cycle()")
        print()
    
    except Exception as e:
        logger.error(f"Demo failed: {e}", exc_info=True)
        print(f"\n❌ Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    import sys
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
