"""
FinAI v2 Cash Flow Statement — Decimal-precise indirect method.
================================================================
Port of cash_flow.py with all float → Decimal.

Public API:
    from app.services.v2.cash_flow import build_cash_flow
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.v2.decimal_utils import to_decimal, round_fin, safe_divide, is_zero
from app.services.file_parser import map_coa

logger = logging.getLogger(__name__)

D = Decimal

# ── Label groups: BS labels → CFS bucket mapping ──────────────────────

CASH_LABELS = {
    "Cash in Hand (GEL)", "Cash in Hand (FX)", "Bank Accounts",
    "Bank Accounts (GEL)", "Bank Accounts (FX)", "Money in Transit",
    "Cash & Equivalents",
}
RECEIVABLE_LABELS = {
    "Trade Receivables", "Employee Receivables", "Advances to Suppliers",
    "Other Receivables", "Doubtful Debt Allowance", "Other Current Assets",
    "Short-term Investments", "Dividends & Interest Recv",
    "Dividends Receivable", "Interest Receivable",
}
INVENTORY_LABELS = {
    "Inventory", "Goods in Transit", "Merchandise",
    "Raw Materials & Fuel", "Work in Progress", "Finished Goods",
}
PREPAID_LABELS = {"Prepaid Taxes", "Prepaid VAT", "Input VAT (Asset)"}
FIXED_ASSET_LABELS = {
    "Fixed Assets (PP&E)", "Land", "Construction in Progress",
    "Fixed Assets", "Investment Property", "Land Acquisition",
    "Fixed Asset Acquisition", "Noncurrent Assets",
}
DEPRECIATION_LABELS = {"Accumulated Depreciation", "Acc. Depr. - Fixed Assets"}
INTANGIBLE_LABELS = {
    "Intangible Assets", "Acc. Amort. - Intangibles", "Accumulated Amortization",
}
DEFERRED_TAX_ASSET_LABELS = {"Deferred Tax Assets", "Long-term Investments"}
TRADE_PAYABLE_LABELS = {
    "Trade Payables", "Advances Received", "Other Trade Payables",
    "Wages Payable", "Accrued Liabilities", "Interest Payable",
    "Dividends Payable", "Other Accrued Liabilities",
}
TAX_PAYABLE_LABELS = {
    "VAT Payable", "Output VAT (Liability)", "Excise Tax Payable",
    "Income Tax Payable", "Other Tax Payables",
}
SHORT_TERM_DEBT_LABELS = {
    "Short-term Bank Loans", "Short-term Debt", "Current Portion of LT Debt",
}
LONG_TERM_DEBT_LABELS = {
    "Long-term Bank Loans", "Long-term Debt", "Bonds Payable",
    "Long-term Obligations", "Deferred Tax Liability",
}
EQUITY_LABELS = {
    "Share Capital", "Retained Earnings", "Reserves",
    "Additional Paid-in Capital", "Revaluation Reserve",
    "Treasury Shares", "Accumulated OCI",
}


def _classify_account(code: str) -> Optional[str]:
    """Classify an account code into a CFS bucket using COA mapping."""
    if not code:
        return None
    mapped = map_coa(code)
    if not mapped:
        return None
    label = mapped.get("bs") or mapped.get("pl") or ""
    if label in CASH_LABELS: return "cash"
    if label in RECEIVABLE_LABELS: return "receivables"
    if label in INVENTORY_LABELS: return "inventory"
    if label in PREPAID_LABELS: return "prepaid"
    if label in FIXED_ASSET_LABELS: return "fixed_assets"
    if label in DEPRECIATION_LABELS: return "depreciation"
    if label in INTANGIBLE_LABELS: return "intangibles"
    if label in DEFERRED_TAX_ASSET_LABELS: return "deferred_tax_assets"
    if label in TRADE_PAYABLE_LABELS: return "trade_payables"
    if label in TAX_PAYABLE_LABELS: return "tax_payables"
    if label in SHORT_TERM_DEBT_LABELS: return "short_term_debt"
    if label in LONG_TERM_DEBT_LABELS: return "long_term_debt"
    if label in EQUITY_LABELS: return "equity"
    # Fallback by account class
    first = code[0] if code else ""
    if first in ("1",): return "other_assets"
    if first in ("2",): return "other_assets"
    if first in ("3",): return "other_liabilities"
    if first in ("4",): return "other_liabilities"
    return None


@dataclass
class CashFlowStatement:
    """Structured Cash Flow Statement — ALL amounts are Decimal."""
    period: str = ""
    currency: str = "GEL"
    is_comparative: bool = True

    # Operating
    net_income: Decimal = field(default_factory=lambda: D("0"))
    depreciation_amortization: Decimal = field(default_factory=lambda: D("0"))
    change_receivables: Decimal = field(default_factory=lambda: D("0"))
    change_inventory: Decimal = field(default_factory=lambda: D("0"))
    change_prepaid: Decimal = field(default_factory=lambda: D("0"))
    change_trade_payables: Decimal = field(default_factory=lambda: D("0"))
    change_tax_payables: Decimal = field(default_factory=lambda: D("0"))
    net_operating_cash: Decimal = field(default_factory=lambda: D("0"))

    # Investing
    capex: Decimal = field(default_factory=lambda: D("0"))
    intangible_purchases: Decimal = field(default_factory=lambda: D("0"))
    other_investing: Decimal = field(default_factory=lambda: D("0"))
    net_investing_cash: Decimal = field(default_factory=lambda: D("0"))

    # Financing
    change_short_term_debt: Decimal = field(default_factory=lambda: D("0"))
    change_long_term_debt: Decimal = field(default_factory=lambda: D("0"))
    change_equity: Decimal = field(default_factory=lambda: D("0"))
    net_financing_cash: Decimal = field(default_factory=lambda: D("0"))

    # Reconciliation
    net_change_in_cash: Decimal = field(default_factory=lambda: D("0"))
    beginning_cash: Decimal = field(default_factory=lambda: D("0"))
    ending_cash: Decimal = field(default_factory=lambda: D("0"))
    ending_cash_per_bs: Decimal = field(default_factory=lambda: D("0"))
    cash_discrepancy: Decimal = field(default_factory=lambda: D("0"))
    note: str = ""

    def to_rows(self) -> List[Dict]:
        rows: List[Dict] = []

        def add(code, label, actual, plan=D("0"), level=0, bold=False, sep=False, sign=1):
            rows.append({
                "c": code, "l": label,
                "ac": str(round_fin(actual)), "pl": str(round_fin(plan)),
                "lvl": level, "bold": bold, "sep": sep, "s": sign,
            })

        add("CFS", "CASH FLOW STATEMENT", D("0"), level=0, bold=True, sep=True)

        # Operating
        add("OP", "OPERATING ACTIVITIES", self.net_operating_cash, level=0, bold=True, sep=True,
            sign=1 if self.net_operating_cash >= 0 else -1)
        add("OP.NI", "Net Income", self.net_income, level=1, sign=1 if self.net_income >= 0 else -1)
        add("OP.DA", "Depreciation & Amortization", self.depreciation_amortization, level=1, sign=1)
        add("OP.AR", "Change in Receivables", self.change_receivables, level=1,
            sign=1 if self.change_receivables >= 0 else -1)
        add("OP.INV", "Change in Inventory", self.change_inventory, level=1,
            sign=1 if self.change_inventory >= 0 else -1)
        add("OP.PP", "Change in Prepaid", self.change_prepaid, level=1,
            sign=1 if self.change_prepaid >= 0 else -1)
        add("OP.AP", "Change in Trade Payables", self.change_trade_payables, level=1,
            sign=1 if self.change_trade_payables >= 0 else -1)
        add("OP.TAX", "Change in Tax Payables", self.change_tax_payables, level=1,
            sign=1 if self.change_tax_payables >= 0 else -1)

        # Investing
        add("INV", "INVESTING ACTIVITIES", self.net_investing_cash, level=0, bold=True, sep=True,
            sign=1 if self.net_investing_cash >= 0 else -1)
        add("INV.CAP", "Capital Expenditure", self.capex, level=1, sign=-1)
        add("INV.INT", "Intangible Purchases", self.intangible_purchases, level=1, sign=-1)
        add("INV.OTH", "Other Investing", self.other_investing, level=1,
            sign=1 if self.other_investing >= 0 else -1)

        # Financing
        add("FIN", "FINANCING ACTIVITIES", self.net_financing_cash, level=0, bold=True, sep=True,
            sign=1 if self.net_financing_cash >= 0 else -1)
        add("FIN.STD", "Change in Short-term Debt", self.change_short_term_debt, level=1,
            sign=1 if self.change_short_term_debt >= 0 else -1)
        add("FIN.LTD", "Change in Long-term Debt", self.change_long_term_debt, level=1,
            sign=1 if self.change_long_term_debt >= 0 else -1)
        add("FIN.EQ", "Change in Equity", self.change_equity, level=1,
            sign=1 if self.change_equity >= 0 else -1)

        # Reconciliation
        add("NET", "NET CHANGE IN CASH", self.net_change_in_cash, level=0, bold=True, sep=True,
            sign=1 if self.net_change_in_cash >= 0 else -1)
        add("BEG", "Beginning Cash", self.beginning_cash, level=1, sign=1)
        add("END", "Ending Cash", self.ending_cash, level=1, bold=True, sign=1)
        add("END.BS", "Ending Cash (per BS)", self.ending_cash_per_bs, level=1, sign=1)

        if not is_zero(self.cash_discrepancy):
            add("DISC", "Cash Discrepancy", self.cash_discrepancy, level=1,
                sign=1 if self.cash_discrepancy >= 0 else -1)

        return rows

    def to_dict(self) -> Dict:
        return {
            "period": self.period, "currency": self.currency,
            "is_comparative": self.is_comparative,
            "operating": {
                "net_income": str(round_fin(self.net_income)),
                "depreciation_amortization": str(round_fin(self.depreciation_amortization)),
                "change_receivables": str(round_fin(self.change_receivables)),
                "change_inventory": str(round_fin(self.change_inventory)),
                "change_prepaid": str(round_fin(self.change_prepaid)),
                "change_trade_payables": str(round_fin(self.change_trade_payables)),
                "change_tax_payables": str(round_fin(self.change_tax_payables)),
                "net_operating_cash": str(round_fin(self.net_operating_cash)),
            },
            "investing": {
                "capex": str(round_fin(self.capex)),
                "intangible_purchases": str(round_fin(self.intangible_purchases)),
                "other_investing": str(round_fin(self.other_investing)),
                "net_investing_cash": str(round_fin(self.net_investing_cash)),
            },
            "financing": {
                "change_short_term_debt": str(round_fin(self.change_short_term_debt)),
                "change_long_term_debt": str(round_fin(self.change_long_term_debt)),
                "change_equity": str(round_fin(self.change_equity)),
                "net_financing_cash": str(round_fin(self.net_financing_cash)),
            },
            "reconciliation": {
                "net_change_in_cash": str(round_fin(self.net_change_in_cash)),
                "beginning_cash": str(round_fin(self.beginning_cash)),
                "ending_cash": str(round_fin(self.ending_cash)),
                "ending_cash_per_bs": str(round_fin(self.ending_cash_per_bs)),
                "cash_discrepancy": str(round_fin(self.cash_discrepancy)),
            },
            "rows": self.to_rows(),
            "note": self.note,
        }


def _compute_bs_buckets(txns: List[Any]) -> Dict[str, Decimal]:
    """Compute BS section balances from transactions — Decimal precision."""
    buckets: Dict[str, Decimal] = {
        "cash": D("0"), "receivables": D("0"), "inventory": D("0"),
        "prepaid": D("0"), "fixed_assets": D("0"), "depreciation": D("0"),
        "intangibles": D("0"), "deferred_tax_assets": D("0"),
        "trade_payables": D("0"), "tax_payables": D("0"),
        "short_term_debt": D("0"), "long_term_debt": D("0"),
        "equity": D("0"), "other_assets": D("0"), "other_liabilities": D("0"),
    }
    for txn in txns:
        amt = to_decimal(txn.amount)
        if is_zero(amt):
            continue
        dr_code = txn.acct_dr or ""
        cr_code = txn.acct_cr or ""
        dr_bucket = _classify_account(dr_code)
        if dr_bucket and dr_bucket in buckets:
            buckets[dr_bucket] += amt
        cr_bucket = _classify_account(cr_code)
        if cr_bucket and cr_bucket in buckets:
            buckets[cr_bucket] -= amt
    return buckets


async def build_cash_flow(
    db: AsyncSession,
    current_dataset_id: int,
    prior_dataset_id: Optional[int] = None,
) -> CashFlowStatement:
    """Build Cash Flow Statement (indirect method) — ALL Decimal."""
    from app.models.all_models import Transaction, Dataset, RevenueItem, COGSItem, GAExpenseItem

    cfs = CashFlowStatement()

    # Step 1: Dataset metadata
    result = await db.execute(select(Dataset).where(Dataset.id == current_dataset_id))
    current_ds = result.scalars().first()
    if current_ds:
        cfs.period = current_ds.period or ""
        cfs.currency = current_ds.currency or "GEL"

    # Step 2: Current transactions
    result = await db.execute(select(Transaction).where(Transaction.dataset_id == current_dataset_id))
    current_txns = result.scalars().all()

    # Step 3: Prior transactions
    prior_txns = []
    has_prior = prior_dataset_id is not None
    if has_prior:
        result = await db.execute(select(Transaction).where(Transaction.dataset_id == prior_dataset_id))
        prior_txns = result.scalars().all()
        if not prior_txns:
            has_prior = False
    cfs.is_comparative = has_prior

    # Step 4: BS buckets
    current_buckets = _compute_bs_buckets(current_txns)
    prior_buckets = _compute_bs_buckets(prior_txns) if has_prior else {k: D("0") for k in current_buckets}

    # Step 5: P&L (using v2 income statement)
    try:
        from app.services.v2.income_statement import build_income_statement as build_pl
        rev = (await db.execute(select(RevenueItem).where(RevenueItem.dataset_id == current_dataset_id))).scalars().all()
        cogs = (await db.execute(select(COGSItem).where(COGSItem.dataset_id == current_dataset_id))).scalars().all()
        ga = (await db.execute(select(GAExpenseItem).where(GAExpenseItem.dataset_id == current_dataset_id))).scalars().all()
        pl = build_pl(rev, cogs, ga, period=cfs.period, currency=cfs.currency)
        cfs.net_income = pl.net_profit
        cfs.depreciation_amortization = pl.da_expenses
    except Exception as exc:
        logger.error("Error building P&L for CFS: %s", exc)

    # Step 6: Working capital changes
    cfs.change_receivables = -(current_buckets["receivables"] - prior_buckets["receivables"])
    cfs.change_inventory = -(current_buckets["inventory"] - prior_buckets["inventory"])
    cfs.change_prepaid = -(current_buckets["prepaid"] - prior_buckets["prepaid"])
    cfs.change_trade_payables = -(current_buckets["trade_payables"] - prior_buckets["trade_payables"])
    cfs.change_tax_payables = -(current_buckets["tax_payables"] - prior_buckets["tax_payables"])

    cfs.net_operating_cash = (
        cfs.net_income + cfs.depreciation_amortization +
        cfs.change_receivables + cfs.change_inventory + cfs.change_prepaid +
        cfs.change_trade_payables + cfs.change_tax_payables
    )

    # Step 7: Investing
    gross_fa = current_buckets["fixed_assets"] - prior_buckets["fixed_assets"]
    depr_chg = current_buckets["depreciation"] - prior_buckets["depreciation"]
    cfs.capex = -(gross_fa + depr_chg)
    cfs.intangible_purchases = -(current_buckets["intangibles"] - prior_buckets["intangibles"])
    cfs.other_investing = -(current_buckets["deferred_tax_assets"] - prior_buckets["deferred_tax_assets"])
    cfs.net_investing_cash = cfs.capex + cfs.intangible_purchases + cfs.other_investing

    # Step 8: Financing
    cfs.change_short_term_debt = -(current_buckets["short_term_debt"] - prior_buckets["short_term_debt"])
    cfs.change_long_term_debt = -(current_buckets["long_term_debt"] - prior_buckets["long_term_debt"])
    cfs.change_equity = -(current_buckets["equity"] - prior_buckets["equity"])
    cfs.net_financing_cash = cfs.change_short_term_debt + cfs.change_long_term_debt + cfs.change_equity

    # Step 9: Reconciliation
    cfs.net_change_in_cash = cfs.net_operating_cash + cfs.net_investing_cash + cfs.net_financing_cash
    cfs.beginning_cash = prior_buckets["cash"]
    cfs.ending_cash = cfs.beginning_cash + cfs.net_change_in_cash
    cfs.ending_cash_per_bs = current_buckets["cash"]
    cfs.cash_discrepancy = round_fin(cfs.ending_cash - cfs.ending_cash_per_bs)

    if not is_zero(cfs.cash_discrepancy):
        logger.warning("Cash discrepancy: CFS=%s, BS=%s, diff=%s",
                        cfs.ending_cash, cfs.ending_cash_per_bs, cfs.cash_discrepancy)

    if not has_prior:
        cfs.note = "No prior period — values are absolute balances, not period-over-period changes."

    return cfs
