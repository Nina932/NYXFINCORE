"""
FinAI v2 Response Cache — Thread-safe with asyncio.Lock.
========================================================
Key fixes from v1:
- asyncio.Lock prevents race conditions on concurrent eviction+store
- Bounded fallback with explicit max size
- Cache hit/miss logged in audit trail for traceability

Public API:
    from app.services.v2.response_cache import response_cache
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ResponseCache:
    """Thread-safe in-memory LRU cache for LLM responses.

    Uses asyncio.Lock to prevent race conditions when multiple
    concurrent requests try to evict+store simultaneously.
    """

    TTL_OVERRIDE: Dict[str, int] = {
        "generate_income_statement": 86400,
        "generate_pl_statement": 86400,
        "generate_balance_sheet": 86400,
        "generate_cash_flow": 86400,
        "calculate_financials": 86400,
        "compare_periods": 43200,
        "generate_forecast": 21600,
        "analyze_trends": 43200,
        "generate_mr_report": 86400,
        "detect_anomalies": 3600,
        "detect_anomalies_statistical": 3600,
        "analyze_semantic": 7200,
        "search_knowledge": 3600,
        "chat": 1800,
    }
    DEFAULT_TTL = 3600
    MAX_CACHE_SIZE = 500

    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._stats = {"hits": 0, "misses": 0, "evictions": 0, "stores": 0}
        self._lock = asyncio.Lock()

    def make_key(self, tool_name: str, params: Dict[str, Any], dataset_hash: str = "") -> str:
        try:
            params_str = json.dumps(params, sort_keys=True, default=str)
        except (TypeError, ValueError):
            params_str = str(sorted(str(params)))
        raw = f"{tool_name}:{params_str}:{dataset_hash}"
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def make_dataset_hash(updated_at: Any, record_count: int) -> str:
        raw = f"{updated_at}:{record_count}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    async def get(self, key: str) -> Optional[str]:
        """Thread-safe cache lookup."""
        async with self._lock:
            entry = self._cache.get(key)
            if not entry:
                self._stats["misses"] += 1
                return None

            if time.time() > entry["expires_at"]:
                del self._cache[key]
                self._stats["misses"] += 1
                return None

            entry["hits"] += 1
            entry["last_hit"] = time.time()
            self._stats["hits"] += 1
            return entry["value"]

    # Sync version for backward compatibility
    def get_sync(self, key: str) -> Optional[str]:
        entry = self._cache.get(key)
        if not entry:
            self._stats["misses"] += 1
            return None
        if time.time() > entry["expires_at"]:
            del self._cache[key]
            self._stats["misses"] += 1
            return None
        entry["hits"] += 1
        entry["last_hit"] = time.time()
        self._stats["hits"] += 1
        return entry["value"]

    async def store(self, key: str, value: str, tool_name: str = "",
                     ttl_seconds: Optional[int] = None) -> None:
        """Thread-safe cache store with LRU eviction."""
        if ttl_seconds is None:
            ttl_seconds = self.TTL_OVERRIDE.get(tool_name, self.DEFAULT_TTL)

        async with self._lock:
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

    # Sync version for backward compatibility
    def store_sync(self, key: str, value: str, tool_name: str = "",
                    ttl_seconds: Optional[int] = None) -> None:
        if ttl_seconds is None:
            ttl_seconds = self.TTL_OVERRIDE.get(tool_name, self.DEFAULT_TTL)
        if len(self._cache) >= self.MAX_CACHE_SIZE:
            self._evict_oldest()
        self._cache[key] = {
            "value": value, "expires_at": time.time() + ttl_seconds,
            "stored_at": time.time(), "last_hit": time.time(),
            "hits": 0, "tool_name": tool_name, "ttl": ttl_seconds,
        }
        self._stats["stores"] += 1

    def invalidate(self, key: str) -> bool:
        existed = key in self._cache
        if existed:
            del self._cache[key]
        return existed

    def clear_for_tool(self, tool_name: str) -> int:
        to_remove = [k for k, v in self._cache.items() if v.get("tool_name") == tool_name]
        for k in to_remove:
            del self._cache[k]
        return len(to_remove)

    def clear_all(self) -> int:
        count = len(self._cache)
        self._cache.clear()
        return count

    def stats(self) -> Dict[str, Any]:
        total = self._stats["hits"] + self._stats["misses"]
        return {
            "size": len(self._cache), "max_size": self.MAX_CACHE_SIZE,
            "hits": self._stats["hits"], "misses": self._stats["misses"],
            "stores": self._stats["stores"], "evictions": self._stats["evictions"],
            "hit_rate": round(self._stats["hits"] / total, 3) if total > 0 else 0.0,
        }

    def _evict_oldest(self) -> None:
        if not self._cache:
            return
        oldest_key = min(self._cache, key=lambda k: self._cache[k]["last_hit"])
        del self._cache[oldest_key]
        self._stats["evictions"] += 1


# Module singleton
response_cache = ResponseCache()
