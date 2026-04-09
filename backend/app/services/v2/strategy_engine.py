"""
FinAI v2 Strategy Engine — Decimal-precise, deterministic strategies.
=====================================================================
Key changes from v1:
- All financial projections use Decimal
- _fmt_currency uses Decimal division (no float precision loss)
- TimeSimulator monthly projections are Decimal
- StrategyLearner/CompanyMemory use structured in-memory state (DB in Phase 12)
- Deterministic: same inputs always produce same strategy

Public API:
    from app.services.v2.strategy_engine import strategic_engine
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.services.v2.decimal_utils import to_decimal, safe_divide, round_fin, apply_pct, is_zero

logger = logging.getLogger(__name__)


def _fmt_currency(v: Any) -> str:
    d = to_decimal(v)
    if abs(d) >= 1_000_000:
        return f"₾{safe_divide(d, Decimal('1000000'), precision=Decimal('0.1'))}M"
    if abs(d) >= 1_000:
        return f"₾{safe_divide(d, Decimal('1000'), precision=Decimal('0.0'))}K"
    return f"₾{round_fin(d)}"


# ── Dataclasses ────────────────────────────────────────────────────────

@dataclass
class StrategyPhase:
    phase_name: str
    phase_number: int
    description: str
    actions: List[Dict[str, Any]]
    duration_days: int
    expected_revenue_delta: Decimal
    expected_cost_delta: Decimal
    expected_profit_delta: Decimal
    cumulative_investment: Decimal
    success_criteria: List[str]

    def to_dict(self):
        return {
            "phase_name": self.phase_name, "phase_number": self.phase_number,
            "description": self.description, "actions": self.actions,
            "duration_days": self.duration_days,
            "expected_revenue_delta": str(round_fin(self.expected_revenue_delta)),
            "expected_cost_delta": str(round_fin(self.expected_cost_delta)),
            "expected_profit_delta": str(round_fin(self.expected_profit_delta)),
            "cumulative_investment": str(round_fin(self.cumulative_investment)),
            "success_criteria": self.success_criteria,
        }


@dataclass
class Strategy:
    strategy_id: str
    name: str
    phases: List[StrategyPhase]
    total_duration_days: int
    total_investment: Decimal
    total_expected_profit_delta: Decimal
    overall_roi: Decimal
    risk_level: str
    time_projection: List[Dict[str, Any]] = field(default_factory=list)
    generated_at: str = ""

    def to_dict(self):
        return {
            "strategy_id": self.strategy_id, "name": self.name,
            "phases": [p.to_dict() for p in self.phases],
            "total_duration_days": self.total_duration_days,
            "total_investment": str(round_fin(self.total_investment)),
            "total_expected_profit_delta": str(round_fin(self.total_expected_profit_delta)),
            "overall_roi": str(round_fin(self.overall_roi)),
            "risk_level": self.risk_level,
            "time_projection": self.time_projection,
            "generated_at": self.generated_at,
        }


@dataclass
class MonthlyProjection:
    month: int
    revenue: Decimal
    cogs: Decimal
    gross_profit: Decimal
    ga_expenses: Decimal
    ebitda: Decimal
    net_profit: Decimal
    cumulative_cash_flow: Decimal

    def to_dict(self):
        return {k: str(round_fin(v)) if isinstance(v, Decimal) else v
                for k, v in self.__dict__.items()}


# ── Phase Templates ───────────────────────────────────────────────────

_PHASE_TEMPLATES = {
    "critical": {
        "phases": [
            {"name": "stabilization", "duration": 30, "focus": "cost_reduction",
             "description": "Stop the bleeding: freeze discretionary spend, renegotiate urgent contracts",
             "impact_multiplier": "0.3", "criteria": ["Achieve positive EBITDA", "Reduce burn rate 20%"]},
            {"name": "optimization", "duration": 60, "focus": "operational_efficiency",
             "description": "Restructure operations: automate, consolidate, optimize working capital",
             "impact_multiplier": "0.5", "criteria": ["Net margin > 0%", "Current ratio > 1.0"]},
            {"name": "growth", "duration": 90, "focus": "revenue_growth",
             "description": "Rebuild revenue: pricing optimization, channel expansion",
             "impact_multiplier": "0.2", "criteria": ["Revenue growth > 5%", "Gross margin > median"]},
        ],
    },
    "distressed": {
        "phases": [
            {"name": "stabilization", "duration": 45, "focus": "risk_mitigation",
             "description": "Reduce exposure: hedge, tighten credit, build cash reserves",
             "impact_multiplier": "0.25", "criteria": ["Cash runway > 6 months", "D/E < 3.0"]},
            {"name": "optimization", "duration": 60, "focus": "cost_reduction",
             "description": "Lean operations: zero-based budgeting, supplier consolidation",
             "impact_multiplier": "0.45", "criteria": ["COGS/Revenue < 85%", "G&A reduced 10%"]},
            {"name": "growth", "duration": 90, "focus": "revenue_growth",
             "description": "Controlled expansion: high-margin products",
             "impact_multiplier": "0.3", "criteria": ["Revenue growth > 8%", "EBITDA margin > 5%"]},
        ],
    },
    "recovering": {
        "phases": [
            {"name": "optimization", "duration": 60, "focus": "operational_efficiency",
             "description": "Process excellence: automation, analytics, SKU rationalization",
             "impact_multiplier": "0.4", "criteria": ["Operating efficiency > 90%"]},
            {"name": "growth", "duration": 90, "focus": "revenue_growth",
             "description": "Scale: new channels, product expansion, market share capture",
             "impact_multiplier": "0.6", "criteria": ["Revenue growth > 10%", "Market share +2pp"]},
        ],
    },
    "healthy": {
        "phases": [
            {"name": "growth", "duration": 90, "focus": "revenue_growth",
             "description": "Aggressive growth: new markets, M&A, innovation",
             "impact_multiplier": "0.7", "criteria": ["Revenue growth > 15%", "ROE > 20%"]},
            {"name": "optimization", "duration": 60, "focus": "capital_optimization",
             "description": "Capital efficiency: dividend policy, strategic reserves",
             "impact_multiplier": "0.3", "criteria": ["ROIC > WACC + 3%"]},
        ],
    },
}


# ── Strategy Builder ──────────────────────────────────────────────────

class StrategyBuilder:
    def build_strategy(self, actions: List[Any], health_score: float,
                       financials: Dict[str, Any]) -> Strategy:
        # Select phase template based on health
        if health_score < 30:
            template_key = "critical"
        elif health_score < 50:
            template_key = "distressed"
        elif health_score < 70:
            template_key = "recovering"
        else:
            template_key = "healthy"

        template = _PHASE_TEMPLATES[template_key]
        total_impact = sum((to_decimal(getattr(a, "expected_impact", 0)) for a in actions), Decimal("0"))
        total_cost = sum((to_decimal(getattr(a, "implementation_cost", 0)) for a in actions), Decimal("0"))

        phases = []
        cumulative_investment = Decimal("0")
        total_profit_delta = Decimal("0")
        total_duration = 0

        for i, phase_tmpl in enumerate(template["phases"]):
            multiplier = to_decimal(phase_tmpl["impact_multiplier"])
            phase_impact = total_impact * multiplier
            phase_cost = total_cost * multiplier
            cumulative_investment += phase_cost

            # Match actions to phase focus
            phase_actions = []
            for a in actions:
                cat = getattr(a, "category", "") if not isinstance(a, dict) else a.get("category", "")
                if cat == phase_tmpl["focus"] or not phase_actions:
                    phase_actions.append(
                        a.to_dict() if hasattr(a, "to_dict") else
                        {"description": str(a), "category": cat}
                    )

            phase = StrategyPhase(
                phase_name=phase_tmpl["name"],
                phase_number=i + 1,
                description=phase_tmpl["description"],
                actions=phase_actions[:3],
                duration_days=phase_tmpl["duration"],
                expected_revenue_delta=round_fin(phase_impact * Decimal("0.6")),
                expected_cost_delta=round_fin(phase_impact * Decimal("0.4")),
                expected_profit_delta=round_fin(phase_impact),
                cumulative_investment=round_fin(cumulative_investment),
                success_criteria=phase_tmpl["criteria"],
            )
            phases.append(phase)
            total_profit_delta += phase_impact
            total_duration += phase_tmpl["duration"]

        overall_roi = safe_divide(total_profit_delta, cumulative_investment) if cumulative_investment > 0 else Decimal("0")

        risk_levels = [getattr(a, "risk_level", "medium") for a in actions]
        worst_risk = "low"
        for r in ["critical", "high", "medium"]:
            if r in risk_levels:
                worst_risk = r
                break

        return Strategy(
            strategy_id=uuid.uuid4().hex[:8],
            name=f"{template_key.title()} Recovery Strategy" if health_score < 70 else "Growth Strategy",
            phases=phases,
            total_duration_days=total_duration,
            total_investment=round_fin(cumulative_investment),
            total_expected_profit_delta=round_fin(total_profit_delta),
            overall_roi=round_fin(overall_roi),
            risk_level=worst_risk,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )


# ── Time Simulator ────────────────────────────────────────────────────

class TimeSimulator:
    def project(self, financials: Dict[str, Any], strategy: Strategy,
                months: int = 12) -> List[MonthlyProjection]:
        rev = to_decimal(financials.get("revenue", 0))
        cogs = to_decimal(financials.get("cogs", 0))
        ga = to_decimal(financials.get("ga_expenses", 0))

        # Monthly base (annual / 12)
        m_rev = safe_divide(rev, Decimal("12"))
        m_cogs = safe_divide(cogs, Decimal("12"))
        m_ga = safe_divide(ga, Decimal("12"))

        # Monthly improvement rate from strategy
        monthly_rev_pct = Decimal("0")
        monthly_cost_pct = Decimal("0")
        if strategy.total_duration_days > 0 and not is_zero(rev):
            total_months = max(strategy.total_duration_days / 30, 1)
            monthly_rev_pct = safe_divide(
                strategy.total_expected_profit_delta * Decimal("0.6") * Decimal("100"),
                rev * to_decimal(total_months),
                precision=Decimal("0.001"),
            )
            monthly_cost_pct = safe_divide(
                strategy.total_expected_profit_delta * Decimal("0.4") * Decimal("100"),
                (cogs + ga) * to_decimal(total_months),
                precision=Decimal("0.001"),
            )

        projections = []
        cumulative_cf = Decimal("0")

        for month in range(1, months + 1):
            # Compound monthly improvements
            m_rev = apply_pct(m_rev, monthly_rev_pct)
            m_cogs = apply_pct(m_cogs, -monthly_cost_pct)
            m_ga = apply_pct(m_ga, -monthly_cost_pct * Decimal("0.5"))

            gp = m_rev - m_cogs
            ebitda = gp - m_ga
            np = ebitda * Decimal("0.85")  # After-tax proxy
            cumulative_cf += np

            projections.append(MonthlyProjection(
                month=month, revenue=round_fin(m_rev), cogs=round_fin(m_cogs),
                gross_profit=round_fin(gp), ga_expenses=round_fin(m_ga),
                ebitda=round_fin(ebitda), net_profit=round_fin(np),
                cumulative_cash_flow=round_fin(cumulative_cf),
            ))

        return projections


# ── Strategy Learner (in-memory for now, DB in Phase 12) ──────────────

class StrategyLearner:
    def __init__(self):
        self._recommendations: Dict[str, Dict] = {}
        self._executions: Dict[str, Dict] = {}
        self._outcomes: Dict[str, Dict] = {}

    def track_recommendation(self, action_id: str, desc: str, category: str, impact: Any):
        self._recommendations[action_id] = {
            "description": desc, "category": category,
            "predicted_impact": float(to_decimal(impact)),
            "recommended_at": datetime.now(timezone.utc).isoformat(),
        }

    def record_execution(self, action_id: str):
        if action_id in self._recommendations:
            self._executions[action_id] = {
                "executed_at": datetime.now(timezone.utc).isoformat(),
            }

    def record_outcome(self, action_id: str, actual_impact: Any):
        rec = self._recommendations.get(action_id)
        if not rec:
            return
        predicted = to_decimal(rec["predicted_impact"])
        actual = to_decimal(actual_impact)
        error = safe_divide(abs(predicted - actual) * Decimal("100"), abs(actual)) if not is_zero(actual) else Decimal("0")
        self._outcomes[action_id] = {
            "actual_impact": float(actual), "error_pct": float(error),
            "success": actual > 0, "resolved_at": datetime.now(timezone.utc).isoformat(),
        }

    def generate_learning_summary(self) -> Dict[str, Any]:
        total = len(self._recommendations)
        executed = len(self._executions)
        resolved = len(self._outcomes)
        successes = sum(1 for o in self._outcomes.values() if o.get("success"))
        return {
            "total_recommendations": total, "executed": executed,
            "resolved": resolved, "success_rate": round(successes / max(resolved, 1) * 100, 1),
        }


# ── Company Memory (in-memory for now) ────────────────────────────────

class CompanyMemory:
    def __init__(self):
        self._patterns: List[Dict] = []
        self._strategies: List[Dict] = []

    def add_pattern(self, pattern_type: str, metric: str, desc: str, magnitude: float):
        self._patterns.append({
            "pattern_type": pattern_type, "metric": metric,
            "description": desc, "magnitude": magnitude,
            "detected_at": datetime.now(timezone.utc).isoformat(),
        })

    def summary(self) -> Dict[str, Any]:
        return {
            "patterns_detected": len(self._patterns),
            "strategies_generated": len(self._strategies),
            "recent_patterns": self._patterns[-5:],
        }


# ── Strategic Engine ──────────────────────────────────────────────────

class StrategicEngine:
    def __init__(self):
        self.builder = StrategyBuilder()
        self.time_simulator = TimeSimulator()
        self.learner = StrategyLearner()
        self.memory = CompanyMemory()
        self._last_strategy: Optional[Strategy] = None

    def generate_strategy(self, actions: List[Any], health_score: float,
                           financials: Dict[str, Any], project_months: int = 12) -> Dict[str, Any]:
        strategy = self.builder.build_strategy(actions, health_score, financials)
        projection = self.time_simulator.project(financials, strategy, project_months)
        strategy.time_projection = [p.to_dict() for p in projection]

        for action in actions[:5]:
            if hasattr(action, "action_id"):
                self.learner.track_recommendation(
                    action.action_id, getattr(action, "description", ""),
                    getattr(action, "category", ""), getattr(action, "expected_impact", 0),
                )

        self._last_strategy = strategy
        return {
            "strategy": strategy.to_dict(),
            "time_projection": [p.to_dict() for p in projection],
            "learning_summary": self.learner.generate_learning_summary(),
            "company_memory": self.memory.summary(),
        }

    def get_last_strategy(self): return self._last_strategy


# Module singleton
strategic_engine = StrategicEngine()
