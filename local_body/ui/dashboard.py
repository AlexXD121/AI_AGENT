"""Professional analysis dashboard with split-screen layout.

Left: Document viewer with regions
Right: Analysis report with conflicts and data
"""

from typing import Optional, Dict, Any

import streamlit as st
from loguru import logger

from local_body.ui.viewer import DocumentViewer
from local_body.orchestration.state import DocumentProcessingState


def render_analysis_dashboard(state: Optional[DocumentProcessingState]) -> None:
    """Render the professional split-screen analysis dashboard.
    
    Args:
        state: Current processing state
    """
    # Header with reset button
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("## Analysis Report")
    with col2:
        if st.button("New Document", type="secondary", width='stretch'):
            st.session_state['processing_complete'] = False
            st.rerun()
    
    st.divider()
    
    # Split screen layout (60:40)
    left_col, right_col = st.columns([6, 4])
    
    # Left: Document viewer
    with left_col:
        _render_document_source(state)
    
    # Right: Intelligence panel
    with right_col:
        _render_intelligence_panel(state)


def _render_document_source(state: Optional[DocumentProcessingState]) -> None:
    """Render the document viewer panel.
    
    Args:
        state: Processing state
    """
    st.markdown("### Source Document")
    
    # Document name
    doc_name = st.session_state.get('document_name', 'Document')
    st.caption(f"**{doc_name}**")
    
    st.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)
    
    # Render document if available
    if state and state.get('document'):
        document = state['document']
        layout_regions = state.get('layout_regions', [])
        
        # Page selector if multi-page
        if hasattr(document, 'pages') and len(document.pages) > 1:
            page_number = st.slider(
                "Page",
                min_value=1,
                max_value=len(document.pages),
                value=1,
                key="page_selector"
            )
        else:
            page_number = 1
        
        # Render page with regions
        viewer = DocumentViewer()
        
        try:
            if hasattr(document, 'file_path') and document.file_path:
                viewer.render_page(document.file_path, page_number, layout_regions)
            else:
                st.info("Document preview not available")
        except Exception as e:
            logger.error(f"Viewer error: {e}")
            st.warning("Could not render document preview")
    
    else:
        # Placeholder
        st.markdown("""
        <div style="
            background: #F9FAFB;
            border: 2px dashed #D1D5DB;
            border-radius: 0.5rem;
            padding: 4rem 2rem;
            text-align: center;
            color: #9CA3AF;
        ">
            <p>Document preview will appear here</p>
        </div>
        """, unsafe_allow_html=True)


def _render_intelligence_panel(state: Optional[DocumentProcessingState]) -> None:
    """Render the intelligence/analysis panel.
    
    Args:
        state: Processing state
    """
    # Section 1: Executive Summary
    st.markdown("### Executive Summary")
    
    analysis_data = st.session_state.get('analysis_data', {})
    
    # Get REAL values from analysis_data
    confidence = analysis_data.get('confidence', 0.0)
    total_regions = analysis_data.get('fields_extracted', 0)
    
    # Metrics with REAL data
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Confidence", f"{confidence:.0%}")
    with col2:
        st.metric("Regions", total_regions)
    
    # Document metadata - show real data
    total_pages = analysis_data.get('total_pages', 1)
    text_regions = analysis_data.get('text_regions', 0)
    table_regions = analysis_data.get('table_regions', 0)
    
    st.markdown(f"""
    <div class="professional-card" style="margin-top: 1rem;">
        <p style="margin: 0; color: #737373; font-size: 0.875rem; text-transform: uppercase; letter-spacing: 0.05em;">Document Type</p>
        <p style="margin: 0.5rem 0 0 0; font-weight: 600; color: #E5E5E5; font-size: 1rem;">{analysis_data.get('doc_type', 'PDF Document')}</p>
        
        <p style="margin: 1.25rem 0 0 0; color: #737373; font-size: 0.875rem; text-transform: uppercase; letter-spacing: 0.05em;">Pages</p>
        <p style="margin: 0.5rem 0 0 0; font-weight: 600; color: #E5E5E5; font-size: 1rem;">{total_pages} page(s)</p>
        
        <p style="margin: 1.25rem 0 0 0; color: #737373; font-size: 0.875rem; text-transform: uppercase; letter-spacing: 0.05em;">Detected Regions</p>
        <p style="margin: 0.5rem 0 0 0; font-weight: 600; color: #E5E5E5; font-size: 1rem;">{text_regions} text, {table_regions} tables</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.divider()
    
    # Section 2: Attention Required
    st.markdown("### Attention Required")
    
    conflicts_count = analysis_data.get('conflicts_count', 0)
    
    if conflicts_count > 0:
        _render_conflict_cards(state)
    else:
        st.markdown("""
        <div class="professional-card" style="background: #ECFDF5; border-color: #10B981;">
            <p style="margin: 0; color: #065F46; font-weight: 500;">
                No conflicts detected
            </p>
            <p style="margin: 0.5rem 0 0 0; color: #059669; font-size: 0.875rem;">
                All data verified successfully
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    st.divider()
    
    # Section 3: Extracted Data
    st.markdown("### Extracted Data")
    
    # Get real document data
    document = st.session_state.get('document')
    layout_regions = st.session_state.get('layout_regions', [])
    
    if document and hasattr(document, 'pages') and document.pages:
        # Extract text from all pages
        extracted_items = []
        
        for page in document.pages:
            for region in page.regions:
                if hasattr(region, 'content'):
                    # Extract text content
                    text = ""
                    region_type = region.region_type.value if hasattr(region, 'region_type') else 'unknown'
                    confidence = region.confidence if hasattr(region, 'confidence') else 0.0
                    
                    if hasattr(region.content, 'text'):
                        text = region.content.text[:100]  # First 100 chars
                    elif hasattr(region.content, 'rows'):  # Table
                        text = f"Table with {len(region.content.rows)} rows"
                    
                    if text:
                        extracted_items.append({
                            'Page': page.page_number,
                            'Type': region_type.title(),
                            'Content': text,
                            'Confidence': f"{confidence:.0%}"
                        })
        
        if extracted_items:
            import pandas as pd
            df = pd.DataFrame(extracted_items)
            st.dataframe(df, width="stretch", hide_index=True)
        else:
            st.info("No text regions extracted yet. Basic layout detection needs YOLOv8 model.")
    else:
        st.info("No extracted data available yet. Upload a document to begin processing.")
    
    # Action buttons
    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Save to Knowledge Base button (primary action)
        if st.button("💾 Save to Knowledge Base", type="primary", use_container_width=True):
            import asyncio
            from local_body.database.vector_store import DocumentVectorStore
            
            try:
                with st.spinner("Indexing document to vector database..."):
                    # Get document from state
                    document = state.get('document') if state else None
                    
                    if document:
                        # Initialize vector store
                        vector_store = DocumentVectorStore()
                        
                        # Ingest document (handle async)
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            loop.run_until_complete(vector_store.ingest_document(document))
                        finally:
                            loop.close()
                        
                        # Success!
                        st.toast("✅ Document indexed successfully!", icon="✅")
                        st.balloons()
                        st.success(f"Document '{document.file_path}' saved to knowledge base!")
                    else:
                        st.error("No document available to save")
                        
            except Exception as e:
                st.error(f"Failed to save to knowledge base: {str(e)}")
                logger.error(f"Vector store save error: {e}")
    
    with col2:
        # Export button (secondary action)
        if st.button("📤 Export Results", type="secondary", use_container_width=True):
            st.info("Export functionality: Download as JSON, Excel, or Markdown")


def _render_conflict_cards(state: Optional[DocumentProcessingState]) -> None:
    """Render conflict resolution cards with REAL conflict data.
    
    Args:
        state: Processing state with real conflicts from workflow
    """
    if not state:
        st.info("No state available")
        return
    
    # Get real conflicts from workflow state
    conflicts = state.get('conflicts', [])
    
    if not conflicts:
        st.success("✅ No conflicts detected - all extractions match!")
        return
    
    st.caption(f"{len(conflicts)} conflict(s) detected")
    
    # Render each real conflict
    for idx, conflict in enumerate(conflicts):
        # Extract conflict properties (handle both object attributes and dict keys)
        conflict_type = getattr(conflict, 'conflict_type', conflict.get('conflict_type', 'Data Mismatch') if isinstance(conflict, dict) else 'Data Mismatch')
        impact = getattr(conflict, 'impact_score', conflict.get('impact_score', 0.5) if isinstance(conflict, dict) else 0.5)
        
        source_a = getattr(conflict, 'source_a', conflict.get('source_a', 'OCR') if isinstance(conflict, dict) else 'OCR')
        source_b = getattr(conflict, 'source_b', conflict.get('source_b', 'Vision') if isinstance(conflict, dict) else 'Vision')
        
        value_a = str(getattr(conflict, 'value_a', conflict.get('value_a', 'N/A') if isinstance(conflict, dict) else 'N/A'))
        value_b = str(getattr(conflict, 'value_b', conflict.get('value_b', 'N/A') if isinstance(conflict, dict) else 'N/A'))
        
        confidence_a = getattr(conflict, 'confidence_a', conflict.get('confidence_a', 0.0) if isinstance(conflict, dict) else 0.0)
        confidence_b = getattr(conflict, 'confidence_b', conflict.get('confidence_b', 0.0) if isinstance(conflict, dict) else 0.0)
        
        # Determine severity color
        if impact >= 0.7:
            title_color = "#EF4444"  # Red - High Impact
        elif impact >= 0.4:
            title_color = "#FBBF24"  # Yellow - Medium
        else:
            title_color = "#10B981"  # Green - Low
        
        # Conflict card header
        st.markdown(f"""
        <div class="conflict-card">
            <p style="margin: 0; font-weight: 600; color: {title_color}; font-size: 0.9rem;">
                Conflict #{idx + 1}: {conflict_type}
            </p>
            <p style="margin: 0.25rem 0 0 0; font-size: 0.75rem; color: #737373;">
                Impact Score: {impact:.2f}
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # Values comparison (side-by-side)
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown(f"""
            <div style="padding: 1rem; background: #1F1F1F; border-radius: 0.5rem; border: 1px solid #404040;">
                <p style="margin: 0; font-size: 0.75rem; color: #737373; text-transform: uppercase; letter-spacing: 0.05em;">
                    {source_a}
                </p>
                <p style="margin: 0.5rem 0 0 0; font-weight: 700; color: #FFFFFF; font-size: 1.125rem;">
                    {value_a}
                </p>
                <p style="margin: 0.5rem 0 0 0; font-size: 0.75rem; color: #10B981;">
                    {confidence_a:.0%} confidence
                </p>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div style="padding: 1rem; background: #1F1F1F; border-radius: 0.5rem; border: 1px solid #404040;">
                <p style="margin: 0; font-size: 0.75rem; color: #737373; text-transform: uppercase; letter-spacing: 0.05em;">
                    {source_b}
                </p>
                <p style="margin: 0.5rem 0 0 0; font-weight: 700; color: #FFFFFF; font-size: 1.125rem;">
                    {value_b}
                </p>
                <p style="margin: 0.5rem 0 0 0; font-size: 0.75rem; color: #3B82F6;">
                    {confidence_b:.0%} confidence
                </p>
            </div>
            """, unsafe_allow_html=True)
        
        # Check for resolution
        resolutions = state.get('resolutions', [])
        conflict_id = getattr(conflict, 'id', conflict.get('id', None) if isinstance(conflict, dict) else None)
        
        if conflict_id and resolutions:
            # Find matching resolution
            resolution = next(
                (r for r in resolutions 
                 if (getattr(r, 'conflict_id', None) == conflict_id or 
                     (isinstance(r, dict) and r.get('conflict_id') == conflict_id))),
                None
            )
            
            if resolution:
                chosen_value = getattr(resolution, 'chosen_value', resolution.get('chosen_value', 'N/A') if isinstance(resolution, dict) else 'N/A')
                method = getattr(resolution, 'resolution_method', resolution.get('resolution_method', 'auto') if isinstance(resolution, dict) else 'auto')
                
                st.success(f"✓ Resolved ({method}): {chosen_value}")
        
        # Action buttons
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            st.button(
                f"Accept {source_a}",
                key=f"accept_a_{idx}",
                type="secondary",
                use_container_width=True
            )
        
        with btn_col2:
            st.button(
                f"Accept {source_b}",
                key=f"accept_b_{idx}",
                type="primary",
                use_container_width=True
            )
        
        st.markdown("<div style='margin-bottom: 1.5rem;'></div>", unsafe_allow_html=True)

