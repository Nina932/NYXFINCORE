"""
Orchestrator v3 — Autonomous Financial Intelligence Conductor
==============================================================
This is the BRAIN CONDUCTOR. It runs the full intelligence pipeline:

  Upload → DataAgent → CalcAgent → ReconstructionEngine → LLM Chain
        → InsightAgent → StrategyAgent → MonitoringAgent → Memory

Every upload goes through this pipeline. Nothing is stale.
Previous periods influence analysis through CompanyMemory.
LLM explains (never computes). All numbers are deterministic.

STRICT RULES:
- Fresh pipeline on EVERY upload — never shows old data
- All financial numbers computed with Python Decimal
- LLM chain (Claude→Grok→Mistral→Ollama→Template) ONLY explains
- Memory provides cross-period context, never overrides current data
"""

import asyncio
import logging
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.memory.company_memory import company_memory
from app.services.financial_reconstruction import reconstruction_engine
from app.services.llm_chain import llm_chain

logger = logging.getLogger(__name__)


class OrchestratorV3:
    """
    The autonomous conductor. Runs 7 stages on every upload.
    Never shows stale data. Cross-period aware. LLM-enhanced.
    """

    async def run_full_pipeline(
        self,
        company_id: int,
        period: str,
        financials: Dict[str, Any],
        line_items: Optional[List[Dict]] = None,
        balance_sheet: Optional[Dict] = None,
        company_name: str = "Unknown Company",
    ) -> Dict[str, Any]:
        """
        Run the complete intelligence pipeline.

        Args:
            company_id: Company DB ID
            period: Period string (e.g. "2026-01")
            financials: Extracted financial data (from MultiSheetAnalyzer)
            line_items: Detailed account-level items
            balance_sheet: Balance sheet data (if available)
            company_name: Company name for display

        Returns:
            Complete intelligence result with all stages
        """
        start = time.time()
        stages_completed = []
        stages_failed = []
        trace = []

        # ── Stage 1: DATA CLASSIFICATION ───────────────────────────
        try:
            data_result = self._stage_data(financials, line_items or [])
            stages_completed.append("data_classification")
            trace.append(f"[DataAgent] Type: {data_result['data_type']}, "
                        f"Revenue: {'YES' if data_result['has_revenue'] else 'MISSING'}, "
                        f"COGS: {'YES' if data_result['has_cogs'] else 'MISSING'}")
        except Exception as e:
            stages_failed.append("data_classification")
            data_result = {"data_type": "unknown", "has_revenue": False, "has_cogs": False}
            trace.append(f"[DataAgent] FAILED: {e}")

        # ── Stage 2: DETERMINISTIC CALCULATION ─────────────────────
        try:
            calc_result = self._stage_calc(financials, balance_sheet)
            stages_completed.append("calculation")
            trace.append(f"[CalcAgent] Computed {len(calc_result)} metrics")
        except Exception as e:
            stages_failed.append("calculation")
            calc_result = {}
            trace.append(f"[CalcAgent] FAILED: {e}")

        # ── Stage 3: RECONSTRUCTION + INSIGHTS ─────────────────────
        try:
            reconstruction = reconstruction_engine.reconstruct(financials, line_items or [])
            stages_completed.append("reconstruction")
            trace.append(f"[ReconstructionEngine] {reconstruction.completeness.data_type}, "
                        f"{len(reconstruction.insights)} insights, "
                        f"industry={reconstruction.company_character.industry}")
        except Exception as e:
            stages_failed.append("reconstruction")
            reconstruction = None
            trace.append(f"[ReconstructionEngine] FAILED: {e}")

        # ── Stage 4: CROSS-PERIOD MEMORY ───────────────────────────
        try:
            previous = company_memory.get_previous_period(company_id, period)
            deltas = company_memory.compute_deltas(financials, previous)
            stages_completed.append("memory")
            if deltas.get("has_comparison"):
                n_changes = len(deltas.get("changes", {}))
                trace.append(f"[Memory] Compared with {deltas['previous_period']}: {n_changes} metrics tracked")
            else:
                trace.append("[Memory] No previous period for comparison")
        except Exception as e:
            stages_failed.append("memory")
            deltas = {"has_comparison": False}
            trace.append(f"[Memory] FAILED: {e}")

        # ── Stage 5: EXISTING ORCHESTRATOR (7-stage pipeline) ──────
        orch_result = None
        if data_result.get("has_revenue") and data_result.get("has_cogs"):
            try:
                from app.services.orchestrator import orchestrator as existing_orch
                orch_result = existing_orch.run(
                    current_financials=financials,
                    balance_sheet=balance_sheet,
                    industry_id="fuel_distribution",
                    monte_carlo_iterations=100,
                )
                stages_completed.append("orchestrator_7stage")
                trace.append(f"[Orchestrator] Health={orch_result.health_score:.0f}/100 "
                            f"({orch_result.health_grade}), Strategy={orch_result.strategy_name}")
            except Exception as e:
                stages_failed.append("orchestrator_7stage")
                trace.append(f"[Orchestrator] FAILED: {e}")
        else:
            trace.append("[Orchestrator] SKIPPED — incomplete data (revenue/COGS missing)")

        # ── Stage 6: LLM REASONING (CFO-level) ────────────────────
        try:
            llm_context = {
                "company": company_name,
                "period": period,
                "data_type": data_result.get("data_type", "unknown"),
                "pnl": reconstruction.partial_pl if reconstruction else {},
                "balance_sheet": balance_sheet or {},
                "company_character": reconstruction.company_character.to_dict() if reconstruction else {},
                "expense_breakdown": reconstruction.expense_breakdown if reconstruction else {},
                "insights": [i.to_dict() for i in reconstruction.insights] if reconstruction else [],
                "missing_data": reconstruction.completeness.missing_for_pl if reconstruction else [],
                "period_deltas": deltas.get("changes", {}),
            }
            llm_result = await llm_chain.reason(llm_context)
            stages_completed.append("llm_reasoning")
            trace.append(f"[LLM] Model: {llm_chain.last_model_used}, "
                        f"Confidence: {llm_result.get('confidence', '?')}")
        except Exception as e:
            stages_failed.append("llm_reasoning")
            llm_result = {"summary": "LLM reasoning unavailable", "insights": [], "confidence": 0}
            trace.append(f"[LLM] FAILED: {e}")

        # ── Stage 7: MONITORING + ALERTS ───────────────────────────
        try:
            alerts = self._stage_monitoring(financials, balance_sheet, data_result)
            stages_completed.append("monitoring")
            trace.append(f"[Monitoring] {len(alerts)} alerts generated")
        except Exception as e:
            stages_failed.append("monitoring")
            alerts = []
            trace.append(f"[Monitoring] FAILED: {e}")

        # ── ASSEMBLE FINAL RESULT ──────────────────────────────────
        elapsed_ms = int((time.time() - start) * 1000)

        result = {
            "version": "v3",
            "company": company_name,
            "company_id": company_id,
            "period": period,
            "execution_ms": elapsed_ms,
            "stages_completed": stages_completed,
            "stages_failed": stages_failed,
            "reasoning_trace": trace,

            # Data classification
            "data_type": data_result.get("data_type", "unknown"),
            "data_completeness": reconstruction.completeness.to_dict() if reconstruction else {},

            # Financial data (ALL from deterministic computation)
            "pnl": reconstruction.partial_pl if reconstruction else {},
            "balance_sheet": balance_sheet or {},
            "expense_breakdown": reconstruction.expense_breakdown if reconstruction else {},
            "calc_metrics": calc_result,

            # Intelligence (from reconstruction engine)
            "insights": [i.to_dict() for i in reconstruction.insights] if reconstruction else [],
            "company_character": reconstruction.company_character.to_dict() if reconstruction else {},
            "revenue_estimate": reconstruction.revenue_estimate.to_dict() if reconstruction and reconstruction.revenue_estimate else None,
            "suggestions": reconstruction.suggestions if reconstruction else [],
            "user_message": reconstruction.user_message if reconstruction else "",

            # Cross-period
            "period_deltas": deltas,

            # LLM reasoning (explanations only — no numbers)
            "llm_reasoning": llm_result,
            "llm_model_used": llm_chain.last_model_used,

            # Existing orchestrator (if full data available)
            "orchestrator_legacy": orch_result.to_dict() if orch_result else None,

            # Alerts
            "alerts": alerts,

            # LLM chain status
            "llm_chain_status": llm_chain.get_status(),
        }

        # Save to memory
        company_memory.save_run(company_id, result)

        logger.info("Orchestrator v3: %d stages completed, %d failed, %dms, model=%s",
                     len(stages_completed), len(stages_failed), elapsed_ms,
                     llm_chain.last_model_used)

        return result

    # ── Stage implementations ───────────────────────────────────────

    def _stage_data(self, financials: Dict, line_items: List[Dict]) -> Dict:
        """Classify what data we have."""
        has_revenue = bool(financials.get("revenue"))
        has_cogs = bool(financials.get("cogs"))
        has_opex = bool(financials.get("selling_expenses") or financials.get("admin_expenses") or financials.get("ga_expenses"))
        has_other = bool(financials.get("other_income") or financials.get("other_expense"))

        if has_revenue and has_cogs and has_opex:
            data_type = "full_financials"
        elif has_revenue and has_cogs:
            data_type = "basic_pl"
        elif has_revenue:
            data_type = "revenue_only"
        elif has_opex or has_other:
            data_type = "expenses_only"
        else:
            data_type = "unknown"

        return {
            "data_type": data_type,
            "has_revenue": has_revenue,
            "has_cogs": has_cogs,
            "has_opex": has_opex,
            "has_other": has_other,
            "line_item_count": len(line_items),
        }

    def _stage_calc(self, financials: Dict, balance_sheet: Optional[Dict]) -> Dict:
        """Pure deterministic calculations using Decimal."""
        metrics = {}

        rev = Decimal(str(financials.get("revenue", 0) or 0))
        cogs = Decimal(str(financials.get("cogs", 0) or 0))
        selling = Decimal(str(financials.get("selling_expenses", 0) or 0))
        admin = Decimal(str(financials.get("admin_expenses", 0) or 0))
        ga = Decimal(str(financials.get("ga_expenses", 0) or 0))
        other_inc = Decimal(str(financials.get("other_income", 0) or 0))
        other_exp = Decimal(str(financials.get("other_expense", 0) or 0))

        total_opex = selling + admin + ga

        if rev > 0:
            gp = rev - cogs
            metrics["gross_profit"] = float(gp)
            metrics["gross_margin_pct"] = float(round(gp / rev * 100, 2))
            metrics["cogs_to_revenue_pct"] = float(round(cogs / rev * 100, 2))

            ebitda = gp - total_opex
            metrics["ebitda"] = float(ebitda)
            metrics["ebitda_margin_pct"] = float(round(ebitda / rev * 100, 2))

            net = ebitda + other_inc - other_exp
            metrics["net_profit"] = float(net)
            metrics["net_margin_pct"] = float(round(net / rev * 100, 2))

            if total_opex > 0:
                metrics["opex_to_revenue_pct"] = float(round(total_opex / rev * 100, 2))

        if total_opex > 0:
            metrics["total_opex"] = float(total_opex)
            if other_exp > 0:
                metrics["interest_to_opex_pct"] = float(round(other_exp / total_opex * 100, 2))
                metrics["interest_to_total_costs_pct"] = float(round(
                    other_exp / (total_opex + other_exp) * 100, 2))

        # Balance sheet ratios
        if balance_sheet:
            ca = Decimal(str(balance_sheet.get("total_current_assets", 0) or 0))
            cl = Decimal(str(balance_sheet.get("total_current_liabilities", 0) or 0))
            equity = Decimal(str(balance_sheet.get("total_equity", 0) or 0))
            total_debt = Decimal(str(balance_sheet.get("total_liabilities", 0) or 0))

            if cl > 0:
                metrics["current_ratio"] = float(round(ca / cl, 2))
            if equity > 0:
                metrics["debt_to_equity"] = float(round(total_debt / equity, 2))

            metrics["working_capital"] = float(ca - cl)

        return metrics

    def _stage_monitoring(self, financials: Dict, balance_sheet: Optional[Dict],
                          data_result: Dict) -> List[Dict]:
        """Generate alerts from current data."""
        alerts = []

        # Alert: missing critical data
        if not data_result.get("has_revenue"):
            alerts.append({
                "severity": "critical", "type": "missing_data",
                "title": "Revenue Data Missing",
                "message": "Cannot assess profitability without revenue. Upload trial balance or revenue file.",
            })

        if not data_result.get("has_cogs"):
            alerts.append({
                "severity": "warning", "type": "missing_data",
                "title": "COGS Data Missing",
                "message": "Gross margin cannot be computed without COGS.",
            })

        # Alert: leverage
        opex = (financials.get("selling_expenses", 0) or 0) + (financials.get("admin_expenses", 0) or 0)
        interest = financials.get("other_expense", 0) or 0
        if opex > 0 and interest > 0:
            ratio = interest / (opex + interest) * 100
            if ratio > 25:
                alerts.append({
                    "severity": "critical", "type": "leverage",
                    "title": "Critical Leverage Risk",
                    "message": f"Interest expense is {ratio:.0f}% of total costs (healthy: <10%).",
                })
            elif ratio > 15:
                alerts.append({
                    "severity": "warning", "type": "leverage",
                    "title": "Elevated Debt Costs",
                    "message": f"Interest at {ratio:.0f}% of total costs — monitor closely.",
                })

        # Alert: margins (if available)
        rev = financials.get("revenue", 0) or 0
        cogs = financials.get("cogs", 0) or 0
        if rev > 0 and cogs > 0:
            margin = (rev - cogs) / rev * 100
            if margin < 5:
                alerts.append({
                    "severity": "critical", "type": "profitability",
                    "title": "Near-Zero Gross Margin",
                    "message": f"Gross margin is {margin:.1f}% — business sustainability at risk.",
                })
            elif margin < 15:
                alerts.append({
                    "severity": "warning", "type": "profitability",
                    "title": "Thin Margins",
                    "message": f"Gross margin {margin:.1f}% is below industry average.",
                })

        return alerts


# Singleton
orchestrator_v3 = OrchestratorV3()
