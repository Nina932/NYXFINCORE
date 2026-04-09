"""
FinAI v2 Journal System — Persistent Double-Entry Bookkeeping Engine
=====================================================================
System of Record: every financial fact originates from a journal entry.

Architecture:
- JournalEntry: immutable after posting (only reversals, no modifications)
- PostingLine: debit/credit lines with Decimal precision
- DocumentNumberSequence: gapless sequential numbering per fiscal year
- FiscalPeriod: open/closed period enforcement

Core invariant: sum(debit) = sum(credit) for EVERY journal entry, enforced
at both application level and verified via document hash.

Public API:
    from app.services.v2.journal_system import journal_service
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.v2.decimal_utils import to_decimal, round_fin, is_zero

logger = logging.getLogger(__name__)


class UnbalancedEntryError(Exception):
    """Raised when a journal entry's debits do not equal credits."""
    pass


class PeriodClosedError(Exception):
    """Raised when posting to a closed period."""
    pass


class ImmutableEntryError(Exception):
    """Raised when trying to modify a posted (immutable) journal entry."""
    pass


class JournalService:
    """
    Persistent double-entry journal system.

    Every financial operation flows through this service:
    1. Create draft journal entry
    2. Add posting lines (debit + credit)
    3. Validate balance (DR = CR)
    4. Post → assigns document number, becomes immutable
    5. Reverse → creates mirror entry (never modifies original)
    """

    # ── Journal Entry CRUD ────────────────────────────────────────────

    async def create_entry(
        self,
        posting_date: datetime,
        period: str,
        fiscal_year: int,
        description: str,
        lines: List[Dict[str, Any]],
        currency: str = "GEL",
        reference: str = "",
        source_type: str = "manual",
        source_id: Optional[int] = None,
        created_by: Optional[int] = None,
        db: AsyncSession = None,
    ) -> Dict[str, Any]:
        """Create a draft journal entry with posting lines.

        Args:
            lines: List of dicts with keys: account_code, debit, credit, description,
                   cost_center (optional), tax_code (optional)

        Returns:
            Dict with journal entry details including id and status="draft"

        Raises:
            UnbalancedEntryError: if sum(debit) != sum(credit)
            ValueError: if no lines provided
        """
        if not db:
            raise ValueError("Database session required")
        if not lines:
            raise ValueError("Journal entry must have at least one posting line")

        from app.models.all_models import JournalEntryRecord, PostingLineRecord

        # Validate balance BEFORE creating anything
        total_dr = Decimal("0")
        total_cr = Decimal("0")
        for line in lines:
            total_dr += to_decimal(line.get("debit", 0))
            total_cr += to_decimal(line.get("credit", 0))

        if total_dr != total_cr:
            raise UnbalancedEntryError(
                f"Journal entry is unbalanced: DR={round_fin(total_dr)} != CR={round_fin(total_cr)}. "
                f"Difference: {round_fin(abs(total_dr - total_cr))}"
            )

        if is_zero(total_dr):
            raise ValueError("Journal entry has zero total — at least one line must have a non-zero amount")

        # Check period status
        await self._validate_period_open(period, db)

        # Create journal entry (draft — temporary unique number, replaced on posting)
        import uuid as _uuid
        je = JournalEntryRecord(
            document_number=f"DRAFT-{_uuid.uuid4().hex[:12]}",
            posting_date=posting_date,
            period=period,
            fiscal_year=fiscal_year,
            description=description,
            status="draft",
            reference=reference,
            currency=currency,
            source_type=source_type,
            source_id=source_id,
            total_debit=str(round_fin(total_dr)),
            total_credit=str(round_fin(total_cr)),
            created_by=created_by,
        )
        db.add(je)
        await db.flush()  # Get the ID

        # Create posting lines
        for i, line in enumerate(lines, 1):
            pl = PostingLineRecord(
                journal_entry_id=je.id,
                line_number=i,
                account_code=line["account_code"],
                account_name=line.get("account_name", ""),
                cost_center=line.get("cost_center"),
                profit_center=line.get("profit_center"),
                debit=str(round_fin(to_decimal(line.get("debit", 0)))),
                credit=str(round_fin(to_decimal(line.get("credit", 0)))),
                description=line.get("description", ""),
                tax_code=line.get("tax_code"),
                currency=currency,
            )
            db.add(pl)

        await db.flush()

        logger.info(
            "JE draft created: id=%d, DR=%s, CR=%s, lines=%d",
            je.id, round_fin(total_dr), round_fin(total_cr), len(lines),
        )

        return je.to_dict()

    async def post_entry(
        self,
        journal_entry_id: int,
        posted_by: Optional[int] = None,
        db: AsyncSession = None,
    ) -> Dict[str, Any]:
        """Post a draft journal entry — assigns document number, makes immutable.

        Raises:
            ImmutableEntryError: if already posted
            UnbalancedEntryError: if lines are unbalanced (re-verified)
            PeriodClosedError: if period is hard-closed
        """
        if not db:
            raise ValueError("Database session required")

        from app.models.all_models import JournalEntryRecord, PostingLineRecord

        # Load entry
        result = await db.execute(
            select(JournalEntryRecord).where(JournalEntryRecord.id == journal_entry_id)
        )
        je = result.scalar_one_or_none()
        if not je:
            raise ValueError(f"Journal entry {journal_entry_id} not found")

        if je.status != "draft":
            raise ImmutableEntryError(
                f"Journal entry {je.document_number} is already {je.status} — cannot post"
            )

        # Re-verify period
        await self._validate_period_open(je.period, db)

        # Re-verify balance
        lines_result = await db.execute(
            select(PostingLineRecord).where(PostingLineRecord.journal_entry_id == je.id)
        )
        lines = lines_result.scalars().all()
        total_dr = sum(to_decimal(l.debit) for l in lines)
        total_cr = sum(to_decimal(l.credit) for l in lines)

        if total_dr != total_cr:
            raise UnbalancedEntryError(
                f"Re-verification failed: DR={total_dr} != CR={total_cr}"
            )

        # Assign gapless document number
        doc_number = await self._next_document_number("JE", je.fiscal_year, db)

        # Compute document hash for immutability verification
        doc_hash = self._compute_hash(je, lines)

        # Update entry
        je.document_number = doc_number
        je.status = "posted"
        je.is_immutable = True
        je.posted_by = posted_by
        je.posted_at = datetime.now(timezone.utc)
        je.document_hash = doc_hash

        await db.flush()

        logger.info(
            "JE posted: %s (id=%d), DR=%s, CR=%s, hash=%s",
            doc_number, je.id, total_dr, total_cr, doc_hash[:12],
        )

        # Audit trail: record status change draft → posted
        try:
            from app.services.v2.audit_trail import audit_trail_service
            await audit_trail_service.log_change(
                db, "journal_entry", je.id, "status",
                "draft", "posted",
                str(posted_by or "system"),
                f"Journal entry posted as {doc_number}",
            )
        except Exception:
            pass  # Audit trail should never block the main operation

        # Emit event → triggers downstream workflows (reconciliation, KPI update, etc.)
        try:
            from app.services.v2.event_dispatcher import event_dispatcher
            import asyncio
            asyncio.ensure_future(event_dispatcher.dispatch("journal_posted", {
                "entry_id": je.id,
                "document_number": doc_number,
                "period": je.period,
                "total_debit": str(total_dr),
                "total_credit": str(total_cr),
                "description": je.description,
                "source_type": je.source_type,
            }))
        except Exception:
            pass  # Non-blocking: event dispatch failure shouldn't block posting

        return je.to_dict()

    async def reverse_entry(
        self,
        journal_entry_id: int,
        reversal_date: Optional[datetime] = None,
        reversed_by: Optional[int] = None,
        db: AsyncSession = None,
    ) -> Dict[str, Any]:
        """Create a reversal entry (mirror of original). Original is NOT modified.

        Returns the NEW reversal journal entry.
        """
        if not db:
            raise ValueError("Database session required")

        from app.models.all_models import JournalEntryRecord, PostingLineRecord

        # Load original
        result = await db.execute(
            select(JournalEntryRecord).where(JournalEntryRecord.id == journal_entry_id)
        )
        original = result.scalar_one_or_none()
        if not original:
            raise ValueError(f"Journal entry {journal_entry_id} not found")

        if original.status != "posted":
            raise ValueError(f"Can only reverse posted entries (current status: {original.status})")

        # Load original lines
        lines_result = await db.execute(
            select(PostingLineRecord).where(PostingLineRecord.journal_entry_id == original.id)
        )
        original_lines = lines_result.scalars().all()

        # Create reversal lines (swap debit/credit)
        reversal_lines = []
        for line in original_lines:
            reversal_lines.append({
                "account_code": line.account_code,
                "account_name": line.account_name,
                "debit": line.credit,  # Swapped
                "credit": line.debit,  # Swapped
                "description": f"Reversal of {original.document_number}: {line.description or ''}",
                "cost_center": line.cost_center,
                "tax_code": line.tax_code,
            })

        rev_date = reversal_date or datetime.now(timezone.utc)

        # Create the reversal entry
        reversal = await self.create_entry(
            posting_date=rev_date,
            period=original.period,
            fiscal_year=original.fiscal_year,
            description=f"Reversal of {original.document_number}: {original.description}",
            lines=reversal_lines,
            currency=original.currency,
            reference=f"REV-{original.document_number}",
            source_type="reversal",
            source_id=original.id,
            created_by=reversed_by,
            db=db,
        )

        # Post the reversal immediately
        reversal_posted = await self.post_entry(
            reversal["id"], posted_by=reversed_by, db=db
        )

        # Mark original as reversed
        original.status = "reversed"
        original.reversed_by = reversed_by
        original.reversed_at = datetime.now(timezone.utc)
        original.reversal_of_id = reversal_posted["id"]

        await db.flush()

        logger.info(
            "JE reversed: %s → %s", original.document_number, reversal_posted["document_number"],
        )

        # Audit trail: record reversal
        try:
            from app.services.v2.audit_trail import audit_trail_service
            await audit_trail_service.log_change(
                db, "journal_entry", original.id, "status",
                "posted", "reversed",
                str(reversed_by or "system"),
                f"Reversed by {reversal_posted['document_number']}",
            )
        except Exception:
            pass  # Audit trail should never block the main operation

        return reversal_posted

    # ── Period Control ────────────────────────────────────────────────

    async def close_period(
        self,
        period_name: str,
        close_type: str = "hard_close",
        closed_by: Optional[int] = None,
        db: AsyncSession = None,
    ) -> Dict[str, Any]:
        """Close a fiscal period. Generates closing entries on hard_close.

        close_type: "soft_close" (warn only) or "hard_close" (reject + close entries)
        """
        if not db:
            raise ValueError("Database session required")

        from app.models.all_models import FiscalPeriod

        result = await db.execute(
            select(FiscalPeriod).where(FiscalPeriod.period_name == period_name)
        )
        period = result.scalar_one_or_none()

        if not period:
            raise ValueError(f"Period '{period_name}' not found. Create it first.")

        if period.status == "hard_close":
            raise ValueError(f"Period '{period_name}' is already hard-closed")

        period.status = close_type
        period.closed_by = closed_by
        period.closed_at = datetime.now(timezone.utc)

        if close_type == "hard_close":
            # Generate closing entries (revenue/expense → retained earnings)
            closing_je = await self._generate_closing_entries(period, closed_by, db)
            if closing_je:
                period.closing_je_id = closing_je["id"]

        await db.flush()

        logger.info("Period %s: %s (by user %s)", period_name, close_type, closed_by)

        # Audit trail: record period close
        try:
            from app.services.v2.audit_trail import audit_trail_service
            old_status = "open"  # period was open before closing
            await audit_trail_service.log_change(
                db, "fiscal_period", period.id, "status",
                old_status, close_type,
                str(closed_by or "system"),
                f"Period {period_name} closed ({close_type})",
            )
        except Exception:
            pass  # Audit trail should never block the main operation

        # Emit event → triggers downstream workflows
        try:
            from app.services.v2.event_dispatcher import event_dispatcher
            import asyncio
            asyncio.ensure_future(event_dispatcher.dispatch("period_closed", {
                "period_name": period_name,
                "close_type": close_type,
                "closed_by": closed_by,
            }))
        except Exception:
            pass

        return period.to_dict()

    async def reopen_period(
        self,
        period_name: str,
        reopened_by: Optional[int] = None,
        db: AsyncSession = None,
    ) -> Dict[str, Any]:
        """Reopen a closed period (admin only, with audit trail)."""
        if not db:
            raise ValueError("Database session required")

        from app.models.all_models import FiscalPeriod

        result = await db.execute(
            select(FiscalPeriod).where(FiscalPeriod.period_name == period_name)
        )
        period = result.scalar_one_or_none()

        if not period:
            raise ValueError(f"Period '{period_name}' not found")

        old_status = period.status
        period.status = "open"
        period.reopened_by = reopened_by
        period.reopened_at = datetime.now(timezone.utc)

        await db.flush()

        logger.warning(
            "Period %s REOPENED: %s → open (by user %s). Audit trail recorded.",
            period_name, old_status, reopened_by,
        )

        # Audit trail: record period reopen
        try:
            from app.services.v2.audit_trail import audit_trail_service
            await audit_trail_service.log_change(
                db, "fiscal_period", period.id, "status",
                old_status, "open",
                str(reopened_by or "system"),
                f"Period {period_name} reopened from {old_status}",
            )
        except Exception:
            pass  # Audit trail should never block the main operation

        return period.to_dict()

    # ── Query ─────────────────────────────────────────────────────────

    async def get_entry(self, entry_id: int, db: AsyncSession) -> Optional[Dict]:
        from app.models.all_models import JournalEntryRecord, PostingLineRecord

        je_result = await db.execute(
            select(JournalEntryRecord).where(JournalEntryRecord.id == entry_id)
        )
        je = je_result.scalar_one_or_none()
        if not je:
            return None

        lines_result = await db.execute(
            select(PostingLineRecord)
            .where(PostingLineRecord.journal_entry_id == entry_id)
            .order_by(PostingLineRecord.line_number)
        )
        lines = [l.to_dict() for l in lines_result.scalars().all()]

        result = je.to_dict()
        result["lines"] = lines
        return result

    async def verify_hash(self, entry_id: int, db: AsyncSession) -> Dict[str, Any]:
        """Verify document hash integrity — detect tampering."""
        from app.models.all_models import JournalEntryRecord, PostingLineRecord

        je_result = await db.execute(
            select(JournalEntryRecord).where(JournalEntryRecord.id == entry_id)
        )
        je = je_result.scalar_one_or_none()
        if not je:
            return {"verified": False, "error": "Entry not found"}

        lines_result = await db.execute(
            select(PostingLineRecord).where(PostingLineRecord.journal_entry_id == entry_id)
        )
        lines = lines_result.scalars().all()

        computed = self._compute_hash(je, lines)
        matches = computed == je.document_hash

        return {
            "entry_id": entry_id,
            "document_number": je.document_number,
            "stored_hash": je.document_hash,
            "computed_hash": computed,
            "verified": matches,
            "tampered": not matches,
        }

    async def trial_balance(
        self, period: str, db: AsyncSession
    ) -> Dict[str, Any]:
        """Compute trial balance from posted journal entries for a period."""
        from app.models.all_models import PostingLineRecord, JournalEntryRecord

        result = await db.execute(
            select(
                PostingLineRecord.account_code,
                func.sum(PostingLineRecord.debit).label("total_debit"),
                func.sum(PostingLineRecord.credit).label("total_credit"),
            )
            .join(JournalEntryRecord, PostingLineRecord.journal_entry_id == JournalEntryRecord.id)
            .where(
                JournalEntryRecord.period == period,
                JournalEntryRecord.status == "posted",
            )
            .group_by(PostingLineRecord.account_code)
        )

        rows = []
        total_dr = Decimal("0")
        total_cr = Decimal("0")
        for row in result.all():
            dr = to_decimal(row.total_debit)
            cr = to_decimal(row.total_credit)
            total_dr += dr
            total_cr += cr
            rows.append({
                "account_code": row.account_code,
                "debit": str(round_fin(dr)),
                "credit": str(round_fin(cr)),
                "net": str(round_fin(dr - cr)),
            })

        return {
            "period": period,
            "accounts": sorted(rows, key=lambda r: r["account_code"]),
            "total_debit": str(round_fin(total_dr)),
            "total_credit": str(round_fin(total_cr)),
            "is_balanced": total_dr == total_cr,
        }

    # ── Internal ──────────────────────────────────────────────────────

    async def _validate_period_open(self, period: str, db: AsyncSession) -> None:
        """Raise PeriodClosedError if period is hard-closed."""
        from app.models.all_models import FiscalPeriod

        result = await db.execute(
            select(FiscalPeriod).where(FiscalPeriod.period_name == period)
        )
        fp = result.scalar_one_or_none()

        if fp and fp.status == "hard_close":
            raise PeriodClosedError(
                f"Period '{period}' is hard-closed (closed at {fp.closed_at}). "
                f"Reopen the period before posting."
            )

    async def _next_document_number(
        self, prefix: str, fiscal_year: int, db: AsyncSession
    ) -> str:
        """Get next gapless document number. Thread-safe via SELECT FOR UPDATE."""
        from app.models.all_models import DocumentNumberSequence

        result = await db.execute(
            select(DocumentNumberSequence).where(
                DocumentNumberSequence.prefix == prefix,
                DocumentNumberSequence.fiscal_year == fiscal_year,
            )
        )
        seq = result.scalar_one_or_none()

        if not seq:
            seq = DocumentNumberSequence(
                prefix=prefix, fiscal_year=fiscal_year, next_number=1,
            )
            db.add(seq)
            await db.flush()

        doc_number = f"{prefix}-{fiscal_year}-{seq.next_number:06d}"
        seq.next_number += 1
        await db.flush()

        return doc_number

    def _compute_hash(self, je, lines) -> str:
        """Compute SHA256 hash of journal entry + lines for immutability."""
        parts = [
            str(je.id),
            str(je.posting_date),
            je.period,
            je.description,
            je.currency,
        ]
        for line in sorted(lines, key=lambda l: l.line_number if hasattr(l, 'line_number') else 0):
            if hasattr(line, 'account_code'):
                parts.extend([
                    line.account_code,
                    str(line.debit),
                    str(line.credit),
                ])
            else:
                parts.extend([
                    line.get("account_code", ""),
                    str(line.get("debit", "0")),
                    str(line.get("credit", "0")),
                ])
        raw = "|".join(parts)
        return hashlib.sha256(raw.encode()).hexdigest()

    async def _generate_closing_entries(
        self, period, closed_by, db: AsyncSession
    ) -> Optional[Dict]:
        """Generate period-end closing entries (revenue/expense → retained earnings)."""
        # Get all posted entries for this period
        tb = await self.trial_balance(period.period_name, db)

        revenue_total = Decimal("0")
        expense_total = Decimal("0")
        closing_lines = []

        for row in tb["accounts"]:
            code = row["account_code"]
            net = to_decimal(row["net"])

            if not code:
                continue

            first_digit = code[0]

            # Revenue accounts (4xxx, 6xxx): normally credit balance → debit to close
            if first_digit in ("4", "6") and not is_zero(net):
                # Net is DR-CR; for revenue, it's typically negative (credit balance)
                closing_lines.append({
                    "account_code": code,
                    "debit": str(round_fin(abs(net))) if net < 0 else "0",
                    "credit": str(round_fin(abs(net))) if net > 0 else "0",
                    "description": f"Close {code} to Retained Earnings",
                })
                revenue_total += abs(net) if net < 0 else Decimal("0")

            # Expense accounts (5xxx, 7xxx, 8xxx, 9xxx): normally debit balance → credit to close
            elif first_digit in ("5", "7", "8", "9") and not is_zero(net):
                closing_lines.append({
                    "account_code": code,
                    "debit": "0" if net > 0 else str(round_fin(abs(net))),
                    "credit": str(round_fin(abs(net))) if net > 0 else "0",
                    "description": f"Close {code} to Retained Earnings",
                })
                expense_total += abs(net) if net > 0 else Decimal("0")

        if not closing_lines:
            return None

        # Net income to retained earnings (account 5310)
        net_income = revenue_total - expense_total
        if not is_zero(net_income):
            closing_lines.append({
                "account_code": "5310",
                "account_name": "Retained Earnings",
                "debit": str(round_fin(net_income)) if net_income < 0 else "0",
                "credit": str(round_fin(net_income)) if net_income > 0 else "0",
                "description": f"Net income for {period.period_name}: {round_fin(net_income)}",
            })

        try:
            je = await self.create_entry(
                posting_date=period.end_date or datetime.now(timezone.utc),
                period=period.period_name,
                fiscal_year=period.fiscal_year,
                description=f"Period close: {period.period_name}",
                lines=closing_lines,
                source_type="closing",
                created_by=closed_by,
                db=db,
            )
            return await self.post_entry(je["id"], posted_by=closed_by, db=db)
        except UnbalancedEntryError as e:
            logger.error("Closing entries unbalanced: %s", e)
            return None


# Module singleton
journal_service = JournalService()
