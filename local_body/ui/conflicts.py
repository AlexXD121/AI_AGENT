"""Conflict Resolution Interface for Streamlit UI.

This module provides the conflict resolution panel where users can:
- View pending conflicts with visual evidence
- Compare OCR vs Vision values side-by-side
- Make resolution decisions (Accept OCR/Vision/Manual Override)
- View resolution history and audit trail
"""

from typing import Optional, Dict, Any
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
    checkpoint_dir: Optional[str] = None
) -> None:
    """Render the conflict resolution panel.
    
    Args:
        doc_id: Document ID to fetch conflicts for
        checkpoint_dir: Optional checkpoint directory path
    """
    st.subheader("⚠️ Conflict Resolution")
    
    # Initialize resolution manager
    if checkpoint_dir is None:
        checkpoint_dir = "test_checkpoint"  # Default for development
    
    try:
        manager = ManualResolutionManager(checkpoint_dir=checkpoint_dir)
    except Exception as e:
        st.error(f"Failed to initialize resolution manager: {e}")
        return
    
    # Fetch pending conflicts
    try:
        conflicts = manager.get_pending_conflicts(doc_id)
    except Exception as e:
        st.error(f"Failed to fetch conflicts: {e}")
        logger.error(f"Error fetching conflicts for {doc_id}: {e}")
        return
    
    # Empty state - all resolved!
    if not conflicts:
        st.success("✅ All conflicts resolved!")
        st.balloons()
        
        # Show resolution history
        _render_resolution_history(manager, doc_id)
        return
    
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
    """Render a single conflict resolution card.
    
    Args:
        manager: ManualResolutionManager instance
        doc_id: Document ID
        conflict: Conflict object
        index: Conflict index for unique keys
    """
    # Card container
    with st.container():
        # Header with conflict info
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"### Conflict #{index + 1}")
            st.caption(f"Type: **{conflict.conflict_type.value}** | Impact: **{conflict.impact_score:.2f}**")
        with col2:
            # Field name
            st.caption("**Field:**")
            st.code(conflict.field_name if hasattr(conflict, 'field_name') else "Unknown")
        
        # Visual evidence
        _render_visual_evidence(manager, doc_id, conflict, index)
        
        # Side-by-side comparison
        st.markdown("#### 📊 Value Comparison")
        ocr_val = conflict.text_value if conflict.text_value is not None else "N/A"
        vision_val = conflict.vision_value if conflict.vision_value is not None else "N/A"
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**OCR Result**")
            ocr_conf = conflict.confidence_scores.get('text', 0.0) if hasattr(conflict, 'confidence_scores') else 0.0
            st.metric(
                label="Value",
                value=str(ocr_val)[:50],  # Truncate long values
                delta=f"{ocr_conf:.1%} confidence"
            )
        
        with col2:
            st.markdown("**Vision Result**")
            vision_conf = conflict.confidence_scores.get('vision', 0.0) if hasattr(conflict, 'confidence_scores') else 0.0
            st.metric(
                label="Value",
                value=str(vision_val)[:50],
                delta=f"{vision_conf:.1%} confidence"
            )
        
        # Discrepancy indicator
        if hasattr(conflict, 'discrepancy_percentage'):
            if conflict.discrepancy_percentage > 0.5:  # 50%+
                st.error(f"⚠️ High discrepancy: {conflict.discrepancy_percentage:.1%}")
            else:
                st.warning(f"ℹ️ Discrepancy: {conflict.discrepancy_percentage:.1%}")
        
        # Decision buttons
        st.markdown("#### 🎯 Resolution")
        
        btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 2])
        
        with btn_col1:
            if st.button(
                "✅ Accept OCR",
                key=f"btn_ocr_{conflict.id}_{index}",
                type="secondary",
                width='stretch'
            ):
                _apply_resolution(
                    manager=manager,
                    doc_id=doc_id,
                    conflict_id=conflict.id,
                    value=ocr_val,
                    strategy=ResolutionStrategy.USER_SELECTED_TEXT,
                    notes=f"User selected OCR value: {ocr_val}"
                )
        
        with btn_col2:
            if st.button(
                "👁️ Accept Vision",
                key=f"btn_vision_{conflict.id}_{index}",
                type="secondary",
                width='stretch'
            ):
                _apply_resolution(
                    manager=manager,
                    doc_id=doc_id,
                    conflict_id=conflict.id,
                    value=vision_val,
                    strategy=ResolutionStrategy.USER_SELECTED_VISION,
                    notes=f"User selected Vision value: {vision_val}"
                )
        
        with btn_col3:
            # Manual override input
            manual_value = st.text_input(
                "Manual Override",
                key=f"input_manual_{conflict.id}_{index}",
                placeholder="Enter custom value..."
            )
            
            if st.button(
                "📝 Apply Manual",
                key=f"btn_manual_{conflict.id}_{index}",
                type="primary",
                width='stretch',
                disabled=not manual_value
            ):
                _apply_resolution(
                    manager=manager,
                    doc_id=doc_id,
                    conflict_id=conflict.id,
                    value=manual_value,
                    strategy=ResolutionStrategy.MANUAL_OVERRIDE,
                    notes=f"User entered manual value: {manual_value}"
                )


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
            with st.expander("🖼️ Visual Evidence", expanded=True):
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
            st.success(f"✅ Conflict resolved: {value}")
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
    with st.expander("📜 Resolution History"):
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
            st.success("✅ All resolved!")
    
    except Exception as e:
        logger.error(f"Error in conflict summary widget: {e}")
        st.caption("⚠️ Status unavailable")
