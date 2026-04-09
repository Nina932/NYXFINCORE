"""
forecasting.py -- Financial Forecasting Engine for NYX Core Thinker.

Provides multi-method time-series forecasting and trend analysis across
revenue, COGS, gross margin, and G&A expense data stored across multiple
dataset periods.

Methods supported:
  - Moving Average (rolling window)
  - Exponential Smoothing (SES with dampening)
  - Linear Regression (numpy polyfit)
  - Growth Rate (CAGR-based projection)
  - Seasonal Decomposition (additive: Trend + Seasonal + Residual)
  - Auto-select (picks best method based on data characteristics)

All forecasts include confidence intervals and are persisted to the
Forecast table for audit trail and dashboard consumption.
"""

import math
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple

import numpy as np
import pandas as pd

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.all_models import Dataset, RevenueItem, COGSItem, GAExpenseItem, Forecast

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# MONTH ORDERING HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

_MONTH_ORDER = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}


def _period_sort_key(period: str) -> Tuple[int, int]:
    """
    Convert a period string like 'January 2025' to a sortable (year, month)
    tuple. Falls back to (0, 0) for unrecognised formats.
    """
    try:
        parts = period.strip().split()
        if len(parts) == 2:
            month_num = _MONTH_ORDER.get(parts[0].lower(), 0)
            year_num = int(parts[1])
            return (year_num, month_num)
    except (ValueError, IndexError):
        pass
    return (0, 0)


def _next_period_label(last_period: str, steps_ahead: int) -> str:
    """
    Generate a future period label given the last known period.
    E.g. 'November 2025' + 2 -> 'January 2026'.
    """
    year, month = _period_sort_key(last_period)
    if year == 0:
        return f"Period +{steps_ahead}"
    month_names = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ]
    total_months = (year * 12 + month - 1) + steps_ahead
    new_year = total_months // 12
    new_month = total_months % 12  # 0-indexed
    return f"{month_names[new_month]} {new_year}"


# ═══════════════════════════════════════════════════════════════════════════════
# FORECAST ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class ForecastEngine:
    """
    Multi-method forecasting engine for fuel distribution financial data.

    Supports moving average, exponential smoothing, linear regression,
    CAGR-based growth rate projection, and additive seasonal decomposition.
    Each method returns confidence intervals and can be persisted to the DB.
    """

    # Monthly seasonal indices by fuel product for NYX Core Thinker.
    # Heating diesel peaks in winter; gasoline peaks in summer; bitumen peaks
    # in construction season (May-Sep).
    FUEL_SEASONAL_INDICES = {
        1:  {"diesel": 1.15, "petrol": 0.85, "cng": 0.95, "lpg": 1.10, "bitumen": 0.60},
        2:  {"diesel": 1.12, "petrol": 0.87, "cng": 0.95, "lpg": 1.08, "bitumen": 0.65},
        3:  {"diesel": 1.05, "petrol": 0.92, "cng": 1.00, "lpg": 1.02, "bitumen": 0.80},
        4:  {"diesel": 0.95, "petrol": 1.00, "cng": 1.02, "lpg": 0.98, "bitumen": 1.00},
        5:  {"diesel": 0.88, "petrol": 1.08, "cng": 1.05, "lpg": 0.95, "bitumen": 1.15},
        6:  {"diesel": 0.82, "petrol": 1.15, "cng": 1.08, "lpg": 0.90, "bitumen": 1.20},
        7:  {"diesel": 0.80, "petrol": 1.18, "cng": 1.10, "lpg": 0.88, "bitumen": 1.25},
        8:  {"diesel": 0.82, "petrol": 1.15, "cng": 1.08, "lpg": 0.90, "bitumen": 1.20},
        9:  {"diesel": 0.90, "petrol": 1.05, "cng": 1.02, "lpg": 0.95, "bitumen": 1.10},
        10: {"diesel": 1.05, "petrol": 0.95, "cng": 0.98, "lpg": 1.02, "bitumen": 0.85},
        11: {"diesel": 1.12, "petrol": 0.88, "cng": 0.95, "lpg": 1.08, "bitumen": 0.70},
        12: {"diesel": 1.18, "petrol": 0.83, "cng": 0.92, "lpg": 1.12, "bitumen": 0.55},
    }

    # ------------------------------------------------------------------
    # 1. Moving Average
    # ------------------------------------------------------------------

    @staticmethod
    def moving_average(
        data: List[float],
        periods: int = 6,
        window: int = 3,
    ) -> Dict:
        """
        Forecast using a rolling-window moving average.

        The last ``window`` observations are averaged to produce each future
        point.  Confidence bands are set at +/-1.5 standard deviations of
        the most recent window.

        Args:
            data: Historical time-series values (chronological order).
            periods: Number of future periods to forecast.
            window: Rolling window size.

        Returns:
            Dict with method name, forecast values, and confidence level.
        """
        if not data:
            return {"method": "moving_average", "values": [], "confidence": "low", "error": "No data provided"}

        # Handle single-data-point case
        if len(data) == 1:
            return ForecastEngine._single_point_forecast(data, periods, "moving_average")

        series = pd.Series(data)
        effective_window = min(window, len(data))
        rolling_mean = series.rolling(window=effective_window, min_periods=1).mean()

        # Base forecast = last rolling mean value
        base_value = float(rolling_mean.iloc[-1])

        # Confidence band width from recent volatility
        recent = data[-effective_window:]
        std = float(np.std(recent, ddof=1)) if len(recent) > 1 else abs(base_value) * 0.1
        band = 1.5 * std

        forecast_values = []
        for i in range(1, periods + 1):
            forecast_values.append({
                "period": i,
                "value": round(base_value, 2),
                "lower": round(base_value - band * math.sqrt(i), 2),
                "upper": round(base_value + band * math.sqrt(i), 2),
            })

        return {
            "method": "moving_average",
            "values": forecast_values,
            "confidence": "moderate",
            "parameters": {"window": effective_window},
        }

    # ------------------------------------------------------------------
    # 2. Exponential Smoothing (Simple)
    # ------------------------------------------------------------------

    @staticmethod
    def exponential_smoothing(
        data: List[float],
        periods: int = 6,
        alpha: float = 0.3,
    ) -> Dict:
        """
        Simple Exponential Smoothing (SES) with slight dampening.

        S_t = alpha * Y_t + (1 - alpha) * S_{t-1}

        Forecast equals the last smoothed level with progressive dampening
        for further horizons.  Confidence intervals widen with
        residual_std * sqrt(horizon).

        Args:
            data: Historical time-series values.
            periods: Forecast horizon.
            alpha: Smoothing factor in (0, 1).

        Returns:
            Dict with method, forecast values, and confidence metadata.
        """
        if not data:
            return {"method": "exponential_smoothing", "values": [], "confidence": "low", "error": "No data provided"}

        if len(data) == 1:
            return ForecastEngine._single_point_forecast(data, periods, "exponential_smoothing")

        alpha = max(0.01, min(alpha, 0.99))

        # Compute smoothed series
        smoothed = [data[0]]
        for t in range(1, len(data)):
            s = alpha * data[t] + (1 - alpha) * smoothed[-1]
            smoothed.append(s)

        last_smooth = smoothed[-1]

        # Residuals for CI
        residuals = [data[t] - smoothed[t] for t in range(len(data))]
        residual_std = float(np.std(residuals, ddof=1)) if len(residuals) > 1 else abs(last_smooth) * 0.1

        # Dampening factor: slight decay for distant horizons
        dampening = 0.98

        forecast_values = []
        for h in range(1, periods + 1):
            projected = last_smooth * (dampening ** h)
            ci = residual_std * math.sqrt(h)
            forecast_values.append({
                "period": h,
                "value": round(projected, 2),
                "lower": round(projected - 1.96 * ci, 2),
                "upper": round(projected + 1.96 * ci, 2),
            })

        return {
            "method": "exponential_smoothing",
            "values": forecast_values,
            "confidence": "moderate",
            "parameters": {"alpha": alpha, "dampening": dampening},
        }

    # ------------------------------------------------------------------
    # 3. Linear Regression
    # ------------------------------------------------------------------

    @staticmethod
    def linear_regression(
        data: List[float],
        periods: int = 6,
    ) -> Dict:
        """
        Ordinary least-squares linear trend extrapolation.

        Uses numpy.polyfit(x, y, deg=1) to fit a straight line, then
        projects forward.  Prediction intervals use the standard formula:

            CI = residual_std * sqrt(1 + 1/n + (x_pred - x_mean)^2 / SS_x)

        Args:
            data: Historical time-series values.
            periods: Number of future periods.

        Returns:
            Dict with method, forecast values, slope/intercept, and R-squared.
        """
        if not data:
            return {"method": "linear_regression", "values": [], "confidence": "low", "error": "No data provided"}

        if len(data) == 1:
            return ForecastEngine._single_point_forecast(data, periods, "linear_regression")

        n = len(data)
        x = np.arange(n, dtype=float)
        y = np.array(data, dtype=float)

        # Fit
        coeffs = np.polyfit(x, y, deg=1)
        slope, intercept = float(coeffs[0]), float(coeffs[1])

        # Fitted values and residuals
        y_fit = slope * x + intercept
        residuals = y - y_fit
        residual_std = float(np.std(residuals, ddof=2)) if n > 2 else float(np.std(residuals, ddof=1)) if n > 1 else abs(y[0]) * 0.1

        x_mean = float(np.mean(x))
        ss_x = float(np.sum((x - x_mean) ** 2))

        # R-squared
        ss_res = float(np.sum(residuals ** 2))
        ss_tot = float(np.sum((y - np.mean(y)) ** 2))
        r_squared = round(1 - ss_res / ss_tot, 4) if ss_tot > 0 else 0.0

        forecast_values = []
        for h in range(1, periods + 1):
            x_pred = n - 1 + h
            predicted = slope * x_pred + intercept
            # Prediction interval
            ci_factor = math.sqrt(1 + 1 / n + (x_pred - x_mean) ** 2 / ss_x) if ss_x > 0 else 1.0
            ci = 1.96 * residual_std * ci_factor
            forecast_values.append({
                "period": h,
                "value": round(predicted, 2),
                "lower": round(predicted - ci, 2),
                "upper": round(predicted + ci, 2),
            })

        confidence = "high" if abs(r_squared) > 0.7 else "moderate" if abs(r_squared) > 0.4 else "low"

        return {
            "method": "linear_regression",
            "values": forecast_values,
            "confidence": confidence,
            "parameters": {
                "slope": round(slope, 4),
                "intercept": round(intercept, 2),
                "r_squared": r_squared,
            },
        }

    # ------------------------------------------------------------------
    # 4. Growth Rate (CAGR)
    # ------------------------------------------------------------------

    @staticmethod
    def growth_rate(
        data: List[float],
        periods: int = 6,
        rate: float = None,
    ) -> Dict:
        """
        Compound Annual Growth Rate projection.

        If ``rate`` is not provided, computes CAGR from the first and last
        data points:  CAGR = (last / first)^(1/n) - 1.

        Projects forward as: last_value * (1 + rate)^h.

        Confidence intervals widen proportionally with the forecast horizon.

        Args:
            data: Historical time-series values.
            periods: Forecast horizon.
            rate: Optional explicit growth rate (e.g. 0.05 for 5%).

        Returns:
            Dict with method, forecast values, computed CAGR, and confidence.
        """
        if not data:
            return {"method": "growth_rate", "values": [], "confidence": "low", "error": "No data provided"}

        if len(data) == 1:
            return ForecastEngine._single_point_forecast(data, periods, "growth_rate")

        last_value = data[-1]
        first_value = data[0]
        n = len(data) - 1  # number of growth intervals

        # Compute CAGR if rate not explicitly given
        if rate is None:
            if first_value != 0 and last_value != 0 and n > 0:
                ratio = abs(last_value / first_value)
                sign = 1 if last_value / first_value > 0 else -1
                rate = sign * (ratio ** (1.0 / n)) - 1
            else:
                rate = 0.0

        # Clamp extreme rates for safety
        rate = max(-0.5, min(rate, 2.0))

        # Historical growth rates for volatility estimation
        growth_rates = []
        for i in range(1, len(data)):
            if data[i - 1] != 0:
                growth_rates.append((data[i] - data[i - 1]) / abs(data[i - 1]))
        growth_std = float(np.std(growth_rates)) if growth_rates else abs(rate) * 0.5

        forecast_values = []
        for h in range(1, periods + 1):
            projected = last_value * ((1 + rate) ** h)
            # CI widens with horizon
            ci = abs(projected) * growth_std * math.sqrt(h)
            forecast_values.append({
                "period": h,
                "value": round(projected, 2),
                "lower": round(projected - 1.96 * ci, 2),
                "upper": round(projected + 1.96 * ci, 2),
            })

        return {
            "method": "growth_rate",
            "values": forecast_values,
            "confidence": "moderate" if abs(rate) < 0.3 else "low",
            "parameters": {
                "cagr": round(rate, 4),
                "cagr_pct": round(rate * 100, 2),
                "base_value": round(last_value, 2),
            },
        }

    # ------------------------------------------------------------------
    # 5. Seasonal Decomposition (Additive)
    # ------------------------------------------------------------------

    @staticmethod
    def seasonal_decompose(
        data: List[float],
        labels: List[str] = None,
        season_length: int = 12,
    ) -> Dict:
        """
        Additive seasonal decomposition: Y = Trend + Seasonal + Residual.

        Trend is estimated via a centered moving average of width
        ``season_length``.  Seasonal component is the average of detrended
        values for each position in the season.

        Requires at least ``season_length`` data points.  Forecast extends
        by repeating the seasonal pattern on top of the projected trend.

        Args:
            data: Historical time-series values.
            labels: Optional period labels for the data.
            season_length: Length of one seasonal cycle (default 12 months).

        Returns:
            Dict with trend, seasonal indices, residual stats, and
            forecast values for the next season_length periods.
        """
        if not data:
            return {"method": "seasonal_decompose", "values": [], "confidence": "low", "error": "No data provided"}

        n = len(data)
        if n < season_length:
            # Fall back to linear regression when insufficient data for decomposition
            logger.warning(
                "Seasonal decomposition requires >= %d data points (got %d). "
                "Falling back to linear regression.",
                season_length, n,
            )
            return ForecastEngine.linear_regression(data, periods=season_length)

        y = np.array(data, dtype=float)

        # -- Trend via centered moving average --
        trend = np.full(n, np.nan)
        half = season_length // 2
        for i in range(half, n - half):
            window_vals = y[max(0, i - half): i + half + 1]
            trend[i] = np.mean(window_vals)

        # Fill edges with nearest valid trend
        first_valid = None
        last_valid = None
        for i in range(n):
            if not np.isnan(trend[i]):
                if first_valid is None:
                    first_valid = i
                last_valid = i
        if first_valid is not None:
            trend[:first_valid] = trend[first_valid]
            trend[last_valid + 1:] = trend[last_valid]

        # -- Seasonal component --
        detrended = y - trend
        seasonal = np.zeros(season_length)
        for s in range(season_length):
            positions = [i for i in range(s, n, season_length)]
            vals = [detrended[i] for i in positions if not np.isnan(detrended[i])]
            seasonal[s] = float(np.mean(vals)) if vals else 0.0

        # Normalise so seasonal sums to zero (additive)
        seasonal -= np.mean(seasonal)

        # -- Residual --
        seasonal_full = np.array([seasonal[i % season_length] for i in range(n)])
        residual = y - trend - seasonal_full
        residual_std = float(np.std(residual[~np.isnan(residual)])) if np.any(~np.isnan(residual)) else 0.0

        # -- Forecast: project trend + repeat seasonal pattern --
        # Trend projection via linear fit on the trend component
        valid_mask = ~np.isnan(trend)
        x_valid = np.arange(n)[valid_mask]
        trend_valid = trend[valid_mask]
        if len(x_valid) >= 2:
            t_coeffs = np.polyfit(x_valid, trend_valid, deg=1)
            t_slope, t_intercept = float(t_coeffs[0]), float(t_coeffs[1])
        else:
            t_slope, t_intercept = 0.0, float(trend_valid[0]) if len(trend_valid) > 0 else float(y[0])

        forecast_periods = season_length
        forecast_values = []
        for h in range(1, forecast_periods + 1):
            x_pred = n - 1 + h
            trend_pred = t_slope * x_pred + t_intercept
            season_idx = (n - 1 + h) % season_length
            predicted = trend_pred + seasonal[season_idx]
            ci = 1.96 * residual_std * math.sqrt(h / season_length + 1)
            forecast_values.append({
                "period": h,
                "value": round(predicted, 2),
                "lower": round(predicted - ci, 2),
                "upper": round(predicted + ci, 2),
            })

        return {
            "method": "seasonal_decompose",
            "values": forecast_values,
            "confidence": "high" if n >= 2 * season_length else "moderate",
            "trend": [round(float(t), 2) if not np.isnan(t) else None for t in trend],
            "seasonal": [round(float(s), 2) for s in seasonal],
            "residual_std": round(residual_std, 2),
            "parameters": {"season_length": season_length},
        }

    # ------------------------------------------------------------------
    # 6. Auto-Select Method
    # ------------------------------------------------------------------

    @staticmethod
    def auto_select_method(data: List[float]) -> str:
        """
        Heuristically select the best forecasting method based on data
        length and characteristics.

        Decision tree:
          - < 3 points  -> growth_rate (minimal data)
          - < 6 points  -> exponential_smoothing
          - < 12 points -> linear_regression
          - >= 12 pts   -> seasonal_decompose if seasonal pattern detected,
                           otherwise linear_regression

        Seasonal detection: compute autocorrelation at lag 12; if
        |r(12)| > 0.3 the data is considered seasonal.

        Args:
            data: Historical time-series values.

        Returns:
            Method name string suitable for dispatch.
        """
        n = len(data)
        if n < 3:
            return "growth_rate"
        if n < 6:
            return "exponential_smoothing"
        if n < 12:
            return "linear_regression"

        # Seasonal detection via autocorrelation at lag 12
        try:
            y = np.array(data, dtype=float)
            y_demean = y - np.mean(y)
            var = float(np.sum(y_demean ** 2))
            if var > 0:
                lag = 12
                if n > lag:
                    autocorr = float(np.sum(y_demean[:n - lag] * y_demean[lag:])) / var
                    if abs(autocorr) > 0.3:
                        return "seasonal_decompose"
        except Exception:
            pass

        return "linear_regression"

    # ------------------------------------------------------------------
    # 7. Generate Forecast (async DB entry point)
    # ------------------------------------------------------------------

    async def generate_forecast(
        self,
        db: AsyncSession,
        forecast_type: str,
        product: str = None,
        segment: str = None,
        method: str = "auto",
        periods: int = 6,
    ) -> Dict:
        """
        Main entry point: gather historical data from all datasets,
        run the chosen forecasting method, persist the result, and return
        a complete forecast dictionary.

        Supported forecast_type values:
          - 'revenue'     : sums RevenueItem.net grouped by dataset period
          - 'cogs'        : sums COGSItem.total_cogs grouped by dataset period
          - 'margin'      : revenue minus cogs per period
          - 'ga_expenses' : sums GAExpenseItem.amount grouped by dataset period

        Args:
            db: Async SQLAlchemy session.
            forecast_type: One of revenue / cogs / margin / ga_expenses.
            product: Optional product filter.
            segment: Optional segment filter.
            method: Forecasting method or 'auto'.
            periods: Forecast horizon.

        Returns:
            Dict with historical data, forecast result, metadata, and
            the persisted Forecast record id.
        """
        try:
            logger.info(
                "Generating %s forecast | method=%s periods=%d product=%s segment=%s",
                forecast_type, method, periods, product, segment,
            )

            # ── Step 1: Gather historical data ─────────────────────────
            historical_data, period_labels = await self._gather_historical(
                db, forecast_type, product, segment,
            )

            if not historical_data:
                return {
                    "success": False,
                    "error": f"No historical data found for forecast_type='{forecast_type}'",
                    "forecast_type": forecast_type,
                    "product": product,
                    "segment": segment,
                }

            # ── Step 2: Select method ─────────────────────────────────
            if method == "auto":
                method = self.auto_select_method(historical_data)
                logger.info("Auto-selected method: %s (n=%d)", method, len(historical_data))

            # ── Step 3: Run forecast ──────────────────────────────────
            result = self._dispatch_method(method, historical_data, periods, period_labels)

            # ── Step 4: Attach period labels to forecast values ───────
            if period_labels and result.get("values"):
                last_label = period_labels[-1]
                for fv in result["values"]:
                    fv["period_label"] = _next_period_label(last_label, fv["period"])

            # ── Step 5: Persist to DB ─────────────────────────────────
            forecast_record = Forecast(
                forecast_type=forecast_type,
                product=product,
                segment=segment,
                method=method,
                period_start=period_labels[0] if period_labels else None,
                period_end=period_labels[-1] if period_labels else None,
                periods=periods,
                values=result.get("values"),
                confidence_interval=0.95,
                parameters=result.get("parameters"),
                input_data=[round(v, 2) for v in historical_data],
            )
            db.add(forecast_record)
            await db.flush()

            logger.info(
                "Forecast saved: id=%s method=%s periods=%d",
                forecast_record.id, method, periods,
            )

            return {
                "success": True,
                "forecast_id": forecast_record.id,
                "forecast_type": forecast_type,
                "product": product,
                "segment": segment,
                "method": method,
                "periods": periods,
                "historical_periods": period_labels,
                "historical_values": [round(v, 2) for v in historical_data],
                "data_points": len(historical_data),
                "result": result,
                "generated_at": datetime.utcnow().isoformat(),
            }

        except Exception as exc:
            logger.exception("Forecast generation failed: %s", exc)
            return {
                "success": False,
                "error": str(exc),
                "forecast_type": forecast_type,
                "method": method,
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _gather_historical(
        self,
        db: AsyncSession,
        forecast_type: str,
        product: Optional[str],
        segment: Optional[str],
    ) -> Tuple[List[float], List[str]]:
        """
        Query all datasets ordered by period and aggregate the requested
        metric per period.

        Returns:
            Tuple of (values_list, period_labels_list) both in
            chronological order.
        """
        # Get all datasets ordered by period
        ds_result = await db.execute(
            select(Dataset.id, Dataset.period)
            .order_by(Dataset.period)
        )
        datasets = ds_result.all()

        if not datasets:
            return [], []

        # Sort datasets chronologically
        datasets = sorted(datasets, key=lambda d: _period_sort_key(d.period))

        if forecast_type == "margin":
            # Need both revenue and cogs per period
            rev_data, rev_labels = await self._gather_historical(db, "revenue", product, segment)
            cogs_data, cogs_labels = await self._gather_historical(db, "cogs", product, segment)

            # Align periods
            rev_map = dict(zip(rev_labels, rev_data))
            cogs_map = dict(zip(cogs_labels, cogs_data))
            all_periods = sorted(
                set(rev_labels) | set(cogs_labels),
                key=_period_sort_key,
            )
            margin_values = []
            margin_labels = []
            for p in all_periods:
                r = rev_map.get(p, 0.0)
                c = cogs_map.get(p, 0.0)
                margin_values.append(r - c)
                margin_labels.append(p)
            return margin_values, margin_labels

        # Build per-period aggregation for revenue / cogs / ga_expenses
        period_values: Dict[str, float] = {}

        for ds_id, ds_period in datasets:
            value = await self._query_period_value(
                db, ds_id, forecast_type, product, segment,
            )
            if value is not None:
                period_values[ds_period] = period_values.get(ds_period, 0.0) + value

        # Sort chronologically
        sorted_periods = sorted(period_values.keys(), key=_period_sort_key)
        values = [period_values[p] for p in sorted_periods]
        return values, sorted_periods

    async def _query_period_value(
        self,
        db: AsyncSession,
        dataset_id: int,
        forecast_type: str,
        product: Optional[str],
        segment: Optional[str],
    ) -> Optional[float]:
        """
        Query the aggregate value for one dataset period.
        """
        if forecast_type == "revenue":
            q = select(func.sum(RevenueItem.net)).where(
                RevenueItem.dataset_id == dataset_id
            )
            if product:
                q = q.where(RevenueItem.product.ilike(f"%{product}%"))
            if segment:
                q = q.where(RevenueItem.segment.ilike(f"%{segment}%"))
            result = await db.execute(q)
            return result.scalar()

        elif forecast_type == "cogs":
            q = select(func.sum(COGSItem.total_cogs)).where(
                COGSItem.dataset_id == dataset_id
            )
            if product:
                q = q.where(COGSItem.product.ilike(f"%{product}%"))
            if segment:
                q = q.where(COGSItem.segment.ilike(f"%{segment}%"))
            result = await db.execute(q)
            return result.scalar()

        elif forecast_type == "ga_expenses":
            q = select(func.sum(GAExpenseItem.amount)).where(
                GAExpenseItem.dataset_id == dataset_id
            )
            result = await db.execute(q)
            return result.scalar()

        else:
            logger.warning("Unknown forecast_type: %s", forecast_type)
            return None

    def _dispatch_method(
        self,
        method: str,
        data: List[float],
        periods: int,
        labels: List[str] = None,
    ) -> Dict:
        """Dispatch to the appropriate forecasting method."""
        dispatch = {
            "moving_average": lambda: self.moving_average(data, periods),
            "exponential_smoothing": lambda: self.exponential_smoothing(data, periods),
            "linear_regression": lambda: self.linear_regression(data, periods),
            "growth_rate": lambda: self.growth_rate(data, periods),
            "seasonal_decompose": lambda: self.seasonal_decompose(data, labels, season_length=12),
        }
        fn = dispatch.get(method)
        if fn is None:
            logger.warning("Unknown method '%s', falling back to linear_regression", method)
            return self.linear_regression(data, periods)
        return fn()

    @staticmethod
    def _single_point_forecast(
        data: List[float],
        periods: int,
        method_name: str,
    ) -> Dict:
        """
        Handle the edge case where only a single historical data point
        exists.  Uses baseline projection with wide +/-25 % confidence
        intervals and an explanatory note.
        """
        base = data[0]
        band_pct = 0.25
        forecast_values = []
        for h in range(1, periods + 1):
            band = abs(base) * band_pct * math.sqrt(h)
            forecast_values.append({
                "period": h,
                "value": round(base, 2),
                "lower": round(base - band, 2),
                "upper": round(base + band, 2),
            })

        return {
            "method": method_name,
            "values": forecast_values,
            "confidence": "low",
            "parameters": {"baseline": round(base, 2)},
            "note": (
                "Limited data: only 1 period available. Forecast uses "
                "baseline projection with wide confidence intervals."
            ),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# TREND ANALYZER
# ═══════════════════════════════════════════════════════════════════════════════

class TrendAnalyzer:
    """
    Analyses historical financial trends across multiple dataset periods.

    Computes period-over-period changes, CAGR, volatility, and provides a
    human-readable directional summary for dashboards and AI-agent
    consumption.
    """

    async def analyze_trends(
        self,
        db: AsyncSession,
        metric: str = "revenue",
        segment: str = None,
        product: str = None,
    ) -> Dict:
        """
        Analyse trends for the given metric across all available datasets.

        For each consecutive pair of periods, computes both absolute and
        percentage change.  Aggregate statistics include CAGR, average
        growth, and volatility.  The overall direction is classified as
        'growing', 'declining', 'stable', or 'volatile'.

        Args:
            db: Async SQLAlchemy session.
            metric: One of 'revenue', 'cogs', 'margin', 'ga_expenses'.
            segment: Optional segment filter.
            product: Optional product filter.

        Returns:
            Dict with periods, changes, aggregate stats, direction,
            and a human-readable summary string.
        """
        try:
            engine = ForecastEngine()
            values, labels = await engine._gather_historical(
                db, metric, product, segment,
            )

            if not values:
                return {
                    "metric": metric,
                    "segment": segment,
                    "product": product,
                    "error": f"No data found for metric='{metric}'",
                    "periods": [],
                    "changes": [],
                    "direction": "unknown",
                    "summary": f"No historical data available for {metric} trend analysis.",
                }

            n = len(values)

            # ── Period-over-period changes ────────────────────────────
            changes = []
            growth_rates = []
            for i in range(1, n):
                abs_change = values[i] - values[i - 1]
                pct_change = (abs_change / abs(values[i - 1]) * 100) if values[i - 1] != 0 else 0.0
                growth_rates.append(pct_change / 100)
                changes.append({
                    "from_period": labels[i - 1],
                    "to_period": labels[i],
                    "from_value": round(values[i - 1], 2),
                    "to_value": round(values[i], 2),
                    "absolute_change": round(abs_change, 2),
                    "pct_change": round(pct_change, 2),
                })

            # ── CAGR ─────────────────────────────────────────────────
            cagr = None
            if n >= 2 and values[0] != 0 and values[-1] != 0:
                ratio = abs(values[-1] / values[0])
                sign = 1 if values[-1] / values[0] > 0 else -1
                cagr = round((sign * (ratio ** (1.0 / (n - 1))) - 1) * 100, 2)

            # ── Average growth rate ──────────────────────────────────
            avg_growth = round(float(np.mean(growth_rates)) * 100, 2) if growth_rates else 0.0

            # ── Volatility (std of growth rates) ─────────────────────
            volatility = round(float(np.std(growth_rates, ddof=1)) * 100, 2) if len(growth_rates) > 1 else 0.0

            # ── Direction classification ─────────────────────────────
            direction = self._classify_direction(growth_rates, volatility / 100)

            # ── Top growing / declining items ────────────────────────
            top_growing = []
            top_declining = []
            if product is None and segment is None:
                # Attempt product-level breakdown
                top_growing, top_declining = await self._product_breakdown(
                    db, metric, labels,
                )

            # ── Build periods list ───────────────────────────────────
            periods_list = [
                {"period": labels[i], "value": round(values[i], 2)}
                for i in range(n)
            ]

            # ── Human-readable summary ───────────────────────────────
            summary = self._build_summary(
                metric, direction, n, labels, values, cagr, avg_growth, volatility,
            )

            return {
                "metric": metric,
                "segment": segment,
                "product": product,
                "periods": periods_list,
                "changes": changes,
                "cagr": cagr,
                "avg_growth": avg_growth,
                "volatility": volatility,
                "direction": direction,
                "top_growing": top_growing,
                "top_declining": top_declining,
                "data_points": n,
                "summary": summary,
            }

        except Exception as exc:
            logger.exception("Trend analysis failed: %s", exc)
            return {
                "metric": metric,
                "error": str(exc),
                "direction": "unknown",
                "summary": f"Trend analysis failed: {exc}",
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _classify_direction(
        growth_rates: List[float],
        volatility: float,
    ) -> str:
        """
        Classify the overall trend direction.

        Rules:
          - volatility > 15 %            -> 'volatile'
          - avg growth >  2 %            -> 'growing'
          - avg growth < -2 %            -> 'declining'
          - otherwise                    -> 'stable'
        """
        if not growth_rates:
            return "stable"

        avg = float(np.mean(growth_rates))

        if volatility > 0.15:
            return "volatile"
        if avg > 0.02:
            return "growing"
        if avg < -0.02:
            return "declining"
        return "stable"

    async def _product_breakdown(
        self,
        db: AsyncSession,
        metric: str,
        period_labels: List[str],
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Find top growing and top declining products/items across periods.
        Compares earliest vs latest period to compute total growth.

        Returns (top_growing, top_declining) lists of up to 5 items each.
        """
        if len(period_labels) < 2:
            return [], []

        first_period = period_labels[0]
        last_period = period_labels[-1]

        # Get datasets for first and last period
        first_ds = await db.execute(
            select(Dataset.id).where(Dataset.period == first_period)
        )
        last_ds = await db.execute(
            select(Dataset.id).where(Dataset.period == last_period)
        )
        first_ids = [r[0] for r in first_ds.all()]
        last_ids = [r[0] for r in last_ds.all()]

        if not first_ids or not last_ids:
            return [], []

        if metric == "revenue":
            model = RevenueItem
            amount_col = RevenueItem.net
            name_col = RevenueItem.product
        elif metric == "cogs":
            model = COGSItem
            amount_col = COGSItem.total_cogs
            name_col = COGSItem.product
        else:
            return [], []

        # Aggregate per product in first period
        q_first = (
            select(name_col, func.sum(amount_col))
            .where(model.dataset_id.in_(first_ids))
            .group_by(name_col)
        )
        first_result = await db.execute(q_first)
        first_map = {r[0]: float(r[1] or 0) for r in first_result.all()}

        # Aggregate per product in last period
        q_last = (
            select(name_col, func.sum(amount_col))
            .where(model.dataset_id.in_(last_ids))
            .group_by(name_col)
        )
        last_result = await db.execute(q_last)
        last_map = {r[0]: float(r[1] or 0) for r in last_result.all()}

        # Compute growth per product
        all_products = set(first_map.keys()) | set(last_map.keys())
        product_growth = []
        for p in all_products:
            v_first = first_map.get(p, 0)
            v_last = last_map.get(p, 0)
            abs_change = v_last - v_first
            pct_change = (abs_change / abs(v_first) * 100) if v_first != 0 else 0.0
            product_growth.append({
                "product": p,
                "first_value": round(v_first, 2),
                "last_value": round(v_last, 2),
                "absolute_change": round(abs_change, 2),
                "pct_change": round(pct_change, 2),
            })

        # Sort
        product_growth.sort(key=lambda x: x["pct_change"], reverse=True)
        top_growing = [g for g in product_growth if g["pct_change"] > 0][:5]
        top_declining = [g for g in product_growth if g["pct_change"] < 0]
        top_declining.sort(key=lambda x: x["pct_change"])
        top_declining = top_declining[:5]

        return top_growing, top_declining

    @staticmethod
    def _build_summary(
        metric: str,
        direction: str,
        n: int,
        labels: List[str],
        values: List[float],
        cagr: Optional[float],
        avg_growth: float,
        volatility: float,
    ) -> str:
        """
        Build a concise human-readable trend summary suitable for
        dashboard display or AI agent context.
        """
        metric_display = metric.replace("_", " ").title()
        first_label = labels[0] if labels else "start"
        last_label = labels[-1] if labels else "end"
        first_val = round(values[0], 2) if values else 0
        last_val = round(values[-1], 2) if values else 0

        direction_text = {
            "growing": "an upward trend",
            "declining": "a downward trend",
            "stable": "relative stability",
            "volatile": "high volatility",
        }.get(direction, "no clear trend")

        parts = [
            f"{metric_display} shows {direction_text} across {n} period(s) "
            f"from {first_label} to {last_label}.",
        ]

        if n >= 2:
            overall_change = last_val - first_val
            overall_pct = (overall_change / abs(first_val) * 100) if first_val != 0 else 0
            change_word = "increased" if overall_change >= 0 else "decreased"
            parts.append(
                f"Overall {change_word} by {abs(round(overall_pct, 1))}% "
                f"({round(abs(overall_change), 2):,.2f} in absolute terms)."
            )

        if cagr is not None:
            parts.append(f"CAGR: {cagr}%.")

        parts.append(f"Average period growth: {avg_growth}%. Volatility: {volatility}%.")

        return " ".join(parts)
