"""
Test Suite: v2 Sensitivity Analyzer — Determinism & Decimal
=============================================================
"""
import pytest
from decimal import Decimal
from app.services.v2.sensitivity_analyzer import (
    sensitivity_analyzer, scenario_monte_carlo, multi_var_simulator,
)


FINANCIALS = {
    "revenue": 50_000_000, "cogs": 41_000_000, "ga_expenses": 5_000_000,
    "depreciation": 1_000_000, "finance_expense": 500_000, "tax_rate": 0.15,
}


class TestSensitivityAnalyzer:
    def test_produces_decimal_bands(self):
        report = sensitivity_analyzer.analyze(
            FINANCIALS, variables={"revenue_pct": (-10, 10)}, steps=3,
        )
        assert isinstance(report.base_net_profit, Decimal)
        assert len(report.bands) == 1
        assert isinstance(report.bands[0].swing, Decimal)

    def test_tornado_order(self):
        """Bands must be sorted by swing descending (biggest impact first)."""
        report = sensitivity_analyzer.analyze(
            FINANCIALS,
            variables={"revenue_pct": (-10, 10), "cogs_pct": (-10, 10)},
            steps=3,
        )
        if len(report.bands) > 1:
            assert report.bands[0].swing >= report.bands[1].swing


class TestMonteCarlo:
    def test_deterministic(self):
        """Same seed must produce identical results."""
        r1 = scenario_monte_carlo.simulate(FINANCIALS, iterations=100, seed=42)
        r2 = scenario_monte_carlo.simulate(FINANCIALS, iterations=100, seed=42)
        assert r1.mean_net_profit == r2.mean_net_profit
        assert r1.probability_loss == r2.probability_loss

    def test_different_seed_different_result(self):
        r1 = scenario_monte_carlo.simulate(FINANCIALS, iterations=100, seed=42)
        r2 = scenario_monte_carlo.simulate(FINANCIALS, iterations=100, seed=99)
        assert r1.mean_net_profit != r2.mean_net_profit

    def test_decimal_output(self):
        result = scenario_monte_carlo.simulate(FINANCIALS, iterations=50, seed=1)
        assert isinstance(result.mean_net_profit, Decimal)
        assert isinstance(result.probability_loss, Decimal)


class TestMultiVar:
    def test_interaction_effect(self):
        result = multi_var_simulator.simulate(
            FINANCIALS, {"revenue_pct": 10, "cogs_pct": -5},
        )
        assert isinstance(result.interaction_effect, Decimal)
        assert result.scenario_net_profit != result.base_net_profit
