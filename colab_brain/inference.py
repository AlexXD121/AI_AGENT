"""Vision-language model inference using vLLM with Qwen2.5-VL-7B.

Optimized for Google Colab T4 GPU (16GB VRAM) using 4-bit AWQ quantization.
"""

import base64
import io
from typing import Optional

from PIL import Image
from loguru import logger

try:
    from vllm import LLM, SamplingParams
except ImportError:
    logger.warning("vLLM not installed")
    LLM = None
    SamplingParams = None


class VisionModelEngine:
    """Vision model inference engine"""
    
    def __init__(self, model_name: str = "Qwen/Qwen2.5-VL-7B-Instruct-AWQ"):
        if LLM is None:
            raise ImportError("vLLM required: pip install vllm")
        
        logger.info(f"Loading: {model_name}")
        
        self.llm = LLM(
            model=model_name,
            quantization="awq",
            gpu_memory_utilization=0.9,
            trust_remote_code=True,
            max_model_len=4096,
            dtype="half"
        )
        self.model_name = model_name
        logger.success("Model loaded")
    
    def process_request(self, query: str, image: Image.Image) -> str:
        """Process vision request"""
        try:
            img_b64 = self._image_to_base64(image)
            
            messages = [{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
                    {"type": "text", "text": query}
                ]
            }]
            
            params = SamplingParams(temperature=0.7, max_tokens=512, top_p=0.9)
            outputs = self.llm.generate(messages, sampling_params=params)
            
            return outputs[0].outputs[0].text.strip()
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            raise
    
    def _image_to_base64(self, image: Image.Image) -> str:
        """Convert PIL Image to base64"""
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG")
        return base64.b64encode(buffer.getvalue()).decode()
