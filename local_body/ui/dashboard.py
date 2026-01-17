"""Professional analysis dashboard with tabbed layout.

Top: High-level metrics
Tabs: Executive Summary, Conflict Resolution, Document Viewer, Analytics, Raw Data
"""

from typing import Optional, Dict, Any

import streamlit as st
from loguru import logger
import plotly.express as px
import plotly.graph_objects as go

from local_body.ui.viewer import DocumentViewer
from local_body.ui.conflicts import render_conflict_panel
from local_body.orchestration.state import DocumentProcessingState


def render_analysis_dashboard(state: Optional[DocumentProcessingState]) -> None:
    """Render the professional tabbed analysis dashboard.
    
    Args:
        state: Current processing state
    """
    try:
        logger.info("=== DASHBOARD RENDER STARTED ===")
        logger.info(f"State type: {type(state)}, State is dict: {isinstance(state, dict)}")
        
        if state and isinstance(state, dict):
            logger.info(f"State keys: {list(state.keys())[:10]}")  # First 10 keys
        
        # 1. Header and Global Actions
        col1, col2 = st.columns([3, 1])
        with col1:
            doc_name = st.session_state.get('document_name', 'Document')
            st.markdown(f"## {doc_name}")
        with col2:
            if st.button("New Document", type="secondary", width="stretch"):
                st.session_state['processing_complete'] = False
                st.rerun()
        
        st.divider()

        # Debug: Check if state exists
        if not state:
            st.error("No processing state found. Please re-upload your document.")
            logger.error("Dashboard called with None/empty state!")
            return

        logger.info("Rendering KPIs...")
        
        # Get analysis data
        analysis_data = st.session_state.get('analysis_data', {})
        logger.info(f"Analysis data: {len(analysis_data)} keys")

        # 2. Top Level Metrics (KPIs)
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        
        # KPI 1: Confidence
        confidence = analysis_data.get('confidence', 0.0)
        conf_delta = "High Confidence" if confidence > 0.8 else "Review Needed"
        conf_color = "normal" if confidence > 0.8 else "inverse"
        
        kpi1.metric("Avg Confidence", f"{confidence:.1%}", conf_delta)

        # KPI 2: Pages
        pages = analysis_data.get('total_pages', len(state.get('document', {}).pages) if state.get('document') and hasattr(state.get('document'), 'pages') else 0)
        kpi2.metric("Pages Processed", pages)

        # KPI 3: Conflicts
        conflicts_count = len(state.get('conflicts', []))
        conflict_delta = f"{conflicts_count} active"
        kpi3.metric("Conflicts Detected", conflicts_count, conflict_delta, delta_color="inverse")

        # KPI 4: Regions
        regions = analysis_data.get('total_regions', 0)
        kpi4.metric("Extracted Fields", regions)

        st.markdown("<div style='margin-bottom: 2rem;'></div>", unsafe_allow_html=True)

        logger.info("Rendering tabs...")
        
        # 3. Main Tabbed Interface
        tab_summary, tab_conflicts, tab_viewer, tab_analytics, tab_data = st.tabs([
            "Executive Summary", 
            "Conflict Resolution", 
            "Document Viewer",
            "Analytics",
            "Raw Data"
        ])

        # --- TAB 1: EXECUTIVE SUMMARY ---
        with tab_summary:
            logger.info("Rendering summary tab...")
            st.markdown("### Document Summary")
            
            # Summary Content (extracted text preview)
            document = state.get('document')
            if document and hasattr(document, 'text') and document.text:
                text_preview = document.text[:1000] + "..." if len(document.text) > 1000 else document.text
                st.text_area("Extracted Text Content", text_preview, height=200)
            else:
                st.info("No text content extracted available for summary.")

            st.markdown("### Key Extractions")
            
            # Extracted Data Table
            if document and hasattr(document, 'pages'):
                 # Reuse extraction logic
                extracted_items = []
                for page in document.pages:
                    for region in page.regions:
                        if hasattr(region, 'content'):
                            val = region.content.text if hasattr(region.content, 'text') else (f"Table ({len(region.content.rows)} rows)" if hasattr(region.content, 'rows') else "")
                            if val:
                                extracted_items.append({
                                    "Page": page.page_number,
                                    "Content": val[:100],
                                    "Confidence": f"{region.confidence:.1%}" if hasattr(region, 'confidence') else "N/A"
                                })
                
                if extracted_items:
                    st.dataframe(extracted_items, width="stretch")
                else:
                    st.caption("No specific fields extracted.")

        # --- TAB 2: CONFLICT RESOLUTION ---
        with tab_conflicts:
            logger.info("Rendering conflicts tab...")
             # Use the dedicated conflict panel component we optimized
             doc_id = document.id if document and hasattr(document, 'id') else "unknown"
             conflicts = state.get('conflicts', [])
             
             render_conflict_panel(doc_id, conflicts=conflicts)

        # --- TAB 3: DOCUMENT VIEWER ---
        with tab_viewer:
            logger.info("Rendering viewer tab...")
            _render_document_viewer_tab(state)

        # --- TAB 4: ANALYTICS ---
        with tab_analytics:
            logger.info("Rendering analytics tab...")
            _render_analytics_tab(state)

        # --- TAB 5: RAW DATA ---
        with tab_data:
            logger.info("Rendering raw data tab...")
            st.markdown("### System State Inspection")
            st.json(state, expanded=False)
        
        logger.info("=== DASHBOARD RENDER COMPLETE ===")
        
    except Exception as e:
        logger.exception(f"Dashboard rendering failed: {e}")
        st.error(f"Error rendering dashboard: {e}")
        st.expander("Error Details").code(str(e))


def _render_document_viewer_tab(state: Dict[str, Any]):
    """Render the document viewer content inside the tab."""
    document = state.get('document')
    layout_regions = state.get('layout_regions', [])
    
    if document:
        col_ctrl, col_view = st.columns([1, 5])
        
        # Initialize Viewer
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
                # Use temp path if available for rendering
                if hasattr(document, 'file_path') and document.file_path:
                    viewer.render_page(document.file_path, page_num, layout_regions)
                elif 'temp_file_path' in st.session_state:
                     viewer.render_page(st.session_state['temp_file_path'], page_num, layout_regions)
                else:
                    st.warning("Document source file not found for preview.")
            except Exception as e:
                st.error(f"Error rendering preview: {e}")
    else:
        st.warning("No document loaded.")


def _render_analytics_tab(state: Dict[str, Any]):
    """Render analytics visualizations using Plotly.
    
    Args:
        state: Processing state with document data
    """
    st.markdown("### Document Analytics")
    
    document = state.get('document')
    conflicts = state.get('conflicts', [])
    
    if not document:
        st.info("No document data available for analytics.")
        return
    
    # === GRAPH A: Content Composition (Donut Chart) ===
    st.markdown("####Content Composition")
    
    if hasattr(document, 'pages') and document.pages:
        # Count region types across all pages
        region_counts = {}
        for page in document.pages:
            for region in page.regions:
                region_type = region.region_type.value if hasattr(region, 'region_type') else 'unknown'
                region_counts[region_type] = region_counts.get(region_type, 0) + 1
        
        if region_counts:
            # Create donut chart
            fig = px.pie(
                names=list(region_counts.keys()),
                values=list(region_counts.values()),
                title="Document Structure by Region Type",
                hole=0.4,  # Makes it a donut chart
                color_discrete_sequence=px.colors.sequential.Blues_r
            )
            fig.update_traces(textposition='inside', textinfo='percent+label')
            fig.update_layout(
                showlegend=True,
                height=400,
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font_color='#E5E5E5'
            )
            st.plotly_chart(fig, key="content_composition")
        else:
            st.caption("No regions detected.")
    else:
        st.caption("No page data available.")
    
    st.divider()
    
    # === GRAPH B: Confidence Analysis (Bar Chart) ===
    st.markdown("#### Confidence Analysis by Page")
    
    if hasattr(document, 'pages') and document.pages:
        # Extract confidence scores per page
        page_data = []
        for page in document.pages:
            ocr_confidences = []
            for region in page.regions:
                if hasattr(region, 'confidence'):
                    ocr_confidences.append(region.confidence)
            
            avg_ocr_conf = sum(ocr_confidences) / len(ocr_confidences) if ocr_confidences else 0.0
            
            page_data.append({
                'Page': page.page_number,
                'OCR Confidence': avg_ocr_conf,
                'Source': 'OCR'
            })
        
        # Vision confidence (if available)
        vision_results = state.get('vision_results', {})
        for page_num, vision_data in vision_results.items():
            if isinstance(vision_data, dict) and 'confidence' in vision_data:
                page_data.append({
                    'Page': page_num,
                    'OCR Confidence': vision_data['confidence'],
                    'Source': 'Vision'
                })
        
        if page_data:
            # Create grouped bar chart
            import pandas as pd
            df = pd.DataFrame(page_data)
            
            fig = px.bar(
                df,
                x='Page',
                y='OCR Confidence',
                color='Source',
                title="Confidence Scores Across Pages",
                barmode='group',
                color_discrete_map={'OCR': '#3B82F6', 'Vision': '#8B5CF6'}
            )
            fig.update_layout(
                yaxis_title="Confidence Score",
                xaxis_title="Page Number",
                yaxis_range=[0, 1],
                height=400,
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font_color='#E5E5E5'
            )
            st.plotly_chart(fig, key="confidence_analysis")
        else:
            st.caption("No confidence data available.")
    else:
        st.caption("No page data available.")
    
    st.divider()
    
    # === GRAPH C: Conflict Impact Analysis (Scatter Plot) ===
    st.markdown("#### Conflict Impact Analysis")
    
    if conflicts:
        # Extract conflict data
        conflict_data = []
        for conflict in conflicts:
            # Handle both object attributes and dict keys
            page_num = getattr(conflict, 'page_number', conflict.get('page_number', 1) if isinstance(conflict, dict) else 1)
            impact = getattr(conflict, 'impact_score', conflict.get('impact_score', 0.5) if isinstance(conflict, dict) else 0.5)
            conflict_type = str(getattr(conflict, 'conflict_type', conflict.get('conflict_type', 'Unknown') if isinstance(conflict, dict) else 'Unknown'))
            
            # Get conflicting values for tooltip
            value_a = str(getattr(conflict, 'text_value', conflict.get('text_value', 'N/A') if isinstance(conflict, dict) else 'N/A'))[:30]
            value_b = str(getattr(conflict, 'vision_value', conflict.get('vision_value', 'N/A') if isinstance(conflict, dict) else 'N/A'))[:30]
            
            conflict_data.append({
                'Page': page_num,
                'Impact Score': impact,
                'Type': conflict_type,
                'Details': f"OCR: {value_a} | Vision: {value_b}"
            })
        
        if conflict_data:
            import pandas as pd
            df = pd.DataFrame(conflict_data)
            
            fig = px.scatter(
                df,
                x='Page',
                y='Impact Score',
                color='Type',
                size='Impact Score',
                hover_data=['Details'],
                title="Conflict Severity Distribution",
                color_discrete_sequence=px.colors.qualitative.Set2
            )
            fig.update_layout(
                yaxis_title="Impact Score (Severity)",
                xaxis_title="Page Number",
                yaxis_range=[0, 1],
                height=400,
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font_color='#E5E5E5'
            )
            st.plotly_chart(fig, key="conflict_impact")
        else:
            st.caption("No conflict data to visualize.")
    else:
        st.success("No conflicts detected - all extractions are consistent!")
