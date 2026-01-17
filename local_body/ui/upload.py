"""Professional upload interface with modular document processing pipeline.

Provides centralized upload UI with real-time progress tracking and
comprehensive error handling.
"""

from pathlib import Path
from typing import Any, Dict, Optional
import tempfile
import time

import streamlit as st
from loguru import logger

from local_body.utils.hardware import HardwareDetector
from local_body.core.datamodels import Document
from local_body.orchestration.state import DocumentProcessingState


def render_upload_hero() -> None:
    """Render minimalist upload screen with system status."""
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        _render_hero_header()
        _render_system_status()
        
        st.markdown("<div style='margin-top: 3rem;'></div>", unsafe_allow_html=True)
        
        uploaded_file = st.file_uploader(
            "Upload PDF",
            type=['pdf'],
            label_visibility="collapsed",
            help="Select a PDF document to analyze"
        )
        
        if uploaded_file:
            _render_upload_actions(uploaded_file)
        else:
            _render_upload_help()


def _render_hero_header() -> None:
    """Render centered hero header with title and description."""
    st.markdown("""
    <div style="text-align: center; margin-top: 4rem; margin-bottom: 3rem;">
        <h1 style="font-size: 3.5rem; font-weight: 700; color: #FFFFFF; margin-bottom: 1rem; 
                   text-shadow: 0 0 30px rgba(59, 130, 246, 0.3);">
            Document Intelligence
        </h1>
        <p style="font-size: 1.25rem; color: #A3A3A3; max-width: 650px; margin: 0 auto; line-height: 1.6;">
            Securely analyze financial documents with local AI.
            Extract, validate, and export data with confidence.
        </p>
    </div>
    """, unsafe_allow_html=True)


def _render_system_status() -> None:
    """Render minimal system status indicator with RAM availability."""
    try:
        detector = HardwareDetector()
        ram_available = detector.get_available_ram_gb()
        ram_total = detector.get_total_ram_gb()
        
        ram_used_percent = ((ram_total - ram_available) / ram_total * 100) if ram_total > 0 else 0
        
        # Determine status based on available RAM
        if ram_total >= 12:
            if ram_available >= 1.5:
                status_color, status_text = "#10B981", "System Ready"
            elif ram_available >= 0.5:
                status_color, status_text = "#F59E0B", "AI Models Active"
            else:
                status_color, status_text = "#EF4444", "Low Memory"
        else:
            if ram_available >= 4:
                status_color, status_text = "#10B981", "System Ready"
            elif ram_available >= 2:
                status_color, status_text = "#F59E0B", "Limited Resources"
            else:
                status_color, status_text = "#EF4444", "Low Memory"
        
        st.markdown(f"""
        <div style="text-align: center; padding: 1rem; border-radius: 8px; 
                    background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.05);">
            <div style="display: flex; align-items: center; justify-content: center; gap: 0.5rem;">
                <div style="width: 8px; height:  8px; border-radius: 50%; background: {status_color};"></div>
                <span style="color: #A3A3A3; font-size: 0.875rem;">{status_text}</span>
                <span style="color: #525252; margin-left: 1rem; font-size: 0.875rem;">
                    RAM: {ram_available:.1f}GB / {ram_total:.1f}GB
                </span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
    except Exception as e:
        logger.debug(f"Could not render system status: {e}")


def _render_upload_actions(uploaded_file: Any) -> None:
    """Render file info and processing button.
    
    Args:
        uploaded_file: Streamlit uploaded file object
    """
    st.success(f"Ready to analyze: {uploaded_file.name}")
    
    file_size_mb = uploaded_file.size / (1024 * 1024)
    st.caption(f"File size: {file_size_mb:.2f} MB")
    
    st.markdown("<div style='margin-top: 2rem;'></div>", unsafe_allow_html=True)
    
    # Check system readiness
    from local_body.ui.monitor_integration import check_system_ready_for_processing
    
    if check_system_ready_for_processing():
        if st.button("Analyze Document", type="primary", width="stretch"):
            import asyncio
            asyncio.run(_process_document(uploaded_file))
    else:
        st.button(
            "Analyze Document (System Not Ready)", 
            type="primary", 
            width="stretch",
            disabled=True,
            help="System resources are critical or in cool-down mode. Please wait."
        )


def _render_upload_help() -> None:
    """Render upload help text when no file selected."""
    st.markdown("""
    <div style="text-align: center; margin-top: 2rem; color: #737373;">
        <p style="font-size: 1rem;">Drag and drop a PDF file, or click to browse</p>
        <p style="font-size: 0.875rem; margin-top: 0.75rem; color: #525252;">
            Supported formats: PDF | Max size: 50MB
        </p>
    </div>
    """, unsafe_allow_html=True)


async def _process_document(uploaded_file: Any) -> None:
    """Execute complete document processing workflow with progress tracking.
    
    Orchestrates the multi-agent pipeline: Layout → OCR → Vision → Validation
    
    Args:
        uploaded_file: Streamlit uploaded file object
    """
    tmp_path = _create_temp_file(uploaded_file)
    
    status_placeholder = st.empty()
    progress_placeholder = st.empty()
    
    try:
        document, config = _initialize_document_loader(
            tmp_path, uploaded_file.name, status_placeholder, progress_placeholder
        )
        
        initial_state = _create_initial_state(
            document, tmp_path, status_placeholder, progress_placeholder
        )
        
        result_state = await _execute_workflow(
            initial_state, status_placeholder, progress_placeholder
        )
        
        # Clear UI elements
        status_placeholder.empty()
        progress_placeholder.empty()
        
        # Route based on processing outcome
        if result_state.get('processing_stage') == 'FAILED':
            _handle_workflow_failure(result_state)
        else:
            _handle_workflow_success(result_state)
            
    except Exception as e:
        _handle_processing_exception(e, uploaded_file.name, status_placeholder, progress_placeholder)


def _create_temp_file(uploaded_file: Any) -> str:
    """Create temporary file from uploaded content.
    
    Args:
        uploaded_file: Streamlit uploaded file object
        
    Returns:
        Path to temporary file
    """
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
        tmp_file.write(uploaded_file.getbuffer())
        return tmp_file.name


def _initialize_document_loader(
    tmp_path: str, 
    filename: str,
    status_placeholder: Any, 
    progress_placeholder: Any
) -> tuple[Document, Any]:
    """Initialize configuration and load document.
    
    Args:
        tmp_path: Path to temporary PDF file
        filename: Original filename for display
        status_placeholder: Streamlit placeholder for status messages
        progress_placeholder: Streamlit placeholder for progress bar
        
    Returns:
        Tuple of (loaded document, system configuration)
    """
    from local_body.utils.document_loader import DocumentLoader
    from local_body.core.config_manager import ConfigManager
    
    with st.spinner("Initializing system..."):
        status_placeholder.info("Loading system configuration...")
        progress_placeholder.progress(0.05)
        
        config = ConfigManager().load_config()
        loader = DocumentLoader()
        
        status_placeholder.info("Loading document...")
        progress_placeholder.progress(0.1)
        
        document = loader.load_document(tmp_path)
        st.session_state['document_name'] = filename
        
        logger.info(f"Document loaded: {document.id}, {len(document.pages)} pages")
        
    return document, config


def _create_initial_state(
    document: Document,
    tmp_path: str,
    status_placeholder: Any,
    progress_placeholder: Any
) -> Dict[str, Any]:
    """Prepare initial workflow state.
    
    Args:
        document: Loaded document object
        tmp_path: Path to temporary file
        status_placeholder: Streamlit status placeholder
        progress_placeholder: Streamlit progress placeholder
        
    Returns:
        Initial state dictionary for workflow
    """
    from local_body.orchestration.state import ProcessingStage
    
    status_placeholder.info("Preparing processing pipeline...")
    progress_placeholder.progress(0.15)
    
    initial_state = {
        'document': document,
        'file_path': tmp_path,
        'processing_stage': ProcessingStage.INGEST,
        'layout_regions': [],
        'ocr_results': {},
        'vision_results': {},
        'conflicts': [],
        'resolutions': [],
        'error_log': []
    }
    
    logger.info("Initial state prepared")
    return initial_state


async def _execute_workflow(
    initial_state: Dict[str, Any],
    status_placeholder: Any,
    progress_placeholder: Any
) -> DocumentProcessingState:
    """Execute multi-agent workflow with progress tracking.
    
    Args:
        initial_state: Initial workflow state
        status_placeholder: Streamlit status placeholder
        progress_placeholder: Streamlit progress placeholder
        
    Returns:
        Final workflow state after processing
    """
    from local_body.orchestration.workflow import DocumentWorkflow
    
    with st.status("AI Agents working...", expanded=True) as status:
        status.write("Layout Agent: Scanning structure...")
        progress_placeholder.progress(0.25)
        
        status.write("Starting Agent Swarm...")
        
        workflow = DocumentWorkflow()
        result_state = await workflow.run(initial_state)
        
        status.update(label="AI Agents Finished!", state="complete", expanded=False)
        
    return result_state


def _handle_workflow_failure(state: DocumentProcessingState) -> None:
    """Display workflow failure information to user.
    
    Args:
        state: Failed workflow state with error information
    """
    failed_node = state.get('failed_node', 'Unknown')
    error_message = state.get('error_message', 'Unknown error occurred')
    traceback_info = state.get('traceback_info', '')
    error_log = state.get('error_log', [])
    
    st.error(f"Analysis Failed: {error_message}")
    
    with st.expander("View Technical Details"):
        if traceback_info:
            st.markdown("### Python Traceback")
            st.code(traceback_info, language="python")
        
        if error_log:
            st.markdown("### Error Log")
            for idx, err in enumerate(error_log):
                st.markdown(f"**Step {idx + 1}: {err.get('node', 'Unknown')}**")
                st.code(f"{err.get('type', 'Error')}: {err.get('error', 'No details')}")
    
    # Store failed state
    st.session_state['current_state'] = state
    st.session_state['processing_complete'] = False
    st.session_state['processing_failed'] = True
    
    logger.error(f"Workflow failed at {failed_node}: {error_message}")


def _handle_workflow_success(state: DocumentProcessingState) -> None:
    """Process successful workflow results and update session state.
    
    Args:
        state: Successful workflow state with analysis results
    """
    st.session_state['current_state'] = state
    
    # Extract metrics for dashboard
    analysis_data = _extract_analysis_metrics(state)
    st.session_state['analysis_data'] = analysis_data
    
    # Mark processing as complete
    st.session_state['processing_complete'] = True
    st.session_state['processing_failed'] = False
    
    logger.info(f"Analysis complete: {len(state.get('conflicts', []))} conflicts detected")
    logger.info(f"Session state updated: processing_complete=True")
    
    # Success feedback
    st.toast("Analysis Complete!")
    time.sleep(0.5)
    logger.info("Triggering rerun to show dashboard...")
    st.rerun()


def _handle_processing_exception(
    error: Exception,
    filename: str,
    status_placeholder: Any,
    progress_placeholder: Any
) -> None:
    """Handle unexpected processing exceptions.
    
    Args:
        error: Exception that occurred
        filename: Name of file being processed
        status_placeholder: Streamlit status placeholder
        progress_placeholder: Streamlit progress placeholder
    """
    logger.error(f"Document processing failed: {error}")
    logger.error(f"Error type: {type(error).__name__}")
    
    import traceback
    error_details = traceback.format_exc()
    logger.error(f"Full traceback:\n{error_details}")
    
    status_placeholder.error("Processing failed")
    progress_placeholder.empty()
    
    st.error(f"""
    **Processing Error**
    
    Failed to process document: {filename}
    
    Error: {str(error)}
    
    Please try again or contact support if the issue persists.
    """)
    
    with st.expander("Technical Details"):
        st.code(error_details, language="python")
    
    st.session_state['processing_complete'] = False
    st.session_state['processing_failed'] = True


def _extract_analysis_metrics(state: DocumentProcessingState) -> Dict[str, Any]:
    """Extract key metrics from processing state for dashboard display.
    
    Args:
        state: Completed workflow state
        
    Returns:
        Dictionary of extracted metrics for visualization
    """
    document = state.get('document')
    
    if not document or not hasattr(document, 'pages'):
        return {}
    
    # Calculate average OCR confidence
    all_confidences = []
    total_regions = 0
    
    for page in document.pages:
        total_regions += len(page.regions)
        for region in page.regions:
            if hasattr(region, 'confidence'):
                all_confidences.append(region.confidence)
    
    avg_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0
    
    return {
        'total_pages': len(document.pages),
        'total_regions': total_regions,
        'confidence': avg_confidence,
        'conflicts': len(state.get('conflicts', [])),
        'processing_stage': state.get('processing_stage', 'UNKNOWN')
    }
