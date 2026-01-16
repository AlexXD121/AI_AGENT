"""Professional upload hero screen with minimalist design and LangGraph backend integration.

Clean, centered upload interface with status indicators.
"""

from pathlib import Path
import tempfile
import time

import streamlit as st
from loguru import logger

from local_body.utils.hardware import HardwareDetector


def render_upload_hero() -> None:
    """Render the minimalist hero upload screen."""
    
    # Center content using columns
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        # Hero header
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
        
        # System status (subtle)
        _render_system_status()
        
        st.markdown("<div style='margin-top: 3rem;'></div>", unsafe_allow_html=True)
        
        # File uploader
        uploaded_file = st.file_uploader(
            "Upload PDF",
            type=['pdf'],
            label_visibility="collapsed",
            help="Select a PDF document to analyze"
        )
        
        if uploaded_file:
            st.success(f"Ready to analyze: {uploaded_file.name}")
            
            # Show file details
            file_size_mb = uploaded_file.size / (1024 * 1024)
            st.caption(f"File size: {file_size_mb:.2f} MB")
            
            # Processing button
            st.markdown("<div style='margin-top: 2rem;'></div>", unsafe_allow_html=True)
            
            # SYSTEM MONITOR PROTECTION: Check if system is ready before allowing processing
            from local_body.ui.monitor_integration import check_system_ready_for_processing
            
            if check_system_ready_for_processing():
                # System is healthy - show button and allow processing
                if st.button("Analyze Document", type="primary", use_container_width=True):
                    _process_document(uploaded_file)
            else:
                # System not ready - button disabled, error already shown by check function
                st.button(
                    "Analyze Document (System Not Ready)", 
                    type="primary", 
                    use_container_width=True,
                    disabled=True,
                    help="System resources are critical or in cool-down mode. Please wait."
                )
        else:
            # Show help
            st.markdown("""
            <div style="text-align: center; margin-top: 2rem; color: #737373;">
                <p style="font-size: 1rem;">Drag and drop a PDF file, or click to browse</p>
                <p style="font-size: 0.875rem; margin-top: 0.75rem; color: #525252;">
                    Supported formats: PDF | Max size: 50MB
                </p>
            </div>
            """, unsafe_allow_html=True)


def _render_system_status() -> None:
    """Render minimal system status indicator."""
    try:
        detector = HardwareDetector()
        ram_available = detector.get_available_ram_gb()
        ram_total = detector.get_total_ram_gb()
        
        # Calculate RAM usage percentage
        ram_used_percent = ((ram_total - ram_available) / ram_total * 100) if ram_total > 0 else 0
        
        # Intelligent status based on total RAM and usage
        if ram_total >= 12:  # High RAM systems
            if ram_available >= 1.5:
                status_color = "#10B981"
                status_text = "System Ready"
            elif ram_available >= 0.5:
                status_color = "#F59E0B"
                status_text = "AI Models Active"
            else:
                status_color = "#EF4444"
                status_text = "Low Memory"
        else:  # Lower RAM systems
            if ram_available >= 4:
                status_color = "#10B981"
                status_text = "System Ready"
            elif ram_available >= 2:
                status_color = "#F59E0B"
                status_text = "Limited Resources"
            else:
                status_color = "#EF4444"
                status_text = "Low Memory"
        
        # Render status
        st.markdown(f"""
        <div style="text-align: center; margin-bottom: 1rem;">
            <span style="display: inline-block; padding: 0.5rem 1rem; 
                        background: rgba(255,255,255,0.05); border-radius: 1rem;
                        border: 1px solid rgba(255,255,255,0.1);">
                <span style="display: inline-block; width: 8px; height: 8px; 
                            background: {status_color}; border-radius: 50%; margin-right: 0.5rem;"></span>
                <span style="color: #A3A3A3; font-size: 0.875rem;">{status_text}</span>
                <span style="color: #737373; font-size: 0.75rem; margin-left: 0.75rem;">
                    {ram_available:.1f}/{ram_total:.1f} GB
                </span>
            </span>
        </div>
        """, unsafe_allow_html=True)
    except:
        pass  # Silently fail if hardware detection unavailable


def _process_document(uploaded_file) -> None:
    """Process uploaded document using multi-agent workflow.
    
    This function integrates the LangGraph DocumentWorkflow backend with
    the Streamlit frontend, executing the full processing pipeline:
    Layout → OCR → Vision → Validation → Resolution
    
    Args:
        uploaded_file: Streamlit uploaded file object
    """
    # Create temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
        tmp_file.write(uploaded_file.getbuffer())
        tmp_path = tmp_file.name
    
    # Processing UI elements
    status_placeholder = st.empty()
    progress_placeholder = st.empty()
    
    try:
        # Import required modules
        from local_body.utils.document_loader import DocumentLoader
        from local_body.core.config_manager import ConfigManager
        from local_body.orchestration.workflow import DocumentWorkflow
        from local_body.orchestration.state import ProcessingStage
        
        # Stage 1: Initialize configuration and load document
        with st.spinner("Initializing system..."):
            status_placeholder.info("📋 Loading system configuration...")
            progress_placeholder.progress(0.05)
            
            config = ConfigManager().load_config()
            loader = DocumentLoader()
            
            status_placeholder.info("📄 Loading document...")
            progress_placeholder.progress(0.1)
            
            document = loader.load_document(tmp_path)
            st.session_state['document_name'] = uploaded_file.name
            
            logger.info(f"Document loaded: {document.file_id}, {len(document.pages)} pages")
        
        # Stage 2: Prepare initial workflow state
        status_placeholder.info("🔧 Preparing processing pipeline...")
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
        
        # Stage 3: Execute multi-agent workflow
        status_placeholder.info("🤖 Starting multi-agent processing...")
        progress_placeholder.progress(0.2)
        
        workflow = DocumentWorkflow()
        
        # Execute workflow with progress updates
        with st.spinner("Agents are analyzing document..."):
            # Layout Detection
            status_placeholder.info("🔍 Layout Detection Agent working...")
            progress_placeholder.progress(0.3)
            
            # OCR Extraction
            status_placeholder.info("📖 OCR Agent extracting text...")
            progress_placeholder.progress(0.5)
            
            # Vision Analysis
            status_placeholder.info("👁️ Vision Agent analyzing content...")
            progress_placeholder.progress(0.7)
            
            # Conflict Validation
            status_placeholder.info("⚖️ Validation Agent checking conflicts...")
            progress_placeholder.progress(0.85)
            
            # Run the workflow
            result_state = workflow.run(initial_state)
            
            logger.success(f"Workflow completed: stage={result_state.get('processing_stage')}")
        
        # Stage 4: Process results and update session state
        status_placeholder.info("✅ Finalizing results...")
        progress_placeholder.progress(0.95)
        
        # Store complete state
        st.session_state['current_state'] = result_state
        
        # Extract metrics for dashboard
        analysis_data = _extract_analysis_metrics(result_state)
        st.session_state['analysis_data'] = analysis_data
        
        # Mark processing as complete
        st.session_state['processing_complete'] = True
        
        # Success
        progress_placeholder.progress(1.0)
        status_placeholder.success("✅ Document processing complete!")
        
        logger.info(f"Analysis complete: {len(result_state.get('conflicts', []))} conflicts detected")
        
        # Auto-advance to dashboard
        time.sleep(0.5)
        st.rerun()
        
    except Exception as e:
        # Error handling
        logger.error(f"Document processing failed: {e}")
        logger.error(f"Error type: {type(e).__name__}")
        
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Full traceback:\n{error_details}")
        
        # Show user-friendly error
        status_placeholder.error("❌ Processing failed")
        progress_placeholder.empty()
        
        st.error(f"""
        **Processing Error**
        
        Failed to process document: {uploaded_file.name}
        
        Error: {str(e)}
        
        Please try again or contact support if the issue persists.
        """)
        
        # Show technical details in expander
        with st.expander("Technical Details"):
            st.code(error_details, language="python")
        
        # Keep processing_complete as False
        st.session_state['processing_complete'] = False
    
    finally:
        # Cleanup temp file
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except Exception as e:
            logger.warning(f"Failed to delete temp file: {e}")


def _extract_analysis_metrics(state: dict) -> dict:
    """Extract analysis metrics from processing state for dashboard.
    
    Args:
        state: DocumentProcessingState from workflow
        
    Returns:
        Dictionary with analysis metrics
    """
    document = state.get('document')
    layout_regions = state.get('layout_regions', [])
    conflicts = state.get('conflicts', [])
    
    # Calculate confidence scores
    ocr_results = state.get('ocr_results', {})
    ocr_confidence = ocr_results.get('avg_confidence', 0.0)
    
    vision_results = state.get('vision_results', {})
    vision_confidence = vision_results.get('avg_confidence', 0.0)
    
    # Average confidence
    avg_confidence = (ocr_confidence + vision_confidence) / 2 if (ocr_confidence or vision_confidence) else 0.85
    
    # Count regions by type
    region_counts = {}
    for region in layout_regions:
        region_type = region.region_type if hasattr(region, 'region_type') else 'unknown'
        region_counts[region_type] = region_counts.get(region_type, 0) + 1
    
    # Extract text length
    text_length = len(document.text) if document and hasattr(document, 'text') and document.text else 0
    
    return {
        'confidence': avg_confidence,
        'total_regions': len(layout_regions),
        'region_breakdown': region_counts,
        'total_conflicts': len(conflicts),
        'text_length': text_length,
        'page_count': len(document.pages) if document and hasattr(document, 'pages') else 0,
        'processing_stage': state.get('processing_stage', 'unknown')
    }
