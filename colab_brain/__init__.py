"""Cloud Brain module for GPU-accelerated vision-language inference.

This module runs on Google Colab with T4 GPU and provides vision-language
model inference using vLLM with Qwen2.5-VL-7B.

Note: This module requires Colab-specific dependencies (vLLM, FastAPI) that
may not be available in local testing environments.
"""

__version__ = "0.1.0"

__all__ = []

# Optional imports - may not be available in all environments
try:
    from colab_brain.inference import VisionModelEngine
    __all__.append("VisionModelEngine")
except ImportError:
    VisionModelEngine = None

try:
    from colab_brain.server import app
    __all__.append("app")
except ImportError:
    app = None
