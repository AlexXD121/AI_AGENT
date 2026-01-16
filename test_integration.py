"""Quick integration test for LangGraph backend + Streamlit frontend.

Run this to verify the integration is working correctly.
"""

import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))


def test_imports():
    """Test that all required modules can be imported."""
    print("Testing imports...")
    
    try:
        from local_body.orchestration.workflow import DocumentWorkflow
        from local_body.orchestration.state import DocumentProcessingState, ProcessingStage
        from local_body.core.config_manager import ConfigManager
        from local_body.utils.document_loader import DocumentLoader
        from local_body.ui.upload import render_upload_hero, _extract_analysis_metrics
        from local_body.ui.dashboard import render_analysis_dashboard
        
        print("✅ All imports successful")
        return True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False


def test_workflow_initialization():
    """Test that DocumentWorkflow can be initialized."""
    print("\nTesting DocumentWorkflow initialization...")
    
    try:
        from local_body.orchestration.workflow import DocumentWorkflow
        
        workflow = DocumentWorkflow()
        print(f"✅ Workflow initialized: {workflow}")
        print(f"   Graph nodes: {workflow.graph}")
        return True
    except Exception as e:
        print(f"❌ Workflow initialization failed: {e}")
        return False


def test_state_structure():
    """Test that DocumentProcessingState can be created."""
    print("\nTesting state structure...")
    
    try:
        from local_body.orchestration.state import ProcessingStage
        from local_body.core.datamodels import Document, Page, DocumentMetadata
        
        # Create mock document with all required fields
        metadata = DocumentMetadata(
            page_count=1,
            file_size_bytes=1024
        )
        
        document = Document(
            file_id="test_123",
            file_name="test.pdf",
            file_path="/tmp/test.pdf",
            pages_count=1,
            pages=[],  # Required field
            metadata=metadata
        )
        
        # Create state
        initial_state = {
            'document': document,
            'file_path': '/tmp/test.pdf',
            'processing_stage': ProcessingStage.INGEST,
            'layout_regions': [],
            'ocr_results': {},
            'vision_results': {},
            'conflicts': [],
            'resolutions': [],
            'error_log': []
        }
        
        print("✅ State structure created successfully")
        print(f"   Document ID: {initial_state['document'].id}")
        print(f"   Stage: {initial_state['processing_stage']}")
        return True
    except Exception as e:
        print(f"❌ State creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_metrics_extraction():
    """Test metrics extraction function."""
    print("\nTesting metrics extraction...")
    
    try:
        from local_body.ui.upload import _extract_analysis_metrics
        from local_body.core.datamodels import Document, DocumentMetadata
        
        # Create mock state with all required fields
        metadata = DocumentMetadata(
            page_count=2,
            file_size_bytes=2048
        )
        
        document = Document(
            file_id="test",
            file_name="test.pdf",
            file_path="/tmp/test.pdf",
            pages_count=2,
            pages=[],
            metadata=metadata
        )
        # Note: Document doesn't have 'text' attribute
        # Text is stored in Page.regions[].content.text
        
        state = {
            'document': document,
            'layout_regions': [],
            'conflicts': [],
            'ocr_results': {'avg_confidence': 0.85},
            'vision_results': {'avg_confidence': 0.90},
            'processing_stage': 'complete'
        }
        
        metrics = _extract_analysis_metrics(state)
        
        print("✅ Metrics extracted successfully")
        print(f"   Confidence: {metrics['confidence']:.2%}")
        print(f"   Total regions: {metrics['total_regions']}")
        print(f"   Total conflicts: {metrics['total_conflicts']}")
        print(f"   Page count: {metrics['page_count']}")
        return True
    except Exception as e:
        print(f"❌ Metrics extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_config_loading():
    """Test system configuration loading."""
    print("\nTesting config loading...")
    
    try:
        from local_body.core.config_manager import ConfigManager
        
        config = ConfigManager().load_config()
        
        print("✅ Config loaded successfully")
        print(f"   Config type: {type(config).__name__}")
        print(f"   Available RAM: {config.available_ram_gb}GB")
        return True
    except Exception as e:
        print(f"❌ Config loading failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all integration tests."""
    print("=" * 70)
    print("LANGGRAPH BACKEND INTEGRATION TEST")
    print("=" * 70)
    
    tests = [
        test_imports,
        test_config_loading,
        test_state_structure,
        test_metrics_extraction,
        test_workflow_initialization,
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(results)
    total = len(results)
    
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("\n✅ ALL TESTS PASSED - Integration ready!")
        print("\nNext steps:")
        print("  1. Run: streamlit run app.py")
        print("  2. Upload a test PDF")
        print("  3. Click 'Analyze Document'")
        print("  4. Verify agents execute in sequence")
        print("  5. Check dashboard displays real conflicts")
        return 0
    else:
        print(f"\n❌ {total - passed} test(s) failed")
        print("\nPlease fix the issues before running the UI")
        return 1


if __name__ == "__main__":
    sys.exit(main())
