"""
FinAI v2 Lineage Service — End-to-end drill-down from any report line.
======================================================================
Fixes stress test finding: "Drill-down breaks at Step 2. No way to click
a P&L line item and see constituent journal entries."

Provides:
- P&L line code → underlying transactions
- Account code → all transactions affecting it
- Full lineage chain: Report → P&L Line → Transaction → Source Document

Public API:
    from app.services.v2.lineage_service import lineage_service
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.v2.decimal_utils import to_decimal, round_fin

logger = logging.getLogger(__name__)


class LineageService:
    """End-to-end lineage from report lines to source transactions."""

    async def get_transactions_for_pl_line(
        self,
        pl_line_code: str,
        dataset_id: int,
        db: AsyncSession,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """Get all transactions that aggregate into a P&L line.

        Args:
            pl_line_code: P&L row code (e.g., "REV.W.P", "COGS.W.D", "GA")
            dataset_id: Dataset to search in
            limit: Max transactions to return

        Returns:
            Dict with transactions, total, and account codes involved.
        """
        from app.models.all_models import Transaction, RevenueItem, COGSItem, GAExpenseItem

        # Map P&L codes to account patterns and item types
        account_patterns = self._resolve_pl_code_to_accounts(pl_line_code)

        if not account_patterns:
            return {
                "pl_line_code": pl_line_code,
                "error": f"Unknown P&L line code: {pl_line_code}",
                "transactions": [],
            }

        # Query transactions matching the account patterns
        q = select(Transaction).where(Transaction.dataset_id == dataset_id)

        filters = []
        for pattern in account_patterns:
            filters.append(Transaction.acct_dr.like(f"{pattern}%"))
            filters.append(Transaction.acct_cr.like(f"{pattern}%"))

        q = q.where(or_(*filters)).limit(limit)
        result = await db.execute(q)
        txns = result.scalars().all()

        # Also get specific revenue/COGS items for product detail
        items = []
        if pl_line_code.startswith("REV"):
            category = self._pl_code_to_category(pl_line_code, "revenue")
            if category:
                item_result = await db.execute(
                    select(RevenueItem).where(
                        RevenueItem.dataset_id == dataset_id,
                        RevenueItem.category == category,
                    )
                )
                items = [{"type": "revenue", "product": r.product, "net": str(to_decimal(r.net)),
                           "category": r.category, "id": r.id}
                          for r in item_result.scalars().all()]

        elif pl_line_code.startswith("COGS"):
            category = self._pl_code_to_category(pl_line_code, "cogs")
            if category:
                item_result = await db.execute(
                    select(COGSItem).where(
                        COGSItem.dataset_id == dataset_id,
                        COGSItem.category == category,
                    )
                )
                items = [{"type": "cogs", "product": c.product,
                           "total_cogs": str(to_decimal(c.total_cogs)),
                           "category": c.category, "id": c.id}
                          for c in item_result.scalars().all()]

        return {
            "pl_line_code": pl_line_code,
            "dataset_id": dataset_id,
            "account_patterns": account_patterns,
            "transaction_count": len(txns),
            "transactions": [
                {
                    "id": t.id,
                    "date": str(t.date) if t.date else None,
                    "acct_dr": t.acct_dr,
                    "acct_cr": t.acct_cr,
                    "amount": str(to_decimal(t.amount)),
                    "counterparty": t.counterparty,
                    "description": t.recorder or "",
                }
                for t in txns
            ],
            "source_items": items,
            "lineage_chain": f"Report → {pl_line_code} → {len(account_patterns)} accounts → {len(txns)} transactions",
        }

    async def get_transactions_for_account(
        self,
        account_code: str,
        dataset_id: int,
        db: AsyncSession,
        limit: int = 200,
    ) -> Dict[str, Any]:
        """Get all transactions affecting a specific account code."""
        from app.models.all_models import Transaction

        q = select(Transaction).where(
            Transaction.dataset_id == dataset_id,
            or_(
                Transaction.acct_dr.like(f"{account_code}%"),
                Transaction.acct_cr.like(f"{account_code}%"),
            ),
        ).limit(limit)

        result = await db.execute(q)
        txns = result.scalars().all()

        total_dr = Decimal("0")
        total_cr = Decimal("0")
        transactions = []
        for t in txns:
            amt = to_decimal(t.amount)
            if t.acct_dr and t.acct_dr.startswith(account_code):
                total_dr += amt
            if t.acct_cr and t.acct_cr.startswith(account_code):
                total_cr += amt
            transactions.append({
                "id": t.id,
                "date": str(t.date) if t.date else None,
                "acct_dr": t.acct_dr,
                "acct_cr": t.acct_cr,
                "amount": str(round_fin(amt)),
                "counterparty": t.counterparty,
                "type": t.type,
            })

        return {
            "account_code": account_code,
            "dataset_id": dataset_id,
            "transaction_count": len(transactions),
            "total_debit": str(round_fin(total_dr)),
            "total_credit": str(round_fin(total_cr)),
            "net_balance": str(round_fin(total_dr - total_cr)),
            "transactions": transactions,
        }

    async def get_full_lineage(
        self,
        entity_type: str,
        entity_id: int,
        dataset_id: int,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Get complete lineage for any entity (revenue item, COGS item, etc.)."""
        from app.models.all_models import DataLineage

        result = await db.execute(
            select(DataLineage).where(
                DataLineage.entity_type == entity_type,
                DataLineage.entity_id == entity_id,
                DataLineage.dataset_id == dataset_id,
            )
        )
        records = result.scalars().all()

        return {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "dataset_id": dataset_id,
            "lineage_records": [
                {
                    "id": r.id,
                    "source_file": r.source_file,
                    "source_sheet": r.source_sheet,
                    "source_row": r.source_row,
                    "classification_rule": r.classification_rule,
                    "transform_chain": r.transform_chain,
                }
                for r in records
            ],
            "record_count": len(records),
        }

    # ── Internal helpers ──────────────────────────────────────────────

    def _resolve_pl_code_to_accounts(self, pl_code: str) -> List[str]:
        """Map a P&L line code to account code patterns."""
        # Georgian IFRS account mapping
        _PL_TO_ACCOUNTS = {
            # Revenue (class 6)
            "REV": ["6"],
            "REV.W": ["6110"],
            "REV.W.P": ["6110"],
            "REV.W.D": ["6110"],
            "REV.W.B": ["6110"],
            "REV.W.CNG": ["6110"],
            "REV.W.LPG": ["6110"],
            "REV.R": ["6120", "6110"],
            "REV.R.P": ["6120", "6110"],
            "REV.R.D": ["6120", "6110"],
            # COGS (class 7 + 1610)
            "COGS": ["7", "1610"],
            "COGS.W": ["7110", "1610"],
            "COGS.R": ["7110", "1610"],
            # G&A (class 73, 74)
            "GA": ["73", "74"],
            # D&A
            "DA": ["7410", "7420"],
            # EBITDA, EBIT, EBT (computed — no direct account)
            "EBITDA": [],
            "EBIT": [],
            "EBT": [],
            # Finance
            "FIN": ["75", "76", "8110", "8220"],
            # Tax
            "TAX": ["77", "92"],
            # Net Profit (computed)
            "NP": [],
        }
        return _PL_TO_ACCOUNTS.get(pl_code, [])

    def _pl_code_to_category(self, pl_code: str, source: str) -> Optional[str]:
        """Map P&L code to RevenueItem/COGSItem category name."""
        _REV_CATEGORIES = {
            "REV.W.P": "Revenue Whsale Petrol",
            "REV.W.D": "Revenue Whsale Diesel",
            "REV.W.B": "Revenue Whsale Bitumen",
            "REV.W.CNG": "Revenue Whsale CNG",
            "REV.W.LPG": "Revenue Whsale LPG",
            "REV.R.P": "Revenue Retial Petrol",
            "REV.R.D": "Revenue Retial Diesel",
            "REV.R.CNG": "Revenue Retial CNG",
            "REV.R.LPG": "Revenue Retial LPG",
        }
        _COGS_CATEGORIES = {
            "COGS.W.P": "COGS Whsale Petrol",
            "COGS.W.D": "COGS Whsale Diesel",
            "COGS.W.B": "COGS Whsale Bitumen",
            "COGS.R.P": "COGS Retial Petrol",
            "COGS.R.D": "COGS Retial Diesel",
        }
        if source == "revenue":
            return _REV_CATEGORIES.get(pl_code)
        return _COGS_CATEGORIES.get(pl_code)


# Module singleton
lineage_service = LineageService()
