"""
Pipeline Circuit Breaker — prevents downstream stages from operating on
degraded or invalid financial data.

Three states:
  CLOSED    — normal operation, all stages proceed
  HALF_OPEN — degraded data detected (warnings), LLM output marked provisional
  OPEN      — critical integrity violation, pipeline halts immediately

Critical violations that open the breaker:
  - Balance sheet equation failure (Assets != L + E)
  - Trial balance imbalance (total debits != total credits)
  - Reconstruction engine reports CRITICAL completeness failure
  - Calculation stage produces NaN/Inf values

Warnings that degrade to HALF_OPEN:
  - Net income inconsistency between IS and BS
  - Missing required fields (revenue, cogs present but no gross_profit computed)
  - Data completeness below 50%
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List


class BreakerState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class HaltReason(Enum):
    GAAP_VIOLATION = "critical_gaap_violation"
    RECONSTRUCTION_FAILED = "reconstruction_failed"
    CALCULATION_FAILED = "calculation_failed"
    DATA_INTEGRITY = "data_integrity_failure"
    BS_EQUATION_FAILED = "bs_equation_imbalance"
    TB_IMBALANCE = "trial_balance_imbalance"


@dataclass
class CircuitBreaker:
    """Pipeline circuit breaker for financial data integrity.

    Usage:
        breaker = CircuitBreaker()

        # After each stage, check data integrity
        if bs_assets != bs_liabilities + bs_equity:
            breaker.record_critical(HaltReason.BS_EQUATION_FAILED,
                                    f"A={bs_assets} != L+E={bs_liabilities + bs_equity}")

        # Before starting next stage
        if not breaker.should_continue():
            return breaker.halt_response()

        # Mark LLM output if degraded
        if breaker.is_degraded():
            narrative["provisional"] = True
    """

    state: BreakerState = BreakerState.CLOSED
    halt_reasons: List[str] = field(default_factory=list)
    critical_failures: int = 0
    warning_count: int = 0

    MAX_CRITICAL: int = 1
    MAX_WARNINGS: int = 3

    def record_critical(self, reason: HaltReason, detail: str = ""):
        """Record a critical failure. Opens the breaker immediately."""
        self.critical_failures += 1
        msg = f"CRITICAL: {reason.value}"
        if detail:
            msg += f" — {detail}"
        self.halt_reasons.append(msg)
        self.state = BreakerState.OPEN

    def record_warning(self, detail: str = ""):
        """Record a warning. Degrades to HALF_OPEN after threshold."""
        self.warning_count += 1
        self.halt_reasons.append(f"WARNING: {detail}")
        if self.warning_count >= self.MAX_WARNINGS:
            self.state = BreakerState.HALF_OPEN

    def should_continue(self) -> bool:
        """Can the pipeline proceed to the next stage?"""
        return self.state != BreakerState.OPEN

    def is_degraded(self) -> bool:
        """Should LLM narratives be marked as provisional?"""
        return self.state == BreakerState.HALF_OPEN

    def halt_response(self) -> dict:
        """Return a structured response when the pipeline is halted."""
        return {
            "status": "halted",
            "action_required": True,
            "breaker_state": self.state.value,
            "halt_reasons": self.halt_reasons,
            "critical_failures": self.critical_failures,
            "warning_count": self.warning_count,
            "message": (
                "Pipeline halted due to critical data integrity violation. "
                "The uploaded data contains errors that would produce unreliable "
                "financial analysis. Please review and correct the source data."
            ),
        }

    def status_summary(self) -> dict:
        """Return current breaker status for inclusion in pipeline results."""
        return {
            "breaker_state": self.state.value,
            "critical_failures": self.critical_failures,
            "warning_count": self.warning_count,
            "halt_reasons": self.halt_reasons,
            "data_reliable": self.state == BreakerState.CLOSED,
            "provisional": self.is_degraded(),
        }
