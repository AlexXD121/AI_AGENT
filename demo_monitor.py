"""Quick demo of SystemMonitor functionality.

Run this script to see the monitor in action:
    python demo_monitor.py
"""

import time
from loguru import logger
from local_body.core.monitor import SystemMonitor, HealthStatus


def print_separator(title: str = ""):
    """Print a visual separator."""
    if title:
        print(f"\n{'='*60}")
        print(f"  {title}")
        print('='*60)
    else:
        print('-'*60)


def demo_basic_metrics():
    """Demo: Basic system metrics."""
    print_separator("DEMO 1: Basic System Metrics")
    
    monitor = SystemMonitor.get_instance()
    metrics = monitor.get_current_metrics()
    
    print(f"\n📊 Current System Status")
    print(f"   Timestamp: {metrics.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Health Status: {metrics.health_status.value.upper()}")
    print()
    
    # CPU
    print(f"🔧 CPU")
    print(f"   Usage: {metrics.cpu_percent:.1f}%")
    print(f"   Cores: {metrics.cpu_count}")
    if metrics.cpu_temperature_c:
        temp_icon = "🔥" if metrics.cpu_temperature_c > 70 else "❄️"
        print(f"   Temperature: {temp_icon} {metrics.cpu_temperature_c:.1f}°C")
    else:
        print(f"   Temperature: Not available")
    print()
    
    # RAM
    print(f"💾 Memory")
    print(f"   Total: {metrics.ram_total_gb:.1f} GB")
    print(f"   Used: {metrics.ram_used_gb:.1f} GB")
    print(f"   Available: {metrics.ram_available_gb:.1f} GB")
    print(f"   Usage: {metrics.ram_percent:.1f}%")
    
    # Visual bar
    bar_length = 40
    filled = int((metrics.ram_percent / 100) * bar_length)
    bar = '█' * filled + '░' * (bar_length - filled)
    print(f"   [{bar}] {metrics.ram_percent:.0f}%")
    print()
    
    # GPU
    if metrics.gpu_available:
        print(f"🎮 GPU")
        if metrics.gpu_vram_used_mb and metrics.gpu_vram_total_mb:
            vram_percent = (metrics.gpu_vram_used_mb / metrics.gpu_vram_total_mb) * 100
            print(f"   VRAM: {metrics.gpu_vram_used_mb:.0f}MB / {metrics.gpu_vram_total_mb:.0f}MB ({vram_percent:.0f}%)")
        
        if metrics.gpu_temperature_c:
            print(f"   Temperature: {metrics.gpu_temperature_c:.0f}°C")
        
        if metrics.gpu_utilization_percent:
            print(f"   Utilization: {metrics.gpu_utilization_percent:.0f}%")
    else:
        print(f"🎮 GPU: Not detected or not available")


def demo_streaming_decision():
    """Demo: Streaming mode decision logic."""
    print_separator("DEMO 2: Streaming Mode Decision")
    
    monitor = SystemMonitor.get_instance()
    
    test_cases = [
        (10, 5, "Small PDF"),
        (30, 15, "Medium PDF"),
        (75, 30, "Large PDF"),
        (120, 50, "Very Large PDF"),
    ]
    
    print("\n📄 Document Processing Mode Recommendations:\n")
    
    for file_size_mb, page_count, description in test_cases:
        should_stream = monitor.should_use_streaming(file_size_mb, page_count)
        mode = "🌊 STREAMING" if should_stream else "📖 NORMAL"
        
        print(f"   {description:20} ({file_size_mb:3}MB, {page_count:2} pages) → {mode}")


def demo_health_monitoring():
    """Demo: Health status monitoring."""
    print_separator("DEMO 3: Health Status Monitoring")
    
    monitor = SystemMonitor.get_instance()
    
    print("\n🏥 Health Status Thresholds:")
    print(f"   RAM Warning: {monitor.RAM_WARNING_THRESHOLD}%")
    print(f"   RAM Critical: {monitor.RAM_CRITICAL_THRESHOLD}%")
    print(f"   Temperature Critical: {monitor.TEMP_CRITICAL}°C")
    print(f"   Cool-down Exit Temp: {monitor.TEMP_COOLDOWN_EXIT}°C")
    print()
    
    # Current health
    health = monitor.check_health()
    
    health_icons = {
        HealthStatus.OK: "✅",
        HealthStatus.WARNING: "⚠️",
        HealthStatus.CRITICAL: "🚨"
    }
    
    icon = health_icons[health]
    print(f"   Current Health: {icon} {health.value.upper()}")
    
    # Can process?
    can_process = monitor.can_process_new_task()
    status_icon = "✓" if can_process else "✗"
    print(f"   Can Process Tasks: {status_icon} {'YES' if can_process else 'NO (Cool-down active)'}")


def demo_memory_cleanup():
    """Demo: Memory cleanup."""
    print_separator("DEMO 4: Memory Cleanup")
    
    monitor = SystemMonitor.get_instance()
    
    # Get metrics before
    before_metrics = monitor.get_current_metrics()
    print(f"\n🧹 Memory Status:")
    print(f"   Before Cleanup: {before_metrics.ram_used_gb:.2f} GB ({before_metrics.ram_percent:.1f}%)")
    
    # Perform cleanup
    print("\n   Performing cleanup...")
    success = monitor.attempt_memory_cleanup(force=True)
    
    if success:
        print("   ✓ Cleanup executed")
        
        # Get metrics after
        time.sleep(0.5)  # Give system time to update
        after_metrics = monitor.get_current_metrics()
        
        freed_mb = (before_metrics.ram_used_gb - after_metrics.ram_used_gb) * 1024
        freed_percent = before_metrics.ram_percent - after_metrics.ram_percent
        
        print(f"   After Cleanup: {after_metrics.ram_used_gb:.2f} GB ({after_metrics.ram_percent:.1f}%)")
        print(f"   Freed: {freed_mb:+.0f} MB ({freed_percent:+.1f}%)")
    else:
        print("   ⏭️  Cleanup skipped (cooldown period)")


def demo_continuous_monitoring():
    """Demo: Continuous monitoring over time."""
    print_separator("DEMO 5: Continuous Monitoring (5 seconds)")
    
    monitor = SystemMonitor.get_instance()
    
    print("\n⏱️  Monitoring system for 5 seconds...\n")
    print("   Timestamp           CPU%    RAM%    Temp°C  Status")
    print("   " + "-" * 60)
    
    for i in range(5):
        metrics = monitor.get_current_metrics()
        
        timestamp = metrics.timestamp.strftime('%H:%M:%S')
        cpu = f"{metrics.cpu_percent:5.1f}"
        ram = f"{metrics.ram_percent:5.1f}"
        temp = f"{metrics.cpu_temperature_c:6.1f}" if metrics.cpu_temperature_c else "  N/A "
        status = metrics.health_status.value[:4].upper()
        
        print(f"   {timestamp}           {cpu}   {ram}   {temp}   {status}")
        
        if i < 4:  # Don't sleep on last iteration
            time.sleep(1)
    
    print()


def demo_health_check_cycle():
    """Demo: Full health check cycle."""
    print_separator("DEMO 6: Health Check Cycle")
    
    monitor = SystemMonitor.get_instance()
    
    print("\n🔄 Running health check cycle...")
    print("   (Checks memory, temperature, triggers cleanup if needed)")
    print()
    
    monitor.run_health_check_cycle()
    
    metrics = monitor.get_current_metrics()
    
    print(f"   ✓ Health check complete")
    print(f"   Status: {metrics.health_status.value.upper()}")
    print(f"   Cool-down Active: {'YES' if monitor.is_cooldown_active else 'NO'}")


def main():
    """Run all demos."""
    print("\n" + "="*60)
    print("  SYSTEM MONITOR DEMONSTRATION")
    print("  Sovereign Doc - Resource Monitoring System")
    print("="*60)
    
    try:
        # Run all demos
        demo_basic_metrics()
        time.sleep(1)
        
        demo_streaming_decision()
        time.sleep(1)
        
        demo_health_monitoring()
        time.sleep(1)
        
        demo_memory_cleanup()
        time.sleep(1)
        
        demo_continuous_monitoring()
        time.sleep(1)
        
        demo_health_check_cycle()
        
        # Final summary
        print_separator()
        print("\n✅ All demonstrations completed successfully!")
        print("\nTo integrate into your app:")
        print("   1. Import: from local_body.core.monitor import SystemMonitor")
        print("   2. Get instance: monitor = SystemMonitor.get_instance()")
        print("   3. Use in Streamlit: See local_body/ui/monitor_integration.py")
        print()
    
    except Exception as e:
        logger.error(f"Demo failed: {e}", exc_info=True)
        print(f"\n❌ Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
