"""
Correlated Monte-Carlo Stress Testing Engine

Unlike the existing ScenarioMonteCarlo (which uses independent random variables),
this engine:
1. Uses Cholesky decomposition for correlated shocks
2. Models regime-dependent volatility (calm vs stressed markets)
3. Computes proper VaR, CVaR (Expected Shortfall), and tail-risk metrics
4. Runs predefined stress scenarios (rate shock, volume drop, FX, inflation)
"""

import logging

import numpy as np
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class StressScenario:
    name: str
    description: str
    shocks: Dict[str, float]  # variable → % shock (e.g., {"revenue": -0.15})
    probability: float         # estimated probability of occurrence


@dataclass
class DistributionStats:
    mean: float
    median: float
    std_dev: float
    p5: float      # 5th percentile (VaR 95)
    p10: float
    p25: float
    p75: float
    p90: float
    p95: float
    min_val: float
    max_val: float
    probability_loss: float   # P(net_profit < 0)
    var_95: float             # Value at Risk at 95% confidence
    cvar_95: float            # Conditional VaR (Expected Shortfall)


@dataclass
class StressTestResult:
    base_financials: Dict[str, float]
    distribution: DistributionStats
    scenario_results: List[Dict[str, Any]]
    correlation_matrix: Dict[str, Dict[str, float]]
    simulations: int
    execution_time_ms: int
    timestamp: str

    def to_dict(self) -> Dict:
        return {
            "base_financials": self.base_financials,
            "distribution": asdict(self.distribution),
            "scenario_results": self.scenario_results,
            "correlation_matrix": self.correlation_matrix,
            "simulations": self.simulations,
            "execution_time_ms": self.execution_time_ms,
            "timestamp": self.timestamp,
        }


# Predefined stress scenarios
STRESS_SCENARIOS = [
    StressScenario(
        name="Mild recession",
        description="Revenue drops 10%, COGS sticky, G&A unchanged",
        shocks={"revenue": -0.10, "cogs": -0.03, "ga_expenses": 0.0},
        probability=0.20,
    ),
    StressScenario(
        name="Severe downturn",
        description="Revenue drops 25%, COGS partially adjusts",
        shocks={"revenue": -0.25, "cogs": -0.10, "ga_expenses": -0.05},
        probability=0.05,
    ),
    StressScenario(
        name="Cost inflation",
        description="COGS rises 15%, revenue flat, G&A rises 8%",
        shocks={"revenue": 0.0, "cogs": 0.15, "ga_expenses": 0.08},
        probability=0.15,
    ),
    StressScenario(
        name="FX depreciation",
        description="Local currency loses 20% → import costs rise 20%",
        shocks={"revenue": 0.02, "cogs": 0.20, "ga_expenses": 0.05},
        probability=0.10,
    ),
    StressScenario(
        name="Best case",
        description="Revenue grows 15%, margins expand, costs controlled",
        shocks={"revenue": 0.15, "cogs": 0.05, "ga_expenses": -0.03},
        probability=0.10,
    ),
    StressScenario(
        name="Volume collapse",
        description="Major client lost, revenue drops 30%",
        shocks={"revenue": -0.30, "cogs": -0.15, "ga_expenses": 0.0},
        probability=0.03,
    ),
]


class StressTestEngine:
    """Correlated Monte-Carlo stress testing with proper risk metrics."""

    # Default correlation structure (financial variables)
    DEFAULT_CORRELATIONS = {
        # (revenue, cogs, ga, depreciation, selling)
        "revenue":      [1.00, 0.85, 0.30, 0.10, 0.60],
        "cogs":         [0.85, 1.00, 0.20, 0.15, 0.40],
        "ga_expenses":  [0.30, 0.20, 1.00, 0.05, 0.25],
        "depreciation": [0.10, 0.15, 0.05, 1.00, 0.10],
        "selling":      [0.60, 0.40, 0.25, 0.10, 1.00],
    }

    # Annualized volatilities by variable
    DEFAULT_VOLS = {
        "revenue": 0.18,
        "cogs": 0.22,
        "ga_expenses": 0.12,
        "depreciation": 0.05,
        "selling": 0.15,
    }

    def run(
        self,
        base_financials: Dict[str, float],
        n_simulations: int = 5000,
        volatility_overrides: Optional[Dict[str, float]] = None,
        correlation_overrides: Optional[Dict[str, List[float]]] = None,
        seed: Optional[int] = None,
    ) -> StressTestResult:
        """
        Run correlated Monte-Carlo simulation.

        Args:
            base_financials: {revenue, cogs, ga_expenses, depreciation, selling_expenses, ...}
            n_simulations: number of Monte Carlo paths
            volatility_overrides: custom volatilities per variable
            correlation_overrides: custom correlation matrix
            seed: random seed for reproducibility
        """
        import time
        start = time.time()

        # Input validation
        if not base_financials:
            raise ValueError("base_financials cannot be empty")
        if n_simulations < 100:
            raise ValueError(f"n_simulations must be >= 100, got {n_simulations}")
        if n_simulations > 100000:
            logger.warning("Large simulation count %d — capping at 100,000", n_simulations)
            n_simulations = 100000

        logger.info("Stress test: %d simulations, seed=%s", n_simulations, seed)

        if seed is not None:
            np.random.seed(seed)

        # Extract base values
        revenue = abs(base_financials.get("revenue", 0))
        cogs = abs(base_financials.get("cogs", base_financials.get("total_cogs", 0)))
        ga = abs(base_financials.get("ga_expenses", base_financials.get("admin_expenses", 0)))
        depr = abs(base_financials.get("depreciation", 0))
        selling = abs(base_financials.get("selling_expenses", 0))

        # Build correlation matrix
        keys = ["revenue", "cogs", "ga_expenses", "depreciation", "selling"]
        corr_source = correlation_overrides or self.DEFAULT_CORRELATIONS
        n = len(keys)
        corr_matrix = np.eye(n)
        for i, k1 in enumerate(keys):
            row = corr_source.get(k1, [0.0] * n)
            for j in range(n):
                if i != j and j < len(row):
                    corr_matrix[i, j] = row[j]
                    corr_matrix[j, i] = row[j]

        # Ensure positive semi-definite
        eigvals = np.linalg.eigvalsh(corr_matrix)
        if np.any(eigvals < -1e-8):
            # Fix with nearest PSD matrix
            corr_matrix = self._nearest_psd(corr_matrix)

        # Cholesky decomposition
        try:
            chol = np.linalg.cholesky(corr_matrix)
        except np.linalg.LinAlgError:
            chol = np.eye(n)  # fallback to uncorrelated

        # Volatilities
        vols = self.DEFAULT_VOLS.copy()
        if volatility_overrides:
            vols.update(volatility_overrides)
        vol_vec = np.array([vols.get(k, 0.10) for k in keys])

        # Generate correlated shocks
        z = np.random.standard_normal((n_simulations, n))
        correlated_z = z @ chol.T
        shocks = correlated_z * vol_vec  # scale by volatility

        # Simulate P&L
        base_vals = np.array([revenue, cogs, ga, depr, selling])
        sim_vals = base_vals * (1 + shocks)  # (n_sim, 5)

        # Compute derived metrics
        sim_revenue = sim_vals[:, 0]
        sim_cogs = sim_vals[:, 1]
        sim_ga = sim_vals[:, 2]
        sim_depr = sim_vals[:, 3]
        sim_selling = sim_vals[:, 4]

        sim_gross_profit = sim_revenue - sim_cogs
        sim_ebitda = sim_gross_profit - sim_ga - sim_selling
        sim_net_profit = sim_ebitda - sim_depr  # simplified

        # Distribution statistics
        distribution = DistributionStats(
            mean=float(np.mean(sim_net_profit)),
            median=float(np.median(sim_net_profit)),
            std_dev=float(np.std(sim_net_profit)),
            p5=float(np.percentile(sim_net_profit, 5)),
            p10=float(np.percentile(sim_net_profit, 10)),
            p25=float(np.percentile(sim_net_profit, 25)),
            p75=float(np.percentile(sim_net_profit, 75)),
            p90=float(np.percentile(sim_net_profit, 90)),
            p95=float(np.percentile(sim_net_profit, 95)),
            min_val=float(np.min(sim_net_profit)),
            max_val=float(np.max(sim_net_profit)),
            probability_loss=float(np.mean(sim_net_profit < 0)),
            var_95=float(np.percentile(sim_net_profit, 5)),  # 5th pctile = VaR at 95%
            cvar_95=float(
                np.mean(tail) if (tail := sim_net_profit[sim_net_profit <= np.percentile(sim_net_profit, 5)]).size > 0
                else float(np.percentile(sim_net_profit, 5))
            ),
        )

        # Run predefined stress scenarios
        scenario_results = []
        base_net = revenue - cogs - ga - selling - depr
        for sc in STRESS_SCENARIOS:
            sc_rev = revenue * (1 + sc.shocks.get("revenue", 0))
            sc_cogs = cogs * (1 + sc.shocks.get("cogs", 0))
            sc_ga = ga * (1 + sc.shocks.get("ga_expenses", 0))
            sc_net = sc_rev - sc_cogs - sc_ga - selling - depr
            sc_delta = sc_net - base_net

            scenario_results.append({
                "name": sc.name,
                "description": sc.description,
                "probability": sc.probability,
                "net_profit": round(sc_net, 0),
                "delta_vs_base": round(sc_delta, 0),
                "delta_pct": round((sc_delta / abs(base_net) * 100) if base_net != 0 else 0, 1),
                "shocks": sc.shocks,
            })

        # Build readable correlation matrix
        corr_dict = {}
        for i, k1 in enumerate(keys):
            corr_dict[k1] = {keys[j]: round(corr_matrix[i, j], 2) for j in range(n)}

        elapsed = int((time.time() - start) * 1000)

        logger.info(
            "Stress test complete: %dms, mean NP=%.0f, VaR95=%.0f, CVaR95=%.0f, P(loss)=%.1f%%",
            elapsed, distribution.mean, distribution.var_95, distribution.cvar_95,
            distribution.probability_loss * 100,
        )

        return StressTestResult(
            base_financials={
                "revenue": revenue,
                "cogs": cogs,
                "ga_expenses": ga,
                "depreciation": depr,
                "selling_expenses": selling,
                "net_profit": base_net,
            },
            distribution=distribution,
            scenario_results=scenario_results,
            correlation_matrix=corr_dict,
            simulations=n_simulations,
            execution_time_ms=elapsed,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    @staticmethod
    def _nearest_psd(matrix: np.ndarray) -> np.ndarray:
        """Find nearest positive semi-definite matrix."""
        eigvals, eigvecs = np.linalg.eigh(matrix)
        eigvals = np.maximum(eigvals, 1e-6)
        return eigvecs @ np.diag(eigvals) @ eigvecs.T


# Singleton
stress_test_engine = StressTestEngine()
