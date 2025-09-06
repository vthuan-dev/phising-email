# llm/cache.py
import os
import json
import time
import hashlib
from typing import Optional, Dict, Any
from pathlib import Path
import logging

class LLMCache:
    """Simple file-based cache for LLM responses"""
    
    def __init__(self, cache_dir: str = "/tmp/llm_cache", ttl: int = 3600):
        self.cache_dir = Path(cache_dir)
        self.ttl = ttl  # Time to live in seconds
        self.logger = logging.getLogger(__name__)
        
        # Create cache directory
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Clean old entries on init
        self._cleanup_expired()
    
    def _get_cache_file(self, key: str) -> Path:
        """Get cache file path for a key"""
        # Use first 2 chars of hash for directory structure
        subdir = key[:2]
        cache_subdir = self.cache_dir / subdir
        cache_subdir.mkdir(exist_ok=True)
        return cache_subdir / f"{key}.json"
    
    def _is_expired(self, cache_file: Path) -> bool:
        """Check if cache file is expired"""
        try:
            if not cache_file.exists():
                return True
            
            mtime = cache_file.stat().st_mtime
            age = time.time() - mtime
            return age > self.ttl
            
        except OSError:
            return True
    
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached result for a key"""
        try:
            cache_file = self._get_cache_file(key)
            
            if self._is_expired(cache_file):
                return None
            
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.logger.debug(f"Cache hit for key: {key[:8]}...")
            return data
            
        except (OSError, json.JSONDecodeError) as e:
            self.logger.debug(f"Cache miss for key: {key[:8]}... ({e})")
            return None
    
    def set(self, key: str, value: Dict[str, Any]):
        """Set cached result for a key"""
        try:
            cache_file = self._get_cache_file(key)
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(value, f, ensure_ascii=False, indent=2)
            
            self.logger.debug(f"Cached result for key: {key[:8]}...")
            
        except OSError as e:
            self.logger.error(f"Failed to cache result: {e}")
    
    def delete(self, key: str):
        """Delete cached result for a key"""
        try:
            cache_file = self._get_cache_file(key)
            if cache_file.exists():
                cache_file.unlink()
                self.logger.debug(f"Deleted cache for key: {key[:8]}...")
        except OSError as e:
            self.logger.error(f"Failed to delete cache: {e}")
    
    def clear(self):
        """Clear all cached results"""
        try:
            import shutil
            shutil.rmtree(self.cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self.logger.info("Cache cleared")
        except OSError as e:
            self.logger.error(f"Failed to clear cache: {e}")
    
    def _cleanup_expired(self):
        """Clean up expired cache entries"""
        try:
            cleaned = 0
            for cache_file in self.cache_dir.rglob("*.json"):
                if self._is_expired(cache_file):
                    cache_file.unlink()
                    cleaned += 1
            
            if cleaned > 0:
                self.logger.info(f"Cleaned {cleaned} expired cache entries")
                
        except OSError as e:
            self.logger.error(f"Failed to cleanup cache: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        try:
            total_files = len(list(self.cache_dir.rglob("*.json")))
            total_size = sum(f.stat().st_size for f in self.cache_dir.rglob("*.json"))
            
            return {
                'cache_enabled': True,
                'cache_dir': str(self.cache_dir),
                'total_entries': total_files,
                'total_size_bytes': total_size,
                'ttl_seconds': self.ttl
            }
        except OSError:
            return {
                'cache_enabled': True,
                'cache_dir': str(self.cache_dir),
                'total_entries': 0,
                'total_size_bytes': 0,
                'ttl_seconds': self.ttl
            }

class RedisCache(LLMCache):
    """Redis-based cache for production use"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379", ttl: int = 3600):
        try:
            import redis
            self.redis_client = redis.from_url(redis_url)
            self.ttl = ttl
            self.logger = logging.getLogger(__name__)
            
            # Test connection
            self.redis_client.ping()
            self.logger.info("Redis cache initialized")
            
        except (ImportError, redis.ConnectionError) as e:
            self.logger.error(f"Failed to initialize Redis cache: {e}")
            # Fallback to file cache
            super().__init__(ttl=ttl)
    
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached result from Redis"""
        try:
            data = self.redis_client.get(f"llm_cache:{key}")
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            self.logger.error(f"Redis get error: {e}")
            return None
    
    def set(self, key: str, value: Dict[str, Any]):
        """Set cached result in Redis"""
        try:
            data = json.dumps(value, ensure_ascii=False)
            self.redis_client.setex(f"llm_cache:{key}", self.ttl, data)
        except Exception as e:
            self.logger.error(f"Redis set error: {e}")
    
    def delete(self, key: str):
        """Delete cached result from Redis"""
        try:
            self.redis_client.delete(f"llm_cache:{key}")
        except Exception as e:
            self.logger.error(f"Redis delete error: {e}")
    
    def clear(self):
        """Clear all cached results from Redis"""
        try:
            keys = self.redis_client.keys("llm_cache:*")
            if keys:
                self.redis_client.delete(*keys)
            self.logger.info("Redis cache cleared")
        except Exception as e:
            self.logger.error(f"Redis clear error: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get Redis cache statistics"""
        try:
            keys = self.redis_client.keys("llm_cache:*")
            return {
                'cache_enabled': True,
                'cache_type': 'redis',
                'total_entries': len(keys),
                'ttl_seconds': self.ttl
            }
        except Exception as e:
            self.logger.error(f"Redis stats error: {e}")
            return {
                'cache_enabled': False,
                'cache_type': 'redis',
                'error': str(e)
            }
