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
    
    # Export button
    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)
    if st.button("Export Results", type="primary", width="stretch"):
        st.info("Export functionality: Download as JSON, Excel, or Markdown")


def _render_conflict_cards(state: Optional[DocumentProcessingState]) -> None:
    """Render conflict resolution cards.
    
    Args:
        state: Processing state
    """
    # Mock conflicts for demonstration
    conflicts = [
        {
            'title': 'Discrepancy detected in Table 1',
            'text_value': '$5,000',
            'vision_value': '$50,000',
            'confidence_text': 0.85,
            'confidence_vision': 0.92
        },
        {
            'title': 'Inconsistent date format',
            'text_value': '12/31/2023',
            'vision_value': '2023-12-31',
            'confidence_text': 0.78,
            'confidence_vision': 0.88
        }
    ]
    
    for idx, conflict in enumerate(conflicts):
        st.markdown(f"""
        <div class="conflict-card">
            <p style="margin: 0; font-weight: 600; color: #FBBF24; font-size: 0.9rem;">
                {conflict['title']}
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # Values comparison
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"""
            <div style="padding: 1rem; background: #1F1F1F; border-radius: 0.5rem; border: 1px solid #404040;">
                <p style="margin: 0; font-size: 0.75rem; color: #737373; text-transform: uppercase; letter-spacing: 0.05em;">Text reads</p>
                <p style="margin: 0.5rem 0 0 0; font-weight: 700; color: #FFFFFF; font-size: 1.125rem;">{conflict['text_value']}</p>
                <p style="margin: 0.5rem 0 0 0; font-size: 0.75rem; color: #10B981;">
                    {conflict['confidence_text']:.0%} confidence
                </p>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div style="padding: 1rem; background: #1F1F1F; border-radius: 0.5rem; border: 1px solid #404040;">
                <p style="margin: 0; font-size: 0.75rem; color: #737373; text-transform: uppercase; letter-spacing: 0.05em;">Vision sees</p>
                <p style="margin: 0.5rem 0 0 0; font-weight: 700; color: #FFFFFF; font-size: 1.125rem;">{conflict['vision_value']}</p>
                <p style="margin: 0.5rem 0 0 0; font-size: 0.75rem; color: #3B82F6;">
                    {conflict['confidence_vision']:.0%} confidence
                </p>
            </div>
            """, unsafe_allow_html=True)
        
        # Action buttons
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            st.button(
                "Accept Text",
                key=f"accept_text_{idx}",
                type="secondary",
                width='stretch'
            )
        with btn_col2:
            st.button(
                "Accept Vision",
                key=f"accept_vision_{idx}",
                type="primary",
                width='stretch'
            )
        
        st.markdown("<div style='margin-bottom: 1rem;'></div>", unsafe_allow_html=True)
