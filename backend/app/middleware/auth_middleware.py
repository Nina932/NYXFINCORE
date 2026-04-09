"""
FinAI — Global Authentication Middleware
=========================================
When REQUIRE_AUTH=True, enforces Bearer token validation on all endpoints
except a configurable whitelist (health, auth, docs).

This is a defense-in-depth layer. Individual endpoints can still use
`Depends(get_current_user)` for route-level auth + user context injection.
"""

import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import settings
from app.auth import decode_token

logger = logging.getLogger(__name__)

# Paths that never require authentication
AUTH_WHITELIST_PREFIXES = [
    "/health",
    "/api/auth/login",
    "/api/auth/register",
    "/api/auth/sso/",
    "/api/docs",
    "/api/redoc",
    "/api/openapi.json",
    "/openapi.json",
    "/docs",
    "/redoc",
    "/favicon.ico",
    "/ws/",
    "/static/",
    "/app/",
    "/legacy",
    "/metrics",
]


class AuthMiddleware(BaseHTTPMiddleware):
    """Global authentication enforcement middleware.

    When settings.REQUIRE_AUTH is True:
    - Validates Bearer token on all non-whitelisted paths
    - Returns 401 for missing/invalid tokens
    - Passes through OPTIONS requests for CORS preflight

    When settings.REQUIRE_AUTH is False:
    - Passes through all requests (backward compatible)
    """

    async def dispatch(self, request: Request, call_next):
        # Skip auth enforcement if disabled
        if not settings.REQUIRE_AUTH:
            return await call_next(request)

        # Always allow CORS preflight
        if request.method == "OPTIONS":
            return await call_next(request)

        # Check whitelist
        path = request.url.path
        for prefix in AUTH_WHITELIST_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        # Validate Bearer token
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required — provide a Bearer token"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = auth_header[7:]  # Strip "Bearer " prefix
        payload = decode_token(token)
        if payload is None:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or expired token"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Token is valid — attach user ID to request state for downstream use
        request.state.user_id = payload.get("uid")
        request.state.token_jti = payload.get("jti")

        return await call_next(request)
