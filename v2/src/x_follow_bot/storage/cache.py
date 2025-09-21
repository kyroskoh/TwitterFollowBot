"""
Redis cache management for X Follow Bot.
"""

import json
import pickle
from typing import Any, Optional, Union, Dict, List
from datetime import datetime, timedelta
import redis
import structlog

from ..core.config import Settings

logger = structlog.get_logger(__name__)


class CacheManager:
    """Redis cache manager for X Follow Bot."""
    
    def __init__(self, settings: Settings):
        """Initialize cache manager."""
        self.settings = settings
        self.redis_client: Optional[redis.Redis] = None
        self.enabled = settings.redis.enabled
        
        if self.enabled:
            self._initialize_redis()
    
    def _initialize_redis(self):
        """Initialize Redis connection."""
        try:
            self.redis_client = redis.from_url(
                self.settings.redis.url,
                decode_responses=False,  # We'll handle encoding ourselves
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True
            )
            
            # Test connection
            self.redis_client.ping()
            logger.info("Redis cache initialized", url=self.settings.redis.url)
            
        except Exception as e:
            logger.warning("Failed to initialize Redis cache", error=str(e))
            self.enabled = False
            self.redis_client = None
    
    def _serialize(self, value: Any) -> bytes:
        """Serialize value for storage."""
        if isinstance(value, (str, int, float, bool)):
            return json.dumps(value).encode('utf-8')
        else:
            return pickle.dumps(value)
    
    def _deserialize(self, value: bytes) -> Any:
        """Deserialize value from storage."""
        try:
            # Try JSON first (for simple types)
            return json.loads(value.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            # Fall back to pickle
            return pickle.loads(value)
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if not self.enabled or not self.redis_client:
            return None
        
        try:
            value = self.redis_client.get(key)
            if value is None:
                return None
            
            return self._deserialize(value)
            
        except Exception as e:
            logger.warning("Cache get failed", key=key, error=str(e))
            return None
    
    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """Set value in cache."""
        if not self.enabled or not self.redis_client:
            return False
        
        try:
            ttl = ttl or self.settings.redis.ttl
            serialized_value = self._serialize(value)
            
            result = self.redis_client.setex(key, ttl, serialized_value)
            return bool(result)
            
        except Exception as e:
            logger.warning("Cache set failed", key=key, error=str(e))
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if not self.enabled or not self.redis_client:
            return False
        
        try:
            result = self.redis_client.delete(key)
            return bool(result)
            
        except Exception as e:
            logger.warning("Cache delete failed", key=key, error=str(e))
            return False
    
    def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        if not self.enabled or not self.redis_client:
            return False
        
        try:
            return bool(self.redis_client.exists(key))
            
        except Exception as e:
            logger.warning("Cache exists check failed", key=key, error=str(e))
            return False
    
    def increment(self, key: str, amount: int = 1, ttl: Optional[int] = None) -> Optional[int]:
        """Increment counter in cache."""
        if not self.enabled or not self.redis_client:
            return None
        
        try:
            pipeline = self.redis_client.pipeline()
            pipeline.incr(key, amount)
            
            if ttl:
                pipeline.expire(key, ttl)
            
            results = pipeline.execute()
            return int(results[0])
            
        except Exception as e:
            logger.warning("Cache increment failed", key=key, error=str(e))
            return None
    
    def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple values from cache."""
        if not self.enabled or not self.redis_client or not keys:
            return {}
        
        try:
            values = self.redis_client.mget(keys)
            result = {}
            
            for key, value in zip(keys, values):
                if value is not None:
                    result[key] = self._deserialize(value)
            
            return result
            
        except Exception as e:
            logger.warning("Cache get_many failed", keys=keys, error=str(e))
            return {}
    
    def set_many(
        self,
        mapping: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """Set multiple values in cache."""
        if not self.enabled or not self.redis_client or not mapping:
            return False
        
        try:
            ttl = ttl or self.settings.redis.ttl
            pipeline = self.redis_client.pipeline()
            
            for key, value in mapping.items():
                serialized_value = self._serialize(value)
                pipeline.setex(key, ttl, serialized_value)
            
            pipeline.execute()
            return True
            
        except Exception as e:
            logger.warning("Cache set_many failed", mapping_keys=list(mapping.keys()), error=str(e))
            return False
    
    def flush(self) -> bool:
        """Flush all cache data."""
        if not self.enabled or not self.redis_client:
            return False
        
        try:
            self.redis_client.flushdb()
            logger.info("Cache flushed")
            return True
            
        except Exception as e:
            logger.warning("Cache flush failed", error=str(e))
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if not self.enabled or not self.redis_client:
            return {"enabled": False}
        
        try:
            info = self.redis_client.info()
            return {
                "enabled": True,
                "connected_clients": info.get("connected_clients", 0),
                "used_memory": info.get("used_memory", 0),
                "used_memory_human": info.get("used_memory_human", "0B"),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "keys_count": self.redis_client.dbsize(),
            }
            
        except Exception as e:
            logger.warning("Failed to get cache stats", error=str(e))
            return {"enabled": True, "error": str(e)}
    
    def health_check(self) -> bool:
        """Check cache connectivity."""
        if not self.enabled or not self.redis_client:
            return False
        
        try:
            self.redis_client.ping()
            return True
            
        except Exception as e:
            logger.warning("Cache health check failed", error=str(e))
            return False


class CacheKeys:
    """Cache key constants and generators."""
    
    # User cache keys
    USER_BY_ID = "user:id:{user_id}"
    USER_BY_USERNAME = "user:username:{username}"
    USER_FOLLOWERS = "user:followers:{user_id}"
    USER_FOLLOWING = "user:following:{user_id}"
    
    # Tweet cache keys
    TWEET_BY_ID = "tweet:id:{tweet_id}"
    SEARCH_RESULTS = "search:{query_hash}"
    
    # Rate limiting
    RATE_LIMIT_USER = "rate_limit:user:{user_id}:{action}"
    RATE_LIMIT_GLOBAL = "rate_limit:global:{action}"
    
    # Bot session
    SESSION_DATA = "session:{session_id}"
    ACTIVE_SESSIONS = "sessions:active"
    
    # Statistics
    DAILY_STATS = "stats:daily:{date}"
    HOURLY_STATS = "stats:hourly:{date_hour}"
    
    @classmethod
    def user_by_id(cls, user_id: int) -> str:
        return cls.USER_BY_ID.format(user_id=user_id)
    
    @classmethod
    def user_by_username(cls, username: str) -> str:
        return cls.USER_BY_USERNAME.format(username=username.lower())
    
    @classmethod
    def user_followers(cls, user_id: int) -> str:
        return cls.USER_FOLLOWERS.format(user_id=user_id)
    
    @classmethod
    def user_following(cls, user_id: int) -> str:
        return cls.USER_FOLLOWING.format(user_id=user_id)
    
    @classmethod
    def tweet_by_id(cls, tweet_id: int) -> str:
        return cls.TWEET_BY_ID.format(tweet_id=tweet_id)
    
    @classmethod
    def search_results(cls, query: str) -> str:
        import hashlib
        query_hash = hashlib.md5(query.encode()).hexdigest()
        return cls.SEARCH_RESULTS.format(query_hash=query_hash)
    
    @classmethod
    def rate_limit_user(cls, user_id: int, action: str) -> str:
        return cls.RATE_LIMIT_USER.format(user_id=user_id, action=action)
    
    @classmethod
    def rate_limit_global(cls, action: str) -> str:
        return cls.RATE_LIMIT_GLOBAL.format(action=action)
    
    @classmethod
    def session_data(cls, session_id: str) -> str:
        return cls.SESSION_DATA.format(session_id=session_id)
    
    @classmethod
    def daily_stats(cls, date: datetime) -> str:
        return cls.DAILY_STATS.format(date=date.strftime("%Y-%m-%d"))
    
    @classmethod
    def hourly_stats(cls, date: datetime) -> str:
        return cls.HOURLY_STATS.format(date_hour=date.strftime("%Y-%m-%d:%H"))


# Global cache manager instance
_cache_manager: Optional[CacheManager] = None


def get_cache_manager(settings: Optional[Settings] = None) -> CacheManager:
    """Get global cache manager instance."""
    global _cache_manager
    if _cache_manager is None:
        if settings is None:
            from ..core.config import get_settings
            settings = get_settings()
        _cache_manager = CacheManager(settings)
    return _cache_manager


def cached(
    key_template: str,
    ttl: Optional[int] = None,
    key_args: Optional[List[str]] = None
):
    """Decorator for caching function results."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            cache = get_cache_manager()
            if not cache.enabled:
                return func(*args, **kwargs)
            
            # Generate cache key
            if key_args:
                key_values = []
                for arg_name in key_args:
                    if arg_name in kwargs:
                        key_values.append(str(kwargs[arg_name]))
                    else:
                        # Try to get from positional args
                        try:
                            arg_index = func.__code__.co_varnames.index(arg_name)
                            if arg_index < len(args):
                                key_values.append(str(args[arg_index]))
                            else:
                                key_values.append("unknown")
                        except (ValueError, IndexError):
                            key_values.append("unknown")
                
                cache_key = key_template.format(*key_values)
            else:
                cache_key = key_template
            
            # Try to get from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            
            return result
        
        return wrapper
    return decorator