"""Streamlined integration tests for UI-Backend wiring.

Tests verify critical integration points without deep mocking.
"""

import pytest


class TestBackendImports:
    """Test that all backend modules can be imported."""
    
    def test_workflow_modules_import(self):
        """Verify workflow modules import successfully."""
        try:
            from local_body.orchestration.workflow import DocumentWorkflow
            from local_body.orchestration.state import DocumentProcessingState, ProcessingStage
            from local_body.orchestration.nodes import (
                layout_detection_node,
                ocr_processing_node,
                vision_analysis_node,
                validation_node
            )
            assert True
        except ImportError as e:
            pytest.fail(f"Workflow imports failed: {e}")
    
    def test_resolution_modules_import(self):
        """Verify resolution modules import successfully."""
        try:
            from local_body.orchestration.resolution_manager import ManualResolutionManager
            from local_body.agents.resolution_agent import ResolutionStrategy, ResolutionAgent
            assert True
        except ImportError as e:
            pytest.fail(f"Resolution imports failed: {e}")
    
    def test_vector_store_modules_import(self):
        """Verify vector store modules import successfully."""
        try:
            from local_body.database.vector_store import DocumentVectorStore
            from local_body.database.multi_doc_query import MultiDocumentQuery
            assert True
        except ImportError as e:
            pytest.fail(f"Vector store imports failed: {e}")
    
    def test_agent_modules_import(self):
        """Verify agent modules import successfully."""
        try:
            from local_body.agents.layout_agent import LayoutDetectionAgent
            from local_body.agents.ocr_agent import OCRAgent
            from local_body.agents.vision_agent import VisionAgent
            from local_body.agents.validation_agent import ValidationAgent
            assert True
        except ImportError as e:
            pytest.fail(f"Agent imports failed: {e}")
    
    def test_ui_modules_import(self):
        """Verify UI modules import successfully."""
        try:
            # Note: streamlit will fail in test environment, but we can check syntax
            import local_body.ui.viewer
            import local_body.ui.results
            assert True
        except SyntaxError as e:
            pytest.fail(f"UI modules have syntax errors: {e}")


class TestDataModelsIntegrity:
    """Test that core data models are properly defined."""
    
    def test_document_model_instantiation(self):
        """Verify Document model can be created."""
        from local_body.core.datamodels import Document, DocumentMetadata, ProcessingStatus
        
        metadata = DocumentMetadata(
            page_count=1,
            file_size_bytes=1024
        )
        
        doc = Document(
            file_path="test.pdf",
            metadata=metadata,
            processing_status=ProcessingStatus.PENDING
        )
        
        assert doc.file_path == "test.pdf"
        assert doc.processing_status == ProcessingStatus.PENDING
    
    def test_conflict_model_instantiation(self):
        """Verify Conflict model can be created."""
        from local_body.core.datamodels import Conflict, ConflictType, ResolutionStatus
        
        conflict = Conflict(
            field_name="total_amount",
            text_value="100",
            vision_value="120",
            conflict_type=ConflictType.NUMERIC,
            confidence_scores={"text": 0.9, "vision": 0.8}
        )
        
        assert conflict.field_name == "total_amount"
        assert conflict.resolution_status == ResolutionStatus.PENDING
    
    def test_region_model_instantiation(self):
        """Verify Region model can be created."""
        from local_body.core.datamodels import Region, BoundingBox, RegionType, TextContent
        
        bbox = BoundingBox(x=10, y=20, width=100, height=50)
        content = TextContent(text="Sample text", confidence=0.95)
        
        region = Region(
            bbox=bbox,
            region_type=RegionType.TEXT,
            content=content,
            confidence=0.95,
            extraction_method="ocr"
        )
        
        assert region.region_type == RegionType.TEXT
        assert region.confidence == 0.95


class TestConfigurationIntegrity:
    """Test configuration management."""
    
    def test_config_manager_loads(self):
        """Verify ConfigManager can load configuration."""
        from local_body.core.config_manager import ConfigManager
        
        manager = ConfigManager()
        config = manager.load_config()
        
        assert config is not None
        assert hasattr(config, 'qdrant_host')
    
    def test_hardware_detector_works(self):
        """Verify HardwareDetector provides stats."""
        from local_body.utils.hardware import HardwareDetector
        
        detector = HardwareDetector()
        
        total_ram = detector.get_total_ram_gb()
        available_ram = detector.get_available_ram_gb()
        cpu_cores = detector.get_cpu_cores()
        
        assert total_ram > 0
        assert available_ram >= 0
        assert cpu_cores > 0


class TestWorkflowIntegration:
    """Test workflow can be initialized."""
    
    def test_document_workflow_initializes(self):
        """Verify DocumentWorkflow can be created."""
        from local_body.orchestration.workflow import DocumentWorkflow
        from local_body.core.config_manager import ConfigManager
        
        config = ConfigManager().load_config()
        
        # Should not crash
        try:
            workflow = DocumentWorkflow(config)
            assert workflow is not None
        except Exception as e:
            pytest.fail(f"Workflow initialization failed: {e}")


class TestResolutionManagerIntegration:
    """Test resolution manager can be initialized."""
    
    def test_manual_resolution_manager_initializes(self):
        """Verify ManualResolutionManager can be created."""
        from local_body.orchestration.resolution_manager import ManualResolutionManager
        
        # Should not crash
        try:
            manager = ManualResolutionManager(checkpoint_dir="test_checkpoint")
            assert manager is not None
        except Exception as e:
            pytest.fail(f"Resolution manager initialization failed: {e}")


class TestAppSessionState:
    """Test app.py session state initialization."""
    
    def test_app_module_imports(self):
        """Verify app.py can be imported."""
        try:
            import app
            assert hasattr(app, 'initialize_session_state')
            assert hasattr(app, 'main')
        except ImportError as e:
            pytest.fail(f"app.py import failed: {e}")
