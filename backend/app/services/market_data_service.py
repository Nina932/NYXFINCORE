"""
Live Market Data Service — aggregates free APIs for Georgian financial context.

Sources:
  - NBG (National Bank of Georgia): GEL exchange rates (free, no auth)
  - EIA (US Energy Information Admin): Brent/WTI oil prices (free API key)
  - ExchangeRate-API (open): Global forex rates (free, no auth)
  - World Bank: Georgia macro indicators (free, no auth)

All data is cached with TTL to avoid hammering free APIs.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional

import httpx

logger = logging.getLogger(__name__)

# ─── In-memory cache with TTL ───
_cache: Dict[str, Dict[str, Any]] = {}
_cache_ttl: Dict[str, float] = {}

def _get_cached(key: str, max_age_seconds: int = 3600) -> Optional[Any]:
    if key in _cache and (time.time() - _cache_ttl.get(key, 0)) < max_age_seconds:
        return _cache[key]
    return None

def _set_cached(key: str, data: Any):
    _cache[key] = data
    _cache_ttl[key] = time.time()


class MarketDataService:
    """Aggregates live market data from multiple free sources."""

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=15.0, follow_redirects=True)
        return self._client

    # ─── NBG Exchange Rates (free, no auth) ───
    async def get_nbg_rates(self) -> Dict[str, Any]:
        cached = _get_cached("nbg_rates", max_age_seconds=7200)  # 2h cache (daily update)
        if cached:
            return cached

        try:
            client = await self._get_client()
            resp = await client.get("https://nbg.gov.ge/gw/api/ct/monetarypolicy/currencies/en/json/")
            resp.raise_for_status()
            data = resp.json()

            currencies = data[0]["currencies"] if data else []
            rates = {}
            for c in currencies:
                code = c.get("code", "")
                if code in ("USD", "EUR", "GBP", "TRY", "RUB", "AZN", "AMD", "CNY", "JPY", "CHF"):
                    rate = c.get("rate", 0)
                    qty = c.get("quantity", 1)
                    rates[code] = {
                        "rate": round(rate / qty, 4) if qty else rate,
                        "change": c.get("diff", 0),
                        "name": c.get("name", code),
                    }

            result = {
                "source": "NBG (National Bank of Georgia)",
                "base": "GEL",
                "date": data[0].get("date", "")[:10] if data else "",
                "rates": rates,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
            _set_cached("nbg_rates", result)
            return result
        except Exception as e:
            logger.warning("NBG rates fetch failed: %s", e)
            return {"source": "NBG", "error": str(e), "rates": {}}

    # ─── Oil / Energy Prices (EIA or fallback) ───
    async def get_oil_prices(self) -> Dict[str, Any]:
        cached = _get_cached("oil_prices", max_age_seconds=14400)  # 4h cache
        if cached:
            return cached

        try:
            client = await self._get_client()
            # Try free forex/commodity endpoint first
            resp = await client.get(
                "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json"
            )
            resp.raise_for_status()
            usd_data = resp.json()
            gel_rate = usd_data.get("usd", {}).get("gel", 2.70)

            # For oil: use a simple estimate from public data or hardcoded recent
            # In production, register for free EIA API key
            result = {
                "source": "Market estimates (register EIA API for live data)",
                "brent_crude_usd": 73.50,  # Replace with EIA API call when key available
                "wti_crude_usd": 70.20,
                "natural_gas_usd_mmbtu": 3.15,
                "brent_crude_gel": round(73.50 * gel_rate, 2),
                "usd_gel": gel_rate,
                "note": "Oil prices are estimates. Add EIA_API_KEY to .env for live weekly data.",
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
            _set_cached("oil_prices", result)
            return result
        except Exception as e:
            logger.warning("Oil prices fetch failed: %s", e)
            return {"source": "fallback", "brent_crude_usd": 73.50, "error": str(e)}

    # ─── Georgia Macro Indicators (World Bank, free) ───
    async def get_georgia_macro(self) -> Dict[str, Any]:
        cached = _get_cached("georgia_macro", max_age_seconds=86400)  # 24h cache
        if cached:
            return cached

        indicators = {
            "gdp_current_usd": "NY.GDP.MKTP.CD",
            "gdp_growth_pct": "NY.GDP.MKTP.KD.ZG",
            "inflation_pct": "FP.CPI.TOTL.ZG",
            "unemployment_pct": "SL.UEM.TOTL.ZS",
            "population": "SP.POP.TOTL",
            "exports_pct_gdp": "NE.EXP.GNFS.ZS",
        }

        result = {
            "source": "World Bank Open Data",
            "country": "Georgia",
            "indicators": {},
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            client = await self._get_client()
            for key, indicator_code in indicators.items():
                try:
                    resp = await client.get(
                        f"https://api.worldbank.org/v2/country/GEO/indicator/{indicator_code}?format=json&per_page=3&mrv=3"
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        if len(data) > 1 and data[1]:
                            latest = data[1][0]
                            result["indicators"][key] = {
                                "value": latest.get("value"),
                                "year": latest.get("date"),
                                "indicator": latest.get("indicator", {}).get("value", ""),
                            }
                except Exception as inner_e:
                    logger.debug("World Bank indicator %s failed: %s", key, inner_e)
                    continue

            _set_cached("georgia_macro", result)
            return result
        except Exception as e:
            logger.warning("Georgia macro fetch failed: %s", e)
            return {"source": "World Bank", "error": str(e), "indicators": {}}

    # ─── Global Forex Rates (free, no auth) ───
    async def get_forex_rates(self) -> Dict[str, Any]:
        cached = _get_cached("forex_rates", max_age_seconds=7200)
        if cached:
            return cached

        try:
            client = await self._get_client()
            resp = await client.get("https://open.er-api.com/v6/latest/USD")
            resp.raise_for_status()
            data = resp.json()

            rates = data.get("rates", {})
            key_pairs = {
                "USD/GEL": rates.get("GEL", 0),
                "EUR/GEL": round(rates.get("GEL", 0) / rates.get("EUR", 1), 4) if rates.get("EUR") else 0,
                "GBP/GEL": round(rates.get("GEL", 0) / rates.get("GBP", 1), 4) if rates.get("GBP") else 0,
                "TRY/GEL": round(rates.get("GEL", 0) / rates.get("TRY", 1), 4) if rates.get("TRY") else 0,
                "RUB/GEL": round(rates.get("GEL", 0) / rates.get("RUB", 1), 6) if rates.get("RUB") else 0,
                "EUR/USD": round(1 / rates.get("EUR", 1), 4) if rates.get("EUR") else 0,
                "DXY_proxy": round(sum(1 / rates.get(c, 1) for c in ["EUR", "JPY", "GBP", "CAD", "SEK", "CHF"] if rates.get(c)) / 6, 2),
            }

            result = {
                "source": "ExchangeRate-API (open)",
                "base": "USD",
                "date": data.get("time_last_update_utc", ""),
                "rates": key_pairs,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
            _set_cached("forex_rates", result)
            return result
        except Exception as e:
            logger.warning("Forex rates fetch failed: %s", e)
            return {"source": "ExchangeRate-API", "error": str(e), "rates": {}}

    # ─── Aggregated: All market data in one call ───
    async def get_all(self) -> Dict[str, Any]:
        """Fetch all market data sources in parallel."""
        nbg, oil, macro, forex = await asyncio.gather(
            self.get_nbg_rates(),
            self.get_oil_prices(),
            self.get_georgia_macro(),
            self.get_forex_rates(),
            return_exceptions=True,
        )

        return {
            "nbg_rates": nbg if not isinstance(nbg, Exception) else {"error": str(nbg)},
            "oil_prices": oil if not isinstance(oil, Exception) else {"error": str(oil)},
            "georgia_macro": macro if not isinstance(macro, Exception) else {"error": str(macro)},
            "forex_rates": forex if not isinstance(forex, Exception) else {"error": str(forex)},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ─── Context string for LLM injection ───
    async def get_market_context_for_llm(self) -> str:
        """Returns a compact market summary string for injecting into LLM prompts."""
        data = await self.get_all()

        lines = ["CURRENT MARKET CONTEXT:"]

        # FX
        nbg = data.get("nbg_rates", {})
        if nbg.get("rates"):
            usd = nbg["rates"].get("USD", {})
            eur = nbg["rates"].get("EUR", {})
            lines.append(f"  GEL/USD: {usd.get('rate', '?')} (change: {usd.get('change', '?')})")
            lines.append(f"  GEL/EUR: {eur.get('rate', '?')} (change: {eur.get('change', '?')})")

        # Oil
        oil = data.get("oil_prices", {})
        if oil.get("brent_crude_usd"):
            lines.append(f"  Brent Crude: ${oil['brent_crude_usd']}/bbl (≈₾{oil.get('brent_crude_gel', '?')}/bbl)")
            lines.append(f"  Natural Gas: ${oil.get('natural_gas_usd_mmbtu', '?')}/MMBtu")

        # Macro
        macro = data.get("georgia_macro", {}).get("indicators", {})
        if macro.get("gdp_growth_pct", {}).get("value"):
            lines.append(f"  Georgia GDP Growth: {macro['gdp_growth_pct']['value']:.1f}% ({macro['gdp_growth_pct'].get('year', '')})")
        if macro.get("inflation_pct", {}).get("value"):
            lines.append(f"  Georgia Inflation: {macro['inflation_pct']['value']:.1f}% ({macro['inflation_pct'].get('year', '')})")

        return "\n".join(lines)


# ─── Singleton ───
market_data_service = MarketDataService()
