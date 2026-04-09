"""
FinAI Foundry — Ingestion-to-Journal Pipeline
================================================
The bridge between data upload and System of Record.

How real ERPs work (SAP, Oracle, NetSuite):
  1. Data arrives (Excel, bank feed, invoice, API)
  2. System PARSES into structured items (revenue, COGS, expenses)
  3. System AUTO-GENERATES balanced journal entries from parsed items
  4. Journal entries get POSTED → become the immutable GL
  5. ALL reports read from posted journal entries (not from parsed items)

This module implements step 3: converting parsed upload data into
proper double-entry journal entries via the v2 journal system.

Data Flow:
  Upload → Parse → Transaction/Revenue/COGS tables
                          ↓
             IngestionJournalPipeline.process()
                          ↓
             JournalEntry + PostingLine records (balanced, DR=CR)
                          ↓
             Auto-posted with gapless document numbers
                          ↓
             ALL reports now read from PostingLine table

Public API:
    from app.services.v2.ingestion_journal import ingestion_journal
    result = await ingestion_journal.process_dataset(dataset_id, db)
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.v2.decimal_utils import to_decimal, round_fin, is_zero, safe_divide

logger = logging.getLogger(__name__)
D = Decimal


class IngestionJournalPipeline:
    """
    Converts uploaded financial data into proper journal entries.

    For each dataset, creates journal entries from:
    1. Revenue items → DR Receivables / CR Revenue (by product)
    2. COGS items → DR COGS / CR Inventory (by product)
    3. G&A expense items → DR Expense / CR Cash/Payables (by account)
    4. Trial balance items → DR/CR entries matching TB turnovers
    5. Balance sheet items → Opening balance entries

    Each journal entry:
    - Has balanced DR = CR (enforced by journal_system)
    - Gets a gapless document number on posting
    - Is immutable after posting (SHA256 hash)
    - Links back to source dataset via source_type="upload" + source_id
    """

    # Account code mapping for auto-journaling
    # Georgian IFRS COA: receivables=13xx, payables=31xx, cash=11xx, inventory=16xx
    DEFAULT_RECEIVABLES = "1310"  # Trade Receivables
    DEFAULT_PAYABLES = "3110"     # Trade Payables
    DEFAULT_CASH = "1110"         # Cash in Bank
    DEFAULT_INVENTORY = "1610"    # Inventory / Goods

    async def process_dataset(
        self,
        dataset_id: int,
        db: AsyncSession,
        auto_post: bool = True,
        period: Optional[str] = None,
        fiscal_year: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Convert all parsed items in a dataset into journal entries.

        Args:
            dataset_id: The dataset to process
            auto_post: If True, auto-post entries after creation (assigns doc numbers)
            period: Override period (otherwise uses dataset.period)
            fiscal_year: Override fiscal year

        Returns:
            Dict with created journal entry IDs, statistics, and any errors
        """
        from app.models.all_models import (
            Dataset, Transaction, RevenueItem, COGSItem,
            GAExpenseItem, TrialBalanceItem,
        )
        from app.services.v2.journal_system import journal_service

        # Load dataset metadata
        ds = (await db.execute(
            select(Dataset).where(Dataset.id == dataset_id)
        )).scalar_one_or_none()

        if not ds:
            return {"error": f"Dataset {dataset_id} not found", "entries_created": 0}

        _period = period or ds.period or "Unknown"
        _year = fiscal_year or self._extract_year(_period)

        stats = {
            "dataset_id": dataset_id,
            "period": _period,
            "fiscal_year": _year,
            "revenue_entries": 0,
            "cogs_entries": 0,
            "expense_entries": 0,
            "tb_entries": 0,
            "total_entries_created": 0,
            "total_entries_posted": 0,
            "total_debit": D("0"),
            "total_credit": D("0"),
            "errors": [],
            "journal_entry_ids": [],
        }

        # ── 1. Revenue Journal Entries ────────────────────────────────
        rev_items = (await db.execute(
            select(RevenueItem).where(RevenueItem.dataset_id == dataset_id)
        )).scalars().all()

        if rev_items:
            try:
                je = await self._create_revenue_journal(
                    rev_items, _period, _year, dataset_id, db
                )
                if je:
                    stats["revenue_entries"] = 1
                    stats["journal_entry_ids"].append(je["id"])
                    if auto_post:
                        posted = await journal_service.post_entry(je["id"], db=db)
                        stats["total_entries_posted"] += 1
            except Exception as e:
                stats["errors"].append(f"Revenue JE failed: {e}")
                logger.error("Revenue journal creation failed: %s", e)

        # ── 2. COGS Journal Entries ───────────────────────────────────
        cogs_items = (await db.execute(
            select(COGSItem).where(COGSItem.dataset_id == dataset_id)
        )).scalars().all()

        if cogs_items:
            try:
                je = await self._create_cogs_journal(
                    cogs_items, _period, _year, dataset_id, db
                )
                if je:
                    stats["cogs_entries"] = 1
                    stats["journal_entry_ids"].append(je["id"])
                    if auto_post:
                        posted = await journal_service.post_entry(je["id"], db=db)
                        stats["total_entries_posted"] += 1
            except Exception as e:
                stats["errors"].append(f"COGS JE failed: {e}")
                logger.error("COGS journal creation failed: %s", e)

        # ── 3. G&A Expense Journal Entries ────────────────────────────
        ga_items = (await db.execute(
            select(GAExpenseItem).where(GAExpenseItem.dataset_id == dataset_id)
        )).scalars().all()

        if ga_items:
            try:
                je = await self._create_expense_journal(
                    ga_items, _period, _year, dataset_id, db
                )
                if je:
                    stats["expense_entries"] = 1
                    stats["journal_entry_ids"].append(je["id"])
                    if auto_post:
                        posted = await journal_service.post_entry(je["id"], db=db)
                        stats["total_entries_posted"] += 1
            except Exception as e:
                stats["errors"].append(f"Expense JE failed: {e}")
                logger.error("Expense journal creation failed: %s", e)

        # ── 4. Trial Balance Entries (if no revenue/cogs items) ───────
        if not rev_items and not cogs_items:
            tb_items = (await db.execute(
                select(TrialBalanceItem).where(
                    TrialBalanceItem.dataset_id == dataset_id,
                    TrialBalanceItem.hierarchy_level == 1,
                )
            )).scalars().all()

            if tb_items:
                try:
                    je = await self._create_tb_journal(
                        tb_items, _period, _year, dataset_id, db
                    )
                    if je:
                        stats["tb_entries"] = 1
                        stats["journal_entry_ids"].append(je["id"])
                        if auto_post:
                            posted = await journal_service.post_entry(je["id"], db=db)
                            stats["total_entries_posted"] += 1
                except Exception as e:
                    stats["errors"].append(f"TB JE failed: {e}")
                    logger.error("TB journal creation failed: %s", e)

        stats["total_entries_created"] = len(stats["journal_entry_ids"])

        logger.info(
            "Ingestion→Journal: dataset=%d, created=%d, posted=%d, errors=%d",
            dataset_id, stats["total_entries_created"],
            stats["total_entries_posted"], len(stats["errors"]),
        )

        return stats

    # ── Journal Creation Methods ──────────────────────────────────────

    async def _create_revenue_journal(
        self, items: List, period: str, year: int, dataset_id: int, db: AsyncSession
    ) -> Optional[Dict]:
        """Create a single JE for all revenue items: DR Receivables / CR Revenue."""
        from app.services.v2.journal_system import journal_service

        lines = []
        total_revenue = D("0")

        for item in items:
            net = to_decimal(getattr(item, 'net', 0))
            if is_zero(net):
                continue

            product = getattr(item, 'product', '') or ''
            category = getattr(item, 'category', '') or ''

            # CR Revenue account (6xxx)
            rev_account = self._get_revenue_account(category)
            lines.append({
                "account_code": rev_account,
                "account_name": f"Revenue: {product[:50]}",
                "debit": "0",
                "credit": str(round_fin(abs(net))),
                "description": f"{category} - {product}",
            })
            total_revenue += abs(net)

        if is_zero(total_revenue):
            return None

        # DR Receivables (aggregate)
        lines.insert(0, {
            "account_code": self.DEFAULT_RECEIVABLES,
            "account_name": "Trade Receivables",
            "debit": str(round_fin(total_revenue)),
            "credit": "0",
            "description": f"Revenue receivables for {period}",
        })

        return await journal_service.create_entry(
            posting_date=datetime.now(timezone.utc),
            period=period,
            fiscal_year=year,
            description=f"Revenue recognition - {period} ({len(items)} products)",
            lines=lines,
            source_type="upload",
            source_id=dataset_id,
            db=db,
        )

    async def _create_cogs_journal(
        self, items: List, period: str, year: int, dataset_id: int, db: AsyncSession
    ) -> Optional[Dict]:
        """Create JE for COGS: DR COGS / CR Inventory."""
        from app.services.v2.journal_system import journal_service

        lines = []
        total_cogs = D("0")

        for item in items:
            cogs = to_decimal(getattr(item, 'total_cogs', 0))
            if is_zero(cogs):
                continue

            product = getattr(item, 'product', '') or ''
            category = getattr(item, 'category', '') or ''

            # DR COGS account (7xxx)
            cogs_account = self._get_cogs_account(category)
            lines.append({
                "account_code": cogs_account,
                "account_name": f"COGS: {product[:50]}",
                "debit": str(round_fin(abs(cogs))),
                "credit": "0",
                "description": f"{category} - {product}",
            })
            total_cogs += abs(cogs)

        if is_zero(total_cogs):
            return None

        # CR Inventory (aggregate)
        lines.append({
            "account_code": self.DEFAULT_INVENTORY,
            "account_name": "Inventory",
            "debit": "0",
            "credit": str(round_fin(total_cogs)),
            "description": f"Inventory consumption for {period}",
        })

        return await journal_service.create_entry(
            posting_date=datetime.now(timezone.utc),
            period=period,
            fiscal_year=year,
            description=f"COGS - {period} ({len(items)} products)",
            lines=lines,
            source_type="upload",
            source_id=dataset_id,
            db=db,
        )

    async def _create_expense_journal(
        self, items: List, period: str, year: int, dataset_id: int, db: AsyncSession
    ) -> Optional[Dict]:
        """Create JE for G&A expenses: DR Expense / CR Cash."""
        from app.services.v2.journal_system import journal_service

        lines = []
        total_expense = D("0")
        _SKIP = {'FINANCE_INCOME', 'FINANCE_EXPENSE', 'TAX_EXPENSE', 'LABOUR_COSTS'}

        for item in items:
            code = getattr(item, 'account_code', '') or ''
            if code in _SKIP:
                continue

            amt = to_decimal(getattr(item, 'amount', 0))
            if is_zero(amt):
                continue

            name = getattr(item, 'account_name', '') or code
            lines.append({
                "account_code": code if code[0].isdigit() else "7300",
                "account_name": name[:100],
                "debit": str(round_fin(abs(amt))),
                "credit": "0",
                "description": name[:200],
            })
            total_expense += abs(amt)

        if is_zero(total_expense):
            return None

        # CR Cash/Payables
        lines.append({
            "account_code": self.DEFAULT_PAYABLES,
            "account_name": "Accounts Payable",
            "debit": "0",
            "credit": str(round_fin(total_expense)),
            "description": f"Expense payables for {period}",
        })

        return await journal_service.create_entry(
            posting_date=datetime.now(timezone.utc),
            period=period,
            fiscal_year=year,
            description=f"Operating expenses - {period} ({len(items)} items)",
            lines=lines,
            source_type="upload",
            source_id=dataset_id,
            db=db,
        )

    async def _create_tb_journal(
        self, items: List, period: str, year: int, dataset_id: int, db: AsyncSession
    ) -> Optional[Dict]:
        """Create JE from Trial Balance turnovers (when no revenue/COGS detail)."""
        from app.services.v2.journal_system import journal_service

        lines = []
        total_dr = D("0")
        total_cr = D("0")

        for item in items:
            code = getattr(item, 'account_code', '') or ''
            if not code or not code[0].isdigit():
                continue

            dr = to_decimal(getattr(item, 'turnover_debit', 0))
            cr = to_decimal(getattr(item, 'turnover_credit', 0))

            if is_zero(dr) and is_zero(cr):
                continue

            name = getattr(item, 'account_name', '') or code

            if not is_zero(dr):
                lines.append({
                    "account_code": code,
                    "account_name": name[:100],
                    "debit": str(round_fin(dr)),
                    "credit": "0",
                    "description": f"TB turnover: {name}",
                })
                total_dr += dr

            if not is_zero(cr):
                lines.append({
                    "account_code": code,
                    "account_name": name[:100],
                    "debit": "0",
                    "credit": str(round_fin(cr)),
                    "description": f"TB turnover: {name}",
                })
                total_cr += cr

        if not lines:
            return None

        # Balance check — TB should already be balanced
        diff = total_dr - total_cr
        if not is_zero(diff):
            # Add suspense account to balance
            if diff > 0:
                lines.append({
                    "account_code": "9999",
                    "account_name": "Suspense - TB Imbalance",
                    "debit": "0",
                    "credit": str(round_fin(abs(diff))),
                    "description": f"TB imbalance adjustment: {round_fin(diff)}",
                })
            else:
                lines.append({
                    "account_code": "9999",
                    "account_name": "Suspense - TB Imbalance",
                    "debit": str(round_fin(abs(diff))),
                    "credit": "0",
                    "description": f"TB imbalance adjustment: {round_fin(diff)}",
                })
            logger.warning("TB journal has imbalance of %s — suspense account used", round_fin(diff))

        return await journal_service.create_entry(
            posting_date=datetime.now(timezone.utc),
            period=period,
            fiscal_year=year,
            description=f"Trial Balance import - {period} ({len(items)} accounts)",
            lines=lines,
            source_type="upload_tb",
            source_id=dataset_id,
            db=db,
        )

    # ── Helpers ───────────────────────────────────────────────────────

    def _get_revenue_account(self, category: str) -> str:
        """Map revenue category to account code."""
        if "wholesale" in category.lower():
            return "6110"  # Wholesale Revenue
        elif "retail" in category.lower():
            return "6120"  # Retail Revenue
        return "6100"  # General Revenue

    def _get_cogs_account(self, category: str) -> str:
        """Map COGS category to account code."""
        if "wholesale" in category.lower():
            return "7110"  # Wholesale COGS
        elif "retail" in category.lower():
            return "7120"  # Retail COGS
        return "7100"  # General COGS

    def _extract_year(self, period: str) -> int:
        """Extract fiscal year from period string."""
        import re
        match = re.search(r'20\d{2}', period)
        return int(match.group()) if match else datetime.now().year


# Module singleton
ingestion_journal = IngestionJournalPipeline()
