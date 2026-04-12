"""
Multi-tenant query isolation middleware.

Extracts tenant identity (company name) from the authenticated user's JWT
and stores it in a context variable. A SQLAlchemy ORM execute event listener
in database.py reads this context to automatically append
WHERE company = :tenant filters to every SELECT on tenant-scoped models.

Three-layer approach:
  1. TenantMiddleware — sets context from authenticated user
  2. SQLAlchemy event listener — auto-filters queries (database.py)
  3. require_tenant decorator — validates context at route level (auth.py)
"""

from contextvars import ContextVar
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

import logging

logger = logging.getLogger(__name__)

# Thread-safe tenant context (company name string, matching User.company)
_tenant_company: ContextVar[Optional[str]] = ContextVar("tenant_company", default=None)


def get_current_tenant() -> Optional[str]:
    """Return the current request's tenant company name, or None."""
    return _tenant_company.get()


def set_current_tenant(company: Optional[str]) -> None:
    """Explicitly set the tenant context (useful in tests and background tasks)."""
    _tenant_company.set(company)


# Paths that don't need tenant context
_EXEMPT_PREFIXES = frozenset((
    "/health",
    "/api/auth/login",
    "/api/auth/register",
    "/api/auth/sso/",
    "/api/config/public",
    "/docs",
    "/api/docs",
    "/api/redoc",
    "/openapi.json",
    "/api/openapi.json",
    "/redoc",
    "/favicon.ico",
    "/metrics",
    "/static/",
    "/app/",
    "/legacy",
))


class TenantMiddleware(BaseHTTPMiddleware):
    """Extract tenant (company) from authenticated user and set in context.

    Must be registered AFTER AuthMiddleware so that request.state.user_id
    is already populated when this middleware runs.

    For requests where the user is authenticated and has a company,
    the tenant context is set for the duration of the request and
    automatically reset afterward.
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip tenant injection for exempt paths
        for prefix in _EXEMPT_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        # Try to extract company from the authenticated user
        user_id = getattr(request.state, "user_id", None)
        if user_id is not None:
            # Look up the user's company from DB
            try:
                from app.database import AsyncSessionLocal
                from app.models.all_models import User
                from sqlalchemy import select

                async with AsyncSessionLocal() as session:
                    result = await session.execute(
                        select(User.company).where(User.id == user_id)
                    )
                    company = result.scalar_one_or_none()

                if company:
                    token = _tenant_company.set(company)
                    try:
                        response = await call_next(request)
                    finally:
                        _tenant_company.reset(token)
                    return response
            except Exception as exc:
                logger.warning("TenantMiddleware: failed to resolve company for user_id=%s: %s", user_id, exc)

        # No tenant context — pass through (middleware auth or public endpoint)
        return await call_next(request)
