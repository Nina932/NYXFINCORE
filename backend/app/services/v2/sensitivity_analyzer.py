"""
FinAI v2 Sensitivity Analyzer — Decimal-precise, seed-deterministic.
====================================================================
Rewrite of Phase J-1 with:
- Decimal for all financial accumulation (float only for RNG)
- Seed-based deterministic Monte Carlo
- Explicit error handling

Public API (drop-in replacement for v1):
    from app.services.v2.sensitivity_analyzer import (
        sensitivity_analyzer, multi_var_simulator, scenario_monte_carlo
    )
"""

import logging
import math
import random
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from app.services.v2.decimal_utils import to_decimal, safe_divide, round_fin, is_zero

logger = logging.getLogger(__name__)


# ── Dataclasses (Decimal-based) ────────────────────────────────────────────

@dataclass
class SensitivityBand:
    variable: str
    base_value: Decimal
    test_values: List[Decimal]
    net_profit_outcomes: List[Decimal]
    ebitda_outcomes: List[Decimal]
    min_net_profit: Decimal
    max_net_profit: Decimal
    swing: Decimal
    elasticity: Decimal

    def to_dict(self) -> Dict[str, Any]:
        return {
            "variable": self.variable,
            "base_value": str(round_fin(self.base_value)),
            "test_values": [str(round_fin(v)) for v in self.test_values],
            "net_profit_outcomes": [str(round_fin(v)) for v in self.net_profit_outcomes],
            "ebitda_outcomes": [str(round_fin(v)) for v in self.ebitda_outcomes],
            "min_net_profit": str(round_fin(self.min_net_profit)),
            "max_net_profit": str(round_fin(self.max_net_profit)),
            "low_value": str(round_fin(self.min_net_profit)),
            "high_value": str(round_fin(self.max_net_profit)),
            "swing": str(round_fin(self.swing)),
            "elasticity": str(self.elasticity.quantize(Decimal("0.0001"))),
        }


@dataclass
class SensitivityReport:
    base_net_profit: Decimal
    base_ebitda: Decimal
    bands: List[SensitivityBand]
    most_sensitive_variable: str
    least_sensitive_variable: str
    generated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "base_net_profit": str(round_fin(self.base_net_profit)),
            "base_ebitda": str(round_fin(self.base_ebitda)),
            "bands": [b.to_dict() for b in self.bands],
            "most_sensitive_variable": self.most_sensitive_variable,
            "least_sensitive_variable": self.least_sensitive_variable,
            "generated_at": self.generated_at,
        }


@dataclass
class MultiVarResult:
    scenario_name: str
    variables_changed: Dict[str, Decimal]
    base_net_profit: Decimal
    scenario_net_profit: Decimal
    net_profit_delta: Decimal
    base_ebitda: Decimal
    scenario_ebitda: Decimal
    interaction_effect: Decimal
    risk_level: str
    generated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_name": self.scenario_name,
            "variables_changed": {k: str(round_fin(v)) for k, v in self.variables_changed.items()},
            "base_net_profit": str(round_fin(self.base_net_profit)),
            "scenario_net_profit": str(round_fin(self.scenario_net_profit)),
            "net_profit_delta": str(round_fin(self.net_profit_delta)),
            "base_ebitda": str(round_fin(self.base_ebitda)),
            "scenario_ebitda": str(round_fin(self.scenario_ebitda)),
            "interaction_effect": str(round_fin(self.interaction_effect)),
            "risk_level": self.risk_level,
            "generated_at": self.generated_at,
        }


@dataclass
class ScenarioMonteCarloResult:
    iterations: int
    variable_ranges: Dict[str, Tuple[float, float]]
    mean_net_profit: Decimal
    median_net_profit: Decimal
    p5_net_profit: Decimal
    p25_net_profit: Decimal
    p75_net_profit: Decimal
    p95_net_profit: Decimal
    std_dev: Decimal
    probability_loss: Decimal
    value_at_risk_95: Decimal
    generated_at: str = ""
    data_source: str = "fallback_defaults"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "iterations": self.iterations,
            "variable_ranges": {k: [round(v[0], 2), round(v[1], 2)]
                                for k, v in self.variable_ranges.items()},
            "mean_net_profit": str(round_fin(self.mean_net_profit)),
            "median_net_profit": str(round_fin(self.median_net_profit)),
            "p5_net_profit": str(round_fin(self.p5_net_profit)),
            "p25_net_profit": str(round_fin(self.p25_net_profit)),
            "p75_net_profit": str(round_fin(self.p75_net_profit)),
            "p95_net_profit": str(round_fin(self.p95_net_profit)),
            "std_dev": str(round_fin(self.std_dev)),
            "probability_loss_pct": str(round_fin(self.probability_loss * Decimal("100"))),
            "value_at_risk_95": str(round_fin(self.value_at_risk_95)),
            "generated_at": self.generated_at,
            "data_source": self.data_source,
        }


# ── Sensitivity Analyzer ──────────────────────────────────────────────────

class SensitivityAnalyzer:
    """One-at-a-time sensitivity analysis with Decimal precision."""

    _FALLBACK_VARIABLES = {
        "revenue_pct": (-20.0, 20.0),
        "cogs_pct": (-15.0, 15.0),
        "ga_pct": (-25.0, 25.0),
        "tax_rate": (-5.0, 5.0),
        "finance_expense_pct": (-30.0, 30.0),
    }

    _FIELD_TO_VAR = {
        "revenue": "revenue_pct", "cogs": "cogs_pct",
        "ga_expenses": "ga_pct", "admin_expenses": "ga_pct",
        "finance_expense": "finance_expense_pct",
    }

    STEPS = 9

    @property
    def DEFAULT_VARIABLES(self) -> Dict[str, Tuple[float, float]]:
        return self._compute_historical_ranges()

    def _compute_historical_ranges(self, company_id: int = None) -> Dict[str, Tuple[float, float]]:
        try:
            from app.services.data_store import data_store
            companies = data_store.list_companies()
            if not companies:
                return dict(self._FALLBACK_VARIABLES)
            cid = company_id if company_id else companies[0]["id"]
            periods = data_store.get_all_periods(cid)
            if len(periods) < 3:
                return dict(self._FALLBACK_VARIABLES)

            metrics: Dict[str, List[float]] = {}
            for period in periods:
                fin = data_store.get_financials(cid, period)
                if not fin:
                    continue
                for key in ["revenue", "cogs", "ga_expenses", "admin_expenses", "finance_expense"]:
                    v = fin.get(key, 0) or 0
                    if v != 0:
                        metrics.setdefault(key, []).append(v)

            ranges: Dict[str, Tuple[float, float]] = {}
            for key, values in metrics.items():
                var_name = self._FIELD_TO_VAR.get(key)
                if not var_name or var_name in ranges:
                    continue
                if len(values) >= 3:
                    mean = statistics.mean(values)
                    if mean != 0:
                        cv = statistics.stdev(values) / abs(mean)
                        half_range = min(max(cv * 2, 0.05), 0.50) * 100
                        ranges[var_name] = (-half_range, half_range)
                    else:
                        ranges[var_name] = self._FALLBACK_VARIABLES.get(var_name, (-20.0, 20.0))
                else:
                    ranges[var_name] = self._FALLBACK_VARIABLES.get(var_name, (-20.0, 20.0))

            for var_name, fallback in self._FALLBACK_VARIABLES.items():
                if var_name not in ranges:
                    ranges[var_name] = fallback

            return ranges
        except Exception as e:
            logger.warning("Failed to compute historical ranges: %s", e)
            return dict(self._FALLBACK_VARIABLES)

    def analyze(
        self,
        base_financials: Dict[str, Any],
        variables: Optional[Dict[str, Tuple[float, float]]] = None,
        steps: int = 9,
    ) -> SensitivityReport:
        """Run one-at-a-time sensitivity on each variable with Decimal precision."""
        from app.services.v2.financial_reasoning import reasoning_engine

        vars_to_test = variables or self.DEFAULT_VARIABLES
        base = self._normalize(base_financials)

        base_result = reasoning_engine.simulate_scenario("base", base, {})
        base_np = base_result.base_net_profit
        base_ebitda = base_result.base_ebitda

        bands: List[SensitivityBand] = []

        for var_name, (pct_min, pct_max) in vars_to_test.items():
            step_size = (pct_max - pct_min) / max(steps - 1, 1)
            test_pcts = [to_decimal(round(pct_min + i * step_size, 2)) for i in range(steps)]

            np_outcomes = []
            ebitda_outcomes = []

            for pct in test_pcts:
                changes = {var_name: pct}
                result = reasoning_engine.simulate_scenario(
                    f"sensitivity_{var_name}_{pct}", base, changes,
                )
                np_outcomes.append(result.scenario_net_profit)
                ebitda_outcomes.append(result.scenario_ebitda)

            min_np = min(np_outcomes)
            max_np = max(np_outcomes)
            swing = max_np - min_np

            # Elasticity: Decimal
            range_span = to_decimal(pct_max - pct_min)
            if not is_zero(range_span) and not is_zero(base_np):
                elasticity = safe_divide(
                    safe_divide(max_np - min_np, abs(base_np), precision=Decimal("0.0001")),
                    safe_divide(range_span, Decimal("100"), precision=Decimal("0.0001")),
                    precision=Decimal("0.0001"),
                )
            else:
                elasticity = Decimal("0")

            base_val = to_decimal(base.get(var_name.replace("_pct", ""), 0))

            bands.append(SensitivityBand(
                variable=var_name, base_value=base_val,
                test_values=test_pcts, net_profit_outcomes=np_outcomes,
                ebitda_outcomes=ebitda_outcomes,
                min_net_profit=min_np, max_net_profit=max_np,
                swing=swing, elasticity=elasticity,
            ))

        bands.sort(key=lambda b: b.swing, reverse=True)

        return SensitivityReport(
            base_net_profit=base_np, base_ebitda=base_ebitda,
            bands=bands,
            most_sensitive_variable=bands[0].variable if bands else "",
            least_sensitive_variable=bands[-1].variable if bands else "",
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    def _normalize(self, f: Dict[str, Any]) -> Dict[str, Any]:
        rev = to_decimal(f.get("revenue", 0))
        cogs = to_decimal(f.get("cogs", 0))
        ga = f.get("ga_expenses") or f.get("operating_expenses") or f.get("admin_expenses") or 0
        return {
            "revenue": rev, "cogs": cogs,
            "gross_profit": to_decimal(f.get("gross_profit", rev - cogs)),
            "ga_expenses": to_decimal(ga),
            "depreciation": to_decimal(f.get("depreciation", 0)),
            "finance_expense": to_decimal(f.get("finance_expense", 0)),
            "tax_rate": to_decimal(f.get("tax_rate", "0.15")),
        }


# ── Multi-Variable Simulator ──────────────────────────────────────────────

class MultiVariableSimulator:
    """Simultaneous multi-variable scenario with interaction measurement."""

    def simulate(
        self,
        base_financials: Dict[str, Any],
        variable_changes: Dict[str, Any],
        scenario_name: str = "Multi-variable scenario",
    ) -> MultiVarResult:
        from app.services.v2.financial_reasoning import reasoning_engine

        base = self._normalize(base_financials)

        base_result = reasoning_engine.simulate_scenario("base", base, {})
        base_np = base_result.base_net_profit
        base_ebitda = base_result.base_ebitda

        # Convert changes to Decimal
        dec_changes = {k: to_decimal(v) for k, v in variable_changes.items()}

        combined_result = reasoning_engine.simulate_scenario(scenario_name, base, dec_changes)
        combined_np = combined_result.scenario_net_profit
        combined_ebitda = combined_result.scenario_ebitda

        # Individual effects
        sum_individual_deltas = Decimal("0")
        for var, pct in dec_changes.items():
            solo_result = reasoning_engine.simulate_scenario(f"solo_{var}", base, {var: pct})
            sum_individual_deltas += (solo_result.scenario_net_profit - base_np)

        combined_delta = combined_np - base_np
        interaction = round_fin(combined_delta - sum_individual_deltas)

        # Risk assessment
        threshold = abs(base_np)
        if combined_delta < -threshold * Decimal("0.3"):
            risk = "critical"
        elif combined_delta < -threshold * Decimal("0.1"):
            risk = "high"
        elif combined_delta < 0:
            risk = "medium"
        else:
            risk = "low"

        return MultiVarResult(
            scenario_name=scenario_name,
            variables_changed=dec_changes,
            base_net_profit=base_np, scenario_net_profit=combined_np,
            net_profit_delta=combined_delta,
            base_ebitda=base_ebitda, scenario_ebitda=combined_ebitda,
            interaction_effect=interaction, risk_level=risk,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    def _normalize(self, f: Dict[str, Any]) -> Dict[str, Any]:
        rev = to_decimal(f.get("revenue", 0))
        cogs = to_decimal(f.get("cogs", 0))
        ga = f.get("ga_expenses") or f.get("operating_expenses") or f.get("admin_expenses") or 0
        return {
            "revenue": rev, "cogs": cogs,
            "gross_profit": to_decimal(f.get("gross_profit", rev - cogs)),
            "ga_expenses": to_decimal(ga),
            "depreciation": to_decimal(f.get("depreciation", 0)),
            "finance_expense": to_decimal(f.get("finance_expense", 0)),
            "tax_rate": to_decimal(f.get("tax_rate", "0.15")),
        }


# ── Standalone Monte Carlo ────────────────────────────────────────────────

class ScenarioMonteCarlo:
    """Seed-deterministic Monte Carlo on arbitrary P&L scenario — Decimal accumulation."""

    _FALLBACK_RANGES: Dict[str, Tuple[float, float]] = {
        "revenue_pct": (-15.0, 15.0),
        "cogs_pct": (-10.0, 10.0),
        "ga_pct": (-20.0, 20.0),
    }

    _FIELD_TO_VAR = {
        "revenue": "revenue_pct", "cogs": "cogs_pct",
        "ga_expenses": "ga_pct", "admin_expenses": "ga_pct",
    }

    def _compute_historical_ranges(self, company_id: int = None) -> Dict[str, Tuple[float, float]]:
        try:
            from app.services.data_store import data_store
            companies = data_store.list_companies()
            if not companies:
                return dict(self._FALLBACK_RANGES)
            cid = company_id if company_id else companies[0]["id"]
            periods = data_store.get_all_periods(cid)
            if len(periods) < 3:
                return dict(self._FALLBACK_RANGES)

            metrics: Dict[str, List[float]] = {}
            for period in periods:
                fin = data_store.get_financials(cid, period)
                if not fin:
                    continue
                for key in ["revenue", "cogs", "ga_expenses", "admin_expenses"]:
                    v = fin.get(key, 0) or 0
                    if v != 0:
                        metrics.setdefault(key, []).append(v)

            ranges: Dict[str, Tuple[float, float]] = {}
            for key, values in metrics.items():
                var_name = self._FIELD_TO_VAR.get(key)
                if not var_name or var_name in ranges:
                    continue
                if len(values) >= 3:
                    mean = statistics.mean(values)
                    if mean != 0:
                        cv = statistics.stdev(values) / abs(mean)
                        half_range = min(max(cv * 2, 0.05), 0.50) * 100
                        ranges[var_name] = (-half_range, half_range)
                    else:
                        ranges[var_name] = self._FALLBACK_RANGES.get(var_name, (-15.0, 15.0))

            for var_name, fallback in self._FALLBACK_RANGES.items():
                if var_name not in ranges:
                    ranges[var_name] = fallback

            return ranges
        except Exception as e:
            logger.warning("Failed to compute MC historical ranges: %s", e)
            return dict(self._FALLBACK_RANGES)

    def simulate(
        self,
        base_financials: Dict[str, Any],
        variable_ranges: Optional[Dict[str, Tuple[float, float]]] = None,
        iterations: int = 2000,
        seed: int = 42,
    ) -> ScenarioMonteCarloResult:
        """Run Monte Carlo with Decimal accumulation, float RNG."""
        from app.services.v2.financial_reasoning import reasoning_engine

        rng = random.Random(seed)
        if variable_ranges:
            ranges = variable_ranges
            data_source = "user_specified"
        else:
            ranges = self._compute_historical_ranges()
            data_source = "historical_volatility"

        base = self._normalize(base_financials)
        outcomes: List[Decimal] = []

        for i in range(iterations):
            changes = {}
            for var, (lo, hi) in ranges.items():
                # Float for RNG, converted to Decimal for math
                changes[var] = to_decimal(rng.uniform(lo, hi))

            result = reasoning_engine.simulate_scenario(f"mc_{i}", base, changes)
            outcomes.append(result.scenario_net_profit)

        outcomes.sort()
        n = len(outcomes)
        mean_np = safe_divide(sum(outcomes), Decimal(str(n)))
        median_np = outcomes[n // 2]
        variance = safe_divide(
            sum((o - mean_np) ** 2 for o in outcomes),
            Decimal(str(n))
        )
        # std_dev: use float sqrt then convert back (Decimal sqrt is complex)
        std_dev = to_decimal(math.sqrt(float(variance)))
        prob_loss = safe_divide(
            Decimal(str(sum(1 for o in outcomes if o < 0))),
            Decimal(str(n)),
            precision=Decimal("0.001"),
        )

        return ScenarioMonteCarloResult(
            iterations=iterations, variable_ranges=ranges,
            mean_net_profit=mean_np, median_net_profit=median_np,
            p5_net_profit=outcomes[int(n * 0.05)],
            p25_net_profit=outcomes[int(n * 0.25)],
            p75_net_profit=outcomes[int(n * 0.75)],
            p95_net_profit=outcomes[int(n * 0.95)],
            std_dev=std_dev, probability_loss=prob_loss,
            value_at_risk_95=outcomes[int(n * 0.05)],
            generated_at=datetime.now(timezone.utc).isoformat(),
            data_source=data_source,
        )

    def _normalize(self, f: Dict[str, Any]) -> Dict[str, Any]:
        rev = to_decimal(f.get("revenue", 0))
        cogs = to_decimal(f.get("cogs", 0))
        ga = f.get("ga_expenses") or f.get("operating_expenses") or f.get("admin_expenses") or 0
        return {
            "revenue": rev, "cogs": cogs,
            "gross_profit": to_decimal(f.get("gross_profit", rev - cogs)),
            "ga_expenses": to_decimal(ga),
            "depreciation": to_decimal(f.get("depreciation", 0)),
            "finance_expense": to_decimal(f.get("finance_expense", 0)),
            "tax_rate": to_decimal(f.get("tax_rate", "0.15")),
        }


# Module-level singletons
sensitivity_analyzer = SensitivityAnalyzer()
multi_var_simulator = MultiVariableSimulator()
scenario_monte_carlo = ScenarioMonteCarlo()
