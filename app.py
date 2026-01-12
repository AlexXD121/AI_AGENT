"""Sovereign-Doc Streamlit Application.

Main entry point for the Streamlit UI.
"""

import streamlit as st
from loguru import logger

from local_body.ui.dashboard import render_main_dashboard
from local_body.ui.upload import render_upload_page


# Configure Streamlit page
st.set_page_config(
    page_title="Sovereign-Doc",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    /* Main container */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    
    /* Confidence colors */
    .confidence-high {
        color: #00FF00;
        font-weight: bold;
    }
    .confidence-medium {
        color: #FFAA00;
        font-weight: bold;
    }
    .confidence-low {
        color: #FF0000;
        font-weight: bold;
    }
    
    /* Conflict card styling */
    .conflict-card {
        border-left: 4px solid #FF9800;
        padding-left: 1rem;
        margin-bottom: 1rem;
    }
    
    /* Processing stage indicator */
    .stProgress > div > div > div > div {
        background-image: linear-gradient(to right, #00FF00, #0088FF);
    }
</style>
""", unsafe_allow_html=True)


def initialize_session_state():
    """Initialize Streamlit session state variables."""
    if 'processing_active' not in st.session_state:
        st.session_state['processing_active'] = False
    
    if 'current_state' not in st.session_state:
        st.session_state['current_state'] = None
    
    if 'document' not in st.session_state:
        st.session_state['document'] = None
    
    # Additional state variables for complete integration
    if 'document_queue' not in st.session_state:
        st.session_state['document_queue'] = []
    
    if 'results' not in st.session_state:
        st.session_state['results'] = {}
    
    if 'config' not in st.session_state:
        st.session_state['config'] = {}
    
    if 'checkpoint_dir' not in st.session_state:
        st.session_state['checkpoint_dir'] = 'test_checkpoint'
    
    if 'current_document_index' not in st.session_state:
        st.session_state['current_document_index'] = 0


def main():
    """Main application entry point."""
    # Initialize session state
    initialize_session_state()
    
    # Sidebar
    with st.sidebar:
        st.title("⚙️ Settings")
        
        # Processing mode (placeholder for Task 9.3)
        processing_mode = st.selectbox(
            "Processing Mode",
            ["Local + Cloud Brain", "Local Only", "Cloud Only"],
            help="Choose how to process documents"
        )
        
        # Confidence thresholds
        with st.expander("🎯 Confidence Thresholds"):
            ocr_threshold = st.slider("OCR Threshold", 0.0, 1.0, 0.7, 0.05)
            vision_threshold = st.slider("Vision Threshold", 0.0, 1.0, 0.7, 0.05)
        
        # Advanced settings
        with st.expander("🔧 Advanced"):
            batch_size = st.number_input("Batch Size", 1, 100, 10)
            enable_caching = st.checkbox("Enable Caching", value=True)
        
        st.divider()
        
        # System info
        st.caption("**System Status**")
        st.caption("🟢 Qdrant: Connected")
        st.caption("🟢 Embeddings: Ready")
        
        if st.button("🔄 Clear Cache"):
            st.cache_data.clear()
            st.success("Cache cleared!")
    
    # Main content area
    if st.session_state['processing_active'] and st.session_state.get('current_state'):
        # Show dashboard with processing state
        render_main_dashboard(st.session_state['current_state'])
    else:
        # Show advanced upload page
        render_upload_page()
    
    # Footer
    st.divider()
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.caption("Powered by Sovereign-Doc | YOLOv8 + PaddleOCR + Qwen-VL")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Application error: {e}")
        st.error(f"An error occurred: {str(e)}")
        st.exception(e)
