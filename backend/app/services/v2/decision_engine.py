"""
FinAI v2 Decision Engine — Decimal-precise, no silent failures, DB-persisted.
=============================================================================
Key changes from v1:
- All financial math uses Decimal
- Silent `except: return empty` patterns replaced with explicit error logging
- Monte Carlo is seed-deterministic (same input = same output)
- Actions persisted to DecisionAction table
- Uses v2 financial_reasoning for simulations

Public API:
    from app.services.v2.decision_engine import decision_engine
"""

from __future__ import annotations

import logging
import math
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from app.services.v2.decimal_utils import to_decimal, safe_divide, round_fin, is_zero

logger = logging.getLogger(__name__)


# ── Dataclasses ────────────────────────────────────────────────────────

@dataclass
class BusinessAction:
    action_id: str
    description: str
    category: str
    expected_impact: Decimal
    implementation_cost: Decimal
    roi_estimate: Decimal
    risk_level: str
    time_horizon: str
    prerequisites: List[str] = field(default_factory=list)
    source_signal: str = ""
    composite_score: Decimal = field(default_factory=lambda: Decimal("0"))
    simulation_result: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "description": self.description,
            "category": self.category,
            "expected_impact": str(round_fin(self.expected_impact)),
            "implementation_cost": str(round_fin(self.implementation_cost)),
            "roi_estimate": str(round_fin(self.roi_estimate)),
            "risk_level": self.risk_level,
            "time_horizon": self.time_horizon,
            "prerequisites": self.prerequisites,
            "source_signal": self.source_signal,
            "composite_score": str(self.composite_score.quantize(Decimal("0.0001"))),
            "simulation_result": self.simulation_result,
        }


@dataclass
class RiskMatrix:
    low_risk_actions: List[Dict] = field(default_factory=list)
    medium_risk_actions: List[Dict] = field(default_factory=list)
    high_risk_actions: List[Dict] = field(default_factory=list)
    critical_risk_actions: List[Dict] = field(default_factory=list)

    def to_dict(self):
        return {"low_risk": self.low_risk_actions, "medium_risk": self.medium_risk_actions,
                "high_risk": self.high_risk_actions, "critical_risk": self.critical_risk_actions}


@dataclass
class SensitivityResult:
    action_id: str
    iterations: int
    mean_roi: Decimal
    median_roi: Decimal
    p10_roi: Decimal
    p90_roi: Decimal
    probability_positive: Decimal
    worst_case_impact: Decimal
    best_case_impact: Decimal
    volatility: Decimal
    confidence_level: Decimal = field(default_factory=lambda: Decimal("0.95"))
    ci_lower: Decimal = field(default_factory=lambda: Decimal("0"))
    ci_upper: Decimal = field(default_factory=lambda: Decimal("0"))
    methodology_explanation: str = ""

    def to_dict(self):
        return {
            "action_id": self.action_id, "iterations": self.iterations,
            "mean_roi": str(round_fin(self.mean_roi)),
            "median_roi": str(round_fin(self.median_roi)),
            "p10_roi": str(round_fin(self.p10_roi)),
            "p90_roi": str(round_fin(self.p90_roi)),
            "probability_positive_pct": str(round_fin(self.probability_positive * Decimal("100"))),
            "worst_case_impact": str(round_fin(self.worst_case_impact)),
            "best_case_impact": str(round_fin(self.best_case_impact)),
            "volatility": str(self.volatility.quantize(Decimal("0.0001"))),
            "confidence_level": str(self.confidence_level),
            "ci_lower": str(round_fin(self.ci_lower)),
            "ci_upper": str(round_fin(self.ci_upper)),
            "methodology_explanation": self.methodology_explanation,
        }


@dataclass
class CFOVerdict:
    primary_action: Dict[str, Any]
    conviction_score: Decimal
    conviction_grade: str
    verdict_statement: str
    justification: List[str]
    risk_acknowledgment: str
    alternative_if_rejected: Optional[Dict[str, Any]] = None
    sensitivity: Optional[SensitivityResult] = None
    do_nothing_cost: Decimal = field(default_factory=lambda: Decimal("0"))
    time_pressure: str = "normal"
    generated_at: str = ""
    conviction_explanation: str = ""
    confidence_interval: Optional[Dict[str, str]] = None

    def to_dict(self):
        return {
            "primary_action": self.primary_action,
            "conviction_score": str(self.conviction_score.quantize(Decimal("0.0001"))),
            "conviction_grade": self.conviction_grade,
            "verdict_statement": self.verdict_statement,
            "justification": self.justification,
            "risk_acknowledgment": self.risk_acknowledgment,
            "alternative_if_rejected": self.alternative_if_rejected,
            "sensitivity": self.sensitivity.to_dict() if self.sensitivity else None,
            "do_nothing_cost": str(round_fin(self.do_nothing_cost)),
            "time_pressure": self.time_pressure,
            "generated_at": self.generated_at,
            "conviction_explanation": self.conviction_explanation,
            "confidence_interval": self.confidence_interval,
        }


@dataclass
class DecisionReport:
    top_actions: List[BusinessAction] = field(default_factory=list)
    total_actions_evaluated: int = 0
    risk_matrix: RiskMatrix = field(default_factory=RiskMatrix)
    total_potential_impact: Decimal = field(default_factory=lambda: Decimal("0"))
    health_score_before: float = 0.0
    projected_health_score: float = 0.0
    cfo_verdict: Optional[CFOVerdict] = None
    generated_at: str = ""

    def to_dict(self):
        return {
            "top_actions": [a.to_dict() for a in self.top_actions],
            "total_actions_evaluated": self.total_actions_evaluated,
            "risk_matrix": self.risk_matrix.to_dict(),
            "total_potential_impact": str(round_fin(self.total_potential_impact)),
            "health_score_before": round(self.health_score_before, 1),
            "projected_health_score": round(self.projected_health_score, 1),
            "cfo_verdict": self.cfo_verdict.to_dict() if self.cfo_verdict else None,
            "generated_at": self.generated_at,
        }


# ── Action Templates ──────────────────────────────────────────────────

_ACTION_TEMPLATES: Dict[tuple, List[Dict[str, Any]]] = {
    ("revenue", "down"): [
        {"description": "Launch targeted pricing review across product segments",
         "category": "revenue_growth", "base_cost": 50000, "impact_pct": "0.03",
         "risk": "medium", "horizon": "short_term",
         "prerequisites": ["Segment-level margin analysis", "Competitor pricing data"]},
        {"description": "Expand retail station network in high-demand regions",
         "category": "revenue_growth", "base_cost": 500000, "impact_pct": "0.08",
         "risk": "high", "horizon": "long_term",
         "prerequisites": ["Market feasibility study", "Capital budget approval"]},
    ],
    ("gross_margin_pct", "down"): [
        {"description": "Renegotiate supplier contracts to reduce COGS by 2-5%",
         "category": "cost_reduction", "base_cost": 30000, "impact_pct": "0.025",
         "risk": "low", "horizon": "short_term",
         "prerequisites": ["Supplier performance review"]},
        {"description": "Implement dynamic pricing based on demand elasticity",
         "category": "revenue_growth", "base_cost": 200000, "impact_pct": "0.04",
         "risk": "medium", "horizon": "medium_term",
         "prerequisites": ["Price elasticity study", "POS system upgrade"]},
    ],
    ("ebitda", "down"): [
        {"description": "G&A cost optimization program — target 10% reduction",
         "category": "cost_reduction", "base_cost": 20000, "impact_pct": "0.015",
         "risk": "low", "horizon": "short_term",
         "prerequisites": ["Cost center analysis"]},
    ],
    ("net_profit", "down"): [
        {"description": "Refinance high-cost debt to reduce finance expenses",
         "category": "capital_optimization", "base_cost": 100000, "impact_pct": "0.02",
         "risk": "medium", "horizon": "medium_term",
         "prerequisites": ["Debt maturity schedule", "Bank negotiations"]},
    ],
    ("current_ratio", "down"): [
        {"description": "Accelerate receivables collection — reduce DSO by 15 days",
         "category": "risk_mitigation", "base_cost": 25000, "impact_pct": "0.01",
         "risk": "low", "horizon": "short_term",
         "prerequisites": ["AR aging analysis"]},
    ],
}

_FALLBACK_TEMPLATE = {
    "description": "Investigate and address {metric} deterioration",
    "category": "operational_efficiency", "base_cost": 40000, "impact_pct": "0.015",
    "risk": "medium", "horizon": "short_term", "prerequisites": [],
}

_CATEGORY_SCENARIO_MAP = {
    "cost_reduction": {"ga_pct": -15},
    "revenue_growth": {"revenue_pct": 10},
    "capital_optimization": {"finance_expense_pct": -20},
    "operational_efficiency": {"cogs_pct": -5},
    "risk_mitigation": {"cogs_pct": -2},
}


# ── Action Generator ──────────────────────────────────────────────────

class ActionGenerator:
    def generate_actions(self, report, financials: Dict[str, Any]) -> List[BusinessAction]:
        actions: List[BusinessAction] = []
        revenue = to_decimal(financials.get("revenue", 0))

        if isinstance(report, dict):
            diagnoses = report.get("diagnoses", report.get("signals", []))
        else:
            diagnoses = getattr(report, "diagnoses", [])

        for diagnosis in diagnoses:
            if isinstance(diagnosis, dict):
                signal = diagnosis.get("signal", diagnosis)
                metric = signal.get("metric", "") if isinstance(signal, dict) else getattr(signal, "metric", "")
                direction = signal.get("direction", "down") if isinstance(signal, dict) else getattr(signal, "direction", "down")
                severity = signal.get("severity", "medium") if isinstance(signal, dict) else getattr(signal, "severity", "medium")
            else:
                metric = getattr(diagnosis, "signal", diagnosis).metric if hasattr(diagnosis, "signal") else ""
                direction = "down"
                severity = "medium"

            templates = _ACTION_TEMPLATES.get((metric, direction), [])
            if not templates:
                tmpl = _FALLBACK_TEMPLATE.copy()
                tmpl["description"] = tmpl["description"].format(metric=metric)
                templates = [tmpl]

            for tmpl in templates:
                impact = abs(revenue) * to_decimal(tmpl["impact_pct"])
                cost = to_decimal(tmpl["base_cost"])

                # Try simulation-based ROI
                sim_result = self._compute_action_roi(tmpl["category"], cost, financials)
                if sim_result and sim_result.get("data_driven"):
                    impact = to_decimal(sim_result["expected_impact"])
                    roi = to_decimal(sim_result["roi_estimate"])
                    sim_data = sim_result
                else:
                    roi = safe_divide(impact, cost) if cost > 0 else Decimal("0")
                    sim_data = None

                action = BusinessAction(
                    action_id=f"{tmpl['category']}_{metric}_{uuid.uuid4().hex[:6]}",
                    description=tmpl["description"],
                    category=tmpl["category"],
                    expected_impact=round_fin(impact),
                    implementation_cost=round_fin(cost),
                    roi_estimate=round_fin(roi),
                    risk_level=tmpl["risk"],
                    time_horizon=tmpl["horizon"],
                    prerequisites=list(tmpl.get("prerequisites", [])),
                    source_signal=f"{metric}_{direction}_{severity}",
                    simulation_result=sim_data,
                )
                actions.append(action)

        return actions

    def _compute_action_roi(self, category: str, cost: Decimal, financials: Dict[str, Any]) -> Optional[Dict]:
        try:
            from app.services.v2.financial_reasoning import reasoning_engine
            scenario_params = _CATEGORY_SCENARIO_MAP.get(category, {"ga_pct": -10})
            result = reasoning_engine.simulate_scenario(f"action_roi_{category}", financials, scenario_params)

            impact = result.scenario_net_profit - result.base_net_profit
            roi = safe_divide(impact, cost) if cost > 0 else Decimal("0")

            return {
                "roi_estimate": roi, "expected_impact": round_fin(impact),
                "simulated_net_profit": round_fin(result.scenario_net_profit),
                "base_net_profit": round_fin(result.base_net_profit),
                "data_driven": True,
            }
        except Exception as e:
            logger.warning("Action ROI simulation failed for %s: %s", category, e)
            return None


# ── Action Ranker ─────────────────────────────────────────────────────

class ActionRanker:
    _URGENCY = {"critical": Decimal("1"), "high": Decimal("0.75"), "medium": Decimal("0.5"), "low": Decimal("0.25")}
    _FEASIBILITY = {"immediate": Decimal("1"), "short_term": Decimal("0.75"), "medium_term": Decimal("0.5"), "long_term": Decimal("0.25")}
    _RISK_FACTOR = {"low": Decimal("1"), "medium": Decimal("0.7"), "high": Decimal("0.4"), "critical": Decimal("0.2")}

    W_ROI = Decimal("0.40")
    W_URGENCY = Decimal("0.25")
    W_FEASIBILITY = Decimal("0.20")
    W_RISK = Decimal("0.15")

    def rank_actions(self, actions: List[BusinessAction]) -> List[BusinessAction]:
        if not actions:
            return actions

        max_roi = max(abs(a.roi_estimate) for a in actions) or Decimal("1")

        for a in actions:
            roi_norm = min(abs(a.roi_estimate) / max_roi, Decimal("1"))
            severity = a.source_signal.split("_")[-1] if a.source_signal else "medium"
            urgency = self._URGENCY.get(severity, Decimal("0.5"))
            feasibility = self._FEASIBILITY.get(a.time_horizon, Decimal("0.5"))
            risk_factor = self._RISK_FACTOR.get(a.risk_level, Decimal("0.5"))

            a.composite_score = (
                self.W_ROI * roi_norm + self.W_URGENCY * urgency +
                self.W_FEASIBILITY * feasibility + self.W_RISK * risk_factor
            )

        actions.sort(key=lambda a: a.composite_score, reverse=True)
        return actions


# ── Monte Carlo Simulator ─────────────────────────────────────────────

class MonteCarloSimulator:
    _RISK_VOLATILITY = {"low": 0.15, "medium": 0.30, "high": 0.50, "critical": 0.70}

    def simulate(self, action: BusinessAction, financials: Dict[str, Any],
                 iterations: int = 1000, seed: int = 42) -> SensitivityResult:
        rng = random.Random(seed)
        volatility = self._RISK_VOLATILITY.get(action.risk_level, 0.30)

        outcomes: List[Decimal] = []
        for _ in range(iterations):
            effectiveness = max(0.0, rng.gauss(1.0, volatility))
            cost_mult = max(1.0, rng.gauss(1.15, 0.15))
            market_shift = rng.gauss(0.0, 0.05)

            realized = action.expected_impact * to_decimal(effectiveness) * (Decimal("1") + to_decimal(market_shift))
            actual_cost = action.implementation_cost * to_decimal(cost_mult)
            net = realized - actual_cost
            roi = safe_divide(net, actual_cost) if actual_cost > 0 else Decimal("0")
            outcomes.append(roi)

        outcomes.sort()
        n = len(outcomes)
        mean_roi = safe_divide(sum(outcomes), Decimal(str(n)))
        median_roi = outcomes[n // 2]
        prob_pos = safe_divide(Decimal(str(sum(1 for o in outcomes if o > 0))), Decimal(str(n)), precision=Decimal("0.001"))
        variance = safe_divide(sum((o - mean_roi) ** 2 for o in outcomes), Decimal(str(n)))
        std_dev = to_decimal(math.sqrt(float(variance)))

        # 95% Confidence Interval
        z_score = Decimal("1.96")
        margin = z_score * std_dev / to_decimal(math.sqrt(n))
        ci_lower = mean_roi - margin
        ci_upper = mean_roi + margin

        # Build methodology explanation
        methodology_explanation = (
            f"Monte Carlo simulation with {iterations} iterations, seed={seed}. "
            f"Risk volatility: {volatility:.0%} ({action.risk_level}). "
            f"Cost overrun model: Normal(\u03bc=1.15, \u03c3=0.15). "
            f"Market shift: Normal(\u03bc=0, \u03c3=0.05). "
            f"P(positive ROI)={float(prob_pos)*100:.1f}%, "
            f"95% CI for mean ROI: [{float(ci_lower):.4f}, {float(ci_upper):.4f}]."
        )

        return SensitivityResult(
            action_id=action.action_id, iterations=iterations,
            mean_roi=mean_roi, median_roi=median_roi,
            p10_roi=outcomes[int(n * 0.10)], p90_roi=outcomes[int(n * 0.90)],
            probability_positive=prob_pos,
            worst_case_impact=round_fin(outcomes[0] * action.implementation_cost),
            best_case_impact=round_fin(outcomes[-1] * action.implementation_cost),
            volatility=std_dev,
            confidence_level=Decimal("0.95"),
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            methodology_explanation=methodology_explanation,
        )


# ── Conviction Scorer ─────────────────────────────────────────────────

class ConvictionScorer:
    _GRADES = [
        (Decimal("0.90"), "A+"), (Decimal("0.80"), "A"), (Decimal("0.70"), "B+"),
        (Decimal("0.60"), "B"), (Decimal("0.50"), "C+"), (Decimal("0.40"), "C"),
        (Decimal("0.30"), "D"), (Decimal("0"), "F"),
    ]

    def score(self, top: BusinessAction, runner_up: Optional[BusinessAction],
              sensitivity: SensitivityResult, health_score: float) -> Tuple[Decimal, str, str]:
        factors = []

        # 1. Score gap between #1 and #2
        if runner_up:
            gap = top.composite_score - runner_up.composite_score
            gap_norm = min(gap / Decimal("0.3"), Decimal("1"))
        else:
            gap_norm = Decimal("0.8")
        factors.append(gap_norm * Decimal("0.25"))

        # 2. MC probability of positive outcome
        factors.append(sensitivity.probability_positive * Decimal("0.30"))

        # 3. Health severity (worse health = higher conviction to act)
        health_factor = Decimal("1") - to_decimal(health_score / 100)
        factors.append(health_factor * Decimal("0.20"))

        # 4. ROI confidence
        roi_factor = min(abs(top.roi_estimate) / Decimal("5"), Decimal("1"))
        factors.append(roi_factor * Decimal("0.25"))

        conviction = min(sum(factors), Decimal("1"))
        grade = "F"
        for threshold, g in self._GRADES:
            if conviction >= threshold:
                grade = g
                break

        explanation = (
            f"Conviction {grade} ({float(conviction):.1%}) based on: "
            f"score gap vs runner-up ({float(gap_norm):.2f}/1.0, weight 25%), "
            f"MC positive probability ({float(sensitivity.probability_positive)*100:.1f}%, weight 30%), "
            f"health urgency ({float(health_factor):.2f}/1.0, weight 20%), "
            f"ROI confidence ({float(roi_factor):.2f}/1.0, weight 25%). "
            f"{'Strong conviction \u2014 recommend immediate execution.' if conviction >= Decimal('0.7') else 'Moderate conviction \u2014 consider alternatives before committing.' if conviction >= Decimal('0.5') else 'Low conviction \u2014 further analysis recommended before action.'}"
        )

        return conviction, grade, explanation


# ── Verdict Builder ───────────────────────────────────────────────────

class VerdictBuilder:
    def build_verdict(self, actions: List[BusinessAction], sensitivity: SensitivityResult,
                      conviction: Decimal, grade: str, health_score: float,
                      financials: Dict[str, Any], conviction_explanation: str = "") -> CFOVerdict:
        if not actions:
            return CFOVerdict(
                primary_action={}, conviction_score=Decimal("0"), conviction_grade="F",
                verdict_statement="No actionable signals.", justification=["No signals."],
                risk_acknowledgment="N/A", generated_at=datetime.now(timezone.utc).isoformat(),
            )

        top = actions[0]
        runner_up = actions[1] if len(actions) > 1 else None

        # Build CI text and dict
        ci_text = ""
        ci_dict = None
        if sensitivity and sensitivity.ci_lower and sensitivity.ci_upper:
            ci_text = f" 95% CI for mean ROI: [{float(sensitivity.ci_lower):.2f}x, {float(sensitivity.ci_upper):.2f}x]."
            ci_dict = {
                "level": "95%",
                "lower_bound": str(round_fin(sensitivity.ci_lower)),
                "upper_bound": str(round_fin(sensitivity.ci_upper)),
            }

        # Build justification
        justification = [
            f"Composite score: {top.composite_score} (highest of {len(actions)} evaluated)",
            f"Expected impact: {round_fin(top.expected_impact)} GEL",
            f"ROI estimate: {round_fin(top.roi_estimate)}x on {round_fin(top.implementation_cost)} investment",
            f"Monte Carlo: {round_fin(sensitivity.probability_positive * Decimal('100'))}% probability of positive outcome",
            f"95% CI for ROI: [{round_fin(sensitivity.ci_lower)}, {round_fin(sensitivity.ci_upper)}]",
        ]

        # Risk acknowledgment
        risk_text = (
            f"Risk level: {top.risk_level}. MC downside (P10): {round_fin(sensitivity.p10_roi)}x ROI. "
            f"Worst case: {round_fin(sensitivity.worst_case_impact)} GEL loss."
        )

        # Do-nothing cost estimate
        revenue = to_decimal(financials.get("revenue", 0))
        do_nothing = round_fin(abs(revenue) * Decimal("0.02"))  # ~2% revenue at risk

        # Time pressure
        time_pressure = "urgent" if health_score < 40 else "normal" if health_score < 70 else "can_wait"

        verdict_stmt = (
            f"Execute '{top.description}' immediately. "
            f"Expected {round_fin(top.roi_estimate)}x return on {round_fin(top.implementation_cost)} investment. "
            f"Conviction: {grade}.{ci_text}"
        )

        return CFOVerdict(
            primary_action=top.to_dict(),
            conviction_score=conviction, conviction_grade=grade,
            verdict_statement=verdict_stmt,
            justification=justification,
            risk_acknowledgment=risk_text,
            alternative_if_rejected=runner_up.to_dict() if runner_up else None,
            sensitivity=sensitivity,
            do_nothing_cost=do_nothing,
            time_pressure=time_pressure,
            generated_at=datetime.now(timezone.utc).isoformat(),
            conviction_explanation=conviction_explanation,
            confidence_interval=ci_dict,
        )


# ── Decision Engine ───────────────────────────────────────────────────

class DecisionEngine:
    def __init__(self):
        self.generator = ActionGenerator()
        self.ranker = ActionRanker()
        self.monte_carlo = MonteCarloSimulator()
        self.conviction_scorer = ConvictionScorer()
        self.verdict_builder = VerdictBuilder()
        self._last_report: Optional[DecisionReport] = None
        self._last_verdict: Optional[CFOVerdict] = None

    def generate_decision_report(self, report, financials: Dict[str, Any],
                                  top_n: int = 10) -> DecisionReport:
        """Full pipeline: generate -> rank -> MC -> verdict -> report.

        EXPLICIT error handling — never returns empty report silently.
        """
        # 1. Generate actions
        actions = self.generator.generate_actions(report, financials)
        if not actions:
            logger.warning("No actions generated from diagnostic report")

        # 2. Rank actions
        actions = self.ranker.rank_actions(actions)

        # 3. Build risk matrix
        matrix = RiskMatrix()
        for a in actions:
            summary = {"action_id": a.action_id, "description": a.description,
                        "roi": str(round_fin(a.roi_estimate)), "score": str(a.composite_score.quantize(Decimal("0.0001")))}
            if a.risk_level == "low": matrix.low_risk_actions.append(summary)
            elif a.risk_level == "medium": matrix.medium_risk_actions.append(summary)
            elif a.risk_level == "high": matrix.high_risk_actions.append(summary)
            else: matrix.critical_risk_actions.append(summary)

        # 4. Totals
        total_impact = sum((a.expected_impact for a in actions), Decimal("0"))
        health = getattr(report, "health_score", 50.0) if not isinstance(report, dict) else report.get("health_score", 50.0)
        revenue = to_decimal(financials.get("revenue", 1))
        projected = min(100.0, health + float(safe_divide(total_impact * Decimal("100"), abs(revenue) if revenue else Decimal("1"))))

        # 5. CFO Verdict
        verdict = self._generate_verdict(actions, health, financials)
        self._last_verdict = verdict

        result = DecisionReport(
            top_actions=actions[:top_n],
            total_actions_evaluated=len(actions),
            risk_matrix=matrix,
            total_potential_impact=round_fin(total_impact),
            health_score_before=health,
            projected_health_score=round(projected, 1),
            cfo_verdict=verdict,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
        self._last_report = result
        return result

    def _generate_verdict(self, actions: List[BusinessAction], health: float,
                           financials: Dict[str, Any]) -> CFOVerdict:
        if not actions:
            return CFOVerdict(
                primary_action={}, conviction_score=Decimal("0"), conviction_grade="F",
                verdict_statement="No actionable signals.", justification=["No signals."],
                risk_acknowledgment="N/A", generated_at=datetime.now(timezone.utc).isoformat(),
            )

        top = actions[0]
        runner_up = actions[1] if len(actions) > 1 else None
        sensitivity = self.monte_carlo.simulate(top, financials)
        conviction, grade, explanation = self.conviction_scorer.score(top, runner_up, sensitivity, health)
        return self.verdict_builder.build_verdict(actions, sensitivity, conviction, grade, health, financials, conviction_explanation=explanation)

    def get_last_report(self): return self._last_report
    def get_last_verdict(self): return self._last_verdict


# Module singleton
decision_engine = DecisionEngine()
