"""Advanced document upload and configuration interface.

This module provides an intelligent upload interface with:
- Hardware detection and processing mode recommendations
- Configurable processing parameters
- Batch upload support for multiple PDFs
- Config override management
"""

import os
import shutil
from typing import Dict, Any, List, Optional
from pathlib import Path

import streamlit as st
from loguru import logger

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

from local_body.utils.hardware import HardwareDetector
from local_body.core.config_manager import ConfigManager


def render_upload_page() -> None:
    """Render the main upload page with hardware stats and configuration."""
    st.title("📄 Sovereign-Doc Document Processor")
    st.markdown("### Intelligent Document Ingestion")
    
    # Hardware status section
    render_hardware_status()
    
    st.divider()
    
    # Configuration panel
    config_overrides = render_configuration_panel()
    
    st.divider()
    
    # Upload section
    render_upload_section(config_overrides)


def render_hardware_status() -> None:
    """Render system hardware status and processing recommendations."""
    st.subheader("🖥️ System Status")
    
    try:
        # Initialize hardware detector
        detector = HardwareDetector()
        
        # Display metrics in columns
        col1, col2, col3 = st.columns(3)
        
        with col1:
            cpu_usage = psutil.cpu_percent(interval=0.1) if PSUTIL_AVAILABLE else 0
            cpu_delta = "Normal" if cpu_usage < 80 else "High"
            st.metric(
                label="CPU Usage",
                value=f"{cpu_usage:.1f}%",
                delta=cpu_delta,
                delta_color="normal" if cpu_usage < 80 else "inverse"
            )
        
        with col2:
            ram_available = detector.get_available_ram_gb()
            ram_total = detector.get_total_ram_gb()
            ram_percent = (ram_available / ram_total * 100) if ram_total > 0 else 0
            st.metric(
                label="RAM Available",
                value=f"{ram_available:.1f} GB",
                delta=f"{ram_percent:.0f}% free"
            )
        
        with col3:
            gpu_available = detector.has_gpu()
            gpu_info = detector.get_gpu_info()
            gpu_name = gpu_info.get('name', 'N/A') if gpu_info else 'N/A'
            st.metric(
                label="GPU Status",
                value="Available" if gpu_available else "Not Available",
                delta=gpu_name if gpu_available else "CPU Only"
            )
        
        # Intelligent recommendations
        st.markdown("#### 💡 Recommended Configuration")
        
        if not gpu_available and ram_available < 8:
            st.warning(
                "⚠️ **Limited Resources Detected**\n\n"
                "**Recommended Mode:** Local (Light)\n\n"
                "Your system has limited resources. We recommend:\n"
                "- Processing Mode: Local (Privacy Focused)\n"
                "- Batch Size: 1-2 documents\n"
                "- Sequential processing"
            )
        elif not gpu_available and ram_available >= 8:
            st.info(
                "ℹ️ **CPU Processing Available**\n\n"
                "**Recommended Mode:** Hybrid (Cloud Brain for Vision)\n\n"
                "Your system can handle local OCR/Layout but may benefit from cloud vision."
            )
        elif gpu_available:
            st.success(
                "✅ **High Performance System**\n\n"
                "**Recommended Mode:** Local (Full GPU Acceleration)\n\n"
                "Your system is optimized for local processing with GPU support!"
            )
        else:
            st.success(
                "✅ **System Ready**\n\n"
                "**Recommended Mode:** Hybrid (Cloud Brain)\n\n"
                "Balance between local privacy and cloud intelligence."
            )
    
    except Exception as e:
        logger.error(f"Hardware detection failed: {e}")
        st.warning(
            "⚠️ Hardware detection unavailable. "
            "Proceeding with default configuration."
        )


def render_configuration_panel() -> Dict[str, Any]:
    """Render configuration panel for processing parameters.
    
    Returns:
        Dictionary of configuration overrides
    """
    config_overrides = {}
    
    with st.expander("⚙️ Processing Configuration", expanded=False):
        st.markdown("**Customize processing behavior**")
        
        # Processing mode selection
        col1, col2 = st.columns(2)
        
        with col1:
            processing_mode = st.selectbox(
                "Processing Mode",
                [
                    "Hybrid (Cloud Brain + Local)",
                    "Local (Privacy Focused)",
                    "Cloud Only (Requires Internet)"
                ],
                index=0,
                help="Choose how documents are processed:\n"
                     "- Hybrid: Best accuracy (uses cloud for vision)\n"
                     "- Local: Maximum privacy (CPU/GPU only)\n"
                     "- Cloud: Fastest (requires stable internet)"
            )
            
            # Map selection to config value
            mode_mapping = {
                "Hybrid (Cloud Brain + Local)": "hybrid",
                "Local (Privacy Focused)": "local",
                "Cloud Only (Requires Internet)": "cloud"
            }
            config_overrides['processing_mode'] = mode_mapping[processing_mode]
        
        with col2:
            batch_size = st.number_input(
                "Batch Size",
                min_value=1,
                max_value=10,
                value=5,
                help="Number of documents to process in parallel.\n"
                     "Higher values = faster but more memory usage."
            )
            config_overrides['batch_size'] = batch_size
        
        st.markdown("---")
        st.markdown("**Advanced Settings**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            conflict_threshold = st.slider(
                "Conflict Detection Threshold",
                min_value=0.0,
                max_value=1.0,
                value=0.15,
                step=0.05,
                help="Discrepancy percentage to trigger a conflict.\n"
                     "Lower values = more sensitive (more conflicts)\n"
                     "Higher values = less sensitive (fewer conflicts)"
            )
            config_overrides['conflict_threshold'] = conflict_threshold
        
        with col2:
            confidence_threshold = st.slider(
                "Confidence Threshold",
                min_value=0.0,
                max_value=1.0,
                value=0.7,
                step=0.05,
                help="Minimum confidence score to accept results.\n"
                     "Lower values accept more results (less strict)\n"
                     "Higher values require higher quality (more strict)"
            )
            config_overrides['confidence_threshold'] = confidence_threshold
        
        # Additional options
        st.markdown("---")
        st.markdown("**Optional Features**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            enable_auto_resolution = st.checkbox(
                "Enable Auto-Resolution",
                value=True,
                help="Automatically resolve low-impact conflicts"
            )
            config_overrides['enable_auto_resolution'] = enable_auto_resolution
        
        with col2:
            save_intermediate = st.checkbox(
                "Save Intermediate Results",
                value=False,
                help="Save processing checkpoints for debugging"
            )
            config_overrides['save_intermediate'] = save_intermediate
    
    return config_overrides


def render_upload_section(config_overrides: Dict[str, Any]) -> None:
    """Render document upload section with batch support.
    
    Args:
        config_overrides: Configuration overrides from panel
    """
    st.subheader("📁 Document Upload")
    
    # File uploader with multi-file support
    uploaded_files = st.file_uploader(
        "Drop PDF files here or click to browse",
        type=['pdf'],
        accept_multiple_files=True,
        help="You can upload multiple PDFs at once for batch processing"
    )
    
    # Display upload status
    if uploaded_files:
        st.success(f"✅ Uploaded {len(uploaded_files)} file(s)")
        
        # Show file list
        with st.expander("📋 Uploaded Files", expanded=True):
            for idx, file in enumerate(uploaded_files):
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.text(f"{idx + 1}. {file.name}")
                with col2:
                    file_size_mb = file.size / (1024 * 1024)
                    st.caption(f"{file_size_mb:.2f} MB")
                with col3:
                    st.caption(f"{file.type}")
        
        # Processing button
        st.markdown("---")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button(
                "🚀 Start Processing",
                type="primary",
                use_container_width=True
            ):
                _start_processing(uploaded_files, config_overrides)
    
    else:
        # Show help when no files uploaded
        st.info(
            "👆 Upload one or more PDF documents to begin processing.\n\n"
            "**Supported formats:** PDF\n\n"
            "**Batch processing:** Upload multiple files for parallel processing"
        )
        
        # Show examples
        with st.expander("📖 Example Documents"):
            st.markdown("""
            **Sovereign-Doc** works best with structured documents:
            
            - 📊 Financial reports (balance sheets, income statements)
            - 📄 Contracts and legal documents
            - 🧾 Invoices and receipts
            - 📋 Forms and applications
            - 📑 Research papers and technical documents
            """)


def _start_processing(uploaded_files: List, config_overrides: Dict[str, Any]) -> None:
    """Initialize processing for uploaded files.
    
    Args:
        uploaded_files: List of uploaded file objects
        config_overrides: Configuration overrides
    """
    try:
        # Create temp directory if it doesn't exist
        temp_dir = Path("temp")
        temp_dir.mkdir(exist_ok=True)
        
        # Clear existing files in temp directory
        if temp_dir.exists():
            for item in temp_dir.iterdir():
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
        
        st.info("📂 Preparing documents...")
        
        # Save uploaded files to temp directory
        document_paths = []
        progress_bar = st.progress(0)
        
        for idx, uploaded_file in enumerate(uploaded_files):
            # Save file
            file_path = temp_dir / uploaded_file.name
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            document_paths.append(str(file_path))
            
            # Update progress
            progress = (idx + 1) / len(uploaded_files)
            progress_bar.progress(progress)
        
        progress_bar.empty()
        
        # Load and merge configuration
        config_manager = ConfigManager()
        base_config = config_manager.load_config()
        
        # Merge overrides
        for key, value in config_overrides.items():
            if hasattr(base_config, key):
                setattr(base_config, key, value)
        
        # Initialize session state
        st.session_state['document_queue'] = document_paths
        st.session_state['config'] = base_config
        st.session_state['processing_active'] = True
        st.session_state['current_document_index'] = 0
        st.session_state['checkpoint_dir'] = 'test_checkpoint'
        
        logger.info(f"Initialized processing for {len(document_paths)} documents")
        
        st.success(f"✅ Ready to process {len(document_paths)} document(s)!")
        st.info("🔄 Redirecting to processing dashboard...")
        
        # Rerun to show dashboard
        st.rerun()
    
    except Exception as e:
        logger.error(f"Error initializing processing: {e}")
        st.error(f"❌ Failed to start processing: {str(e)}")
        st.exception(e)


def render_upload_summary_widget() -> None:
    """Render a compact upload summary for sidebar."""
    if 'document_queue' in st.session_state and st.session_state.get('processing_active'):
        queue = st.session_state['document_queue']
        current_idx = st.session_state.get('current_document_index', 0)
        
        st.metric(
            "Documents in Queue",
            f"{current_idx + 1}/{len(queue)}"
        )
        
        current_doc = Path(queue[current_idx]).name if current_idx < len(queue) else "N/A"
        st.caption(f"Current: {current_doc}")
        
        if st.button("🔄 Reset Queue", use_container_width=True):
            st.session_state['processing_active'] = False
            st.session_state['document_queue'] = []
            st.rerun()
