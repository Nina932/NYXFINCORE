"""
external_data_router.py — Live market data endpoints for FinAI.

Exposes the ExternalDataService through the API so the frontend
and agents can request market context with data provenance info.

All responses include a `data_quality` field:
  "live"        — fetched from a real external API right now
  "live_eia"    — fetched from EIA API v2 right now
  "cached"      — served from in-memory cache (within TTL)
  "estimated"   — representative values; no real-time source exists
  "synthetic"   — EIA API key not configured; representative data
  "unavailable" — external API was called but failed

Endpoints:
  GET /api/external-data/exchange-rates     — NBG official rates (live)
  GET /api/external-data/commodities        — Brent/WTI crude (live)
  GET /api/external-data/market-indices     — GSE + S&P500 (live)
  GET /api/external-data/fuel-prices        — Company pump prices (estimated)
  GET /api/external-data/competitors        — Competitor prices (estimated)
  GET /api/external-data/economic-indicators — Macro indicators (estimated)
  GET /api/external-data/full-context       — All of the above in one call
  POST /api/external-data/fuel-prices       — Manual update of pump prices
  GET /api/external-data/eia/petroleum-report — EIA Weekly Petroleum Report
  GET /api/external-data/eia/prices          — EIA price data (WTI, nat gas)
  GET /api/external-data/eia/inventories     — Crude stocks + SPR levels
  GET /api/external-data/situational-risk    — Risk intelligence (+ EIA supply data)
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Body
from pydantic import BaseModel

from app.auth import get_optional_user
from app.config import settings
from app.services.external_data import ExternalDataService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/external-data", tags=["external-data"])


def _serialise(obj: Any) -> Any:
    """Convert Decimal/datetime objects for JSON serialisation."""
    from decimal import Decimal
    from datetime import datetime
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _serialise(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialise(i) for i in obj]
    return obj


@router.get("/exchange-rates", summary="NBG official exchange rates (live)")
async def exchange_rates(user=Depends(get_optional_user)):
    """
    Fetch live exchange rates from the National Bank of Georgia.
    USD/GEL, EUR/GEL, RUB/GEL and all other NBG-published currencies.
    """
    async with ExternalDataService() as svc:
        data = await svc.get_bank_exchange_rates()
    return _serialise(data)


@router.get("/commodities", summary="Commodity prices — Brent/WTI crude (live)")
async def commodities(user=Depends(get_optional_user)):
    """Brent Crude, WTI Crude, and Natural Gas prices from Yahoo Finance."""
    async with ExternalDataService() as svc:
        data = await svc.get_commodity_prices()
    return _serialise(data)


@router.get("/market-indices", summary="Georgian and international market indices")
async def market_indices(user=Depends(get_optional_user)):
    """GSE index (best-effort live) + S&P 500 + Brent Crude via Yahoo Finance."""
    async with ExternalDataService() as svc:
        data = await svc.get_market_indices()
    return _serialise(data)


@router.get("/fuel-prices", summary=f"{settings.COMPANY_NAME} pump prices (estimated)")
async def fuel_prices(user=Depends(get_optional_user)):
    f"""
    Representative {settings.COMPANY_NAME} pump prices.

    Note: No public API exists. Prices reflect recent public price boards.
    Use POST /api/external-data/fuel-prices to manually update these values.
    """
    async with ExternalDataService() as svc:
        data = await svc.get_nyx_fuel_prices()
    return _serialise(data)


@router.get("/competitors", summary="Competitor fuel prices (estimated)")
async def competitor_prices(user=Depends(get_optional_user)):
    """
    Rompetrol, Lukoil, Wissol, and Gulf representative prices.
    Based on Georgian Competition Agency filings and press monitoring.
    """
    async with ExternalDataService() as svc:
        data = await svc.get_competitor_pricing()
    return _serialise(data)


@router.get("/economic-indicators", summary="Georgian macro indicators (estimated)")
async def economic_indicators(user=Depends(get_optional_user)):
    """
    GDP growth, inflation, unemployment, NBG policy rate.
    Source: Geostat and NBG publications (quarterly cadence).
    """
    async with ExternalDataService() as svc:
        data = await svc.get_economic_indicators()
    return _serialise(data)


@router.get("/full-context", summary="All market data in one call")
async def full_context(user=Depends(get_optional_user)):
    """
    Combined: exchange rates + commodities + economic indicators + fuel prices.
    Used by InsightAgent for enriched financial analysis context.
    The `sources` sub-dict shows data_quality per section.
    """
    async with ExternalDataService() as svc:
        data = await svc.get_full_market_context()
    return _serialise(data)


@router.get("/situational-risk", summary="Real-time risk intelligence for map overlays")
async def situational_risk(user=Depends(get_optional_user)):
    try:
        from app.services.risk_intelligence import risk_engine
        data = await risk_engine.get_situational_risk()

        # Merge EIA supply data into supply_fundamentals section
        try:
            from app.services.eia_client import eia_client
            eia_supply = await eia_client.get_supply_summary_for_risk()
            if isinstance(data.get("supply_fundamentals"), dict):
                data["supply_fundamentals"].update(eia_supply)
            else:
                data["supply_fundamentals"] = eia_supply
        except Exception as exc:
            logger.debug("EIA supply merge into risk failed: %s", exc)

        return _serialise(data)
    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}


# =========================================================================
# EIA (Energy Information Administration) ENDPOINTS
# =========================================================================

@router.get("/eia/petroleum-report", summary="EIA Weekly Petroleum Status Report")
async def eia_petroleum_report(user=Depends(get_optional_user)):
    """
    Full weekly petroleum report from the U.S. Energy Information Administration.

    Includes crude oil stocks, production, imports, refinery utilization,
    WTI spot price, and a supply/demand balance assessment.

    Data quality is 'live_eia' when EIA_API_KEY is configured and the API
    responds, or 'synthetic' with representative fallback data otherwise.
    """
    from app.services.eia_client import eia_client
    data = await eia_client.get_weekly_petroleum_report()
    return _serialise(data)


@router.get("/eia/prices", summary="EIA energy prices (WTI crude + natural gas)")
async def eia_prices(user=Depends(get_optional_user)):
    """
    EIA price data: WTI crude oil spot price and Henry Hub natural gas spot price.
    Includes 4-week trend analysis for each commodity.
    """
    from app.services.eia_client import eia_client

    crude = await eia_client.get_crude_oil_prices()
    natgas = await eia_client.get_natural_gas_prices()

    combined = {
        "crude_oil": crude,
        "natural_gas": natgas,
        "timestamp": crude.get("timestamp") or natgas.get("timestamp"),
        "data_quality": crude.get("data_quality", "synthetic"),
        "source": "U.S. Energy Information Administration (EIA)",
    }
    return _serialise(combined)


@router.get("/eia/inventories", summary="Crude oil inventories + SPR levels")
async def eia_inventories(user=Depends(get_optional_user)):
    """
    U.S. commercial crude oil inventories and Strategic Petroleum Reserve levels.
    Includes total stocks, days-of-supply estimate, and 4-week trend.
    """
    from app.services.eia_client import eia_client
    data = await eia_client.get_inventory_levels()
    return _serialise(data)


@router.get("/logistics/benchmark", summary="Deep comparison between two major operators")
async def benchmark_competitors(target_a: str, target_b: str, user=Depends(get_optional_user)):
    """
    Compares two competitors (e.g., SOCAR vs Rompetrol) on sourcing, 
    logistics margins, and supply resilience.
    """
    try:
        from app.services.logistics_intelligence_service import logistics_intelligence
        data = await logistics_intelligence.benchmark_competitors(target_a, target_b)
        return _serialise(data)
    except Exception as e:
        return {"error": str(e)}

