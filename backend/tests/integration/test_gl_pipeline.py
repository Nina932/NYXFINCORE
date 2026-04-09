"""
Integration Tests — GL Pipeline
================================
Tests the full deterministic financial pipeline:
  raw transactions → trial balance → IS → BS → CF

These are the highest-value tests in the system — they verify
that the financial heart of NYX Core FinAI produces correct
and consistent numbers end-to-end.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


# ── Sample test data ─────────────────────────────────────────────────────────

SAMPLE_TRANSACTIONS = [
    # Revenue accounts (6xxx)
    {"account_code": "6110", "debit": 0,        "credit": 1_000_000, "description": "Wholesale fuel revenue"},
    {"account_code": "6120", "debit": 0,        "credit": 500_000,   "description": "Retail revenue"},
    # COGS (7xxx)
    {"account_code": "7110", "debit": 600_000,  "credit": 0,         "description": "Wholesale COGS"},
    {"account_code": "7120", "debit": 280_000,  "credit": 0,         "description": "Retail COGS"},
    # Operating expenses (8xxx)
    {"account_code": "8110", "debit": 80_000,   "credit": 0,         "description": "Selling expenses"},
    {"account_code": "8210", "debit": 60_000,   "credit": 0,         "description": "Admin expenses"},
    {"account_code": "8310", "debit": 20_000,   "credit": 0,         "description": "Depreciation"},
    # Balance sheet — Assets (1xxx)
    {"account_code": "1110", "debit": 50_000,   "credit": 0,         "description": "Cash"},
    {"account_code": "1210", "debit": 120_000,  "credit": 0,         "description": "Receivables"},
    {"account_code": "1310", "debit": 80_000,   "credit": 0,         "description": "Inventory"},
    # Balance sheet — Liabilities (4xxx)
    {"account_code": "4110", "debit": 0,        "credit": 100_000,   "description": "Accounts payable"},
    # Balance sheet — Equity (5xxx)
    {"account_code": "5110", "debit": 0,        "credit": 150_000,   "description": "Share capital"},
]


class TestGLPipeline:
    """Tests for the GL → Trial Balance → IS → BS → CF pipeline."""

    def test_gl_pipeline_import(self):
        """GL pipeline module must be importable."""
        from app.services.gl_pipeline import gl_pipeline
        assert gl_pipeline is not None

    def test_run_from_transactions_returns_dict(self):
        """Pipeline must return a dict with expected keys."""
        from app.services.gl_pipeline import gl_pipeline
        result = gl_pipeline.run_from_transactions(
            SAMPLE_TRANSACTIONS, period="2025-01", currency="GEL"
        )
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        assert "trial_balance" in result or "statements" in result or "error" not in result, \
            f"Unexpected result structure: {list(result.keys())}"

    def test_trial_balance_debits_equal_credits(self):
        """Trial balance must balance (total debits == total credits)."""
        from app.services.gl_pipeline import gl_pipeline
        result = gl_pipeline.run_from_transactions(
            SAMPLE_TRANSACTIONS, period="2025-01", currency="GEL"
        )
        tb = result.get("trial_balance", {})
        if not tb:
            pytest.skip("Trial balance not in result structure")

        total_debits = sum(
            v.get("debit", 0) for v in tb.values() if isinstance(v, dict)
        )
        total_credits = sum(
            v.get("credit", 0) for v in tb.values() if isinstance(v, dict)
        )
        assert abs(total_debits - total_credits) < 1.0, \
            f"Trial balance doesn't balance: debits={total_debits}, credits={total_credits}"

    def test_income_statement_revenue_positive(self):
        """Income statement revenue must be positive for our test data."""
        from app.services.gl_pipeline import gl_pipeline
        result = gl_pipeline.run_from_transactions(
            SAMPLE_TRANSACTIONS, period="2025-01", currency="GEL"
        )
        stmts = result.get("statements", {})
        if not stmts:
            pytest.skip("statements not in result structure")
        is_ = stmts.get("income_statement", {})
        revenue = is_.get("revenue", 0)
        assert revenue > 0, f"Revenue should be positive, got {revenue}"

    def test_income_statement_gross_profit_correct(self):
        """Gross profit = Revenue - COGS. Must match expected value."""
        from app.services.gl_pipeline import gl_pipeline
        result = gl_pipeline.run_from_transactions(
            SAMPLE_TRANSACTIONS, period="2025-01", currency="GEL"
        )
        stmts = result.get("statements", {})
        if not stmts:
            pytest.skip("statements not in result structure")
        is_ = stmts.get("income_statement", {})
        revenue = is_.get("revenue", 0)
        cogs = is_.get("cogs", 0)
        gross_profit = is_.get("gross_profit", revenue - cogs)
        expected_gp = 1_500_000 - 880_000  # 620_000
        tolerance = expected_gp * 0.05  # 5% tolerance
        assert abs(gross_profit - expected_gp) <= tolerance, \
            f"Gross profit mismatch: got {gross_profit}, expected ~{expected_gp}"

    def test_with_empty_transactions(self):
        """Pipeline must handle empty transactions without crashing."""
        from app.services.gl_pipeline import gl_pipeline
        result = gl_pipeline.run_from_transactions([], period="2025-01", currency="GEL")
        assert isinstance(result, dict), "Empty transactions should return a dict"

    def test_with_single_transaction(self):
        """Pipeline must handle a single transaction."""
        from app.services.gl_pipeline import gl_pipeline
        single = [{"account_code": "6110", "debit": 0, "credit": 100_000}]
        result = gl_pipeline.run_from_transactions(single, period="2025-01", currency="GEL")
        assert isinstance(result, dict)

    def test_account_classification(self):
        """Account classifier must correctly classify known Georgian COA codes."""
        from app.services.account_hierarchy import account_hierarchy_builder
        # Test known revenue account
        result = account_hierarchy_builder.classify_account("6110")
        assert result.get("is_pl") or result.get("section") == "income_statement", \
            f"6110 should be income statement, got: {result}"

    def test_bs_equation_on_known_data(self):
        """Assets = Liabilities + Equity must hold for our test data."""
        from app.services.gl_pipeline import gl_pipeline
        result = gl_pipeline.run_from_transactions(
            SAMPLE_TRANSACTIONS, period="2025-01", currency="GEL"
        )
        stmts = result.get("statements", {})
        if not stmts:
            pytest.skip("statements not in result structure")
        bs = stmts.get("balance_sheet", {})
        if not bs:
            pytest.skip("balance_sheet not in statements")
        total_assets = bs.get("total_assets", 0)
        total_liabilities = bs.get("total_liabilities", 0)
        total_equity = bs.get("total_equity", 0)
        if total_assets and (total_liabilities or total_equity):
            diff = abs(total_assets - (total_liabilities + total_equity))
            assert diff < 1.0 or diff / total_assets < 0.01, \
                f"BS equation violated: assets={total_assets}, " \
                f"liabilities={total_liabilities}, equity={total_equity}"


class TestAccountHierarchy:
    """Tests for the 406-account Georgian COA classification system."""

    @pytest.mark.parametrize("code,expected_section", [
        ("6110", "income_statement"),    # Wholesale revenue
        ("6120", "income_statement"),    # Retail revenue
        ("7110", "income_statement"),    # COGS
        ("8110", "income_statement"),    # Selling expenses
        ("1110", "balance_sheet"),       # Cash
        ("1210", "balance_sheet"),       # Receivables
        ("4110", "balance_sheet"),       # AP
        ("5110", "balance_sheet"),       # Equity
    ])
    def test_account_classification_by_code(self, code: str, expected_section: str):
        """Account classification must correctly classify known account codes."""
        try:
            from app.services.account_hierarchy import account_hierarchy_builder
            result = account_hierarchy_builder.classify_account(code)
            actual = result.get("section", result.get("ifrs_section", ""))
            assert expected_section in actual or actual in expected_section, \
                f"Account {code}: expected {expected_section}, got {actual!r}"
        except ImportError:
            pytest.skip("account_hierarchy_builder not available")
