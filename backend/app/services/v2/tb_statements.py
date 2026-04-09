"""
FinAI v2 TB-to-Statements — Decimal adapter for DerivedStatements.
===================================================================
Wraps the existing tb_to_statements.py (983 lines of classification logic)
with a Decimal conversion layer. The classification rules are sound — only
the output precision needs fixing.

Strategy: Run v1 classification → convert all float outputs to Decimal.
This preserves the complex account hierarchy logic while eliminating
IEEE 754 precision loss at the output boundary.

Public API:
    from app.services.v2.tb_statements import convert_tb_to_decimal_statements
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.services.v2.decimal_utils import to_decimal, safe_divide, round_fin, is_zero

logger = logging.getLogger(__name__)
D = Decimal


@dataclass
class DecimalStatements:
    """P&L and BS with Decimal precision — converted from DerivedStatements."""
    # P&L
    revenue: Decimal = field(default_factory=lambda: D("0"))
    revenue_wholesale: Decimal = field(default_factory=lambda: D("0"))
    revenue_retail: Decimal = field(default_factory=lambda: D("0"))
    revenue_other: Decimal = field(default_factory=lambda: D("0"))
    cogs: Decimal = field(default_factory=lambda: D("0"))
    gross_profit: Decimal = field(default_factory=lambda: D("0"))
    selling_expenses: Decimal = field(default_factory=lambda: D("0"))
    admin_expenses: Decimal = field(default_factory=lambda: D("0"))
    labour_costs: Decimal = field(default_factory=lambda: D("0"))
    ga_expenses: Decimal = field(default_factory=lambda: D("0"))
    ebitda: Decimal = field(default_factory=lambda: D("0"))
    depreciation: Decimal = field(default_factory=lambda: D("0"))
    ebit: Decimal = field(default_factory=lambda: D("0"))
    finance_income: Decimal = field(default_factory=lambda: D("0"))
    finance_expense: Decimal = field(default_factory=lambda: D("0"))
    other_income: Decimal = field(default_factory=lambda: D("0"))
    other_expense: Decimal = field(default_factory=lambda: D("0"))
    profit_before_tax: Decimal = field(default_factory=lambda: D("0"))
    tax_expense: Decimal = field(default_factory=lambda: D("0"))
    net_profit: Decimal = field(default_factory=lambda: D("0"))

    # BS
    cash: Decimal = field(default_factory=lambda: D("0"))
    receivables: Decimal = field(default_factory=lambda: D("0"))
    inventory: Decimal = field(default_factory=lambda: D("0"))
    prepayments: Decimal = field(default_factory=lambda: D("0"))
    other_current_assets: Decimal = field(default_factory=lambda: D("0"))
    total_current_assets: Decimal = field(default_factory=lambda: D("0"))
    fixed_assets: Decimal = field(default_factory=lambda: D("0"))
    accumulated_depreciation: Decimal = field(default_factory=lambda: D("0"))
    intangible_assets: Decimal = field(default_factory=lambda: D("0"))
    other_noncurrent_assets: Decimal = field(default_factory=lambda: D("0"))
    total_noncurrent_assets: Decimal = field(default_factory=lambda: D("0"))
    total_assets: Decimal = field(default_factory=lambda: D("0"))
    payables: Decimal = field(default_factory=lambda: D("0"))
    short_term_debt: Decimal = field(default_factory=lambda: D("0"))
    tax_payable: Decimal = field(default_factory=lambda: D("0"))
    other_current_liabilities: Decimal = field(default_factory=lambda: D("0"))
    total_current_liabilities: Decimal = field(default_factory=lambda: D("0"))
    long_term_debt: Decimal = field(default_factory=lambda: D("0"))
    deferred_tax: Decimal = field(default_factory=lambda: D("0"))
    other_noncurrent_liabilities: Decimal = field(default_factory=lambda: D("0"))
    total_noncurrent_liabilities: Decimal = field(default_factory=lambda: D("0"))
    total_liabilities: Decimal = field(default_factory=lambda: D("0"))
    share_capital: Decimal = field(default_factory=lambda: D("0"))
    retained_earnings: Decimal = field(default_factory=lambda: D("0"))
    reserves: Decimal = field(default_factory=lambda: D("0"))
    total_equity: Decimal = field(default_factory=lambda: D("0"))

    # Ratios (Decimal)
    current_ratio: Optional[Decimal] = None
    debt_to_equity: Optional[Decimal] = None
    gross_margin: Optional[Decimal] = None
    ebitda_margin: Optional[Decimal] = None
    net_margin: Optional[Decimal] = None

    # Metadata (preserved from v1)
    account_classifications: List[Dict] = field(default_factory=list)
    unclassified_accounts: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    bs_equation_holds: bool = False
    bs_imbalance: Decimal = field(default_factory=lambda: D("0"))

    def to_financials_dict(self) -> Dict[str, str]:
        """Return all financial values as string-encoded Decimals."""
        return {
            "revenue": str(round_fin(self.revenue)),
            "cogs": str(round_fin(self.cogs)),
            "gross_profit": str(round_fin(self.gross_profit)),
            "ga_expenses": str(round_fin(self.ga_expenses)),
            "ebitda": str(round_fin(self.ebitda)),
            "depreciation": str(round_fin(self.depreciation)),
            "ebit": str(round_fin(self.ebit)),
            "net_profit": str(round_fin(self.net_profit)),
            "total_assets": str(round_fin(self.total_assets)),
            "total_liabilities": str(round_fin(self.total_liabilities)),
            "total_equity": str(round_fin(self.total_equity)),
            "current_ratio": str(round_fin(self.current_ratio)) if self.current_ratio else None,
            "gross_margin_pct": str(round_fin(self.gross_margin)) if self.gross_margin else None,
            "ebitda_margin_pct": str(round_fin(self.ebitda_margin)) if self.ebitda_margin else None,
            "net_margin_pct": str(round_fin(self.net_margin)) if self.net_margin else None,
            "bs_equation_holds": self.bs_equation_holds,
            "bs_imbalance": str(round_fin(self.bs_imbalance)),
        }


# ── Float-to-Decimal fields map ──────────────────────────────────────

_FINANCIAL_FIELDS = [
    "revenue", "revenue_wholesale", "revenue_retail", "revenue_other",
    "cogs", "gross_profit", "selling_expenses", "admin_expenses",
    "labour_costs", "ga_expenses", "ebitda", "depreciation", "ebit",
    "finance_income", "finance_expense", "other_income", "other_expense",
    "profit_before_tax", "tax_expense", "net_profit",
    "cash", "receivables", "inventory", "prepayments",
    "other_current_assets", "total_current_assets",
    "fixed_assets", "accumulated_depreciation", "intangible_assets",
    "other_noncurrent_assets", "total_noncurrent_assets", "total_assets",
    "payables", "short_term_debt", "tax_payable",
    "other_current_liabilities", "total_current_liabilities",
    "long_term_debt", "deferred_tax", "other_noncurrent_liabilities",
    "total_noncurrent_liabilities", "total_liabilities",
    "share_capital", "retained_earnings", "reserves", "total_equity",
]

_RATIO_FIELDS = [
    "current_ratio", "debt_to_equity", "gross_margin",
    "ebitda_margin", "net_margin",
]


def convert_to_decimal_statements(v1_result) -> DecimalStatements:
    """Convert a v1 DerivedStatements (float) to DecimalStatements (Decimal).

    This is the boundary conversion — all downstream v2 code works with Decimal.
    """
    ds = DecimalStatements()

    # Convert all financial fields
    for fld in _FINANCIAL_FIELDS:
        val = getattr(v1_result, fld, 0.0)
        setattr(ds, fld, to_decimal(val))

    # Convert ratios (may be 0.0 for undefined)
    for fld in _RATIO_FIELDS:
        val = getattr(v1_result, fld, 0.0)
        if val != 0:
            setattr(ds, fld, to_decimal(val))
        else:
            setattr(ds, fld, None)

    # Recalculate ratios with Decimal for precision
    if not is_zero(ds.total_current_liabilities):
        ds.current_ratio = safe_divide(ds.total_current_assets, ds.total_current_liabilities)
    if not is_zero(ds.total_equity):
        ds.debt_to_equity = safe_divide(ds.total_liabilities, ds.total_equity)
    if not is_zero(ds.revenue):
        ds.gross_margin = safe_divide(ds.gross_profit * D("100"), ds.revenue)
        ds.ebitda_margin = safe_divide(ds.ebitda * D("100"), ds.revenue)
        ds.net_margin = safe_divide(ds.net_profit * D("100"), ds.revenue)

    # Recheck BS equation with Decimal precision (₾1 tolerance)
    ds.bs_imbalance = abs(ds.total_assets - ds.total_liabilities - ds.total_equity)
    ds.bs_equation_holds = ds.bs_imbalance < D("1")

    # Preserve metadata
    ds.account_classifications = getattr(v1_result, "account_classifications", [])
    ds.unclassified_accounts = getattr(v1_result, "unclassified_accounts", [])
    ds.warnings = list(getattr(v1_result, "warnings", []))

    if not ds.bs_equation_holds:
        ds.warnings.append(
            f"BS imbalance: {round_fin(ds.bs_imbalance)} GEL "
            f"(Assets={round_fin(ds.total_assets)}, L+E={round_fin(ds.total_liabilities + ds.total_equity)})"
        )

    return ds


def convert_tb_to_decimal_statements(tb_parse_result) -> DecimalStatements:
    """Full pipeline: TB → v1 classify → Decimal convert.

    Usage:
        from app.services.tb_parser import TBParser
        tb = TBParser().parse(items)
        result = convert_tb_to_decimal_statements(tb)
    """
    from app.services.tb_to_statements import TBToStatements

    converter = TBToStatements()
    v1_result = converter.convert(tb_parse_result)
    return convert_to_decimal_statements(v1_result)
