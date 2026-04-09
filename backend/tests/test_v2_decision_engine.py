"""
Test Suite: v2 Decision Engine — Determinism & Decimal Precision
=================================================================
"""
import pytest
from decimal import Decimal
from app.services.v2.decision_engine import decision_engine, BusinessAction


FINANCIALS = {
    "revenue": 50_000_000, "cogs": 41_000_000, "ga_expenses": 5_000_000,
    "depreciation": 1_000_000, "finance_expense": 500_000, "tax_rate": 0.15,
}

REPORT = {
    "health_score": 45.0,
    "diagnoses": [
        {"signal": {"metric": "gross_margin_pct", "direction": "down", "severity": "critical"}},
        {"signal": {"metric": "revenue", "direction": "down", "severity": "high"}},
    ]
}


class TestDecisionEngine:
    def test_generates_actions(self):
        result = decision_engine.generate_decision_report(REPORT, FINANCIALS)
        assert result.total_actions_evaluated > 0

    def test_decimal_roi(self):
        result = decision_engine.generate_decision_report(REPORT, FINANCIALS)
        assert isinstance(result.top_actions[0].roi_estimate, Decimal)

    def test_decimal_composite_score(self):
        result = decision_engine.generate_decision_report(REPORT, FINANCIALS)
        assert isinstance(result.top_actions[0].composite_score, Decimal)

    def test_deterministic_mc(self):
        """Same input must produce identical Monte Carlo results."""
        r1 = decision_engine.generate_decision_report(REPORT, FINANCIALS)
        r2 = decision_engine.generate_decision_report(REPORT, FINANCIALS)
        assert r1.cfo_verdict.sensitivity.mean_roi == r2.cfo_verdict.sensitivity.mean_roi

    def test_cfo_verdict_exists(self):
        result = decision_engine.generate_decision_report(REPORT, FINANCIALS)
        assert result.cfo_verdict is not None
        assert result.cfo_verdict.conviction_grade in ["A+", "A", "B+", "B", "C+", "C", "D", "F"]

    def test_no_silent_failure(self):
        """Empty report must still have generated_at (not silently empty)."""
        result = decision_engine.generate_decision_report({"health_score": 50, "diagnoses": []}, FINANCIALS)
        assert result.generated_at != ""

    def test_ranking_order(self):
        result = decision_engine.generate_decision_report(REPORT, FINANCIALS)
        if len(result.top_actions) > 1:
            assert result.top_actions[0].composite_score >= result.top_actions[1].composite_score
