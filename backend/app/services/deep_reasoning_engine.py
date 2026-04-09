"""
Deep Reasoning Engine — builds on existing CausalChain + DiagnosisEngine + DecisionEngine
to produce a unified, rich reasoning output suitable for the ReasoningPage.

This is NOT a replacement — it's an orchestration layer that:
1. Runs diagnosis → gets signals + causal chains
2. Decomposes variance into structured factors
3. Generates counterfactual scenarios ("what if X hadn't happened?")
4. Produces executive narrative connecting cause → effect → action
5. Ranks actions with full ROI/probability/effort metadata
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import traceback


@dataclass
class CausalInsight:
    variable: str
    effect_on: str
    estimated_effect: float       # fractional: 0.12 = 12%
    confidence: float             # 0-1
    evidence: List[str]
    counterfactual: Dict[str, float]  # {"net_profit_if_unchanged": X}
    severity: str = "medium"


@dataclass
class RecommendedAction:
    action: str
    target_variable: str
    expected_impact: float        # fractional
    roi_estimate: float
    effort: str                   # Low|Medium|High
    probability_success: float    # 0-1
    deadline_months: int
    risk_level: str               # Low|Medium|High
    dependencies: List[str]
    composite_score: float = 0.0


@dataclass
class DeepReasoningResult:
    company: str
    period: str
    health_score: float
    health_grade: str
    causal_insights: List[CausalInsight]
    recommended_actions: List[RecommendedAction]
    executive_narrative: str
    risk_summary: Dict[str, Any]
    counterfactual_scenarios: List[Dict[str, Any]]
    trace_id: str
    execution_time_ms: int = 0

    def to_dict(self) -> Dict:
        return {
            "company": self.company,
            "period": self.period,
            "health_score": self.health_score,
            "health_grade": self.health_grade,
            "causal_insights": [asdict(c) for c in self.causal_insights],
            "recommended_actions": [asdict(a) for a in self.recommended_actions],
            "executive_narrative": self.executive_narrative,
            "risk_summary": self.risk_summary,
            "counterfactual_scenarios": self.counterfactual_scenarios,
            "trace_id": self.trace_id,
            "execution_time_ms": self.execution_time_ms,
        }


class DeepReasoningEngine:
    """
    Integrates existing diagnosis + reasoning + decision engines
    into a single deep-analysis pipeline.
    """

    def __init__(self):
        # Lazy imports to avoid circular dependencies
        self._diagnosis_engine = None
        self._reasoning_engine = None
        self._decision_engine = None
        self._sensitivity_analyzer = None

    def _ensure_engines(self):
        if self._diagnosis_engine is None:
            from app.services.diagnosis_engine import diagnosis_engine
            from app.services.financial_reasoning import reasoning_engine
            from app.services.decision_engine import decision_engine
            from app.services.sensitivity_analyzer import sensitivity_analyzer
            self._diagnosis_engine = diagnosis_engine
            self._reasoning_engine = reasoning_engine
            self._decision_engine = decision_engine
            self._sensitivity_analyzer = sensitivity_analyzer

    def analyze(
        self,
        financials: Dict[str, float],
        balance_sheet: Optional[Dict[str, float]] = None,
        previous_financials: Optional[Dict[str, float]] = None,
        period: str = "",
        company: str = "",
        industry_id: str = "fuel_distribution",
    ) -> DeepReasoningResult:
        """
        Run full deep reasoning pipeline:
        1. Diagnosis (health score, signals, causal factors)
        2. Causal decomposition (why did each metric change?)
        3. Counterfactual scenarios (what if X hadn't happened?)
        4. Action generation + ranking
        5. Executive narrative synthesis
        """
        import time
        start = time.time()
        self._ensure_engines()

        trace_id = f"reason-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

        # ── Stage 1: Diagnosis ──
        try:
            diag = self._diagnosis_engine.run_full_diagnosis(
                current_financials=financials,
                previous_financials=previous_financials,
                balance_sheet=balance_sheet,
                industry_id=industry_id,
            )
        except Exception as e:
            traceback.print_exc()
            return self._error_result(company, period, trace_id, f"Diagnosis failed: {e}")

        # ── Stage 2: Build causal insights from diagnosis signals ──
        causal_insights = self._build_causal_insights(financials, balance_sheet, diag)

        # ── Stage 3: Counterfactual scenarios ──
        counterfactuals = self._build_counterfactuals(financials, causal_insights)

        # ── Stage 4: Decision generation ──
        try:
            dr = self._decision_engine.generate_decision_report(
                report=diag, financials=financials, top_n=8
            )
            actions = self._convert_actions(dr)
        except Exception:
            traceback.print_exc()
            actions = []

        # ── Stage 5: Sensitivity-based risk summary ──
        risk_summary = self._build_risk_summary(financials, balance_sheet, diag)

        # ── Stage 6: Executive narrative ──
        narrative = self._synthesize_narrative(
            financials, diag, causal_insights, actions, risk_summary, company, period
        )

        elapsed = int((time.time() - start) * 1000)

        return DeepReasoningResult(
            company=company,
            period=period,
            health_score=diag.health_score,
            health_grade=diag.health_grade,
            causal_insights=causal_insights,
            recommended_actions=actions,
            executive_narrative=narrative,
            risk_summary=risk_summary,
            counterfactual_scenarios=counterfactuals,
            trace_id=trace_id,
            execution_time_ms=elapsed,
        )

    # ── Internal: Build causal insights from diagnosis ──

    def _build_causal_insights(self, financials, balance_sheet, diag) -> List[CausalInsight]:
        insights = []
        revenue = financials.get("revenue", 0)
        cogs = abs(financials.get("cogs", 0))
        gross_profit = financials.get("gross_profit", revenue - cogs)
        net_profit = financials.get("net_profit", 0)
        ebitda = financials.get("ebitda", 0)
        ga = abs(financials.get("ga_expenses", 0))

        # COGS → Gross Margin relationship
        if revenue > 0:
            cogs_ratio = cogs / revenue
            if cogs_ratio > 0.85:
                counterfactual_gp = revenue * 0.80 - (revenue - gross_profit)  # if COGS were 80%
                insights.append(CausalInsight(
                    variable="COGS ratio",
                    effect_on="Gross Margin",
                    estimated_effect=-(cogs_ratio - 0.80),
                    confidence=0.92,
                    evidence=[
                        f"COGS is {cogs_ratio*100:.1f}% of revenue (industry norm ~80%)",
                        f"Excess COGS costs ₾{(cogs - revenue*0.80):,.0f} vs benchmark",
                    ],
                    counterfactual={"gross_profit_if_cogs_80pct": round(revenue * 0.20, 0)},
                    severity="high" if cogs_ratio > 0.90 else "medium",
                ))

        # G&A → EBITDA relationship
        if revenue > 0 and ga > 0:
            ga_ratio = ga / revenue
            if ga_ratio > 0.05:
                insights.append(CausalInsight(
                    variable="G&A Expenses",
                    effect_on="EBITDA",
                    estimated_effect=-(ga_ratio - 0.03),
                    confidence=0.85,
                    evidence=[
                        f"G&A is {ga_ratio*100:.1f}% of revenue",
                        f"Reducing to 3% would save ₾{ga - revenue*0.03:,.0f}",
                    ],
                    counterfactual={"ebitda_if_ga_3pct": round(ebitda + (ga - revenue*0.03), 0)},
                    severity="medium",
                ))

        # Net profit margin analysis
        if revenue > 0:
            npm = net_profit / revenue
            if npm < 0:
                insights.append(CausalInsight(
                    variable="Operating losses",
                    effect_on="Net Profit",
                    estimated_effect=npm,
                    confidence=0.95,
                    evidence=[
                        f"Net margin is {npm*100:.1f}% — company is loss-making",
                        "Cash burn will erode equity if sustained",
                    ],
                    counterfactual={"net_profit_if_breakeven": 0},
                    severity="critical",
                ))
            elif npm < 0.05:
                insights.append(CausalInsight(
                    variable="Thin margins",
                    effect_on="Net Profit",
                    estimated_effect=npm - 0.10,
                    confidence=0.80,
                    evidence=[
                        f"Net margin is {npm*100:.1f}% — thin for the industry",
                        "Vulnerable to cost shocks or revenue dips",
                    ],
                    counterfactual={"net_profit_if_10pct_margin": round(revenue * 0.10, 0)},
                    severity="medium",
                ))

        # Leverage analysis from balance sheet
        if balance_sheet:
            total_debt = balance_sheet.get("total_liabilities", 0)
            equity = balance_sheet.get("total_equity", 0)
            if equity > 0 and total_debt > 0:
                de_ratio = total_debt / equity
                if de_ratio > 2.0:
                    insights.append(CausalInsight(
                        variable="Debt-to-Equity",
                        effect_on="Financial Risk",
                        estimated_effect=de_ratio / 4.0,  # normalize to 0-1ish
                        confidence=0.90,
                        evidence=[
                            f"D/E ratio is {de_ratio:.1f}x — elevated leverage",
                            f"Total debt ₾{total_debt:,.0f} vs equity ₾{equity:,.0f}",
                        ],
                        counterfactual={"equity_needed_for_1x_de": round(total_debt, 0)},
                        severity="high" if de_ratio > 3.0 else "medium",
                    ))

        # Add diagnosis signals as insights
        for diag_item in (diag.diagnoses or [])[:3]:
            sig = diag_item.signal
            if sig and hasattr(sig, 'metric') and sig.metric not in [i.variable for i in insights]:
                insights.append(CausalInsight(
                    variable=sig.metric,
                    effect_on="Financial Health",
                    estimated_effect=sig.change_pct / 100 if hasattr(sig, 'change_pct') and sig.change_pct else 0,
                    confidence=0.70,
                    evidence=[sig.explanation if hasattr(sig, 'explanation') else str(sig)],
                    counterfactual={},
                    severity=sig.severity if hasattr(sig, 'severity') else "medium",
                ))

        # Sort by absolute impact
        insights.sort(key=lambda x: abs(x.estimated_effect), reverse=True)
        return insights[:8]

    # ── Internal: Build counterfactual scenarios ──

    def _build_counterfactuals(self, financials, insights) -> List[Dict]:
        scenarios = []
        revenue = financials.get("revenue", 0)
        cogs = abs(financials.get("cogs", 0))
        net_profit = financials.get("net_profit", 0)

        if revenue > 0:
            # Scenario 1: Revenue +10%
            sc1_rev = revenue * 1.10
            sc1_gp = sc1_rev - cogs  # assume COGS stays fixed (operating leverage)
            scenarios.append({
                "name": "Revenue +10% (operating leverage)",
                "description": "If revenue increases 10% with fixed COGS, what happens to profit?",
                "base": {"revenue": revenue, "net_profit": net_profit},
                "scenario": {"revenue": sc1_rev, "net_profit": net_profit + (sc1_rev - revenue)},
                "delta_pct": ((sc1_rev - revenue) / abs(net_profit) * 100) if net_profit != 0 else 0,
            })

            # Scenario 2: COGS -5%
            sc2_cogs = cogs * 0.95
            sc2_savings = cogs - sc2_cogs
            scenarios.append({
                "name": "COGS reduction 5%",
                "description": "Supplier renegotiation reduces COGS by 5%",
                "base": {"cogs": cogs, "net_profit": net_profit},
                "scenario": {"cogs": sc2_cogs, "net_profit": net_profit + sc2_savings},
                "delta_pct": (sc2_savings / abs(net_profit) * 100) if net_profit != 0 else 0,
            })

            # Scenario 3: Revenue -15% stress test
            sc3_rev = revenue * 0.85
            sc3_loss = revenue - sc3_rev
            scenarios.append({
                "name": "Revenue drop -15% (stress)",
                "description": "Market downturn causes 15% revenue decline",
                "base": {"revenue": revenue, "net_profit": net_profit},
                "scenario": {"revenue": sc3_rev, "net_profit": net_profit - sc3_loss},
                "delta_pct": (-sc3_loss / abs(net_profit) * 100) if net_profit != 0 else 0,
            })

        return scenarios

    # ── Internal: Convert decision engine actions to our format ──

    def _convert_actions(self, decision_report) -> List[RecommendedAction]:
        actions = []
        top_actions = getattr(decision_report, 'top_actions', [])
        if not top_actions:
            d = decision_report.to_dict() if hasattr(decision_report, 'to_dict') else {}
            top_actions = d.get('top_actions', [])

        for act in top_actions:
            if isinstance(act, dict):
                desc = act.get("description", "")
                cat = act.get("category", "")
                roi = act.get("roi_estimate", 0)
                risk = act.get("risk_level", "Medium")
                score = act.get("composite_score", 0)
                impact = act.get("expected_impact", 0)
                cost = act.get("implementation_cost", 0)
            else:
                desc = getattr(act, 'description', '')
                cat = getattr(act, 'category', '')
                roi = getattr(act, 'roi_estimate', 0)
                risk = getattr(act, 'risk_level', 'Medium')
                score = getattr(act, 'composite_score', 0)
                impact = getattr(act, 'expected_impact', 0)
                cost = getattr(act, 'implementation_cost', 0)

            effort = "Low" if cost < 50000 else "High" if cost > 500000 else "Medium"
            horizon = "short_term" if score > 0.7 else "medium_term"

            actions.append(RecommendedAction(
                action=desc,
                target_variable=cat.replace("_", " ").title(),
                expected_impact=impact / 1000000 if impact > 1000 else impact,  # normalize
                roi_estimate=roi,
                effort=effort,
                probability_success=min(0.95, 0.5 + score * 0.4),
                deadline_months=3 if horizon == "short_term" else 6,
                risk_level=risk.title() if isinstance(risk, str) else "Medium",
                dependencies=[],
                composite_score=score,
            ))

        actions.sort(key=lambda a: a.composite_score, reverse=True)
        return actions[:8]

    # ── Internal: Risk summary ──

    def _build_risk_summary(self, financials, balance_sheet, diag) -> Dict:
        revenue = financials.get("revenue", 0)
        net_profit = financials.get("net_profit", 0)

        # Run quick sensitivity if possible
        try:
            sens = self._sensitivity_analyzer.analyze(financials)
            most_sensitive = sens.most_sensitive_variable
            max_swing = sens.bands[0].swing if sens.bands else 0
        except Exception:
            most_sensitive = "revenue"
            max_swing = abs(net_profit) * 0.5

        # Liquidity
        try:
            liq = self._reasoning_engine.build_liquidity_analysis(balance_sheet or {})
        except Exception:
            liq = {"health": "unknown", "ratios": {}, "flags": []}

        return {
            "overall_risk": "high" if diag.health_score < 50 else "medium" if diag.health_score < 75 else "low",
            "health_score": diag.health_score,
            "most_sensitive_variable": most_sensitive,
            "max_profit_swing": max_swing,
            "liquidity_health": liq.get("health", "unknown"),
            "liquidity_flags": liq.get("flags", []),
            "critical_signals": diag.signal_summary.get("critical", 0),
            "warning_signals": diag.signal_summary.get("high", 0) + diag.signal_summary.get("medium", 0),
            "accounting_issues": len(diag.accounting_issues) if diag.accounting_issues else 0,
        }

    # ── Internal: Executive narrative ──

    def _synthesize_narrative(self, financials, diag, insights, actions, risk, company, period) -> str:
        from app.services.company_ontology import get_accounting_rules
        rules = get_accounting_rules(company)

        revenue = financials.get("revenue", 0)
        net_profit = financials.get("net_profit", 0)
        gm_pct = financials.get("gross_margin_pct", 0)
        health = diag.health_score

        # Industry context
        industry = rules.get("industry", "general")
        gm_range = rules.get("gross_margin_range", "varies")

        # Opening
        if health >= 75:
            opening = f"{company or 'The company'} shows solid financial health (score: {health:.0f}/100) for {period or 'the current period'}."
        elif health >= 50:
            opening = f"{company or 'The company'} is in fair financial condition (score: {health:.0f}/100) for {period or 'the current period'}, with areas requiring attention."
        else:
            opening = f"{company or 'The company'} faces significant financial challenges (score: {health:.0f}/100) for {period or 'the current period'}. Immediate action is recommended."

        # Industry context line
        if industry != "general":
            opening += f" Industry: {industry.replace('_', ' ')} (typical gross margin: {gm_range})."

        # Key metrics
        metrics = f"Revenue stands at ₾{revenue/1e6:.1f}M with a gross margin of {gm_pct:.1f}%."
        if net_profit >= 0:
            metrics += f" Net profit is ₾{net_profit/1e6:.1f}M."
        else:
            metrics += f" The company is loss-making at ₾{net_profit/1e6:.1f}M net loss."

        # Causal story
        causal_parts = []
        for ins in insights[:3]:
            direction = "reduces" if ins.estimated_effect < 0 else "supports"
            causal_parts.append(
                f"• {ins.variable} {direction} {ins.effect_on} "
                f"(estimated impact: {abs(ins.estimated_effect)*100:.1f}%, confidence: {ins.confidence*100:.0f}%)"
            )
        causal_section = "Key causal drivers:\n" + "\n".join(causal_parts) if causal_parts else ""

        # Risk
        risk_text = f"Overall risk level: {risk.get('overall_risk', 'unknown').upper()}."
        if risk.get("critical_signals", 0) > 0:
            risk_text += f" {risk['critical_signals']} critical signal(s) detected."
        if risk.get("liquidity_flags"):
            risk_text += f" Liquidity concerns: {', '.join(risk['liquidity_flags'][:2])}."

        # Top action
        action_text = ""
        if actions:
            top = actions[0]
            action_text = (
                f"Priority recommendation: {top.action} "
                f"(estimated ROI: {top.roi_estimate:.1f}x, success probability: {top.probability_success*100:.0f}%, "
                f"effort: {top.effort})."
            )

        # Market context (best-effort, non-blocking)
        market_text = ""
        try:
            from app.services.market_data_service import _get_cached
            nbg = _get_cached("nbg_rates")
            oil = _get_cached("oil_prices")
            if nbg and nbg.get("rates"):
                usd_rate = nbg["rates"].get("USD", {}).get("rate", "?")
                market_text = f"Market context: GEL/USD {usd_rate}"
            if oil and oil.get("brent_crude_usd"):
                market_text += f", Brent crude ${oil['brent_crude_usd']}/bbl"
                if industry == "fuel_distribution":
                    market_text += " (directly impacts COGS for fuel distributors)"
            if market_text:
                market_text += "."
        except Exception:
            pass  # Market data is supplementary, never block analysis

        return "\n\n".join(filter(None, [opening, metrics, market_text, causal_section, risk_text, action_text]))

    # ── Error fallback ──

    def _error_result(self, company, period, trace_id, error_msg) -> DeepReasoningResult:
        return DeepReasoningResult(
            company=company, period=period,
            health_score=0, health_grade="F",
            causal_insights=[], recommended_actions=[],
            executive_narrative=f"Analysis failed: {error_msg}",
            risk_summary={"overall_risk": "unknown", "error": error_msg},
            counterfactual_scenarios=[], trace_id=trace_id,
        )


# Singleton
deep_reasoning_engine = DeepReasoningEngine()
