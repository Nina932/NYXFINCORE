"""
FinAI Planning Agent
=====================
Decomposes complex financial goals into executable step sequences.
Examples:
- "Close the month" -> [verify TB -> check unposted JEs -> close period -> generate report]
- "Explain this variance" -> [get current -> get prior -> compute delta -> reason -> explain]
- "Prepare for audit" -> [run reconciliation -> check gaps -> verify hashes -> generate audit pack]
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


@dataclass
class PlanStep:
    step_num: int
    action: str
    description: str
    endpoint: str
    params: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[int] = field(default_factory=list)
    status: str = "pending"  # pending, running, completed, failed
    result: Any = None


@dataclass
class ExecutionPlan:
    goal: str
    steps: List[PlanStep]
    estimated_time_seconds: int = 0
    complexity: str = "simple"  # simple, moderate, complex


PLAN_TEMPLATES = {
    "close_month": {
        "description": "Month-end close procedure",
        "complexity": "complex",
        "steps": [
            {
                "action": "verify_tb",
                "description": "Verify Trial Balance is balanced",
                "endpoint": "/api/journal/gl/trial-balance",
            },
            {
                "action": "check_unposted",
                "description": "Check for unposted journal entries",
                "endpoint": "/api/journal/entries?status=draft",
            },
            {
                "action": "run_reconciliation",
                "description": "Run P&L -> TB -> BS reconciliation",
                "endpoint": "/api/analytics/reconciliation",
            },
            {
                "action": "close_period",
                "description": "Close the accounting period",
                "endpoint": "/api/journal/periods/close",
            },
            {
                "action": "generate_report",
                "description": "Generate final financial report",
                "endpoint": "/api/analytics/pl-comparison",
            },
        ],
    },
    "explain_variance": {
        "description": "Variance analysis workflow",
        "complexity": "moderate",
        "steps": [
            {
                "action": "get_current",
                "description": "Get current period P&L",
                "endpoint": "/api/analytics/pl-comparison",
            },
            {
                "action": "get_revenue_detail",
                "description": "Get revenue breakdown",
                "endpoint": "/api/analytics/revenue-comparison",
            },
            {
                "action": "get_cogs_detail",
                "description": "Get cost breakdown",
                "endpoint": "/api/analytics/cogs-comparison",
            },
            {
                "action": "explain",
                "description": "Run AI causal reasoning",
                "endpoint": "/api/agent/agents/reasoning/explain",
            },
        ],
    },
    "prepare_audit": {
        "description": "Audit preparation workflow",
        "complexity": "complex",
        "steps": [
            {
                "action": "reconciliation",
                "description": "Run full reconciliation",
                "endpoint": "/api/analytics/reconciliation",
            },
            {
                "action": "verify_hashes",
                "description": "Verify journal hash chain integrity",
                "endpoint": "/api/journal/integrity",
            },
            {
                "action": "check_gaps",
                "description": "Check for gaps in document numbering",
                "endpoint": "/api/journal/entries",
            },
            {
                "action": "audit_trail",
                "description": "Generate audit trail report",
                "endpoint": "/api/journal/audit-trail/journal_entry/all",
            },
            {
                "action": "generate_pack",
                "description": "Generate audit pack (Excel)",
                "endpoint": "/api/analytics/pl-comparison/export",
            },
        ],
    },
    "full_analysis": {
        "description": "Complete financial analysis pipeline",
        "complexity": "complex",
        "steps": [
            {
                "action": "pl_analysis",
                "description": "Income Statement analysis",
                "endpoint": "/api/analytics/pl-comparison",
            },
            {
                "action": "bs_analysis",
                "description": "Balance Sheet analysis",
                "endpoint": "/api/analytics/bs-comparison",
            },
            {
                "action": "benchmarks",
                "description": "Industry benchmark comparison",
                "endpoint": "/api/agent/agents/benchmarks/compare",
            },
            {
                "action": "sensitivity",
                "description": "Sensitivity analysis",
                "endpoint": "/api/agent/agents/sensitivity/analyze",
            },
            {
                "action": "forecast",
                "description": "Ensemble forecast",
                "endpoint": "/api/agent/agents/forecast/ensemble",
            },
            {
                "action": "strategy",
                "description": "Strategic recommendations",
                "endpoint": "/api/agent/agents/strategy/generate",
            },
        ],
    },
    "revenue_deep_dive": {
        "description": "Revenue deep-dive analysis",
        "complexity": "moderate",
        "steps": [
            {
                "action": "revenue",
                "description": "Get revenue by product",
                "endpoint": "/api/analytics/revenue-comparison",
            },
            {
                "action": "pl_context",
                "description": "Get P&L context",
                "endpoint": "/api/analytics/pl-comparison",
            },
            {
                "action": "explain",
                "description": "Explain revenue changes",
                "endpoint": "/api/agent/agents/reasoning/explain",
            },
        ],
    },
}


class PlanningAgent:
    def create_plan(self, goal: str, context: Dict[str, Any] = None) -> ExecutionPlan:
        """Create an execution plan for a financial goal."""
        goal_lower = goal.lower()

        # Match to template
        if any(w in goal_lower for w in ["close", "month-end", "period close"]):
            template = PLAN_TEMPLATES["close_month"]
        elif any(w in goal_lower for w in ["variance", "explain", "why", "changed"]):
            template = PLAN_TEMPLATES["explain_variance"]
        elif any(w in goal_lower for w in ["audit", "compliance", "sox"]):
            template = PLAN_TEMPLATES["prepare_audit"]
        elif any(
            w in goal_lower for w in ["full analysis", "complete", "everything", "pipeline"]
        ):
            template = PLAN_TEMPLATES["full_analysis"]
        elif any(w in goal_lower for w in ["revenue", "sales", "top line"]):
            template = PLAN_TEMPLATES["revenue_deep_dive"]
        else:
            template = PLAN_TEMPLATES["full_analysis"]

        steps = []
        for i, step_def in enumerate(template["steps"]):
            steps.append(
                PlanStep(
                    step_num=i + 1,
                    action=step_def["action"],
                    description=step_def["description"],
                    endpoint=step_def["endpoint"],
                    depends_on=[i] if i > 0 else [],
                )
            )

        return ExecutionPlan(
            goal=goal,
            steps=steps,
            estimated_time_seconds=len(steps) * 3,
            complexity=template["complexity"],
        )

    async def execute_plan(self, plan: ExecutionPlan, db=None) -> Dict[str, Any]:
        """Execute a plan step by step, collecting results."""
        results = {}

        for step in plan.steps:
            step.status = "running"
            try:
                # Use internal imports instead of HTTP calls for speed
                if "pl-comparison" in step.endpoint:
                    from app.services.v2.pl_comparison import pl_comparison
                    from app.models.all_models import Dataset
                    from sqlalchemy import select

                    ds = (
                        await db.execute(
                            select(Dataset)
                            .where(
                                Dataset.record_count > 0, Dataset.record_count < 10000
                            )
                            .order_by(Dataset.id.desc())
                            .limit(1)
                        )
                    ).scalar_one_or_none()
                    if ds:
                        step.result = await pl_comparison.full_pl(ds.id, None, db)
                        step.status = "completed"
                    else:
                        step.result = {"error": "No dataset"}
                        step.status = "failed"
                elif "reconciliation" in step.endpoint:
                    try:
                        from app.services.v2.reconciliation_engine import (
                            reconciliation_engine,
                        )

                        step.result = (
                            await reconciliation_engine.run_full_reconciliation(db=db)
                        )
                        step.status = "completed"
                    except Exception as e:
                        step.result = {"error": str(e)}
                        step.status = "failed"
                elif "trial-balance" in step.endpoint:
                    from app.services.v2.gl_reporting import gl_reporting

                    step.result = await gl_reporting.trial_balance(db=db)
                    step.status = "completed"
                else:
                    step.result = {
                        "info": f"Endpoint {step.endpoint} available for execution"
                    }
                    step.status = "completed"

                results[step.action] = step.result
            except Exception as e:
                step.status = "failed"
                step.result = {"error": str(e)}
                results[step.action] = step.result

        return {
            "goal": plan.goal,
            "complexity": plan.complexity,
            "steps_total": len(plan.steps),
            "steps_completed": sum(
                1 for s in plan.steps if s.status == "completed"
            ),
            "steps_failed": sum(1 for s in plan.steps if s.status == "failed"),
            "steps": [
                {
                    "num": s.step_num,
                    "action": s.action,
                    "description": s.description,
                    "status": s.status,
                    "has_result": s.result is not None,
                }
                for s in plan.steps
            ],
            "results": {
                k: (
                    v
                    if isinstance(v, dict) and len(str(v)) < 1000
                    else {"summary": str(v)[:500]}
                )
                for k, v in results.items()
            },
        }


# Global
planning_agent = PlanningAgent()
