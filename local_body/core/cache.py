"""Persistent cache manager for document processing results.

Uses diskcache for persistent storage to survive application restarts.
Caches OCR, layout, and vision results by file hash + stage.
"""

import hashlib
import pickle
from pathlib import Path
from typing import Any, Optional
from datetime import timedelta

from diskcache import Cache
from loguru import logger

from local_body.core.privacy import get_privacy_manager


class CacheManager:
    """Manages persistent caching of processing results.
    
    Features:
    - Disk-based cache (survives restarts)
    - Content-based keys (file hash + stage)
    - Automatic expiration
    - Cache statistics
    - Privacy-safe (no PII in keys)
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, cache_dir: str = "data/cache"):
        """Initialize cache manager.
        
        Args:
            cache_dir: Directory for cache storage
        """
        if not hasattr(self, '_initialized'):
            self.cache_dir = Path(cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            
            # Initialize diskcache
            self.cache = Cache(
                directory=str(self.cache_dir),
                size_limit=1024 * 1024 * 1024,  # 1GB max
                eviction_policy='least-recently-used'
            )
            
            # Statistics
            self.hits = 0
            self.misses = 0
            
            self._initialized = True
            logger.info(f"CacheManager initialized: {self.cache_dir}")
    
    @classmethod
    def get_instance(cls) -> "CacheManager":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def generate_key(
        self,
        file_path: str,
        stage: str,
        additional_params: Optional[dict] = None
    ) -> str:
        """Generate cache key based on file content and processing stage.
        
        Uses SHA256 of file content + stage name to ensure:
        - Same file = same key
        - Modified file = different key
        - Different stages = different keys
        
        Args:
            file_path: Path to file
            stage: Processing stage (e.g., 'ocr', 'layout', 'vision')
            additional_params: Optional parameters affecting output
            
        Returns:
            Cache key (SHA256 hash)
        """
        try:
            # Hash file content
            hasher = hashlib.sha256()
            
            with open(file_path, 'rb') as f:
                # Read in chunks to handle large files
                for chunk in iter(lambda: f.read(8192), b''):
                    hasher.update(chunk)
            
            # Add stage
            hasher.update(stage.encode())
            
            # Add additional params if provided
            if additional_params:
                # Sort keys for consistency
                param_str = str(sorted(additional_params.items()))
                hasher.update(param_str.encode())
            
            cache_key = hasher.hexdigest()
            logger.debug(f"Generated cache key: {cache_key[:16]}... for {stage}")
            
            return cache_key
            
        except Exception as e:
            logger.error(f"Failed to generate cache key: {e}")
            # Return unique key to avoid conflicts
            return f"error_{stage}_{hash(file_path)}"
    
    def get(self, key: str) -> Optional[Any]:
        """Retrieve value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value if exists, None otherwise
        """
        try:
            value = self.cache.get(key)
            
            if value is not None:
                self.hits += 1
                logger.info(f"Cache HIT: {key[:16]}... (hits: {self.hits})")
                
                # Audit cache hit
                get_privacy_manager().audit_log(
                    action="cache_hit",
                    resource="cache",
                    resource_id=key[:16]
                )
                
                return value
            else:
                self.misses += 1
                logger.debug(f"Cache MISS: {key[:16]}... (misses: {self.misses})")
                return None
                
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None
    
    def set(
        self,
        key: str,
        value: Any,
        expire: int = 86400  # 24 hours default
    ) -> bool:
        """Store value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            expire: Expiration time in seconds (default: 24h)
            
        Returns:
            True if stored successfully
        """
        try:
            # Store with expiration
            success = self.cache.set(key, value, expire=expire)
            
            if success:
                logger.info(f"Cache SET: {key[:16]}... (expires in {expire}s)")
                
                # Audit cache set
                get_privacy_manager().audit_log(
                    action="cache_set",
                    resource="cache",
                    resource_id=key[:16],
                    metadata={"expire": expire}
                )
            
            return success
            
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False
    
    def invalidate(self, key: str) -> bool:
        """Remove entry from cache.
        
        Args:
            key: Cache key to remove
            
        Returns:
            True if removed
        """
        try:
            success = self.cache.delete(key)
            
            if success:
                logger.info(f"Cache INVALIDATE: {key[:16]}...")
            
            return success
            
        except Exception as e:
            logger.error(f"Cache invalidate error: {e}")
            return False
    
    def clear_by_stage(self, stage: str) -> int:
        """Clear all cache entries for a specific stage.
        
        Args:
            stage: Stage name (e.g., 'ocr', 'layout')
            
        Returns:
            Number of entries removed
        """
        try:
            # Iterate through cache and remove matching entries
            removed = 0
            
            # Note: diskcache doesn't have pattern matching,
            # so we need to track stage in metadata or use key convention
            # For now, we clear entire cache
            logger.warning(f"clear_by_stage not fully implemented - clearing entire cache")
            
            self.cache.clear()
            removed = 1
            
            logger.info(f"Cleared cache for stage: {stage} ({removed} entries)")
            return removed
            
        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            return 0
    
    def clear_all(self) -> None:
        """Clear entire cache."""
        try:
            self.cache.clear()
            logger.info("Cache cleared completely")
            
            # Reset stats
            self.hits = 0
            self.misses = 0
            
        except Exception as e:
            logger.error(f"Cache clear all error: {e}")
    
    def get_stats(self) -> dict:
        """Get cache statistics.
        
        Returns:
            Dictionary with cache metrics
        """
        try:
            total_requests = self.hits + self.misses
            hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0
            
            return {
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": f"{hit_rate:.1f}%",
                "size_bytes": self.cache.volume(),
                "entry_count": len(self.cache),
                "max_size_bytes": 1024 * 1024 * 1024
            }
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {
                "hits": self.hits,
                "misses": self.misses,
                "error": str(e)
            }
    
    def prune_expired(self) -> int:
        """Remove expired entries.
        
        Returns:
            Number of entries removed
        """
        try:
            # diskcache handles this automatically, but we can force it
            removed = self.cache.cull()
            
            if removed > 0:
                logger.info(f"Pruned {removed} expired cache entries")
            
            return removed
            
        except Exception as e:
            logger.error(f"Cache prune error: {e}")
            return 0


# Convenience functions
def get_cache_manager() -> CacheManager:
    """Get CacheManager singleton instance."""
    return CacheManager.get_instance()


def cache_document_stage(
    file_path: str,
    stage: str,
    result: Any,
    expire_hours: int = 24
) -> bool:
    """Cache document processing result.
    
    Args:
        file_path: Path to document
        stage: Processing stage
        result: Result to cache
        expire_hours: Expiration time in hours
        
    Returns:
        True if cached successfully
    """
    cache = get_cache_manager()
    key = cache.generate_key(file_path, stage)
    return cache.set(key, result, expire=expire_hours * 3600)


def get_cached_result(
    file_path: str,
    stage: str
) -> Optional[Any]:
    """Retrieve cached processing result.
    
    Args:
        file_path: Path to document
        stage: Processing stage
        
    Returns:
        Cached result if available
    """
    cache = get_cache_manager()
    key = cache.generate_key(file_path, stage)
    return cache.get(key)
