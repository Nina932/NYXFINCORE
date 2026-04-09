"""
auth_router.py — Authentication endpoints for FinAI.

Endpoints:
  POST /api/auth/register    — create a new user account
  POST /api/auth/login       — exchange credentials for JWT
  GET  /api/auth/me          — return current user info
  POST /api/auth/refresh     — (future) refresh expired tokens
  POST /api/auth/logout      — client-side token invalidation hint

Security notes:
  - Passwords are bcrypt-hashed server-side
  - Tokens are HS256-signed JWTs (no refresh token yet — single token per login)
  - The first registered user is automatically given the "admin" role
  - Registration is open by default; set REQUIRE_AUTH=True to lock down
"""

import logging
import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.config import settings
from app.database import get_db
from app.models.all_models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_\-]+$")
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = None
    company: Optional[str] = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if not _EMAIL_RE.match(v.strip()):
            raise ValueError("Invalid email address format")
        return v.strip().lower()


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int      # seconds
    user: dict


class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    full_name: Optional[str]
    role: str
    company: Optional[str]
    is_active: bool
    is_verified: bool
    created_at: Optional[str]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """
    Create a new user and return an access token immediately.

    The first user to register receives the `admin` role.
    Subsequent users receive the `analyst` role by default.
    """
    # Check email uniqueness
    existing = await db.execute(
        select(User).where(User.email == body.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Email '{body.email}' is already registered",
        )

    # Check username uniqueness
    existing_uname = await db.execute(
        select(User).where(User.username == body.username)
    )
    if existing_uname.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{body.username}' is already taken",
        )

    # First user becomes admin
    count_result = await db.execute(select(func.count(User.id)))
    user_count = count_result.scalar() or 0
    role = "admin" if user_count == 0 else "analyst"

    user = User(
        email=body.email,
        username=body.username,
        full_name=body.full_name,
        hashed_password=hash_password(body.password),
        role=role,
        company=body.company or settings.COMPANY_NAME,
        is_active=True,
        is_verified=False,  # Email verification not yet implemented
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    logger.info("New user registered: %s (role=%s)", user.email, user.role)

    token = create_access_token(user.id, user.email, user.role)
    return TokenResponse(
        access_token=token,
        expires_in=settings.JWT_EXPIRE_HOURS * 3600,
        user=user.to_dict(),
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Exchange credentials for a JWT access token",
)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate with email + password and receive a JWT."""
    result = await db.execute(
        select(User).where(User.email == body.email, User.is_active == True)
    )
    user = result.scalar_one_or_none()

    # Use constant-time comparison to mitigate timing attacks
    if user is None or not verify_password(body.password, user.hashed_password):
        # Phase G-4: Log failed login
        try:
            from app.services.auth_audit import auth_audit
            await auth_audit.log_login_attempt(db, body.email, success=False)
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Phase G-4: Log successful login
    try:
        from app.services.auth_audit import auth_audit
        await auth_audit.log_login_attempt(db, body.email, success=True)
    except Exception:
        pass

    # Update last login timestamp
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    from app.config import settings
    token = create_access_token(user.id, user.email, user.role)
    logger.info("User login: %s", user.email)

    return TokenResponse(
        access_token=token,
        expires_in=settings.JWT_EXPIRE_HOURS * 3600,
        user=user.to_dict(),
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Return the currently authenticated user's profile",
)
async def me(current_user: User = Depends(get_current_user)):
    """Returns the profile of the user who owns the supplied Bearer token."""
    return UserResponse(**current_user.to_dict())


@router.post(
    "/logout",
    summary="Revoke the current token (Phase G-4)",
)
async def logout(
    current_user: User = Depends(get_current_user),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: AsyncSession = Depends(get_db),
):
    """
    Phase G-4: Server-side token revocation.
    Extracts the actual JTI from the token and adds it to the revoked_tokens table.
    """
    try:
        from app.auth import decode_token
        from app.models.all_models import RevokedToken
        from app.services.auth_audit import auth_audit
        from datetime import datetime, timezone

        # Extract actual JTI from the token
        token_str = credentials.credentials if credentials else None
        if not token_str:
            return {"message": "Logged out. Please discard your token on the client side."}

        payload = decode_token(token_str)
        if not payload or "jti" not in payload:
            return {"message": "Logged out. Please discard your token on the client side."}

        jti = payload["jti"]

        # Calculate token expiry from payload
        exp_timestamp = payload.get("exp")
        expires_at = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc) if exp_timestamp else None

        revoked = RevokedToken(
            jti=jti,
            user_id=current_user.id,
            expires_at=expires_at,
        )
        db.add(revoked)
        await auth_audit.log_token_event(db, current_user.id, "revoked")
        logger.info("Token revoked for user %s (jti=%s)", current_user.email, jti[:8])
        return {"message": "Token revoked successfully. Please discard your token on the client side."}
    except Exception as e:
        logger.warning("Logout revocation failed: %s", e)
        return {"message": "Logged out. Please discard your token on the client side."}


@router.get(
    "/audit",
    summary="View auth audit events (admin only, Phase G-4)",
)
async def auth_audit_events(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return recent authentication audit events. Requires admin role."""
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    try:
        from app.services.auth_audit import auth_audit
        events = await auth_audit.get_recent_events(db, limit=limit)
        return {"events": events, "count": len(events)}
    except Exception as e:
        return {"error": str(e), "events": []}


@router.get(
    "/users",
    summary="List all users (admin only)",
)
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all registered users. Requires admin role."""
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    result = await db.execute(select(User).order_by(User.created_at))
    users = result.scalars().all()
    return [u.to_dict() for u in users]


# ---------------------------------------------------------------------------
# SSO / SAML / OIDC endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/sso/config",
    summary="List available SSO providers",
)
async def sso_config():
    """Return all configured SSO identity providers (public info, no secrets)."""
    from app.services.sso_provider import sso_manager
    providers = sso_manager.list_providers()
    return {"providers": providers, "sso_enabled": len(providers) > 0}


@router.get(
    "/sso/{provider}/login",
    summary="Initiate SSO login flow",
)
async def sso_login(provider: str):
    """Generate the SSO redirect URL for the given provider.

    The frontend should redirect the user's browser to the returned URL.
    After authentication the IdP will POST/redirect back to our callback.
    """
    from app.services.sso_provider import sso_manager

    result = sso_manager.initiate_login(provider)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SSO provider '{provider}' is not configured or not enabled",
        )
    return {
        "provider": provider,
        "redirect_url": result["redirect_url"],
        "state": result["state"],
    }


class SSOCallbackRequest(BaseModel):
    code: Optional[str] = None          # OAuth2/OIDC authorization code
    state: Optional[str] = None         # CSRF state parameter
    SAMLResponse: Optional[str] = None  # SAML Response (base64)
    RelayState: Optional[str] = None    # SAML RelayState


@router.post(
    "/sso/{provider}/callback",
    summary="Handle SSO callback from identity provider",
)
async def sso_callback(
    provider: str,
    body: SSOCallbackRequest,
    db: AsyncSession = Depends(get_db),
):
    """Process the SSO callback from an identity provider.

    For OAuth2/OIDC: exchanges the authorization code for tokens and user info.
    For SAML: parses the SAML assertion to extract user attributes.

    If the user email exists, logs them in. Otherwise, creates a new account.
    Returns the same JWT token format as /login.
    """
    from app.services.sso_provider import sso_manager

    # Handle the callback through the SSO manager
    user_attrs = await sso_manager.handle_callback(
        provider_id=provider,
        code=body.code or "",
        state=body.state or body.RelayState or "",
        saml_response=body.SAMLResponse or "",
    )

    if not user_attrs:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="SSO authentication failed — could not verify identity",
        )

    email = user_attrs.get("email", "").lower().strip()
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SSO provider did not return an email address",
        )

    # Find or create user
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None:
        # Create new user from SSO attributes
        full_name = user_attrs.get("full_name", "")
        username = email.split("@")[0]

        # Ensure unique username
        existing_uname = await db.execute(
            select(User).where(User.username == username)
        )
        if existing_uname.scalar_one_or_none():
            import secrets as _secrets
            username = f"{username}_{_secrets.token_hex(3)}"

        # Determine role (first user = admin)
        count_result = await db.execute(select(func.count(User.id)))
        user_count = count_result.scalar() or 0
        role = "admin" if user_count == 0 else "analyst"

        # SSO users get a random password hash (they authenticate via SSO)
        import secrets as _secrets
        random_pw = _secrets.token_urlsafe(32)

        user = User(
            email=email,
            username=username,
            full_name=full_name or username,
            hashed_password=hash_password(random_pw),
            role=role,
            company=user_attrs.get("company", ""),
            is_active=True,
            is_verified=True,  # SSO-verified by the IdP
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        logger.info("SSO user created: %s via %s", email, provider)
    else:
        # Update last login
        user.last_login_at = datetime.now(timezone.utc)
        await db.commit()
        logger.info("SSO user login: %s via %s", email, provider)

    # Issue JWT
    from app.config import settings as _settings
    token = create_access_token(user.id, user.email, user.role)

    # Audit log
    try:
        from app.services.auth_audit import auth_audit
        await auth_audit.log_login_attempt(db, email, success=True)
    except Exception:
        pass

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": _settings.JWT_EXPIRE_HOURS * 3600,
        "user": user.to_dict(),
        "sso_provider": provider,
    }
