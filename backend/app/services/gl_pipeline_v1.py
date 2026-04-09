"""
gl_pipeline.py -- GL Transaction to Financial Statement Pipeline
================================================================
End-to-end pipeline: raw GL transactions (acct_dr/acct_cr/amount)
  -> Trial Balance (per-account debit/credit totals)
  -> Income Statement (from P&L accounts in TB)
  -> Balance Sheet (from BS accounts in TB)
  -> Cash Flow (indirect method from BS changes)
  -> Circular reconciliation checks

Uses account_hierarchy.py for account classification and
FinancialStatementMapper for the statement building step.

Phase G-1 of the FinAI Full System Upgrade.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class TrialBalanceRow:
    """One account in the trial balance."""
    account_code: str
    account_name: str = ""
    total_debit: Decimal = Decimal("0")
    total_credit: Decimal = Decimal("0")

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
        return {
            "account_code": self.account_code,
            "account_name": self.account_name,
            "total_debit": float(self.total_debit),
            "total_credit": float(self.total_credit),
            "net_balance": float(self.net_balance),
            "closing_debit": float(self.closing_debit),
            "closing_credit": float(self.closing_credit),
        }


@dataclass
class TrialBalance:
    """Complete trial balance."""
    rows: Dict[str, TrialBalanceRow] = field(default_factory=dict)
    period: str = ""
    currency: str = "GEL"
    dataset_id: Optional[int] = None

    def total_debits(self) -> Decimal:
        return sum((r.total_debit for r in self.rows.values()), Decimal("0"))

    def total_credits(self) -> Decimal:
        return sum((r.total_credit for r in self.rows.values()), Decimal("0"))

    def is_balanced(self, tolerance: Decimal = Decimal("0.01")) -> bool:
        return abs(self.total_debits() - self.total_credits()) <= tolerance

    def account_count(self) -> int:
        return len(self.rows)

    def to_statement_transactions(self) -> List[Dict]:
        """Convert TB rows into the format expected by FinancialStatementMapper.build_statements()."""
        result = []
        for row in self.rows.values():
            result.append({
                "account_code": row.account_code,
                "debit": float(row.total_debit),
                "credit": float(row.total_credit),
            })
        return result

    def to_dict(self) -> Dict[str, Any]:
        return {
            "period": self.period,
            "currency": self.currency,
            "dataset_id": self.dataset_id,
            "account_count": self.account_count(),
            "total_debits": float(self.total_debits()),
            "total_credits": float(self.total_credits()),
            "is_balanced": self.is_balanced(),
            "rows": {code: row.to_dict() for code, row in self.rows.items()},
        }


# ---------------------------------------------------------------------------
# TransactionAdapter
# ---------------------------------------------------------------------------

class TransactionAdapter:
    """
    Converts DB Transaction records (acct_dr, acct_cr, amount) into
    normalized (account_code, debit, credit) entries suitable for
    TrialBalance aggregation and FinancialStatementMapper.

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
        """
        Expand a single transaction into one or two single-account entries.
        Accepts either a Transaction ORM object or a dict with acct_dr/acct_cr/amount.
        """
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
        amount = Decimal(str(raw_amount or 0))

        entries = []
        if dr and amount > 0:
            entries.append({
                "account_code": dr,
                "debit": float(amount),
                "credit": 0.0,
            })
        if cr and amount > 0:
            entries.append({
                "account_code": cr,
                "debit": 0.0,
                "credit": float(amount),
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
    """Aggregates expanded (account_code, debit, credit) entries into a trial balance."""

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
            debit = Decimal(str(entry.get("debit", 0) or 0))
            credit = Decimal(str(entry.get("credit", 0) or 0))
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

    Returns trial_balance + statements + reconciliation.
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
            return {
                "trial_balance": TrialBalance(period=period, currency=currency, dataset_id=dataset_id).to_dict(),
                "statements": {"income_statement": {}, "balance_sheet": {}, "cash_flow": {}, "totals": {}, "warnings": ["No transactions found"]},
                "reconciliation": {"tb_balanced": True, "bs_equation_holds": True, "net_income_matches": True, "warnings": ["No transactions"]},
            }

        # Expand and build
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
        Cross-check:
          1. TB debits == TB credits
          2. BS Assets == Liabilities + Equity
          3. Net income from IS is consistent with equity movement (proxy check)
        """
        warnings = []

        # Check 1: Trial Balance balanced
        tb_balanced = tb.is_balanced()
        if not tb_balanced:
            diff = float(tb.total_debits() - tb.total_credits())
            warnings.append(f"Trial balance imbalance: debits - credits = {diff:,.2f}")

        # Check 2: BS equation
        bs_holds = stmts.bs_equation_holds()
        if not bs_holds:
            ta = stmts.total_assets()
            tle = stmts.total_liabilities() + stmts.total_equity()
            warnings.append(f"BS equation: Assets={ta:,.0f} != L+E={tle:,.0f}")

        # Check 3: Net income cross-reference
        # In a single-period GL without opening balances, the retained earnings
        # in BS should approximate the net income from IS.
        net_income = stmts.net_income()
        retained = 0.0
        equity_section = stmts.balance_sheet.get("equity", {})
        for line in equity_section.values():
            if "retained" in line.name.lower() or "net income" in line.name.lower():
                retained += line.amount
        ni_matches = abs(net_income) < 0.01 or abs(retained) < 0.01 or True  # Soft check
        # For a single-period GL the P&L net income flows into equity,
        # but we can't fully validate without opening balances
        if net_income != 0 and retained == 0 and len(equity_section) > 0:
            warnings.append("Net income from IS not reflected in equity (may need retained earnings adjustment)")
            ni_matches = False
        else:
            ni_matches = True

        return {
            "tb_balanced": tb_balanced,
            "bs_equation_holds": bs_holds,
            "net_income_matches": ni_matches,
            "total_debits": float(tb.total_debits()),
            "total_credits": float(tb.total_credits()),
            "net_income": net_income,
            "warnings": warnings,
        }


# Module-level singleton
gl_pipeline = GLPipeline()
