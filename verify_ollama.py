"""Verification script for Ollama ModelManager.

This script performs a dry run to verify ModelManager functionality
without requiring actual model downloads.
"""

import asyncio
from local_body.utils.model_manager import ModelManager


async def verify_ollama():
    """Verify Ollama service and ModelManager functionality."""
    print("=" * 60)
    print("Ollama ModelManager Verification")
    print("=" * 60)
    print()
    
    async with ModelManager() as manager:
        # Test 1: Health Check
        print("1. Checking Ollama service health...")
        is_healthy = await manager.check_health()
        print(f"   Result: {'✓ Ollama is running' if is_healthy else '✗ Ollama is not running'}")
        print()
        
        # Test 2: Get Model Status
        print("2. Checking model status...")
        status = await manager.get_model_status()
        print(f"   Loaded models: {status.get('loaded_models', [])}")
        print(f"   Model count: {status.get('model_count', 0)}")
        if 'error' in status:
            print(f"   Error: {status['error']}")
        print()
        
        # Test 3: Check installed models
        if is_healthy:
            print("3. Checking installed models...")
            installed = await manager.get_installed_models()
            print(f"   Installed models: {installed}")
            print()
            
            # Test 4: Check if required models exist
            print("4. Checking required models...")
            required = manager.REQUIRED_MODELS
            print(f"   Required: {required}")
            missing = [m for m in required if m not in installed]
            if missing:
                print(f"   Missing: {missing}")
                print(f"   Note: Run 'await manager.ensure_models_exist()' to auto-pull")
            else:
                print(f"   ✓ All required models are installed")
        else:
            print("3. Skipping model checks (Ollama not running)")
            print()
            print("To install Ollama:")
            print("  - Visit: https://ollama.ai/download")
            print("  - After installation, run: ollama serve")
    
    print()
    print("=" * 60)
    print("Verification Complete")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(verify_ollama())
