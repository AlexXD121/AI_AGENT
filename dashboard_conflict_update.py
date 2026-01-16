"""
Dashboard conflict rendering update for LangGraph integration.

INSTRUCTIONS:
Replace the _render_conflict_cards() function in local_body/ui/dashboard.py (lines 214-289)
with this version to use REAL conflict data from DocumentProcessingState.
"""


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
        conflict_type = getattr(conflict, 'conflict_type', conflict.get('conflict_type', 'Data Mismatch'))
        impact = getattr(conflict, 'impact_score', conflict.get('impact_score', 0.5))
        
        source_a = getattr(conflict, 'source_a', conflict.get('source_a', 'OCR'))
        source_b = getattr(conflict, 'source_b', conflict.get('source_b', 'Vision'))
        
        value_a = str(getattr(conflict, 'value_a', conflict.get('value_a', 'N/A')))
        value_b = str(getattr(conflict, 'value_b', conflict.get('value_b', 'N/A')))
        
        confidence_a = getattr(conflict, 'confidence_a', conflict.get('confidence_a', 0.0))
        confidence_b = getattr(conflict, 'confidence_b', conflict.get('confidence_b', 0.0))
        
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
        conflict_id = getattr(conflict, 'id', conflict.get('id', None))
        
        if conflict_id and resolutions:
            # Find matching resolution
            resolution = next(
                (r for r in resolutions 
                 if getattr(r, 'conflict_id', r.get('conflict_id')) == conflict_id),
                None
            )
            
            if resolution:
                chosen_value = getattr(resolution, 'chosen_value', resolution.get('chosen_value', 'N/A'))
                method = getattr(resolution, 'resolution_method', resolution.get('resolution_method', 'auto'))
                
                st.success(f"✓ Resolved ({method}): {chosen_value}")
        
        # Action buttons
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            if st.button(f"Accept {source_a}", key=f"accept_a_{idx}", type="secondary", use_container_width=True):
                st.info(f"Selected {source_a} value: {value_a}")
        
        with btn_col2:
            if st.button(f"Accept {source_b}", key=f"accept_b_{idx}", type="primary", use_container_width=True):
                st.success(f"Selected {source_b} value: {value_b}")
        
        st.markdown("<div style='margin-bottom: 1.5rem;'></div>", unsafe_allow_html=True)
