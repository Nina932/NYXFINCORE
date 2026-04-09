"""
FinAI v2 Auth Audit — DB-first write ordering, bounded fallback.
================================================================
Key fix from v1: events are appended to in-memory ONLY if DB write fails.
Previously, in-memory was written FIRST, causing inconsistency when DB failed.

Public API:
    from app.services.v2.auth_audit import auth_audit
"""

from __future__ import annotations

import logging
from collections import deque
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Maximum in-memory fallback entries (prevents unbounded growth)
_MAX_FALLBACK = 1000


class AuthAuditLogger:
    """DB-first auth audit logger with bounded in-memory fallback."""

    def __init__(self):
        self._fallback: deque = deque(maxlen=_MAX_FALLBACK)

    async def log_login_attempt(self, db, email: str, success: bool, ip_address: str = "") -> None:
        event_type = "login_success" if success else "login_failure"
        await self._store_event(
            db, event_type=event_type, email=email, ip_address=ip_address,
            detail=f"Login {'succeeded' if success else 'failed'} for {email}",
        )

    async def log_data_access(self, db, user_id: int, resource_type: str,
                                resource_id: int, action: str = "read") -> None:
        await self._store_event(
            db, event_type="data_access", user_id=user_id,
            resource_type=resource_type, resource_id=resource_id,
            detail=f"User {user_id} {action} {resource_type}:{resource_id}",
        )

    async def log_rbac_violation(self, db, user_id: int, required_role: str,
                                   user_role: str, endpoint: str) -> None:
        await self._store_event(
            db, event_type="rbac_violation", user_id=user_id,
            detail=f"User {user_id} (role={user_role}) denied {endpoint} (requires {required_role})",
        )

    async def log_token_event(self, db, user_id: int, event_type: str) -> None:
        await self._store_event(
            db, event_type=f"token_{event_type}", user_id=user_id,
            detail=f"Token {event_type} for user {user_id}",
        )

    async def get_recent_events(self, db, limit: int = 50) -> list:
        try:
            from sqlalchemy import select
            from app.models.all_models import AuthAuditEvent
            result = await db.execute(
                select(AuthAuditEvent).order_by(AuthAuditEvent.created_at.desc()).limit(limit)
            )
            return [e.to_dict() for e in result.scalars().all()]
        except Exception as e:
            logger.warning("DB query failed, returning fallback: %s", e)
            return list(self._fallback)[-limit:]

    async def _store_event(self, db, event_type: str, email: str = "",
                            user_id: Optional[int] = None, ip_address: str = "",
                            resource_type: str = "", resource_id: Optional[int] = None,
                            detail: str = "") -> None:
        """DB-FIRST write. Only falls back to in-memory if DB fails."""
        event_dict = {
            "event_type": event_type, "email": email, "user_id": user_id,
            "ip_address": ip_address, "resource_type": resource_type,
            "resource_id": resource_id, "detail": detail,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # DB-first: write to DB before in-memory
        try:
            from app.models.all_models import AuthAuditEvent
            event = AuthAuditEvent(
                event_type=event_type, email=email, user_id=user_id,
                ip_address=ip_address, resource_type=resource_type,
                resource_id=resource_id, detail=detail,
            )
            db.add(event)
            await db.flush()
            # DB succeeded — do NOT add to in-memory (it's in the DB now)
            return
        except Exception as e:
            logger.warning("Auth audit DB write failed (fallback to memory): %s", e)

        # DB failed — store in bounded in-memory fallback
        self._fallback.append(event_dict)

    async def flush_fallback_to_db(self, db) -> int:
        """Drain in-memory fallback to DB when connection recovers."""
        if not self._fallback:
            return 0

        from app.models.all_models import AuthAuditEvent
        count = 0
        while self._fallback:
            evt = self._fallback.popleft()
            try:
                db.add(AuthAuditEvent(
                    event_type=evt["event_type"], email=evt.get("email", ""),
                    user_id=evt.get("user_id"), ip_address=evt.get("ip_address", ""),
                    detail=evt.get("detail", ""),
                ))
                count += 1
            except Exception as e:
                logger.debug("Flush failed for event %s: %s", evt.get("event_type", "?"), e)
                self._fallback.appendleft(evt)  # Put it back
                break

        if count > 0:
            await db.flush()
            logger.info("Flushed %d fallback audit events to DB", count)
        return count


# Module singleton
auth_audit = AuthAuditLogger()
