"""
Field-Level Audit Trail
========================
Tracks every field change on journal entries, posting lines, and periods.
Stores: entity_type, entity_id, field_name, old_value, new_value, changed_by, changed_at, change_reason

Provides immutable, queryable audit history for SOX/IFRS compliance.

Public API:
    from app.services.v2.audit_trail import audit_trail_service
    await audit_trail_service.log_change(db, "journal_entry", 42, "status", "draft", "posted", "system", "Auto-post")
    trail = await audit_trail_service.get_trail(db, "journal_entry", 42)
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class AuditTrailService:
    """
    Field-level audit trail for financial records.

    Every mutation to journal entries, posting lines, fiscal periods,
    or any tracked entity is recorded as an immutable audit entry.
    """

    async def log_change(
        self,
        db: AsyncSession,
        entity_type: str,
        entity_id: int,
        field_name: str,
        old_value: Optional[str],
        new_value: Optional[str],
        changed_by: str = "system",
        reason: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Record a single field-level change.

        Args:
            db: Async database session
            entity_type: Type of entity ("journal_entry", "posting_line", "period")
            entity_id: ID of the entity being changed
            field_name: Name of the field that changed
            old_value: Previous value (as string, None for creation)
            new_value: New value (as string, None for deletion)
            changed_by: User or system identifier
            reason: Human-readable reason for the change
            session_id: Optional session/request identifier for grouping

        Returns:
            Dict with the created audit entry details.
        """
        from app.models.all_models import AuditTrailEntry

        entry = AuditTrailEntry(
            entity_type=entity_type,
            entity_id=entity_id,
            field_name=field_name,
            old_value=str(old_value) if old_value is not None else None,
            new_value=str(new_value) if new_value is not None else None,
            changed_by=changed_by,
            changed_at=datetime.now(timezone.utc),
            change_reason=reason,
            session_id=session_id or str(uuid.uuid4())[:8],
        )
        db.add(entry)
        await db.flush()

        logger.info(
            "Audit: %s #%d field '%s' changed from '%s' to '%s' by %s",
            entity_type, entity_id, field_name,
            old_value, new_value, changed_by,
        )

        return {
            "id": entry.id,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "field_name": field_name,
            "old_value": old_value,
            "new_value": new_value,
            "changed_by": changed_by,
            "change_reason": reason,
        }

    async def log_changes_bulk(
        self,
        db: AsyncSession,
        entity_type: str,
        entity_id: int,
        changes: Dict[str, tuple],
        changed_by: str = "system",
        reason: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Record multiple field changes for the same entity in one call.

        Args:
            changes: Dict of field_name -> (old_value, new_value)

        Returns:
            List of created audit entry dicts.
        """
        sid = session_id or str(uuid.uuid4())[:8]
        results = []
        for field_name, (old_val, new_val) in changes.items():
            if str(old_val) != str(new_val):
                result = await self.log_change(
                    db, entity_type, entity_id, field_name,
                    old_val, new_val, changed_by, reason, sid,
                )
                results.append(result)
        return results

    async def get_trail(
        self,
        db: AsyncSession,
        entity_type: str,
        entity_id: int,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get the full audit trail for a specific entity.

        Args:
            db: Async database session
            entity_type: Type of entity
            entity_id: ID of the entity
            limit: Max records to return

        Returns:
            List of audit trail entries, newest first.
        """
        from app.models.all_models import AuditTrailEntry

        result = await db.execute(
            select(AuditTrailEntry)
            .where(
                AuditTrailEntry.entity_type == entity_type,
                AuditTrailEntry.entity_id == entity_id,
            )
            .order_by(desc(AuditTrailEntry.changed_at))
            .limit(limit)
        )
        entries = result.scalars().all()

        return [
            {
                "id": e.id,
                "entity_type": e.entity_type,
                "entity_id": e.entity_id,
                "field_name": e.field_name,
                "old_value": e.old_value,
                "new_value": e.new_value,
                "changed_by": e.changed_by,
                "changed_at": e.changed_at.isoformat() if e.changed_at else None,
                "change_reason": e.change_reason,
                "session_id": e.session_id,
            }
            for e in entries
        ]

    async def get_trail_summary(
        self,
        db: AsyncSession,
        entity_type: str,
        limit: int = 1000,
    ) -> Dict[str, Any]:
        """
        Get aggregate summary of changes for an entity type.

        Returns counts by field name, by user, and recent activity.
        """
        from app.models.all_models import AuditTrailEntry

        # Counts by field
        field_counts_result = await db.execute(
            select(
                AuditTrailEntry.field_name,
                func.count(AuditTrailEntry.id).label("count"),
            )
            .where(AuditTrailEntry.entity_type == entity_type)
            .group_by(AuditTrailEntry.field_name)
            .order_by(func.count(AuditTrailEntry.id).desc())
        )
        by_field = {row.field_name: row.count for row in field_counts_result.all()}

        # Counts by user
        user_counts_result = await db.execute(
            select(
                AuditTrailEntry.changed_by,
                func.count(AuditTrailEntry.id).label("count"),
            )
            .where(AuditTrailEntry.entity_type == entity_type)
            .group_by(AuditTrailEntry.changed_by)
            .order_by(func.count(AuditTrailEntry.id).desc())
        )
        by_user = {row.changed_by: row.count for row in user_counts_result.all()}

        # Total count
        total_result = await db.execute(
            select(func.count(AuditTrailEntry.id))
            .where(AuditTrailEntry.entity_type == entity_type)
        )
        total_count = total_result.scalar() or 0

        # Most recent entries
        recent_result = await db.execute(
            select(AuditTrailEntry)
            .where(AuditTrailEntry.entity_type == entity_type)
            .order_by(desc(AuditTrailEntry.changed_at))
            .limit(10)
        )
        recent = [
            {
                "entity_id": e.entity_id,
                "field_name": e.field_name,
                "changed_by": e.changed_by,
                "changed_at": e.changed_at.isoformat() if e.changed_at else None,
                "change_reason": e.change_reason,
            }
            for e in recent_result.scalars().all()
        ]

        return {
            "entity_type": entity_type,
            "total_changes": total_count,
            "by_field": by_field,
            "by_user": by_user,
            "recent_changes": recent,
        }


# Module singleton
audit_trail_service = AuditTrailService()
