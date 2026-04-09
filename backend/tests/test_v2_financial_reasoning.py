"""
Test Suite: v2 Financial Reasoning — Edge Cases & Decimal Precision
====================================================================
"""
import pytest
from decimal import Decimal
from app.services.v2.financial_reasoning import reasoning_engine


class TestSimulateScenario:
    BASE = {
        "revenue": 50_000_000, "cogs": 41_000_000, "ga_expenses": 5_000_000,
        "depreciation": 1_000_000, "finance_expense": 500_000, "tax_rate": 0.15,
    }

    def test_returns_decimal(self):
        result = reasoning_engine.simulate_scenario("test", self.BASE, {"cogs_pct": 5})
        assert isinstance(result.base_net_profit, Decimal)
        assert isinstance(result.scenario_net_profit, Decimal)

    def test_no_change_returns_same(self):
        result = reasoning_engine.simulate_scenario("test", self.BASE, {})
        assert result.base_net_profit == result.scenario_net_profit

    def test_revenue_increase(self):
        result = reasoning_engine.simulate_scenario("test", self.BASE, {"revenue_pct": 10})
        assert result.scenario_revenue > result.base_revenue
        assert result.scenario_net_profit > result.base_net_profit

    def test_zero_revenue(self):
        """Edge case: zero revenue must not crash."""
        base = dict(self.BASE)
        base["revenue"] = 0
        result = reasoning_engine.simulate_scenario("test", base, {"cogs_pct": 10})
        assert result.revenue_change_pct is None  # Can't compute % change from 0

    def test_deterministic(self):
        r1 = reasoning_engine.simulate_scenario("test", self.BASE, {"revenue_pct": 5})
        r2 = reasoning_engine.simulate_scenario("test", self.BASE, {"revenue_pct": 5})
        assert r1.scenario_net_profit == r2.scenario_net_profit


class TestBuildLiquidityAnalysis:
    def test_zero_liabilities(self):
        """Division by zero must return None, not crash (v1 bug)."""
        result = reasoning_engine.build_liquidity_analysis({
            "total_current_assets": 100000,
            "total_current_liabilities": 0,
        })
        assert result["ratios"]["current_ratio"] is None

    def test_negative_equity(self):
        result = reasoning_engine.build_liquidity_analysis({
            "total_current_assets": 100, "total_current_liabilities": 200,
            "total_equity": -100, "total_debt": 300, "total_assets": 200,
        })
        assert result["health"] == "critical"


class TestExplainMetricChange:
    def test_pct_from_zero(self):
        """Change from 0 must return None for pct, not 0.0 (v1 bug)."""
        chain = reasoning_engine.explain_metric_change("revenue", 0, 1000000)
        assert chain.change_pct is None

    def test_critical_severity(self):
        chain = reasoning_engine.explain_metric_change("gross_margin_pct", 32, 18)
        assert chain.severity == "critical"


class TestDetectAccountingIssues:
    def test_bs_imbalance(self):
        issues = reasoning_engine.detect_accounting_issues(
            {"revenue": 100}, {"total_assets": 1000, "total_liabilities": 600, "total_equity": 300}
        )
        assert any(i["type"] == "balance_sheet_imbalance" for i in issues)

    def test_negative_revenue(self):
        issues = reasoning_engine.detect_accounting_issues(
            {"revenue": -100}, {"total_assets": 100, "total_liabilities": 50, "total_equity": 50}
        )
        assert any(i["type"] == "negative_revenue" for i in issues)
