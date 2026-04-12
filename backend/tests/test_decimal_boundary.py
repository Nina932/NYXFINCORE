"""
test_decimal_boundary.py — Verify the Float/Decimal boundary fix.

Every financial value computed by compute_derived_metrics must be Decimal,
never float. This prevents rounding errors at the ingestion boundary.
"""

import pytest
from decimal import Decimal


class TestDecimalBoundary:
    """Verify compute_derived_metrics outputs Decimal, not float."""

    def test_no_float_in_derived_metrics(self):
        """Every output value must be Decimal, never float."""
        from app.services.smart_excel_parser import compute_derived_metrics

        data = {"revenue": "51163022.93", "cogs": "44572371.58"}
        result, corrections = compute_derived_metrics(data)

        for key, value in result.items():
            if isinstance(value, (int, str, type(None))):
                continue
            assert isinstance(value, Decimal), (
                f"{key} is {type(value).__name__}, expected Decimal"
            )

        assert result["gross_profit"] == Decimal("6590651.35")
        assert result["gross_margin_pct"] == Decimal("12.88")

    def test_float_input_converted_safely(self):
        """Float inputs (from Excel) must be converted via string repr."""
        from app.services.smart_excel_parser import compute_derived_metrics

        data = {"revenue": 51163022.93, "cogs": 44572371.58}
        result, _ = compute_derived_metrics(data)
        assert isinstance(result["gross_profit"], Decimal)

    def test_zero_revenue_no_division_error(self):
        """Zero revenue should not cause division by zero."""
        from app.services.smart_excel_parser import compute_derived_metrics

        data = {"revenue": "0", "cogs": "100"}
        result, corrections = compute_derived_metrics(data)
        # Should compute gross_profit but skip percentages
        assert result["gross_profit"] == Decimal("-100")
        assert "gross_margin_pct" not in result

    def test_none_values_handled(self):
        """None values should not cause errors."""
        from app.services.smart_excel_parser import compute_derived_metrics

        data = {"revenue": None, "cogs": None}
        result, corrections = compute_derived_metrics(data)
        assert "gross_profit" not in result
        assert len(corrections) == 0

    def test_string_numeric_input(self):
        """String numeric values should be parsed correctly."""
        from app.services.smart_excel_parser import compute_derived_metrics

        data = {
            "revenue": "1000000.50",
            "cogs": "600000.30",
            "ga_expenses": "200000.10",
        }
        result, corrections = compute_derived_metrics(data)
        assert result["gross_profit"] == Decimal("400000.20")
        assert result["ebitda"] == Decimal("200000.10")
        assert result["gross_margin_pct"] == Decimal("40.00")

    def test_safe_decimal_function(self):
        """_safe_decimal handles all edge cases."""
        from app.services.smart_excel_parser import _safe_decimal

        assert _safe_decimal(None) is None
        assert _safe_decimal("abc") is None
        assert _safe_decimal(42.5) == Decimal("42.5")
        assert _safe_decimal("42.5") == Decimal("42.5")
        assert _safe_decimal(Decimal("42.5")) == Decimal("42.5")
        assert _safe_decimal(0) == Decimal("0")

    def test_full_pipeline_all_margins_decimal(self):
        """All margin percentages must be Decimal with 2 decimal places."""
        from app.services.smart_excel_parser import compute_derived_metrics

        data = {
            "revenue": "10000000",
            "cogs": "6000000",
            "ga_expenses": "2000000",
            "depreciation": "500000",
            "finance_expense": "200000",
            "tax_expense": "300000",
        }
        result, corrections = compute_derived_metrics(data)

        # All percentage fields must be Decimal
        pct_fields = ["gross_margin_pct", "net_margin_pct", "ebitda_margin_pct", "cogs_to_revenue_pct"]
        for field in pct_fields:
            assert field in result, f"Missing: {field}"
            assert isinstance(result[field], Decimal), f"{field} is not Decimal"

        assert result["gross_margin_pct"] == Decimal("40.00")
        assert result["ebitda_margin_pct"] == Decimal("20.00")
        assert result["cogs_to_revenue_pct"] == Decimal("60.00")
