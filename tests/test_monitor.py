"""Test suite for SystemMonitor.

Tests CPU, RAM, GPU monitoring, thermal management, and streaming decisions.
"""

import pytest
import time
from datetime import datetime, timedelta
from local_body.core.monitor import SystemMonitor, HealthStatus, SystemMetrics


class TestSystemMonitor:
    """Test SystemMonitor functionality."""
    
    def test_singleton_pattern(self):
        """Test that SystemMonitor uses singleton pattern."""
        monitor1 = SystemMonitor.get_instance()
        monitor2 = SystemMonitor.get_instance()
        
        assert monitor1 is monitor2, "SystemMonitor should be a singleton"
    
    def test_get_cpu_usage(self):
        """Test CPU usage retrieval."""
        monitor = SystemMonitor.get_instance()
        cpu_usage = monitor.get_cpu_usage(interval=0.1)
        
        assert isinstance(cpu_usage, float), "CPU usage should be float"
        assert 0 <= cpu_usage <= 100, "CPU usage should be between 0-100%"
    
    def test_get_ram_usage(self):
        """Test RAM usage retrieval."""
        monitor = SystemMonitor.get_instance()
        used_gb, percent = monitor.get_ram_usage()
        
        assert isinstance(used_gb, float), "RAM used should be float"
        assert isinstance(percent, float), "RAM percent should be float"
        assert used_gb >= 0, "RAM used should be non-negative"
        assert 0 <= percent <= 100, "RAM percent should be between 0-100%"
    
    def test_get_gpu_metrics(self):
        """Test GPU metrics retrieval."""
        monitor = SystemMonitor.get_instance()
        metrics = monitor.get_gpu_metrics()
        
        assert isinstance(metrics, dict), "GPU metrics should be dict"
        assert "vram_used_mb" in metrics
        assert "vram_total_mb" in metrics
        assert "temperature_c" in metrics
        assert "utilization_percent" in metrics
        
        # Values can be None if no GPU
        if metrics["vram_used_mb"] is not None:
            assert metrics["vram_used_mb"] >= 0
    
    def test_get_system_temperature(self):
        """Test temperature retrieval."""
        monitor = SystemMonitor.get_instance()
        temp = monitor.get_system_temperature()
        
        # Temperature may not be available on all systems
        if temp is not None:
            assert isinstance(temp, float)
            assert 0 < temp < 150, "Temperature should be reasonable (0-150°C)"
    
    def test_get_current_metrics(self):
        """Test comprehensive metrics retrieval."""
        monitor = SystemMonitor.get_instance()
        metrics = monitor.get_current_metrics()
        
        assert isinstance(metrics, SystemMetrics)
        assert isinstance(metrics.timestamp, datetime)
        assert metrics.cpu_percent >= 0
        assert metrics.ram_percent >= 0
        assert metrics.health_status in HealthStatus
    
    def test_health_status_calculation(self):
        """Test health status calculation logic."""
        monitor = SystemMonitor.get_instance()
        
        # Test OK status (low RAM, low temp)
        status = monitor._calculate_health_status(50.0, 50.0, None)
        assert status == HealthStatus.OK
        
        # Test WARNING status (high RAM but below critical)
        status = monitor._calculate_health_status(87.0, 50.0, None)
        assert status == HealthStatus.WARNING
        
        # Test CRITICAL status (very high RAM)
        status = monitor._calculate_health_status(96.0, 50.0, None)
        assert status == HealthStatus.CRITICAL
        
        # Test CRITICAL status (high temperature)
        status = monitor._calculate_health_status(50.0, 85.0, None)
        assert status == HealthStatus.CRITICAL
    
    def test_check_health(self):
        """Test health check function."""
        monitor = SystemMonitor.get_instance()
        health = monitor.check_health()
        
        assert isinstance(health, HealthStatus)
    
    def test_memory_cleanup(self):
        """Test memory cleanup function."""
        monitor = SystemMonitor.get_instance()
        
        # Should execute cleanup
        result = monitor.attempt_memory_cleanup(force=True)
        assert result is True, "Cleanup should execute when forced"
        
        # Should skip due to cooldown
        result = monitor.attempt_memory_cleanup(force=False)
        assert result is False, "Cleanup should be skipped due to cooldown"
    
    def test_streaming_decision_large_file(self):
        """Test streaming mode decision for large files."""
        monitor = SystemMonitor.get_instance()
        
        # Large file (>50MB) should trigger streaming
        should_stream = monitor.should_use_streaming(75, 10)
        assert should_stream is True, "Large files should use streaming"
    
    def test_streaming_decision_many_pages(self):
        """Test streaming mode decision for many pages."""
        monitor = SystemMonitor.get_instance()
        
        # Many pages (>20) should trigger streaming
        should_stream = monitor.should_use_streaming(30, 25)
        assert should_stream is True, "Documents with many pages should use streaming"
    
    def test_streaming_decision_normal_document(self):
        """Test streaming mode decision for normal documents."""
        monitor = SystemMonitor.get_instance()
        
        # Normal document should not require streaming (unless RAM is high)
        should_stream = monitor.should_use_streaming(20, 10)
        # Result depends on current RAM usage, so we just check it returns bool
        assert isinstance(should_stream, bool)
    
    def test_can_process_new_task(self):
        """Test task processing readiness check."""
        monitor = SystemMonitor.get_instance()
        
        # Should be able to process if not in cooldown
        can_process = monitor.can_process_new_task()
        assert isinstance(can_process, bool)
    
    def test_cooldown_state_management(self):
        """Test cooldown mode state."""
        monitor = SystemMonitor.get_instance()
        
        # Initially should not be in cooldown
        initial_state = monitor.is_cooldown_active
        assert isinstance(initial_state, bool)
    
    def test_health_check_cycle(self):
        """Test complete health check cycle."""
        monitor = SystemMonitor.get_instance()
        
        # Should run without errors
        monitor.run_health_check_cycle()
        
        # Verify metrics are updated
        metrics = monitor.get_current_metrics()
        assert metrics.timestamp is not None


class TestSystemMetrics:
    """Test SystemMetrics dataclass."""
    
    def test_metrics_creation(self):
        """Test creating SystemMetrics object."""
        metrics = SystemMetrics(
            timestamp=datetime.now(),
            cpu_percent=50.0,
            cpu_count=8,
            ram_total_gb=16.0,
            ram_used_gb=8.0,
            ram_available_gb=8.0,
            ram_percent=50.0,
            gpu_available=False,
            health_status=HealthStatus.OK
        )
        
        assert metrics.cpu_percent == 50.0
        assert metrics.ram_percent == 50.0
        assert metrics.health_status == HealthStatus.OK
    
    def test_metrics_with_gpu(self):
        """Test metrics with GPU data."""
        metrics = SystemMetrics(
            timestamp=datetime.now(),
            cpu_percent=50.0,
            cpu_count=8,
            ram_total_gb=16.0,
            ram_used_gb=8.0,
            ram_available_gb=8.0,
            ram_percent=50.0,
            gpu_available=True,
            gpu_vram_used_mb=4096.0,
            gpu_vram_total_mb=8192.0,
            gpu_temperature_c=65.0,
            gpu_utilization_percent=75.0,
            health_status=HealthStatus.OK
        )
        
        assert metrics.gpu_available is True
        assert metrics.gpu_vram_used_mb == 4096.0
        assert metrics.gpu_temperature_c == 65.0


@pytest.mark.integration
class TestMonitorIntegration:
    """Integration tests for SystemMonitor."""
    
    def test_continuous_monitoring(self):
        """Test continuous monitoring over time."""
        monitor = SystemMonitor.get_instance()
        
        # Collect metrics over 3 seconds
        samples = []
        for _ in range(3):
            metrics = monitor.get_current_metrics()
            samples.append(metrics)
            time.sleep(1)
        
        assert len(samples) == 3
        
        # Check that timestamps are increasing
        for i in range(1, len(samples)):
            assert samples[i].timestamp > samples[i-1].timestamp
    
    def test_memory_pressure_simulation(self):
        """Test system behavior under simulated memory pressure."""
        monitor = SystemMonitor.get_instance()
        
        # Get initial metrics
        initial_metrics = monitor.get_current_metrics()
        
        # Create some memory pressure (allocate large list)
        large_data = [0] * (10 * 1024 * 1024)  # ~80MB
        
        # Get metrics after allocation
        pressure_metrics = monitor.get_current_metrics()
        
        # RAM usage should have increased
        assert pressure_metrics.ram_used_gb >= initial_metrics.ram_used_gb
        
        # Cleanup
        del large_data
        monitor.attempt_memory_cleanup(force=True)
        
        # Metrics after cleanup
        cleanup_metrics = monitor.get_current_metrics()
        # RAM might be lower (but not guaranteed due to Python GC behavior)
        assert isinstance(cleanup_metrics.ram_used_gb, float)


if __name__ == "__main__":
    # Run basic tests
    print("Running SystemMonitor tests...")
    
    monitor = SystemMonitor.get_instance()
    
    print("\n1. Getting current metrics...")
    metrics = monitor.get_current_metrics()
    print(f"   CPU: {metrics.cpu_percent:.1f}%")
    print(f"   RAM: {metrics.ram_used_gb:.1f}GB / {metrics.ram_total_gb:.1f}GB ({metrics.ram_percent:.1f}%)")
    print(f"   Health: {metrics.health_status.value}")
    
    if metrics.cpu_temperature_c:
        print(f"   CPU Temp: {metrics.cpu_temperature_c:.1f}°C")
    
    if metrics.gpu_available:
        print(f"   GPU VRAM: {metrics.gpu_vram_used_mb:.0f}MB / {metrics.gpu_vram_total_mb:.0f}MB")
        if metrics.gpu_temperature_c:
            print(f"   GPU Temp: {metrics.gpu_temperature_c:.1f}°C")
    
    print("\n2. Testing streaming decision...")
    should_stream = monitor.should_use_streaming(75, 30)
    print(f"   Large doc (75MB, 30 pages): Streaming = {should_stream}")
    
    should_stream = monitor.should_use_streaming(10, 5)
    print(f"   Small doc (10MB, 5 pages): Streaming = {should_stream}")
    
    print("\n3. Testing memory cleanup...")
    result = monitor.attempt_memory_cleanup(force=True)
    print(f"   Cleanup executed: {result}")
    
    print("\n4. Testing system readiness...")
    can_process = monitor.can_process_new_task()
    print(f"   Can process new task: {can_process}")
    
    print("\n✓ All manual tests completed successfully!")
