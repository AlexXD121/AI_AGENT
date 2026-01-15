# SystemMonitor - Quick Reference

## Installation

```bash
pip install psutil gputil
```

## Basic Usage

```python
from local_body.core.monitor import SystemMonitor

# Get singleton instance
monitor = SystemMonitor.get_instance()

# Get current metrics
metrics = monitor.get_current_metrics()
print(f"RAM: {metrics.ram_percent:.1f}%")
print(f"CPU: {metrics.cpu_percent:.1f}%")
print(f"Health: {metrics.health_status.value}")
```

## Common Patterns

### 1. Check System Health Before Processing

```python
# Quick health check
if monitor.check_health() == HealthStatus.CRITICAL:
    print("System resources critical!")
    monitor.attempt_memory_cleanup(force=True)
```

### 2. Determine Processing Mode

```python
# Should we use streaming?
file_size_mb = uploaded_file.size / (1024 * 1024)
page_count = estimate_page_count(file_path)

if monitor.should_use_streaming(file_size_mb, page_count):
    document = loader.load_streaming(file_path)
else:
    document = loader.load_normal(file_path)
```

### 3. Respect Cool-Down Mode

```python
# Check if system is ready
if not monitor.can_process_new_task():
    st.warning("System cooling down - please wait")
    return

# Process document
process_document(file_path)
```

### 4. Manual Cleanup

```python
# User-triggered cleanup button
if st.button("Free Memory"):
    if monitor.attempt_memory_cleanup(force=True):
        st.success("Memory freed!")
    else:
        st.info("Cleanup skipped (recent cleanup)")
```

## Streamlit Integration

### Sidebar Widget

```python
from local_body.ui.monitor_integration import render_system_monitor_sidebar

with st.sidebar:
    render_system_monitor_sidebar()
```

### System Readiness

```python
from local_body.ui.monitor_integration import check_system_ready_for_processing

if check_system_ready_for_processing():
    # Safe to process
    process_document()
```

## Configuration

### Adjust Thresholds

```python
# In your code, before using monitor
SystemMonitor.RAM_WARNING_THRESHOLD = 80.0   # Default: 85%
SystemMonitor.RAM_CRITICAL_THRESHOLD = 90.0  # Default: 95%
SystemMonitor.TEMP_CRITICAL = 75.0           # Default: 80°C
SystemMonitor.TEMP_COOLDOWN_EXIT = 65.0      # Default: 70°C
```

## Periodic Monitoring (Optional)

```python
import threading
import time

def background_monitor():
    monitor = SystemMonitor.get_instance()
    while True:
        monitor.run_health_check_cycle()
        time.sleep(10)  # Check every 10 seconds

# Start daemon thread
thread = threading.Thread(target=background_monitor, daemon=True)
thread.start()
```

## API Reference

| Method | Returns | Description |
|--------|---------|-------------|
| `get_cpu_usage(interval=1.0)` | `float` | CPU usage 0-100% |
| `get_ram_usage()` | `(float, float)` | (used_gb, percent) |
| `get_gpu_metrics()` | `Dict` | VRAM, temp, utilization |
| `get_system_temperature()` | `Optional[float]` | CPU temp in °C |
| `get_current_metrics()` | `SystemMetrics` | All metrics |
| `check_health()` | `HealthStatus` | OK/WARNING/CRITICAL |
| `can_process_new_task()` | `bool` | False if cooling down |
| `attempt_memory_cleanup(force)` | `bool` | True if executed |
| `should_use_streaming(mb, pages)` | `bool` | Streaming recommended? |
| `run_health_check_cycle()` | `None` | Full monitoring cycle |

## Health Status Levels

- **OK**: RAM < 85%, Temp < 70°C
- **WARNING**: RAM 85-95%, Temp 70-80°C
- **CRITICAL**: RAM > 95% OR Temp > 80°C

## Automatic Behaviors

| Condition | Action |
|-----------|--------|
| RAM > 95% | Trigger automatic cleanup |
| Temp > 80°C | Activate cool-down mode |
| Temp < 70°C | Exit cool-down mode |
| File > 50MB | Recommend streaming |
| Pages > 20 | Recommend streaming |
| RAM > 70% | Recommend streaming |

## Testing

```bash
# Run demo
python demo_monitor.py

# Run tests
pytest tests/test_monitor.py -v

# Expected: 19/19 passing ✅
```

## Troubleshooting

**No GPU detected?**
- Normal if you don't have NVIDIA GPU
- System works fine without GPU

**Temperature shows N/A?**
- Windows: Requires admin privileges
- macOS: Requires root access
- System works fine without temperature

**Memory cleanup not freeing much?**
- Python GC is lazy - this is expected
- Main benefit is model cache clearing
- Cleanup prevents OOM crashes

## Files

- Core: `local_body/core/monitor.py`
- Integration: `local_body/ui/monitor_integration.py`
- Tests: `tests/test_monitor.py`
- Demo: `demo_monitor.py`

---

**Quick Start**: `python demo_monitor.py` to see it in action!
