"""
Phase K: Financial Intelligence Orchestrator
==============================================
End-to-end pipeline that chains every subsystem into a single autonomous flow:

    Input financials
        → Diagnosis (signal detection, root cause, health score)
        → Decision Intelligence (ranked actions, CFO verdict)
        → Strategy (phased plan, time projection)
        → Simulation (sensitivity, Monte Carlo)
        → Monitoring (alerts, KPIs, cash runway, expense spikes)
        → Persistent Learning (track, calibrate, feed back)

This is the system's "brain" — the single entry point that runs the entire
financial intelligence pipeline and returns a unified strategic assessment.

Rules:
    - ALL financial math is deterministic (no LLM)
    - Pipeline stages are independent and composable
    - Failures in one stage don't block subsequent stages
    - Every stage result is captured for audit trail
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# ORCHESTRATOR OUTPUT
# ═══════════════════════════════════════════════════════════════════

@dataclass
class OrchestratorResult:
    """
    Complete output of the full financial intelligence pipeline.

    Contains every layer's output in a single, auditable structure.
    This is what a board presentation is built from.
    """
    # Stage 1: Diagnosis
    health_score: float = 0.0
    health_grade: str = "F"
    signals_detected: int = 0
    diagnoses_count: int = 0
    recommendations_count: int = 0
    diagnosis_summary: Dict[str, Any] = field(default_factory=dict)

    # Stage 2: Decision Intelligence
    actions_evaluated: int = 0
    top_action: Optional[Dict[str, Any]] = None
    cfo_verdict: Optional[Dict[str, Any]] = None
    conviction_grade: str = "F"
    do_nothing_cost: float = 0.0

    # Stage 3: Strategy
    strategy_name: str = ""
    strategy_phases: int = 0
    strategy_duration_days: int = 0
    strategy_roi: float = 0.0
    time_projection: List[Dict[str, Any]] = field(default_factory=list)
    strategy_summary: Optional[Dict[str, Any]] = None

    # Stage 4: Simulation
    most_sensitive_variable: str = ""
    monte_carlo_probability_positive: float = 0.0
    monte_carlo_var_95: float = 0.0
    sensitivity_summary: Optional[Dict[str, Any]] = None

    # Stage 5: Monitoring
    active_alerts: int = 0
    critical_alerts: int = 0
    system_health: str = "unknown"
    kpi_missed: int = 0
    kpi_on_track: int = 0
    cash_runway_months: float = 0.0
    cash_runway_risk: str = "unknown"
    expense_spikes: int = 0
    monitoring_summary: Optional[Dict[str, Any]] = None

    # Stage 6: Learning
    learning_summary: Optional[Dict[str, Any]] = None

    # Stage 7: Analogy
    analogy_matches: int = 0
    dominant_historical_strategy: str = ""
    analogy_confidence: float = 0.0
    analogy_summary: Optional[Dict[str, Any]] = None

    # Meta
    stages_completed: List[str] = field(default_factory=list)
    stages_failed: List[str] = field(default_factory=list)
    execution_time_ms: int = 0
    generated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "executive_summary": {
                "health_score": round(self.health_score, 1),
                "health_grade": self.health_grade,
                "conviction_grade": self.conviction_grade,
                "strategy_name": self.strategy_name,
                "do_nothing_cost": round(self.do_nothing_cost, 2),
                "cash_runway_months": round(self.cash_runway_months, 1),
                "system_health": self.system_health,
                "stages_completed": len(self.stages_completed),
                "stages_failed": len(self.stages_failed),
            },
            "diagnosis": self.diagnosis_summary,
            "decision": {
                "actions_evaluated": self.actions_evaluated,
                "top_action": self.top_action,
                "cfo_verdict": self.cfo_verdict,
            },
            "strategy": self.strategy_summary,
            "simulation": self.sensitivity_summary,
            "monitoring": self.monitoring_summary,
            "learning": self.learning_summary,
            "analogy": self.analogy_summary,
            "time_projection": self.time_projection,
            "meta": {
                "stages_completed": self.stages_completed,
                "stages_failed": self.stages_failed,
                "execution_time_ms": self.execution_time_ms,
                "generated_at": self.generated_at,
            },
        }


# ═══════════════════════════════════════════════════════════════════
# FINANCIAL INTELLIGENCE ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════

class FinancialOrchestrator:
    """
    The brain of the system. Chains all subsystems into a single autonomous flow.

    Pipeline:
        1. Diagnosis → health score, signals, root causes
        2. Decision → ranked actions, CFO verdict with conviction
        3. Strategy → phased plan, time projection
        4. Simulation → sensitivity, Monte Carlo, VaR
        5. Monitoring → alerts, KPIs, cash runway, spikes
        6. Learning → track outcomes, calibrate

    Each stage runs independently — failures are captured, not propagated.
    """

    def __init__(self):
        self._last_result: Optional[OrchestratorResult] = None
        self._run_count: int = 0

    def run(
        self,
        current_financials: Dict[str, float],
        previous_financials: Optional[Dict[str, float]] = None,
        balance_sheet: Optional[Dict[str, float]] = None,
        industry_id: str = "fuel_distribution",
        project_months: int = 12,
        monte_carlo_iterations: int = 500,
    ) -> OrchestratorResult:
        """
        Execute the full financial intelligence pipeline.

        Args:
            current_financials: Current P&L metrics
            previous_financials: Prior period metrics (optional, enables comparison)
            balance_sheet: BS metrics (optional, enables liquidity/runway)
            industry_id: Industry for benchmark comparison
            project_months: Months to project forward
            monte_carlo_iterations: MC simulation runs (lower = faster)

        Returns:
            OrchestratorResult with all stages' outputs
        """
        import time
        start = time.time()
        self._run_count += 1

        # ── Enrich financials with computed ratios ────────────────────
        # Subsystems (diagnosis, monitoring KPIs, decision engine) depend
        # on derived percentage metrics that may not be present in raw input.
        current_financials = self._enrich_financials(current_financials)
        if previous_financials:
            previous_financials = self._enrich_financials(previous_financials)

        result = OrchestratorResult(
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

        # ── Stage 1: DIAGNOSIS ──────────────────────────────────────
        diag_report = self._run_diagnosis(
            result, current_financials, previous_financials,
            balance_sheet, industry_id,
        )

        # ── Stage 2: DECISION INTELLIGENCE ──────────────────────────
        dec_report = self._run_decision(result, diag_report, current_financials)

        # ── Stage 3: STRATEGY ───────────────────────────────────────
        self._run_strategy(result, dec_report, diag_report, current_financials, project_months)

        # ── Stage 4: SIMULATION ─────────────────────────────────────
        self._run_simulation(result, current_financials, monte_carlo_iterations)

        # ── Stage 5: MONITORING ─────────────────────────────────────
        self._run_monitoring(result, current_financials, previous_financials, balance_sheet)

        # ── Stage 6: LEARNING ───────────────────────────────────────
        self._run_learning(result)

        # ── Stage 7: ANALOGY ──────────────────────────────────────
        self._run_analogy(result, current_financials, industry_id)

        # ── Finalize ────────────────────────────────────────────────
        result.execution_time_ms = int((time.time() - start) * 1000)
        self._last_result = result

        logger.info(
            "Orchestrator run #%d complete: %d/%d stages passed, health=%s, verdict=%s, %dms",
            self._run_count,
            len(result.stages_completed),
            len(result.stages_completed) + len(result.stages_failed),
            result.health_grade,
            result.conviction_grade,
            result.execution_time_ms,
        )

        return result

    # ── Financial enrichment ───────────────────────────────────────

    @staticmethod
    def _enrich_financials(fin: Dict[str, float]) -> Dict[str, float]:
        """
        Compute derived financial ratios from raw P&L/BS inputs.

        Subsystems like diagnosis, monitoring, and decision engine
        depend on percentage metrics (gross_margin_pct, net_margin_pct, etc.)
        that may not be present in the raw input from the user.
        """
        enriched = dict(fin)
        revenue = abs(enriched.get("revenue", 0)) or 1  # avoid div-by-zero

        # Gross profit
        cogs = abs(enriched.get("cogs", 0))
        if "gross_profit" not in enriched and revenue > 1:
            enriched["gross_profit"] = revenue - cogs

        gp = enriched.get("gross_profit", revenue - cogs)

        # Gross margin %
        if "gross_margin_pct" not in enriched and revenue > 1:
            enriched["gross_margin_pct"] = round(gp / revenue * 100, 2)

        # COGS to revenue %
        if "cogs_to_revenue_pct" not in enriched and revenue > 1:
            enriched["cogs_to_revenue_pct"] = round(cogs / revenue * 100, 2)

        # Map operating_expenses -> ga_expenses if needed
        if "ga_expenses" not in enriched and "operating_expenses" in enriched:
            enriched["ga_expenses"] = enriched["operating_expenses"]

        # EBITDA
        selling = abs(enriched.get("selling_expenses", 0))
        admin = abs(enriched.get("ga_expenses", 0)) or abs(enriched.get("admin_expenses", 0))
        dep = abs(enriched.get("depreciation", 0))
        if "ebitda" not in enriched and revenue > 1:
            enriched["ebitda"] = gp - selling - admin

        ebitda = enriched.get("ebitda", gp - selling - admin)

        # EBITDA margin %
        if "ebitda_margin_pct" not in enriched and revenue > 1:
            enriched["ebitda_margin_pct"] = round(ebitda / revenue * 100, 2)

        # Net margin %
        net = enriched.get("net_profit", 0)
        if "net_margin_pct" not in enriched and revenue > 1 and net != 0:
            enriched["net_margin_pct"] = round(net / revenue * 100, 2)

        # EBIT
        if "ebit" not in enriched and revenue > 1:
            enriched["ebit"] = ebitda - dep

        return enriched

    # ── Stage 1: Diagnosis ──────────────────────────────────────────

    def _run_diagnosis(self, result: OrchestratorResult,
                        current: Dict, previous: Optional[Dict],
                        balance_sheet: Optional[Dict], industry_id: str):
        """Run diagnostic pipeline."""
        try:
            from app.services.diagnosis_engine import diagnosis_engine

            report = diagnosis_engine.run_full_diagnosis(
                current_financials=current,
                previous_financials=previous,
                balance_sheet=balance_sheet,
                industry_id=industry_id,
            )

            result.health_score = report.health_score
            result.health_grade = report.health_grade
            result.signals_detected = sum(report.signal_summary.values())
            result.diagnoses_count = len(report.diagnoses)
            result.recommendations_count = len(report.recommendations)
            result.diagnosis_summary = report.to_dict()

            result.stages_completed.append("diagnosis")
            logger.info("Stage 1 (Diagnosis): health=%s (%s), %d signals, %d diagnoses",
                        report.health_score, report.health_grade,
                        result.signals_detected, result.diagnoses_count)
            return report

        except Exception as e:
            logger.error("Stage 1 (Diagnosis) failed: %s", e)
            result.stages_failed.append(f"diagnosis: {str(e)[:100]}")
            return None

    # ── Stage 2: Decision Intelligence ──────────────────────────────

    def _run_decision(self, result: OrchestratorResult, diag_report, current: Dict):
        """Run decision intelligence pipeline."""
        try:
            from app.services.decision_engine import decision_engine

            if diag_report is None:
                result.stages_failed.append("decision: no diagnosis available")
                return None

            dec_report = decision_engine.generate_decision_report(diag_report, current)

            result.actions_evaluated = dec_report.total_actions_evaluated
            if dec_report.top_actions:
                result.top_action = dec_report.top_actions[0].to_dict()
            if dec_report.cfo_verdict:
                result.cfo_verdict = dec_report.cfo_verdict.to_dict()
                result.conviction_grade = dec_report.cfo_verdict.conviction_grade
                result.do_nothing_cost = float(dec_report.cfo_verdict.do_nothing_cost)

            result.stages_completed.append("decision")
            logger.info("Stage 2 (Decision): %d actions, verdict=%s",
                        result.actions_evaluated, result.conviction_grade)
            return dec_report

        except Exception as e:
            logger.error("Stage 2 (Decision) failed: %s", e)
            result.stages_failed.append(f"decision: {str(e)[:100]}")
            return None

    # ── Stage 3: Strategy ───────────────────────────────────────────

    def _run_strategy(self, result: OrchestratorResult, dec_report, diag_report,
                       current: Dict, months: int):
        """Run strategy generation pipeline."""
        try:
            from app.services.strategy_engine import strategic_engine

            if dec_report is None or not dec_report.top_actions:
                # No urgent actions — company is healthy, generate "maintain" strategy
                result.strategy_name = "Maintain & Optimize"
                result.strategy_phases = 1
                result.strategy_roi = 0.0
                result.stages_completed.append("strategy")
                return

            health = diag_report.health_score if diag_report else 50.0
            strat_result = strategic_engine.generate_strategy(
                dec_report.top_actions, health, current, months,
            )

            strategy = strategic_engine.get_last_strategy()
            if strategy:
                result.strategy_name = strategy.name
                result.strategy_phases = len(strategy.phases)
                result.strategy_duration_days = strategy.total_duration_days
                result.strategy_roi = strategy.overall_roi
                result.time_projection = strat_result.get("time_projection", [])
                result.strategy_summary = strat_result.get("strategy", {})

            result.stages_completed.append("strategy")
            logger.info("Stage 3 (Strategy): %s (%d phases, %d days, ROI=%.1fx)",
                        result.strategy_name, result.strategy_phases,
                        result.strategy_duration_days, result.strategy_roi)

        except Exception as e:
            logger.error("Stage 3 (Strategy) failed: %s", e)
            result.stages_failed.append(f"strategy: {str(e)[:100]}")

    # ── Stage 4: Simulation ─────────────────────────────────────────

    def _run_simulation(self, result: OrchestratorResult, current: Dict,
                         mc_iterations: int):
        """Run sensitivity + Monte Carlo analysis."""
        try:
            from app.services.sensitivity_analyzer import (
                sensitivity_analyzer, scenario_monte_carlo,
            )

            # Sensitivity analysis
            sens = sensitivity_analyzer.analyze(current, steps=5)
            result.most_sensitive_variable = sens.most_sensitive_variable

            # Monte Carlo
            mc = scenario_monte_carlo.simulate(current, iterations=mc_iterations, seed=42)
            result.monte_carlo_probability_positive = float(1 - mc.probability_loss)
            result.monte_carlo_var_95 = float(mc.value_at_risk_95)

            # Build band details for PDF tornado chart
            band_details = []
            for b in sens.bands:
                bd = b.to_dict() if hasattr(b, "to_dict") else b
                band_details.append(bd)

            result.sensitivity_summary = {
                "sensitivity": {
                    "most_sensitive_variable": sens.most_sensitive_variable,
                    "least_sensitive_variable": sens.least_sensitive_variable,
                    "band_count": len(sens.bands),
                    "base_net_profit": float(round(sens.base_net_profit, 2)),
                    "bands": band_details,
                },
                "monte_carlo": {
                    "iterations": mc.iterations,
                    "mean_net_profit": float(round(mc.mean_net_profit, 2)),
                    "median_net_profit": float(round(mc.median_net_profit, 2)),
                    "p5_net_profit": float(round(mc.p5_net_profit, 2)),
                    "p95_net_profit": float(round(mc.p95_net_profit, 2)),
                    "probability_positive_pct": float(round((1 - mc.probability_loss) * 100, 1)),
                    "value_at_risk_95": float(round(mc.value_at_risk_95, 2)),
                },
            }

            result.stages_completed.append("simulation")
            logger.info("Stage 4 (Simulation): sensitive=%s, MC prob_positive=%.0f%%, VaR=%.0f",
                        sens.most_sensitive_variable,
                        (1.0 - mc.probability_loss) * 100, mc.value_at_risk_95)

        except Exception as e:
            logger.error("Stage 4 (Simulation) failed: %s", e)
            result.stages_failed.append(f"simulation: {str(e)[:100]}")

    # ── Stage 5: Monitoring ─────────────────────────────────────────

    def _run_monitoring(self, result: OrchestratorResult, current: Dict,
                         previous: Optional[Dict], balance_sheet: Optional[Dict]):
        """Run monitoring checks, KPIs, cash runway, expense spikes."""
        try:
            from app.services.monitoring_engine import monitoring_engine

            # Stage 5 is now DB-persisted

            # Alerts
            alerts = monitoring_engine.run_checks(current, balance_sheet)
            result.active_alerts = len(alerts)
            result.critical_alerts = sum(1 for a in alerts if a.severity in ("critical", "emergency"))

            # Dashboard
            dashboard = monitoring_engine.get_dashboard()
            result.system_health = dashboard.system_health

            # KPIs
            kpi_statuses = monitoring_engine.kpi_watcher.evaluate(current)
            result.kpi_missed = sum(1 for s in kpi_statuses if s.status == "missed")
            result.kpi_on_track = sum(1 for s in kpi_statuses if s.status in ("on_track", "exceeded"))

            # Cash runway
            revenue = abs(current.get("revenue", 0))
            expenses = abs(current.get("cogs", 0)) + abs(current.get("ga_expenses", 0))
            cash = 0.0
            if balance_sheet:
                cash = balance_sheet.get("cash", balance_sheet.get("total_current_assets", 0) * 0.3)

            if cash > 0 or expenses > revenue:
                runway = monitoring_engine.cash_runway.calculate(
                    cash_balance=cash,
                    monthly_revenue=revenue / 12,
                    monthly_expenses=expenses / 12,
                )
                result.cash_runway_months = runway.runway_months
                result.cash_runway_risk = runway.risk_level
            else:
                result.cash_runway_months = 999
                result.cash_runway_risk = "safe"

            # Expense spikes
            spike_details = []
            if previous:
                spikes = monitoring_engine.expense_spike.detect(
                    current_expenses={k: v for k, v in current.items() if "expense" in k or k in ("cogs", "ga_expenses")},
                    previous_expenses={k: v for k, v in previous.items() if "expense" in k or k in ("cogs", "ga_expenses")},
                )
                result.expense_spikes = len(spikes)
                spike_details = spikes
            else:
                result.expense_spikes = 0

            result.monitoring_summary = {
                "alerts": {
                    "active": result.active_alerts,
                    "critical": result.critical_alerts,
                    "details": [a.to_dict() for a in alerts],
                },
                "system_health": result.system_health,
                "kpi": {
                    "missed": result.kpi_missed,
                    "on_track": result.kpi_on_track,
                    "total": len(kpi_statuses),
                    "statuses": [s.to_dict() for s in kpi_statuses],
                },
                "cash_runway": {
                    "months": result.cash_runway_months,
                    "risk": result.cash_runway_risk,
                },
                "expense_spikes": result.expense_spikes,
                "expense_spike_details": spike_details,
            }

            result.stages_completed.append("monitoring")
            logger.info("Stage 5 (Monitoring): %d alerts, %d KPIs missed, runway=%s, %d spikes",
                        result.active_alerts, result.kpi_missed,
                        result.cash_runway_risk, result.expense_spikes)

        except Exception as e:
            logger.error("Stage 5 (Monitoring) failed: %s", e)
            result.stages_failed.append(f"monitoring: {str(e)[:100]}")

    # ── Stage 6: Learning ───────────────────────────────────────────

    def _run_learning(self, result: OrchestratorResult):
        """Capture learning state and track predictions from this run."""
        try:
            from app.services.prediction_tracker import prediction_tracker
            from app.services.strategy_engine import strategic_engine

            # Auto-record predictions from the current run's top action and strategy
            from app.services.prediction_tracker import PredictionEntry as _PE

            if result.top_action:
                try:
                    conviction = 0.5
                    if isinstance(result.cfo_verdict, dict):
                        conviction = result.cfo_verdict.get("conviction_score", 0.5)
                    prediction_tracker.record_prediction(_PE(
                        prediction_type="action_impact",
                        metric=result.top_action.get("category", "unknown"),
                        predicted_value=result.top_action.get("expected_impact", 0),
                        confidence=conviction,
                        source_method="decision_engine",
                    ))
                except Exception:
                    pass  # Non-critical

            if result.monte_carlo_var_95 != 0:
                try:
                    prediction_tracker.record_prediction(_PE(
                        prediction_type="risk_assessment",
                        metric="value_at_risk_95",
                        predicted_value=result.monte_carlo_var_95,
                        confidence=0.95,
                        source_method="monte_carlo",
                    ))
                except Exception:
                    pass

            pred_report = prediction_tracker.generate_report()
            learning = strategic_engine.learner.generate_learning_summary()

            result.learning_summary = {
                "predictions": {
                    "total": pred_report.total_predictions,
                    "resolved": pred_report.total_resolved,
                    "accuracy_pct": pred_report.overall_accuracy_pct,
                    "by_method": pred_report.by_method if hasattr(pred_report, "by_method") else {},
                },
                "strategy_learner": learning,
                "company_memory": strategic_engine.memory.summary(),
                "run_number": self._run_count,
            }

            result.stages_completed.append("learning")
            logger.info("Stage 6 (Learning): %d predictions, %d resolved, %.1f%% accuracy",
                        pred_report.total_predictions, pred_report.total_resolved,
                        pred_report.overall_accuracy_pct)

        except Exception as e:
            logger.error("Stage 6 (Learning) failed: %s", e)
            result.stages_failed.append(f"learning: {str(e)[:100]}")

    # ── Stage 7: Analogy ──────────────────────────────────────────────

    def _run_analogy(self, result: OrchestratorResult, current: Dict,
                      industry_id: str):
        """Find analogous historical situations and their outcomes."""
        try:
            from app.services.analogy_base import analogy_base

            strategies = analogy_base.get_analogous_strategies(
                current, top_k=5, industry=industry_id,
            )

            result.analogy_matches = len(strategies.get("matches", []))
            result.dominant_historical_strategy = strategies.get("dominant_strategy", "") or ""
            result.analogy_confidence = strategies.get("confidence", 0.0)
            result.analogy_summary = strategies

            result.stages_completed.append("analogy")
            logger.info("Stage 7 (Analogy): %d matches, dominant=%s, confidence=%.2f",
                        result.analogy_matches,
                        result.dominant_historical_strategy,
                        result.analogy_confidence)

        except Exception as e:
            logger.error("Stage 7 (Analogy) failed: %s", e)
            result.stages_failed.append(f"analogy: {str(e)[:100]}")

    # ── Accessors ───────────────────────────────────────────────────

    def get_last_result(self) -> Optional[OrchestratorResult]:
        """Return the most recent orchestrator result."""
        return self._last_result

    def get_run_count(self) -> int:
        """Return total number of pipeline runs."""
        return self._run_count


# Module-level singleton
orchestrator = FinancialOrchestrator()
