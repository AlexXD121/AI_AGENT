"""Vision inference agent for remote and local image analysis.

This agent sends images to the Cloud Brain (Colab) for vision-language analysis
with caching, retry logic, and local fallback capabilities.
"""

import hashlib
import httpx
from typing import Dict, Any, Optional
from io import BytesIO
from PIL import Image
from loguru import logger

from local_body.agents.base import BaseAgent
from local_body.core.datamodels import Document
from local_body.tunnel.secure_tunnel import SecureTunnel


class VisionAgent(BaseAgent):
    """Vision inference agent with remote Cloud Brain and local fallback.
    
    Features:
    - Remote inference via Cloud Brain (Colab)
    - In-memory caching for efficiency
    - Automatic retry with timeout handling
    - Local Ollama fallback on connection failure
    
    Requirements:
    - Req 3.4: Deep document analysis
    - Req 15.3: Hybrid cloud-local fallback
    - Req 2.5: Result caching
    """
    
    def __init__(self, config: Dict[str, Any], tunnel: SecureTunnel):
        """Initialize vision agent.
        
        Args:
            config: System configuration
            tunnel: SecureTunnel instance for Cloud Brain connectivity
        """
        super().__init__(agent_type="vision", config=config)
        
        self.tunnel = tunnel
        self._cache: Dict[str, str] = {}
        
        # Configuration
        self.max_retries = self.get_config("max_retries", 3)
        self.timeout = self.get_config("timeout", 30)
        self.enable_cache = self.get_config("enable_cache", True)
        self.fallback_model = self.get_config("fallback_model", "llama3.2-vision")
        
        # Image compression settings
        self.api_key = self.get_config("brain_secret", "sovereign-secret-key")
        self.max_image_size = 1024
        self.jpeg_quality = 85
        
        logger.info(f"VisionAgent initialized (retries={self.max_retries}, timeout={self.timeout}s)")
    
    async def process(self, document: Document) -> Document:
        """Process document with vision analysis.
        
        Args:
            document: Document to analyze
            
        Returns:
            Document with vision summaries added
        """
        logger.info(f"Processing document {document.id} with vision analysis")
        
        for page_idx, page in enumerate(document.pages):
            if not page.raw_image_bytes:
                logger.warning(f"Page {page_idx} has no image bytes, skipping")
                continue
            
            try:
                # Standard vision prompt
                query = "Describe this document structure and content in detail."
                
                # Try remote inference first
                try:
                    result = await self.analyze_image_remote(
                        page.raw_image_bytes,
                        query
                    )
                    logger.debug(f"Page {page_idx}: Remote analysis success")
                    
                except (httpx.ConnectError, httpx.TimeoutException, ConnectionError) as e:
                    logger.warning(f"Cloud Brain unreachable: {e}. Falling back to local model.")
                    result = await self._analyze_local(page.raw_image_bytes, query)
                    logger.debug(f"Page {page_idx}: Local fallback used")
                
                # Store result in page metadata
                if not page.metadata:
                    page.metadata = {}
                page.metadata['vision_summary'] = result
                
            except Exception as e:
                logger.error(f"Page {page_idx} vision analysis failed: {e}")
                if not page.metadata:
                    page.metadata = {}
                page.metadata['vision_summary'] = f"ERROR: {str(e)}"
        
        return document
    
    def _compress_image(self, image_bytes: bytes) -> bytes:
        """Compress image to reduce transfer size.
        
        - Resize to max 1024px (maintaining aspect ratio)
        - Convert to RGB if needed
        - Save as JPEG with 85% quality
        
        Args:
            image_bytes: Original image bytes
            
        Returns:
            Compressed image bytes
        """
        try:
            # Load image
            img = Image.open(BytesIO(image_bytes))
            
            # Resize if needed
            if img.width > self.max_image_size or img.height > self.max_image_size:
                # Calculate new dimensions maintaining aspect ratio
                if img.width > img.height:
                    new_width = self.max_image_size
                    new_height = int(img.height * (self.max_image_size / img.width))
                else:
                    new_height = self.max_image_size
                    new_width = int(img.width * (self.max_image_size / img.height))
                
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                logger.debug(f"Resized image from {image_bytes.__len__()} to {new_width}x{new_height}")
            
            # Convert RGBA to RGB if needed
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Compress to JPEG
            output = BytesIO()
            img.save(output, format='JPEG', quality=self.jpeg_quality, optimize=True)
            compressed_bytes = output.getvalue()
            
            reduction = (1 - len(compressed_bytes) / len(image_bytes)) * 100
            logger.debug(f"Compressed image: {len(image_bytes)} → {len(compressed_bytes)} bytes ({reduction:.1f}% reduction)")
            
            return compressed_bytes
            
        except Exception as e:
            logger.warning(f"Image compression failed: {e}. Using original image.")
            return image_bytes
    
    async def analyze_image_remote(
        self,
        image_bytes: bytes,
        query: str
    ) -> str:
        """Analyze image using remote Cloud Brain.
        
        Args:
            image_bytes: Image data
            query: Analysis query
            
        Returns:
            Analysis result text
            
        Raises:
            ConnectionError: If Cloud Brain is unreachable
            httpx.TimeoutException: If request times out
            httpx.HTTPStatusError: If authentication fails (401)
        """
        # Check cache first
        if self.enable_cache:
            cache_key = self._generate_cache_key(image_bytes, query)
            if cache_key in self._cache:
                logger.debug("Cache hit - returning cached result")
                return self._cache[cache_key]
        
        # Get tunnel URL
        status = self.tunnel.get_status()
        if not status['active'] or not status['public_url']:
            raise ConnectionError("Cloud Brain tunnel not active")
        
        public_url = status['public_url']
        endpoint = f"{public_url}/analyze"
        
        # Get security manager for auth token
        from local_body.core.security import get_security_manager
        security_mgr = get_security_manager()
        
        # Early check: If no access token, switch to local mode immediately
        try:
            auth_header = security_mgr.get_auth_header()
        except ValueError:
            logger.info("Remote Brain access token not found. Switching to Local Vision Model.")
            raise ConnectionError("Access token not configured")
        
        # Check if requests should be blocked due to security
        if security_mgr.should_block_request():
            raise ConnectionError("Requests blocked due to security concerns")
        
        # Send request with retry
        async with httpx.AsyncClient(timeout=self.timeout, verify=True) as client:  # SSL verification enabled
            for attempt in range(self.max_retries):
                try:
                    logger.debug(f"Sending request to {endpoint} (attempt {attempt+1}/{self.max_retries})")
                    
                    # Compress image before sending
                    compressed_bytes = self._compress_image(image_bytes)
                    
                    # Prepare multipart request with auth headers
                    files = {'file': ('image.jpg', compressed_bytes, 'image/jpeg')}
                    data = {'query': query}
                    
                    # Build headers with security token
                    headers = {
                        'Authorization': f'Bearer {self.api_key}',  # Legacy API key (backward compat)
                    }
                    
                    
                    # Use the auth header we already validated earlier
                    headers.update(auth_header)
                    
                    response = await client.post(endpoint, files=files, data=data, headers=headers)
                    
                    # Handle authentication errors specifically
                    if response.status_code == 401:
                        logger.error("Authentication failed (401 Unauthorized)")
                        security_mgr.record_auth_failure(endpoint, 401)
                        
                        # Trigger security alert
                        from local_body.core.alerts import AlertManager, AlertSeverity, AlertComponent
                        alert_mgr = AlertManager.get_instance()
                        alert_mgr.create_alert(
                            component=AlertComponent.SECURITY,
                            severity=AlertSeverity.ERROR,
                            message="Colab Brain authentication failed - check access token",
                            metadata={"endpoint": endpoint}
                        )
                        
                        raise httpx.HTTPStatusError(
                            "Authentication failed",
                            request=response.request,
                            response=response
                        )
                    
                    response.raise_for_status()
                    
                    # Extract result
                    result_data = response.json()
                    result = result_data.get('response', '')
                    
                    # Cache result
                    if self.enable_cache:
                        self._cache[cache_key] = result
                    
                    logger.success(f"Remote analysis successful ({len(result)} chars)")
                    return result
                    
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 401:
                        # Don't retry auth failures
                        raise
                    logger.error(f"HTTP error {e.response.status_code}: {e}")
                    if attempt == self.max_retries - 1:
                        raise
                    
                except (httpx.ConnectError, httpx.TimeoutException) as e:
                    logger.warning(f"Connection attempt {attempt+1} failed: {e}")
                    if attempt == self.max_retries - 1:
                        raise
        
        raise ConnectionError("All retry attempts failed")
    
    async def _analyze_local(self, image_bytes: bytes, query: str) -> str:
        """Fallback to local Ollama vision model.
        
        Args:
            image_bytes: Image data
            query: Analysis query
            
        Returns:
            Local analysis result
        """
        try:
            # Use Ollama API for local vision
            logger.info(f"Using local fallback model: {self.fallback_model}")
            
            # Encode image to base64
            import base64
            image_b64 = base64.b64encode(image_bytes).decode()
            
            # Call Ollama API
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    "http://localhost:11434/api/generate",
                    json={
                        "model": self.fallback_model,
                        "prompt": query,
                        "images": [image_b64],
                        "stream": False
                    }
                )
                response.raise_for_status()
                
                result = response.json().get('response', '')
                logger.success(f"Local analysis successful ({len(result)} chars)")
                return result
                
        except Exception as e:
            logger.error(f"Local fallback failed: {e}")
            return f"LOCAL_FALLBACK_ERROR: {str(e)}"
    
    def _generate_cache_key(self, image_bytes: bytes, query: str) -> str:
        """Generate MD5 cache key for image+query pair.
        
        Args:
            image_bytes: Image data
            query: Query text
            
        Returns:
            MD5 hash string
        """
        hasher = hashlib.md5()
        hasher.update(image_bytes)
        hasher.update(query.encode())
        return hasher.hexdigest()
    
    def clear_cache(self):
        """Clear the inference cache."""
        self._cache.clear()
        logger.info("Vision inference cache cleared")
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics.
        
        Returns:
            Dictionary with cache metrics
        """
        return {
            'entries': len(self._cache),
            'hits': getattr(self, '_cache_hits', 0),
            'misses': getattr(self, '_cache_misses', 0)
        }
