"""Demonstration of graceful degradation system.

Shows intelligent mode selection, retry logic, and page-level recovery.
"""

import asyncio
import time
from loguru import logger
from local_body.core.config_manager import ConfigManager
from local_body.core.fallback import FallbackManager, ProcessingMode, with_retry
from local_body.core.recovery import RecoveryManager, RecoveryState


def print_separator(title: str = ""):
    """Print visual separator."""
    if title:
        print(f"\n{'='*70}")
        print(f"  {title}")
        print('='*70)
    else:
        print('-'*70)


async def demo_mode_selection():
    """Demo: Intelligent mode selection."""
    print_separator("DEMO 1: Intelligent Mode Selection")
    
    config = ConfigManager().load_config()
    manager = FallbackManager.get_instance(config)
    
    print("\n🤖 Determining optimal processing mode...\n")
    
    # Get optimal mode
    mode = manager.determine_optimal_mode()
    
    print(f"Selected Mode: {mode.name}")
    print(f"Mode Level: {mode.value}")
    
    # Show requirements
    requirements = manager.MODE_REQUIREMENTS[mode]
    print(f"\nMode Requirements:")
    print(f"  Min RAM: {requirements.min_ram_gb}GB")
    print(f"  Needs GPU: {'Yes' if requirements.needs_gpu else 'No'}")
    print(f"  Needs Database: {'Yes' if requirements.needs_database else 'No'}")
    print(f"  Needs Network: {'Yes' if requirements.needs_network else 'No'}")
    print(f"  Description: {requirements.description}")
    
    # Check mode availability
    print(f"\n📋 Mode Availability Check:")
    for test_mode in ProcessingMode:
        can_use = manager.can_use_mode(test_mode)
        status = "✅ Available" if can_use else "❌ Not available"
        print(f"  {test_mode.name:15} {status}")


async def demo_mode_downgrade():
    """Demo: Mode downgrade hierarchy."""
    print_separator("DEMO 2: Mode Downgrade Hierarchy")
    
    config = ConfigManager().load_config()
    manager = FallbackManager.get_instance(config)
    
    print("\n⬇️  Demonstrating mode downgrade path:\n")
    
    current_mode = ProcessingMode.HYBRID
    
    while True:
        next_mode = manager.downgrade_mode(current_mode)
        
        print(f"  {current_mode.name:15} → {next_mode.name}")
        
        if current_mode == next_mode:
            print(f"  (Reached lowest mode: {next_mode.name})")
            break
        
        current_mode = next_mode


def demo_retry_decorator():
    """Demo: Retry decorator with recovery."""
    print_separator("DEMO 3: Retry Decorator with Recovery")
    
    print("\n🔄 Testing retry logic...\n")
    
    # Successful function
    print("1. Function that succeeds immediately:")
    
    @with_retry(max_retries=3, backoff_delays=[0.5, 1.0, 2.0])
    def always_succeeds():
        return "Success!"
    
    result = always_succeeds()
    print(f"   ✅ Result: {result}\n")
    
    # Flaky function that recovers
    print("2. Flaky function that succeeds on retry:")
    attempt_count = 0
    
    @with_retry(max_retries=3, backoff_delays=[0.3, 0.3, 0.3])
    def flaky_function():
        nonlocal attempt_count
        attempt_count += 1
        
        if attempt_count < 3:
            raise ValueError(f"Attempt {attempt_count} failed (simulated)")
        
        return "Success on attempt 3!"
    
    result = flaky_function()
    print(f"   ✅ Result: {result}")
    print(f"   Took {attempt_count} attempts\n")
    
    # Function that exhausts retries
    print("3. Function that exhausts all retries:")
    
    @with_retry(max_retries=3, backoff_delays=[0.2, 0.2, 0.2], on_failure_downgrade=True)
    def always_fails():
        raise RuntimeError("Persistent failure (simulated)")
    
    try:
        always_fails()
    except RuntimeError as e:
        print(f"   ❌ All retries exhausted: {e}")
        print(f"   Mode downgrade was requested")


def demo_recovery_checkpoint():
    """Demo: Page-level checkpoint and recovery."""
    print_separator("DEMO 4: Page-Level Checkpoint & Recovery")
    
    print("\n💾 Demonstrating checkpoint system...\n")
    
    manager = RecoveryManager(recovery_dir="./data/demo_recovery")
    
    # Simulate processing a document
    doc_id = "demo_document_2026"
    total_pages = 10
    
    print(f"1. Starting new document: {doc_id}")
    print(f"   Total pages: {total_pages}\n")
    
    # Process first few pages
    print("2. Processing pages 1-5...")
    for page in range(1, 6):
        time.sleep(0.1)  # Simulate processing
        manager.save_checkpoint(doc_id, page, "completed", total_pages=total_pages)
        print(f"   ✓ Page {page} completed")
    
    # Simulate crash by "restarting"
    print("\n3. ⚠️  Simulating crash...\n")
    print("4. Recovering from checkpoint...")
    
    # Load and resume
    next_page, completed = manager.get_resume_point(doc_id)
    print(f"   Resume from page: {next_page}")
    print(f"   Already completed: {completed}")
    
    # Continue processing
    print(f"\n5. Resuming processing from page {next_page}...")
    for page in range(next_page, total_pages + 1):
        time.sleep(0.1)
        manager.save_checkpoint(doc_id, page, "completed")
        print(f"   ✓ Page {page} completed")
    
    # Mark complete
    manager.mark_completed(doc_id)
    print(f"\n6. ✅ Document marked as COMPLETED")
    
    # Show final stats
    stats = manager.get_progress_stats(doc_id)
    print(f"\nFinal Statistics:")
    print(f"  Total Pages: {stats['total_pages']}")
    print(f"  Completed: {stats['completed']}")
    print(f"  Progress: {stats['progress_percent']:.0f}%")
    print(f"  Status: {stats['status']}")
    
    # Cleanup
    manager.clear_checkpoint(doc_id)
    print(f"\n7. Checkpoint cleared (cleanup)")


def demo_pending_jobs():
    """Demo: List pending jobs."""
    print_separator("DEMO 5: Pending Jobs Recovery")
    
    print("\n📋 Managing interrupted jobs...\n")
    
    manager = RecoveryManager(recovery_dir="./data/demo_recovery")
    
    # Create some pending jobs
    print("1. Creating simulated interrupted jobs...")
    for i in range(1, 4):
        doc_id = f"interrupted_doc_{i}"
        pages_done = i * 5
        
        for page in range(1, pages_done + 1):
            manager.save_checkpoint(doc_id, page, "completed", total_pages=20)
        
        stats = manager.get_progress_stats(doc_id)
        print(f"   {doc_id}: {stats['completed']}/20 pages ({stats['progress_percent']:.0f}%)")
    
    # List pending jobs
    print("\n2. Listing all pending jobs:")
    pending = manager.list_pending_jobs()
    
    print(f"   Found {len(pending)} pending job(s)\n")
    
    for state in pending:
        completed = len(state.completed_pages)
        progress = (completed / state.total_pages * 100) if state.total_pages > 0 else 0
        print(f"   📄 {state.doc_id}")
        print(f"      Progress: {completed}/{state.total_pages} pages ({progress:.0f}%)")
        print(f"      Last updated: {state.last_updated}")
        print()
    
    # Cleanup
    print("3. Cleaning up demo checkpoints...")
    for state in pending:
        manager.clear_checkpoint(state.doc_id)
    print("   ✓ All checkpoints cleared")


async def demo_integration():
    """Demo: Full integration of mode selection + recovery."""
    print_separator("DEMO 6: Full Integration Example")
    
    print("\n🔗 Demonstrating integrated workflow...\n")
    
    config = ConfigManager().load_config()
    fallback = FallbackManager.get_instance(config)
    recovery = RecoveryManager(recovery_dir="./data/demo_recovery")
    
    doc_id = "integrated_demo_doc"
    total_pages = 8
    
    # Step 1: Determine mode
    print("1. Determining optimal processing mode...")
    mode = fallback.determine_optimal_mode()
    print(f"   Selected: {mode.name}\n")
    
    # Step 2: Check for existing checkpoint
    print("2. Checking for previous checkpoint...")
    next_page, completed = recovery.get_resume_point(doc_id)
    
    if completed:
        print(f"   ✓ Resuming from page {next_page} ({len(completed)} pages already done)")
    else:
        print(f"   ℹ️  Starting fresh from page 1\n")
    
    # Step 3: Process with retry
    print(f"3. Processing pages {next_page}-{total_pages} with retry protection...")
    
    @with_retry(max_retries=2, backoff_delays=[0.2, 0.3], on_failure_downgrade=True)
    def process_page(page_num):
        # Simulate occasional failure
        import random
        if random.random() < 0.2:  # 20% failure rate
            raise ValueError(f"Simulated processing error on page {page_num}")
        
        time.sleep(0.1)
        return f"Page {page_num} processed"
    
    for page in range(next_page, total_pages + 1):
        try:
            result = process_page(page)
            recovery.save_checkpoint(doc_id, page, "completed", total_pages=total_pages, processing_mode=mode.name)
            print(f"   ✓ Page {page} completed")
        except Exception as e:
            recovery.save_checkpoint(doc_id, page, "failed", total_pages=total_pages)
            print(f"   ✗ Page {page} failed: {e}")
    
    # Step 4: Mark complete
    recovery.mark_completed(doc_id)
    stats = recovery.get_progress_stats(doc_id)
    
    print(f"\n4. Processing complete!")
    print(f"   Completed: {stats['completed']}/{stats['total_pages']} pages")
    print(f"   Failed: {stats['failed']} pages")
    print(f"   Mode used: {stats['processing_mode']}")
    
    # Cleanup
    recovery.clear_checkpoint(doc_id)


async def main():
    """Run all demonstrations."""
    print("\n" + "="*70)
    print("  GRACEFUL DEGRADATION SYSTEM DEMONSTRATION")
    print("  Sovereign Doc - Intelligent Fallback & Recovery")
    print("="*70)
    
    try:
        await demo_mode_selection()
        await asyncio.sleep(1)
        
        await demo_mode_downgrade()
        await asyncio.sleep(1)
        
        demo_retry_decorator()
        await asyncio.sleep(1)
        
        demo_recovery_checkpoint()
        await asyncio.sleep(1)
        
        demo_pending_jobs()
        await asyncio.sleep(1)
        
        await demo_integration()
        
        print_separator()
        print("\n✅ All demonstrations completed successfully!")
        print("\nKey Features Demonstrated:")
        print("  1. ✅ Intelligent mode selection based on resources")
        print("  2. ✅ Automatic mode downgrading under constraints")
        print("  3. ✅ Retry decorator with exponential backoff")
        print("  4. ✅ Page-level checkpoint and recovery")
        print("  5. ✅ Pending jobs management")
        print("  6. ✅ Full integration workflow")
        print("\nTo integrate:")
        print("  from local_body.core.fallback import FallbackManager, with_retry")
        print("  from local_body.core.recovery import RecoveryManager")
        print()
    
    except Exception as e:
        logger.error(f"Demo failed: {e}", exc_info=True)
        print(f"\n❌ Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    import sys
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
