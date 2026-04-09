"""
FinAI Decision Agent — Decision intelligence, prediction tracking, monitoring.
═══════════════════════════════════════════════════════════════════════════════
The Decision Agent is the "what to do" engine. While InsightAgent explains WHY
something happened, DecisionAgent generates ACTIONS:

  - Generate ranked business actions from diagnostic signals
  - Simulate financial impact of each action
  - Track prediction accuracy and self-calibrate
  - Monitor financial metrics and generate proactive alerts

Tools owned:
  - generate_actions            -> ranked business actions from diagnosis
  - simulate_action_impact      -> scenario simulation for a specific action
  - get_decision_report         -> full decision intelligence report
  - get_predictions             -> prediction accuracy and learning report
  - get_monitoring_status       -> current monitoring state and active alerts

Architecture:
  Supervisor -> DecisionAgent.execute(task) -> decision_engine / prediction_tracker / monitoring_engine
                                             -> returns AgentResult with actions + simulations
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.agents.base import BaseAgent, AgentTask, AgentContext, AgentResult
from app.agents.registry import registry

logger = logging.getLogger(__name__)


# Tools this agent owns
DECISION_TOOLS = [
    "generate_actions",
    "simulate_action_impact",
    "get_decision_report",
    "get_predictions",
    "get_monitoring_status",
]

# Template fallback responses for when Claude API is unavailable
DECISION_TEMPLATE_RESPONSES = {
    "generate_actions": (
        "Decision intelligence engine analysis:\n\n"
        "The system evaluates financial signals and generates ranked actions across 5 categories:\n"
        "- Cost Reduction: supplier negotiation, procurement optimization\n"
        "- Revenue Growth: pricing review, channel expansion\n"
        "- Risk Mitigation: hedging, compliance hardening\n"
        "- Capital Optimization: debt restructuring, working capital improvement\n"
        "- Operational Efficiency: automation, process optimization\n\n"
        "Each action is scored by composite formula: 0.40*ROI + 0.25*urgency + 0.20*feasibility + 0.15*risk_factor.\n"
        "Please provide financial data for specific action recommendations."
    ),
    "simulate_action_impact": (
        "Action impact simulation uses the financial reasoning engine to project P&L changes.\n"
        "Please specify the action to simulate with base financial data."
    ),
    "get_decision_report": (
        "The decision report includes:\n"
        "- Top ranked business actions with ROI estimates\n"
        "- Risk matrix (low/medium/high/critical grouping)\n"
        "- Total potential impact and projected health score improvement\n"
        "Please provide current and previous period financials."
    ),
    "get_predictions": (
        "The prediction learning system tracks forecast accuracy:\n"
        "- Records predictions from all forecast methods\n"
        "- Matches predictions to actual outcomes\n"
        "- Computes calibration adjustments per method\n"
        "- Generates accuracy reports by method and metric."
    ),
    "get_monitoring_status": (
        "Real-time monitoring tracks financial metrics against configurable thresholds:\n"
        "- 5 default rules (gross margin, net margin, current ratio, D/E, EBITDA margin)\n"
        "- Cooldown-based deduplication prevents alert storms\n"
        "- Auto-generates diagnostic reports on critical/emergency alerts."
    ),
}


class DecisionAgent(BaseAgent):
    """Decision intelligence, prediction tracking, and monitoring specialist.

    Owns decision/prediction/monitoring tools. Generates actionable business
    recommendations grounded in deterministic financial analysis.

    Resilience:
    - Template fallback responses when Claude API is down
    - Health tracking via BaseAgent.safe_execute()
    - Graceful degradation on service failures
    """

    name = "decision"
    description = "Decision intelligence — business actions, predictions, monitoring"
    capabilities = ["decision", "prediction", "monitoring", "strategy"]
    tools = []  # Tools routed via Supervisor TOOL_ROUTING

    def can_handle(self, task: AgentTask) -> bool:
        return (
            task.task_type in self.capabilities
            or task.parameters.get("tool_name") in DECISION_TOOLS
        )

    async def execute(self, task: AgentTask, context: AgentContext) -> AgentResult:
        """Route to appropriate decision/prediction/monitoring service."""
        tool_name = task.parameters.get("tool_name", "")
        tool_params = task.parameters.get("tool_params", {})

        try:
            if tool_name == "generate_actions":
                return await self._handle_generate_actions(tool_params, context)
            elif tool_name == "simulate_action_impact":
                return await self._handle_simulate_action(tool_params, context)
            elif tool_name == "get_decision_report":
                return await self._handle_decision_report(tool_params, context)
            elif tool_name == "get_predictions":
                return await self._handle_predictions(tool_params, context)
            elif tool_name == "get_monitoring_status":
                return await self._handle_monitoring_status(tool_params, context)
            else:
                return self._error_result(f"Unknown decision tool: {tool_name}")
        except Exception as e:
            logger.error("DecisionAgent error on %s: %s", tool_name, e)
            return self._error_result(str(e))

    async def _handle_generate_actions(self, params: Dict, context: AgentContext) -> AgentResult:
        """Generate ranked business actions from financial diagnosis."""
        from app.services.decision_engine import decision_engine
        from app.services.diagnosis_engine import diagnosis_engine

        financials = params.get("current", params.get("financials", {}))
        previous = params.get("previous", None)
        balance_sheet = params.get("balance_sheet", None)
        industry = params.get("industry", "fuel_distribution")
        top_n = params.get("top_n", 10)

        # Run diagnosis first
        report = diagnosis_engine.run_full_diagnosis(
            current_financials=financials,
            previous_financials=previous,
            balance_sheet=balance_sheet,
            industry_id=industry,
        )

        # Generate decision report
        decision_report = decision_engine.generate_decision_report(
            report=report,
            financials=financials,
            top_n=top_n,
        )

        return self._make_result(
            data=decision_report.to_dict(),
            narrative=f"Generated {decision_report.total_actions_evaluated} actions, "
                      f"top {len(decision_report.top_actions)} ranked by composite score.",
        )

    async def _handle_simulate_action(self, params: Dict, context: AgentContext) -> AgentResult:
        """Simulate impact of a specific action."""
        from app.services.decision_engine import decision_engine, BusinessAction

        action_desc = params.get("description", "Custom action")
        category = params.get("category", "operational_efficiency")
        financials = params.get("financials", {})

        action = BusinessAction(
            action_id=f"custom_{category}",
            description=action_desc,
            category=category,
            expected_impact=0,
            implementation_cost=params.get("cost", 50_000),
            roi_estimate=0,
            risk_level=params.get("risk", "medium"),
            time_horizon=params.get("horizon", "short_term"),
            source_signal="manual",
        )

        result = decision_engine.simulator.simulate_action(action, financials)
        return self._make_result(data=result, narrative=result.get("narrative", ""))

    async def _handle_decision_report(self, params: Dict, context: AgentContext) -> AgentResult:
        """Get the most recent or generate a new decision report."""
        from app.services.decision_engine import decision_engine

        report = decision_engine.get_last_report()
        if report:
            return self._make_result(data=report.to_dict())

        return self._error_result("No decision report available. Use generate_actions first.")

    async def _handle_predictions(self, params: Dict, context: AgentContext) -> AgentResult:
        """Get prediction accuracy and learning report."""
        from app.services.prediction_tracker import prediction_tracker
        report = prediction_tracker.generate_report()
        return self._make_result(data=report.to_dict())

    async def _handle_monitoring_status(self, params: Dict, context: AgentContext) -> AgentResult:
        """Get monitoring dashboard with active alerts."""
        from app.services.monitoring_engine import monitoring_engine
        dashboard = monitoring_engine.get_dashboard()
        return self._make_result(data=dashboard.to_dict())

    def get_template_response(self, tool_name: str) -> Optional[str]:
        """Return fallback response when Claude API is unavailable."""
        return DECISION_TEMPLATE_RESPONSES.get(tool_name)


# Register with the agent registry
registry.register(DecisionAgent())
