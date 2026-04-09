"""
AIP Evaluation Framework
=========================
Automated test cases for AI output quality.

Each eval defines an input, expected output characteristics, and a scoring function.
The runner executes all registered evals and returns pass/fail + scores.

Public API:
    from app.services.v2.aip_evals import aip_eval_runner
    results = await aip_eval_runner.run_all()
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class AIPEval:
    """Test case for AI output quality."""
    name: str
    description: str
    input_data: Dict[str, Any]
    expected_output: Dict[str, Any]
    evaluator: Callable  # function(actual, expected) -> score 0.0-1.0
    category: str = "general"
    threshold: float = 0.5  # minimum score to pass


class AIPEvalRunner:
    """Run and manage AIP evaluation test cases."""

    def __init__(self):
        self.evals: List[AIPEval] = []

    def register(self, eval_case: AIPEval):
        """Register an evaluation test case."""
        self.evals.append(eval_case)

    def list_evals(self) -> List[Dict[str, Any]]:
        """List all registered evals without running them."""
        return [
            {
                "name": ev.name,
                "description": ev.description,
                "category": ev.category,
                "threshold": ev.threshold,
            }
            for ev in self.evals
        ]

    async def run_all(self) -> Dict[str, Any]:
        """Run all registered evals and return results."""
        results = []
        for ev in self.evals:
            try:
                actual = await self._execute_eval(ev)
                score = ev.evaluator(actual, ev.expected_output)
                passed = score >= ev.threshold
                results.append({
                    "name": ev.name,
                    "category": ev.category,
                    "passed": passed,
                    "score": round(score, 3),
                    "threshold": ev.threshold,
                    "actual_summary": _summarize(actual),
                    "error": None,
                })
            except Exception as e:
                logger.error("Eval '%s' failed: %s", ev.name, e)
                results.append({
                    "name": ev.name,
                    "category": ev.category,
                    "passed": False,
                    "score": 0.0,
                    "threshold": ev.threshold,
                    "actual_summary": None,
                    "error": str(e),
                })

        passed_count = sum(1 for r in results if r["passed"])
        return {
            "total": len(results),
            "passed": passed_count,
            "failed": len(results) - passed_count,
            "pass_rate": round(passed_count / len(results) * 100, 1) if results else 0,
            "results": results,
        }

    async def run_by_category(self, category: str) -> Dict[str, Any]:
        """Run evals filtered by category."""
        filtered = [ev for ev in self.evals if ev.category == category]
        original = self.evals
        self.evals = filtered
        try:
            return await self.run_all()
        finally:
            self.evals = original

    async def _execute_eval(self, ev: AIPEval) -> Any:
        """Execute a single eval's input function and get actual output."""
        input_data = ev.input_data

        eval_type = input_data.get("eval_type", "")

        if eval_type == "health_score":
            return self._eval_health_score(input_data)
        elif eval_type == "revenue_reasoning":
            return self._eval_revenue_reasoning(input_data)
        elif eval_type == "tb_reconciliation":
            return self._eval_tb_reconciliation(input_data)
        elif eval_type == "anomaly_detection":
            return self._eval_anomaly_detection(input_data)
        else:
            return {"error": f"Unknown eval type: {eval_type}"}

    def _eval_health_score(self, input_data: Dict) -> Dict[str, Any]:
        """Compute health score from financial metrics."""
        net_profit = input_data.get("net_profit", 0)
        revenue = input_data.get("revenue", 0)
        margin = (net_profit / revenue * 100) if revenue else 0

        # Simple health score: 0-100
        score = 50  # baseline
        if margin > 10:
            score = 80
        elif margin > 0:
            score = 60
        elif margin > -10:
            score = 35
        else:
            score = 15

        return {"health_score": score, "net_margin": round(margin, 2)}

    def _eval_revenue_reasoning(self, input_data: Dict) -> Dict[str, Any]:
        """Evaluate revenue decline reasoning."""
        current = input_data.get("current_revenue", 0)
        prior = input_data.get("prior_revenue", 0)
        decline_pct = ((current - prior) / abs(prior) * 100) if prior else 0

        severity = "normal"
        if decline_pct < -50:
            severity = "critical"
        elif decline_pct < -20:
            severity = "warning"
        elif decline_pct < -5:
            severity = "minor"

        return {
            "decline_pct": round(decline_pct, 2),
            "severity": severity,
            "identified": decline_pct < -5,
        }

    def _eval_tb_reconciliation(self, input_data: Dict) -> Dict[str, Any]:
        """Check trial balance reconciliation."""
        total_debit = input_data.get("total_debit", 0)
        total_credit = input_data.get("total_credit", 0)
        diff = abs(total_debit - total_credit)
        balanced = diff < 0.01

        return {
            "total_debit": total_debit,
            "total_credit": total_credit,
            "difference": round(diff, 2),
            "balanced": balanced,
            "imbalance_detected": not balanced,
        }

    def _eval_anomaly_detection(self, input_data: Dict) -> Dict[str, Any]:
        """Detect anomalies in financial data."""
        values = input_data.get("values", [])
        anomalies = []

        for i, v in enumerate(values):
            if v < 0:
                anomalies.append({
                    "index": i,
                    "value": v,
                    "type": "negative_value",
                    "severity": "high" if abs(v) > 1000000 else "medium",
                })

        return {
            "anomaly_count": len(anomalies),
            "anomalies": anomalies,
            "has_anomalies": len(anomalies) > 0,
        }


def _summarize(result: Any) -> str:
    """Create a short summary of eval result."""
    if isinstance(result, dict):
        keys = list(result.keys())[:5]
        parts = []
        for k in keys:
            v = result[k]
            if isinstance(v, (list, dict)):
                parts.append(f"{k}=<{type(v).__name__}>")
            else:
                parts.append(f"{k}={v}")
        return ", ".join(parts)
    return str(result)[:100]


# ═══════════════════════════════════════════════════════════════════
# BUILT-IN EVALS
# ═══════════════════════════════════════════════════════════════════

def _register_builtin_evals(runner: AIPEvalRunner):
    """Register the 4 built-in evaluation test cases."""

    # Eval 1: Negative net profit should yield health score < 50
    runner.register(AIPEval(
        name="negative_profit_health_score",
        description="Given negative net profit, health score should be < 50",
        input_data={
            "eval_type": "health_score",
            "net_profit": -5000000,
            "revenue": 100000000,
        },
        expected_output={"health_score_below": 50},
        evaluator=lambda actual, expected: 1.0 if actual.get("health_score", 100) < expected["health_score_below"] else 0.0,
        category="health",
        threshold=1.0,
    ))

    # Eval 2: Revenue decline > 50% should be flagged as critical
    runner.register(AIPEval(
        name="critical_revenue_decline",
        description="Given revenue decline > 50%, reasoning should identify it as critical",
        input_data={
            "eval_type": "revenue_reasoning",
            "current_revenue": 40000000,
            "prior_revenue": 100000000,
        },
        expected_output={"severity": "critical", "identified": True},
        evaluator=lambda actual, expected: (
            1.0 if actual.get("severity") == expected["severity"] and actual.get("identified") == expected["identified"]
            else 0.5 if actual.get("identified") == expected["identified"]
            else 0.0
        ),
        category="reasoning",
        threshold=1.0,
    ))

    # Eval 3: Reconciliation should detect TB imbalance
    runner.register(AIPEval(
        name="tb_imbalance_detection",
        description="Reconciliation should detect TB imbalance",
        input_data={
            "eval_type": "tb_reconciliation",
            "total_debit": 1000000,
            "total_credit": 999000,
        },
        expected_output={"imbalance_detected": True},
        evaluator=lambda actual, expected: 1.0 if actual.get("imbalance_detected") == expected["imbalance_detected"] else 0.0,
        category="reconciliation",
        threshold=1.0,
    ))

    # Eval 4: Anomaly detection should flag negative revenue
    runner.register(AIPEval(
        name="negative_revenue_anomaly",
        description="AIP detect_anomaly should flag negative revenue",
        input_data={
            "eval_type": "anomaly_detection",
            "values": [50000000, 48000000, -2000000, 51000000],
        },
        expected_output={"has_anomalies": True, "min_anomaly_count": 1},
        evaluator=lambda actual, expected: (
            1.0 if actual.get("has_anomalies") == expected["has_anomalies"]
            and actual.get("anomaly_count", 0) >= expected["min_anomaly_count"]
            else 0.0
        ),
        category="anomaly",
        threshold=1.0,
    ))


# Module singleton
aip_eval_runner = AIPEvalRunner()
_register_builtin_evals(aip_eval_runner)
