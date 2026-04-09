"""
FinAI Response Cache — Content-hash keyed result caching for LLM responses.
============================================================================
Reduces Claude API calls by caching responses for identical financial data states.

Cache key = SHA256(tool_name + sorted(params) + dataset_content_hash)
where dataset_content_hash = hash of dataset.updated_at + record_count

If the dataset hasn't changed, the calculation result is deterministic.

Hit rate estimates:
- P&L narrative for same period: 100% after first generation
- Variance analysis same periods: 100%
- Repeated chat queries: ~80% (same data + same question)
- Novel analysis: 0% (expected)
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ResponseCache:
    """In-memory LRU cache for LLM responses.

    Cache invalidation:
    - By TTL (configurable, default 24 hours for calculations, 1 hour for chat)
    - By dataset content hash (auto-invalidates when data changes)
    - Manual: clear_for_dataset(dataset_id)

    Thread safety: single-process asyncio — no locks needed.
    """

    # TTL in seconds per tool type
    TTL_OVERRIDE: Dict[str, int] = {
        "generate_income_statement": 86400,    # 24h — deterministic given same data
        "generate_pl_statement": 86400,
        "generate_balance_sheet": 86400,
        "generate_cash_flow": 86400,
        "calculate_financials": 86400,
        "compare_periods": 43200,              # 12h — two datasets
        "generate_forecast": 21600,            # 6h — may depend on market factors
        "analyze_trends": 43200,
        "generate_mr_report": 86400,
        "detect_anomalies": 3600,              # 1h — anomalies may be re-analyzed
        "detect_anomalies_statistical": 3600,
        "analyze_semantic": 7200,
        "search_knowledge": 3600,
        "chat": 1800,                          # 30min for conversational
    }
    DEFAULT_TTL = 3600  # 1 hour fallback
    MAX_CACHE_SIZE = 500  # Max entries before LRU eviction

    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}  # key → {value, expires_at, hits, tool_name}
        self._stats = {"hits": 0, "misses": 0, "evictions": 0, "stores": 0}

    # ── Public API ──────────────────────────────────────────────────────────

    def make_key(
        self,
        tool_name: str,
        params: Dict[str, Any],
        dataset_hash: str = "",
    ) -> str:
        """Build a deterministic cache key.

        Args:
            tool_name: Name of the tool/operation
            params: Tool parameters (will be sorted for determinism)
            dataset_hash: Hash of current dataset state (see make_dataset_hash)

        Returns:
            SHA256 hex digest (64 chars)
        """
        # Sort params for determinism (same params in different order = same key)
        try:
            params_str = json.dumps(params, sort_keys=True, default=str)
        except (TypeError, ValueError):
            params_str = str(sorted(str(params)))

        raw = f"{tool_name}:{params_str}:{dataset_hash}"
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def make_dataset_hash(updated_at: Any, record_count: int) -> str:
        """Build a hash representing the current state of a dataset.

        If the dataset hasn't changed (same updated_at + record_count),
        the cache key will be the same and the cached result is valid.

        Args:
            updated_at: Dataset.updated_at timestamp (any type, stringified)
            record_count: Dataset.record_count (number of records)

        Returns:
            Short SHA256 hex (16 chars — enough for cache discrimination)
        """
        raw = f"{updated_at}:{record_count}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def get(self, key: str) -> Optional[str]:
        """Retrieve a cached value if it exists and hasn't expired.

        Returns:
            Cached value string, or None if cache miss/expired.
        """
        entry = self._cache.get(key)
        if not entry:
            self._stats["misses"] += 1
            return None

        if time.time() > entry["expires_at"]:
            # Expired — remove and return miss
            del self._cache[key]
            self._stats["misses"] += 1
            return None

        # Hit
        entry["hits"] += 1
        entry["last_hit"] = time.time()
        self._stats["hits"] += 1
        logger.debug(
            "Cache HIT for key %s... (tool=%s, hits=%d)",
            key[:12], entry.get("tool_name", "?"), entry["hits"],
        )
        return entry["value"]

    def store(
        self,
        key: str,
        value: str,
        tool_name: str = "",
        ttl_seconds: Optional[int] = None,
    ) -> None:
        """Store a value in the cache.

        Args:
            key: Cache key from make_key()
            value: String value to cache (LLM response)
            tool_name: Tool name for TTL lookup and logging
            ttl_seconds: Override TTL; if None, uses TTL_OVERRIDE or DEFAULT_TTL
        """
        if ttl_seconds is None:
            ttl_seconds = self.TTL_OVERRIDE.get(tool_name, self.DEFAULT_TTL)

        # LRU eviction if at capacity
        if len(self._cache) >= self.MAX_CACHE_SIZE:
            self._evict_oldest()

        self._cache[key] = {
            "value": value,
            "expires_at": time.time() + ttl_seconds,
            "stored_at": time.time(),
            "last_hit": time.time(),
            "hits": 0,
            "tool_name": tool_name,
            "ttl": ttl_seconds,
        }
        self._stats["stores"] += 1
        logger.debug(
            "Cache STORE key %s... (tool=%s, ttl=%ds)",
            key[:12], tool_name, ttl_seconds,
        )

    def invalidate(self, key: str) -> bool:
        """Remove a specific cache entry. Returns True if it existed."""
        existed = key in self._cache
        if existed:
            del self._cache[key]
        return existed

    def clear_for_tool(self, tool_name: str) -> int:
        """Remove all cache entries for a specific tool. Returns count removed."""
        to_remove = [k for k, v in self._cache.items() if v.get("tool_name") == tool_name]
        for k in to_remove:
            del self._cache[k]
        return len(to_remove)

    def clear_all(self) -> int:
        """Remove all cache entries. Returns count removed."""
        count = len(self._cache)
        self._cache.clear()
        return count

    def stats(self) -> Dict[str, Any]:
        """Return cache statistics for monitoring."""
        total = self._stats["hits"] + self._stats["misses"]
        return {
            "size": len(self._cache),
            "max_size": self.MAX_CACHE_SIZE,
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "stores": self._stats["stores"],
            "evictions": self._stats["evictions"],
            "hit_rate": round(self._stats["hits"] / total, 3) if total > 0 else 0.0,
        }

    # ── Internal helpers ────────────────────────────────────────────────────

    def _evict_oldest(self) -> None:
        """Remove the least recently used cache entry."""
        if not self._cache:
            return
        oldest_key = min(self._cache, key=lambda k: self._cache[k]["last_hit"])
        del self._cache[oldest_key]
        self._stats["evictions"] += 1


# Module-level singleton
response_cache = ResponseCache()
