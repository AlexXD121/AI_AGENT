"""Sovereign Doc - Professional Document Intelligence Platform

Main Streamlit application with sleek dark theme.
"""

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

import streamlit as st
from loguru import logger

from local_body.ui.upload import render_upload_hero
from local_body.ui.dashboard import render_analysis_dashboard


# Configure page
st.set_page_config(
    page_title="Sovereign Doc",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Professional Dark Theme CSS
# Professional Dark Theme CSS
def load_css():
    st.markdown("""
    <style>
        /* Hide Streamlit branding */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        
        /* Global typography */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');
        
        html, body, [class*="css"] {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }
        
        .mono {
            font-family: 'JetBrains Mono', 'Consolas', monospace;
        }
        
        /* Dark background */
        .stApp {
            background-color: #0F0F0F;
        }
        
        /* Main container */
        .main .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
            max-width: 100%;
            background-color: #0F0F0F;
        }
        
        /* Headers */
        h1 {
            font-weight: 700;
            font-size: 2.5rem;
            letter-spacing: -0.02em;
            color: #FFFFFF;
            margin-bottom: 0.5rem;
        }
        
        h2 {
            font-weight: 600;
            font-size: 1.5rem;
            color: #E5E5E5;
            margin-bottom: 1rem;
        }
        
        h3 {
            font-weight: 600;
            font-size: 1.125rem;
            color: #D4D4D4;
            margin-bottom: 0.75rem;
        }
        
        /* Paragraph text */
        p {
            color: #A3A3A3;
        }
        
        /* Flat toast notifications */
        .stAlert {
            border-radius: 0.5rem;
            border: 1px solid rgba(255, 255, 255, 0.1);
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
            padding: 1rem 1.5rem;
        }
        
        /* Info box */
        .stAlert[data-baseweb="notification"] {
            background-color: #1E293B;
            color: #60A5FA;
            border-color: #3B82F6;
        }
        
        /* Success box */
        .stSuccess {
            background-color: #1E3A2C;
            color: #34D399;
            border-color: #10B981;
        }
        
        /* Warning box */
        .stWarning {
            background-color: #3A2E1E;
            color: #FBBF24;
            border-color: #F59E0B;
        }
        
        /* Error box */
        .stError {
            background-color: #3A1E1E;
            color: #F87171;
            border-color: #EF4444;
        }
        
        /* Buttons */
        .stButton > button {
            border-radius: 0.5rem;
            font-weight: 500;
            padding: 0.625rem 1.25rem;
            border: none;
            transition: all 0.2s ease;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
        }
        
        .stButton > button:hover {
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
            transform: translateY(-1px);
        }
        
        /* Primary button - Electric Blue */
        .stButton > button[kind="primary"] {
            background: linear-gradient(135deg, #3B82F6 0%, #2563EB 100%);
            color: white;
        }
        
        .stButton > button[kind="primary"]:hover {
            background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%);
        }
        
        /* Secondary button */
        .stButton > button[kind="secondary"] {
            background-color: #1F1F1F;
            color: #E5E5E5;
            border: 1px solid #404040;
        }
        
        .stButton > button[kind="secondary"]:hover {
            background-color: #2A2A2A;
            border-color: #525252;
        }
        
        /* File uploader */
        .stFileUploader {
            border: 2px dashed #404040;
            border-radius: 0.75rem;
            padding: 2rem;
            background: linear-gradient(135deg, #1A1A1A 0%, #0F0F0F 100%);
            transition: all 0.3s ease;
        }
        
        .stFileUploader:hover {
            border-color: #3B82F6;
            background: linear-gradient(135deg, #1F1F1F 0%, #141414 100%);
        }
        
        /* Metrics */
        [data-testid="stMetricValue"] {
            font-family: 'JetBrains Mono', 'Consolas', monospace;
            font-size: 1.75rem;
            font-weight: 700;
            color: #FFFFFF;
        }
        
        [data-testid="stMetricLabel"] {
            font-size: 0.875rem;
            font-weight: 500;
            color: #737373;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        
        [data-testid="stMetricDelta"] {
            font-family: 'JetBrains Mono', 'Consolas', monospace;
            color: #60A5FA;
        }
        
        /* Dataframes */
        .stDataFrame {
            border-radius: 0.5rem;
            overflow: hidden;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
            background-color: #1A1A1A;
        }
        
        /* Containers with borders */
        [data-testid="stVerticalBlock"] > [style*="border"] {
            border-radius: 0.75rem;
            border-color: #262626;
            background-color: #171717;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
        }
        
        /* Progress bars */
        .stProgress > div > div {
            background: linear-gradient(90deg, #3B82F6 0%, #8B5CF6 100%);
            border-radius: 9999px;
        }
        
        /* Status Elements */
        .stStatus {
             background-color: #171717;
             border: 1px solid #262626;
             border-radius: 0.75rem;
        }

        /* Professional card styling */
        .professional-card {
            background: linear-gradient(135deg, #1F1F1F 0%, #171717 100%);
            border-radius: 0.75rem;
            padding: 1.5rem;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
            border: 1px solid #262626;
            margin-bottom: 1rem;
        }
        
        /* Conflict card */
        .conflict-card {
            background: linear-gradient(135deg, #3A2E1E 0%, #2D2416 100%);
            border-left: 4px solid #F59E0B;
            padding: 1.25rem;
            border-radius: 0.5rem;
            margin-bottom: 1rem;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
        }
        
        /* Sidebar */
        [data-testid="stSidebar"] {
            background-color: #0A0A0A;
            border-right: 1px solid #1F1F1F;
        }
        
        [data-testid="stSidebar"] h3 {
            color: #FFFFFF;
        }
        
        [data-testid="stSidebar"] p {
            color: #737373;
        }
        
        /* Dividers */
        hr {
            border-color: #262626;
        }
        
        /* Input fields */
        .stTextInput > div > div > input,
        .stNumberInput > div > div > input,
        .stSelectbox > div > div {
            background-color: #1A1A1A;
            color: #E5E5E5;
            border-color: #404040;
            font-family: 'JetBrains Mono', 'Consolas', monospace;
        }
        
        /* Captions */
        .st-caption {
            color: #737373 !important;
        }
        
        /* Tabs */
        .stTabs [data-baseweb="tab-list"] {
            gap: 2rem;
            background-color: transparent;
        }

        .stTabs [data-baseweb="tab"] {
            height: 3rem;
            white-space: pre-wrap;
            background-color: transparent;
            border-radius: 0px;
            color: #737373;
            font-weight: 500;
        }

        .stTabs [aria-selected="true"] {
            background-color: transparent;
            color: #3B82F6;
            border-bottom: 2px solid #3B82F6;
        }
        
        /* Section dividers with gradient */
        .section-divider {
            height: 1px;
            background: linear-gradient(90deg, transparent 0%, #3B82F6 50%, transparent 100%);
            margin: 2rem 0;
        }
        
        /* JSON Tree */
        .json-formatter-row {
            font-family: 'JetBrains Mono', monospace !important;
        }
    </style>
    """, unsafe_allow_html=True)


def initialize_session_state():
    """Initialize session state variables."""
    if 'processing_complete' not in st.session_state:
        st.session_state['processing_complete'] = False
    
    if 'document' not in st.session_state:
        st.session_state['document'] = None
    
    if 'current_state' not in st.session_state:
        st.session_state['current_state'] = None
    
    if 'analysis_data' not in st.session_state:
        st.session_state['analysis_data'] = {}
    
    if 'system_initialized' not in st.session_state:
        st.session_state['system_initialized'] = False
    
    if 'system_error' not in st.session_state:
        st.session_state['system_error'] = None


def render_maintenance_screen(error):
    """Render system maintenance screen when startup fails.
    
    Args:
        error: The SovereignError that occurred
    """
    st.markdown("# ⚙️ System Maintenance")
    
    st.error(f"**Startup Error:** {error.message}")
    
    # Show error details if available
    if hasattr(error, 'details') and error.details:
        with st.expander("🔍 Error Details"):
            for key, value in error.details.items():
                st.text(f"{key}: {value}")
    
    # Show appropriate guidance based on error type
    from local_body.core.exceptions import ResourceError, DependencyError, ConfigurationError
    
    if isinstance(error, ResourceError):
        st.warning("### 💾 Resource Issue Detected")
        st.markdown("""
        **Recommended Actions:**
        1. Close other applications to free up RAM
        2. Reduce `batch_size` in config.yaml
        3. Switch to `processing_mode: ocr_only` for lighter processing
        
        See the [Configuration Guide](docs/CONFIGURATION_GUIDE.md) for details.
        """)
    
    elif isinstance(error, DependencyError):
        st.warning("### 🔌 Dependency Not Available")
        st.markdown("""
        **Recommended Actions:**
        1. Start Qdrant: `docker-compose up -d`
        2. Check Colab Brain connection if using hybrid mode
        3. Run in local-only mode
        
        See the [Installation Guide](docs/INSTALLATION.md) for setup instructions.
        """)
    
    elif isinstance(error, ConfigurationError):
        st.warning("### ⚙️ Configuration Issue")
        st.markdown("""
        **Recommended Actions:**
        1. Check `config.yaml` exists and is valid
        2. Verify required environment variables are set
        3. Review the [Configuration Guide](docs/CONFIGURATION_GUIDE.md)
        """)
    
    # Retry button
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("🔄 Retry Startup", type="primary", use_container_width=True):
            # Clear error state
            st.session_state['system_initialized'] = False
            st.session_state['system_error'] = None
            st.rerun()


def main():
    """Main application entry point."""
    load_css()
    initialize_session_state()
    
    # STEP 1: SYSTEM BOOTSTRAP
    # Initialize system before rendering any UI
    if not st.session_state['system_initialized'] and not st.session_state['system_error']:
        try:
            from local_body.core.bootstrap import initialize_system
            from local_body.core.exceptions import SovereignError
            
            # Show temporary loading message
            with st.spinner("🚀 Initializing Sovereign-Doc..."):
                # This will raise SovereignError if anything fails
                config = initialize_system()
                
                # Store config in session state for access by components
                st.session_state['system_config'] = config
                st.session_state['system_initialized'] = True
                
                # Force rerun to show main UI
                st.rerun()
                
        except SovereignError as e:
            # Capture startup error
            logger.error(f"System startup failed: {e}")
            st.session_state['system_error'] = e
            st.rerun()
        
        except Exception as e:
            # Unexpected error - wrap in StartupError
            from local_body.core.exceptions import StartupError
            logger.error(f"Unexpected startup error: {e}")
            st.session_state['system_error'] = StartupError(
                f"Unexpected error during startup: {str(e)}",
                startup_stage="unknown"
            )
            st.rerun()
    
    # STEP 2: RENDER UI
    # If system failed to initialize, show maintenance screen
    if st.session_state['system_error']:
        render_maintenance_screen(st.session_state['system_error'])
        return
    
    # If still initializing (shouldn't happen due to rerun, but safety check)
    if not st.session_state['system_initialized']:
        st.info("Initializing system...")
        return
    
    # System initialized successfully - render normal UI
    
    # Minimal sidebar
    with st.sidebar:
        st.markdown("### Sovereign Doc")
        st.caption("Document Intelligence")
        
        st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
        
        if st.session_state['processing_complete']:
            if st.button("Reset Application", use_container_width=True):
                # Clear all session state except system init
                keys_to_keep = ['system_initialized', 'system_config']
                for key in list(st.session_state.keys()):
                    if key not in keys_to_keep:
                        del st.session_state[key]
                st.rerun()
        
        st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
        
        st.caption("Version 1.0.0")
        st.caption("Privacy-First AI")
    
    # Main content routing
    if not st.session_state['processing_complete']:
        render_upload_hero()
    else:
        render_analysis_dashboard(st.session_state['current_state'])


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Application error: {e}")
        st.error(f"An error occurred: {str(e)}")

