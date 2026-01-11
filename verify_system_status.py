#!/usr/bin/env python3
"""System-Wide Health Verification for Sovereign-Doc (Async Version).

This script performs startup sequence checks on all major components.
"""

import sys
import os
import asyncio
from loguru import logger

# Configure console-only logging
logger.remove()
logger.add(sys.stdout, format="<level>{message}</level>", level="INFO")

# Add local path
sys.path.append(os.getcwd())


def print_header(title: str):
    """Print section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


async def main():
    """Run all system health checks (async)."""
    print("\n" + "="*60)
    print("  SOVEREIGN-DOC SYSTEM HEALTH VERIFICATION")
    print("="*60)
    
    results = {}
    
    # --- 1. CONFIGURATION ---
    print_header("Task 2: Configuration Management")
    try:
        from local_body.core.config_manager import ConfigManager
        
        config_manager = ConfigManager()
        sys_config = config_manager.load_config()
        print(f"✅ Configuration Loaded - Mode: {sys_config.processing_mode}")
        results['Configuration'] = True
    except Exception as e:
        print(f"❌ Configuration Failed: {e}")
        results['Configuration'] = False
        return 1

    # --- 2. INFRASTRUCTURE ---
    print_header("Task 3: Infrastructure")
    
    # Vector Store (Async)
    try:
        from local_body.database.vector_store import DocumentVectorStore
        vector_store = DocumentVectorStore(config=sys_config)
        
        # AWAIT the async health check
        is_healthy = await vector_store.check_health()
        
        if is_healthy:
            print("✅ Qdrant Vector Store - Connected")
            results['Vector Store'] = True
        else:
            print("❌ Qdrant Vector Store - Health check failed")
            results['Vector Store'] = False
    except ImportError as e:
        print(f"❌ Qdrant Vector Store - Missing Dependency: {e}")
        results['Vector Store'] = False
    except Exception as e:
        print(f"❌ Qdrant Vector Store Failed: {e}")
        results['Vector Store'] = False

    # Model Manager (Async)
    try:
        from local_body.utils.model_manager import ModelManager
        model_manager = ModelManager(config=sys_config)
        
        # AWAIT the async health check
        is_healthy = await model_manager.check_health()
        
        if is_healthy:
            print("✅ Ollama Model Manager - Running")
            results['Ollama'] = True
        else:
            print("❌ Ollama Model Manager - Not running (start with: ollama serve)")
            results['Ollama'] = False
    except Exception as e:
        print(f"❌ Ollama Model Manager Failed: {e}")
        results['Ollama'] = False

    # --- 3. VISION PIPELINE ---
    print_header("Task 4: Vision Pipeline")
    
    # Layout Agent
    try:
        import cv2
        from local_body.agents.layout_agent import LayoutAgent
        layout_agent = LayoutAgent(config=sys_config.model_dump())
        print("✅ LayoutAgent (YOLOv8) - Initialized")
        results['Layout Agent'] = True
    except ImportError as e:
        print(f"❌ LayoutAgent - Missing Dependency: {e}")
        results['Layout Agent'] = False
    except Exception as e:
        print(f"❌ LayoutAgent Failed: {e}")
        results['Layout Agent'] = False

    # OCR Agent
    try:
        from local_body.agents.ocr_agent import OCRAgent
        ocr_agent = OCRAgent(config=sys_config.model_dump())
        print("✅ OCRAgent (PaddleOCR) - Initialized")
        results['OCR Agent'] = True
    except ImportError as e:
        print(f"❌ OCRAgent - Missing Dependency: {e}")
        results['OCR Agent'] = False
    except Exception as e:
        print(f"❌ OCRAgent Failed: {e}")
        results['OCR Agent'] = False

    # --- 4. CLOUD CONNECTIVITY ---
    print_header("Task 5: Cloud Connectivity")
    
    # Secure Tunnel
    try:
        from local_body.tunnel.secure_tunnel import SecureTunnel
        tunnel = SecureTunnel(config=sys_config)
        print("✅ SecureTunnel - Initialized (not started)")
        results['Secure Tunnel'] = True
    except ImportError as e:
        print(f"❌ SecureTunnel - Missing Dependency (pyngrok): {e}")
        results['Secure Tunnel'] = False
    except Exception as e:
        print(f"❌ SecureTunnel Failed: {e}")
        results['Secure Tunnel'] = False

    # Vision Agent
    try:
        from local_body.agents.vision_agent import VisionAgent
        from unittest.mock import Mock
        
        # Use mock tunnel for verification
        mock_tunnel = Mock()
        mock_tunnel.get_status.return_value = {'active': False, 'public_url': None}
        
        vision_agent = VisionAgent(config=sys_config.model_dump(), tunnel=mock_tunnel)
        print("✅ VisionAgent - Initialized")
        results['Vision Agent'] = True
    except ImportError as e:
        print(f"❌ VisionAgent - Missing Dependency: {e}")
        results['Vision Agent'] = False
    except Exception as e:
        print(f"❌ VisionAgent Failed: {e}")
        results['Vision Agent'] = False

    # Summary
    print_header("VERIFICATION SUMMARY")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for component, status in results.items():
        status_icon = "✅" if status else "❌"
        print(f"{status_icon} {component}")
    
    print(f"\n{passed}/{total} components operational")
    
    print("\n" + "="*60)
    if all(results.values()):
        print("  ✅ ALL SYSTEMS OPERATIONAL")
        print("="*60 + "\n")
        return 0
    else:
        print("  ⚠️  SOME SYSTEMS NEED ATTENTION")
        print("="*60 + "\n")
        return 1


if __name__ == "__main__":
    # Run the async main function
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
