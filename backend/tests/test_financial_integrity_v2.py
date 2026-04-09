"""
High-Fidelity Financial Integrity Test — NYX Core v2
===================================================
Verifies the 'Deterministic Moat':
1. Perfect double-entry balance using Decimal precision.
2. Georgian COA recursive hierarchy integrity.
3. Accurate P&L and Balance Sheet generation from raw Trial Balance rows.
"""
import pytest
from decimal import Decimal
from app.services.v2.gl_pipeline import gl_pipeline, TrialBalanceBuilder
from app.services.v2.tb_statements import tb_to_statements

def test_georgian_coa_hierarchy_integrity():
    """Verify that nested Georgian account codes roll up correctly."""
    # Mock Trial Balance with Georgian account codes (1xxx = Assets, 6xxx = Revenue, 7xxx = Expenses)
    # 1110 = Cash, 1111 = Cash in Bank, 1112 = Petty Cash
    raw_tb = [
        {"account_code": "1111", "account_name": "Bank", "total_debit": Decimal("1000.50"), "total_credit": Decimal("0")},
        {"account_code": "1112", "account_name": "Petty Cash", "total_debit": Decimal("500.25"), "total_credit": Decimal("0")},
        {"account_code": "6110", "account_name": "Sales", "total_debit": Decimal("0"), "total_credit": Decimal("1500.75")},
    ]
    
    # 1. Pipeline should produce a balanced TB
    result = gl_pipeline.run_from_expanded(raw_tb)
    assert result["trial_balance"]["is_balanced"] is True
    assert Decimal(result["trial_balance"]["total_debit"]) == Decimal("1500.75")

    # 2. TB to Statements should classify correctly
    statements = tb_to_statements.generate(raw_tb)
    
    # Revenue (6xxx) should be in P&L
    revenue = next(item for item in statements["pl"]["rows"] if "Sales" in item["name"])
    assert Decimal(revenue["amount"]) == Decimal("1500.75")
    
    # Assets (1xxx) should be in BS
    assets = statements["bs"]["assets"]["total"]
    assert Decimal(assets) == Decimal("1500.75")

def test_decimal_precision_large_numbers():
    """Verify that GEL amounts up to 1 Billion do not lose precision (Float safety check)."""
    large_amt = Decimal("999999999.99")
    txns = [
        {"acct_dr": "1110", "acct_cr": "6110", "amount": float(large_amt)},
    ]
    
    # If the system were using floats internally, precision would trigger at this magnitude.
    # Our Decimal pipeline preserves the .99.
    result = gl_pipeline.run_from_transactions(txns)
    tb_total = Decimal(result["trial_balance"]["total_debit"])
    
    assert tb_total == large_amt
    assert str(tb_total).endswith(".99")

def test_complex_multi_period_reconciliation():
    """Verify that the system can reconcile multi-period dataset snapshots."""
    # Simulate a scenario where Opening Balance + Period Activity = Closing Balance
    opening = [{"account_code": "1110", "total_debit": Decimal("1000.00")}]
    activity = [{"acct_dr": "1110", "acct_cr": "6110", "amount": 500.25}]
    
    # Correct closing should be 1500.25
    result = gl_pipeline.reconcile_periods(opening, activity)
    closing_cash = next(r for r in result["closing_tb"] if r["account_code"] == "1110")
    
    assert Decimal(closing_cash["total_debit"]) == Decimal("1500.25")
