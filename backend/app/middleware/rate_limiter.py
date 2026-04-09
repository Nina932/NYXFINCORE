"""
FinAI — Lightweight In-Memory Rate Limiter Middleware
=====================================================
Provides per-IP request throttling without external dependencies.
Uses a sliding window counter with automatic cleanup.

Limits:
  - General API: 120 requests/minute per IP
  - Chat/Agent: 30 requests/minute per IP (LLM calls are expensive)
  - Auth: 10 requests/minute per IP (brute-force protection)
  - Upload: 10 requests/minute per IP
"""

import time
import logging
from collections import defaultdict
from typing import Dict, List, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# Rate limit configurations: (max_requests, window_seconds)
RATE_LIMITS: Dict[str, Tuple[int, int]] = {
    "/api/agent/chat": (30, 60),          # 30 req/min — LLM calls
    "/api/agent/agents/": (30, 60),       # 30 req/min — agent endpoints
    "/ws/chat": (30, 60),                 # 30 req/min — WebSocket chat
    "/api/auth/login": (10, 60),          # 10 req/min — brute-force protection
    "/api/auth/register": (5, 60),        # 5 req/min — registration abuse
    "/api/datasets/upload": (10, 60),     # 10 req/min — file uploads
    "/api/datasets": (60, 60),            # 60 req/min — dataset operations
    "/api/analytics": (60, 60),           # 60 req/min — analytics
}
DEFAULT_LIMIT = (120, 60)  # 120 req/min for all other endpoints

# Cleanup interval: sweep expired entries every N requests
_CLEANUP_INTERVAL = 500
_MAX_TRACKED_IPS = 10000  # Cap tracked IPs to prevent memory bloat


class RateLimitStore:
    """Thread-safe in-memory sliding window rate limiter."""

    def __init__(self):
        # {ip: {route_prefix: [timestamp, timestamp, ...]}}
        self._requests: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
        self._total_checks: int = 0

    def is_allowed(self, ip: str, route_prefix: str, max_requests: int, window_seconds: int) -> bool:
        """Check if request is allowed under the rate limit.

        Returns True if allowed, False if rate-limited.
        """
        now = time.time()
        cutoff = now - window_seconds

        # Get request timestamps for this IP + route
        timestamps = self._requests[ip][route_prefix]

        # Remove expired timestamps (outside window)
        self._requests[ip][route_prefix] = [t for t in timestamps if t > cutoff]
        timestamps = self._requests[ip][route_prefix]

        # Check limit
        if len(timestamps) >= max_requests:
            return False

        # Record this request
        timestamps.append(now)

        # Periodic cleanup
        self._total_checks += 1
        if self._total_checks % _CLEANUP_INTERVAL == 0:
            self._cleanup()

        return True

    def _cleanup(self):
        """Remove stale entries to prevent memory bloat."""
        now = time.time()
        stale_ips = []
        for ip, routes in self._requests.items():
            # Remove empty route entries
            empty_routes = [r for r, ts in routes.items() if not ts or all(t < now - 120 for t in ts)]
            for r in empty_routes:
                del routes[r]
            if not routes:
                stale_ips.append(ip)
        for ip in stale_ips:
            del self._requests[ip]

        # Hard cap on tracked IPs
        if len(self._requests) > _MAX_TRACKED_IPS:
            # Remove oldest half
            sorted_ips = sorted(
                self._requests.keys(),
                key=lambda ip: max((max(ts) for ts in self._requests[ip].values() if ts), default=0)
            )
            for ip in sorted_ips[:len(sorted_ips) // 2]:
                del self._requests[ip]
            logger.warning("Rate limiter: pruned %d stale IPs", len(sorted_ips) // 2)


# Module-level singleton
_store = RateLimitStore()


def _get_client_ip(request: Request) -> str:
    """Extract client IP, respecting X-Forwarded-For behind reverse proxy."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _match_rate_limit(path: str) -> Tuple[str, int, int]:
    """Find the best matching rate limit for a request path.

    Returns (route_prefix, max_requests, window_seconds).
    """
    for prefix, (max_req, window) in RATE_LIMITS.items():
        if path.startswith(prefix):
            return prefix, max_req, window
    return "default", DEFAULT_LIMIT[0], DEFAULT_LIMIT[1]


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware using sliding window counters.

    Skips rate limiting for:
    - Health checks (/health)
    - Static files (/static/, /app/)
    - OPTIONS preflight requests
    """

    SKIP_PREFIXES = ["/health", "/static/", "/app/", "/assets/", "/favicon.ico"]

    async def dispatch(self, request: Request, call_next):
        # Skip for non-rate-limited paths
        path = request.url.path
        if request.method == "OPTIONS" or any(path.startswith(p) for p in self.SKIP_PREFIXES):
            return await call_next(request)

        # Check rate limit
        client_ip = _get_client_ip(request)
        route_prefix, max_requests, window = _match_rate_limit(path)

        if not _store.is_allowed(client_ip, route_prefix, max_requests, window):
            logger.warning(
                "Rate limit exceeded: ip=%s path=%s limit=%d/%ds",
                client_ip, path[:80], max_requests, window,
            )
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Too many requests. Please slow down.",
                    "retry_after": window,
                },
                headers={
                    "Retry-After": str(window),
                    "X-RateLimit-Limit": str(max_requests),
                },
            )

        response = await call_next(request)

        # Add rate limit headers to response
        response.headers["X-RateLimit-Limit"] = str(max_requests)

        return response
