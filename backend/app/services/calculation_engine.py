"""
FinAI Calculation Engine — Decimal-precise financial mathematics.

Problem: Python floats introduce rounding errors in financial calculations.
  float(51163022.93) - float(44572371.58) = 6590651.349999...  (wrong!)
  Decimal("51163022.93") - Decimal("44572371.58") = Decimal("6590651.35")  (exact!)

Solution: All financial math goes through this module.
  - DB stores Float (SQLite limitation) — we convert at boundaries
  - All intermediate calculations use Decimal
  - Results round to 2 decimal places before returning

Usage:
    from app.services.calculation_engine import FinancialDecimal as FD

    revenue = FD.from_float(51163022.93)
    cogs = FD.from_float(44572371.58)
    gross_profit = FD.subtract(revenue, cogs)  # Decimal("6590651.35")
    margin = FD.margin(revenue, cogs)           # Decimal("12.88") (percent)
    formatted = FD.format_gel(gross_profit)     # "₾6,590,651.35"
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

logger = logging.getLogger(__name__)

# Standard financial precision: 2 decimal places
TWO_PLACES = Decimal("0.01")
FOUR_PLACES = Decimal("0.0001")
ZERO = Decimal("0")
HUNDRED = Decimal("100")


class FinancialDecimal:
    """Static utility class for Decimal-precise financial math.

    Every method accepts floats, ints, strings, or Decimals and
    converts them to Decimal internally. Returns Decimal.
    """

    # ── Conversion ───────────────────────────────────────────────────────

    @staticmethod
    def to_decimal(value: Any) -> Decimal:
        """Convert any numeric value to Decimal safely.

        Key: `Decimal(str(float_value))` preserves the human-readable digits.
        `Decimal(float_value)` does NOT — it captures the full IEEE 754 representation.
        """
        if value is None:
            return ZERO
        if isinstance(value, Decimal):
            return value
        if isinstance(value, (int, float)):
            return Decimal(str(value))
        if isinstance(value, str):
            try:
                return Decimal(value.replace(",", "").strip())
            except InvalidOperation:
                logger.warning("Cannot convert '%s' to Decimal — returning 0", value)
                return ZERO
        logger.warning("Unexpected type %s for Decimal conversion — returning 0", type(value))
        return ZERO

    @staticmethod
    def from_float(value: float) -> Decimal:
        """Alias for to_decimal — explicit about the source type."""
        return FinancialDecimal.to_decimal(value)

    @staticmethod
    def to_float(value: Decimal) -> float:
        """Convert Decimal back to float for DB storage. Rounds to 2 places first."""
        if isinstance(value, Decimal):
            return float(value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP))
        return float(value)

    @staticmethod
    def round2(value: Any) -> Decimal:
        """Round to 2 decimal places (standard financial rounding)."""
        d = FinancialDecimal.to_decimal(value)
        return d.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    @staticmethod
    def round4(value: Any) -> Decimal:
        """Round to 4 decimal places (for rates, percentages)."""
        d = FinancialDecimal.to_decimal(value)
        return d.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)

    # ── Arithmetic ───────────────────────────────────────────────────────

    @staticmethod
    def add(*values: Any) -> Decimal:
        """Sum multiple values with Decimal precision."""
        return sum(
            (FinancialDecimal.to_decimal(v) for v in values),
            ZERO,
        )

    @staticmethod
    def subtract(a: Any, b: Any) -> Decimal:
        """a - b with Decimal precision."""
        return FinancialDecimal.to_decimal(a) - FinancialDecimal.to_decimal(b)

    @staticmethod
    def multiply(a: Any, b: Any) -> Decimal:
        """a * b with Decimal precision."""
        return FinancialDecimal.to_decimal(a) * FinancialDecimal.to_decimal(b)

    @staticmethod
    def divide(a: Any, b: Any, default: Decimal = ZERO) -> Decimal:
        """a / b with Decimal precision. Returns `default` if b is zero."""
        divisor = FinancialDecimal.to_decimal(b)
        if divisor == ZERO:
            return default
        return FinancialDecimal.to_decimal(a) / divisor

    @staticmethod
    def sum_list(values: Sequence[Any]) -> Decimal:
        """Sum a list/sequence of values."""
        return sum(
            (FinancialDecimal.to_decimal(v) for v in values),
            ZERO,
        )

    @staticmethod
    def negate(value: Any) -> Decimal:
        """Return -value."""
        return -FinancialDecimal.to_decimal(value)

    @staticmethod
    def abs(value: Any) -> Decimal:
        """Return absolute value."""
        return abs(FinancialDecimal.to_decimal(value))

    # ── Financial Calculations ───────────────────────────────────────────

    @staticmethod
    def margin(revenue: Any, cost: Any) -> Decimal:
        """Calculate margin percentage: ((revenue - cost) / revenue) * 100.

        Returns 0 if revenue is zero.
        """
        r = FinancialDecimal.to_decimal(revenue)
        c = FinancialDecimal.to_decimal(cost)
        if r == ZERO:
            return ZERO
        return ((r - c) / r * HUNDRED).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    @staticmethod
    def gross_profit(revenue: Any, cogs: Any) -> Decimal:
        """Revenue - COGS."""
        return FinancialDecimal.subtract(revenue, cogs)

    @staticmethod
    def growth_rate(current: Any, previous: Any) -> Decimal:
        """Period-over-period growth: ((current - previous) / |previous|) * 100.

        Returns 0 if previous is zero.
        """
        c = FinancialDecimal.to_decimal(current)
        p = FinancialDecimal.to_decimal(previous)
        if p == ZERO:
            return ZERO
        return ((c - p) / abs(p) * HUNDRED).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    @staticmethod
    def variance(actual: Any, budget: Any) -> Tuple[Decimal, Decimal]:
        """Calculate variance and variance percentage.

        Returns: (variance_amount, variance_pct)
        """
        a = FinancialDecimal.to_decimal(actual)
        b = FinancialDecimal.to_decimal(budget)
        var = a - b
        pct = ZERO
        if b != ZERO:
            pct = (var / abs(b) * HUNDRED).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        return (var, pct)

    @staticmethod
    def percentage_of(part: Any, whole: Any) -> Decimal:
        """(part / whole) * 100, rounded to 2 places."""
        w = FinancialDecimal.to_decimal(whole)
        if w == ZERO:
            return ZERO
        p = FinancialDecimal.to_decimal(part)
        return (p / w * HUNDRED).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    @staticmethod
    def allocate(total: Any, weights: Sequence[Any]) -> List[Decimal]:
        """Allocate a total amount by weights, ensuring exact distribution.

        The last bucket absorbs any rounding residual so the parts
        sum to exactly `total`.
        """
        t = FinancialDecimal.to_decimal(total)
        weight_decimals = [FinancialDecimal.to_decimal(w) for w in weights]
        weight_sum = sum(weight_decimals, ZERO)

        if weight_sum == ZERO or not weight_decimals:
            return [ZERO] * len(weights)

        parts = []
        allocated = ZERO
        for i, w in enumerate(weight_decimals):
            if i == len(weight_decimals) - 1:
                # Last bucket gets the remainder
                parts.append(t - allocated)
            else:
                share = (t * w / weight_sum).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
                parts.append(share)
                allocated += share

        return parts

    # ── Currency Conversion ──────────────────────────────────────────────

    @staticmethod
    def convert(amount: Any, rate: Any) -> Decimal:
        """Convert amount by exchange rate, rounded to 2 places."""
        result = FinancialDecimal.multiply(amount, rate)
        return result.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    # ── Formatting ───────────────────────────────────────────────────────

    @staticmethod
    def format_gel(value: Any) -> str:
        """Format as GEL currency: ₾1,234,567.89"""
        d = FinancialDecimal.round2(value)
        sign = "-" if d < ZERO else ""
        d = abs(d)
        integer_part = int(d)
        decimal_part = d - Decimal(integer_part)
        formatted = f"{integer_part:,}"
        cents = str(decimal_part.quantize(TWO_PLACES))[2:]  # "0.XX" → "XX"
        return f"{sign}₾{formatted}.{cents}"

    @staticmethod
    def format_usd(value: Any) -> str:
        """Format as USD currency: $1,234,567.89"""
        d = FinancialDecimal.round2(value)
        sign = "-" if d < ZERO else ""
        d = abs(d)
        integer_part = int(d)
        decimal_part = d - Decimal(integer_part)
        formatted = f"{integer_part:,}"
        cents = str(decimal_part.quantize(TWO_PLACES))[2:]
        return f"{sign}${formatted}.{cents}"

    @staticmethod
    def format_number(value: Any, decimals: int = 2) -> str:
        """Format with thousands separator: 1,234,567.89"""
        d = FinancialDecimal.to_decimal(value)
        places = Decimal(10) ** -decimals
        d = d.quantize(places, rounding=ROUND_HALF_UP)
        sign = "-" if d < ZERO else ""
        d = abs(d)
        integer_part = int(d)
        decimal_part = d - Decimal(integer_part)
        formatted = f"{integer_part:,}"
        if decimals > 0:
            dec_str = str(decimal_part.quantize(places))[2:]
            return f"{sign}{formatted}.{dec_str}"
        return f"{sign}{formatted}"

    @staticmethod
    def format_percent(value: Any) -> str:
        """Format as percentage: 12.88%"""
        d = FinancialDecimal.round2(value)
        return f"{d}%"


# ═══════════════════════════════════════════════════════════════════════════════
# INCOME STATEMENT — Decimal-precise P&L structure
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class DecimalIncomeStatement:
    """P&L waterfall with exact Decimal precision.

    Wraps the existing `build_income_statement()` output and recalculates
    all derived figures (margins, subtotals) using Decimal math.
    """

    # Revenue
    revenue_wholesale: Decimal = ZERO
    revenue_retail: Decimal = ZERO
    revenue_other: Decimal = ZERO
    total_revenue: Decimal = ZERO

    # COGS
    cogs_wholesale: Decimal = ZERO
    cogs_retail: Decimal = ZERO
    cogs_other: Decimal = ZERO
    total_cogs: Decimal = ZERO

    # Gross Profit
    gross_profit: Decimal = ZERO
    gross_margin_pct: Decimal = ZERO

    # Operating Expenses
    ga_expenses: Decimal = ZERO          # G&A / SGA
    depreciation: Decimal = ZERO         # D&A (8410/8420)
    other_operating: Decimal = ZERO

    # Derived
    ebitda: Decimal = ZERO
    ebit: Decimal = ZERO

    # Below the line
    other_income: Decimal = ZERO
    other_expense: Decimal = ZERO
    finance_income: Decimal = ZERO
    finance_expense: Decimal = ZERO

    # Tax & Net
    profit_before_tax: Decimal = ZERO
    income_tax: Decimal = ZERO
    net_profit: Decimal = ZERO
    net_margin_pct: Decimal = ZERO

    # Metadata
    period: str = ""
    currency: str = "GEL"
    dataset_id: Optional[int] = None

    def calculate_derived(self) -> None:
        """Recompute all derived fields from component values."""
        FD = FinancialDecimal

        self.total_revenue = FD.add(
            self.revenue_wholesale, self.revenue_retail, self.revenue_other
        )
        self.total_cogs = FD.add(
            self.cogs_wholesale, self.cogs_retail, self.cogs_other
        )
        self.gross_profit = FD.subtract(self.total_revenue, self.total_cogs)
        self.gross_margin_pct = FD.margin(self.total_revenue, self.total_cogs)

        self.ebitda = FD.subtract(self.gross_profit, self.ga_expenses)
        self.ebit = FD.subtract(self.ebitda, self.depreciation)

        self.profit_before_tax = FD.add(
            self.ebit,
            self.other_income,
            FD.negate(self.other_expense),
            self.finance_income,
            FD.negate(self.finance_expense),
        )
        self.net_profit = FD.subtract(self.profit_before_tax, self.income_tax)
        self.net_margin_pct = FD.margin(self.total_revenue, FD.subtract(self.total_revenue, self.net_profit))

    @classmethod
    def from_float_dict(cls, data: Dict[str, Any], **kwargs) -> "DecimalIncomeStatement":
        """Build from the existing `build_income_statement()` float output.

        Maps the existing output keys to DecimalIncomeStatement fields.
        """
        FD = FinancialDecimal
        stmt = cls(**kwargs)

        # Revenue mapping
        stmt.revenue_wholesale = FD.from_float(data.get("revenue_wholesale", 0))
        stmt.revenue_retail = FD.from_float(data.get("revenue_retail", 0))
        stmt.revenue_other = FD.from_float(data.get("revenue_other", 0))

        # COGS mapping
        stmt.cogs_wholesale = FD.from_float(data.get("cogs_wholesale", 0))
        stmt.cogs_retail = FD.from_float(data.get("cogs_retail", 0))
        stmt.cogs_other = FD.from_float(data.get("cogs_other", 0))

        # OpEx
        stmt.ga_expenses = FD.from_float(data.get("total_sga", 0) or data.get("ga_expenses", 0))
        stmt.depreciation = FD.from_float(data.get("depreciation_amortization", 0) or data.get("depreciation", 0))
        stmt.other_operating = FD.from_float(data.get("other_operating", 0))

        # Below the line
        stmt.other_income = FD.from_float(data.get("other_income", 0))
        stmt.other_expense = FD.from_float(data.get("other_expense", 0))
        stmt.finance_income = FD.from_float(data.get("finance_income", 0))
        stmt.finance_expense = FD.from_float(data.get("finance_expense", 0))

        # Tax
        stmt.income_tax = FD.from_float(data.get("income_tax", 0))

        # Recalculate all derived fields with Decimal precision
        stmt.calculate_derived()

        return stmt

    def to_dict(self) -> Dict[str, Any]:
        """Export as float dict for JSON serialization / DB storage."""
        FD = FinancialDecimal
        return {
            "revenue_wholesale": FD.to_float(self.revenue_wholesale),
            "revenue_retail": FD.to_float(self.revenue_retail),
            "revenue_other": FD.to_float(self.revenue_other),
            "total_revenue": FD.to_float(self.total_revenue),
            "cogs_wholesale": FD.to_float(self.cogs_wholesale),
            "cogs_retail": FD.to_float(self.cogs_retail),
            "cogs_other": FD.to_float(self.cogs_other),
            "total_cogs": FD.to_float(self.total_cogs),
            "gross_profit": FD.to_float(self.gross_profit),
            "gross_margin_pct": FD.to_float(self.gross_margin_pct),
            "ga_expenses": FD.to_float(self.ga_expenses),
            "depreciation": FD.to_float(self.depreciation),
            "ebitda": FD.to_float(self.ebitda),
            "ebit": FD.to_float(self.ebit),
            "other_income": FD.to_float(self.other_income),
            "other_expense": FD.to_float(self.other_expense),
            "finance_income": FD.to_float(self.finance_income),
            "finance_expense": FD.to_float(self.finance_expense),
            "profit_before_tax": FD.to_float(self.profit_before_tax),
            "income_tax": FD.to_float(self.income_tax),
            "net_profit": FD.to_float(self.net_profit),
            "net_margin_pct": FD.to_float(self.net_margin_pct),
            "period": self.period,
            "currency": self.currency,
        }

    def summary(self) -> str:
        """One-line financial summary."""
        FD = FinancialDecimal
        return (
            f"Revenue {FD.format_gel(self.total_revenue)} | "
            f"GP {FD.format_gel(self.gross_profit)} ({FD.format_percent(self.gross_margin_pct)}) | "
            f"EBITDA {FD.format_gel(self.ebitda)} | "
            f"Net {FD.format_gel(self.net_profit)} ({FD.format_percent(self.net_margin_pct)})"
        )
