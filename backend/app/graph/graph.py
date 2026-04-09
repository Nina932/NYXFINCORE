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

logger = logging.getLogger(__name__)


def _should_run_orchestrator(state: FinAIState) -> str:
    """Route: run legacy orchestrator only if full data available."""
    if state.get("data_type") in ("full_financials", "basic_pl"):
        return "orchestrator"
    return "reasoner"


def build_finai_graph() -> StateGraph:
    """Build the FinAI LangGraph agent pipeline."""

    workflow = StateGraph(FinAIState)

    # Add all 10 nodes
    workflow.add_node("data_extractor", data_extractor_node)
    workflow.add_node("calculator", calculator_node)
    workflow.add_node("insight_engine", insight_engine_node)
    workflow.add_node("memory", memory_node)
    workflow.add_node("orchestrator", orchestrator_node)
    workflow.add_node("reasoner", reasoner_node)
    workflow.add_node("anomaly_detector", anomaly_detector_node)
    workflow.add_node("whatif_simulator", whatif_simulator_node)
    workflow.add_node("report_generator", report_generator_node)
    workflow.add_node("alerts", alert_node)

    # Sequential flow: Extract → Calculate → Insight → Memory
    workflow.add_edge(START, "data_extractor")
    workflow.add_edge("data_extractor", "calculator")
    workflow.add_edge("calculator", "insight_engine")
    workflow.add_edge("insight_engine", "memory")

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
