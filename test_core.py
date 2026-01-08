"""Test script to verify core implementations.

This script tests the basic functionality of the core components
created in Task 1.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from local_body.core.datamodels import (
    BoundingBox, Region, RegionType, TextContent, 
    Page, Document, DocumentMetadata, ProcessingStatus,
    Conflict, ConflictType, ResolutionStatus
)
from local_body.core.config_manager import ConfigManager, SystemConfig
from local_body.core.logging_setup import setup_logging, get_logger


def test_data_models():
    """Test data model creation and validation."""
    print("Testing data models...")
    
    # Test BoundingBox
    bbox = BoundingBox(x=10.0, y=20.0, width=100.0, height=50.0)
    assert bbox.x == 10.0
    assert bbox.width == 100.0
    
    # Test TextContent
    text_content = TextContent(text="Sample text", confidence=0.95)
    assert text_content.text == "Sample text"
    assert text_content.confidence == 0.95
    
    # Test Region
    region = Region(
        bbox=bbox,
        region_type=RegionType.TEXT,
        content=text_content,
        confidence=0.9,
        extraction_method="ocr"
    )
    assert region.region_type == RegionType.TEXT
    assert region.confidence == 0.9
    
    # Test Page
    page = Page(page_number=1, regions=[region])
    assert page.page_number == 1
    assert len(page.regions) == 1
    
    # Test Document
    metadata = DocumentMetadata(
        page_count=1,
        file_size_bytes=1024,
        document_type="pdf"
    )
    doc = Document(
        file_path="test.pdf",
        pages=[page],
        metadata=metadata
    )
    assert doc.file_path == "test.pdf"
    assert doc.processing_status == ProcessingStatus.PENDING
    assert len(doc.pages) == 1
    
    # Test Conflict
    conflict = Conflict(
        region_id=region.id,
        conflict_type=ConflictType.VALUE_MISMATCH,
        text_value=100,
        vision_value=105,
        discrepancy_percentage=0.05,
        confidence_scores={"text": 0.8, "vision": 0.9}
    )
    assert conflict.conflict_type == ConflictType.VALUE_MISMATCH
    assert conflict.resolution_status == ResolutionStatus.PENDING
    
    print("✓ Data models test passed!")


def test_config_manager():
    """Test configuration management."""
    print("\nTesting configuration manager...")
    
    # Test default config
    config = SystemConfig()
    assert config.processing_mode == "hybrid"
    assert config.conflict_threshold == 0.15
    assert config.batch_size == 5
    
    # Test ConfigManager
    manager = ConfigManager()
    loaded_config = manager.load_config()
    assert loaded_config.processing_mode in ["local", "hybrid", "remote"]
    assert 0.05 <= loaded_config.conflict_threshold <= 0.30
    
    # Test config updates
    manager.update_config({"batch_size": 10})
    updated_config = manager.get_config()
    assert updated_config.batch_size == 10
    
    print("✓ Configuration manager test passed!")


def test_logging_setup():
    """Test logging configuration."""
    print("\nTesting logging setup...")
    
    # Setup logging
    setup_logging(log_level="DEBUG", enable_file=False)
    
    # Get logger
    logger = get_logger("test_module")
    logger.info("Test log message")
    logger.debug("Debug message")
    
    print("✓ Logging setup test passed!")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Sovereign-Doc Core Components Test Suite")
    print("=" * 60)
    
    try:
        test_data_models()
        test_config_manager()
        test_logging_setup()
        
        print("\n" + "=" * 60)
        print("✓ All tests passed successfully!")
        print("=" * 60)
        return 0
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
