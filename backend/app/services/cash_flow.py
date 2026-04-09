"""
cash_flow.py -- Cash Flow Statement builder (indirect method).

Constructs a Cash Flow Statement from balance sheet transaction data,
using the indirect method starting from net income and adjusting for:
  - Non-cash items (depreciation & amortization)
  - Changes in working capital (receivables, inventory, payables, taxes)
  - Investing activities (capex from fixed asset and intangible changes)
  - Financing activities (debt and equity changes)

Georgian Chart of Accounts (1C standard):
  Class 1: Current Assets       Class 3: Current Liabilities
  Class 2: Noncurrent Assets    Class 4: Noncurrent Liabilities
  Class 5: Equity               Class 6-9: P&L accounts

Balance sheet accounting convention:
  DR entry increases assets (debit side), CR entry decreases assets.
  Net balance for an account = sum(DR amounts) - sum(CR amounts).
  Liabilities and equity are negated for display (natural credit balances).
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.all_models import Transaction, Dataset, RevenueItem, COGSItem, GAExpenseItem
from app.services.file_parser import map_coa
from app.services.income_statement import build_income_statement

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Label groups: account "bs" labels from map_coa() -> CFS bucket mapping
# ---------------------------------------------------------------------------

# Cash and cash equivalents (Class 11xx, 12xx)
CASH_LABELS = {
    "Cash in Hand (GEL)", "Cash in Hand (FX)",
    "Bank Accounts", "Bank Accounts (GEL)", "Bank Accounts (FX)",
    "Money in Transit", "Cash & Equivalents",
}

# Receivables -- operating current assets that affect working capital
RECEIVABLE_LABELS = {
    "Trade Receivables", "Employee Receivables",
    "Advances to Suppliers", "Other Receivables",
    "Doubtful Debt Allowance",
    "Other Current Assets", "Short-term Investments",
    "Dividends & Interest Recv", "Dividends Receivable", "Interest Receivable",
}

# Inventory
INVENTORY_LABELS = {
    "Inventory", "Goods in Transit", "Merchandise",
    "Raw Materials & Fuel", "Work in Progress", "Finished Goods",
}

# Prepaid taxes and VAT -- treated as operating asset changes
PREPAID_LABELS = {
    "Prepaid Taxes", "Prepaid VAT", "Input VAT (Asset)",
}

# Fixed assets (PP&E) -- investing
FIXED_ASSET_LABELS = {
    "Fixed Assets (PP&E)", "Land", "Construction in Progress",
    "Fixed Assets", "Investment Property",
    "Land Acquisition", "Fixed Asset Acquisition",
    "Noncurrent Assets",
}

# Accumulated depreciation (contra asset) -- investing adjustment
DEPRECIATION_LABELS = {
    "Accumulated Depreciation", "Acc. Depr. - Fixed Assets",
}

# Intangible assets -- investing
INTANGIBLE_LABELS = {
    "Intangible Assets", "Acc. Amort. - Intangibles",
    "Accumulated Amortization",
}

# Deferred tax assets -- investing / other
DEFERRED_TAX_ASSET_LABELS = {
    "Deferred Tax Assets",
    "Long-term Investments",
}

# Trade payables -- operating liabilities
TRADE_PAYABLE_LABELS = {
    "Trade Payables", "Advances Received",
    "Other Trade Payables", "Wages Payable",
    "Accrued Liabilities", "Interest Payable",
    "Dividends Payable", "Other Accrued Liabilities",
}

# Tax payables -- operating liabilities
TAX_PAYABLE_LABELS = {
    "Tax Payables", "Income Tax Payable", "Revenue Tax Payable",
    "VAT Payable", "Other Tax Payables", "Excise Payable",
    "Pension Obligations", "Property Tax Payable",
    "Other Tax Liabilities",
}

# Short-term debt -- financing
SHORT_TERM_DEBT_LABELS = {
    "Short-term Debt", "Short-term Loans",
    "Current Lease Liability",
}

# Long-term debt -- financing
LONG_TERM_DEBT_LABELS = {
    "Long-term Debt", "Usufruct Obligations", "Long-term Loans",
    "Long-term Lease Liability", "Other LT Liabilities",
    "Noncurrent Liabilities",
    "Deferred Tax Liabilities",
}

# Equity -- financing
EQUITY_LABELS = {
    "Share Capital", "Retained Earnings", "Reserves", "Equity",
}


# ---------------------------------------------------------------------------
# CashFlowStatement dataclass
# ---------------------------------------------------------------------------

@dataclass
class CashFlowStatement:
    """Structured Cash Flow Statement with all sections and a row renderer."""

    period: str = ""
    currency: str = "GEL"
    is_comparative: bool = True  # False when no prior period is available

    # -- Operating Activities (indirect method) --
    net_income: float = 0.0
    depreciation_amortization: float = 0.0      # D&A add-back

    change_receivables: float = 0.0             # decrease = source of cash
    change_inventory: float = 0.0               # decrease = source of cash
    change_prepaid: float = 0.0                 # decrease = source of cash
    change_trade_payables: float = 0.0          # increase = source of cash
    change_tax_payables: float = 0.0            # increase = source of cash

    net_operating_cash: float = 0.0

    # -- Investing Activities --
    capex: float = 0.0                          # purchases of PP&E (negative = outflow)
    intangible_purchases: float = 0.0           # purchases of intangibles
    other_investing: float = 0.0                # deferred tax assets, LT investments

    net_investing_cash: float = 0.0

    # -- Financing Activities --
    change_short_term_debt: float = 0.0
    change_long_term_debt: float = 0.0
    change_equity: float = 0.0                  # excludes retained earnings

    net_financing_cash: float = 0.0

    # -- Reconciliation --
    net_change_in_cash: float = 0.0
    beginning_cash: float = 0.0
    ending_cash: float = 0.0
    ending_cash_per_bs: float = 0.0             # cross-validation from BS
    cash_discrepancy: float = 0.0               # should be zero if correct
    note: str = ""                              # informational message

    def to_rows(self) -> List[Dict]:
        """Convert the CFS to frontend row format: {c, l, ac, pl, lvl, bold, sep, s}."""
        rows: List[Dict] = []

        def add(code: str, label: str, actual: float, plan: float = 0.0,
                level: int = 0, bold: bool = False, sep: bool = False, sign: int = 1):
            rows.append({
                "c": code, "l": label,
                "ac": round(actual, 2), "pl": round(plan, 2),
                "lvl": level, "bold": bold, "sep": sep, "s": sign,
            })

        # ── Section I: Operating Activities ─────────────────────────
        add("CFS.OP", "CASH FLOWS FROM OPERATING ACTIVITIES", self.net_operating_cash,
            0, 0, True, True, 1)

        add("CFS.OP.NI", "Net Income", self.net_income,
            0, 1, False, False, 1)
        add("CFS.OP.DA", "Depreciation & Amortization", self.depreciation_amortization,
            0, 1, False, False, 1)

        # Working capital header
        add("CFS.OP.WC", "Changes in Working Capital:", 0.0,
            0, 1, True, False, 1)

        wc_sign = lambda v: 1 if v >= 0 else -1
        add("CFS.OP.AR", "  (Increase)/Decrease in Receivables", self.change_receivables,
            0, 2, False, False, wc_sign(self.change_receivables))
        add("CFS.OP.INV", "  (Increase)/Decrease in Inventory", self.change_inventory,
            0, 2, False, False, wc_sign(self.change_inventory))
        add("CFS.OP.PP", "  (Increase)/Decrease in Prepaid Items", self.change_prepaid,
            0, 2, False, False, wc_sign(self.change_prepaid))
        add("CFS.OP.AP", "  Increase/(Decrease) in Trade Payables", self.change_trade_payables,
            0, 2, False, False, wc_sign(self.change_trade_payables))
        add("CFS.OP.TP", "  Increase/(Decrease) in Tax Payables", self.change_tax_payables,
            0, 2, False, False, wc_sign(self.change_tax_payables))

        add("CFS.OP.TOT", "Net Cash from Operating Activities", self.net_operating_cash,
            0, 1, True, True, 1 if self.net_operating_cash >= 0 else -1)

        # ── Section II: Investing Activities ────────────────────────
        add("CFS.INV", "CASH FLOWS FROM INVESTING ACTIVITIES", self.net_investing_cash,
            0, 0, True, True, 1)

        add("CFS.INV.CAPEX", "Capital Expenditures (PP&E)", self.capex,
            0, 1, False, False, -1)
        add("CFS.INV.INTG", "Intangible Asset Purchases", self.intangible_purchases,
            0, 1, False, False, -1)
        if abs(self.other_investing) > 0.005:
            add("CFS.INV.OTH", "Other Investing Activities", self.other_investing,
                0, 1, False, False, 1 if self.other_investing >= 0 else -1)

        add("CFS.INV.TOT", "Net Cash from Investing Activities", self.net_investing_cash,
            0, 1, True, True, 1 if self.net_investing_cash >= 0 else -1)

        # ── Section III: Financing Activities ───────────────────────
        add("CFS.FIN", "CASH FLOWS FROM FINANCING ACTIVITIES", self.net_financing_cash,
            0, 0, True, True, 1)

        add("CFS.FIN.STD", "Change in Short-term Debt", self.change_short_term_debt,
            0, 1, False, False, 1 if self.change_short_term_debt >= 0 else -1)
        add("CFS.FIN.LTD", "Change in Long-term Debt", self.change_long_term_debt,
            0, 1, False, False, 1 if self.change_long_term_debt >= 0 else -1)
        if abs(self.change_equity) > 0.005:
            add("CFS.FIN.EQ", "Change in Equity", self.change_equity,
                0, 1, False, False, 1 if self.change_equity >= 0 else -1)

        add("CFS.FIN.TOT", "Net Cash from Financing Activities", self.net_financing_cash,
            0, 1, True, True, 1 if self.net_financing_cash >= 0 else -1)

        # ── Reconciliation ──────────────────────────────────────────
        add("CFS.REC", "CASH RECONCILIATION", 0.0,
            0, 0, True, True, 1)
        add("CFS.REC.BEG", "Beginning Cash Balance", self.beginning_cash,
            0, 1, False, False, 1)
        add("CFS.REC.CHG", "Net Change in Cash", self.net_change_in_cash,
            0, 1, False, False, 1 if self.net_change_in_cash >= 0 else -1)
        add("CFS.REC.END", "Ending Cash Balance", self.ending_cash,
            0, 1, True, False, 1)
        add("CFS.REC.BS", "Ending Cash per Balance Sheet", self.ending_cash_per_bs,
            0, 1, False, False, 1)

        if abs(self.cash_discrepancy) > 0.01:
            add("CFS.REC.DISC", "Cash Discrepancy (unresolved)", self.cash_discrepancy,
                0, 1, False, False, -1)

        if self.note:
            add("CFS.NOTE", self.note, 0.0, 0, 0, False, True, 1)

        return rows

    def to_dict(self) -> Dict:
        """Full dictionary representation for API responses."""
        return {
            "period": self.period,
            "currency": self.currency,
            "is_comparative": self.is_comparative,
            "operating": {
                "net_income": round(self.net_income, 2),
                "depreciation_amortization": round(self.depreciation_amortization, 2),
                "change_receivables": round(self.change_receivables, 2),
                "change_inventory": round(self.change_inventory, 2),
                "change_prepaid": round(self.change_prepaid, 2),
                "change_trade_payables": round(self.change_trade_payables, 2),
                "change_tax_payables": round(self.change_tax_payables, 2),
                "net_operating_cash": round(self.net_operating_cash, 2),
            },
            "investing": {
                "capex": round(self.capex, 2),
                "intangible_purchases": round(self.intangible_purchases, 2),
                "other_investing": round(self.other_investing, 2),
                "net_investing_cash": round(self.net_investing_cash, 2),
            },
            "financing": {
                "change_short_term_debt": round(self.change_short_term_debt, 2),
                "change_long_term_debt": round(self.change_long_term_debt, 2),
                "change_equity": round(self.change_equity, 2),
                "net_financing_cash": round(self.net_financing_cash, 2),
            },
            "reconciliation": {
                "net_change_in_cash": round(self.net_change_in_cash, 2),
                "beginning_cash": round(self.beginning_cash, 2),
                "ending_cash": round(self.ending_cash, 2),
                "ending_cash_per_bs": round(self.ending_cash_per_bs, 2),
                "cash_discrepancy": round(self.cash_discrepancy, 2),
            },
            "note": self.note,
            "rows": self.to_rows(),
        }


# ---------------------------------------------------------------------------
# Helper: classify a single account code into a CFS bucket
# ---------------------------------------------------------------------------

def _classify_account(code: str) -> Optional[str]:
    """
    Map an account code to one of the CFS bucket names using map_coa().
    Returns a bucket key string or None if the account is a P&L account
    (classes 6-9) or unrecognised.
    """
    info = map_coa(code)
    if not info:
        return None

    label = info.get("bs", "")
    if not label:
        # P&L account (side = income/expense), skip for BS computation
        return None

    # Match against known bucket sets
    if label in CASH_LABELS:
        return "cash"
    if label in RECEIVABLE_LABELS:
        return "receivables"
    if label in INVENTORY_LABELS:
        return "inventory"
    if label in PREPAID_LABELS:
        return "prepaid"
    if label in FIXED_ASSET_LABELS:
        return "fixed_assets"
    if label in DEPRECIATION_LABELS:
        return "depreciation"
    if label in INTANGIBLE_LABELS:
        return "intangibles"
    if label in DEFERRED_TAX_ASSET_LABELS:
        return "deferred_tax_assets"
    if label in TRADE_PAYABLE_LABELS:
        return "trade_payables"
    if label in TAX_PAYABLE_LABELS:
        return "tax_payables"
    if label in SHORT_TERM_DEBT_LABELS:
        return "short_term_debt"
    if label in LONG_TERM_DEBT_LABELS:
        return "long_term_debt"
    if label in EQUITY_LABELS:
        return "equity"

    # Fallback: classify by bs_side if label was not explicitly listed
    bs_side = info.get("bs_side", "")
    if bs_side == "asset":
        return "other_assets"
    if bs_side in ("liability",):
        return "other_liabilities"
    if bs_side == "equity":
        return "equity"

    return None


# ---------------------------------------------------------------------------
# Balance Sheet bucket computation from transactions
# ---------------------------------------------------------------------------

def _compute_bs_buckets(txns: List[Any]) -> Dict[str, float]:
    """
    Compute aggregated balance sheet section balances from a list of
    Transaction objects.

    Each transaction has acct_dr (debit account) and acct_cr (credit account)
    plus an amount. The debit side receives (increases assets), the credit
    side gives (decreases assets). For liabilities/equity, a credit increases
    the balance -- we handle the sign at the bucket level.

    Returns a dict of bucket_name -> net balance (positive = natural debit
    balance for assets, natural credit balance stored as positive for
    liabilities/equity after negation).
    """
    buckets: Dict[str, float] = {
        "cash": 0.0,
        "receivables": 0.0,
        "inventory": 0.0,
        "prepaid": 0.0,
        "fixed_assets": 0.0,
        "depreciation": 0.0,
        "intangibles": 0.0,
        "deferred_tax_assets": 0.0,
        "trade_payables": 0.0,
        "tax_payables": 0.0,
        "short_term_debt": 0.0,
        "long_term_debt": 0.0,
        "equity": 0.0,
        "other_assets": 0.0,
        "other_liabilities": 0.0,
    }

    for txn in txns:
        amt = float(txn.amount or 0.0)
        if amt == 0.0:
            continue

        dr_code = txn.acct_dr or ""
        cr_code = txn.acct_cr or ""

        # Debit side: the account that receives value (DR increases assets)
        dr_bucket = _classify_account(dr_code)
        if dr_bucket and dr_bucket in buckets:
            buckets[dr_bucket] += amt

        # Credit side: the account that gives value (CR decreases assets)
        cr_bucket = _classify_account(cr_code)
        if cr_bucket and cr_bucket in buckets:
            buckets[cr_bucket] -= amt

    return buckets


# ---------------------------------------------------------------------------
# Main async builder
# ---------------------------------------------------------------------------

async def build_cash_flow(
    db: AsyncSession,
    current_dataset_id: int,
    prior_dataset_id: Optional[int] = None,
) -> CashFlowStatement:
    """
    Build a Cash Flow Statement using the indirect method.

    Steps:
      1. Fetch transactions for current and prior datasets.
      2. Compute BS buckets for both periods.
      3. Compute P&L data (net income, D&A) via build_income_statement.
      4. Calculate changes in working capital items.
      5. Calculate investing activities (capex, intangibles).
      6. Calculate financing activities (debt, equity).
      7. Reconcile: beginning cash + net change = ending cash.
      8. Cross-validate ending cash against BS cash balance.

    Args:
        db: AsyncSession for database queries.
        current_dataset_id: Dataset ID for the current period.
        prior_dataset_id: Dataset ID for the prior period (optional).

    Returns:
        CashFlowStatement dataclass with all computed fields.
    """
    cfs = CashFlowStatement()

    # ── Step 1: Fetch dataset metadata ──────────────────────────────
    try:
        result = await db.execute(
            select(Dataset).where(Dataset.id == current_dataset_id)
        )
        current_ds = result.scalars().first()
        if current_ds:
            cfs.period = current_ds.period or ""
            cfs.currency = current_ds.currency or "GEL"
        else:
            logger.warning("Current dataset %s not found", current_dataset_id)
    except Exception as exc:
        logger.error("Error fetching current dataset: %s", exc)

    # ── Step 2: Fetch transactions for current period ───────────────
    try:
        result = await db.execute(
            select(Transaction).where(Transaction.dataset_id == current_dataset_id)
        )
        current_txns = result.scalars().all()
        logger.info("Loaded %d transactions for current dataset %s",
                     len(current_txns), current_dataset_id)
    except Exception as exc:
        logger.error("Error fetching current transactions: %s", exc)
        current_txns = []

    # ── Step 3: Fetch transactions for prior period (if available) ──
    prior_txns = []
    has_prior = prior_dataset_id is not None
    if has_prior:
        try:
            result = await db.execute(
                select(Transaction).where(Transaction.dataset_id == prior_dataset_id)
            )
            prior_txns = result.scalars().all()
            logger.info("Loaded %d transactions for prior dataset %s",
                         len(prior_txns), prior_dataset_id)
        except Exception as exc:
            logger.error("Error fetching prior transactions: %s", exc)
            prior_txns = []
            has_prior = False

    cfs.is_comparative = has_prior

    # ── Step 4: Compute BS buckets for both periods ─────────────────
    current_buckets = _compute_bs_buckets(current_txns)
    prior_buckets = _compute_bs_buckets(prior_txns) if has_prior else {
        k: 0.0 for k in current_buckets
    }

    logger.debug("Current BS buckets: %s", {k: round(v, 2) for k, v in current_buckets.items()})
    if has_prior:
        logger.debug("Prior BS buckets: %s", {k: round(v, 2) for k, v in prior_buckets.items()})

    # ── Step 5: Compute P&L data via income statement builder ───────
    # Fetch revenue, COGS, and G&A items for the current period to
    # derive net income and D&A figures.
    try:
        rev_result = await db.execute(
            select(RevenueItem).where(RevenueItem.dataset_id == current_dataset_id)
        )
        rev_items = rev_result.scalars().all()

        cogs_result = await db.execute(
            select(COGSItem).where(COGSItem.dataset_id == current_dataset_id)
        )
        cogs_items = cogs_result.scalars().all()

        ga_result = await db.execute(
            select(GAExpenseItem).where(GAExpenseItem.dataset_id == current_dataset_id)
        )
        ga_items = ga_result.scalars().all()

        income_stmt = build_income_statement(
            rev_items, cogs_items, ga_items,
            period=cfs.period, currency=cfs.currency,
        )
        cfs.net_income = income_stmt.net_profit
        cfs.depreciation_amortization = income_stmt.da_expenses

        logger.info("P&L: net_income=%.2f, D&A=%.2f",
                     cfs.net_income, cfs.depreciation_amortization)
    except Exception as exc:
        logger.error("Error building income statement for CFS: %s", exc)
        cfs.net_income = 0.0
        cfs.depreciation_amortization = 0.0

    # ── Step 6: Changes in working capital ──────────────────────────
    # For assets: decrease in asset = source of cash (positive CFS impact)
    #   change_for_CFS = -(current - prior) = prior - current
    # For liabilities: increase in liability = source of cash (positive)
    #   change_for_CFS = current - prior

    # Asset-side working capital items (sign-inverted for CFS)
    cfs.change_receivables = -(
        current_buckets["receivables"] - prior_buckets["receivables"]
    )
    cfs.change_inventory = -(
        current_buckets["inventory"] - prior_buckets["inventory"]
    )
    cfs.change_prepaid = -(
        current_buckets["prepaid"] - prior_buckets["prepaid"]
    )

    # Liability-side working capital items
    # For liabilities, bucket stores net = sum(DR) - sum(CR).
    # A credit (increase in liability) makes the bucket more negative.
    # So an increase in the liability from prior to current means the
    # bucket value decreased (became more negative). The CFS impact
    # for an increase in liabilities is positive (source of cash).
    # change_for_CFS = -(current - prior) because bucket is inverted.
    cfs.change_trade_payables = -(
        current_buckets["trade_payables"] - prior_buckets["trade_payables"]
    )
    cfs.change_tax_payables = -(
        current_buckets["tax_payables"] - prior_buckets["tax_payables"]
    )

    # ── Net Operating Cash Flow ─────────────────────────────────────
    cfs.net_operating_cash = (
        cfs.net_income
        + cfs.depreciation_amortization
        + cfs.change_receivables
        + cfs.change_inventory
        + cfs.change_prepaid
        + cfs.change_trade_payables
        + cfs.change_tax_payables
    )

    # ── Step 7: Investing activities ────────────────────────────────
    # Capex = change in gross fixed assets (net of accumulated depreciation
    # that is already added back above as D&A).
    # Gross fixed asset change = current_fixed - prior_fixed
    # But depreciation is a contra bucket. The net PP&E on BS is
    # fixed_assets + depreciation (depreciation bucket is negative).
    # Capex (cash outflow) = change in gross fixed assets:
    #   = (current_fixed - prior_fixed) + (current_depr - prior_depr)
    # The D&A add-back in operating section covers the depreciation
    # expense, so for capex we look at gross fixed asset movement
    # plus the depreciation movement (which offsets the D&A add-back
    # for the portion related to existing assets).
    gross_fa_change = (
        current_buckets["fixed_assets"] - prior_buckets["fixed_assets"]
    )
    depr_change = (
        current_buckets["depreciation"] - prior_buckets["depreciation"]
    )
    # Capex = change in gross fixed assets. Depreciation change represents
    # the offset; net PP&E change = gross_fa_change + depr_change.
    # Capex as cash outflow should be negative on the CFS.
    cfs.capex = -(gross_fa_change + depr_change)

    # Intangible asset changes (including amortization contra)
    intangible_change = (
        current_buckets["intangibles"] - prior_buckets["intangibles"]
    )
    cfs.intangible_purchases = -intangible_change

    # Other investing (deferred tax assets, LT investments)
    other_inv_change = (
        current_buckets["deferred_tax_assets"] - prior_buckets["deferred_tax_assets"]
    )
    cfs.other_investing = -other_inv_change

    cfs.net_investing_cash = (
        cfs.capex + cfs.intangible_purchases + cfs.other_investing
    )

    # ── Step 8: Financing activities ────────────────────────────────
    # Debt changes: liability buckets store net = DR - CR. An increase
    # in debt (credit entry) makes bucket more negative. So change
    # in liability for CFS = -(current - prior).
    cfs.change_short_term_debt = -(
        current_buckets["short_term_debt"] - prior_buckets["short_term_debt"]
    )
    cfs.change_long_term_debt = -(
        current_buckets["long_term_debt"] - prior_buckets["long_term_debt"]
    )

    # Equity changes (excluding retained earnings which flow from NI)
    # Equity bucket follows same convention as liabilities.
    cfs.change_equity = -(
        current_buckets["equity"] - prior_buckets["equity"]
    )

    cfs.net_financing_cash = (
        cfs.change_short_term_debt
        + cfs.change_long_term_debt
        + cfs.change_equity
    )

    # ── Step 9: Cash reconciliation ─────────────────────────────────
    cfs.net_change_in_cash = (
        cfs.net_operating_cash + cfs.net_investing_cash + cfs.net_financing_cash
    )

    # Beginning cash = prior period ending cash (from BS buckets)
    cfs.beginning_cash = prior_buckets["cash"]
    cfs.ending_cash = cfs.beginning_cash + cfs.net_change_in_cash

    # Cross-validate: ending cash from CFS should match BS cash balance
    cfs.ending_cash_per_bs = current_buckets["cash"]
    cfs.cash_discrepancy = round(cfs.ending_cash - cfs.ending_cash_per_bs, 2)

    if abs(cfs.cash_discrepancy) > 0.01:
        logger.warning(
            "Cash discrepancy detected: CFS ending=%.2f, BS cash=%.2f, diff=%.2f",
            cfs.ending_cash, cfs.ending_cash_per_bs, cfs.cash_discrepancy,
        )

    # ── Step 10: Handle no-prior-period case ────────────────────────
    if not has_prior:
        cfs.note = (
            "No prior period available. Values represent absolute balances "
            "for the current period rather than period-over-period changes."
        )
        logger.info("CFS built without prior period -- absolute values shown.")
    else:
        logger.info(
            "CFS complete: operating=%.2f, investing=%.2f, financing=%.2f, "
            "net_change=%.2f, ending_cash=%.2f",
            cfs.net_operating_cash, cfs.net_investing_cash,
            cfs.net_financing_cash, cfs.net_change_in_cash, cfs.ending_cash,
        )

    return cfs
