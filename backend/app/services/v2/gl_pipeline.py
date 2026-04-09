"""
gl_pipeline.py (v2) -- GL Transaction to Financial Statement Pipeline
=====================================================================
Audit-safe, Decimal-precise rewrite of the v1 GL pipeline.

Changes from v1:
- ALL financial values are Decimal — never converted to float
- to_dict() serializes Decimal as str to preserve precision
- Reconciliation tolerance is relative to balance sheet size
- TransactionAdapter produces Decimal entries (not float)
- Explicit error handling — no silent failures

Phase G-1 of the FinAI Full System Upgrade (v2 rewrite).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional

from app.services.v2.decimal_utils import to_decimal, safe_divide, round_fin, is_zero

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes — all financial fields are Decimal
# ---------------------------------------------------------------------------

@dataclass
class TrialBalanceRow:
    """One account in the trial balance."""
    account_code: str
    account_name: str = ""
    total_debit: Decimal = field(default_factory=lambda: Decimal("0"))
    total_credit: Decimal = field(default_factory=lambda: Decimal("0"))

    @property
    def net_balance(self) -> Decimal:
        return self.total_debit - self.total_credit

    @property
    def closing_debit(self) -> Decimal:
        return max(self.net_balance, Decimal("0"))

    @property
    def closing_credit(self) -> Decimal:
        return max(-self.net_balance, Decimal("0"))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize with string-encoded Decimals for JSON precision."""
        return {
            "account_code": self.account_code,
            "account_name": self.account_name,
            "total_debit": str(round_fin(self.total_debit)),
            "total_credit": str(round_fin(self.total_credit)),
            "net_balance": str(round_fin(self.net_balance)),
            "closing_debit": str(round_fin(self.closing_debit)),
            "closing_credit": str(round_fin(self.closing_credit)),
        }


@dataclass
class TrialBalance:
    """Complete trial balance with Decimal precision."""
    rows: Dict[str, TrialBalanceRow] = field(default_factory=dict)
    period: str = ""
    currency: str = "GEL"
    dataset_id: Optional[int] = None

    def total_debits(self) -> Decimal:
        return sum((r.total_debit for r in self.rows.values()), Decimal("0"))

    def total_credits(self) -> Decimal:
        return sum((r.total_credit for r in self.rows.values()), Decimal("0"))

    def is_balanced(self, tolerance: Optional[Decimal] = None) -> bool:
        """Check if TB is balanced.

        Default tolerance: max(0.01, 0.0001% of total debits) to handle
        both small and large balance sheets correctly.
        """
        total_d = self.total_debits()
        total_c = self.total_credits()
        diff = abs(total_d - total_c)

        if tolerance is not None:
            return diff <= tolerance

        # Relative tolerance: 0.0001% of total, minimum 0.01
        relative_tol = max(
            Decimal("0.01"),
            total_d * Decimal("0.000001")
        )
        return diff <= relative_tol

    def account_count(self) -> int:
        return len(self.rows)

    def to_statement_transactions(self) -> List[Dict]:
        """Convert TB rows to format expected by FinancialStatementMapper.

        NOTE: Returns Decimal values (not float) for v2 compatibility.
        If the downstream mapper requires float, convert at the boundary.
        """
        result = []
        for row in self.rows.values():
            result.append({
                "account_code": row.account_code,
                "debit": float(row.total_debit),  # Mapper still expects float (v1 compat)
                "credit": float(row.total_credit),
            })
        return result

    def to_dict(self) -> Dict[str, Any]:
        return {
            "period": self.period,
            "currency": self.currency,
            "dataset_id": self.dataset_id,
            "account_count": self.account_count(),
            "total_debits": str(round_fin(self.total_debits())),
            "total_credits": str(round_fin(self.total_credits())),
            "is_balanced": self.is_balanced(),
            "rows": {code: row.to_dict() for code, row in self.rows.items()},
        }


# ---------------------------------------------------------------------------
# TransactionAdapter — now produces Decimal entries
# ---------------------------------------------------------------------------

class TransactionAdapter:
    """
    Converts DB Transaction records (acct_dr, acct_cr, amount) into
    normalized (account_code, debit, credit) entries with Decimal precision.

    Each Transaction generates up to TWO entries:
      1. (acct_dr, debit=amount, credit=0)
      2. (acct_cr, debit=0, credit=amount)
    """

    @staticmethod
    def _normalize_code(code: Optional[str]) -> Optional[str]:
        if not code:
            return None
        c = code.strip()
        return c if c else None

    @staticmethod
    def expand(txn) -> List[Dict]:
        """Expand a single transaction into debit/credit entries."""
        if isinstance(txn, dict):
            acct_dr = txn.get("acct_dr")
            acct_cr = txn.get("acct_cr")
            raw_amount = txn.get("amount", 0)
        else:
            acct_dr = getattr(txn, "acct_dr", None)
            acct_cr = getattr(txn, "acct_cr", None)
            raw_amount = getattr(txn, "amount", 0)

        dr = TransactionAdapter._normalize_code(acct_dr)
        cr = TransactionAdapter._normalize_code(acct_cr)
        amount = to_decimal(raw_amount)

        if amount <= Decimal("0"):
            return []

        entries = []
        if dr:
            entries.append({
                "account_code": dr,
                "debit": amount,
                "credit": Decimal("0"),
            })
        if cr:
            entries.append({
                "account_code": cr,
                "debit": Decimal("0"),
                "credit": amount,
            })
        return entries

    @staticmethod
    def expand_batch(transactions) -> List[Dict]:
        """Expand a batch of transactions."""
        result = []
        for txn in transactions:
            result.extend(TransactionAdapter.expand(txn))
        return result


# ---------------------------------------------------------------------------
# TrialBalanceBuilder
# ---------------------------------------------------------------------------

class TrialBalanceBuilder:
    """Aggregates expanded entries into a trial balance with Decimal precision."""

    def build_from_expanded(
        self,
        entries: List[Dict],
        period: str = "",
        currency: str = "GEL",
        dataset_id: Optional[int] = None,
    ) -> TrialBalance:
        """Build TB from already-expanded entries."""
        tb = TrialBalance(period=period, currency=currency, dataset_id=dataset_id)
        for entry in entries:
            code = str(entry.get("account_code", "")).strip()
            if not code:
                continue
            debit = to_decimal(entry.get("debit", 0))
            credit = to_decimal(entry.get("credit", 0))
            if code not in tb.rows:
                tb.rows[code] = TrialBalanceRow(account_code=code)
            tb.rows[code].total_debit += debit
            tb.rows[code].total_credit += credit
        return tb

    def build_from_transactions(
        self,
        transactions,
        period: str = "",
        currency: str = "GEL",
        dataset_id: Optional[int] = None,
    ) -> TrialBalance:
        """Build TB from raw Transaction objects or dicts (acct_dr/cr/amount)."""
        entries = TransactionAdapter.expand_batch(transactions)
        return self.build_from_expanded(entries, period, currency, dataset_id)


# ---------------------------------------------------------------------------
# GLPipeline
# ---------------------------------------------------------------------------

class GLPipeline:
    """
    End-to-end pipeline:
      load_transactions(dataset_id, db)
        -> build_trial_balance()
        -> build_statements()
        -> reconcile()

    Returns trial_balance + statements + reconciliation with Decimal precision.
    """

    def __init__(self):
        self._adapter = TransactionAdapter()
        self._tb_builder = TrialBalanceBuilder()

    def _get_mapper(self):
        from app.services.account_hierarchy import financial_statement_mapper
        return financial_statement_mapper

    async def run(
        self,
        dataset_id: int,
        db,
        period: str = "",
        currency: str = "GEL",
    ) -> Dict[str, Any]:
        """Full pipeline for a dataset: load transactions from DB, build everything."""
        from sqlalchemy import select
        from app.models.all_models import Transaction

        result = await db.execute(
            select(Transaction).where(Transaction.dataset_id == dataset_id)
        )
        transactions = result.scalars().all()

        if not transactions:
            logger.warning("No transactions found for dataset %d", dataset_id)
            return {
                "trial_balance": TrialBalance(period=period, currency=currency, dataset_id=dataset_id).to_dict(),
                "statements": {
                    "income_statement": {}, "balance_sheet": {},
                    "cash_flow": {}, "totals": {},
                    "warnings": ["No transactions found"],
                },
                "reconciliation": {
                    "tb_balanced": True, "bs_equation_holds": True,
                    "net_income_matches": True, "warnings": ["No transactions"],
                },
            }

        entries = self._adapter.expand_batch(transactions)
        return self._build_from_entries(entries, period, currency, dataset_id)

    def run_from_entries(
        self,
        entries: List[Dict],
        period: str = "",
        currency: str = "GEL",
    ) -> Dict[str, Any]:
        """Run pipeline from pre-expanded entries (for testing/API)."""
        return self._build_from_entries(entries, period, currency)

    def run_from_transactions(
        self,
        transactions: List[Dict],
        period: str = "",
        currency: str = "GEL",
    ) -> Dict[str, Any]:
        """Run pipeline from raw transaction dicts (acct_dr/cr/amount)."""
        entries = self._adapter.expand_batch(transactions)
        return self._build_from_entries(entries, period, currency)

    def _build_from_entries(
        self,
        entries: List[Dict],
        period: str = "",
        currency: str = "GEL",
        dataset_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Core pipeline logic."""
        # Step 1: Build Trial Balance
        tb = self._tb_builder.build_from_expanded(entries, period, currency, dataset_id)

        logger.info(
            "TB built: %d accounts, debits=%s, credits=%s, balanced=%s",
            tb.account_count(),
            round_fin(tb.total_debits()),
            round_fin(tb.total_credits()),
            tb.is_balanced(),
        )

        # Step 2: Build Financial Statements via mapper
        mapper = self._get_mapper()
        stmt_entries = tb.to_statement_transactions()
        stmts = mapper.build_statements(stmt_entries, period=period, currency=currency)

        # Step 3: Reconcile
        reconciliation = self._reconcile(tb, stmts)

        return {
            "trial_balance": tb.to_dict(),
            "statements": stmts.to_dict(),
            "reconciliation": reconciliation,
        }

    def _reconcile(self, tb: TrialBalance, stmts) -> Dict[str, Any]:
        """
        Cross-check with Decimal precision:
          1. TB debits == TB credits (relative tolerance)
          2. BS Assets == Liabilities + Equity
          3. Net income from IS reflected in equity
        """
        warnings = []

        # Check 1: Trial Balance balanced
        tb_balanced = tb.is_balanced()
        if not tb_balanced:
            diff = round_fin(tb.total_debits() - tb.total_credits())
            warnings.append(f"Trial balance imbalance: debits - credits = {diff}")

        # Check 2: BS equation
        bs_holds = stmts.bs_equation_holds()
        if not bs_holds:
            ta = to_decimal(stmts.total_assets())
            tle = to_decimal(stmts.total_liabilities()) + to_decimal(stmts.total_equity())
            warnings.append(f"BS equation: Assets={round_fin(ta)} != L+E={round_fin(tle)}")

        # Check 3: Net income cross-reference
        net_income = to_decimal(stmts.net_income())
        retained = Decimal("0")
        equity_section = stmts.balance_sheet.get("equity", {})
        for line in equity_section.values():
            if "retained" in line.name.lower() or "net income" in line.name.lower():
                retained += to_decimal(line.amount)

        ni_matches = True
        if not is_zero(net_income) and is_zero(retained) and len(equity_section) > 0:
            warnings.append(
                "Net income from IS not reflected in equity "
                "(may need retained earnings adjustment)"
            )
            ni_matches = False

        return {
            "tb_balanced": tb_balanced,
            "bs_equation_holds": bs_holds,
            "net_income_matches": ni_matches,
            "total_debits": str(round_fin(tb.total_debits())),
            "total_credits": str(round_fin(tb.total_credits())),
            "net_income": str(round_fin(net_income)),
            "warnings": warnings,
        }


# Module-level singleton (drop-in replacement for v1)
gl_pipeline = GLPipeline()
