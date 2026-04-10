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
from sqlalchemy import select

from app.config import settings
from app.auth import decode_token
from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Middleware-level revocation table verification flag (mirrors auth.py logic)
# ---------------------------------------------------------------------------
# Separate from the flag in auth.py because the middleware runs before
# route-level dependencies.  Same semantics: one-time grace period before
# the table is confirmed reachable, then fail-closed on any error.
_middleware_revocation_verified: bool = False

# Paths that never require authentication
AUTH_WHITELIST_PREFIXES = [
    "/health",
    "/api/auth/login",
    "/api/auth/register",
    "/api/auth/sso/",
    "/api/config/public",
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
            from app.errors import build_error_dict
            return JSONResponse(
                status_code=401,
                content=build_error_dict(
                    detail="Authentication required — provide a Bearer token",
                    error_code="AUTH_REQUIRED",
                    path=path,
                ),
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = auth_header[7:]  # Strip "Bearer " prefix
        payload = decode_token(token)
        if payload is None:
            from app.errors import build_error_dict
            return JSONResponse(
                status_code=401,
                content=build_error_dict(
                    detail="Invalid or expired token",
                    error_code="AUTH_INVALID_TOKEN",
                    path=path,
                ),
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Token is valid — attach user ID to request state for downstream use
        request.state.user_id = payload.get("uid")
        request.state.token_jti = payload.get("jti")

        # Phase G-4: Fail-closed revocation check at the middleware layer.
        # This is a defense-in-depth complement to the route-level check in
        # auth._get_user_from_token().  Both layers enforce fail-closed
        # semantics after the revocation table has been verified reachable.
        jti = payload.get("jti")
        if jti:
            global _middleware_revocation_verified
            try:
                from app.models.all_models import RevokedToken
                async with AsyncSessionLocal() as session:
                    result = await session.execute(
                        select(RevokedToken).where(RevokedToken.jti == jti)
                    )
                    if result.scalar_one_or_none():
                        logger.info("Middleware: rejected revoked token jti=%s", jti)
                        from app.errors import build_error_dict
                        return JSONResponse(
                            status_code=401,
                            content=build_error_dict(
                                detail="Token has been revoked",
                                error_code="AUTH_TOKEN_REVOKED",
                                path=path,
                            ),
                            headers={"WWW-Authenticate": "Bearer"},
                        )
                    _middleware_revocation_verified = True
            except Exception as exc:
                if not _middleware_revocation_verified:
                    # Startup grace period — table may not exist yet
                    logger.warning(
                        "Middleware revocation check failed (table not yet "
                        "verified, allowing through as startup grace): %s", exc,
                    )
                else:
                    # Table was reachable before — fail closed
                    logger.error(
                        "Middleware revocation check failed (fail-closed, "
                        "rejecting token jti=%s): %s", jti, exc,
                    )
                    from app.errors import build_error_dict
                    return JSONResponse(
                        status_code=401,
                        content=build_error_dict(
                            detail="Token validation failed — please retry",
                            error_code="AUTH_VALIDATION_FAILED",
                            path=path,
                        ),
                        headers={"WWW-Authenticate": "Bearer"},
                    )

        return await call_next(request)
