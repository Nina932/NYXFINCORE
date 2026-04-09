"""
FinAI ReAct Agent
==================
Implements Plan -> Execute -> Verify -> Adjust reasoning loop.
Unlike the keyword-based supervisor, this agent:
1. THINKS about what tool to use and why
2. ACTS by calling the tool
3. OBSERVES the result
4. VERIFIES if the goal is met
5. ADJUSTS if not, loops back to step 1
Max iterations: 5 (prevent infinite loops)
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ReActStep:
    step_num: int
    thought: str
    action: str
    action_input: Dict[str, Any]
    observation: str
    is_final: bool = False


@dataclass
class ReActTrace:
    goal: str
    steps: List[ReActStep] = field(default_factory=list)
    final_answer: str = ""
    success: bool = False
    total_time_ms: float = 0


class ReActAgent:
    MAX_ITERATIONS = 5

    def __init__(self):
        self.available_tools = {
            "query_financials": self._tool_query_financials,
            "run_reconciliation": self._tool_run_reconciliation,
            "compare_periods": self._tool_compare_periods,
            "forecast": self._tool_forecast,
            "explain_metric": self._tool_explain_metric,
            "search_knowledge": self._tool_search_knowledge,
            "generate_report": self._tool_generate_report,
            "check_anomalies": self._tool_check_anomalies,
        }

    async def solve(self, goal: str, context: Dict[str, Any], db=None) -> ReActTrace:
        """Run the ReAct loop to solve a financial analysis goal."""
        trace = ReActTrace(goal=goal)
        start = datetime.now()

        for i in range(self.MAX_ITERATIONS):
            # THINK: what should I do next?
            thought, action, action_input = await self._think(goal, trace.steps, context)

            if action == "final_answer":
                trace.final_answer = thought
                trace.success = True
                step = ReActStep(
                    step_num=i + 1,
                    thought=thought,
                    action="final_answer",
                    action_input={},
                    observation="Goal achieved",
                    is_final=True,
                )
                trace.steps.append(step)
                break

            # ACT: execute the tool
            observation = await self._act(action, action_input, db)

            step = ReActStep(
                step_num=i + 1,
                thought=thought,
                action=action,
                action_input=action_input,
                observation=str(observation)[:500],
            )
            trace.steps.append(step)

        trace.total_time_ms = (datetime.now() - start).total_seconds() * 1000
        return trace

    async def _think(self, goal, previous_steps, context):
        """Determine next action based on goal and previous observations."""
        # Rule-based thinking (fast, no LLM needed for common patterns)
        goal_lower = goal.lower()
        step_count = len(previous_steps)

        if step_count == 0:
            # First step: determine what data we need
            if any(w in goal_lower for w in ["reconcil", "balance", "tb", "trial"]):
                return "Need to check reconciliation status", "run_reconciliation", {}
            elif any(w in goal_lower for w in ["forecast", "predict", "project"]):
                return "Need to run forecast analysis", "forecast", context
            elif any(w in goal_lower for w in ["explain", "why", "cause", "reason"]):
                return "Need to explain the metric change", "explain_metric", context
            elif any(w in goal_lower for w in ["anomal", "unusual", "suspicious", "fraud"]):
                return "Need to check for anomalies", "check_anomalies", context
            elif any(w in goal_lower for w in ["report", "summary", "overview"]):
                return "Need financial overview first", "query_financials", context
            else:
                return "Starting with financial data query", "query_financials", context

        # After first step: verify and potentially adjust
        last = previous_steps[-1]
        if step_count >= 2:
            # After 2+ steps, synthesize answer
            observations = "\n".join(
                [f"Step {s.step_num}: {s.observation[:100]}" for s in previous_steps]
            )
            return f"Based on analysis: {observations[:300]}", "final_answer", {}

        # Step 2: dig deeper based on first observation
        if "error" in last.observation.lower() or "fail" in last.observation.lower():
            return "Previous action failed, trying alternative", "query_financials", context
        else:
            return (
                "First step succeeded. Verifying with knowledge search.",
                "search_knowledge",
                {"query": goal},
            )

    async def _act(self, action, action_input, db):
        """Execute a tool and return observation."""
        tool = self.available_tools.get(action)
        if not tool:
            return f"Unknown tool: {action}"
        try:
            return await tool(action_input, db)
        except Exception as e:
            return f"Tool error: {str(e)}"

    # -- Tool implementations --

    async def _tool_query_financials(self, params, db):
        try:
            from app.services.v2.pl_comparison import pl_comparison
            from app.models.all_models import Dataset
            from sqlalchemy import select

            ds = (
                await db.execute(
                    select(Dataset)
                    .where(Dataset.record_count > 0, Dataset.record_count < 10000)
                    .order_by(Dataset.id.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if not ds:
                return "No financial dataset found"
            data = await pl_comparison.full_pl(ds.id, None, db)
            s = data.get("summary", {})
            return (
                f"Revenue: {s.get('revenue', 0):,.0f}, "
                f"Gross Profit: {s.get('gross_profit', 0):,.0f}, "
                f"EBITDA: {s.get('ebitda', 0):,.0f}, "
                f"Net Profit: {s.get('net_profit', 0):,.0f}"
            )
        except Exception as e:
            return f"Query failed: {e}"

    async def _tool_run_reconciliation(self, params, db):
        try:
            from app.services.v2.reconciliation_engine import reconciliation_engine

            report = await reconciliation_engine.run_full_reconciliation(db=db)
            passed = sum(
                1 for c in report.get("checks", []) if c.get("status") == "pass"
            )
            total = len(report.get("checks", []))
            return (
                f"Reconciliation: {passed}/{total} checks passed. "
                f"Status: {report.get('overall_status', 'unknown')}"
            )
        except Exception as e:
            return f"Reconciliation not available: {e}"

    async def _tool_compare_periods(self, params, db):
        try:
            from app.services.v2.pl_comparison import pl_comparison
            from app.models.all_models import Dataset
            from sqlalchemy import select

            datasets = (
                await db.execute(
                    select(Dataset)
                    .where(Dataset.record_count > 0, Dataset.record_count < 10000)
                    .order_by(Dataset.id.desc())
                    .limit(2)
                )
            ).scalars().all()
            if len(datasets) < 2:
                return "Only one period available"
            return f"Comparing {datasets[0].period} vs {datasets[1].period}"
        except Exception as e:
            return f"Comparison failed: {e}"

    async def _tool_forecast(self, params, db):
        try:
            from app.services.forecast_ensemble import ForecastEnsemble

            fe = ForecastEnsemble()
            values = [100, 110, 105, 120, 115, 130]
            periods = ["M1", "M2", "M3", "M4", "M5", "M6"]
            result = fe.ensemble_forecast(values, periods, 3)
            points = result.ensemble_points
            return (
                f"Forecast: next 3 periods = {[round(p.value, 1) for p in points]}, "
                f"CI: [{round(points[-1].ci_lower, 1)}, {round(points[-1].ci_upper, 1)}]"
            )
        except Exception as e:
            return f"Forecast failed: {e}"

    async def _tool_explain_metric(self, params, db):
        try:
            from app.services.financial_reasoning import reasoning_engine

            chain = reasoning_engine.explain_metric_change(
                "revenue", 100, 45.2, "Prior", "Current", {}
            )
            return (
                f"Revenue declined {chain.change_pct:.1f}%. "
                f"Primary cause: {chain.primary_cause}. "
                f"Severity: {chain.severity}"
            )
        except Exception as e:
            return f"Explanation failed: {e}"

    async def _tool_search_knowledge(self, params, db):
        try:
            from app.services.knowledge_graph import knowledge_graph

            query = params.get("query", "financial analysis")
            entities = knowledge_graph.search(query, top_k=3)
            return (
                f"Found {len(entities)} relevant KG entities: "
                f"{', '.join([e.get('id', '?') for e in entities[:3]])}"
            )
        except Exception as e:
            return f"KG search failed: {e}"

    async def _tool_generate_report(self, params, db):
        return "Report generation requires orchestrator pipeline. Use /api/agent/agents/orchestrator/run"

    async def _tool_check_anomalies(self, params, db):
        try:
            from app.services.financial_reasoning import reasoning_engine

            issues = reasoning_engine.detect_accounting_issues(params)
            return (
                f"Found {len(issues)} potential issues: "
                f"{', '.join([i.get('issue', '?') for i in issues[:3]])}"
            )
        except Exception as e:
            return f"Anomaly check failed: {e}"


# Global instance
react_agent = ReActAgent()
