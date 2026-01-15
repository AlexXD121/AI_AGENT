"""Integration example for SystemMonitor in Streamlit UI.

This file demonstrates how to integrate the SystemMonitor into the main
Streamlit application to display real-time system stats in the sidebar.

Copy the relevant functions into your app.py or create a new UI component.
"""

import streamlit as st
from local_body.core.monitor import SystemMonitor, HealthStatus


def render_system_monitor_sidebar() -> None:
    """Render system monitoring panel in Streamlit sidebar.
    
    Usage:
        Add this to your app.py sidebar:
        
        with st.sidebar:
            render_system_monitor_sidebar()
    """
    monitor = SystemMonitor.get_instance()
    
    st.markdown("### 🖥️ System Health")
    
    # Get current metrics
    metrics = monitor.get_current_metrics()
    
    # Health status badge
    status_colors = {
        HealthStatus.OK: "#10B981",
        HealthStatus.WARNING: "#F59E0B",
        HealthStatus.CRITICAL: "#EF4444"
    }
    
    status_icons = {
        HealthStatus.OK: "✓",
        HealthStatus.WARNING: "⚠️",
        HealthStatus.CRITICAL: "🚨"
    }
    
    status_color = status_colors[metrics.health_status]
    status_icon = status_icons[metrics.health_status]
    status_text = metrics.health_status.value.upper()
    
    st.markdown(f"""
    <div style="
        padding: 0.75rem;
        background: linear-gradient(135deg, #1F1F1F 0%, #171717 100%);
        border-left: 4px solid {status_color};
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    ">
        <p style="margin: 0; color: {status_color}; font-weight: 600; font-size: 0.9rem;">
            {status_icon} Status: {status_text}
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Cool-down warning if active
    if monitor.is_cooldown_active:
        st.warning("🌡️ System in cool-down mode - waiting for temperature to normalize")
    
    # RAM usage
    st.caption("**Memory**")
    st.progress(metrics.ram_percent / 100.0)
    st.caption(
        f"{metrics.ram_used_gb:.1f}GB / {metrics.ram_total_gb:.1f}GB "
        f"({metrics.ram_percent:.0f}%)"
    )
    
    # CPU usage
    st.caption("**CPU**")
    st.progress(metrics.cpu_percent / 100.0)
    st.caption(f"{metrics.cpu_percent:.0f}% ({metrics.cpu_count} cores)")
    
    # Temperature if available
    if metrics.cpu_temperature_c:
        temp_color = "#10B981"  # Green
        if metrics.cpu_temperature_c > 70:
            temp_color = "#F59E0B"  # Orange
        if metrics.cpu_temperature_c > 80:
            temp_color = "#EF4444"  # Red
        
        st.caption("**Temperature**")
        st.markdown(f"""
        <p style="margin: 0.25rem 0; color: {temp_color}; font-weight: 600;">
            {metrics.cpu_temperature_c:.1f}°C
        </p>
        """, unsafe_allow_html=True)
    
    # GPU info if available
    if metrics.gpu_available:
        st.caption("**GPU**")
        if metrics.gpu_vram_used_mb and metrics.gpu_vram_total_mb:
            vram_percent = (metrics.gpu_vram_used_mb / metrics.gpu_vram_total_mb) * 100
            st.progress(vram_percent / 100.0)
            st.caption(
                f"{metrics.gpu_vram_used_mb:.0f}MB / {metrics.gpu_vram_total_mb:.0f}MB "
                f"({vram_percent:.0f}%)"
            )
        
        if metrics.gpu_temperature_c:
            st.caption(f"🌡️ {metrics.gpu_temperature_c:.0f}°C")
    
    # Manual cleanup button
    st.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)
    
    if st.button("🧹 Clean Memory", key="manual_cleanup", use_container_width=True):
        with st.spinner("Cleaning up memory..."):
            monitor.attempt_memory_cleanup(force=True)
            st.success("Memory cleanup complete!")
            st.rerun()


def check_system_ready_for_processing() -> bool:
    """Check if system is ready to process a new document.
    
    Returns:
        True if system is ready, False if in cool-down or critical state
        
    Usage:
        if check_system_ready_for_processing():
            # Process document
        else:
            st.warning("System not ready - please wait")
    """
    monitor = SystemMonitor.get_instance()
    
    # Check cool-down mode
    if not monitor.can_process_new_task():
        st.warning(
            "⏸️ System in cool-down mode due to high temperature. "
            "Please wait for system to cool down before processing."
        )
        return False
    
    # Check health status
    metrics = monitor.get_current_metrics()
    
    if metrics.health_status == HealthStatus.CRITICAL:
        st.error(
            f"🚨 System resources critical! "
            f"RAM: {metrics.ram_percent:.0f}%, "
            f"Temp: {metrics.cpu_temperature_c or 'N/A'}°C. "
            f"Please free up resources before continuing."
        )
        
        # Offer automatic cleanup
        if st.button("Try Automatic Cleanup"):
            monitor.attempt_memory_cleanup(force=True)
            st.rerun()
        
        return False
    
    if metrics.health_status == HealthStatus.WARNING:
        st.warning(
            f"⚠️ System resources are running low. "
            f"RAM: {metrics.ram_percent:.0f}%. "
            f"Consider closing other applications."
        )
        # Allow processing but warn user
    
    return True


def integrate_with_upload_screen():
    """Example integration with upload screen.
    
    Add this logic to your upload.py file in the _process_document function.
    """
    import streamlit as st
    from local_body.core.monitor import SystemMonitor
    
    # Get file info
    uploaded_file = st.file_uploader("Upload PDF", type=['pdf'])
    
    if uploaded_file:
        file_size_mb = uploaded_file.size / (1024 * 1024)
        
        # Estimate page count (rough: 1 page = ~100KB for typical PDFs)
        estimated_pages = max(int(file_size_mb * 10), 1)
        
        # Check if streaming mode is needed
        monitor = SystemMonitor.get_instance()
        use_streaming = monitor.should_use_streaming(file_size_mb, estimated_pages)
        
        if use_streaming:
            st.info(
                f"📄 Large document detected ({file_size_mb:.1f}MB, ~{estimated_pages} pages). "
                f"Using streaming mode for optimal performance."
            )
        
        # Check system readiness
        if check_system_ready_for_processing():
            if st.button("Process Document"):
                # Process with appropriate mode
                if use_streaming:
                    # Call streaming loader
                    pass
                else:
                    # Call normal loader
                    pass


# Background monitoring thread (optional - for advanced usage)
def start_background_monitoring():
    """Start background monitoring thread (optional).
    
    This is NOT required for basic usage, but can be used for continuous
    monitoring in long-running applications.
    
    Warning: Streamlit has specific threading considerations.
    """
    import threading
    import time
    from loguru import logger
    
    def monitoring_loop():
        monitor = SystemMonitor.get_instance()
        
        while True:
            try:
                # Run health check cycle
                monitor.run_health_check_cycle()
                
                # Sleep for 10 seconds
                time.sleep(10)
            
            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")
                time.sleep(30)  # Back off on error
    
    # Start daemon thread
    thread = threading.Thread(target=monitoring_loop, daemon=True)
    thread.start()
    logger.info("Background monitoring thread started")


if __name__ == "__main__":
    # Demo: Quick test of the monitoring UI
    st.set_page_config(page_title="System Monitor Demo", layout="wide")
    
    st.title("System Monitor Demo")
    
    col1, col2 = st.columns([1, 3])
    
    with col1:
        render_system_monitor_sidebar()
    
    with col2:
        st.markdown("### Monitor Integration Example")
        st.markdown("""
        The sidebar shows real-time system metrics:
        - **RAM**: Memory usage with progress bar
        - **CPU**: Processor usage and core count
        - **Temperature**: CPU/GPU temperature (if available)
        - **GPU**: VRAM usage and temperature (if GPU detected)
        - **Health Status**: Overall system health (OK/WARNING/CRITICAL)
        
        The monitor automatically:
        - Triggers memory cleanup at 95% RAM usage
        - Activates cool-down mode at 80°C
        - Recommends streaming mode for large files
        """)
        
        # Test buttons
        st.markdown("### Test Functions")
        
        if st.button("Test System Readiness Check"):
            ready = check_system_ready_for_processing()
            if ready:
                st.success("✓ System ready for processing")
        
        if st.button("Test Streaming Decision (50MB, 25 pages)"):
            monitor = SystemMonitor.get_instance()
            should_stream = monitor.should_use_streaming(50, 25)
            if should_stream:
                st.info("Streaming mode recommended")
            else:
                st.success("Normal mode OK")
        
        # Show current metrics
        st.markdown("### Current Metrics")
        monitor = SystemMonitor.get_instance()
        metrics = monitor.get_current_metrics()
        
        st.json({
            "timestamp": str(metrics.timestamp),
            "health_status": metrics.health_status.value,
            "ram_percent": f"{metrics.ram_percent:.1f}%",
            "cpu_percent": f"{metrics.cpu_percent:.1f}%",
            "cpu_temp": f"{metrics.cpu_temperature_c:.1f}°C" if metrics.cpu_temperature_c else "N/A",
            "cooldown_active": monitor.is_cooldown_active
        })
