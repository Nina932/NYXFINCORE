"""
test_circuit_breaker.py — Verify the pipeline circuit breaker pattern.

Tests:
  - Critical violations immediately open the breaker
  - Warnings accumulate to HALF_OPEN
  - Normal data keeps the breaker CLOSED
  - Halt response contains actionable information
"""

import pytest
from app.orchestrator.circuit_breaker import (
    CircuitBreaker,
    BreakerState,
    HaltReason,
)


class TestCircuitBreaker:
    """Unit tests for the CircuitBreaker class."""

    def test_initial_state_is_closed(self):
        breaker = CircuitBreaker()
        assert breaker.state == BreakerState.CLOSED
        assert breaker.should_continue() is True
        assert breaker.is_degraded() is False

    def test_critical_opens_breaker(self):
        breaker = CircuitBreaker()
        breaker.record_critical(HaltReason.BS_EQUATION_FAILED, "A=100 != L+E=90")
        assert breaker.state == BreakerState.OPEN
        assert breaker.should_continue() is False
        assert breaker.critical_failures == 1

    def test_single_warning_keeps_closed(self):
        breaker = CircuitBreaker()
        breaker.record_warning("Minor inconsistency")
        assert breaker.state == BreakerState.CLOSED
        assert breaker.should_continue() is True
        assert breaker.is_degraded() is False

    def test_three_warnings_degrades_to_half_open(self):
        breaker = CircuitBreaker()
        breaker.record_warning("Warning 1")
        breaker.record_warning("Warning 2")
        breaker.record_warning("Warning 3")
        assert breaker.state == BreakerState.HALF_OPEN
        assert breaker.should_continue() is True
        assert breaker.is_degraded() is True

    def test_halt_response_structure(self):
        breaker = CircuitBreaker()
        breaker.record_critical(HaltReason.GAAP_VIOLATION, "TB imbalance")
        resp = breaker.halt_response()
        assert resp["status"] == "halted"
        assert resp["action_required"] is True
        assert resp["breaker_state"] == "open"
        assert len(resp["halt_reasons"]) == 1
        assert "gaap_violation" in resp["halt_reasons"][0]

    def test_status_summary(self):
        breaker = CircuitBreaker()
        breaker.record_warning("test warning")
        summary = breaker.status_summary()
        assert summary["breaker_state"] == "closed"
        assert summary["warning_count"] == 1
        assert summary["data_reliable"] is True
        assert summary["provisional"] is False

    def test_degraded_summary(self):
        breaker = CircuitBreaker()
        for i in range(3):
            breaker.record_warning(f"Warning {i+1}")
        summary = breaker.status_summary()
        assert summary["breaker_state"] == "half_open"
        assert summary["provisional"] is True
        assert summary["data_reliable"] is False

    def test_all_halt_reasons(self):
        """All HaltReason enum values should be usable."""
        breaker = CircuitBreaker()
        for reason in HaltReason:
            b = CircuitBreaker()
            b.record_critical(reason, "test")
            assert b.state == BreakerState.OPEN

    def test_reconstruction_failed(self):
        breaker = CircuitBreaker()
        breaker.record_critical(HaltReason.RECONSTRUCTION_FAILED, "completeness=15%")
        assert not breaker.should_continue()
        assert "reconstruction_failed" in breaker.halt_reasons[0]

    def test_calculation_nan_inf(self):
        breaker = CircuitBreaker()
        breaker.record_critical(HaltReason.CALCULATION_FAILED, "revenue is NaN")
        assert not breaker.should_continue()


class TestCircuitBreakerGraphIntegration:
    """Test the circuit breaker check node function."""

    def test_clean_data_passes(self):
        """Clean financial data should not trigger the breaker."""
        from app.graph.graph import _circuit_breaker_check

        state = {
            "balance_sheet": {},
            "calculated_metrics": {"revenue": 1000000, "gross_profit": 400000},
            "completeness": {"completeness_pct": 85},
            "insights": [],
            "reasoning_trace": [],
        }
        result = _circuit_breaker_check(state)
        cb = result["circuit_breaker_status"]
        assert cb["breaker_state"] == "closed"
        assert result.get("status") != "halted"

    def test_bs_imbalance_halts(self):
        """Unbalanced balance sheet should halt the pipeline."""
        from app.graph.graph import _circuit_breaker_check

        state = {
            "balance_sheet": {
                "total_assets": 1000000,
                "total_liabilities": 500000,
                "total_equity": 300000,  # A=1M != L+E=800K
            },
            "calculated_metrics": {},
            "completeness": {"completeness_pct": 80},
            "insights": [],
            "reasoning_trace": [],
        }
        result = _circuit_breaker_check(state)
        cb = result["circuit_breaker_status"]
        assert cb["breaker_state"] == "open"
        assert result["status"] == "halted"

    def test_low_completeness_halts(self):
        """Very low data completeness should halt the pipeline."""
        from app.graph.graph import _circuit_breaker_check

        state = {
            "balance_sheet": {},
            "calculated_metrics": {},
            "completeness": {"completeness_pct": 20},
            "insights": [],
            "reasoning_trace": [],
        }
        result = _circuit_breaker_check(state)
        cb = result["circuit_breaker_status"]
        assert cb["breaker_state"] == "open"

    def test_nan_metric_halts(self):
        """NaN in calculated metrics should halt the pipeline."""
        from app.graph.graph import _circuit_breaker_check

        state = {
            "balance_sheet": {},
            "calculated_metrics": {"revenue": float("nan")},
            "completeness": {"completeness_pct": 80},
            "insights": [],
            "reasoning_trace": [],
        }
        result = _circuit_breaker_check(state)
        cb = result["circuit_breaker_status"]
        assert cb["breaker_state"] == "open"
