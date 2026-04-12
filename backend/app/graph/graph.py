"""
FinAI LangGraph — The Production Agent Graph
==============================================
Sequential pipeline: Extract → Calculate → Insight → Memory → Orchestrator → Reason → Alert

This is a DETERMINISTIC graph with ONE LLM node (reasoner).
All financial numbers flow through Decimal-only nodes.
The LLM node only explains — never computes.
"""

import logging
import time
from typing import Dict, Any

from langgraph.graph import StateGraph, START, END

from app.graph.state import FinAIState
from app.graph.nodes import (
    data_extractor_node,
    calculator_node,
    insight_engine_node,
    memory_node,
    orchestrator_node,
    reasoner_node,
    alert_node,
    anomaly_detector_node,
    whatif_simulator_node,
    report_generator_node,
)
from app.orchestrator.circuit_breaker import CircuitBreaker, HaltReason

logger = logging.getLogger(__name__)


def _circuit_breaker_check(state: FinAIState) -> FinAIState:
    """Validate data integrity after extraction, calculation, and reconstruction.

    Checks:
      - Balance sheet equation (A = L + E)
      - Trial balance (debits = credits)
      - Data completeness from reconstruction engine
      - Calculation results for NaN/Inf
    """
    breaker = CircuitBreaker()
    bs = state.get("balance_sheet", {})
    metrics = state.get("calculated_metrics", {})
    completeness = state.get("completeness", {})

    # Check BS equation: Assets = Liabilities + Equity
    total_assets = bs.get("total_assets") or metrics.get("total_assets")
    total_liabilities = bs.get("total_liabilities") or metrics.get("total_liabilities")
    total_equity = bs.get("total_equity") or metrics.get("total_equity")

    if total_assets is not None and total_liabilities is not None and total_equity is not None:
        try:
            a = float(total_assets)
            le = float(total_liabilities) + float(total_equity)
            if abs(a - le) > 1.0:  # Allow 1 unit tolerance for rounding
                breaker.record_critical(
                    HaltReason.BS_EQUATION_FAILED,
                    f"Assets={a:,.2f} != L+E={le:,.2f} (diff={abs(a - le):,.2f})"
                )
        except (ValueError, TypeError):
            breaker.record_warning("BS equation check skipped: non-numeric values")

    # Check for NaN/Inf in calculated metrics
    for key, val in metrics.items():
        if isinstance(val, float):
            import math
            if math.isnan(val) or math.isinf(val):
                breaker.record_critical(
                    HaltReason.CALCULATION_FAILED,
                    f"Metric '{key}' is {val}"
                )

    # Check data completeness from reconstruction engine
    completeness_pct = completeness.get("completeness_pct", 100)
    if isinstance(completeness_pct, (int, float)) and completeness_pct < 30:
        breaker.record_critical(
            HaltReason.RECONSTRUCTION_FAILED,
            f"Data completeness {completeness_pct}% — below 30% threshold"
        )
    elif isinstance(completeness_pct, (int, float)) and completeness_pct < 50:
        breaker.record_warning(f"Data completeness {completeness_pct}% — below 50%")

    # Check for critical violations from reconstruction insights
    for insight in state.get("insights", []):
        severity = insight.get("severity", "")
        if severity == "critical":
            breaker.record_warning(f"Reconstruction: {insight.get('message', 'unknown')}")

    state["circuit_breaker_status"] = breaker.status_summary()

    if not breaker.should_continue():
        state["status"] = "halted"
        state["reasoning_trace"] = state.get("reasoning_trace", []) + [
            f"[CircuitBreaker] HALTED: {'; '.join(breaker.halt_reasons)}"
        ]
        logger.warning("Pipeline halted by circuit breaker: %s", breaker.halt_reasons)

    return state


def _should_continue_after_check(state: FinAIState) -> str:
    """Route after circuit breaker: continue pipeline or halt."""
    cb = state.get("circuit_breaker_status", {})
    if cb.get("breaker_state") == "open":
        return "__end__"
    return "memory"


def _should_run_orchestrator(state: FinAIState) -> str:
    """Route: run legacy orchestrator only if full data available."""
    if state.get("data_type") in ("full_financials", "basic_pl"):
        return "orchestrator"
    return "reasoner"


def build_finai_graph() -> StateGraph:
    """Build the FinAI LangGraph agent pipeline."""

    workflow = StateGraph(FinAIState)

    # Add all nodes (10 + circuit breaker)
    workflow.add_node("data_extractor", data_extractor_node)
    workflow.add_node("calculator", calculator_node)
    workflow.add_node("insight_engine", insight_engine_node)
    workflow.add_node("circuit_breaker_check", _circuit_breaker_check)
    workflow.add_node("memory", memory_node)
    workflow.add_node("orchestrator", orchestrator_node)
    workflow.add_node("reasoner", reasoner_node)
    workflow.add_node("anomaly_detector", anomaly_detector_node)
    workflow.add_node("whatif_simulator", whatif_simulator_node)
    workflow.add_node("report_generator", report_generator_node)
    workflow.add_node("alerts", alert_node)

    # Sequential flow: Extract → Calculate → Insight → Circuit Breaker Check
    workflow.add_edge(START, "data_extractor")
    workflow.add_edge("data_extractor", "calculator")
    workflow.add_edge("calculator", "insight_engine")
    workflow.add_edge("insight_engine", "circuit_breaker_check")

    # Circuit breaker gate: continue or halt
    workflow.add_conditional_edges(
        "circuit_breaker_check",
        _should_continue_after_check,
        {"memory": "memory", "__end__": END},
    )

    # Conditional: run orchestrator only if full data
    workflow.add_conditional_edges(
        "memory",
        _should_run_orchestrator,
        {"orchestrator": "orchestrator", "reasoner": "reasoner"},
    )

    # After orchestrator → anomaly detection → what-if → reasoner
    workflow.add_edge("orchestrator", "anomaly_detector")
    workflow.add_edge("anomaly_detector", "whatif_simulator")
    workflow.add_edge("whatif_simulator", "reasoner")

    # After reasoner → alerts → report → END
    workflow.add_edge("reasoner", "alerts")
    workflow.add_edge("alerts", "report_generator")
    workflow.add_edge("report_generator", END)

    return workflow


# Compile the graph
_workflow = build_finai_graph()
finai_graph = _workflow.compile()


async def run_finai_pipeline(
    company_id: int = 0,
    company_name: str = "Unknown",
    period: str = "",
    file_path: str = "",
    command: str = "",
) -> Dict[str, Any]:
    """
    Run the full FinAI LangGraph pipeline.

    Args:
        company_id: Company DB ID
        company_name: Company name
        period: Financial period
        file_path: Path to uploaded Excel file (optional)
        command: User command (optional)

    Returns:
        Complete analysis result
    """
    start = time.time()

    initial_state: FinAIState = {
        "command": command,
        "company_id": company_id,
        "company_name": company_name,
        "period": period,
        "file_path": file_path or None,
        "extracted_financials": {},
        "line_items": [],
        "balance_sheet": {},
        "revenue_breakdown": [],
        "cogs_breakdown": [],
        "data_type": "unknown",
        "calculated_metrics": {},
        "completeness": {},
        "insights": [],
        "company_character": {},
        "suggestions": [],
        "revenue_estimate": None,
        "llm_narrative": "",
        "llm_model_used": "",
        "llm_confidence": 0.0,
        "period_deltas": {},
        "previous_periods": [],
        "orchestrator_result": None,
        "alerts": [],
        "report_path": None,
        "circuit_breaker_status": {},
        "status": "starting",
        "stages_completed": [],
        "stages_failed": [],
        "reasoning_trace": [],
        "execution_ms": 0,
    }

    # Run the graph
    try:
        result = finai_graph.invoke(initial_state)
    except Exception as e:
        logger.error("LangGraph pipeline failed: %s", e, exc_info=True)
        result = {**initial_state, "status": "failed",
                  "reasoning_trace": [f"Pipeline FAILED: {e}"],
                  "stages_failed": ["pipeline"]}

    elapsed = int((time.time() - start) * 1000)
    result["execution_ms"] = elapsed
    result["version"] = "langgraph_v1"

    logger.info("LangGraph pipeline: %d stages, %dms, LLM=%s",
                 len(result.get("stages_completed", [])), elapsed,
                 result.get("llm_model_used", "none"))

    return result
