"""Main dashboard layout for Sovereign-Doc Streamlit UI.

This module implements the three-column layout:
- Left (50%): Document viewer with bounding boxes
- Center (30%): Extraction results and processing status
- Right (20%): Conflict monitor and resolution interface
"""

from typing import Optional

import streamlit as st
from loguru import logger

from local_body.ui.viewer import DocumentViewer
from local_body.ui.conflicts import render_conflict_panel, render_conflict_summary_widget
from local_body.orchestration.state import DocumentProcessingState, ProcessingStage
from local_body.core.datamodels import ResolutionStatus


def render_main_dashboard(state: DocumentProcessingState) -> None:
    """Render the main three-column dashboard.
    
    Args:
        state: Current document processing state
    """
    # Page header
    st.title("📄 Sovereign-Doc Document Processor")
    
    # Get document info
    document = state.get('document')
    if not document:
        st.error("No document loaded")
        return
    
    # Processing stage indicator
    stage = state.get('processing_stage', ProcessingStage.INGEST)
    _render_processing_status(stage)
    
    st.divider()
    
    # Three-column layout: 2:1.2:0.8 ratio (50%, 30%, 20%)
    col1, col2, col3 = st.columns([2, 1.2, 0.8])
    
    # COLUMN 1: Document Viewer
    with col1:
        _render_document_viewer(state)
    
    # COLUMN 2: Extraction Results
    with col2:
        _render_extraction_results(state)
    
    # COLUMN 3: Conflict Monitor
    with col3:
        _render_conflict_monitor(state)


def _render_processing_status(stage: ProcessingStage) -> None:
    """Render processing stage indicator with progress bar.
    
    Args:
        stage: Current processing stage
    """
    # Define stage progression
    stages = {
        ProcessingStage.INGEST: (0.1, "📥 Ingesting"),
        ProcessingStage.LAYOUT: (0.2, "🔍 Layout Detection"),
        ProcessingStage.OCR: (0.4, "📝 OCR Processing"),
        ProcessingStage.VISION: (0.6, "👁️ Vision Analysis"),
        ProcessingStage.VALIDATION: (0.8, "✅ Validation"),
        ProcessingStage.CONFLICT: (0.9, "⚠️ Conflicts Detected"),
        ProcessingStage.AUTO_RESOLVED: (0.95, "🤖 Auto-Resolved"),
        ProcessingStage.HUMAN_REVIEW: (0.95, "👤 Human Review"),
        ProcessingStage.COMPLETED: (1.0, "✨ Completed"),
        ProcessingStage.FAILED: (0.0, "❌ Failed")
    }
    
    progress, status_text = stages.get(stage, (0.5, str(stage)))
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.progress(progress)
    with col2:
        st.caption(status_text)


def _render_document_viewer(state: DocumentProcessingState) -> None:
    """Render document viewer with bounding boxes.
    
    Args:
        state: Current processing state
    """
    st.subheader("📄 Document Viewer")
    
    document = state.get('document')
    layout_regions = state.get('layout_regions', [])
    
    if not document or not document.pages:
        st.info("No pages to display")
        return
    
    # Page selector
    total_pages = len(document.pages)
    if total_pages > 1:
        page_number = st.slider(
            "Page",
            min_value=1,
            max_value=total_pages,
            value=1,
            key="page_selector"
        )
    else:
        page_number = 1
        st.caption(f"Page 1 of {total_pages}")
    
    # Get current page
    current_page = document.pages[page_number - 1]
    
    # Get regions for this page
    page_regions = [r for r in layout_regions if hasattr(r, 'page_number') and r.page_number == page_number]
    if not page_regions:
        # Regions might not have page_number, use all regions
        page_regions = layout_regions
    
    # Render page
    viewer = DocumentViewer()
    
    # Try to render from raw bytes first (if available)
    if hasattr(current_page, 'raw_image_bytes') and current_page.raw_image_bytes:
        viewer.render_from_bytes(current_page.raw_image_bytes, page_regions)
    elif document.file_path:
        # Fallback to PDF rendering
        viewer.render_page(document.file_path, page_number, page_regions)
    else:
        st.warning("No image data available for this page")


def _render_extraction_results(state: DocumentProcessingState) -> None:
    """Render extraction results panel.
    
    Args:
        state: Current processing state
    """
    st.subheader("📊 Extraction Results")
    
    # Get current page for filtering
    page_number = st.session_state.get('page_selector', 1)
    
    # OCR Results
    with st.expander("📝 OCR Text", expanded=False):
        ocr_results = state.get('ocr_results', {})
        
        if ocr_results and ocr_results.get('regions_processed', 0) > 0:
            st.success(f"✅ {ocr_results['regions_processed']} regions processed")
            st.caption(f"Extraction method: {ocr_results.get('extraction_method', 'unknown')}")
            
            # Show text from regions on current page
            layout_regions = state.get('layout_regions', [])
            page_regions = [r for r in layout_regions if hasattr(r, 'page_number') and r.page_number == page_number]
            
            if page_regions:
                st.caption(f"Text from {len(page_regions)} regions on page {page_number}:")
                for i, region in enumerate(page_regions[:5]):  # Limit to 5 for display
                    if hasattr(region, 'content') and region.content:
                        text = getattr(region.content, 'text', '')
                        if text:
                            st.text_area(
                                f"Region {i+1} ({region.region_type.value if hasattr(region, 'region_type') else 'unknown'})",
                                text,
                                height=60,
                                key=f"ocr_text_{i}"
                            )
        else:
            st.info("OCR not yet completed")
    
    # Vision Results
    with st.expander("👁️ Vision Analysis", expanded=False):
        vision_results = state.get('vision_results', {})
        
        if vision_results and vision_results.get('regions_analyzed', 0) > 0:
            st.success(f"✅ {vision_results['regions_analyzed']} regions analyzed")
            st.caption(f"Model: {vision_results.get('model', 'unknown')}")
            
            # Show vision summaries if available
            document = state.get('document')
            if document and document.pages:
                current_page = document.pages[page_number - 1]
                if hasattr(current_page, 'metadata') and current_page.metadata:
                    vision_summary = current_page.metadata.get('vision_summary')
                    if vision_summary:
                        st.markdown("**Page Summary:**")
                        st.info(vision_summary)
        else:
            st.info("Vision analysis not yet completed")
    
    # Validation Results
    with st.expander("✅ Validation Data", expanded=False):
        conflicts = state.get('conflicts', [])
        resolutions = state.get('resolutions', [])
        
        if conflicts:
            resolved_count = sum(1 for c in conflicts if c.resolution_status == ResolutionStatus.RESOLVED)
            st.metric("Total Conflicts", len(conflicts))
            st.metric("Resolved", resolved_count)
            st.metric("Pending", len(conflicts) - resolved_count)
        else:
            st.success("✅ No conflicts detected")
        
        if resolutions:
            st.caption(f"{len(resolutions)} resolutions applied")


def _render_conflict_monitor(state: DocumentProcessingState) -> None:
    """Render conflict resolution panel.
    
    Args:
        state: Current processing state
    """
    # Get document ID
    document = state.get('document')
    if not document:
        st.info("No document loaded")
        return
    
    doc_id = document.id
    
    # Check if we have conflicts in the state
    conflicts = state.get('conflicts', [])
    
    if not conflicts:
        st.success("✅ No conflicts")
        return
    
    # Use the conflict resolution panel
    # Note: checkpoint_dir should ideally come from config
    checkpoint_dir = st.session_state.get('checkpoint_dir', 'test_checkpoint')
    
    try:
        render_conflict_panel(doc_id=doc_id, checkpoint_dir=checkpoint_dir)
    except Exception as e:
        logger.error(f"Error rendering conflict panel: {e}")
        st.error(f"Could not load conflict panel: {str(e)}")
        
        # Fallback to simple display
        st.caption(f"**{len(conflicts)} conflicts detected**")
        for i, conflict in enumerate(conflicts[:3]):
            with st.container():
                st.caption(f"Conflict #{i+1}: {conflict.conflict_type.value}")
                st.caption(f"Impact: {conflict.impact_score:.2f}")
                st.divider()


def render_upload_ui() -> None:
    """Render document upload interface (placeholder for Task 9.3).
    
    This will be fully implemented in Task 9.3.
    """
    st.title("📄 Sovereign-Doc Document Processor")
    st.markdown("### Upload a Document to Begin")
    
    uploaded_file = st.file_uploader(
        "Choose a PDF file",
        type=['pdf'],
        help="Upload a financial document for processing"
    )
    
    if uploaded_file is not None:
        st.success(f"✅ Uploaded: {uploaded_file.name}")
        st.info("Processing functionality will be implemented in Task 9.3")
        
        # Placeholder for processing button
        if st.button("🚀 Start Processing", type="primary"):
            st.warning("Processing pipeline integration coming in Task 9.3")
    else:
        # Show demo/help
        with st.expander("ℹ️ About Sovereign-Doc"):
            st.markdown("""
            **Sovereign-Doc** is an intelligent document processing system that combines:
            
            - 🔍 **Layout Detection** (YOLOv8)
            - 📝 **OCR** (PaddleOCR)
            - 👁️ **Vision Analysis** (Qwen-VL)
            - ✅ **Validation & Conflict Resolution**
            - 🔍 **Hybrid Search** (Dense + Sparse vectors)
            
            Upload a PDF to get started!
            """)
