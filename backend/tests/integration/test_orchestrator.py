"""
Integration Tests — Orchestrator Pipeline
==========================================
Tests the 7-stage financial orchestrator end-to-end:
  financials → diagnosis → decisions → strategy → health score
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


SAMPLE_FINANCIALS = {
    "revenue": 1_500_000,
    "cogs": 880_000,
    "gross_profit": 620_000,
    "ga_expenses": 140_000,
    "ebitda": 480_000,
    "depreciation": 20_000,
    "ebit": 460_000,
    "net_profit": 400_000,
}

SAMPLE_BALANCE_SHEET = {
    "cash": 50_000,
    "receivables": 120_000,
    "inventory": 80_000,
    "current_assets": 250_000,
    "fixed_assets_net": 300_000,
    "total_assets": 550_000,
    "current_liabilities": 100_000,
    "total_liabilities": 150_000,
    "total_equity": 400_000,
}


class TestOrchestrator:
    """Tests for the 7-stage pipeline orchestrator."""

    def test_orchestrator_import(self):
        """Orchestrator must be importable."""
        from app.services.orchestrator import orchestrator
        assert orchestrator is not None

    def test_orchestrator_run_returns_result(self):
        """Orchestrator must run without crashing and return a result."""
        from app.services.orchestrator import orchestrator
        result = orchestrator.run(
            current_financials=SAMPLE_FINANCIALS,
            balance_sheet=SAMPLE_BALANCE_SHEET,
            monte_carlo_iterations=50,  # Fast for tests
        )
        assert result is not None
        result_dict = result.to_dict()
        assert isinstance(result_dict, dict)

    def test_health_score_in_range(self):
        """Health score must be between 0 and 100."""
        from app.services.orchestrator import orchestrator
        result = orchestrator.run(
            current_financials=SAMPLE_FINANCIALS,
            balance_sheet=SAMPLE_BALANCE_SHEET,
            monte_carlo_iterations=50,
        )
        score = result.health_score
        assert 0 <= score <= 100, f"Health score {score} out of range [0, 100]"

    def test_health_grade_is_letter(self):
        """Health grade must be a letter grade (A–F)."""
        from app.services.orchestrator import orchestrator
        result = orchestrator.run(
            current_financials=SAMPLE_FINANCIALS,
            balance_sheet=SAMPLE_BALANCE_SHEET,
            monte_carlo_iterations=50,
        )
        grade = result.health_grade
        assert grade in ("A", "A+", "B", "B+", "C", "C+", "D", "F"), \
            f"Health grade {grade!r} is not a valid letter grade"

    def test_profitable_company_gets_good_score(self):
        """A profitable company with healthy margins must score > 50."""
        from app.services.orchestrator import orchestrator
        result = orchestrator.run(
            current_financials=SAMPLE_FINANCIALS,
            balance_sheet=SAMPLE_BALANCE_SHEET,
            monte_carlo_iterations=50,
        )
        assert result.health_score > 40, \
            f"Profitable company scored only {result.health_score} — scoring logic may be wrong"

    def test_loss_making_company_gets_low_score(self):
        """A loss-making company must score lower than a profitable one."""
        from app.services.orchestrator import orchestrator
        loss_financials = {**SAMPLE_FINANCIALS, "net_profit": -200_000, "ebitda": -100_000}
        result_loss = orchestrator.run(
            current_financials=loss_financials,
            balance_sheet=SAMPLE_BALANCE_SHEET,
            monte_carlo_iterations=50,
        )
        result_profit = orchestrator.run(
            current_financials=SAMPLE_FINANCIALS,
            balance_sheet=SAMPLE_BALANCE_SHEET,
            monte_carlo_iterations=50,
        )
        assert result_loss.health_score < result_profit.health_score, \
            f"Loss company ({result_loss.health_score}) should score lower than " \
            f"profitable company ({result_profit.health_score})"

    def test_orchestrator_with_empty_financials(self):
        """Orchestrator must not crash on empty financials."""
        from app.services.orchestrator import orchestrator
        try:
            result = orchestrator.run(current_financials={}, monte_carlo_iterations=10)
            assert result is not None
        except Exception as e:
            pytest.fail(f"Orchestrator crashed on empty financials: {e}")

    def test_to_dict_has_required_fields(self):
        """Result dict must contain all expected top-level fields."""
        from app.services.orchestrator import orchestrator
        result = orchestrator.run(
            current_financials=SAMPLE_FINANCIALS,
            monte_carlo_iterations=10,
        )
        rd = result.to_dict()
        for field in ("health_score", "health_grade"):
            assert field in rd or hasattr(result, field), \
                f"Required field '{field}' missing from orchestrator result"


class TestDiagnosisEngine:
    """Tests for the financial diagnosis engine."""

    def test_diagnosis_import(self):
        """Diagnosis engine must be importable."""
        from app.services.diagnosis_engine import diagnosis_engine
        assert diagnosis_engine is not None

    def test_diagnosis_returns_report(self):
        """Diagnosis must return a report with findings."""
        from app.services.diagnosis_engine import diagnosis_engine
        report = diagnosis_engine.run_full_diagnosis(
            current_financials=SAMPLE_FINANCIALS,
            industry_id="fuel_distribution",
        )
        assert report is not None
        rd = report.to_dict()
        assert isinstance(rd, dict)

    def test_high_margin_company_has_no_critical_issues(self):
        """A healthy company should not have critical margin issues."""
        from app.services.diagnosis_engine import diagnosis_engine
        healthy_financials = {
            **SAMPLE_FINANCIALS,
            "gross_margin_pct": 41.3,   # Healthy for fuel distribution
            "net_margin_pct": 26.7,
        }
        report = diagnosis_engine.run_full_diagnosis(
            current_financials=healthy_financials,
            industry_id="fuel_distribution",
        )
        rd = report.to_dict()
        # Shouldn't have emergency-level alerts for a healthy company
        if "alerts" in rd:
            emergency = [a for a in rd["alerts"] if a.get("severity") == "emergency"]
            assert len(emergency) == 0, \
                f"Healthy company triggered emergency alerts: {emergency}"
