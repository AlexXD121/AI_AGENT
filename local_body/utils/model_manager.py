"""Model management system for Ollama local AI models.

This module implements the ModelManager class for managing local Ollama models
including health checks, automatic model pulling, and resource management.
"""

import asyncio
from typing import List, Dict, Any, Optional

import httpx
from loguru import logger

from local_body.core.config_manager import SystemConfig


class ModelManager:
    """Manager for Ollama local AI models.
    
    This class handles:
    - Health checks for Ollama service
    - Automatic model pulling and installation
    - Resource management (model loading/unloading)
    - Model status monitoring
    """
    
    def __init__(self, config: SystemConfig, base_url: str = "http://localhost:11434"):
        """Initialize the model manager.
        
        Args:
            config: SystemConfig instance with model configuration
            base_url: Base URL for Ollama API (default: http://localhost:11434)
        """
        self.config = config
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=300.0)  # 5 min timeout for large models
    
    async def check_health(self) -> bool:
        """Check if Ollama service is running and accessible.
        
        Returns:
            True if Ollama is running, False otherwise
        """
        try:
            response = await self.client.get(f"{self.base_url}/api/tags")
            if response.status_code == 200:
                logger.debug("Ollama service health check passed")
                return True
            else:
                logger.warning(
                    f"Ollama service returned status {response.status_code}"
                )
                return False
                
        except httpx.ConnectError:
            logger.warning(
                "Ollama service not detected on port 11434. "
                "Please ensure Ollama is installed and running."
            )
            return False
        except Exception as e:
            logger.error(f"Ollama health check failed: {e}")
            return False
    
    async def get_installed_models(self) -> List[str]:
        """Get list of currently installed models.
        
        Returns:
            List of installed model names
        """
        try:
            response = await self.client.get(f"{self.base_url}/api/tags")
            if response.status_code == 200:
                data = response.json()
                models = [model["name"] for model in data.get("models", [])]
                return models
            return []
        except Exception as e:
            logger.error(f"Failed to get installed models: {e}")
            return []
    
    async def ensure_models_exist(self) -> bool:
        """Ensure all required models are installed, pulling if necessary.
        
        Returns:
            True if all models are available, False if any pull failed
        """
        logger.info("Checking required Ollama models...")
        
        # Get currently installed models
        installed_models = await self.get_installed_models()
        logger.info(f"Installed models: {installed_models}")
        
        # Determine which models need to be pulled
        missing_models = [
            model for model in self.config.required_ollama_models 
            if model not in installed_models
        ]
        
        if not missing_models:
            logger.success("All required models are already installed")
            return True
        
        logger.info(f"Missing models: {missing_models}")
        
        # Pull each missing model
        for model in missing_models:
            success = await self._pull_model(model)
            if not success:
                logger.error(f"Failed to pull model: {model}")
                return False
        
        logger.success("All required models are now installed")
        return True
    
    async def _pull_model(self, model_name: str) -> bool:
        """Pull a specific model from Ollama registry.
        
        Args:
            model_name: Name of the model to pull
            
        Returns:
            True if pull succeeded, False otherwise
        """
        logger.info(f"Pulling model: {model_name} (this may take several minutes)...")
        
        try:
            # Stream the pull response to track progress
            async with self.client.stream(
                "POST",
                f"{self.base_url}/api/pull",
                json={"name": model_name},
                timeout=None  # No timeout for large downloads
            ) as response:
                if response.status_code != 200:
                    logger.error(
                        f"Pull request failed with status {response.status_code}"
                    )
                    return False
                
                last_logged_percent = 0
                
                # Process streaming response
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    
                    try:
                        import json
                        data = json.loads(line)
                        
                        # Log progress every 10%
                        if "total" in data and "completed" in data:
                            total = data["total"]
                            completed = data["completed"]
                            
                            if total > 0:
                                percent = int((completed / total) * 100)
                                
                                # Log at 10% intervals
                                if percent >= last_logged_percent + 10:
                                    logger.info(
                                        f"Pulling {model_name}: {percent}% "
                                        f"({completed}/{total} bytes)"
                                    )
                                    last_logged_percent = percent
                        
                        # Check for completion
                        if data.get("status") == "success":
                            logger.success(f"Successfully pulled model: {model_name}")
                            return True
                            
                    except json.JSONDecodeError:
                        continue
                
                return True
                
        except httpx.ReadTimeout:
            logger.warning(
                f"Pull timeout for {model_name}. "
                "Model is large and may still be downloading in background."
            )
            return False
        except Exception as e:
            logger.error(f"Failed to pull model {model_name}: {e}")
            return False
    
    async def unload_models(self, models: Optional[List[str]] = None) -> bool:
        """Unload models from memory to free resources.
        
        This is useful when the system is idle to free up RAM/VRAM.
        
        Args:
            models: List of model names to unload. If None, unloads all required models.
            
        Returns:
            True if all models were unloaded successfully
        """
        if models is None:
            models = self.config.required_ollama_models
        
        logger.info(f"Unloading models from memory: {models}")
        
        success = True
        for model in models:
            try:
                # Send a generate request with keep_alive=0 to force unload
                response = await self.client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": model,
                        "prompt": "",
                        "keep_alive": 0
                    }
                )
                
                if response.status_code == 200:
                    logger.debug(f"Unloaded model: {model}")
                else:
                    logger.warning(
                        f"Failed to unload {model}: status {response.status_code}"
                    )
                    success = False
                    
            except Exception as e:
                logger.error(f"Error unloading model {model}: {e}")
                success = False
        
        if success:
            logger.success("All models unloaded from memory")
        
        return success
    
    async def get_model_status(self) -> Dict[str, Any]:
        """Get status of currently loaded models.
        
        Returns:
            Dictionary with model status information
        """
        try:
            # Try to get running models from /api/ps endpoint
            response = await self.client.get(f"{self.base_url}/api/ps")
            
            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                
                status = {
                    "loaded_models": [m.get("name") for m in models],
                    "model_count": len(models),
                    "details": models
                }
                
                logger.debug(f"Model status: {status}")
                return status
            else:
                logger.warning("Could not retrieve model status from /api/ps")
                return {"loaded_models": [], "model_count": 0, "details": []}
                
        except Exception as e:
            logger.error(f"Failed to get model status: {e}")
            return {"loaded_models": [], "model_count": 0, "details": [], "error": str(e)}
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def unload_model(self, model_name: str) -> bool:
        """Aggressively unload a specific model from memory.
        
        This performs:
        1. Ollama API unload (keep_alive=0)
        2. Python garbage collection
        3. GPU cache clearing (if applicable)
        
        Args:
            model_name: Name of model to unload
            
        Returns:
            True if unloaded successfully
        """
        logger.info(f"Aggressively unloading model: {model_name}")
        
        try:
            # Step 1: Unload via Ollama API
            response = await self.client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": model_name,
                    "prompt": "",
                    "keep_alive": 0
                }
            )
            
            if response.status_code == 200:
                logger.debug(f"Ollama unloaded: {model_name}")
            else:
                logger.warning(f"Ollama unload failed for {model_name}: {response.status_code}")
            
            # Step 2: Force Python garbage collection
            import gc
            gc.collect()
            logger.debug("Garbage collection triggered")
            
            # Step 3: Clear GPU cache if available
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    torch.cuda.synchronize()
                    logger.debug("GPU cache cleared")
            except ImportError:
                # torch not installed, skip GPU cleanup
                pass
            
            logger.success(f"Model {model_name} fully unloaded from memory")
            return True
            
        except Exception as e:
            logger.error(f"Failed to unload model {model_name}: {e}")
            return False
    
    async def optimize_resources(self, current_stage: str) -> None:
        """Optimize memory by unloading models not needed for current stage.
        
        Stage-based unloading strategy:
        - LAYOUT → Keep layout, unload others
        - OCR → Keep OCR, unload others
        - VISION → Keep vision, unload OCR/layout
        - VALIDATION → Unload processing models
        - COMPLETED → Unload ALL models
        
        Args:
            current_stage: Current processing stage
        """
        logger.info(f"Optimizing resources for stage: {current_stage}")
        
        # Define which models to unload for each stage
        stage_unload_map = {
            "LAYOUT": ["llama3.2", "llama3.2-vision"],  # Keep layout models
            "OCR": ["llama3.2-vision"],  # Keep OCR, unload vision
            "VISION": ["llama3.2"],  # Keep vision, unload text models
            "VALIDATION": ["llama3.2-vision"],  # Unload heavy vision
            "COMPLETED": self.config.required_ollama_models,  # Unload ALL
        }
        
        models_to_unload = stage_unload_map.get(current_stage, [])
        
        if models_to_unload:
            logger.info(f"Unloading {len(models_to_unload)} models for {current_stage} stage")
            
            for model in models_to_unload:
                await self.unload_model(model)
            
            # Final cleanup
            import gc
            gc.collect()
            
            logger.success(f"Resource optimization complete for {current_stage}")
        else:
            logger.debug(f"No models to unload for {current_stage} stage")
    
    def get_memory_stats(self) -> dict:
        """Get current memory usage statistics.
        
        Returns:
            Dictionary with memory metrics
        """
        try:
            import psutil
            import gc
            
            # System memory
            mem = psutil.virtual_memory()
            
            stats = {
                "ram_total_gb": mem.total / (1024**3),
                "ram_available_gb": mem.available / (1024**3),
                "ram_percent": mem.percent,
                "python_objects": len(gc.get_objects())
            }
            
            # GPU memory if available
            try:
                import torch
                if torch.cuda.is_available():
                    stats["gpu_allocated_mb"] = torch.cuda.memory_allocated() / (1024**2)
                    stats["gpu_reserved_mb"] = torch.cuda.memory_reserved() / (1024**2)
                    stats["gpu_available"] = True
                else:
                    stats["gpu_available"] = False
            except ImportError:
                stats["gpu_available"] = False
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get memory stats: {e}")
            return {"error": str(e)}
