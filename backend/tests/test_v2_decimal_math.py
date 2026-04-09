"""
Test Suite: v2 Decimal Math Utilities
======================================
Verifies financial math precision, edge cases, and correctness.
"""
import pytest
from decimal import Decimal
from app.services.v2.decimal_utils import (
    to_decimal, safe_divide, pct_change, round_fin,
    apply_pct, is_zero, sum_decimals, multiply,
)


class TestToDecimal:
    def test_float_precision(self):
        """0.1 + 0.2 must equal 0.3 (float would give 0.30000000000000004)."""
        assert to_decimal(0.1) + to_decimal(0.2) == Decimal("0.3")

    def test_none(self):
        assert to_decimal(None) == Decimal("0")

    def test_string_comma(self):
        assert to_decimal("1,234.56") == Decimal("1234.56")

    def test_negative(self):
        assert to_decimal(-42.5) == Decimal("-42.5")

    def test_bool(self):
        assert to_decimal(True) == Decimal("1")
        assert to_decimal(False) == Decimal("0")

    def test_invalid_string(self):
        assert to_decimal("N/A") == Decimal("0")
        assert to_decimal("null") == Decimal("0")


class TestSafeDivide:
    def test_normal(self):
        assert safe_divide(100, 3) == Decimal("33.33")

    def test_zero_denominator(self):
        assert safe_divide(100, 0) == Decimal("0")

    def test_custom_default(self):
        assert safe_divide(100, 0, default=Decimal("Infinity")) == Decimal("Infinity")

    def test_precision(self):
        result = safe_divide(1, 3, precision=Decimal("0.0001"))
        assert result == Decimal("0.3333")


class TestPctChange:
    def test_positive(self):
        assert pct_change(100, 120) == Decimal("20.00")

    def test_negative(self):
        assert pct_change(100, 80) == Decimal("-20.00")

    def test_zero_base(self):
        """Division by zero must return None, not 0.0 (v1 bug)."""
        assert pct_change(0, 100) is None

    def test_no_change(self):
        assert pct_change(100, 100) == Decimal("0.00")


class TestApplyPct:
    def test_increase(self):
        assert apply_pct(1000, 10) == Decimal("1100.00")

    def test_decrease(self):
        assert apply_pct(1000, -20) == Decimal("800.00")


class TestRoundFin:
    def test_half_up(self):
        """ROUND_HALF_UP: 0.455 → 0.46 (not 0.45 like banker's rounding)."""
        assert round_fin(Decimal("123.455")) == Decimal("123.46")

    def test_normal(self):
        assert round_fin(Decimal("123.444")) == Decimal("123.44")


class TestIsZero:
    def test_small(self):
        assert is_zero(Decimal("0.001")) is True

    def test_not_zero(self):
        assert is_zero(Decimal("0.05")) is False


class TestSumDecimals:
    def test_mixed_types(self):
        result = sum_decimals(10.5, 20.3, "30.2")
        assert result == Decimal("61.00")
