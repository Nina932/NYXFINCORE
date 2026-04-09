"""
FinAI v2 — Decimal Financial Math Utilities
=============================================
All financial calculations MUST use these functions instead of raw float arithmetic.

Design principles:
- Every function returns Decimal, never float
- Division by zero returns Decimal("0") or Decimal("Infinity") as appropriate
- Rounding uses ROUND_HALF_UP (standard financial rounding)
- JSON serialization preserves precision via string representation

Usage:
    from app.services.v2.decimal_utils import to_decimal, safe_divide, pct_change, round_fin
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP, InvalidOperation, DivisionByZero
from typing import Any, Optional, Union

# Standard financial precision: 2 decimal places
FINANCIAL_PRECISION = Decimal("0.01")
# Extended precision for intermediate calculations: 8 decimal places
CALC_PRECISION = Decimal("0.00000001")


def to_decimal(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    """Convert any value to Decimal safely.

    Handles: int, float, str, Decimal, None.
    For float inputs, converts via str() to preserve displayed precision.

    >>> to_decimal(0.1) + to_decimal(0.2) == to_decimal("0.3")
    True
    >>> to_decimal(None)
    Decimal('0')
    >>> to_decimal("1,234.56")  # handles comma-formatted numbers
    Decimal('1234.56')
    """
    if value is None:
        return default
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        return Decimal("1") if value else Decimal("0")
    if isinstance(value, (int,)):
        return Decimal(value)
    if isinstance(value, float):
        # Convert via string to preserve the displayed precision
        # float(0.1) -> "0.1" -> Decimal("0.1") (exact)
        # Direct Decimal(0.1) would give Decimal('0.1000000000000000055511151231257827021181583404541015625')
        return Decimal(str(value))
    if isinstance(value, str):
        # Handle comma-formatted numbers
        cleaned = value.strip().replace(",", "").replace(" ", "")
        if not cleaned or cleaned in ("-", ".", "N/A", "n/a", "None", "null"):
            return default
        try:
            return Decimal(cleaned)
        except (InvalidOperation, ValueError):
            return default
    # Fallback
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return default


def safe_divide(
    numerator: Any,
    denominator: Any,
    default: Decimal = Decimal("0"),
    precision: Decimal = FINANCIAL_PRECISION,
) -> Decimal:
    """Divide two values safely, returning Decimal.

    Returns `default` if denominator is zero or conversion fails.

    >>> safe_divide(100, 3)
    Decimal('33.33')
    >>> safe_divide(100, 0)
    Decimal('0')
    >>> safe_divide(100, 0, default=Decimal("Infinity"))
    Decimal('Infinity')
    """
    try:
        num = to_decimal(numerator)
        den = to_decimal(denominator)
        if den == 0:
            return default
        return (num / den).quantize(precision, rounding=ROUND_HALF_UP)
    except (InvalidOperation, DivisionByZero, ZeroDivisionError):
        return default


def pct_change(
    old_value: Any,
    new_value: Any,
    precision: Decimal = FINANCIAL_PRECISION,
) -> Optional[Decimal]:
    """Calculate percentage change from old to new value.

    Returns None if old_value is zero (undefined percentage change).

    >>> pct_change(100, 120)
    Decimal('20.00')
    >>> pct_change(0, 100) is None
    True
    >>> pct_change(100, 80)
    Decimal('-20.00')
    """
    old = to_decimal(old_value)
    new = to_decimal(new_value)
    if old == 0:
        return None  # Undefined: can't calculate % change from zero
    change = ((new - old) / abs(old)) * Decimal("100")
    return change.quantize(precision, rounding=ROUND_HALF_UP)


def round_fin(
    value: Any,
    precision: Decimal = FINANCIAL_PRECISION,
) -> Decimal:
    """Round a value to financial precision (2 decimal places by default).

    >>> round_fin(Decimal("123.456"))
    Decimal('123.46')
    >>> round_fin(Decimal("123.455"))
    Decimal('123.46')  # ROUND_HALF_UP
    >>> round_fin(Decimal("123.444"))
    Decimal('123.44')
    """
    d = to_decimal(value)
    try:
        return d.quantize(precision, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return d  # Infinity, NaN — return as-is


def decimal_to_json(value: Decimal) -> str:
    """Convert Decimal to a JSON-safe string representation.

    Always returns a string to preserve full precision.
    Use this when serializing financial values to JSON/API responses.

    >>> decimal_to_json(Decimal("1234.56"))
    '1234.56'
    """
    if value is None:
        return "0.00"
    return str(round_fin(value))


def sum_decimals(*values: Any) -> Decimal:
    """Sum multiple values as Decimals.

    >>> sum_decimals(10.5, 20.3, "30.2")
    Decimal('61.00')
    """
    total = Decimal("0")
    for v in values:
        total += to_decimal(v)
    return round_fin(total)


def multiply(a: Any, b: Any, precision: Decimal = FINANCIAL_PRECISION) -> Decimal:
    """Multiply two values as Decimals.

    >>> multiply(100, Decimal("0.15"))
    Decimal('15.00')
    """
    result = to_decimal(a) * to_decimal(b)
    return result.quantize(precision, rounding=ROUND_HALF_UP)


def apply_pct(base: Any, pct: Any, precision: Decimal = FINANCIAL_PRECISION) -> Decimal:
    """Apply a percentage change to a base value.

    >>> apply_pct(1000, 10)  # 1000 * (1 + 10/100)
    Decimal('1100.00')
    >>> apply_pct(1000, -20)
    Decimal('800.00')
    """
    b = to_decimal(base)
    p = to_decimal(pct)
    result = b * (Decimal("1") + p / Decimal("100"))
    return result.quantize(precision, rounding=ROUND_HALF_UP)


def is_zero(value: Any, tolerance: Decimal = FINANCIAL_PRECISION) -> bool:
    """Check if a value is effectively zero within financial tolerance.

    >>> is_zero(Decimal("0.001"))
    True
    >>> is_zero(Decimal("0.05"))
    False
    """
    d = to_decimal(value)
    return abs(d) < tolerance
