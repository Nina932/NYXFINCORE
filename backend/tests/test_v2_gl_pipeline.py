"""
Test Suite: v2 GL Pipeline — Double-Entry Integrity
=====================================================
Verifies debit=credit equality, Decimal precision throughout,
and correct financial statement generation.
"""
import pytest
from decimal import Decimal
from app.services.v2.gl_pipeline import (
    gl_pipeline, TrialBalanceBuilder, TransactionAdapter,
    TrialBalance, TrialBalanceRow,
)


class TestTransactionAdapter:
    def test_expand_produces_decimal(self):
        entries = TransactionAdapter.expand({"acct_dr": "1110", "acct_cr": "6110", "amount": 1000.50})
        assert len(entries) == 2
        assert isinstance(entries[0]["debit"], Decimal)
        assert entries[0]["debit"] == Decimal("1000.5")
        assert entries[1]["credit"] == Decimal("1000.5")

    def test_zero_amount_produces_nothing(self):
        entries = TransactionAdapter.expand({"acct_dr": "1110", "acct_cr": "6110", "amount": 0})
        assert len(entries) == 0

    def test_negative_amount_produces_nothing(self):
        entries = TransactionAdapter.expand({"acct_dr": "1110", "acct_cr": "6110", "amount": -100})
        assert len(entries) == 0


class TestTrialBalance:
    def test_exact_balance(self):
        """Debits must EXACTLY equal credits — no float tolerance needed."""
        txns = [
            {"acct_dr": "1110", "acct_cr": "6110", "amount": 1000.50},
            {"acct_dr": "7310", "acct_cr": "1110", "amount": 500.25},
            {"acct_dr": "8230", "acct_cr": "1110", "amount": 250.10},
        ]
        entries = TransactionAdapter.expand_batch(txns)
        tb = TrialBalanceBuilder().build_from_expanded(entries)

        assert tb.total_debits() == tb.total_credits(), (
            f"TB imbalance: debits={tb.total_debits()} != credits={tb.total_credits()}"
        )
        assert tb.is_balanced()

    def test_serialization_uses_strings(self):
        """to_dict() must use string values (not float) for JSON precision."""
        row = TrialBalanceRow(account_code="1110", total_debit=Decimal("123456.78"))
        d = row.to_dict()
        assert isinstance(d["total_debit"], str)
        assert d["total_debit"] == "123456.78"

    def test_large_balance_sheet(self):
        """Test with large GEL amounts — float would lose precision."""
        entries = [
            {"account_code": "1110", "debit": Decimal("999999999.99"), "credit": Decimal("0")},
            {"account_code": "6110", "debit": Decimal("0"), "credit": Decimal("999999999.99")},
        ]
        tb = TrialBalanceBuilder().build_from_expanded(entries)
        assert tb.total_debits() == Decimal("999999999.99")
        assert tb.is_balanced()

    def test_many_small_transactions(self):
        """Sum of many 0.01 transactions must be exact."""
        entries = []
        for i in range(10000):
            entries.append({"account_code": "1110", "debit": Decimal("0.01"), "credit": Decimal("0")})
            entries.append({"account_code": "6110", "debit": Decimal("0"), "credit": Decimal("0.01")})
        tb = TrialBalanceBuilder().build_from_expanded(entries)
        assert tb.total_debits() == Decimal("100.00")
        assert tb.total_debits() == tb.total_credits()


class TestGLPipeline:
    def test_run_from_transactions(self):
        txns = [
            {"acct_dr": "1110", "acct_cr": "6110", "amount": 50000},
            {"acct_dr": "7310", "acct_cr": "1110", "amount": 30000},
        ]
        result = gl_pipeline.run_from_transactions(txns)
        assert result["trial_balance"]["is_balanced"] is True
        assert "reconciliation" in result

    def test_empty_transactions(self):
        result = gl_pipeline.run_from_transactions([])
        assert result["trial_balance"]["account_count"] == 0
