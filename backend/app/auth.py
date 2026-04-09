"""
auth.py — JWT authentication utilities for FinAI.

Provides:
  - Password hashing / verification  (bcrypt via passlib)
  - JWT token creation / decoding     (HS256 via python-jose)
  - FastAPI dependency functions:
      get_current_user      — raises 401 if token missing/invalid
      get_optional_user     — returns None if no token (non-breaking)
      require_role(...)     — decorator factory for role-based access

Token format:
  Authorization: Bearer <jwt>

JWT payload:
  sub   : user email
  uid   : user id
  role  : "admin" | "analyst" | "viewer"
  exp   : expiry timestamp

Usage in routes:
    from app.auth import get_current_user, get_optional_user
    router = APIRouter()

    # Strict: 401 if no token
    @router.get("/protected")
    async def protected(user=Depends(get_current_user)):
        return {"user": user.email}

    # Soft: works with or without token
    @router.get("/open")
    async def open_route(user=Depends(get_optional_user)):
        return {"authenticated": user is not None}
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt as _bcrypt_lib
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.database import get_db

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Password hashing  (bcrypt directly — passlib 1.7.4 incompatible with bcrypt>=4)
# ---------------------------------------------------------------------------

def hash_password(plain: str) -> str:
    """Return bcrypt hash of a plaintext password."""
    return _bcrypt_lib.hashpw(plain.encode("utf-8"), _bcrypt_lib.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if plain matches the stored bcrypt hash."""
    try:
        return _bcrypt_lib.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# JWT token creation / decoding
# ---------------------------------------------------------------------------

def create_access_token(user_id: int, email: str, role: str) -> str:
    """
    Create a signed JWT access token.

    Expires in `settings.JWT_EXPIRE_HOURS` hours (default 24 h).
    """
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRE_HOURS)
    payload = {
        "sub": email,
        "uid": user_id,
        "role": role,
        "jti": uuid.uuid4().hex,  # Phase G-4: unique token ID for revocation
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """
    Decode and validate a JWT token.

    Returns the payload dict on success, None on any failure.
    """
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as exc:
        logger.debug("JWT decode failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# FastAPI security scheme
# ---------------------------------------------------------------------------
_bearer = HTTPBearer(auto_error=False)


async def _get_user_from_token(
    credentials: Optional[HTTPAuthorizationCredentials],
    db: AsyncSession,
):
    """
    Internal helper: validate Bearer token and load User from DB.

    Returns the User ORM object or None.
    """
    if not credentials or not credentials.credentials:
        return None

    payload = decode_token(credentials.credentials)
    if not payload:
        return None

    user_id: Optional[int] = payload.get("uid")
    if not user_id:
        return None

    # Phase G-4: Check token revocation blacklist
    jti = payload.get("jti")
    if jti:
        try:
            from app.models.all_models import RevokedToken
            revoked = await db.execute(select(RevokedToken).where(RevokedToken.jti == jti))
            if revoked.scalar_one_or_none():
                logger.debug("Token revoked: jti=%s", jti)
                return None
        except Exception:
            pass  # Table may not exist yet; allow through

    # Import here to avoid circular import
    from app.models.all_models import User

    result = await db.execute(select(User).where(User.id == user_id, User.is_active == True))
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
):
    """
    FastAPI dependency — requires a valid Bearer token.

    Raises HTTP 401 if:
      - No Authorization header
      - Token is expired or invalid
      - User not found or inactive

    When settings.REQUIRE_AUTH is False, this dependency is still available
    for routes that explicitly opt in to strict auth.
    """
    user = await _get_user_from_token(credentials, db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated — provide a valid Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
):
    """
    FastAPI dependency — validates token if present, returns None otherwise.

    Safe for use on any existing endpoint: callers that don't send a token
    continue to work as before. Use this to log/track authenticated requests
    without breaking unauthenticated clients.
    """
    return await _get_user_from_token(credentials, db)


def require_role(*roles: str):
    """
    Dependency factory for role-based access control.

    Usage:
        @router.delete("/dataset/{id}")
        async def delete(user=Depends(require_role("admin", "analyst"))):
            ...
    """
    async def _check(
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
        db: AsyncSession = Depends(get_db),
    ):
        user = await _get_user_from_token(credentials, db)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if user.role not in roles:
            # Phase G-4: Log RBAC violation
            try:
                from app.services.auth_audit import auth_audit
                await auth_audit.log_rbac_violation(
                    db, user_id=user.id,
                    required_role=",".join(roles),
                    user_role=user.role,
                    endpoint="(require_role check)",
                )
            except Exception:
                pass
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role}' is not permitted. Required: {list(roles)}",
            )
        return user

    return _check


# ---------------------------------------------------------------------------
# Phase G-4: Dataset ownership check
# ---------------------------------------------------------------------------

async def check_dataset_ownership(user, dataset_id: int, db: AsyncSession) -> bool:
    """
    Verify that a user owns a dataset or is admin.
    Returns True if allowed, False otherwise.
    """
    if user is None:
        return True  # No auth required (REQUIRE_AUTH=False)
    if user.role == "admin":
        return True

    from app.models.all_models import Dataset
    result = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
    dataset = result.scalar_one_or_none()
    if not dataset:
        return True  # Dataset doesn't exist, let the endpoint handle 404
    if dataset.owner_id is None:
        return True  # No owner set, allow access
    return dataset.owner_id == user.id
