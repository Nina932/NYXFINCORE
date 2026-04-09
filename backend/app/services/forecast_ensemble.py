"""
forecast_ensemble.py -- Advanced Forecasting: Ensemble + Backtest
=================================================================
Extends the existing forecasting engine with:
  1. Ensemble forecasting (weighted average of multiple methods)
  2. Confidence interval computation per method
  3. Backtest framework (holdout validation)
  4. Forecast accuracy tracking (MAPE, MAE, RMSE)

Does NOT modify existing forecasting.py -- wraps it.

Phase G-5 of the FinAI Full System Upgrade.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


@dataclass
class ForecastPoint:
    """A single forecast data point with confidence interval."""
    period: str
    value: float
    lower_bound: float
    upper_bound: float
    method: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "period": self.period,
            "value": round(self.value, 2),
            "lower_bound": round(self.lower_bound, 2),
            "upper_bound": round(self.upper_bound, 2),
            "method": self.method,
        }


@dataclass
class MethodResult:
    """Result from a single forecasting method."""
    method: str
    points: List[ForecastPoint] = field(default_factory=list)
    weight: float = 1.0
    mape: Optional[float] = None
    rmse: Optional[float] = None
    mae: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "method": self.method,
            "points": [p.to_dict() for p in self.points],
            "weight": round(self.weight, 4),
            "mape": round(self.mape, 4) if self.mape is not None else None,
            "rmse": round(self.rmse, 2) if self.rmse is not None else None,
            "mae": round(self.mae, 2) if self.mae is not None else None,
        }


@dataclass
class EnsembleForecast:
    """Combined forecast from multiple methods."""
    methods_used: List[str] = field(default_factory=list)
    method_results: List[MethodResult] = field(default_factory=list)
    ensemble_points: List[ForecastPoint] = field(default_factory=list)
    backtest_accuracy: Optional[Dict[str, float]] = None
    best_method: Optional[str] = None
    weights: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "methods_used": self.methods_used,
            "method_results": [m.to_dict() for m in self.method_results],
            "ensemble_points": [p.to_dict() for p in self.ensemble_points],
            "backtest_accuracy": self.backtest_accuracy,
            "best_method": self.best_method,
            "weights": {k: round(v, 4) for k, v in self.weights.items()},
        }


@dataclass
class BacktestResult:
    """Result of backtesting a forecasting method."""
    method: str
    holdout_periods: int = 0
    mape: float = 0.0
    mae: float = 0.0
    rmse: float = 0.0
    predictions: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "method": self.method,
            "holdout_periods": self.holdout_periods,
            "mape": round(self.mape, 4),
            "mae": round(self.mae, 2),
            "rmse": round(self.rmse, 2),
            "predictions": self.predictions,
        }


# ---------------------------------------------------------------------------
# Internal forecasting methods (simple, standalone)
# ---------------------------------------------------------------------------

def _moving_average_forecast(values: List[float], periods: int, window: int = 3) -> List[float]:
    """Simple moving average forecast."""
    if len(values) < window:
        window = len(values)
    forecasts = []
    data = list(values)
    for _ in range(periods):
        avg = sum(data[-window:]) / window
        forecasts.append(avg)
        data.append(avg)
    return forecasts


def _exp_smoothing_forecast(values: List[float], periods: int, alpha: float = 0.3) -> List[float]:
    """Exponential smoothing forecast."""
    if not values:
        return [0.0] * periods
    level = values[0]
    for v in values[1:]:
        level = alpha * v + (1 - alpha) * level
    return [level] * periods


def _linear_regression_forecast(values: List[float], periods: int) -> List[float]:
    """Linear regression trend extrapolation."""
    n = len(values)
    if n < 2:
        return [values[0] if values else 0.0] * periods
    x_mean = (n - 1) / 2
    y_mean = sum(values) / n
    num = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
    den = sum((i - x_mean) ** 2 for i in range(n))
    slope = num / den if den != 0 else 0
    intercept = y_mean - slope * x_mean
    return [slope * (n + i) + intercept for i in range(periods)]


def _growth_rate_forecast(values: List[float], periods: int) -> List[float]:
    """Compound annual growth rate based forecast."""
    if len(values) < 2 or values[0] == 0:
        return [values[-1] if values else 0.0] * periods
    cagr = (values[-1] / values[0]) ** (1 / (len(values) - 1)) - 1
    last = values[-1]
    result = []
    for _ in range(periods):
        last = last * (1 + cagr)
        result.append(last)
    return result


def _seasonal_forecast(values: List[float], periods: int) -> List[float]:
    """Simple seasonal decomposition (repeats the last cycle)."""
    if len(values) < 4:
        return _moving_average_forecast(values, periods)
    # Use last season_len values as the seasonal pattern
    season_len = min(12, len(values) // 2)
    if season_len < 2:
        season_len = len(values)
    seasonal_pattern = values[-season_len:]
    result = []
    for i in range(periods):
        result.append(seasonal_pattern[i % season_len])
    return result


_METHODS = {
    "moving_avg": _moving_average_forecast,
    "exp_smoothing": _exp_smoothing_forecast,
    "linear_regression": _linear_regression_forecast,
    "growth_rate": _growth_rate_forecast,
    "seasonal": _seasonal_forecast,
}


# ---------------------------------------------------------------------------
# ForecastEnsemble
# ---------------------------------------------------------------------------

class ForecastEnsemble:
    """Ensemble forecasting engine wrapping multiple forecast methods."""

    DEFAULT_WEIGHTS = {
        "moving_avg": 0.15,
        "exp_smoothing": 0.25,
        "linear_regression": 0.25,
        "growth_rate": 0.15,
        "seasonal": 0.20,
    }

    def __init__(self):
        self._weights = dict(self.DEFAULT_WEIGHTS)
        self._accuracy_history: List[BacktestResult] = []

    def ensemble_forecast(
        self,
        historical_values: List[float],
        historical_periods: List[str],
        forecast_periods: int = 6,
        confidence_level: float = 0.95,
        methods: Optional[List[str]] = None,
    ) -> EnsembleForecast:
        """Generate an ensemble forecast combining multiple methods."""
        if not historical_values or len(historical_values) < 2:
            return EnsembleForecast(
                methods_used=[], ensemble_points=[],
                weights={}, best_method=None,
            )

        use_methods = methods or list(_METHODS.keys())
        use_methods = [m for m in use_methods if m in _METHODS]

        # Generate future period labels
        future_periods = []
        for i in range(forecast_periods):
            if historical_periods:
                future_periods.append(f"Forecast {i + 1}")
            else:
                future_periods.append(f"Period {len(historical_values) + i + 1}")

        method_results: List[MethodResult] = []
        all_forecasts: Dict[str, List[float]] = {}

        for method_name in use_methods:
            func = _METHODS[method_name]
            try:
                forecasted = func(historical_values, forecast_periods)
            except Exception as e:
                logger.warning("Method %s failed: %s", method_name, e)
                continue

            # Compute confidence intervals
            ci = self.compute_confidence_interval(
                historical_values, forecasted, confidence_level)

            points = []
            for i, val in enumerate(forecasted):
                lower, upper = ci[i] if i < len(ci) else (val * 0.9, val * 1.1)
                points.append(ForecastPoint(
                    period=future_periods[i] if i < len(future_periods) else f"P{i+1}",
                    value=val, lower_bound=lower, upper_bound=upper,
                    method=method_name,
                ))

            weight = self._weights.get(method_name, 1.0 / len(use_methods))
            mr = MethodResult(method=method_name, points=points, weight=weight)
            method_results.append(mr)
            all_forecasts[method_name] = forecasted

        if not method_results:
            return EnsembleForecast(methods_used=use_methods, ensemble_points=[], weights={})

        # Combine into weighted ensemble
        ensemble_values = []
        for i in range(forecast_periods):
            weighted_sum = 0.0
            weight_sum = 0.0
            for mr in method_results:
                if i < len(mr.points):
                    weighted_sum += mr.points[i].value * mr.weight
                    weight_sum += mr.weight
            ensemble_val = weighted_sum / weight_sum if weight_sum > 0 else 0.0
            ensemble_values.append(ensemble_val)

        # Ensemble CI (tighter than individual methods — average of bounds)
        ensemble_points = []
        for i in range(forecast_periods):
            val = ensemble_values[i]
            # Ensemble CI: weighted average of individual CIs
            lower_sum, upper_sum, w_sum = 0.0, 0.0, 0.0
            for mr in method_results:
                if i < len(mr.points):
                    lower_sum += mr.points[i].lower_bound * mr.weight
                    upper_sum += mr.points[i].upper_bound * mr.weight
                    w_sum += mr.weight
            lower = lower_sum / w_sum if w_sum > 0 else val * 0.9
            upper = upper_sum / w_sum if w_sum > 0 else val * 1.1
            # Tighten by averaging with point estimate
            lower = (lower + val) / 2
            upper = (upper + val) / 2
            # Ensure lower < val < upper
            lower = min(lower, val)
            upper = max(upper, val)

            ensemble_points.append(ForecastPoint(
                period=future_periods[i] if i < len(future_periods) else f"P{i+1}",
                value=val, lower_bound=lower, upper_bound=upper,
                method="ensemble",
            ))

        weights = {mr.method: mr.weight for mr in method_results}

        return EnsembleForecast(
            methods_used=use_methods,
            method_results=method_results,
            ensemble_points=ensemble_points,
            weights=weights,
            best_method=max(method_results, key=lambda m: m.weight).method if method_results else None,
        )

    def compute_confidence_interval(
        self,
        historical_values: List[float],
        forecast_values: List[float],
        confidence_level: float = 0.95,
    ) -> List[Tuple[float, float]]:
        """Compute CI using residual standard deviation."""
        if not historical_values or len(historical_values) < 2:
            return [(v * 0.9, v * 1.1) for v in forecast_values]

        # Compute residual std dev from historical data
        mean_val = sum(historical_values) / len(historical_values)
        variance = sum((v - mean_val) ** 2 for v in historical_values) / (len(historical_values) - 1)
        std_dev = math.sqrt(variance) if variance > 0 else abs(mean_val) * 0.1

        # Z-score for confidence level
        z_scores = {0.90: 1.645, 0.95: 1.960, 0.99: 2.576}
        z = z_scores.get(confidence_level, 1.960)

        intervals = []
        for i, val in enumerate(forecast_values):
            # CI widens with forecast horizon
            horizon_factor = math.sqrt(1 + i * 0.5)
            margin = z * std_dev * horizon_factor
            intervals.append((val - margin, val + margin))
        return intervals

    def backtest(
        self,
        historical_values: List[float],
        historical_periods: List[str],
        holdout_pct: float = 0.2,
        methods: Optional[List[str]] = None,
    ) -> List[BacktestResult]:
        """Backtest each method using holdout validation."""
        if len(historical_values) < 6:
            return [BacktestResult(method=m, holdout_periods=0, mape=0, mae=0, rmse=0)
                    for m in (methods or list(_METHODS.keys()))]

        n = len(historical_values)
        holdout_n = max(1, int(n * holdout_pct))
        train = historical_values[:n - holdout_n]
        actual = historical_values[n - holdout_n:]

        use_methods = methods or list(_METHODS.keys())
        results = []

        for method_name in use_methods:
            if method_name not in _METHODS:
                continue
            func = _METHODS[method_name]
            try:
                predicted = func(train, holdout_n)
            except Exception as e:
                logger.warning("Backtest %s failed: %s", method_name, e)
                results.append(BacktestResult(method=method_name, holdout_periods=holdout_n))
                continue

            # Compute error metrics
            errors = []
            predictions_log = []
            for i in range(min(len(actual), len(predicted))):
                a, p = actual[i], predicted[i]
                error = abs(a - p)
                error_pct = (error / abs(a) * 100) if a != 0 else 0.0
                errors.append((error, error_pct, (a - p) ** 2))
                predictions_log.append({
                    "period": historical_periods[n - holdout_n + i] if i < len(historical_periods) - (n - holdout_n) else f"Holdout {i+1}",
                    "actual": round(a, 2),
                    "predicted": round(p, 2),
                    "error_pct": round(error_pct, 2),
                })

            # Filter out zero-actual for MAPE
            mape_vals = [ep for _, ep, _ in errors if ep > 0]
            mape = sum(mape_vals) / len(mape_vals) if mape_vals else 0.0
            mae = sum(e for e, _, _ in errors) / len(errors) if errors else 0.0
            rmse = math.sqrt(sum(sq for _, _, sq in errors) / len(errors)) if errors else 0.0

            bt = BacktestResult(
                method=method_name,
                holdout_periods=holdout_n,
                mape=mape, mae=mae, rmse=rmse,
                predictions=predictions_log,
            )
            results.append(bt)
            self._accuracy_history.append(bt)

        return results

    def update_weights_from_backtest(
        self,
        backtest_results: List[BacktestResult],
    ) -> Dict[str, float]:
        """Update method weights based on backtest accuracy (inverse MAPE)."""
        valid = [(r.method, r.mape) for r in backtest_results if r.mape > 0]
        if not valid:
            return dict(self._weights)

        # Inverse MAPE weighting
        inv_mapes = [(m, 1.0 / mape) for m, mape in valid]
        total_inv = sum(im for _, im in inv_mapes)
        if total_inv > 0:
            new_weights = {m: im / total_inv for m, im in inv_mapes}
            self._weights.update(new_weights)
        return dict(self._weights)

    def accuracy_report(self) -> Dict[str, Any]:
        """Return historical accuracy metrics from all backtests."""
        if not self._accuracy_history:
            return {"total_backtests": 0, "methods": {}}

        by_method: Dict[str, List[BacktestResult]] = {}
        for bt in self._accuracy_history:
            by_method.setdefault(bt.method, []).append(bt)

        method_stats = {}
        for method, runs in by_method.items():
            avg_mape = sum(r.mape for r in runs) / len(runs)
            avg_mae = sum(r.mae for r in runs) / len(runs)
            avg_rmse = sum(r.rmse for r in runs) / len(runs)
            method_stats[method] = {
                "runs": len(runs),
                "avg_mape": round(avg_mape, 4),
                "avg_mae": round(avg_mae, 2),
                "avg_rmse": round(avg_rmse, 2),
                "current_weight": self._weights.get(method, 0),
            }

        return {
            "total_backtests": len(self._accuracy_history),
            "methods": method_stats,
        }


# Module singleton
forecast_ensemble = ForecastEnsemble()
