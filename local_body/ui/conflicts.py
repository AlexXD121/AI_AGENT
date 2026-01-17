"""Conflict Resolution Interface for Streamlit UI.

This module provides the conflict resolution panel where users can:
- View pending conflicts with visual evidence
- Compare OCR vs Vision values side-by-side
- Make resolution decisions (Accept OCR/Vision/Manual Override)
- View resolution history and audit trail
"""

from typing import Optional, Dict, Any, List
from io import BytesIO
from pathlib import Path

import streamlit as st
from PIL import Image
from loguru import logger

from local_body.orchestration.resolution_manager import ManualResolutionManager
from local_body.core.datamodels import ResolutionStatus
from local_body.agents.resolution_agent import ResolutionStrategy


def render_conflict_panel(
    doc_id: str,
    checkpoint_dir: Optional[str] = None,
    conflicts: Optional[List[Any]] = None
) -> None:
    """Render the conflict resolution panel.
    
    Args:
        doc_id: Document ID to fetch conflicts for
        checkpoint_dir: Optional checkpoint directory path
        conflicts: Optional list of conflict objects (if not loading from manager)
    """
    st.subheader("Conflict Resolution")
    
    # Initialize resolution manager
    if checkpoint_dir is None:
        checkpoint_dir = "test_checkpoint"  # Default for development
    
    try:
        manager = ManualResolutionManager(checkpoint_dir=checkpoint_dir)
    except Exception as e:
        # If we have conflicts passed in, we might tolerate manager failure slightly, 
        # but we need manager for resolution actions.
        if not conflicts:
            st.error(f"Failed to initialize resolution manager: {e}")
            return
        manager = None # fallback
    
    # Fetch pending conflicts if not provided
    if conflicts is None:
        if manager:
            try:
                conflicts = manager.get_pending_conflicts(doc_id)
            except Exception as e:
                st.error(f"Failed to fetch conflicts: {e}")
                logger.error(f"Error fetching conflicts for {doc_id}: {e}")
                return
        else:
            conflicts = []
    
    # Empty state - all resolved!
    if not conflicts:
        st.success("All conflicts resolved!")
        # st.balloons() # Too noisy for tab switching
        
        # Show resolution history
        if manager:
            _render_resolution_history(manager, doc_id)
        return
     
    # Show conflict count
    st.markdown(f"**{len(conflicts)} Pending Conflicts**")
    # st.caption(f"Document: `{doc_id}`")
    st.divider()
    
    # Show conflict count
    st.metric("Pending Conflicts", len(conflicts))
    st.caption(f"Document: `{doc_id}`")
    st.divider()
    
    # Render each conflict as a card
    for idx, conflict in enumerate(conflicts):
        _render_conflict_card(
            manager=manager,
            doc_id=doc_id,
            conflict=conflict,
            index=idx
        )
        
        # Separator between conflicts
        if idx < len(conflicts) - 1:
            st.divider()
    
    # Resolution history at the bottom
    st.divider()
    _render_resolution_history(manager, doc_id)


def _render_conflict_card(
    manager: ManualResolutionManager,
    doc_id: str,
    conflict: Any,
    index: int
) -> None:
    """Render a single conflict resolution card with Professional Diff Tool Styling."""
    
    # 1. Determine Styling based on Impact Score
    impact = conflict.impact_score if hasattr(conflict, 'impact_score') else 0.5
    
    if impact >= 0.7:
        card_class = "status-error" # Red accent
        border_color = "#EF4444"
        bg_color = "rgba(239, 68, 68, 0.05)"
    elif impact >= 0.3:
        card_class = "status-warning" # Yellow accent
        border_color = "#F59E0B"
        bg_color = "rgba(245, 158, 11, 0.05)"
    else:
        card_class = "status-success" # Green accent (Low impact)
        border_color = "#10B981"
        bg_color = "rgba(16, 185, 129, 0.05)"

    # 2. Main Card Container
    with st.container():
        # CSS Injection for this specific card (optional extra styling)
        st.markdown(f"""
        <div style="
            border-left: 4px solid {border_color};
            background-color: #1A1A1A;
            border-radius: 0.5rem;
            padding: 1rem;
            margin-bottom: 1rem;
            box-shadow: 0 4px 6px rgba(0,0,0,0.2);
        ">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                <div>
                    <span style="font-weight: 700; color: #FFFFFF; font-size: 1.1rem;">Conflict #{index + 1}</span>
                    <span style="margin-left: 1rem; background: {bg_color}; color: {border_color}; padding: 0.2rem 0.6rem; border-radius: 1rem; font-size: 0.8rem; font-weight: 600;">
                        Impact: {impact:.2f}
                    </span>
                </div>
                <div style="text-align: right;">
                    <span style="color: #737373; font-size: 0.8rem;">Field</span><br>
                    <code style="color: #E5E5E5; background: #262626; padding: 0.2rem 0.4rem; border-radius: 0.3rem;">
                        {conflict.field_name if hasattr(conflict, 'field_name') else 'Unknown'}
                    </code>
                </div>
            </div>
            
            <!-- Type Description -->
            <p style="color: #A3A3A3; font-size: 0.9rem; margin-top: -0.5rem; margin-bottom: 1rem;">
                {conflict.conflict_type.value}
            </p>
        </div>
        """, unsafe_allow_html=True)

        # 3. Diff View - Side by Side
        col1, col_arrow, col2 = st.columns([5, 1, 5])
        
        # SOURCE A (OCR)
        with col1:
            st.markdown(f"""<div style="text-align: center; color: #A3A3A3; font-size: 0.8rem; margin-bottom: 0.5rem;">OCR AGENT</div>""", unsafe_allow_html=True)
            ocr_val = str(conflict.text_value if conflict.text_value is not None else "N/A")
            ocr_conf = conflict.confidence_scores.get('text', 0.0) if hasattr(conflict, 'confidence_scores') else 0.0
            
            st.code(ocr_val, language=None)
            st.caption(f"Confidence: {ocr_conf:.1%}")
            
            if st.button("Accept OCR", key=f"btn_ocr_{conflict.id}_{index}", width="stretch"):
                _apply_resolution(
                    manager=manager,
                    doc_id=doc_id,
                    conflict_id=conflict.id,
                    value=ocr_val,
                    strategy=ResolutionStrategy.USER_SELECTED_TEXT,
                    notes=f"User accepted OCR: {ocr_val}"
                )

        # ARROW
        with col_arrow:
            st.markdown("<div style='text-align: center; margin-top: 1.5rem; color: #525252;'>⚡</div>", unsafe_allow_html=True)

        # SOURCE B (VISION)
        with col2:
            st.markdown(f"""<div style="text-align: center; color: #A3A3A3; font-size: 0.8rem; margin-bottom: 0.5rem;">VISION AGENT</div>""", unsafe_allow_html=True)
            vision_val = str(conflict.vision_value if conflict.vision_value is not None else "N/A")
            vision_conf = conflict.confidence_scores.get('vision', 0.0) if hasattr(conflict, 'confidence_scores') else 0.0
            
            st.code(vision_val, language=None)
            st.caption(f"Confidence: {vision_conf:.1%}")
            
            if st.button("Accept Vision", key=f"btn_vis_{conflict.id}_{index}", width="stretch", type="primary"):
                _apply_resolution(
                    manager=manager,
                    doc_id=doc_id,
                    conflict_id=conflict.id,
                    value=vision_val,
                    strategy=ResolutionStrategy.USER_SELECTED_VISION,
                    notes=f"User accepted Vision: {vision_val}"
                )

        # 4. Visual Evidence Expander
        _render_visual_evidence(manager, doc_id, conflict, index)
            
        # 5. Manual Override Expander
        with st.expander("Manual Override"):
            manual_val = st.text_input("Correct Value", key=f"man_val_{conflict.id}_{index}")
            if st.button("Apply Manual Correction", key=f"btn_man_{conflict.id}_{index}"):
                 _apply_resolution(
                    manager=manager,
                    doc_id=doc_id,
                    conflict_id=conflict.id,
                    value=manual_val,
                    strategy=ResolutionStrategy.MANUAL_OVERRIDE,
                    notes=f"User manual override: {manual_val}"
                )
        
        st.divider()


def _render_visual_evidence(
    manager: ManualResolutionManager,
    doc_id: str,
    conflict: Any,
    index: int
) -> None:
    """Render visual evidence for the conflict.
    
    Args:
        manager: ManualResolutionManager instance
        doc_id: Document ID
        conflict: Conflict object
        index: Conflict index for unique keys
    """
    try:
        # Fetch visual context
        image_bytes = manager.get_conflict_visual_context(doc_id, conflict.id)
        
        if image_bytes:
            # Convert bytes to PIL Image
            image = Image.open(BytesIO(image_bytes))
            
            # Display with expander to save space
            with st.expander("Visual Evidence", expanded=True):
                st.image(
                    image,
                    caption=f"Source region for conflict #{index + 1}",
                    use_column_width=True
                )
        else:
            st.caption("ℹ️ No visual evidence available")
    
    except Exception as e:
        logger.warning(f"Could not load visual evidence for conflict {conflict.id}: {e}")
        st.caption("⚠️ Visual evidence unavailable")


def _apply_resolution(
    manager: ManualResolutionManager,
    doc_id: str,
    conflict_id: str,
    value: Any,
    strategy: ResolutionStrategy,
    notes: str
) -> None:
    """Apply a resolution decision and refresh the UI.
    
    Args:
        manager: ManualResolutionManager instance
        doc_id: Document ID
        conflict_id: Conflict ID
        value: Resolved value
        strategy: Resolution strategy used
        notes: Resolution notes
    """
    try:
        # Apply resolution
        success = manager.apply_manual_resolution(
            doc_id=doc_id,
            conflict_id=conflict_id,
            chosen_value=value,
            strategy=strategy,
            notes=notes
        )
        
        if success:
            st.success(f"Conflict resolved: {value}")
            logger.info(f"Resolved conflict {conflict_id} for {doc_id} with strategy {strategy}")
            
            # Rerun to refresh the UI and remove resolved conflict
            st.rerun()
        else:
            st.error("❌ Failed to apply resolution")
    
    except Exception as e:
        logger.error(f"Error applying resolution: {e}")
        st.error(f"Error: {str(e)}")


def _render_resolution_history(
    manager: ManualResolutionManager,
    doc_id: str
) -> None:
    """Render resolution history and audit trail.
    
    Args:
        manager: ManualResolutionManager instance
        doc_id: Document ID
    """
    with st.expander("Resolution History"):
        try:
            history = manager.get_resolution_history(doc_id)
            
            if not history:
                st.info("No resolutions yet")
                return
            
            # Display as a table
            st.caption(f"Total resolutions: **{len(history)}**")
            
            # Format history for display
            history_data = []
            for resolution in history:
                history_data.append({
                    "Field": resolution.get('field_name', 'Unknown'),
                    "Chosen Value": str(resolution.get('chosen_value', 'N/A'))[:50],
                    "Strategy": resolution.get('resolution_method', 'Unknown').replace('_', ' ').title(),
                    "Confidence": f"{resolution.get('confidence', 0):.1%}",
                    "Timestamp": resolution.get('timestamp', 'Unknown')
                })
            
            # Display as dataframe
            if history_data:
                st.dataframe(
                    history_data,
                    width='stretch',
                    hide_index=True
                )
                
                # Summary statistics
                strategies = [h.get('resolution_method', 'unknown') for h in history]
                st.caption(f"**Breakdown:** {strategies.count('USER_SELECTED_TEXT')} OCR, "
                          f"{strategies.count('USER_SELECTED_VISION')} Vision, "
                          f"{strategies.count('MANUAL_OVERRIDE')} Manual")
        
        except Exception as e:
            logger.error(f"Error loading resolution history: {e}")
            st.warning(f"Could not load history: {str(e)}")


def render_conflict_summary_widget(doc_id: str, checkpoint_dir: Optional[str] = None) -> None:
    """Render a compact conflict summary widget for dashboard sidebar.
    
    Args:
        doc_id: Document ID
        checkpoint_dir: Optional checkpoint directory
    """
    if checkpoint_dir is None:
        checkpoint_dir = "test_checkpoint"
    
    try:
        manager = ManualResolutionManager(checkpoint_dir=checkpoint_dir)
        conflicts = manager.get_pending_conflicts(doc_id)
        
        if conflicts:
            st.warning(f"⚠️ **{len(conflicts)}** conflicts pending")
            
            # Show first conflict preview
            first_conflict = conflicts[0]
            st.caption(f"Next: {first_conflict.conflict_type.value}")
            
            if st.button("🔧 Resolve Now", width='stretch'):
                # Navigate to conflict panel (handled by main app)
                st.session_state['show_conflicts'] = True
                st.rerun()
        else:
            st.success("All resolved!")
    
    except Exception as e:
        logger.error(f"Error in conflict summary widget: {e}")
        st.caption("⚠️ Status unavailable")
