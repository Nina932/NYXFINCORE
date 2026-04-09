"""
Phase J-1: Advanced Simulation — Sensitivity Analysis + Multi-Variable + Standalone Monte Carlo
================================================================================================
Fills Phase 5 gaps:
    - One-at-a-time sensitivity analysis (tornado charts)
    - Multi-variable simultaneous simulation with correlation
    - Standalone Monte Carlo on arbitrary P&L scenarios

All math is deterministic. No LLM.

Reuses:
    - financial_reasoning.reasoning_engine.simulate_scenario()
    - decision_engine.MonteCarloSimulator (seed-based RNG)
"""

import logging
import math
import random
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# DATACLASSES
# ═══════════════════════════════════════════════════════════════════

@dataclass
class SensitivityBand:
    """One variable's impact across a range of values."""
    variable: str
    base_value: float
    test_values: List[float]
    net_profit_outcomes: List[float]
    ebitda_outcomes: List[float]
    min_net_profit: float
    max_net_profit: float
    swing: float              # max - min (total range of impact)
    elasticity: float         # % change in NP per 1% change in variable

    def to_dict(self) -> Dict[str, Any]:
        return {
            "variable": self.variable,
            "base_value": round(self.base_value, 2),
            "test_values": [round(v, 2) for v in self.test_values],
            "net_profit_outcomes": [round(v, 2) for v in self.net_profit_outcomes],
            "ebitda_outcomes": [round(v, 2) for v in self.ebitda_outcomes],
            "min_net_profit": round(self.min_net_profit, 2),
            "max_net_profit": round(self.max_net_profit, 2),
            "swing": round(self.swing, 2),
            "elasticity": round(self.elasticity, 4),
        }


@dataclass
class SensitivityReport:
    """Tornado-chart ready sensitivity analysis."""
    base_net_profit: float
    base_ebitda: float
    bands: List[SensitivityBand]      # sorted by swing descending (biggest impact first)
    most_sensitive_variable: str
    least_sensitive_variable: str
    generated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "base_net_profit": round(self.base_net_profit, 2),
            "base_ebitda": round(self.base_ebitda, 2),
            "bands": [b.to_dict() for b in self.bands],
            "most_sensitive_variable": self.most_sensitive_variable,
            "least_sensitive_variable": self.least_sensitive_variable,
            "generated_at": self.generated_at,
        }


@dataclass
class MultiVarResult:
    """Result of simultaneous multi-variable scenario."""
    scenario_name: str
    variables_changed: Dict[str, float]  # {variable: pct_change}
    base_net_profit: float
    scenario_net_profit: float
    net_profit_delta: float
    base_ebitda: float
    scenario_ebitda: float
    interaction_effect: float   # delta vs sum-of-individual-effects
    risk_level: str
    generated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_name": self.scenario_name,
            "variables_changed": {k: round(v, 2) for k, v in self.variables_changed.items()},
            "base_net_profit": round(self.base_net_profit, 2),
            "scenario_net_profit": round(self.scenario_net_profit, 2),
            "net_profit_delta": round(self.net_profit_delta, 2),
            "base_ebitda": round(self.base_ebitda, 2),
            "scenario_ebitda": round(self.scenario_ebitda, 2),
            "interaction_effect": round(self.interaction_effect, 2),
            "risk_level": self.risk_level,
            "generated_at": self.generated_at,
        }


@dataclass
class ScenarioMonteCarloResult:
    """Monte Carlo simulation on an arbitrary P&L scenario."""
    iterations: int
    variable_ranges: Dict[str, Tuple[float, float]]  # {var: (min_pct, max_pct)}
    mean_net_profit: float
    median_net_profit: float
    p5_net_profit: float
    p25_net_profit: float
    p75_net_profit: float
    p95_net_profit: float
    std_dev: float
    probability_loss: float    # % of runs with net_profit < 0
    value_at_risk_95: float    # 5th percentile loss (VaR)
    generated_at: str = ""
    data_source: str = "fallback_defaults"  # "historical_volatility" | "user_specified" | "fallback_defaults"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "iterations": self.iterations,
            "variable_ranges": {k: [round(v[0], 2), round(v[1], 2)]
                                for k, v in self.variable_ranges.items()},
            "mean_net_profit": round(self.mean_net_profit, 2),
            "median_net_profit": round(self.median_net_profit, 2),
            "p5_net_profit": round(self.p5_net_profit, 2),
            "p25_net_profit": round(self.p25_net_profit, 2),
            "p75_net_profit": round(self.p75_net_profit, 2),
            "p95_net_profit": round(self.p95_net_profit, 2),
            "std_dev": round(self.std_dev, 2),
            "probability_loss_pct": round(self.probability_loss * 100, 1),
            "value_at_risk_95": round(self.value_at_risk_95, 2),
            "generated_at": self.generated_at,
            "data_source": self.data_source,
        }


# ═══════════════════════════════════════════════════════════════════
# SENSITIVITY ANALYZER
# ═══════════════════════════════════════════════════════════════════

class SensitivityAnalyzer:
    """
    One-at-a-time sensitivity analysis: vary each variable while holding others constant.
    Produces tornado-chart data showing which variables have the biggest P&L impact.
    """

    # Fallback ranges used when historical data is unavailable
    _FALLBACK_VARIABLES = {
        "revenue_pct": (-20.0, 20.0),
        "cogs_pct": (-15.0, 15.0),
        "ga_pct": (-25.0, 25.0),
        "tax_rate": (-5.0, 5.0),     # absolute pp change
        "finance_expense_pct": (-30.0, 30.0),
    }

    # Mapping from data_store field names to scenario variable names
    _FIELD_TO_VAR = {
        "revenue": "revenue_pct",
        "cogs": "cogs_pct",
        "ga_expenses": "ga_pct",
        "admin_expenses": "ga_pct",
        "finance_expense": "finance_expense_pct",
    }

    STEPS = 9  # -20, -15, -10, -5, 0, 5, 10, 15, 20 (for default range)

    @property
    def DEFAULT_VARIABLES(self) -> Dict[str, Tuple[float, float]]:
        """Compute ranges from historical data; fall back to static defaults."""
        return self._compute_historical_ranges()

    def _compute_historical_ranges(self, company_id: int = None) -> Dict[str, Tuple[float, float]]:
        """
        Compute sensitivity ranges from actual historical volatility.

        Uses the coefficient of variation (std/mean) of each metric across
        all stored periods. Range = +/- 2*CV (roughly 95% confidence),
        clamped between 5% and 50%.

        Falls back to _FALLBACK_VARIABLES when fewer than 3 periods exist.
        """
        try:
            from app.services.data_store import data_store

            companies = data_store.list_companies()
            if not companies:
                return dict(self._FALLBACK_VARIABLES)

            cid = company_id if company_id else companies[0]["id"]
            periods = data_store.get_all_periods(cid)

            if len(periods) < 3:
                return dict(self._FALLBACK_VARIABLES)

            # Collect metric values across periods
            metrics: Dict[str, List[float]] = {}
            for period in periods:
                fin = data_store.get_financials(cid, period)
                if not fin:
                    continue
                for key in ["revenue", "cogs", "ga_expenses", "admin_expenses", "finance_expense"]:
                    v = fin.get(key, 0) or 0
                    if v != 0:
                        metrics.setdefault(key, []).append(v)

            # Compute coefficient of variation -> range
            ranges: Dict[str, Tuple[float, float]] = {}
            for key, values in metrics.items():
                var_name = self._FIELD_TO_VAR.get(key)
                if not var_name or var_name in ranges:
                    continue
                if len(values) >= 3:
                    mean = statistics.mean(values)
                    if mean != 0:
                        cv = statistics.stdev(values) / abs(mean)
                        half_range = min(max(cv * 2, 0.05), 0.50) * 100  # convert to percentage
                        ranges[var_name] = (-half_range, half_range)
                    else:
                        ranges[var_name] = self._FALLBACK_VARIABLES.get(var_name, (-20.0, 20.0))
                else:
                    ranges[var_name] = self._FALLBACK_VARIABLES.get(var_name, (-20.0, 20.0))

            # Fill in any missing variables from fallback
            for var_name, fallback in self._FALLBACK_VARIABLES.items():
                if var_name not in ranges:
                    ranges[var_name] = fallback

            logger.info(
                "Sensitivity ranges computed from %d historical periods: %s",
                len(periods),
                {k: (round(v[0], 1), round(v[1], 1)) for k, v in ranges.items()},
            )
            return ranges
        except Exception as e:
            logger.warning("Failed to compute historical ranges, using fallback: %s", e)
            return dict(self._FALLBACK_VARIABLES)

    def analyze(
        self,
        base_financials: Dict[str, float],
        variables: Optional[Dict[str, Tuple[float, float]]] = None,
        steps: int = 9,
    ) -> SensitivityReport:
        """
        Run one-at-a-time sensitivity on each variable.

        Args:
            base_financials: {revenue, cogs, ga_expenses, depreciation, finance_expense, tax_rate}
            variables: {var_name: (min_pct, max_pct)} — defaults to DEFAULT_VARIABLES
            steps: number of test points per variable
        """
        from app.services.financial_reasoning import reasoning_engine

        vars_to_test = variables or self.DEFAULT_VARIABLES
        base = self._normalize(base_financials)

        # Get base case
        base_result = reasoning_engine.simulate_scenario("base", base, {})
        base_np = base_result.base_net_profit
        base_ebitda = base_result.base_ebitda

        bands: List[SensitivityBand] = []

        for var_name, (pct_min, pct_max) in vars_to_test.items():
            step_size = (pct_max - pct_min) / max(steps - 1, 1)
            test_pcts = [round(pct_min + i * step_size, 2) for i in range(steps)]

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

            # Elasticity: % change in NP for a 1% change in the variable
            if abs(pct_max - pct_min) > 0 and abs(base_np) > 0:
                elasticity = ((max_np - min_np) / abs(base_np)) / ((pct_max - pct_min) / 100.0)
            else:
                elasticity = 0.0

            base_val = base.get(var_name.replace("_pct", ""), 0)

            bands.append(SensitivityBand(
                variable=var_name,
                base_value=base_val,
                test_values=test_pcts,
                net_profit_outcomes=np_outcomes,
                ebitda_outcomes=ebitda_outcomes,
                min_net_profit=min_np,
                max_net_profit=max_np,
                swing=swing,
                elasticity=elasticity,
            ))

        # Sort by swing descending — biggest impact first (tornado order)
        bands.sort(key=lambda b: b.swing, reverse=True)

        return SensitivityReport(
            base_net_profit=base_np,
            base_ebitda=base_ebitda,
            bands=bands,
            most_sensitive_variable=bands[0].variable if bands else "",
            least_sensitive_variable=bands[-1].variable if bands else "",
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    def _normalize(self, f: Dict[str, float]) -> Dict[str, float]:
        rev = f.get("revenue", 0)
        cogs = f.get("cogs", 0)
        return {
            "revenue": rev,
            "cogs": cogs,
            "gross_profit": f.get("gross_profit", rev - cogs),
            "ga_expenses": f.get("ga_expenses", 0),
            "depreciation": f.get("depreciation", 0),
            "finance_expense": f.get("finance_expense", 0),
            "tax_rate": f.get("tax_rate", 0.15),
        }


# ═══════════════════════════════════════════════════════════════════
# MULTI-VARIABLE SIMULATOR
# ═══════════════════════════════════════════════════════════════════

class MultiVariableSimulator:
    """
    Simultaneous multi-variable scenario: change revenue, COGS, and G&A together
    and measure interaction effects (non-linear compounding).
    """

    def simulate(
        self,
        base_financials: Dict[str, float],
        variable_changes: Dict[str, float],
        scenario_name: str = "Multi-variable scenario",
    ) -> MultiVarResult:
        """
        Apply multiple variable changes simultaneously and measure interaction.

        Args:
            base_financials: base P&L
            variable_changes: {var_name: pct_change} — e.g. {"revenue_pct": 10, "cogs_pct": -5, "ga_pct": -3}
        """
        from app.services.financial_reasoning import reasoning_engine

        base = self._normalize(base_financials)

        # Base case
        base_result = reasoning_engine.simulate_scenario("base", base, {})
        base_np = base_result.base_net_profit
        base_ebitda = base_result.base_ebitda

        # Combined scenario
        combined_result = reasoning_engine.simulate_scenario(scenario_name, base, variable_changes)
        combined_np = combined_result.scenario_net_profit
        combined_ebitda = combined_result.scenario_ebitda

        # Individual effects (sum of isolated changes)
        sum_individual_deltas = 0.0
        for var, pct in variable_changes.items():
            solo_result = reasoning_engine.simulate_scenario(f"solo_{var}", base, {var: pct})
            sum_individual_deltas += (solo_result.scenario_net_profit - base_np)

        combined_delta = combined_np - base_np
        interaction = round(combined_delta - sum_individual_deltas, 2)

        # Risk assessment
        if combined_delta < -abs(base_np) * 0.3:
            risk = "critical"
        elif combined_delta < -abs(base_np) * 0.1:
            risk = "high"
        elif combined_delta < 0:
            risk = "medium"
        else:
            risk = "low"

        return MultiVarResult(
            scenario_name=scenario_name,
            variables_changed=variable_changes,
            base_net_profit=base_np,
            scenario_net_profit=combined_np,
            net_profit_delta=combined_delta,
            base_ebitda=base_ebitda,
            scenario_ebitda=combined_ebitda,
            interaction_effect=interaction,
            risk_level=risk,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    def _normalize(self, f: Dict[str, float]) -> Dict[str, float]:
        rev = f.get("revenue", 0)
        cogs = f.get("cogs", 0)
        return {
            "revenue": rev, "cogs": cogs,
            "gross_profit": f.get("gross_profit", rev - cogs),
            "ga_expenses": f.get("ga_expenses", 0),
            "depreciation": f.get("depreciation", 0),
            "finance_expense": f.get("finance_expense", 0),
            "tax_rate": f.get("tax_rate", 0.15),
        }


# ═══════════════════════════════════════════════════════════════════
# STANDALONE MONTE CARLO — arbitrary P&L scenario
# ═══════════════════════════════════════════════════════════════════

class ScenarioMonteCarlo:
    """
    Standalone Monte Carlo: vary multiple P&L variables simultaneously
    across specified ranges and compute distribution of outcomes.
    """

    # Fallback ranges when no historical data is available
    _FALLBACK_RANGES: Dict[str, Tuple[float, float]] = {
        "revenue_pct": (-15.0, 15.0),
        "cogs_pct": (-10.0, 10.0),
        "ga_pct": (-20.0, 20.0),
    }

    # Mapping from data_store field names to scenario variable names
    _FIELD_TO_VAR = {
        "revenue": "revenue_pct",
        "cogs": "cogs_pct",
        "ga_expenses": "ga_pct",
        "admin_expenses": "ga_pct",
    }

    def _compute_historical_ranges(self, company_id: int = None) -> Dict[str, Tuple[float, float]]:
        """
        Compute Monte Carlo ranges from actual historical volatility of financial data.

        Uses coefficient of variation (std/mean) * 2 as the half-range,
        clamped between 5% and 50%.
        """
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
                else:
                    ranges[var_name] = self._FALLBACK_RANGES.get(var_name, (-15.0, 15.0))

            # Fill missing from fallback
            for var_name, fallback in self._FALLBACK_RANGES.items():
                if var_name not in ranges:
                    ranges[var_name] = fallback

            logger.info(
                "Monte Carlo ranges from historical volatility (%d periods): %s",
                len(periods),
                {k: (round(v[0], 1), round(v[1], 1)) for k, v in ranges.items()},
            )
            return ranges
        except Exception as e:
            logger.warning("Failed to compute MC historical ranges, using fallback: %s", e)
            return dict(self._FALLBACK_RANGES)

    def simulate(
        self,
        base_financials: Dict[str, float],
        variable_ranges: Optional[Dict[str, Tuple[float, float]]] = None,
        iterations: int = 2000,
        seed: int = 42,
    ) -> ScenarioMonteCarloResult:
        """
        Run Monte Carlo simulation on arbitrary P&L scenario.

        Args:
            base_financials: base P&L metrics
            variable_ranges: {var: (min_pct, max_pct)} — e.g. {"revenue_pct": (-15, 15), "cogs_pct": (-10, 10)}
            iterations: number of MC runs
            seed: RNG seed for reproducibility
        """
        from app.services.financial_reasoning import reasoning_engine

        rng = random.Random(seed)
        if variable_ranges:
            ranges = variable_ranges
            data_source = "user_specified"
        else:
            # Derive ranges from historical volatility
            ranges = self._compute_historical_ranges()
            data_source = "historical_volatility"

        base = self._normalize(base_financials)
        outcomes: List[float] = []

        for i in range(iterations):
            changes = {}
            for var, (lo, hi) in ranges.items():
                # Uniform distribution across range
                changes[var] = rng.uniform(lo, hi)

            result = reasoning_engine.simulate_scenario(f"mc_{i}", base, changes)
            outcomes.append(result.scenario_net_profit)

        outcomes.sort()
        n = len(outcomes)
        mean_np = sum(outcomes) / n
        median_np = outcomes[n // 2]
        variance = sum((o - mean_np) ** 2 for o in outcomes) / n
        std_dev = math.sqrt(variance)
        prob_loss = sum(1 for o in outcomes if o < 0) / n

        return ScenarioMonteCarloResult(
            iterations=iterations,
            variable_ranges=ranges,
            mean_net_profit=mean_np,
            median_net_profit=median_np,
            p5_net_profit=outcomes[int(n * 0.05)],
            p25_net_profit=outcomes[int(n * 0.25)],
            p75_net_profit=outcomes[int(n * 0.75)],
            p95_net_profit=outcomes[int(n * 0.95)],
            std_dev=std_dev,
            probability_loss=prob_loss,
            value_at_risk_95=outcomes[int(n * 0.05)],  # VaR = 5th percentile
            generated_at=datetime.now(timezone.utc).isoformat(),
            data_source=data_source,
        )

    def _normalize(self, f: Dict[str, float]) -> Dict[str, float]:
        rev = f.get("revenue", 0)
        cogs = f.get("cogs", 0)
        return {
            "revenue": rev, "cogs": cogs,
            "gross_profit": f.get("gross_profit", rev - cogs),
            "ga_expenses": f.get("ga_expenses", 0),
            "depreciation": f.get("depreciation", 0),
            "finance_expense": f.get("finance_expense", 0),
            "tax_rate": f.get("tax_rate", 0.15),
        }


# Module-level singletons
sensitivity_analyzer = SensitivityAnalyzer()
multi_var_simulator = MultiVariableSimulator()
scenario_monte_carlo = ScenarioMonteCarlo()
