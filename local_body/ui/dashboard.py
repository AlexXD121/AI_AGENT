"""Professional analysis dashboard with modular architecture.

Provides tabbed interface for document analysis results with clean
separation of concerns and testable components.
"""

from typing import Optional, Dict, Any, List
import streamlit as st
from loguru import logger

from local_body.ui.viewer import DocumentViewer
from local_body.ui.conflicts import render_conflict_panel
from local_body.ui.charts import (
    create_composition_chart,
    create_confidence_chart,
    create_conflict_scatter
)
from local_body.orchestration.state import DocumentProcessingState


def render_analysis_dashboard(state: Optional[DocumentProcessingState]) -> None:
    """Render complete analysis dashboard with tabs and metrics.
    
    Args:
        state: Current document processing state from workflow
    """
    try:
        logger.info("=== DASHBOARD RENDER STARTED ===")
        logger.info(f"State type: {type(state)}, State is dict: {isinstance(state, dict)}")
        
        if state and isinstance(state, dict):
            logger.info(f"State keys: {list(state.keys())[:10]}")
        
        _render_header()
        
        if not state:
            st.error("No processing state found. Please re-upload your document.")
            logger.error("Dashboard called with None/empty state!")
            return

        logger.info("Rendering KPIs...")
        
        analysis_data = st.session_state.get('analysis_data', {})
        logger.info(f"Analysis data: {len(analysis_data)} keys")

        _render_metrics_row(state, analysis_data)
        
        st.markdown("<div style='margin-bottom: 2rem;'></div>", unsafe_allow_html=True)

        logger.info("Rendering tabs...")
        
        _render_tabbed_content(state)
        
        logger.info("=== DASHBOARD RENDER COMPLETE ===")
        
    except Exception as e:
        logger.exception(f"Dashboard rendering failed: {e}")
        st.error(f"Error rendering dashboard: {e}")
        with st.expander("Error Details"):
            st.code(str(e))


def _render_header() -> None:
    """Render dashboard header with document name and action buttons."""
    col1, col2 = st.columns([3, 1])
    
    with col1:
        doc_name = st.session_state.get('document_name', 'Document')
        st.markdown(f"## {doc_name}")
    
    with col2:
        if st.button("New Document", type="secondary", width="stretch"):
            st.session_state['processing_complete'] = False
            st.rerun()
    
    st.divider()


def _render_metrics_row(state: Dict[str, Any], analysis_data: Dict[str, Any]) -> None:
    """Render top-level KPI metrics row.
    
    Args:
        state: Document processing state
        analysis_data: Extracted analysis metrics
    """
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    
    # Confidence metric
    confidence = analysis_data.get('confidence', 0.0)
    conf_delta = "High Confidence" if confidence > 0.8 else "Review Needed"
    kpi1.metric("Avg Confidence", f"{confidence:.1%}", conf_delta)

    # Pages metric
    pages = analysis_data.get('total_pages', 
        len(state.get('document', {}).pages) if state.get('document') and hasattr(state.get('document'), 'pages') else 0
    )
    kpi2.metric("Pages Processed", pages)

    # Conflicts metric
    conflicts_count = len(state.get('conflicts', []))
    conflict_delta = f"{conflicts_count} active"
    kpi3.metric("Conflicts Detected", conflicts_count, conflict_delta, delta_color="inverse")

    # Regions metric
    regions = analysis_data.get('total_regions', 0)
    kpi4.metric("Extracted Fields", regions)


def _render_tabbed_content(state: Dict[str, Any]) -> None:
    """Render main tabbed interface with all content sections.
    
    Args:
        state: Document processing state
    """
    tab_summary, tab_conflicts, tab_viewer, tab_analytics, tab_data = st.tabs([
        "Executive Summary", 
        "Conflict Resolution", 
        "Document Viewer",
        "Analytics",
        "Raw Data"
    ])

    with tab_summary:
        logger.info("Rendering summary tab...")
        _render_executive_summary_tab(state)

    with tab_conflicts:
        logger.info("Rendering conflicts tab...")
        _render_conflict_tab(state)

    with tab_viewer:
        logger.info("Rendering viewer tab...")
        _render_viewer_tab(state)

    with tab_analytics:
        logger.info("Rendering analytics tab...")
        _render_analytics_tab(state)

    with tab_data:
        logger.info("Rendering raw data tab...")
        st.markdown("### System State Inspection")
        st.json(state, expanded=False)


def _render_executive_summary_tab(state: Dict[str, Any]) -> None:
    """Render executive summary with text preview and key extractions.
    
    Args:
        state: Document processing state
    """
    st.markdown("### Document Summary")
    
    document = state.get('document')
    
    # Text preview
    if document and hasattr(document, 'text') and document.text:
        text_preview = document.text[:1000] + "..." if len(document.text) > 1000 else document.text
        st.text_area("Extracted Text Content", text_preview, height=200)
    else:
        st.info("No text content extracted available for summary.")

    st.markdown("### Key Extractions")
    
    # Extracted data table
    if document and hasattr(document, 'pages'):
        extracted_items = _extract_items_from_pages(document.pages)
        
        if extracted_items:
            st.dataframe(extracted_items, width="stretch")
        else:
            st.caption("No specific fields extracted.")


def _extract_items_from_pages(pages: List[Any]) -> List[Dict[str, Any]]:
    """Extract displayable items from document pages.
    
    Args:
        pages: List of page objects with regions
        
    Returns:
        List of dictionaries with page, content, and confidence data
    """
    items = []
    
    for page in pages:
        for region in page.regions:
            if hasattr(region, 'content'):
                val = region.content.text if hasattr(region.content, 'text') else (
                    f"Table ({len(region.content.rows)} rows)" if hasattr(region.content, 'rows') else ""
                )
                if val:
                    items.append({
                        "Page": page.page_number,
                        "Content": val[:100],
                        "Confidence": f"{region.confidence:.1%}" if hasattr(region, 'confidence') else "N/A"
                    })
    
    return items


def _render_conflict_tab(state: Dict[str, Any]) -> None:
    """Render conflict resolution interface.
    
    Args:
        state: Document processing state
    """
    document = state.get('document')
    doc_id = document.id if document and hasattr(document, 'id') else "unknown"
    conflicts = state.get('conflicts', [])
    
    render_conflict_panel(doc_id, conflicts=conflicts)


def _render_viewer_tab(state: Dict[str, Any]) -> None:
    """Render document viewer with page navigation.
    
    Args:
        state: Document processing state
    """
    document = state.get('document')
    layout_regions = state.get('layout_regions', [])
    
    if not document:
        st.warning("No document loaded.")
        return
    
    col_ctrl, col_view = st.columns([1, 5])
    
    viewer = DocumentViewer()
    
    with col_ctrl:
        st.markdown("#### Page Control")
        if hasattr(document, 'pages') and len(document.pages) > 1:
            page_num = st.number_input("Page Number", min_value=1, max_value=len(document.pages), value=1)
        else:
            page_num = 1
            st.caption("Single Page Document")
            
    with col_view:
        try:
            if hasattr(document, 'file_path') and document.file_path:
                viewer.render_page(document.file_path, page_num, layout_regions)
            elif 'temp_file_path' in st.session_state:
                 viewer.render_page(st.session_state['temp_file_path'], page_num, layout_regions)
            else:
                st.warning("Document source file not found for preview.")
        except Exception as e:
            st.error(f"Error rendering preview: {e}")


def _render_analytics_tab(state: Dict[str, Any]) -> None:
    """Render analytics visualizations using Plotly charts.
    
    Args:
        state: Document processing state with analysis results
    """
    st.markdown("### Document Analytics")
    
    document = state.get('document')
    conflicts = state.get('conflicts', [])
    
    if not document:
        st.info("No document data available for analytics.")
        return
    
    # Content composition chart
    st.markdown("#### Content Composition")
    region_counts = _count_region_types(document)
    
    if region_counts:
        fig = create_composition_chart(region_counts)
        st.plotly_chart(fig, key="content_composition")
    else:
        st.caption("No regions detected.")
    
    st.divider()
    
    # Confidence analysis chart
    st.markdown("#### Confidence Analysis by Page")
    page_data = _extract_confidence_data(document, state)
    
    if page_data:
        fig = create_confidence_chart(page_data)
        st.plotly_chart(fig, key="confidence_analysis")
    else:
        st.caption("No confidence data available.")
    
    st.divider()
    
    # Conflict impact chart
    st.markdown("#### Conflict Impact Analysis")
    
    if conflicts:
        conflict_data = _extract_conflict_data(conflicts)
        if conflict_data:
            fig = create_conflict_scatter(conflict_data)
            st.plotly_chart(fig, key="conflict_impact")
        else:
            st.caption("No conflict data to visualize.")
    else:
        st.success("No conflicts detected - all extractions are consistent!")


def _count_region_types(document: Any) -> Dict[str, int]:
    """Count occurrences of each region type in document.
    
    Args:
        document: Document object with pages and regions
        
    Returns:
        Dictionary mapping region types to counts
    """
    if not hasattr(document, 'pages') or not document.pages:
        return {}
    
    counts = {}
    for page in document.pages:
        for region in page.regions:
            region_type = region.region_type.value if hasattr(region, 'region_type') else 'unknown'
            counts[region_type] = counts.get(region_type, 0) + 1
    
    return counts


def _extract_confidence_data(document: Any, state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract confidence scores per page for visualization.
    
    Args:
        document: Document object with pages
        state: Processing state with vision results
        
    Returns:
        List of dictionaries with page, confidence, and source data
    """
    if not hasattr(document, 'pages') or not document.pages:
        return []
    
    data = []
    
    # OCR confidence scores
    for page in document.pages:
        ocr_confidences = [
            region.confidence for region in page.regions 
            if hasattr(region, 'confidence')
        ]
        
        avg_conf = sum(ocr_confidences) / len(ocr_confidences) if ocr_confidences else 0.0
        
        data.append({
            'Page': page.page_number,
            'OCR Confidence': avg_conf,
            'Source': 'OCR'
        })
    
    # Vision confidence scores
    vision_results = state.get('vision_results', {})
    for page_num, vision_data in vision_results.items():
        if isinstance(vision_data, dict) and 'confidence' in vision_data:
            data.append({
                'Page': page_num,
                'OCR Confidence': vision_data['confidence'],
                'Source': 'Vision'
            })
    
    return data


def _extract_conflict_data(conflicts: List[Any]) -> List[Dict[str, Any]]:
    """Extract conflict data for scatter plot visualization.
    
    Args:
        conflicts: List of conflict objects
        
    Returns:
        List of dictionaries with page, impact, type, and detail data
    """
    data = []
    
    for conflict in conflicts:
        # Handle both object attributes and dict keys
        page_num = getattr(conflict, 'page_number', 
            conflict.get('page_number', 1) if isinstance(conflict, dict) else 1
        )
        impact = getattr(conflict, 'impact_score', 
            conflict.get('impact_score', 0.5) if isinstance(conflict, dict) else 0.5
        )
        conflict_type = str(getattr(conflict, 'conflict_type', 
            conflict.get('conflict_type', 'Unknown') if isinstance(conflict, dict) else 'Unknown'
        ))
        
        # Get conflicting values for tooltip
        value_a = str(getattr(conflict, 'text_value', 
            conflict.get('text_value', 'N/A') if isinstance(conflict, dict) else 'N/A'
        ))[:30]
        value_b = str(getattr(conflict, 'vision_value', 
            conflict.get('vision_value', 'N/A') if isinstance(conflict, dict) else 'N/A'
        ))[:30]
        
        data.append({
            'Page': page_num,
            'Impact Score': impact,
            'Type': conflict_type,
            'Details': f"OCR: {value_a} | Vision: {value_b}"
        })
    
    return data
