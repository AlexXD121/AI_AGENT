"""Test suite for graceful degradation system (FallbackManager and RecoveryManager).

Tests processing mode selection, retry logic, and page-level recovery.
"""

import pytest
import time
from pathlib import Path
from local_body.core.fallback import FallbackManager, ProcessingMode, with_retry
from local_body.core.recovery import RecoveryManager, RecoveryState
from local_body.core.config_manager import ConfigManager


class TestProcessingMode:
    """Test ProcessingMode enum."""
    
    def test_mode_hierarchy(self):
        """Test that modes are ordered correctly."""
        assert ProcessingMode.HYBRID < ProcessingMode.LOCAL_GPU
        assert ProcessingMode.LOCAL_GPU < ProcessingMode.LOCAL_CPU
        assert ProcessingMode.LOCAL_CPU < ProcessingMode.OCR_ONLY
    
    def test_mode_comparison(self):
        """Test mode comparison operators."""
        assert ProcessingMode.HYBRID <= ProcessingMode.LOCAL_GPU
        assert not (ProcessingMode.OCR_ONLY < ProcessingMode.HYBRID)


class TestFallbackManager:
    """Test FallbackManager functionality."""
    
    def test_singleton_pattern(self):
        """Test that FallbackManager uses singleton pattern."""
        config = ConfigManager().load_config()
        
        manager1 = FallbackManager.get_instance(config)
        manager2 = FallbackManager.get_instance()
        
        assert manager1 is manager2
    
    def test_determine_optimal_mode(self):
        """Test basic mode selection."""
        config = ConfigManager().load_config()
        manager = FallbackManager.get_instance(config)
        
        mode = manager.determine_optimal_mode()
        
        assert isinstance(mode, ProcessingMode)
        # Should return a valid mode
        assert mode in ProcessingMode
    
    def test_can_use_mode(self):
        """Test mode availability checking."""
        config = ConfigManager().load_config()
        manager = FallbackManager.get_instance(config)
        
        # OCR_ONLY should always be available (lowest requirements)
        can_use_ocr = manager.can_use_mode(ProcessingMode.OCR_ONLY)
        assert can_use_ocr is True
    
    def test_downgrade_mode(self):
        """Test mode downgrading."""
        config = ConfigManager().load_config()
        manager = FallbackManager.get_instance(config)
        
        # Test each downgrade step
        assert manager.downgrade_mode(ProcessingMode.HYBRID) == ProcessingMode.LOCAL_GPU
        assert manager.downgrade_mode(ProcessingMode.LOCAL_GPU) == ProcessingMode.LOCAL_CPU
        assert manager.downgrade_mode(ProcessingMode.LOCAL_CPU) == ProcessingMode.OCR_ONLY
        assert manager.downgrade_mode(ProcessingMode.OCR_ONLY) == ProcessingMode.OCR_ONLY  # At lowest
    
    def test_get_current_mode(self):
        """Test getting current mode."""
        config = ConfigManager().load_config()
        manager = FallbackManager.get_instance(config)
        
        # Initially may be None
        current = manager.get_current_mode()
        assert current is None or isinstance(current, ProcessingMode)
        
        # After determining mode
        manager.determine_optimal_mode()
        current = manager.get_current_mode()
        assert isinstance(current, ProcessingMode)


class TestWithRetryDecorator:
    """Test retry decorator."""
    
    def test_retry_success_first_attempt(self):
        """Test successful function on first attempt."""
        call_count = 0
        
        @with_retry(max_retries=3)
        def successful_function():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = successful_function()
        
        assert result == "success"
        assert call_count == 1  # Should only call once
    
    def test_retry_success_after_failures(self):
        """Test recovery after initial failures."""
        call_count = 0
        
        @with_retry(max_retries=3, backoff_delays=[0.1, 0.1, 0.1])
        def flaky_function():
            nonlocal call_count
            call_count += 1
            
            if call_count < 3:
                raise ValueError("Temporary error")
            
            return "success"
        
        result = flaky_function()
        
        assert result == "success"
        assert call_count == 3  # Should succeed on third attempt
    
    def test_retry_exhausted(self):
        """Test when all retries are exhausted."""
        call_count = 0
        
        @with_retry(max_retries=3, backoff_delays=[0.1, 0.1, 0.1])
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise RuntimeError("Persistent error")
        
        with pytest.raises(RuntimeError):
            always_fails()
        
        assert call_count == 3  # Should try 3 times
    
    def test_retry_specific_exceptions(self):
        """Test retrying only specific exceptions."""
        call_count = 0
        
        @with_retry(
            max_retries=3,
            retry_on_exceptions=(ValueError,),
            backoff_delays=[0.1, 0.1, 0.1]
        )
        def specific_error():
            nonlocal call_count
            call_count += 1
            
            if call_count == 1:
                raise ValueError("Retryable")
            else:
                raise TypeError("Non-retryable")
        
        with pytest.raises(TypeError):
            specific_error()
        
        assert call_count == 2  # First ValueError retried, then TypeError raised


class TestRecoveryState:
    """Test RecoveryState dataclass."""
    
    def test_recovery_state_creation(self):
        """Test creating RecoveryState."""
        state = RecoveryState(
            doc_id="test123",
            total_pages=10
        )
        
        assert state.doc_id == "test123"
        assert state.total_pages == 10
        assert len(state.completed_pages) == 0
        assert state.status == "IN_PROGRESS"
    
    def test_recovery_state_serialization(self):
        """Test to_dict and from_dict."""
        original = RecoveryState(
            doc_id="test456",
            total_pages=20,
            completed_pages={1, 2, 3, 5},
            failed_pages={4}
        )
        
        # Serialize
        data = original.to_dict()
        
        assert isinstance(data, dict)
        assert isinstance(data["completed_pages"], list)
        
        # Deserialize
        restored = RecoveryState.from_dict(data)
        
        assert restored.doc_id == original.doc_id
        assert restored.completed_pages == original.completed_pages
        assert restored.failed_pages == original.failed_pages


class TestRecoveryManager:
    """Test RecoveryManager functionality."""
    
    @pytest.fixture
    def temp_recovery_dir(self, tmp_path):
        """Create temporary recovery directory."""
        recovery_dir = tmp_path / "recovery"
        return str(recovery_dir)
    
    def test_save_and_load_checkpoint(self, temp_recovery_dir):
        """Test saving and loading checkpoints."""
        manager = RecoveryManager(recovery_dir=temp_recovery_dir)
        
        # Save checkpoint
        success = manager.save_checkpoint(
            doc_id="test_doc",
            page_num=5,
            status="completed",
            total_pages=10
        )
        
        assert success is True
        
        # Load checkpoint
        state = manager.load_checkpoint("test_doc")
        
        assert state is not None
        assert state.doc_id == "test_doc"
        assert 5 in state.completed_pages
    
    def test_get_resume_point_no_checkpoint(self, temp_recovery_dir):
        """Test resume point when no checkpoint exists."""
        manager = RecoveryManager(recovery_dir=temp_recovery_dir)
        
        next_page, completed = manager.get_resume_point("new_doc")
        
        assert next_page == 1
        assert completed == []
    
    def test_get_resume_point_with_checkpoint(self, temp_recovery_dir):
        """Test resume point with existing checkpoint."""
        manager = RecoveryManager(recovery_dir=temp_recovery_dir)
        
        # Create checkpoint with some completed pages
        manager.save_checkpoint("doc123", 1, "completed", total_pages=10)
        manager.save_checkpoint("doc123", 2, "completed")
        manager.save_checkpoint("doc123", 3, "completed")
        
        next_page, completed = manager.get_resume_point("doc123")
        
        assert next_page == 4
        assert completed == [1, 2, 3]
    
    def test_mark_completed(self, temp_recovery_dir):
        """Test marking document as completed."""
        manager = RecoveryManager(recovery_dir=temp_recovery_dir)
        
        # Create checkpoint
        manager.save_checkpoint("doc456", 1, "completed", total_pages=5)
        
        # Mark completed
        success = manager.mark_completed("doc456")
        
        assert success is True
        
        # Verify status
        state = manager.load_checkpoint("doc456")
        assert state.status == "COMPLETED"
    
    def test_list_pending_jobs(self, temp_recovery_dir):
        """Test listing pending jobs."""
        manager = RecoveryManager(recovery_dir=temp_recovery_dir)
        
        # Create some checkpoints
        manager.save_checkpoint("pending1", 1, "completed", total_pages=10)
        manager.save_checkpoint("pending2", 5, "completed", total_pages=20)
        
        # Mark one as completed
        manager.mark_completed("pending2")
        
        pending = manager.list_pending_jobs()
        
        # Should only have one pending
        assert len(pending) == 1
        assert pending[0].doc_id == "pending1"
    
    def test_clear_checkpoint(self, temp_recovery_dir):
        """Test clearing checkpoint."""
        manager = RecoveryManager(recovery_dir=temp_recovery_dir)
        
        # Create checkpoint
        manager.save_checkpoint("doc789", 1, "completed", total_pages=5)
        
        # Clear it
        success = manager.clear_checkpoint("doc789")
        
        assert success is True
        
        # Should not be loadable
        state = manager.load_checkpoint("doc789")
        assert state is None
    
    def test_get_progress_stats(self, temp_recovery_dir):
        """Test getting progress statistics."""
        manager = RecoveryManager(recovery_dir=temp_recovery_dir)
        
        # Create checkpoint with progress
        manager.save_checkpoint("doc_progress", 1, "completed", total_pages=100)
        manager.save_checkpoint("doc_progress", 2, "completed")
        manager.save_checkpoint("doc_progress", 3, "failed")
        
        stats = manager.get_progress_stats("doc_progress")
        
        assert stats is not None
        assert stats["total_pages"] == 100
        assert stats["completed"] == 2
        assert stats["failed"] == 1
        assert stats["remaining"] == 98
        assert stats["progress_percent"] == 2.0
    
    def test_atomic_write(self, temp_recovery_dir):
        """Test that writes are atomic."""
        manager = RecoveryManager(recovery_dir=temp_recovery_dir)
        
        # Save checkpoint
        manager.save_checkpoint("atomic_test", 1, "completed", total_pages=5)
        
        # Verify no .tmp file left behind
        recovery_path = Path(temp_recovery_dir)
        tmp_files = list(recovery_path.glob("*.tmp"))
        
        assert len(tmp_files) == 0


if __name__ == "__main__":
    # Run basic smoke tests
    print("Running degradation system tests...")
    
    # Test ProcessingMode
    print("\n1. Testing ProcessingMode hierarchy...")
    assert ProcessingMode.HYBRID < ProcessingMode.OCR_ONLY
    print("   ✓ Mode hierarchy correct")
    
    # Test FallbackManager
    print("\n2. Testing FallbackManager...")
    config = ConfigManager().load_config()
    manager = FallbackManager.get_instance(config)
    mode = manager.determine_optimal_mode()
    print(f"   Current optimal mode: {mode.name}")
    print(f"   Can use OCR_ONLY: {manager.can_use_mode(ProcessingMode.OCR_ONLY)}")
    
    # Test RecoveryManager
    print("\n3. Testing RecoveryManager...")
    recovery = RecoveryManager(recovery_dir="./data/test_recovery")
    recovery.save_checkpoint("test_doc", 1, "completed", total_pages=10)
    next_page, completed = recovery.get_resume_point("test_doc")
    print(f"   Resume point: page {next_page}")
    print(f"   Completed pages: {completed}")
    recovery.clear_checkpoint("test_doc")
    
    # Test retry decorator
    print("\n4. Testing retry decorator...")
    attempt_count = 0
    
    @with_retry(max_retries=3, backoff_delays=[0.1, 0.1, 0.1])
    def test_retry():
        global attempt_count
        attempt_count += 1
        if attempt_count < 2:
            raise ValueError("Test error")
        return "success"
    
    result = test_retry()
    print(f"   Retry succeeded after {attempt_count} attempts")
    
    print("\n✓ All smoke tests passed!")
