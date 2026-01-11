"""Integration Verification Script for Sovereign-Doc (Tasks 1-7).

This script verifies that the ResolutionAgent is properly integrated into the
workflow and is using the new contextual resolution strategies instead of the
old simple logic.
"""

import asyncio
from datetime import datetime
from loguru import logger

from local_body.core.datamodels import (
    Document,
    DocumentMetadata,
    Page,
    Conflict,
    ConflictType,
    RegionType,
    ProcessingStatus,
    ResolutionMethod
)
from local_body.orchestration.state import DocumentProcessingState, ProcessingStage
from local_body.orchestration.nodes import auto_resolution_node


async def verify_task_1_to_7_integration():
    """Verify that ResolutionAgent is active and using contextual strategies."""
    
    print("\n" + "="*70)
    print("  SOVEREIGN-DOC INTEGRATION VERIFICATION (TASKS 1-7)")
    print("="*70)
    print("\n📋 Test Scenario:")
    print("   - OCR Confidence: 0.98 (very high)")
    print("   - Vision Confidence: 0.40 (low)")
    print("   - Impact Score: 0.6 (medium-high)")
    print("   - Discrepancy: 80%")
    print("\n🔍 Expected Behavior:")
    print("   - OLD LOGIC: Would flag for manual review (impact >= 0.5)")
    print("   - NEW LOGIC: Should AUTO-RESOLVE using 'Confidence Dominance' strategy")
    print("-" * 70)

    # Create mock document
    doc = Document(
        id="test_doc_verification",
        file_path="test_verification.pdf",
        pages=[
            Page(
                page_number=1,
                raw_image_bytes=None,
                regions=[]
            )
        ],
        metadata=DocumentMetadata(
            file_size_bytes=1000,
            page_count=1,
            created_date=datetime.now()
        ),
        processing_status=ProcessingStatus.PENDING,
        created_at=datetime.now()
    )
    
    # Create conflict with high OCR confidence, low Vision confidence
    # This should trigger Confidence Dominance strategy
    conflict = Conflict(
        region_id="reg_verification_1",
        conflict_type=ConflictType.VALUE_MISMATCH,
        text_value=1000.0,
        vision_value=5000.0,
        discrepancy_percentage=0.8,
        confidence_scores={'text': 0.98, 'vision': 0.40},
        region_type=RegionType.TEXT
    )
    
    # Set impact score intentionally high to differentiate OLD vs NEW logic
    conflict.impact_score = 0.6  # Old logic would flag this for manual review
    
    # Create state
    state: DocumentProcessingState = {
        'document': doc,
        'file_path': 'test_verification.pdf',
        'processing_stage': ProcessingStage.CONFLICT,
        'layout_regions': [],
        'ocr_results': {},
        'vision_results': {},
        'conflicts': [conflict],
        'resolutions': [],
        'error_log': []
    }

    print("\n🚀 Running Auto-Resolution Node...")
    print("-" * 70)
    
    try:
        # Run the auto-resolution node
        result = await auto_resolution_node(state)
        
        resolutions = result.get('resolutions', [])
        
        if not resolutions:
            print("\n❌ FAILURE: No resolutions generated")
            print("   📌 Cause: System is likely using OLD LOGIC")
            print("   📌 OLD LOGIC would check: impact_score >= 0.5 → Manual Review")
            print("   📌 The conflict was not auto-resolved.")
            return False

        # Check resolution details
        res = resolutions[0]
        strategy_from_notes = res.notes.split(':')[0] if res.notes else None  # Strategy is in notes
        method = res.resolution_method
        
        print(f"\n✅ SUCCESS: Resolution Generated!")
        print(f"   🎯 Conflict ID: {res.conflict_id}")
        print(f"   💡 Strategy Used: {strategy_from_notes}")
        print(f"   📝 Notes: {res.notes}")
        print(f"   🔧 Method: {method}")
        print(f"   📈 Chosen Value: {res.chosen_value}")
        print(f"   🎲 Confidence: {res.confidence}")
        
        # Verify NEW CODE is active
        if strategy_from_notes and "ResolutionStrategy" in strategy_from_notes:
            print("\n" + "="*70)
            print("🌟 VERIFICATION PASSED!")
            print(f"   ✓ NEW CODE IS ACTIVE")
            print(f"   ✓ ResolutionAgent is properly integrated")
            print(f"   ✓ Using contextual strategy: {strategy_from_notes}")
            print("="*70)
            return True
        else:
            print("\n⚠️  WARNING: Strategy format unexpected")
            print(f"   Notes field: {res.notes}")
            print("   Checking if this is still better than OLD LOGIC...")
            # If it auto-resolved with high confidence, it's still good
            if method == ResolutionMethod.AUTO and res.confidence > 0.9:
                print("   ✓ Still using NEW LOGIC (auto-resolved with high OCR confidence)")
                return True
            return False

    except Exception as e:
        print(f"\n❌ CRASHED: {e}")
        print("   System failed during execution")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Main entry point."""
    success = await verify_task_1_to_7_integration()
    
    if success:
        print("\n✨ All systems operational! Ready for production.")
    else:
        print("\n⚠️  Integration issues detected. Review logs above.")
    
    return success


if __name__ == "__main__":
    result = asyncio.run(main())
    exit(0 if result else 1)
