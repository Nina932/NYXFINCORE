"""
eia_client.py --- EIA (Energy Information Administration) API v2 client.

Provides access to U.S. petroleum supply/demand data, crude oil prices,
natural gas prices, and inventory levels from the EIA Weekly Petroleum
Status Report.

DATA PROVENANCE:
  "live_eia"   --- fetched from EIA API v2 in this request
  "cached"     --- served from in-memory cache (within 1-hour TTL)
  "synthetic"  --- no API key configured; returning representative data

EIA API v2 docs: https://www.eia.gov/opendata/documentation.php

Series IDs used:
  PET.WCESTUS1.W  --- Weekly U.S. Ending Stocks of Crude Oil (thousand barrels)
  PET.RWTC.W      --- Weekly Cushing OK WTI Spot Price ($/barrel)
  PET.WCRFPUS2.W  --- Weekly U.S. Field Production of Crude Oil (thousand bbl/d)
  PET.WCRIMUS2.W  --- Weekly U.S. Imports of Crude Oil (thousand bbl/d)
  PET.WPULEUS3.W  --- Weekly Percent Utilization of Refinery Capacity
  NG.RNGWHHD.W    --- Weekly Henry Hub Natural Gas Spot Price ($/MMBtu)
  PET.WCSSTUS1.W  --- Weekly U.S. SPR Stocks of Crude Oil (thousand barrels)

Usage:
    from app.services.eia_client import eia_client
    report = await eia_client.get_weekly_petroleum_report()
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_EIA_BASE_URL = "https://api.eia.gov/v2/"

# EIA series IDs for the Weekly Petroleum Status Report
_SERIES = {
    "crude_stocks":         "PET.WCESTUS1.W",
    "wti_spot":             "PET.RWTC.W",
    "production":           "PET.WCRFPUS2.W",
    "imports":              "PET.WCRIMUS2.W",
    "refinery_utilization": "PET.WPULEUS3.W",
    "natural_gas":          "NG.RNGWHHD.W",
    "spr_stocks":           "PET.WCSSTUS1.W",
}

# Synthetic fallback data when API key is missing or API fails
_SYNTHETIC_DATA = {
    "crude_stocks": {
        "series_id": "PET.WCESTUS1.W",
        "description": "U.S. Ending Stocks of Crude Oil (Thousand Barrels)",
        "latest_value": 440200.0,
        "previous_value": 441800.0,
        "weekly_change": -1600.0,
        "unit": "Thousand Barrels",
        "period": "2026-03-27",
    },
    "wti_spot": {
        "series_id": "PET.RWTC.W",
        "description": "Cushing OK WTI Spot Price FOB",
        "latest_value": 79.50,
        "previous_value": 78.80,
        "weekly_change": 0.70,
        "unit": "Dollars per Barrel",
        "period": "2026-03-27",
    },
    "production": {
        "series_id": "PET.WCRFPUS2.W",
        "description": "U.S. Field Production of Crude Oil",
        "latest_value": 13200.0,
        "previous_value": 13150.0,
        "weekly_change": 50.0,
        "unit": "Thousand Barrels per Day",
        "period": "2026-03-27",
    },
    "imports": {
        "series_id": "PET.WCRIMUS2.W",
        "description": "U.S. Imports of Crude Oil",
        "latest_value": 6450.0,
        "previous_value": 6380.0,
        "weekly_change": 70.0,
        "unit": "Thousand Barrels per Day",
        "period": "2026-03-27",
    },
    "refinery_utilization": {
        "series_id": "PET.WPULEUS3.W",
        "description": "Percent Utilization of Refinery Operable Capacity",
        "latest_value": 87.6,
        "previous_value": 87.2,
        "weekly_change": 0.4,
        "unit": "Percent",
        "period": "2026-03-27",
    },
    "natural_gas": {
        "series_id": "NG.RNGWHHD.W",
        "description": "Henry Hub Natural Gas Spot Price",
        "latest_value": 2.15,
        "previous_value": 2.08,
        "weekly_change": 0.07,
        "unit": "Dollars per Million Btu",
        "period": "2026-03-27",
    },
    "spr_stocks": {
        "series_id": "PET.WCSSTUS1.W",
        "description": "U.S. Strategic Petroleum Reserve Stocks",
        "latest_value": 395500.0,
        "previous_value": 395500.0,
        "weekly_change": 0.0,
        "unit": "Thousand Barrels",
        "period": "2026-03-27",
    },
}


class EIAClient:
    """
    Async client for the U.S. Energy Information Administration (EIA) API v2.

    Provides petroleum market data from the Weekly Petroleum Status Report.
    When EIA_API_KEY is not set, returns synthetic fallback data with
    data_quality='synthetic' so downstream consumers can still function.
    """

    def __init__(self):
        self._api_key: str = os.environ.get("EIA_API_KEY", "")
        self._client: Optional[httpx.AsyncClient] = None
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = 3600  # 1 hour (EIA data updates weekly)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=20.0,
                headers={"User-Agent": "FinAI/3.0 EIA-Client"},
                follow_redirects=True,
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    def _get_valid_cache(self, key: str) -> Optional[Dict[str, Any]]:
        entry = self._cache.get(key)
        if not entry:
            return None
        cached_at = entry.get("_cached_at")
        if cached_at and isinstance(cached_at, datetime):
            if (datetime.now() - cached_at).total_seconds() < self._cache_ttl:
                return entry
        return None

    def _set_cache(self, key: str, data: Dict[str, Any]) -> None:
        self._cache[key] = {**data, "_cached_at": datetime.now()}

    # ------------------------------------------------------------------
    # Core EIA API fetcher
    # ------------------------------------------------------------------

    async def _fetch_series(self, series_id: str, num_points: int = 4) -> Optional[List[Dict]]:
        """
        Fetch data points for a given EIA series ID.

        EIA v2 API pattern:
            GET https://api.eia.gov/v2/seriesid/{SERIES_ID}
            ?api_key={KEY}&num={N}

        Returns list of {period, value} dicts sorted newest-first,
        or None if the request fails.
        """
        if not self._api_key:
            return None

        client = await self._get_client()
        try:
            url = f"{_EIA_BASE_URL}seriesid/{series_id}"
            params = {
                "api_key": self._api_key,
                "num": str(num_points),
            }
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            payload = resp.json()

            # EIA v2 response structure:
            # { "response": { "data": [ { "period": "2026-03-27", "value": 440200 }, ... ] } }
            records = payload.get("response", {}).get("data", [])
            if records:
                return records

            # Fallback: some series use "series" key
            series_data = payload.get("series", [{}])
            if series_data and isinstance(series_data, list):
                data_points = series_data[0].get("data", [])
                if data_points:
                    # Convert [["2026-03-27", 440200], ...] to [{period, value}]
                    return [{"period": dp[0], "value": dp[1]} for dp in data_points]

            return None
        except Exception as exc:
            logger.debug("EIA series %s fetch failed: %s", series_id, exc)
            return None

    def _build_series_result(self, key: str, records: Optional[List[Dict]]) -> Dict[str, Any]:
        """
        Build a standardized result dict from EIA records.
        Falls back to synthetic data if records is None.
        """
        synthetic = _SYNTHETIC_DATA[key]

        if records is None or len(records) < 1:
            return {**synthetic, "data_quality": "synthetic"}

        # Extract latest and previous values
        latest = records[0]
        latest_val = float(latest.get("value", 0))
        period = latest.get("period", "")

        prev_val = None
        if len(records) >= 2:
            prev_val = float(records[1].get("value", 0))

        weekly_change = (latest_val - prev_val) if prev_val is not None else 0.0

        return {
            "series_id": synthetic["series_id"],
            "description": synthetic["description"],
            "latest_value": round(latest_val, 2),
            "previous_value": round(prev_val, 2) if prev_val is not None else None,
            "weekly_change": round(weekly_change, 2),
            "unit": synthetic["unit"],
            "period": period,
            "data_quality": "live_eia",
        }

    # ------------------------------------------------------------------
    # PUBLIC METHODS
    # ------------------------------------------------------------------

    async def get_weekly_petroleum_report(self) -> Dict[str, Any]:
        """
        Full Weekly Petroleum Status Report summary.

        Returns crude oil stocks, production, imports, refinery utilization,
        and supply balance indicators.
        """
        cache_key = "petroleum_report"
        cached = self._get_valid_cache(cache_key)
        if cached:
            return {**cached, "data_quality": "cached"}

        # Fetch all relevant series
        stocks_data = await self._fetch_series(_SERIES["crude_stocks"])
        prod_data = await self._fetch_series(_SERIES["production"])
        import_data = await self._fetch_series(_SERIES["imports"])
        util_data = await self._fetch_series(_SERIES["refinery_utilization"])
        wti_data = await self._fetch_series(_SERIES["wti_spot"])

        stocks = self._build_series_result("crude_stocks", stocks_data)
        production = self._build_series_result("production", prod_data)
        imports = self._build_series_result("imports", import_data)
        utilization = self._build_series_result("refinery_utilization", util_data)
        wti = self._build_series_result("wti_spot", wti_data)

        # Compute supply/demand balance interpretation
        stock_change = stocks.get("weekly_change", 0)
        if stock_change < -5000:
            supply_signal = "SIGNIFICANT_DRAW"
            interpretation = f"Major inventory draw ({abs(stock_change)/1000:.1f}M bbl) --- supply tightening, bullish for prices"
        elif stock_change < -1000:
            supply_signal = "DRAW"
            interpretation = f"Inventory draw ({abs(stock_change)/1000:.1f}M bbl) --- mild supply tightening"
        elif stock_change > 5000:
            supply_signal = "SIGNIFICANT_BUILD"
            interpretation = f"Major inventory build ({stock_change/1000:.1f}M bbl) --- oversupply, bearish for prices"
        elif stock_change > 1000:
            supply_signal = "BUILD"
            interpretation = f"Inventory build ({stock_change/1000:.1f}M bbl) --- supply comfortable"
        else:
            supply_signal = "FLAT"
            interpretation = "Inventories roughly flat --- balanced supply/demand"

        any_live = any(
            v.get("data_quality") == "live_eia"
            for v in [stocks, production, imports, utilization, wti]
        )

        result = {
            "crude_stocks": stocks,
            "production": production,
            "imports": imports,
            "refinery_utilization": utilization,
            "wti_price": wti,
            "supply_signal": supply_signal,
            "interpretation": interpretation,
            "timestamp": datetime.now().isoformat(),
            "data_quality": "live_eia" if any_live else "synthetic",
            "source": "U.S. Energy Information Administration (EIA)",
        }

        self._set_cache(cache_key, result)
        return result

    async def get_crude_oil_prices(self) -> Dict[str, Any]:
        """
        WTI spot prices from EIA (Cushing OK WTI Spot Price FOB).
        """
        cache_key = "eia_crude_prices"
        cached = self._get_valid_cache(cache_key)
        if cached:
            return {**cached, "data_quality": "cached"}

        wti_data = await self._fetch_series(_SERIES["wti_spot"], num_points=8)
        wti = self._build_series_result("wti_spot", wti_data)

        # Compute 4-week trend if enough data
        trend = "stable"
        trend_points: List[float] = []
        if wti_data and len(wti_data) >= 4:
            trend_points = [float(r.get("value", 0)) for r in wti_data[:4]]
            if trend_points[0] > trend_points[-1] * 1.05:
                trend = "rising"
            elif trend_points[0] < trend_points[-1] * 0.95:
                trend = "falling"

        result = {
            "wti_spot": wti,
            "trend_4w": trend,
            "recent_prices": trend_points,
            "timestamp": datetime.now().isoformat(),
            "data_quality": wti.get("data_quality", "synthetic"),
            "source": "EIA --- Weekly Cushing OK WTI Spot Price",
        }

        self._set_cache(cache_key, result)
        return result

    async def get_natural_gas_prices(self) -> Dict[str, Any]:
        """
        Henry Hub Natural Gas Spot Price from EIA.
        """
        cache_key = "eia_natgas_prices"
        cached = self._get_valid_cache(cache_key)
        if cached:
            return {**cached, "data_quality": "cached"}

        ng_data = await self._fetch_series(_SERIES["natural_gas"], num_points=8)
        ng = self._build_series_result("natural_gas", ng_data)

        trend = "stable"
        trend_points: List[float] = []
        if ng_data and len(ng_data) >= 4:
            trend_points = [float(r.get("value", 0)) for r in ng_data[:4]]
            if trend_points[0] > trend_points[-1] * 1.10:
                trend = "rising"
            elif trend_points[0] < trend_points[-1] * 0.90:
                trend = "falling"

        result = {
            "henry_hub": ng,
            "trend_4w": trend,
            "recent_prices": trend_points,
            "timestamp": datetime.now().isoformat(),
            "data_quality": ng.get("data_quality", "synthetic"),
            "source": "EIA --- Weekly Henry Hub Natural Gas Spot Price",
        }

        self._set_cache(cache_key, result)
        return result

    async def get_petroleum_supply(self) -> Dict[str, Any]:
        """
        Weekly supply/demand balance: production, imports, stocks, utilization.
        """
        cache_key = "eia_supply"
        cached = self._get_valid_cache(cache_key)
        if cached:
            return {**cached, "data_quality": "cached"}

        stocks_data = await self._fetch_series(_SERIES["crude_stocks"])
        prod_data = await self._fetch_series(_SERIES["production"])
        import_data = await self._fetch_series(_SERIES["imports"])
        util_data = await self._fetch_series(_SERIES["refinery_utilization"])

        stocks = self._build_series_result("crude_stocks", stocks_data)
        production = self._build_series_result("production", prod_data)
        imports = self._build_series_result("imports", import_data)
        utilization = self._build_series_result("refinery_utilization", util_data)

        # Supply adequacy assessment
        stock_change = stocks.get("weekly_change", 0)
        util_pct = utilization.get("latest_value", 87.0)

        if stock_change < -3000 and util_pct > 92:
            balance = "TIGHT"
            balance_note = "High refinery runs drawing down inventories --- tight supply"
        elif stock_change > 3000 and util_pct < 85:
            balance = "LOOSE"
            balance_note = "Low refinery demand + inventory builds --- ample supply"
        elif stock_change < -1000:
            balance = "SLIGHTLY_TIGHT"
            balance_note = "Moderate inventory draws --- supply slightly constrained"
        elif stock_change > 1000:
            balance = "SLIGHTLY_LOOSE"
            balance_note = "Moderate inventory builds --- supply adequate"
        else:
            balance = "BALANCED"
            balance_note = "Inventories stable --- supply and demand in equilibrium"

        any_live = any(
            v.get("data_quality") == "live_eia"
            for v in [stocks, production, imports, utilization]
        )

        result = {
            "crude_stocks": stocks,
            "production": production,
            "imports": imports,
            "refinery_utilization": utilization,
            "supply_balance": balance,
            "balance_note": balance_note,
            "timestamp": datetime.now().isoformat(),
            "data_quality": "live_eia" if any_live else "synthetic",
            "source": "U.S. Energy Information Administration (EIA)",
        }

        self._set_cache(cache_key, result)
        return result

    async def get_inventory_levels(self) -> Dict[str, Any]:
        """
        Commercial crude oil inventories + Strategic Petroleum Reserve levels.
        """
        cache_key = "eia_inventories"
        cached = self._get_valid_cache(cache_key)
        if cached:
            return {**cached, "data_quality": "cached"}

        stocks_data = await self._fetch_series(_SERIES["crude_stocks"], num_points=8)
        spr_data = await self._fetch_series(_SERIES["spr_stocks"], num_points=8)

        commercial = self._build_series_result("crude_stocks", stocks_data)
        spr = self._build_series_result("spr_stocks", spr_data)

        # Compute commercial stock trends
        comm_trend = "stable"
        comm_trend_points: List[float] = []
        if stocks_data and len(stocks_data) >= 4:
            comm_trend_points = [float(r.get("value", 0)) for r in stocks_data[:4]]
            if comm_trend_points[0] < comm_trend_points[-1] * 0.98:
                comm_trend = "drawing"
            elif comm_trend_points[0] > comm_trend_points[-1] * 1.02:
                comm_trend = "building"

        # Total petroleum stocks (commercial + SPR)
        commercial_val = commercial.get("latest_value", 0)
        spr_val = spr.get("latest_value", 0)
        total_stocks = commercial_val + spr_val

        # Days of supply estimate (rough: total stocks / daily consumption ~20M bbl/d)
        daily_consumption_est = 20000.0  # thousand barrels/day
        days_of_supply = round(total_stocks / daily_consumption_est, 1) if daily_consumption_est > 0 else 0

        any_live = any(
            v.get("data_quality") == "live_eia"
            for v in [commercial, spr]
        )

        result = {
            "commercial_crude": commercial,
            "strategic_petroleum_reserve": spr,
            "total_stocks_k_bbl": round(total_stocks, 0),
            "days_of_supply_est": days_of_supply,
            "commercial_trend_4w": comm_trend,
            "commercial_recent_k_bbl": comm_trend_points,
            "timestamp": datetime.now().isoformat(),
            "data_quality": "live_eia" if any_live else "synthetic",
            "source": "U.S. Energy Information Administration (EIA)",
        }

        self._set_cache(cache_key, result)
        return result

    async def get_supply_summary_for_risk(self) -> Dict[str, Any]:
        """
        Compact supply summary designed for merging into the situational-risk
        endpoint's supply_fundamentals section. Returns key EIA metrics
        alongside the existing crude stock data.
        """
        cache_key = "eia_risk_supply"
        cached = self._get_valid_cache(cache_key)
        if cached:
            return {**cached, "data_quality": "cached"}

        stocks_data = await self._fetch_series(_SERIES["crude_stocks"])
        prod_data = await self._fetch_series(_SERIES["production"])
        util_data = await self._fetch_series(_SERIES["refinery_utilization"])
        spr_data = await self._fetch_series(_SERIES["spr_stocks"])
        wti_data = await self._fetch_series(_SERIES["wti_spot"])

        stocks = self._build_series_result("crude_stocks", stocks_data)
        production = self._build_series_result("production", prod_data)
        utilization = self._build_series_result("refinery_utilization", util_data)
        spr = self._build_series_result("spr_stocks", spr_data)
        wti = self._build_series_result("wti_spot", wti_data)

        any_live = any(
            v.get("data_quality") == "live_eia"
            for v in [stocks, production, utilization, spr, wti]
        )

        result = {
            "eia_crude_stocks_k_bbl": stocks.get("latest_value"),
            "eia_stock_change_k_bbl": stocks.get("weekly_change"),
            "eia_production_k_bpd": production.get("latest_value"),
            "eia_refinery_utilization_pct": utilization.get("latest_value"),
            "eia_spr_stocks_k_bbl": spr.get("latest_value"),
            "eia_wti_spot_usd": wti.get("latest_value"),
            "eia_period": stocks.get("period") or production.get("period", ""),
            "eia_data_quality": "live_eia" if any_live else "synthetic",
            "eia_source": "U.S. Energy Information Administration (EIA)",
        }

        self._set_cache(cache_key, result)
        return result


# ---------------------------------------------------------------------------
# Module singleton
# ---------------------------------------------------------------------------
eia_client = EIAClient()
