"""
cache.py — Dual-backend caching service for the FinAI financial platform.

Provides a unified caching interface with two backends:
  - RedisCache:     Uses Redis via redis.asyncio for production deployments.
  - InMemoryCache:  Simple dict-based fallback with TTL expiry for development.

The CacheService class is the main public interface.  It picks the best
available backend at initialization time (Redis if configured, otherwise
in-memory) and exposes JSON-aware get/set/invalidate helpers keyed by
namespace so callers never deal with raw cache keys.

Usage:
    from app.services.cache import cache_service

    await cache_service.initialize()
    await cache_service.set_json("exchange_rates", "GEL_USD", rate_data, ttl=3600)
    data = await cache_service.get_json("exchange_rates", "GEL_USD")
    await cache_service.invalidate("exchange_rates")       # wipe whole namespace
    await cache_service.close()
"""

import json
import time
import logging
from typing import Any, Dict, Optional, Tuple

from app.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Backend: In-Memory Cache
# ---------------------------------------------------------------------------

class InMemoryCache:
    """Dict-based async cache with per-key TTL expiry.

    Each entry is stored as ``{key: (value_str, expiry_timestamp)}``.
    An *expiry_timestamp* of ``0`` means the entry never expires.

    A lightweight garbage-collection sweep runs automatically every
    ``_SWEEP_INTERVAL`` set operations to prune stale keys.
    """

    _SWEEP_INTERVAL = 100  # run cleanup every N writes
    _MAX_SIZE = 10000  # Maximum number of cached entries

    def __init__(self) -> None:
        self._store: Dict[str, Tuple[str, float]] = {}
        self._write_count: int = 0

    # -- public interface ----------------------------------------------------

    async def get(self, key: str) -> Optional[str]:
        """Return the cached value or *None* if missing / expired."""
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expiry = entry
        if expiry != 0 and time.time() > expiry:
            del self._store[key]
            return None
        return value

    async def set(self, key: str, value: str, ttl: int = 0) -> None:
        """Store *value* under *key*.  *ttl* is seconds; 0 = no expiry."""
        expiry = (time.time() + ttl) if ttl > 0 else 0
        self._store[key] = (value, expiry)
        self._write_count += 1
        if self._write_count % self._SWEEP_INTERVAL == 0:
            self._sweep_expired()
        # Enforce size limit — evict oldest entries
        if len(self._store) > self._MAX_SIZE:
            self._evict_oldest()

    async def delete(self, key: str) -> None:
        """Remove a single key (no-op if absent)."""
        self._store.pop(key, None)

    async def clear_pattern(self, pattern: str) -> int:
        """Delete all keys that match a glob-style prefix pattern.

        Only trailing ``*`` is supported (e.g. ``finai:exchange_rates:*``).
        Returns the number of deleted keys.
        """
        prefix = pattern.rstrip("*")
        victims = [k for k in self._store if k.startswith(prefix)]
        for k in victims:
            del self._store[k]
        return len(victims)

    async def close(self) -> None:
        """No-op — exists for interface compatibility with RedisCache."""

    # -- internal ------------------------------------------------------------

    def _sweep_expired(self) -> None:
        """Remove all entries whose TTL has elapsed."""
        now = time.time()
        expired = [k for k, (_, exp) in self._store.items() if exp != 0 and now > exp]
        for k in expired:
            del self._store[k]
        if expired:
            logger.debug("InMemoryCache sweep: removed %d expired keys", len(expired))

    def _evict_oldest(self) -> None:
        """Evict oldest entries when cache exceeds MAX_SIZE."""
        # First sweep expired
        self._sweep_expired()
        if len(self._store) <= self._MAX_SIZE:
            return
        # Sort by expiry/insertion time and remove oldest quarter
        items = sorted(self._store.items(), key=lambda kv: kv[1][1] if kv[1][1] != 0 else float('inf'))
        evict_count = len(self._store) - self._MAX_SIZE + (self._MAX_SIZE // 4)
        for k, _ in items[:evict_count]:
            del self._store[k]
        logger.debug("InMemoryCache eviction: removed %d entries, %d remaining", evict_count, len(self._store))


# ---------------------------------------------------------------------------
# Backend: Redis Cache
# ---------------------------------------------------------------------------

class RedisCache:
    """Async Redis cache using ``redis.asyncio``.

    The *redis* package is imported lazily so the application can start
    even when the package is not installed (it simply falls back to the
    in-memory backend).
    """

    def __init__(self, url: str) -> None:
        self._url = url
        self._redis: Any = None  # redis.asyncio.Redis instance

    async def _get_redis(self) -> Any:
        """Lazily create (or return) the Redis connection pool."""
        if self._redis is None:
            import redis.asyncio as aioredis  # lazy import
            self._redis = aioredis.from_url(
                self._url,
                decode_responses=True,
                socket_connect_timeout=5,
            )
        return self._redis

    # -- public interface ----------------------------------------------------

    async def get(self, key: str) -> Optional[str]:
        r = await self._get_redis()
        return await r.get(key)

    async def set(self, key: str, value: str, ttl: int = 0) -> None:
        r = await self._get_redis()
        if ttl > 0:
            await r.setex(key, ttl, value)
        else:
            await r.set(key, value)

    async def delete(self, key: str) -> None:
        r = await self._get_redis()
        await r.delete(key)

    async def clear_pattern(self, pattern: str) -> int:
        """Delete all keys matching *pattern* using ``SCAN``."""
        r = await self._get_redis()
        count = 0
        async for key in r.scan_iter(match=pattern, count=200):
            await r.delete(key)
            count += 1
        return count

    async def close(self) -> None:
        """Gracefully shut down the Redis connection pool."""
        if self._redis is not None:
            await self._redis.close()
            self._redis = None
            logger.info("Redis connection closed")


# ---------------------------------------------------------------------------
# Main interface: CacheService
# ---------------------------------------------------------------------------

class CacheService:
    """High-level caching facade used throughout the FinAI application.

    Call ``await cache_service.initialize()`` once at startup.  After that,
    use the ``get_json`` / ``set_json`` / ``invalidate`` helpers which
    handle JSON serialization and namespace-prefixed keys automatically.
    """

    # Recommended TTLs (seconds) per data domain
    TTL_EXCHANGE_RATES: int = 3600   # 1 hour
    TTL_FORECASTS: int = 900         # 15 minutes
    TTL_DASHBOARD: int = 300         # 5 minutes
    TTL_COA: int = 0                 # never expires (chart of accounts)

    def __init__(self) -> None:
        self._backend: Optional[Any] = None
        self._initialized: bool = False

    # -- lifecycle -----------------------------------------------------------

    async def initialize(self) -> None:
        """Select and connect to the best available cache backend."""
        redis_enabled: bool = getattr(settings, "REDIS_ENABLED", False)
        redis_url: str = getattr(settings, "REDIS_URL", "")

        if redis_enabled and redis_url:
            try:
                backend = RedisCache(redis_url)
                # Verify connectivity with a quick ping
                r = await backend._get_redis()
                await r.ping()
                self._backend = backend
                logger.info("CacheService initialized with Redis (%s)", redis_url)
            except Exception as exc:
                logger.warning(
                    "Redis unavailable (%s), falling back to in-memory cache", exc
                )
                self._backend = InMemoryCache()
        else:
            self._backend = InMemoryCache()
            logger.info("CacheService initialized with in-memory backend")

        self._initialized = True

    async def close(self) -> None:
        """Shut down the cache backend gracefully."""
        if self._backend is not None:
            await self._backend.close()
            logger.info("CacheService closed")

    # -- key helpers ---------------------------------------------------------

    @staticmethod
    def _key(namespace: str, key: str) -> str:
        """Build a fully-qualified cache key.

        Example: ``_key("exchange_rates", "GEL_USD")``
        returns  ``"finai:exchange_rates:GEL_USD"``
        """
        prefix = getattr(settings, "REDIS_PREFIX", "finai:")
        if key:
            return f"{prefix}{namespace}:{key}"
        return f"{prefix}{namespace}"

    # -- JSON-aware accessors ------------------------------------------------

    async def get_json(self, namespace: str, key: str) -> Optional[Any]:
        """Retrieve and deserialize a cached JSON value.

        Returns *None* when the key is missing, expired, or cannot be
        decoded.
        """
        self._ensure_initialized()
        raw = await self._backend.get(self._key(namespace, key))
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Corrupt cache entry at %s:%s — removing", namespace, key)
            await self._backend.delete(self._key(namespace, key))
            return None

    async def set_json(
        self, namespace: str, key: str, value: Any, ttl: int = 0
    ) -> None:
        """Serialize *value* as JSON and cache it under *namespace:key*."""
        self._ensure_initialized()
        raw = json.dumps(value, default=str)
        await self._backend.set(self._key(namespace, key), raw, ttl=ttl)

    async def invalidate(self, namespace: str, key: str = "") -> None:
        """Remove cached data.

        * If *key* is provided, delete only that single entry.
        * If *key* is empty, wipe **all** entries in the namespace.
        """
        self._ensure_initialized()
        if key:
            await self._backend.delete(self._key(namespace, key))
            logger.debug("Cache invalidated: %s:%s", namespace, key)
        else:
            pattern = f"{self._key(namespace, '')}*"
            count = await self._backend.clear_pattern(pattern)
            logger.debug(
                "Cache invalidated: %s (pattern=%s, removed=%d)",
                namespace, pattern, count,
            )

    # -- internal ------------------------------------------------------------

    def _ensure_initialized(self) -> None:
        """Guard against use before ``initialize()`` has been called."""
        if not self._initialized:
            raise RuntimeError(
                "CacheService has not been initialized. "
                "Call 'await cache_service.initialize()' first."
            )


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
cache_service = CacheService()
