"""
Phase J: Strategic Intelligence Engine
========================================
Transforms single actions into multi-phase strategies, simulates financial
evolution over time, and closes the decision loop.

Components:
    StrategyBuilder     — Converts actions into phased strategies (stabilize → optimize → grow)
    TimeSimulator       — Monthly P&L projection with compounding effects
    StrategyLearner     — Tracks action→outcome, feeds back to Decision Engine
    CompanyMemory       — Persistent financial pattern + strategy history

Rules:
    - ALL calculations are deterministic
    - No LLM-generated numbers
    - Strategies are rule-based, grounded in financial logic

Reuses:
    - decision_engine.BusinessAction (input)
    - financial_reasoning.reasoning_engine.simulate_scenario()
"""

import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _fmt_currency(v: float) -> str:
    """Format a number as GEL currency string."""
    if abs(v) >= 1_000_000:
        return f"₾{v / 1_000_000:,.1f}M"
    if abs(v) >= 1_000:
        return f"₾{v / 1_000:,.0f}K"
    return f"₾{v:,.0f}"


# ═══════════════════════════════════════════════════════════════════
# DATACLASSES
# ═══════════════════════════════════════════════════════════════════

@dataclass
class StrategyPhase:
    """A single phase in a multi-step strategy."""
    phase_name: str            # stabilization|optimization|growth
    phase_number: int
    description: str
    actions: List[Dict[str, Any]]
    duration_days: int
    expected_revenue_delta: float
    expected_cost_delta: float
    expected_profit_delta: float
    cumulative_investment: float
    success_criteria: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase_name": self.phase_name,
            "phase_number": self.phase_number,
            "description": self.description,
            "actions": self.actions,
            "duration_days": self.duration_days,
            "expected_revenue_delta": round(self.expected_revenue_delta, 2),
            "expected_cost_delta": round(self.expected_cost_delta, 2),
            "expected_profit_delta": round(self.expected_profit_delta, 2),
            "cumulative_investment": round(self.cumulative_investment, 2),
            "success_criteria": self.success_criteria,
        }


@dataclass
class Strategy:
    """A multi-phase strategy with timeline and projections."""
    strategy_id: str
    name: str
    phases: List[StrategyPhase]
    total_duration_days: int
    total_investment: float
    total_expected_profit_delta: float
    overall_roi: float
    risk_level: str
    time_projection: List[Dict[str, Any]] = field(default_factory=list)
    generated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "name": self.name,
            "phases": [p.to_dict() for p in self.phases],
            "total_duration_days": self.total_duration_days,
            "total_investment": round(self.total_investment, 2),
            "total_expected_profit_delta": round(self.total_expected_profit_delta, 2),
            "overall_roi": round(self.overall_roi, 2),
            "risk_level": self.risk_level,
            "time_projection": self.time_projection,
            "generated_at": self.generated_at,
        }


@dataclass
class MonthlyProjection:
    """One month in a time simulation."""
    month: int
    revenue: float
    cogs: float
    gross_profit: float
    ga_expenses: float
    ebitda: float
    net_profit: float
    cumulative_cash_flow: float

    def to_dict(self) -> Dict[str, Any]:
        return {k: round(v, 2) if isinstance(v, float) else v
                for k, v in self.__dict__.items()}


@dataclass
class ActionOutcome:
    """Tracked outcome of a recommended action."""
    action_id: str
    action_description: str
    category: str
    recommended_at: str
    executed: bool = False
    executed_at: str = ""
    predicted_impact: float = 0.0
    actual_impact: float = 0.0
    accuracy_pct: float = 0.0     # how close was prediction to actual
    success: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_description": self.action_description,
            "category": self.category,
            "recommended_at": self.recommended_at,
            "executed": self.executed,
            "executed_at": self.executed_at,
            "predicted_impact": round(self.predicted_impact, 2),
            "actual_impact": round(self.actual_impact, 2),
            "accuracy_pct": round(self.accuracy_pct, 2),
            "success": self.success,
        }


@dataclass
class CompanyPattern:
    """A learned financial pattern from company history."""
    pattern_id: str
    pattern_type: str       # seasonal|cyclical|structural|one_time
    metric: str
    description: str
    avg_magnitude: float
    occurrences: int
    last_seen: str

    def to_dict(self) -> Dict[str, Any]:
        return {k: round(v, 2) if isinstance(v, float) else v
                for k, v in self.__dict__.items()}


# ═══════════════════════════════════════════════════════════════════
# STRATEGY BUILDER — single actions → multi-phase strategies
# ═══════════════════════════════════════════════════════════════════

# Phase templates: maps health_score ranges to strategy structure
_PHASE_TEMPLATES = {
    "critical": {  # health < 30
        "phases": [
            {"name": "stabilization", "duration": 30, "focus": "cost_reduction",
             "description": "Stop the bleeding: freeze discretionary spend, renegotiate urgent contracts",
             "impact_multiplier": 0.3, "criteria": ["Achieve positive EBITDA", "Reduce burn rate 20%"]},
            {"name": "optimization", "duration": 60, "focus": "operational_efficiency",
             "description": "Restructure operations: automate, consolidate vendors, optimize working capital",
             "impact_multiplier": 0.5, "criteria": ["Net margin > 0%", "Current ratio > 1.0"]},
            {"name": "growth", "duration": 90, "focus": "revenue_growth",
             "description": "Rebuild revenue: pricing optimization, channel expansion",
             "impact_multiplier": 0.2, "criteria": ["Revenue growth > 5%", "Gross margin > industry median"]},
        ],
    },
    "distressed": {  # health 30-50
        "phases": [
            {"name": "stabilization", "duration": 45, "focus": "risk_mitigation",
             "description": "Reduce exposure: hedge costs, tighten credit, build cash reserves",
             "impact_multiplier": 0.25, "criteria": ["Cash runway > 6 months", "D/E < 3.0"]},
            {"name": "optimization", "duration": 60, "focus": "cost_reduction",
             "description": "Lean operations: zero-based budgeting, supplier consolidation",
             "impact_multiplier": 0.45, "criteria": ["COGS/Revenue < 85%", "G&A reduced 10%"]},
            {"name": "growth", "duration": 90, "focus": "revenue_growth",
             "description": "Controlled expansion: high-margin products, geographic focus",
             "impact_multiplier": 0.3, "criteria": ["Revenue growth > 8%", "EBITDA margin > 5%"]},
        ],
    },
    "recovering": {  # health 50-70
        "phases": [
            {"name": "optimization", "duration": 60, "focus": "operational_efficiency",
             "description": "Process excellence: automation, analytics, SKU rationalization",
             "impact_multiplier": 0.4, "criteria": ["Operating efficiency > 90%", "Inventory turns > 8x"]},
            {"name": "growth", "duration": 90, "focus": "revenue_growth",
             "description": "Scale: new channels, product expansion, market share capture",
             "impact_multiplier": 0.6, "criteria": ["Revenue growth > 10%", "Market share +2pp"]},
        ],
    },
    "healthy": {  # health > 70
        "phases": [
            {"name": "growth", "duration": 90, "focus": "revenue_growth",
             "description": "Aggressive growth: new markets, M&A pipeline, innovation investment",
             "impact_multiplier": 0.7, "criteria": ["Revenue growth > 15%", "ROE > 20%"]},
            {"name": "optimization", "duration": 60, "focus": "capital_optimization",
             "description": "Capital efficiency: dividend policy, buybacks, strategic reserves",
             "impact_multiplier": 0.3, "criteria": ["ROIC > WACC + 3%", "Cash conversion > 90%"]},
        ],
    },
}


class StrategyBuilder:
    """Converts ranked actions into phased strategies based on financial health and actual data."""

    def build_strategy(
        self,
        actions: List[Any],  # List[BusinessAction]
        health_score: float,
        financials: Dict[str, float],
    ) -> Strategy:
        """
        Build a multi-phase strategy from ranked actions.

        Enhanced: generates data-driven phases that reference specific financial line items
        before falling back to templates.
        """
        # Handle health_score passed as dict or number
        if isinstance(health_score, dict):
            health_score = health_score.get("health_score", health_score.get("score", 50))
        health_score = float(health_score) if health_score else 50.0

        revenue = abs(financials.get("revenue", 0)) or 1
        cogs = abs(financials.get("cogs", 0))
        selling = abs(financials.get("selling_expenses", 0))
        admin = abs(financials.get("ga_expenses", 0)) or abs(financials.get("admin_expenses", 0))
        net = financials.get("net_profit", 0)
        gp = financials.get("gross_profit", revenue - cogs)
        gm = (gp / revenue * 100) if revenue else 0
        total_opex = selling + admin

        # Try to build data-driven phases first
        data_driven_phases = self._generate_data_driven_phases(
            revenue, cogs, selling, admin, net, gp, gm, total_opex, financials
        )

        total_action_impact = sum(getattr(a, "expected_impact", 0) for a in actions)
        total_action_cost = sum(getattr(a, "implementation_cost", 0) for a in actions)

        if data_driven_phases:
            # Use data-driven phases, attach matching actions
            phases: List[StrategyPhase] = []
            cumulative_investment = 0.0

            for i, dd_phase in enumerate(data_driven_phases):
                # Find matching actions for this phase
                phase_actions = [
                    a.to_dict() if hasattr(a, "to_dict") else {"description": str(a)}
                    for a in actions
                    if getattr(a, "category", "") in dd_phase.get("categories", [])
                ]
                if not phase_actions and actions:
                    phase_actions = [
                        a.to_dict() if hasattr(a, "to_dict") else {"description": str(a)}
                        for a in actions[:2]
                    ]

                phase_cost = dd_phase.get("target_impact", 0) * 0.1  # 10% investment of target
                cumulative_investment += phase_cost

                phases.append(StrategyPhase(
                    phase_name=dd_phase["name"],
                    phase_number=i + 1,
                    description=" | ".join(dd_phase["actions"][:2]),
                    actions=phase_actions + [{"data_driven_detail": a} for a in dd_phase["actions"]],
                    duration_days=dd_phase["duration_days"],
                    expected_revenue_delta=round(dd_phase.get("target_impact", 0) * 0.6, 2),
                    expected_cost_delta=round(-dd_phase.get("target_impact", 0) * 0.4, 2),
                    expected_profit_delta=round(dd_phase.get("target_impact", 0), 2),
                    cumulative_investment=round(cumulative_investment, 2),
                    success_criteria=[dd_phase.get("kpi_target", "Improve financial position")],
                ))

            total_days = sum(p.duration_days for p in phases)
            total_profit = sum(p.expected_profit_delta for p in phases)
            total_invest = cumulative_investment
            roi = round(total_profit / max(total_invest, 1), 2)
            risk = "low" if health_score > 70 else "medium" if health_score > 50 else "high" if health_score > 30 else "critical"

            strategy = Strategy(
                strategy_id=f"strategy_{uuid.uuid4().hex[:8]}",
                name=self._generate_name(health_score, data_driven=True),
                phases=phases,
                total_duration_days=total_days,
                total_investment=total_invest,
                total_expected_profit_delta=total_profit,
                overall_roi=roi,
                risk_level=risk,
                generated_at=datetime.now(timezone.utc).isoformat(),
            )
            logger.info("Data-driven strategy built: %s (%d phases, %d days, ROI=%.1fx)",
                         strategy.name, len(phases), total_days, roi)
            return strategy

        # Fallback to template-based strategy
        return self._build_template_strategy(actions, health_score, financials,
                                              total_action_impact, total_action_cost, revenue)

    def _generate_data_driven_phases(
        self, revenue, cogs, selling, admin, net, gp, gm, total_opex, financials,
    ) -> List[Dict[str, Any]]:
        """
        Generate strategy phases from SPECIFIC financial line items.

        Each phase references actual numbers, not generic templates.
        """
        phases = []

        # Phase 1: Address profitability if loss-making
        if net < 0:
            loss_amount = abs(net)
            cogs_reduction_needed = (loss_amount / cogs * 100) if cogs else 0
            selling_fix = (loss_amount / selling * 100) if selling else 0

            phases.append({
                "name": f"Restore Profitability (close {_fmt_currency(loss_amount)} gap)",
                "duration_days": 90,
                "actions": [
                    f"Negotiate COGS reduction of {cogs_reduction_needed:.1f}% ({_fmt_currency(loss_amount)} saving needed)",
                    f"Current COGS is {_fmt_currency(cogs)} ({cogs/revenue*100:.1f}% of revenue) — target {(cogs-loss_amount)/revenue*100:.1f}%",
                    f"Alternative: reduce selling expenses by {selling_fix:.0f}% from {_fmt_currency(selling)}",
                ],
                "target_impact": loss_amount,
                "kpi_target": f"Net profit >= 0 (currently -{_fmt_currency(loss_amount)})",
                "categories": ["cost_reduction", "revenue_growth"],
                "computed_from": "actual_net_profit_loss",
            })

        # Phase 2: Improve gross margin if thin
        if gm < 15:
            target_gp = revenue * 0.15
            gap = target_gp - gp
            if gap > 0:
                phases.append({
                    "name": f"Improve Gross Margin from {gm:.1f}% to 15%",
                    "duration_days": 180,
                    "actions": [
                        f"Close {_fmt_currency(gap)} gross profit gap",
                        f"Options: raise prices by {gap/revenue*100:.1f}% OR reduce COGS by {_fmt_currency(gap)}",
                        f"Focus on highest-cost product categories first",
                    ],
                    "target_impact": gap,
                    "kpi_target": f"Gross margin >= 15% (currently {gm:.1f}%)",
                    "categories": ["cost_reduction", "revenue_growth", "operational_efficiency"],
                    "computed_from": "actual_gross_margin_gap",
                })

        # Phase 3: Optimize opex if too high
        if revenue > 0 and total_opex / revenue * 100 > 10:
            opex_target = revenue * 0.10
            saving = total_opex - opex_target
            if saving > 0:
                phases.append({
                    "name": f"Optimize OpEx from {total_opex/revenue*100:.1f}% to 10% of revenue",
                    "duration_days": 180,
                    "actions": [
                        f"Selling expenses: {_fmt_currency(selling)} ({selling/revenue*100:.1f}% of rev)",
                        f"Admin expenses: {_fmt_currency(admin)} ({admin/revenue*100:.1f}% of rev)",
                        f"Target saving: {_fmt_currency(saving)}",
                    ],
                    "target_impact": saving,
                    "kpi_target": f"OpEx <= 10% of revenue (currently {total_opex/revenue*100:.1f}%)",
                    "categories": ["cost_reduction", "operational_efficiency"],
                    "computed_from": "actual_opex_ratio",
                })

        # Phase 4: Growth phase if already profitable
        if net > 0 and gm >= 15:
            growth_target = revenue * 0.10
            phases.append({
                "name": f"Revenue Growth Target: +{_fmt_currency(growth_target)} (10%)",
                "duration_days": 180,
                "actions": [
                    f"Current revenue: {_fmt_currency(revenue)} with {gm:.1f}% gross margin",
                    f"Expand highest-margin channels",
                    f"Target: {_fmt_currency(revenue + growth_target)} annual revenue",
                ],
                "target_impact": growth_target * (gm / 100),  # profit from incremental revenue
                "kpi_target": f"Revenue >= {_fmt_currency(revenue + growth_target)}",
                "categories": ["revenue_growth", "capital_optimization"],
                "computed_from": "actual_growth_opportunity",
            })

        return phases

    def _build_template_strategy(
        self, actions, health_score, financials, total_action_impact, total_action_cost, revenue,
    ) -> Strategy:
        """Fallback: build strategy from generic templates when data-driven phases cannot be generated."""
        if health_score < 30:
            template = _PHASE_TEMPLATES["critical"]
        elif health_score < 50:
            template = _PHASE_TEMPLATES["distressed"]
        elif health_score < 70:
            template = _PHASE_TEMPLATES["recovering"]
        else:
            template = _PHASE_TEMPLATES["healthy"]

        phases: List[StrategyPhase] = []
        cumulative_investment = 0.0

        for i, phase_tmpl in enumerate(template["phases"]):
            focus = phase_tmpl["focus"]
            phase_actions = [
                a.to_dict() if hasattr(a, "to_dict") else {"description": str(a)}
                for a in actions
                if getattr(a, "category", "") == focus
            ]
            if not phase_actions and actions:
                phase_actions = [
                    a.to_dict() if hasattr(a, "to_dict") else {"description": str(a)}
                    for a in actions[:2]
                ]

            impact_share = phase_tmpl["impact_multiplier"]
            phase_profit = round(total_action_impact * impact_share, 2)
            phase_cost = round(total_action_cost * impact_share, 2)
            cumulative_investment += phase_cost

            revenue_delta = round(phase_profit * 0.6, 2)
            cost_delta = round(-phase_profit * 0.4, 2)

            phases.append(StrategyPhase(
                phase_name=phase_tmpl["name"],
                phase_number=i + 1,
                description=phase_tmpl["description"],
                actions=phase_actions,
                duration_days=phase_tmpl["duration"],
                expected_revenue_delta=revenue_delta,
                expected_cost_delta=cost_delta,
                expected_profit_delta=phase_profit,
                cumulative_investment=round(cumulative_investment, 2),
                success_criteria=phase_tmpl["criteria"],
            ))

        total_days = sum(p.duration_days for p in phases)
        total_profit = sum(p.expected_profit_delta for p in phases)
        total_invest = cumulative_investment
        roi = round(total_profit / max(total_invest, 1), 2)
        risk = "low" if health_score > 70 else "medium" if health_score > 50 else "high" if health_score > 30 else "critical"

        strategy = Strategy(
            strategy_id=f"strategy_{uuid.uuid4().hex[:8]}",
            name=self._generate_name(health_score),
            phases=phases,
            total_duration_days=total_days,
            total_investment=total_invest,
            total_expected_profit_delta=total_profit,
            overall_roi=roi,
            risk_level=risk,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
        logger.info("Template strategy built: %s (%d phases, %d days, ROI=%.1fx)",
                     strategy.name, len(phases), total_days, roi)
        return strategy

    def _generate_name(self, health: float, data_driven: bool = False) -> str:
        prefix = "Data-Driven " if data_driven else ""
        if health < 30:
            return f"{prefix}Emergency Turnaround Strategy"
        elif health < 50:
            return f"{prefix}Financial Recovery Strategy"
        elif health < 70:
            return f"{prefix}Performance Optimization Strategy"
        return f"{prefix}Growth Acceleration Strategy"


# ═══════════════════════════════════════════════════════════════════
# TIME SIMULATOR — monthly P&L projection with compounding
# ═══════════════════════════════════════════════════════════════════

class TimeSimulator:
    """
    Projects financial evolution over time (monthly) applying compounding
    effects of strategy actions.
    """

    def project(
        self,
        base_financials: Dict[str, float],
        strategy: Strategy,
        months: int = 12,
    ) -> List[MonthlyProjection]:
        """
        Project monthly financials applying strategy phases sequentially.

        Each phase's deltas are spread evenly across its duration (in months).
        Effects compound — phase 2 builds on phase 1 results.
        """
        revenue = base_financials.get("revenue", 0) / 12  # monthly
        cogs = base_financials.get("cogs", 0) / 12
        ga = base_financials.get("ga_expenses", 0) / 12
        dep = base_financials.get("depreciation", 0) / 12
        fin = base_financials.get("finance_expense", 0) / 12
        tax_rate = base_financials.get("tax_rate", 0.15)

        projections: List[MonthlyProjection] = []
        cumulative_cf = 0.0

        # Build phase schedule: which phase is active in which month
        phase_schedule = self._build_schedule(strategy.phases, months)

        for month in range(1, months + 1):
            active_phase = phase_schedule.get(month)

            if active_phase:
                # Apply monthly increment of phase deltas
                phase_months = max(active_phase.duration_days / 30, 1)
                monthly_rev_delta = active_phase.expected_revenue_delta / phase_months / 12
                monthly_cost_delta = active_phase.expected_cost_delta / phase_months / 12

                revenue += monthly_rev_delta
                # Cost delta is negative when costs decrease
                cogs += monthly_cost_delta * 0.6
                ga += monthly_cost_delta * 0.4

            gp = revenue - cogs
            ebitda = gp - ga
            ebit = ebitda - dep
            ebt = ebit - fin
            np = ebt * (1 - tax_rate)
            cumulative_cf += np + dep  # simplified: NP + D&A

            projections.append(MonthlyProjection(
                month=month,
                revenue=round(revenue, 2),
                cogs=round(cogs, 2),
                gross_profit=round(gp, 2),
                ga_expenses=round(ga, 2),
                ebitda=round(ebitda, 2),
                net_profit=round(np, 2),
                cumulative_cash_flow=round(cumulative_cf, 2),
            ))

        return projections

    def _build_schedule(self, phases: List[StrategyPhase], total_months: int) -> Dict[int, StrategyPhase]:
        """Map each month to its active phase."""
        schedule: Dict[int, StrategyPhase] = {}
        current_month = 1
        for phase in phases:
            phase_months = max(int(phase.duration_days / 30), 1)
            for m in range(phase_months):
                if current_month <= total_months:
                    schedule[current_month] = phase
                    current_month += 1
        return schedule


# ═══════════════════════════════════════════════════════════════════
# STRATEGY LEARNER — closed decision loop
# ═══════════════════════════════════════════════════════════════════

class StrategyLearner:
    """
    Tracks recommended actions → execution → outcomes.
    Feeds accuracy back into Decision Engine confidence.
    """

    def __init__(self):
        self._tracked_actions: Dict[str, ActionOutcome] = {}
        self._category_accuracy: Dict[str, List[float]] = defaultdict(list)

    def track_recommendation(self, action_id: str, description: str, category: str,
                              predicted_impact: float) -> None:
        """Record a recommended action for future outcome tracking."""
        self._tracked_actions[action_id] = ActionOutcome(
            action_id=action_id,
            action_description=description,
            category=category,
            recommended_at=datetime.now(timezone.utc).isoformat(),
            predicted_impact=predicted_impact,
        )
        logger.info("Tracking action: %s (category=%s, predicted_impact=%.0f)",
                     action_id, category, predicted_impact)

    def record_execution(self, action_id: str) -> bool:
        """Mark an action as executed."""
        outcome = self._tracked_actions.get(action_id)
        if outcome:
            outcome.executed = True
            outcome.executed_at = datetime.now(timezone.utc).isoformat()
            return True
        return False

    def record_outcome(self, action_id: str, actual_impact: float) -> Optional[ActionOutcome]:
        """Record the actual financial impact of an executed action."""
        outcome = self._tracked_actions.get(action_id)
        if not outcome:
            return None

        outcome.actual_impact = actual_impact
        outcome.success = actual_impact > 0

        # Accuracy: how close was prediction?
        if abs(outcome.predicted_impact) > 0:
            error = abs(actual_impact - outcome.predicted_impact) / abs(outcome.predicted_impact)
            outcome.accuracy_pct = round(max(0, (1 - error)) * 100, 2)
        else:
            outcome.accuracy_pct = 100.0 if abs(actual_impact) < 0.01 else 0.0

        self._category_accuracy[outcome.category].append(outcome.accuracy_pct)

        logger.info("Outcome recorded: %s — predicted=%.0f, actual=%.0f, accuracy=%.1f%%",
                     action_id, outcome.predicted_impact, actual_impact, outcome.accuracy_pct)
        return outcome

    def get_category_confidence(self, category: str) -> float:
        """Get learned confidence for an action category (0-1)."""
        accuracies = self._category_accuracy.get(category, [])
        if not accuracies:
            return 0.5  # default: 50% confidence (no data)
        return round(sum(accuracies) / len(accuracies) / 100, 4)

    def get_all_outcomes(self) -> List[ActionOutcome]:
        """Return all tracked action outcomes."""
        return list(self._tracked_actions.values())

    def generate_learning_summary(self) -> Dict[str, Any]:
        """Summary of action tracking and learning."""
        all_outcomes = list(self._tracked_actions.values())
        executed = [o for o in all_outcomes if o.executed]
        with_results = [o for o in executed if o.actual_impact != 0]
        successful = [o for o in with_results if o.success]

        category_stats = {}
        for cat, accs in self._category_accuracy.items():
            category_stats[cat] = {
                "actions_tracked": len(accs),
                "avg_accuracy_pct": round(sum(accs) / len(accs), 1) if accs else 0,
                "confidence": self.get_category_confidence(cat),
            }

        return {
            "total_recommended": len(all_outcomes),
            "total_executed": len(executed),
            "total_with_outcomes": len(with_results),
            "success_rate_pct": round(len(successful) / max(len(with_results), 1) * 100, 1),
            "category_performance": category_stats,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def reset(self):
        """Clear all tracked data (for testing)."""
        self._tracked_actions.clear()
        self._category_accuracy.clear()


# ═══════════════════════════════════════════════════════════════════
# COMPANY MEMORY — persistent financial pattern storage
# ═══════════════════════════════════════════════════════════════════

class CompanyMemory:
    """
    Stores learned financial patterns from company history.
    Tracks which strategies worked in which conditions.
    """

    def __init__(self):
        self._patterns: List[CompanyPattern] = []
        self._strategy_history: List[Dict[str, Any]] = []

    def record_pattern(self, pattern_type: str, metric: str,
                        description: str, magnitude: float) -> CompanyPattern:
        """Record a detected financial pattern."""
        # Check for existing pattern to update
        for p in self._patterns:
            if p.pattern_type == pattern_type and p.metric == metric:
                p.occurrences += 1
                p.avg_magnitude = round(
                    (p.avg_magnitude * (p.occurrences - 1) + magnitude) / p.occurrences, 2)
                p.last_seen = datetime.now(timezone.utc).isoformat()
                return p

        pattern = CompanyPattern(
            pattern_id=f"pattern_{uuid.uuid4().hex[:8]}",
            pattern_type=pattern_type,
            metric=metric,
            description=description,
            avg_magnitude=magnitude,
            occurrences=1,
            last_seen=datetime.now(timezone.utc).isoformat(),
        )
        self._patterns.append(pattern)
        return pattern

    def record_strategy_outcome(self, strategy: Strategy, outcome: str,
                                 health_before: float, health_after: float) -> None:
        """Record how a strategy performed."""
        self._strategy_history.append({
            "strategy_id": strategy.strategy_id,
            "strategy_name": strategy.name,
            "phases": len(strategy.phases),
            "roi": strategy.overall_roi,
            "outcome": outcome,
            "health_before": health_before,
            "health_after": health_after,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        })

    def get_patterns(self, metric: Optional[str] = None) -> List[CompanyPattern]:
        """Get all patterns, optionally filtered by metric."""
        if metric:
            return [p for p in self._patterns if p.metric == metric]
        return list(self._patterns)

    def get_strategy_history(self) -> List[Dict[str, Any]]:
        """Return strategy performance history."""
        return list(self._strategy_history)

    def get_best_strategy_for_health(self, health_score: float) -> Optional[Dict[str, Any]]:
        """Find the best historical strategy for a given health score range."""
        relevant = [
            s for s in self._strategy_history
            if abs(s["health_before"] - health_score) < 20 and s["outcome"] == "success"
        ]
        if relevant:
            return max(relevant, key=lambda s: s.get("health_after", 0) - s.get("health_before", 0))
        return None

    def summary(self) -> Dict[str, Any]:
        """Get company memory summary."""
        return {
            "total_patterns": len(self._patterns),
            "patterns": [p.to_dict() for p in self._patterns],
            "total_strategies_tracked": len(self._strategy_history),
            "successful_strategies": sum(1 for s in self._strategy_history if s["outcome"] == "success"),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def reset(self):
        """Clear all data (for testing)."""
        self._patterns.clear()
        self._strategy_history.clear()


# ═══════════════════════════════════════════════════════════════════
# UNIFIED STRATEGIC ENGINE
# ═══════════════════════════════════════════════════════════════════

class StrategicEngine:
    """
    Orchestrates strategy building, time simulation, learning, and memory.
    """

    def __init__(self):
        self.builder = StrategyBuilder()
        self.time_simulator = TimeSimulator()
        self.learner = StrategyLearner()
        self.memory = CompanyMemory()
        self._last_strategy: Optional[Strategy] = None

    def generate_strategy(
        self,
        actions: List[Any],
        health_score: float,
        financials: Dict[str, float],
        project_months: int = 12,
    ) -> Dict[str, Any]:
        """
        Full strategic pipeline: build strategy → project timeline → return.

        Returns:
            Dict with strategy, time_projection, and learning context.
        """
        # Build strategy
        strategy = self.builder.build_strategy(actions, health_score, financials)

        # Project financial evolution
        projection = self.time_simulator.project(financials, strategy, project_months)
        strategy.time_projection = [p.to_dict() for p in projection]

        # Track actions for closed loop
        for action in actions[:5]:
            if hasattr(action, "action_id"):
                self.learner.track_recommendation(
                    action.action_id,
                    getattr(action, "description", ""),
                    getattr(action, "category", ""),
                    getattr(action, "expected_impact", 0),
                )

        self._last_strategy = strategy

        return {
            "strategy": strategy.to_dict(),
            "time_projection": [p.to_dict() for p in projection],
            "learning_summary": self.learner.generate_learning_summary(),
            "company_memory": self.memory.summary(),
        }

    def get_last_strategy(self) -> Optional[Strategy]:
        return self._last_strategy

    def to_kg_entities(self) -> List[Dict[str, Any]]:
        """Generate KG entities from strategy and learnings."""
        entities = []
        if self._last_strategy:
            for phase in self._last_strategy.phases:
                entities.append({
                    "entity_id": f"strategy_phase_{phase.phase_name}_{self._last_strategy.strategy_id}",
                    "entity_type": "strategy_phase",
                    "label_en": f"{phase.phase_name.title()}: {phase.description[:60]}",
                    "label_ka": "",
                    "description": (
                        f"Phase {phase.phase_number}: {phase.duration_days} days, "
                        f"expected profit delta: {phase.expected_profit_delta:,.0f}"
                    ),
                    "properties": {
                        "phase_name": phase.phase_name,
                        "duration_days": phase.duration_days,
                        "expected_profit_delta": phase.expected_profit_delta,
                    },
                })
        return entities


# Module-level singleton
strategic_engine = StrategicEngine()
