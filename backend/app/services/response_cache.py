"""
SHIM: Re-exports from app.services.v2.response_cache (thread-safe with asyncio.Lock).
Original v1 code preserved in response_cache_v1.py.

NOTE: v2 response_cache has async get()/store() methods. For backward compatibility,
this shim also exposes get_sync()/store_sync() and patches get/store to use sync versions
when called from sync code.
"""
from app.services.v2.response_cache import (  # noqa: F401
    response_cache,
    ResponseCache,
)

# Backward compatibility: callers use response_cache.get() and .store() synchronously.
# Patch the singleton to use sync versions for drop-in compatibility.
_original_get = response_cache.get
_original_store = response_cache.store
response_cache.get = response_cache.get_sync
response_cache.store = response_cache.store_sync
