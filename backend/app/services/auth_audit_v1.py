"""
auth_audit.py -- Authentication Audit Logger
==============================================
Logs all authentication events for security auditing:
  - Login attempts (success/failure)
  - Token validation events
  - Data access events (which user accessed which dataset)
  - RBAC violations (403 events)

Phase G-4 of the FinAI Full System Upgrade.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


class AuthAuditLogger:
    """
    Records authentication and authorization events.

    All methods are async to support DB persistence. Falls back to
    in-memory logging if DB is unavailable.
    """

    def __init__(self):
        self._events: list = []  # In-memory fallback

    async def log_login_attempt(
        self,
        db,
        email: str,
        success: bool,
        ip_address: str = "",
    ) -> None:
        """Log a login attempt (success or failure)."""
        event_type = "login_success" if success else "login_failure"
        await self._store_event(
            db, event_type=event_type, email=email,
            ip_address=ip_address,
            detail=f"Login {'succeeded' if success else 'failed'} for {email}",
        )

    async def log_data_access(
        self,
        db,
        user_id: int,
        resource_type: str,
        resource_id: int,
        action: str = "read",
    ) -> None:
        """Log data access events (dataset read, report view, etc.)."""
        await self._store_event(
            db, event_type="data_access", user_id=user_id,
            resource_type=resource_type, resource_id=resource_id,
            detail=f"User {user_id} {action} {resource_type}:{resource_id}",
        )

    async def log_rbac_violation(
        self,
        db,
        user_id: int,
        required_role: str,
        user_role: str,
        endpoint: str,
    ) -> None:
        """Log RBAC violations (403 access denied events)."""
        await self._store_event(
            db, event_type="rbac_violation", user_id=user_id,
            detail=f"User {user_id} (role={user_role}) denied access to {endpoint} (requires {required_role})",
        )

    async def log_token_event(
        self,
        db,
        user_id: int,
        event_type: str,  # "created" | "revoked" | "expired" | "invalid"
    ) -> None:
        """Log token lifecycle events."""
        await self._store_event(
            db, event_type=f"token_{event_type}", user_id=user_id,
            detail=f"Token {event_type} for user {user_id}",
        )

    async def get_recent_events(self, db, limit: int = 50) -> list:
        """Get recent auth audit events from DB."""
        try:
            from sqlalchemy import select
            from app.models.all_models import AuthAuditEvent
            result = await db.execute(
                select(AuthAuditEvent)
                .order_by(AuthAuditEvent.created_at.desc())
                .limit(limit)
            )
            events = result.scalars().all()
            return [e.to_dict() for e in events]
        except Exception as e:
            logger.warning("Failed to query audit events from DB: %s", e)
            return self._events[-limit:]

    async def _store_event(
        self,
        db,
        event_type: str,
        email: str = "",
        user_id: Optional[int] = None,
        ip_address: str = "",
        resource_type: str = "",
        resource_id: Optional[int] = None,
        detail: str = "",
    ) -> None:
        """Persist an audit event to the DB (or in-memory fallback)."""
        event_dict = {
            "event_type": event_type,
            "email": email,
            "user_id": user_id,
            "ip_address": ip_address,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "detail": detail,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._events.append(event_dict)
        try:
            from app.models.all_models import AuthAuditEvent
            event = AuthAuditEvent(
                event_type=event_type,
                email=email,
                user_id=user_id,
                ip_address=ip_address,
                resource_type=resource_type,
                resource_id=resource_id,
                detail=detail,
            )
            db.add(event)
            await db.flush()
        except Exception as e:
            logger.debug("Auth audit DB store failed (using in-memory): %s", e)


# Module singleton
auth_audit = AuthAuditLogger()
