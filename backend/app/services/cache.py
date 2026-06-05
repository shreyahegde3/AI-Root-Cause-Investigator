import os
import json
import redis
from typing import Optional, Any
from app.utils.logger import logger

class CacheService:
    def __init__(self):
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        try:
            self.client = redis.Redis.from_url(
                redis_url, 
                decode_responses=True,
                socket_timeout=2.0,       # 2-second timeout for quick fallback
                socket_connect_timeout=2.0
            )
            # Test connection
            self.client.ping()
            self._is_active = True
            logger.info("cache_connected", url=redis_url)
        except Exception as e:
            self._is_active = False
            self.client = None
            logger.warn("cache_connection_failed", url=redis_url, error=str(e))

    def get(self, key: str) -> Optional[str]:
        """Fetch string value from cache"""
        if not self._is_active or not self.client:
            return None
        try:
            val = self.client.get(key)
            if val:
                logger.info("cache_hit", key=key)
            else:
                logger.info("cache_miss", key=key)
            return val
        except Exception as e:
            logger.warn("cache_get_error", key=key, error=str(e))
            return None

    def set(self, key: str, value: str, ttl_seconds: int = 600) -> bool:
        """Set string value in cache with a TTL"""
        if not self._is_active or not self.client:
            return False
        try:
            self.client.set(key, value, ex=ttl_seconds)
            logger.info("cache_set", key=key, ttl=ttl_seconds)
            return True
        except Exception as e:
            logger.warn("cache_set_error", key=key, error=str(e))
            return False

    def get_json(self, key: str) -> Optional[Any]:
        """Fetch JSON/dict value from cache"""
        data = self.get(key)
        if data:
            try:
                return json.loads(data)
            except Exception as e:
                logger.error("cache_json_decode_error", key=key, error=str(e))
        return None

    def set_json(self, key: str, value: Any, ttl_seconds: int = 600) -> bool:
        """Set JSON/dict value in cache with a TTL"""
        try:
            serialized = json.dumps(value)
            return self.set(key, serialized, ttl_seconds)
        except Exception as e:
            logger.error("cache_json_encode_error", key=key, error=str(e))
            return False

# Export singleton instance
cache_service = CacheService()
