"""
FinAI — Standardized Error Handling
====================================
Provides a consistent error response schema and helper functions for all
API endpoints.  Every HTTP error should flow through these helpers so that
clients always receive the same JSON shape:

    {
        "detail": "Human-readable message",
        "error_code": "MACHINE_READABLE_CODE",
        "timestamp": "2025-01-15T12:00:00Z",
        "path": "/api/datasets/42",
        "request_id": "abc-123"
    }

Usage in routers:
    from app.errors import raise_not_found, raise_validation_error
    raise_not_found("Dataset", dataset_id)
    raise_validation_error("account_code is required", field="account_code")

The global exception handler in main.py catches HTTPException and wraps it
in the ErrorResponse format automatically.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, NoReturn, Optional

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Standard error response model
# ---------------------------------------------------------------------------

class ErrorResponse(BaseModel):
    """Consistent error payload returned by all FinAI API endpoints."""
    detail: str                          # Human-readable message
    error_code: str                      # Machine-readable code (e.g. "NOT_FOUND")
    timestamp: str                       # ISO 8601
    path: Optional[str] = None           # Request path
    request_id: Optional[str] = None     # Trace ID if available


# ---------------------------------------------------------------------------
# Structured HTTPException subclass — carries error_code in *detail* dict
# ---------------------------------------------------------------------------

class FinAIHTTPException(HTTPException):
    """HTTPException that also carries an ``error_code``."""

    def __init__(
        self,
        status_code: int,
        detail: str,
        error_code: str,
        headers: dict | None = None,
    ):
        # Store error_code as part of the detail dict so the global handler
        # can extract it without monkey-patching.
        super().__init__(
            status_code=status_code,
            detail={"message": detail, "error_code": error_code},
            headers=headers,
        )


# ---------------------------------------------------------------------------
# Helper functions — each raises and never returns
# ---------------------------------------------------------------------------

def raise_not_found(resource: str, id: Any) -> NoReturn:
    """404 — resource not found."""
    raise FinAIHTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"{resource} {id} not found",
        error_code="NOT_FOUND",
    )


def raise_validation_error(detail: str, field: str | None = None) -> NoReturn:
    """400 — validation / bad-request error."""
    msg = f"{field}: {detail}" if field else detail
    raise FinAIHTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=msg,
        error_code="VALIDATION_FAILED",
    )


def raise_auth_error(detail: str = "Authentication required") -> NoReturn:
    """401 — authentication error."""
    raise FinAIHTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        error_code="AUTH_REQUIRED",
        headers={"WWW-Authenticate": "Bearer"},
    )


def raise_forbidden(detail: str = "Insufficient permissions") -> NoReturn:
    """403 — authorization / permission error."""
    raise FinAIHTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=detail,
        error_code="FORBIDDEN",
    )


def raise_conflict(detail: str) -> NoReturn:
    """409 — conflict (duplicate, already exists, etc.)."""
    raise FinAIHTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=detail,
        error_code="CONFLICT",
    )


def raise_rate_limited(retry_after: int = 60) -> NoReturn:
    """429 — too many requests."""
    raise FinAIHTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Too many requests. Please slow down.",
        error_code="RATE_LIMITED",
        headers={"Retry-After": str(retry_after)},
    )


def raise_upload_error(detail: str) -> NoReturn:
    """413 — upload too large or upload-related error."""
    raise FinAIHTTPException(
        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        detail=detail,
        error_code="UPLOAD_TOO_LARGE",
    )


def raise_unprocessable(detail: str) -> NoReturn:
    """422 — unprocessable entity (parse failures, schema errors, etc.)."""
    raise FinAIHTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=detail,
        error_code="UNPROCESSABLE_ENTITY",
    )


def raise_internal_error(detail: str = "Internal server error") -> NoReturn:
    """500 — unexpected server-side error."""
    raise FinAIHTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=detail,
        error_code="INTERNAL_ERROR",
    )


# ---------------------------------------------------------------------------
# Utility: build an ErrorResponse dict (used by middleware, global handler)
# ---------------------------------------------------------------------------

def build_error_dict(
    detail: str,
    error_code: str,
    path: str | None = None,
    request_id: str | None = None,
) -> dict:
    """Return a plain dict matching the ErrorResponse schema."""
    return {
        "detail": detail,
        "error_code": error_code,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "path": path,
        "request_id": request_id,
    }


# ---------------------------------------------------------------------------
# Global exception handlers — installed in main.py
# ---------------------------------------------------------------------------

def _extract_trace_id(request: Request) -> str | None:
    """Try to pull the trace/request ID from request state or headers."""
    try:
        return getattr(request.state, "trace_id", None) or request.headers.get("X-Trace-Id")
    except Exception:
        return None


async def finai_http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle HTTPException (including FinAIHTTPException) and return ErrorResponse JSON."""
    path = request.url.path
    request_id = _extract_trace_id(request)

    # FinAIHTTPException stores detail as {"message": ..., "error_code": ...}
    if isinstance(exc.detail, dict) and "error_code" in exc.detail:
        detail_msg = exc.detail["message"]
        error_code = exc.detail["error_code"]
    else:
        detail_msg = str(exc.detail) if exc.detail else "Unknown error"
        # Derive a reasonable error_code from the status code
        error_code = _status_to_error_code(exc.status_code)

    body = build_error_dict(
        detail=detail_msg,
        error_code=error_code,
        path=path,
        request_id=request_id,
    )

    headers = getattr(exc, "headers", None) or {}
    return JSONResponse(status_code=exc.status_code, content=body, headers=headers)


async def finai_generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unhandled exceptions — always returns ErrorResponse JSON."""
    from app.config import settings

    logger.error("Unhandled error: %s", exc, exc_info=True)
    detail_msg = str(exc) if settings.DEBUG else "Internal server error"
    path = request.url.path
    request_id = _extract_trace_id(request)

    body = build_error_dict(
        detail=detail_msg,
        error_code="INTERNAL_ERROR",
        path=path,
        request_id=request_id,
    )
    return JSONResponse(status_code=500, content=body)


def _status_to_error_code(status_code: int) -> str:
    """Map HTTP status codes to machine-readable error codes."""
    mapping = {
        400: "VALIDATION_FAILED",
        401: "AUTH_REQUIRED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        413: "UPLOAD_TOO_LARGE",
        422: "UNPROCESSABLE_ENTITY",
        429: "RATE_LIMITED",
        500: "INTERNAL_ERROR",
        502: "BAD_GATEWAY",
        503: "SERVICE_UNAVAILABLE",
    }
    return mapping.get(status_code, "ERROR")
