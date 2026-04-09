"""
FinAI v2 Approval Engine — Maker-checker workflow for financial operations.
============================================================================
Fills the "No posting approval" gap from SAP FI benchmark.

Workflow: Draft → Submitted → Approved/Rejected → Posted
- Maker creates journal entry (status=draft)
- Submits for approval (status=submitted)
- Checker reviews and approves/rejects
- On approval: auto-posts via journal_system

Enforces segregation of duties: maker ≠ checker.

Public API:
    from app.services.v2.approval_engine import approval_engine
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class ApprovalEngine:
    """Maker-checker approval workflow for journal entries."""

    async def submit_for_approval(
        self,
        journal_entry_id: int,
        submitted_by: int,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Submit a draft journal entry for approval."""
        from app.models.all_models import JournalEntryRecord

        result = await db.execute(
            select(JournalEntryRecord).where(JournalEntryRecord.id == journal_entry_id)
        )
        je = result.scalar_one_or_none()

        if not je:
            raise ValueError(f"Journal entry {journal_entry_id} not found")
        if je.status != "draft":
            raise ValueError(f"Only draft entries can be submitted (current: {je.status})")

        je.status = "submitted"
        await db.flush()

        # Audit trail: record draft → submitted
        try:
            from app.services.v2.audit_trail import audit_trail_service
            await audit_trail_service.log_change(
                db, "journal_entry", je.id, "status",
                "draft", "submitted",
                str(submitted_by),
                "Journal entry submitted for approval",
            )
        except Exception:
            pass  # Audit trail should never block the main operation

        logger.info("JE %s submitted for approval by user %d", je.document_number, submitted_by)
        return {"journal_entry_id": je.id, "status": "submitted", "submitted_by": submitted_by}

    async def approve(
        self,
        journal_entry_id: int,
        approved_by: int,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Approve a submitted journal entry. Auto-posts on approval.

        Enforces segregation of duties: approver ≠ creator.
        """
        from app.models.all_models import JournalEntryRecord

        result = await db.execute(
            select(JournalEntryRecord).where(JournalEntryRecord.id == journal_entry_id)
        )
        je = result.scalar_one_or_none()

        if not je:
            raise ValueError(f"Journal entry {journal_entry_id} not found")
        if je.status != "submitted":
            raise ValueError(f"Only submitted entries can be approved (current: {je.status})")

        # Segregation of duties: approver cannot be the creator
        if je.created_by and je.created_by == approved_by:
            raise ValueError(
                f"Segregation of duties violation: user {approved_by} cannot approve "
                f"their own journal entry. A different user must approve."
            )

        # Audit trail: record submitted → approved (before auto-post)
        try:
            from app.services.v2.audit_trail import audit_trail_service
            await audit_trail_service.log_change(
                db, "journal_entry", je.id, "status",
                "submitted", "approved",
                str(approved_by),
                "Journal entry approved",
            )
        except Exception:
            pass  # Audit trail should never block the main operation

        # Auto-post on approval
        from app.services.v2.journal_system import journal_service
        posted = await journal_service.post_entry(je.id, posted_by=approved_by, db=db)

        logger.info("JE %s approved and posted by user %d", je.document_number, approved_by)
        return {
            "journal_entry_id": je.id,
            "status": "posted",
            "approved_by": approved_by,
            "document_number": posted["document_number"],
        }

    async def reject(
        self,
        journal_entry_id: int,
        rejected_by: int,
        reason: str,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Reject a submitted journal entry back to draft."""
        from app.models.all_models import JournalEntryRecord

        result = await db.execute(
            select(JournalEntryRecord).where(JournalEntryRecord.id == journal_entry_id)
        )
        je = result.scalar_one_or_none()

        if not je:
            raise ValueError(f"Journal entry {journal_entry_id} not found")
        if je.status != "submitted":
            raise ValueError(f"Only submitted entries can be rejected (current: {je.status})")

        je.status = "draft"  # Return to draft for corrections
        je.reference = f"{je.reference or ''} | REJECTED: {reason}"
        await db.flush()

        # Audit trail: record submitted → draft (rejected)
        try:
            from app.services.v2.audit_trail import audit_trail_service
            await audit_trail_service.log_change(
                db, "journal_entry", je.id, "status",
                "submitted", "draft",
                str(rejected_by),
                f"Journal entry rejected: {reason}",
            )
        except Exception:
            pass  # Audit trail should never block the main operation

        logger.info("JE %s rejected by user %d: %s", je.document_number, rejected_by, reason)
        return {
            "journal_entry_id": je.id,
            "status": "draft",
            "rejected_by": rejected_by,
            "reason": reason,
        }

    async def get_pending_approvals(
        self,
        db: AsyncSession,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get all journal entries awaiting approval."""
        from app.models.all_models import JournalEntryRecord

        result = await db.execute(
            select(JournalEntryRecord)
            .where(JournalEntryRecord.status == "submitted")
            .order_by(JournalEntryRecord.created_at.desc())
            .limit(limit)
        )
        entries = result.scalars().all()
        return [je.to_dict() for je in entries]

    async def get_approval_stats(self, db: AsyncSession) -> Dict[str, int]:
        """Get approval queue statistics."""
        from app.models.all_models import JournalEntryRecord

        draft = (await db.execute(
            select(func.count()).select_from(JournalEntryRecord)
            .where(JournalEntryRecord.status == "draft")
        )).scalar() or 0

        submitted = (await db.execute(
            select(func.count()).select_from(JournalEntryRecord)
            .where(JournalEntryRecord.status == "submitted")
        )).scalar() or 0

        posted = (await db.execute(
            select(func.count()).select_from(JournalEntryRecord)
            .where(JournalEntryRecord.status == "posted")
        )).scalar() or 0

        return {"draft": draft, "submitted": submitted, "posted": posted, "total": draft + submitted + posted}


# Module singleton
approval_engine = ApprovalEngine()
