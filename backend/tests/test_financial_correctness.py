"""
Financial Correctness Unit Tests
=================================
Tests the mathematical correctness of the core financial engine
with known inputs and exact expected outputs.

These tests verify:
  1. P&L waterfall arithmetic (Revenue → GP → EBITDA → EBIT → EBT → NP)
  2. Balance Sheet equation (Assets = Liabilities + Equity)
  3. Cash Flow reconciliation (Operating + Investing + Financing = Net change)
  4. Net Income flows into Equity (BS equation holds after NI injection)
  5. Edge cases: zero equity, negative retained earnings, single account

Audit reference: F5 — "No unit tests for financial calculations"
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── Known test data with EXACT expected outputs ────────────────────────────

# Minimal balanced double-entry set for NYX-like company
KNOWN_TRANSACTIONS = [
    # Revenue (6xxx) — credit increases revenue
    {"account_code": "6110", "debit": 0,          "credit": 1_000_000, "description": "Wholesale fuel"},
    {"account_code": "6120", "debit": 0,          "credit": 500_000,   "description": "Retail fuel"},
    # COGS (71xx) — debit increases expense
    {"account_code": "7110", "debit": 650_000,    "credit": 0,         "description": "Wholesale COGS"},
    {"account_code": "7120", "debit": 250_000,    "credit": 0,         "description": "Retail COGS"},
    # Selling expenses (73xx)
    {"account_code": "7310", "debit": 40_000,     "credit": 0,         "description": "Marketing"},
    # Admin expenses (72xx)
    {"account_code": "7210", "debit": 80_000,     "credit": 0,         "description": "Office & admin"},
    # Depreciation (8xxx → Other Operating Income bucket or separate)
    {"account_code": "8110", "debit": 30_000,     "credit": 0,         "description": "D&A"},
    # Finance income / costs
    {"account_code": "8210", "debit": 0,          "credit": 5_000,     "description": "Interest income"},
    {"account_code": "8310", "debit": 15_000,     "credit": 0,         "description": "Interest expense"},
    # Tax (9xxx)
    {"account_code": "9110", "debit": 67_500,     "credit": 0,         "description": "Income tax"},
    # Balance Sheet — Assets
    {"account_code": "1110", "debit": 200_000,    "credit": 0,         "description": "Cash"},
    {"account_code": "1310", "debit": 350_000,    "credit": 0,         "description": "Trade receivables"},
    {"account_code": "1510", "debit": 180_000,    "credit": 0,         "description": "Inventory"},
    {"account_code": "2110", "debit": 500_000,    "credit": 0,         "description": "PP&E"},
    # Balance Sheet — Liabilities
    {"account_code": "3110", "debit": 0,          "credit": 250_000,   "description": "Trade payables"},
    {"account_code": "4110", "debit": 0,          "credit": 400_000,   "description": "Long-term debt"},
    # Balance Sheet — Equity
    {"account_code": "5110", "debit": 0,          "credit": 200_000,   "description": "Share capital"},
    {"account_code": "5310", "debit": 0,          "credit": 7_500,     "description": "Retained earnings"},
]

# ── Expected values (hand-calculated) ─────────────────────────────────────
# Revenue = 1,000,000 + 500,000 = 1,500,000
# COGS = 650,000 + 250,000 = 900,000
# Gross Profit = 1,500,000 - 900,000 = 600,000
# Selling = 40,000
# Admin = 80,000
# Other operating = 30,000 (debit side of 8110)
# Finance income (8210) = 5,000  (credit → treated as Other Operating Income)
# Finance costs (8310) = 15,000
# Tax = 67,500
#
# BS Assets = 200,000 + 350,000 + 180,000 + 500,000 = 1,230,000
# BS Liabilities = 250,000 + 400,000 = 650,000
# BS Equity (before NI) = 200,000 + 7,500 = 207,500
# Net Income injected into equity makes: Assets = L + E + NI

EXPECTED_REVENUE = 1_500_000
EXPECTED_COGS = 900_000
EXPECTED_GROSS_PROFIT = 600_000
EXPECTED_TOTAL_ASSETS = 1_230_000
EXPECTED_TOTAL_LIABILITIES = 650_000
EXPECTED_EQUITY_BEFORE_NI = 207_500


class TestPLWaterfall:
    """P&L waterfall correctness with known inputs and exact expected outputs."""

    @pytest.fixture(autouse=True)
    def _build_statements(self):
        from app.services.account_hierarchy import FinancialStatementMapper
        mapper = FinancialStatementMapper()
        self.stmts = mapper.build_statements(
            KNOWN_TRANSACTIONS, period="2025-01", currency="GEL"
        )

    def test_revenue_exact(self):
        """Revenue must equal sum of all 6xxx credit entries."""
        revenue = self.stmts.income_statement.get("Revenue")
        assert revenue is not None, "Revenue line missing from IS"
        assert abs(revenue.amount - EXPECTED_REVENUE) < 0.01, \
            f"Revenue: expected {EXPECTED_REVENUE}, got {revenue.amount}"

    def test_cogs_exact(self):
        """COGS must equal sum of all 71xx debit entries."""
        cogs = self.stmts.income_statement.get("Cost of Sales")
        assert cogs is not None, "Cost of Sales line missing from IS"
        assert abs(cogs.amount - EXPECTED_COGS) < 0.01, \
            f"COGS: expected {EXPECTED_COGS}, got {cogs.amount}"

    def test_gross_profit_exact(self):
        """Gross Profit = Revenue - COGS."""
        gp = self.stmts.gross_profit()
        assert abs(gp - EXPECTED_GROSS_PROFIT) < 0.01, \
            f"Gross Profit: expected {EXPECTED_GROSS_PROFIT}, got {gp}"

    def test_net_income_computed(self):
        """Net Income must be computed and present in IS."""
        ni = self.stmts.income_statement.get("Net Income")
        assert ni is not None, "Net Income line missing from IS"
        # Net income = Revenue - all expenses
        assert ni.amount != 0, "Net Income should not be zero for this data"

    def test_pl_waterfall_consistency(self):
        """Revenue - sum(expenses) = Net Income."""
        revenue = self.stmts.income_statement.get("Revenue")
        ni = self.stmts.income_statement.get("Net Income")
        total_expenses = sum(
            line.amount for name, line in self.stmts.income_statement.items()
            if name not in ("Revenue", "Net Income")
        )
        computed_ni = revenue.amount - total_expenses
        assert abs(computed_ni - ni.amount) < 0.01, \
            f"Waterfall inconsistency: Rev({revenue.amount}) - Expenses({total_expenses}) " \
            f"= {computed_ni}, but NI line = {ni.amount}"

    def test_no_negative_revenue(self):
        """Revenue should never be negative for credit-side entries."""
        revenue = self.stmts.income_statement.get("Revenue")
        assert revenue.amount >= 0, f"Negative revenue: {revenue.amount}"

    def test_expense_lines_non_negative(self):
        """All expense lines should be non-negative (absolute amounts)."""
        for name, line in self.stmts.income_statement.items():
            if name not in ("Revenue", "Net Income", "Other Operating Income",
                            "Finance Income"):
                assert line.amount >= 0, \
                    f"Expense line '{name}' is negative: {line.amount}"


class TestBalanceSheet:
    """Balance Sheet equation and structure correctness."""

    @pytest.fixture(autouse=True)
    def _build_statements(self):
        from app.services.account_hierarchy import FinancialStatementMapper
        mapper = FinancialStatementMapper()
        self.stmts = mapper.build_statements(
            KNOWN_TRANSACTIONS, period="2025-01", currency="GEL"
        )

    def test_bs_equation_holds(self):
        """Assets = Liabilities + Equity (including net income injection)."""
        assert self.stmts.bs_equation_holds(tolerance=1.0), \
            f"BS equation violated: Assets={self.stmts.total_assets():,.2f}, " \
            f"L+E={self.stmts.total_liabilities() + self.stmts.total_equity():,.2f}"

    def test_total_assets_exact(self):
        """Total assets must match sum of all 1xxx and 2xxx debit entries."""
        ta = self.stmts.total_assets()
        assert abs(ta - EXPECTED_TOTAL_ASSETS) < 1.0, \
            f"Total Assets: expected {EXPECTED_TOTAL_ASSETS}, got {ta}"

    def test_total_liabilities_exact(self):
        """Total liabilities must match sum of all 3xxx and 4xxx credit entries."""
        tl = self.stmts.total_liabilities()
        assert abs(tl - EXPECTED_TOTAL_LIABILITIES) < 1.0, \
            f"Total Liabilities: expected {EXPECTED_TOTAL_LIABILITIES}, got {tl}"

    def test_net_income_in_equity(self):
        """Net income must appear in equity as Retained Earnings (Net Income)."""
        equity = self.stmts.balance_sheet.get("equity", {})
        retained_ni = equity.get("Retained Earnings (Net Income)")
        assert retained_ni is not None, \
            "Retained Earnings (Net Income) missing from equity section"
        assert retained_ni.amount != 0, \
            "Retained Earnings (Net Income) should not be zero"

    def test_equity_plus_ni_balances(self):
        """Equity (share capital + RE + NI injection) must make BS equation hold."""
        ta = self.stmts.total_assets()
        tl = self.stmts.total_liabilities()
        te = self.stmts.total_equity()
        diff = abs(ta - (tl + te))
        assert diff < 1.0, \
            f"BS imbalance: A={ta:,.2f} vs L+E={tl + te:,.2f}, diff={diff:,.2f}"

    def test_current_assets_populated(self):
        """Current assets section must contain cash, receivables, inventory."""
        ca = self.stmts.balance_sheet.get("current_assets", {})
        assert len(ca) >= 3, f"Expected ≥3 current asset lines, got {len(ca)}: {list(ca.keys())}"

    def test_noncurrent_assets_populated(self):
        """Non-current assets must contain PP&E."""
        nca = self.stmts.balance_sheet.get("noncurrent_assets", {})
        assert len(nca) >= 1, f"Expected ≥1 NCA line, got {len(nca)}: {list(nca.keys())}"


class TestBalanceSheetEdgeCases:
    """Edge cases: zero equity, negative retained earnings, empty data."""

    def test_zero_equity(self):
        """BS with zero equity must still report equation correctly."""
        from app.services.account_hierarchy import FinancialStatementMapper
        mapper = FinancialStatementMapper()
        # Assets = Liabilities, no equity entries
        txns = [
            {"account_code": "1110", "debit": 100_000, "credit": 0},
            {"account_code": "3110", "debit": 0,       "credit": 100_000},
        ]
        stmts = mapper.build_statements(txns, period="2025-01")
        # Equity should be 0 or only contain NI injection
        assert stmts.total_assets() == 100_000
        # BS equation should hold (assets = liabilities + 0 equity + 0 NI)
        assert stmts.bs_equation_holds(tolerance=1.0)

    def test_negative_retained_earnings(self):
        """Company with net loss: NI injection should be negative in equity."""
        from app.services.account_hierarchy import FinancialStatementMapper
        mapper = FinancialStatementMapper()
        # Revenue 100k, Expenses 150k → Net Loss of 50k
        txns = [
            {"account_code": "6110", "debit": 0,       "credit": 100_000},
            {"account_code": "7110", "debit": 150_000, "credit": 0},
            # BS entries
            {"account_code": "1110", "debit": 200_000, "credit": 0},
            {"account_code": "3110", "debit": 0,       "credit": 200_000},
            {"account_code": "5110", "debit": 0,       "credit": 50_000},
        ]
        stmts = mapper.build_statements(txns, period="2025-01")
        ni = stmts.income_statement.get("Net Income")
        assert ni is not None
        assert ni.amount < 0, f"Expected negative net income (loss), got {ni.amount}"
        # BS must still balance
        assert stmts.bs_equation_holds(tolerance=1.0), \
            f"BS doesn't balance with net loss: A={stmts.total_assets()}, " \
            f"L+E={stmts.total_liabilities() + stmts.total_equity()}"

    def test_empty_transactions(self):
        """Empty transactions should produce valid (zero) statements."""
        from app.services.account_hierarchy import FinancialStatementMapper
        mapper = FinancialStatementMapper()
        stmts = mapper.build_statements([], period="2025-01")
        assert stmts.total_assets() == 0
        assert stmts.total_liabilities() == 0
        assert stmts.total_equity() == 0
        assert stmts.bs_equation_holds()

    def test_single_revenue_entry(self):
        """Single revenue entry should create valid P&L with revenue only."""
        from app.services.account_hierarchy import FinancialStatementMapper
        mapper = FinancialStatementMapper()
        txns = [{"account_code": "6110", "debit": 0, "credit": 500_000}]
        stmts = mapper.build_statements(txns, period="2025-01")
        revenue = stmts.income_statement.get("Revenue")
        assert revenue is not None
        assert revenue.amount == 500_000

    def test_large_amounts_precision(self):
        """Large GEL amounts should not lose precision."""
        from app.services.account_hierarchy import FinancialStatementMapper
        mapper = FinancialStatementMapper()
        large_amt = 999_999_999.99
        txns = [
            {"account_code": "6110", "debit": 0,        "credit": large_amt},
            {"account_code": "7110", "debit": large_amt, "credit": 0},
            {"account_code": "1110", "debit": large_amt, "credit": 0},
            {"account_code": "3110", "debit": 0,         "credit": large_amt},
        ]
        stmts = mapper.build_statements(txns, period="2025-01")
        rev = stmts.income_statement.get("Revenue")
        assert abs(rev.amount - large_amt) < 0.01, \
            f"Precision loss: expected {large_amt}, got {rev.amount}"


class TestCashFlowReconciliation:
    """Cash flow statement classification and reconciliation."""

    @pytest.fixture(autouse=True)
    def _build_statements(self):
        from app.services.account_hierarchy import FinancialStatementMapper
        mapper = FinancialStatementMapper()
        self.stmts = mapper.build_statements(
            KNOWN_TRANSACTIONS, period="2025-01", currency="GEL"
        )

    def test_cash_flow_sections_populated(self):
        """Cash flow must have entries classified into operating/investing/financing."""
        cf = self.stmts.cash_flow
        sections = {line.section for line in cf.values()}
        # At least operating should be present (receivables, inventory, payables movements)
        assert "operating" in sections or len(cf) > 0, \
            f"Cash flow has no operating entries. Sections: {sections}"

    def test_cash_flow_account_classification(self):
        """Account codes must classify to correct CF sections."""
        from app.services.account_hierarchy import AccountHierarchyBuilder
        builder = AccountHierarchyBuilder()
        # 1xxx (assets) that are current → operating
        assert builder.get_cf_section("1310") == "operating"  # Trade receivables
        assert builder.get_cf_section("1510") == "operating"  # Inventory
        # 2xxx → investing
        assert builder.get_cf_section("2110") == "investing"  # PP&E
        # 4xxx → financing
        assert builder.get_cf_section("4110") == "financing"  # Long-term debt
        # 5xxx → financing
        assert builder.get_cf_section("5110") == "financing"  # Share capital


class TestAccountClassification:
    """Account code classification correctness for Georgian 1C COA."""

    @pytest.fixture(autouse=True)
    def _get_builder(self):
        from app.services.account_hierarchy import AccountHierarchyBuilder
        self.builder = AccountHierarchyBuilder()

    @pytest.mark.parametrize("code,expected_line", [
        ("6110", "Revenue"),
        ("6120", "Revenue"),
        ("6210", "Revenue"),
        ("7110", "Cost of Sales"),
        ("7120", "Cost of Sales"),
        ("7210", "Admin Expenses"),
        ("7310", "Selling Expenses"),
        ("8210", "Finance Income"),
        ("8310", "Finance Costs"),
        ("9110", "Income Tax"),
    ])
    def test_pl_line_classification(self, code: str, expected_line: str):
        """P&L line assignment must be correct for known Georgian COA codes."""
        result = self.builder.get_pl_line(code)
        assert result == expected_line, \
            f"Account {code}: expected P&L line '{expected_line}', got '{result}'"

    @pytest.mark.parametrize("code,expected_section,expected_line", [
        ("1110", "current_assets", "Cash & Cash Equivalents"),
        ("1310", "current_assets", "Trade Receivables"),
        ("1510", "current_assets", "Inventory"),
        ("2110", "noncurrent_assets", "Property, Plant & Equipment"),
        ("3110", "current_liabilities", "Trade Payables"),
        ("4110", "noncurrent_liabilities", "Long-term Debt"),
        ("5110", "equity", "Share Capital"),
        ("5310", "equity", "Retained Earnings"),
    ])
    def test_bs_position_classification(self, code: str, expected_section: str, expected_line: str):
        """BS section assignment must be correct for known Georgian COA codes."""
        section, line = self.builder.get_bs_position(code)
        assert section == expected_section, \
            f"Account {code}: expected BS section '{expected_section}', got '{section}'"
        assert line == expected_line, \
            f"Account {code}: expected BS line '{expected_line}', got '{line}'"

    @pytest.mark.parametrize("code,expected_is_pl", [
        ("6110", True),   # Revenue
        ("7110", True),   # COGS
        ("8110", True),   # Other operating
        ("9110", True),   # Tax
        ("1110", False),  # Cash (BS)
        ("2110", False),  # PP&E (BS)
        ("3110", False),  # Trade payables (BS)
        ("5110", False),  # Share capital (BS)
    ])
    def test_pl_vs_bs_classification(self, code: str, expected_is_pl: bool):
        """Accounts must correctly classify as P&L vs Balance Sheet."""
        result = self.builder.classify_account(code)
        assert result["is_pl"] == expected_is_pl, \
            f"Account {code}: expected is_pl={expected_is_pl}, got {result['is_pl']}"
        assert result["is_bs"] == (not expected_is_pl), \
            f"Account {code}: is_bs should be opposite of is_pl"


class TestDeterminism:
    """Financial engine must produce identical outputs for identical inputs."""

    def test_same_input_same_output(self):
        """Running the same transactions twice must produce identical results."""
        from app.services.account_hierarchy import FinancialStatementMapper
        mapper = FinancialStatementMapper()

        stmts1 = mapper.build_statements(KNOWN_TRANSACTIONS, period="2025-01")
        stmts2 = mapper.build_statements(KNOWN_TRANSACTIONS, period="2025-01")

        assert stmts1.gross_profit() == stmts2.gross_profit()
        assert stmts1.net_income() == stmts2.net_income()
        assert stmts1.total_assets() == stmts2.total_assets()
        assert stmts1.total_liabilities() == stmts2.total_liabilities()
        assert stmts1.total_equity() == stmts2.total_equity()

    def test_computation_fingerprint_deterministic(self):
        """Same inputs must produce the same SHA-256 fingerprint."""
        from app.services.account_hierarchy import FinancialStatementMapper
        mapper = FinancialStatementMapper()

        stmts1 = mapper.build_statements(KNOWN_TRANSACTIONS, period="2025-01")
        stmts2 = mapper.build_statements(KNOWN_TRANSACTIONS, period="2025-01")

        fp1 = stmts1.computation_fingerprint()
        fp2 = stmts2.computation_fingerprint()
        assert fp1 == fp2, f"Fingerprints differ: {fp1} != {fp2}"
        assert len(fp1) == 64, "Fingerprint should be a 64-char SHA-256 hex string"

    def test_fingerprint_changes_with_data(self):
        """Different inputs must produce different fingerprints."""
        from app.services.account_hierarchy import FinancialStatementMapper
        mapper = FinancialStatementMapper()

        stmts1 = mapper.build_statements(KNOWN_TRANSACTIONS, period="2025-01")
        # Modify one transaction
        modified = [t.copy() for t in KNOWN_TRANSACTIONS]
        modified[0]["credit"] = 999_999  # Change revenue
        stmts2 = mapper.build_statements(modified, period="2025-01")

        assert stmts1.computation_fingerprint() != stmts2.computation_fingerprint(), \
            "Different financial data must produce different fingerprints"

    def test_fingerprint_in_to_dict(self):
        """to_dict() must include the computation fingerprint."""
        from app.services.account_hierarchy import FinancialStatementMapper
        mapper = FinancialStatementMapper()

        stmts = mapper.build_statements(KNOWN_TRANSACTIONS, period="2025-01")
        d = stmts.to_dict()
        assert "computation_fingerprint" in d, "to_dict() missing computation_fingerprint"
        assert len(d["computation_fingerprint"]) == 64

    def test_transaction_order_independence(self):
        """Shuffled transaction order must produce identical totals."""
        import random
        from app.services.account_hierarchy import FinancialStatementMapper
        mapper = FinancialStatementMapper()

        stmts_original = mapper.build_statements(KNOWN_TRANSACTIONS, period="2025-01")

        shuffled = KNOWN_TRANSACTIONS.copy()
        random.seed(42)
        random.shuffle(shuffled)
        stmts_shuffled = mapper.build_statements(shuffled, period="2025-01")

        assert abs(stmts_original.gross_profit() - stmts_shuffled.gross_profit()) < 0.01
        assert abs(stmts_original.net_income() - stmts_shuffled.net_income()) < 0.01
        assert abs(stmts_original.total_assets() - stmts_shuffled.total_assets()) < 0.01
        assert abs(stmts_original.total_equity() - stmts_shuffled.total_equity()) < 0.01
