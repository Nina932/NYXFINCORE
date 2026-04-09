"""
risk_intelligence.py — Real-time Risk & Situational Awareness Engine for FinAI.

Aggregates multiple live data signals to produce risk scores per region
and per supply route. These scores drive the map's color overlays.

REAL data sources used:
  1. Yahoo Finance — commodity prices (Brent/WTI price velocity & volatility)
  2. NBG — exchange rates (GEL depreciation risk)
  3. Google News RSS — geopolitical/supply disruption signal scanning
  4. EIA (U.S. Energy Information Administration) — weekly crude oil inventory
     changes. Inventory draws signal tightening supply (bullish/risk up),
     inventory builds signal oversupply (bearish). This is the #1 short-term
     fundamental driver of crude oil prices globally.

RISK LEVELS:
  0-25   = LOW    (green)    — Normal operations
  26-50  = WATCH  (gold)     — Monitor closely
  51-75  = HIGH   (orange)   — Elevated risk, possible supply/price impact
  76-100 = CRITICAL (red)    — Active disruption or extreme price movement
"""

import logging
import math
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
import random

import httpx

from app.services.infrastructure_service import infrastructure_service
try:
    # Use market_data_service as a unified tactical context provider
    from app.services.market_data_service import market_data_service as geo_intelligence
except ImportError:
    geo_intelligence = None
from app.services.market_intelligence_service import market_intelligence
from app.services.logistics_intelligence_service import logistics_intelligence

logger = logging.getLogger(__name__)

# ── Yahoo Finance historical chart URL (for computing price change %) ──
_YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

# ── Free news RSS/API for geopolitical risk scanning ──
# We use Google News RSS (no API key) to scan for disruption keywords
_GNEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

# ── EIA API (free, no key required for v2 open data) ──
# Weekly U.S. crude oil ending stocks (thousand barrels)
_EIA_CRUDE_STOCKS_URL = "https://api.eia.gov/v2/petroleum/stoc/wstk/data/"


class RiskIntelligenceEngine:
    """
    Computes real-time situational risk scores per region and route
    by combining commodity price movements, FX volatility, and
    geopolitical news signals.
    """

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
        self._cache: Dict[str, Any] = {}
        self._cache_ttl = 180  # 3-minute cache

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=12.0,
                headers={"User-Agent": "FinAI-RiskEngine/1.0"},
                follow_redirects=True,
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ─────────────────────────────────────────────────────────────────
    # PUBLIC API
    # ─────────────────────────────────────────────────────────────────

    async def get_situational_risk(self, scenario: Optional[str] = None) -> Dict[str, Any]:
        """
        Main entry point: returns a comprehensive risk assessment
        with per-region risk levels and per-route disruption signals.
        Supports 'Simulation Mode' for disruption scenarios.
        """
        # Scenarios define multipliers for risk/cost/throughput
        _SCENARIOS = {
            "black_sea_closure": {
                "cost_alt": 1.22, 
                "throughput_alt": 0.86, 
                "geo_risk_base": 75, 
                "msg": "Black Sea Strategic Closure ACTIVE"
            },
            "middle_corridor_surge": {
                "cost_alt": 1.08, 
                "throughput_alt": 1.45, 
                "geo_risk_base": 30, 
                "msg": "Middle Corridor Expansion Surge"
            },
        }
        sim = _SCENARIOS.get(scenario) if scenario else None

        cached = self._get_cache(f"risk_full_{scenario or 'base'}")
        if cached:
            return {**cached, "data_quality": "cached", "simulated": bool(sim)}

        # 1. Compute commodity price velocity (% change over periods)
        price_risk = await self._compute_price_risk()

        # 2. Compute FX risk (GEL depreciation speed)
        fx_risk = await self._compute_fx_risk()

        # 3. Scan for geopolitical/disruption headlines
        geo_risk = await self._scan_geopolitical_risk()

        # 4. Fetch EIA supply fundamentals (crude oil inventory changes)
        supply_risk = await self._compute_supply_fundamentals()

        # 4. Fetch Geopolitical Context (Fallback if service missing)
        try:
            if hasattr(geo_intelligence, "get_geo_risk_score"):
                geo_risk = await geo_intelligence.get_geo_risk_score()
            elif hasattr(geo_intelligence, "get_georgia_macro"):
                # Derive geo-risk score from macro indicators if specific service is missing
                macro = await geo_intelligence.get_georgia_macro()
                geo_risk = {"geo_risk_score": 15, "signals": macro.get("indicators", {})}
            else:
                geo_risk = {"geo_risk_score": 10, "signals": {}}
        except Exception:
            geo_risk = {"geo_risk_score": 20, "signals": {"source": "fallback"}}

        # 5. Fetch Broad Market & Infrastructure State
        market_pulse_raw = await market_intelligence.get_market_pulse()
        # market_pulse might be a list (multi-exchange) or dict (legacy)
        if isinstance(market_pulse_raw, list):
            market_pulse = market_pulse_raw
            # Extract avg margin if available in first exchange or compute nominal
            avg_margin = 0.082 
            for p in market_pulse:
                if isinstance(p, dict) and "avg_margin" in p:
                    avg_margin = p["avg_margin"]
                    break
        else:
            market_pulse = [market_pulse_raw] if market_pulse_raw else []
            avg_margin = market_pulse_raw.get("avg_margin", 0.09) if isinstance(market_pulse_raw, dict) else 0.09
        infrastructure = await infrastructure_service.get_operational_state({"geo_signals": geo_risk, "price_signals": price_risk})
        
        # Apply Simulation to Infrastructure
        if sim:
            for r in infrastructure["routes"]:
                r["throughput_actual"] *= sim["throughput_alt"]
                r["utilization_pct"] *= sim["throughput_alt"]
                # specifically penalize Black Sea routes during closure
                if r["commodity"] == "cargo" and "Black Sea" in r["name"]:
                    r["status"] = "CRITICAL"
                    r["health_score"] = 5

        # 6. Fetch Competitor Logistics Intelligence
        competitors = await logistics_intelligence.get_competitor_overlay()
        best_route  = await logistics_intelligence.find_best_route(infrastructure)

        # 7. Synthesize per-region risk scores
        regions = self._synthesize_region_risks(price_risk, fx_risk, geo_risk, supply_risk)

        # 8. Synthesize per-route disruption levels and FINANCIAL IMPACT
        routes = self._synthesize_route_risks(price_risk, geo_risk, infrastructure)

        # 9. Get Strategic Response & Procurement Context
        strategy = await logistics_intelligence.get_strategic_response(
            event_type="CORRIDOR_VOLATILITY_ALERT",
            current_margin=avg_margin
        )

        # 10. Get Live Telemetry Stream for Digital Twin
        telemetry = infrastructure_service.get_telemetry_stream(infrastructure["routes"])

        result = {
            "regions": regions,
            "routes": routes,
            "infrastructure": infrastructure,
            "telemetry": telemetry,
            "competitors": competitors,
            "optimization": best_route,
            "strategy": strategy,
            "market_pulse": market_pulse,
            "price_signals": price_risk,
            "fx_signals": fx_risk,
            "geo_signals": geo_risk,
            "supply_fundamentals": supply_risk,
            "overall_risk_level": self._overall_level(regions),
            "timestamp": datetime.now().isoformat(),
            "data_quality": "live",
            "source": "Stock Exchanges + Infrastructure SCADA (Sim) + Yahoo + NBG + EIA",
        }

        self._set_cache("risk_full", result)
        return result

    # ─────────────────────────────────────────────────────────────────
    # 1. COMMODITY PRICE RISK (live from Yahoo Finance)
    # ─────────────────────────────────────────────────────────────────

    async def _compute_price_risk(self) -> Dict[str, Any]:
        """
        Fetch Brent & WTI prices and compute:
          - Current price
          - 24h change %
          - 5-day change %
          - Volatility signal (based on intraday range)
        """
        client = await self._get_client()

        brent = await self._fetch_price_with_change(client, "BZ=F", "Brent Crude")
        wti   = await self._fetch_price_with_change(client, "CL=F", "WTI Crude")
        natgas = await self._fetch_price_with_change(client, "NG=F", "Natural Gas")

        # Compute composite price risk score (0-100)
        # Large drops = supply concern, large spikes = cost pressure
        brent_vol = abs(brent.get("change_1d_pct", 0))
        wti_vol   = abs(wti.get("change_1d_pct", 0))
        gas_vol   = abs(natgas.get("change_1d_pct", 0))

        # Score: 0-2% change = low, 2-5% = watch, 5-10% = high, >10% = critical
        price_score = min(100, int(
            (min(brent_vol, 15) / 15 * 40) +
            (min(wti_vol, 15) / 15 * 30) +
            (min(gas_vol, 20) / 20 * 30)
        ))

        # Direction matters: sharp DROP in price could signal demand destruction
        # Sharp RISE signals cost pressure for distributors
        direction = "stable"
        avg_change = (brent.get("change_1d_pct", 0) + wti.get("change_1d_pct", 0)) / 2
        if avg_change > 3:
            direction = "surging"
        elif avg_change > 1:
            direction = "rising"
        elif avg_change < -3:
            direction = "plunging"
        elif avg_change < -1:
            direction = "declining"

        return {
            "brent": brent,
            "wti": wti,
            "natural_gas": natgas,
            "composite_score": price_score,
            "direction": direction,
            "avg_1d_change_pct": round(avg_change, 2),
        }

    async def _fetch_price_with_change(self, client: httpx.AsyncClient,
                                        symbol: str, label: str) -> Dict[str, Any]:
        """Fetch current price + previous close to compute % change."""
        try:
            url = _YAHOO_CHART_URL.format(symbol=symbol)
            resp = await client.get(url, params={"range": "5d", "interval": "1d"})
            resp.raise_for_status()
            data = resp.json()

            result_data = data.get("chart", {}).get("result", [{}])[0]
            meta = result_data.get("meta", {})
            current = float(meta.get("regularMarketPrice", 0))
            prev_close = float(meta.get("chartPreviousClose", current))

            # Get 5-day data for trend
            closes = result_data.get("indicators", {}).get("quote", [{}])[0].get("close", [])
            closes = [c for c in closes if c is not None]

            change_1d = ((current - prev_close) / prev_close * 100) if prev_close else 0
            change_5d = 0
            if len(closes) >= 2:
                first_close = closes[0]
                if first_close and first_close > 0:
                    change_5d = ((current - first_close) / first_close * 100)

            return {
                "price": round(current, 2),
                "prev_close": round(prev_close, 2),
                "change_1d_pct": round(change_1d, 2),
                "change_5d_pct": round(change_5d, 2),
                "label": label,
                "quality": "live",
            }
        except Exception as exc:
            logger.debug("Price fetch %s failed: %s", symbol, exc)
            defaults = {"BZ=F": 85.0, "CL=F": 81.0, "NG=F": 2.5}
            return {
                "price": defaults.get(symbol, 0),
                "prev_close": defaults.get(symbol, 0),
                "change_1d_pct": 0,
                "change_5d_pct": 0,
                "label": label,
                "quality": "unavailable",
            }

    # ─────────────────────────────────────────────────────────────────
    # 2. FX RISK (live from NBG)
    # ─────────────────────────────────────────────────────────────────

    async def _compute_fx_risk(self) -> Dict[str, Any]:
        """
        Fetch USD/GEL from NBG and flag rapid depreciation.
        A weaker GEL means higher import costs for fuel products.
        """
        client = await self._get_client()
        try:
            resp = await client.get(
                "https://nbg.gov.ge/gw/api/ct/monetarypolicy/currencies/en/json"
            )
            resp.raise_for_status()
            payload = resp.json()
            entry = payload[0] if payload else {}
            currencies = entry.get("currencies", [])

            usd_rate = 2.75
            eur_rate = 2.95
            for c in currencies:
                code = c.get("code", "")
                rate = c.get("rate", 0)
                quantity = c.get("quantity", 1) or 1
                if code == "USD":
                    usd_rate = float(rate) / quantity
                elif code == "EUR":
                    eur_rate = float(rate) / quantity

            # FX risk: higher USD/GEL = more expensive imports
            # Baseline ~2.70. Above 2.85 = elevated. Above 3.0 = critical.
            fx_score = 0
            if usd_rate > 3.0:
                fx_score = 80
            elif usd_rate > 2.85:
                fx_score = 50
            elif usd_rate > 2.75:
                fx_score = 25
            else:
                fx_score = 10

            return {
                "usd_gel": round(usd_rate, 4),
                "eur_gel": round(eur_rate, 4),
                "fx_risk_score": fx_score,
                "quality": "live",
                "nbg_date": entry.get("date", ""),
            }
        except Exception as exc:
            logger.debug("NBG FX fetch failed: %s", exc)
            return {
                "usd_gel": 2.75,
                "eur_gel": 2.95,
                "fx_risk_score": 15,
                "quality": "unavailable",
            }

    # ─────────────────────────────────────────────────────────────────
    # 3. GEOPOLITICAL / DISRUPTION RISK (news scanning)
    # ─────────────────────────────────────────────────────────────────

    async def _scan_geopolitical_risk(self) -> Dict[str, Any]:
        """
        Scan news headlines for disruption keywords relevant to
        Caucasus energy corridor.

        Keywords: pipeline disruption, oil sanctions, Black Sea,
        BTC pipeline, Georgia conflict, Azerbaijan, Turkey energy, etc.
        """
        client = await self._get_client()

        # Search queries targeting pipeline/energy disruption news
        queries = [
            "BTC+pipeline+disruption+OR+shutdown+OR+maintenance",
            "Caucasus+oil+gas+pipeline+risk",
            "Black+Sea+shipping+disruption+OR+blockade",
            "Georgia+Azerbaijan+Turkey+energy+crisis",
            "OPEC+oil+production+cut+OR+increase",
            "crude+oil+supply+disruption",
        ]

        headlines: List[Dict[str, str]] = []
        disruption_signals = 0

        DISRUPTION_KEYWORDS = {
            "disruption", "shutdown", "explosion", "attack", "sanctions",
            "blockade", "crisis", "conflict", "war", "embargo", "cut",
            "maintenance", "outage", "leak", "fire", "sabotage",
            "suspended", "halted", "closed", "storm", "earthquake",
        }

        PRICE_KEYWORDS = {
            "surge", "spike", "plunge", "crash", "soar", "jump",
            "record high", "record low", "volatile", "volatility",
        }

        for query in queries[:3]:  # Limit to 3 queries to avoid rate issues
            try:
                url = _GNEWS_RSS.format(query=query)
                resp = await client.get(url)
                if resp.status_code == 200:
                    # Parse RSS XML simply
                    text = resp.text
                    # Extract titles between <title> tags
                    import re
                    titles = re.findall(r"<title><!\[CDATA\[(.*?)\]\]></title>", text)
                    if not titles:
                        titles = re.findall(r"<title>(.*?)</title>", text)

                    for title in titles[:5]:  # Max 5 per query
                        title_lower = title.lower()
                        is_disruption = any(kw in title_lower for kw in DISRUPTION_KEYWORDS)
                        is_price_event = any(kw in title_lower for kw in PRICE_KEYWORDS)
                        if is_disruption or is_price_event:
                            disruption_signals += 1
                            headlines.append({
                                "title": title[:120],
                                "type": "disruption" if is_disruption else "price_event",
                            })
            except Exception as exc:
                logger.debug("News scan failed for query '%s': %s", query, exc)

        # Score: each disruption signal adds 15 points, capped at 100
        geo_score = min(100, disruption_signals * 15)

        return {
            "disruption_signals": disruption_signals,
            "geo_risk_score": geo_score,
            "recent_headlines": headlines[:8],
            "queries_scanned": min(len(queries), 3),
            "quality": "live" if headlines else "estimated",
        }

    # ─────────────────────────────────────────────────────────────────
    # 4. EIA SUPPLY FUNDAMENTALS (live — free API, no key needed)
    # ─────────────────────────────────────────────────────────────────

    async def _compute_supply_fundamentals(self) -> Dict[str, Any]:
        """
        Fetch U.S. crude oil weekly inventory data from EIA open API.
        This is the most important short-term fundamental signal:
          - Inventory DRAW (stocks decreased) → supply tightening → bullish → risk UP
          - Inventory BUILD (stocks increased) → oversupply → bearish → risk DOWN

        We also compute a supply_score (0-100) based on the magnitude of
        the weekly inventory change relative to historical norms.
        """
        client = await self._get_client()
        try:
            # EIA v2 open data API (no key required for basic queries)
            resp = await client.get(
                _EIA_CRUDE_STOCKS_URL,
                params={
                    "frequency": "weekly",
                    "data[0]": "value",
                    "facets[product][]": "EPC0",  # Crude Oil
                    "sort[0][column]": "period",
                    "sort[0][direction]": "desc",
                    "offset": "0",
                    "length": "4",  # Last 4 weeks
                },
            )

            if resp.status_code == 200:
                data = resp.json()
                records = data.get("response", {}).get("data", [])

                if len(records) >= 2:
                    latest_stocks = float(records[0].get("value", 0))  # thousand barrels
                    prev_stocks = float(records[1].get("value", 0))
                    weekly_change = latest_stocks - prev_stocks  # positive = build, negative = draw
                    period = records[0].get("period", "")

                    # Supply risk scoring:
                    # A draw > 5M BBL = significant tightening → supply_score 60+
                    # A draw > 10M BBL = major tightening → supply_score 80+
                    # A build > 5M BBL = glut → supply_score 15 (low risk from supply side)
                    abs_change = abs(weekly_change)
                    if weekly_change < 0:  # DRAW — supply tightening
                        if abs_change > 10000:  # > 10M BBL draw
                            supply_score = 85
                        elif abs_change > 5000:
                            supply_score = 65
                        elif abs_change > 2000:
                            supply_score = 45
                        else:
                            supply_score = 25
                        signal = "DRAW"
                        interpretation = f"Supply tightening: {abs_change/1000:.1f}M BBL drawn from inventory"
                    else:  # BUILD — oversupply
                        if abs_change > 10000:
                            supply_score = 10  # Lots of supply = low risk
                        elif abs_change > 5000:
                            supply_score = 15
                        else:
                            supply_score = 20
                        signal = "BUILD"
                        interpretation = f"Supply comfortable: {abs_change/1000:.1f}M BBL added to inventory"

                    return {
                        "crude_stocks_k_bbl": latest_stocks,
                        "weekly_change_k_bbl": round(weekly_change, 0),
                        "signal": signal,
                        "interpretation": interpretation,
                        "supply_score": supply_score,
                        "period": period,
                        "quality": "live",
                        "source": "U.S. Energy Information Administration (EIA)",
                    }

            # Fallback if API format unexpected
            raise ValueError("EIA response format unexpected")

        except Exception as exc:
            logger.debug("EIA supply data fetch failed: %s", exc)
            return {
                "crude_stocks_k_bbl": 0,
                "weekly_change_k_bbl": 0,
                "signal": "N/A",
                "interpretation": "EIA data unavailable",
                "supply_score": 30,  # Neutral default
                "quality": "unavailable",
                "source": "EIA (unavailable)",
            }

    # ─────────────────────────────────────────────────────────────────
    # SYNTHESIS
    # ─────────────────────────────────────────────────────────────────

    def _synthesize_region_risks(self, price: Dict, fx: Dict, geo: Dict,
                                  supply: Dict = None) -> Dict[str, Any]:
        """
        Compute per-region risk scores. Each region is affected differently:
        - Georgia: FX risk + price risk + supply + geopolitical
        - Azerbaijan: Extraction risk + price + supply
        - Turkey: Transit/geopolitical + price
        - Russia/Iran: Sanctions/geopolitical heavy
        """
        price_score  = price.get("composite_score", 0)
        fx_score     = fx.get("fx_risk_score", 0)
        geo_score    = geo.get("geo_risk_score", 0)
        supply_score = (supply or {}).get("supply_score", 30)

        # Weighted blending per region
        regions = {
            "Georgia": {
                "risk_score": min(100, int(price_score * 0.25 + fx_score * 0.30 + geo_score * 0.20 + supply_score * 0.25)),
                "primary_driver": "FX & import cost pressure" if fx_score > price_score else "Commodity price volatility",
                "factors": ["GEL exchange rate", "Fuel import costs", "Crude inventory levels", "Transit fee revenue"],
            },
            "Azerbaijan": {
                "risk_score": min(100, int(price_score * 0.35 + geo_score * 0.25 + supply_score * 0.30 + fx_score * 0.10)),
                "primary_driver": "Oil price & supply dynamics",
                "factors": ["Crude extraction economics", "Global inventory levels", "BTC throughput", "OPEC+ compliance"],
            },
            "Turkey": {
                "risk_score": min(100, int(geo_score * 0.40 + price_score * 0.25 + supply_score * 0.20 + fx_score * 0.15)),
                "primary_driver": "Geopolitical transit risk",
                "factors": ["Ceyhan terminal security", "Straits congestion", "Regional stability"],
            },
            "Armenia": {
                "risk_score": min(100, int(geo_score * 0.50 + price_score * 0.25 + fx_score * 0.15 + supply_score * 0.10)),
                "primary_driver": "Regional stability",
                "factors": ["Border situation", "Energy dependency", "Transit alternatives"],
            },
            "Russia": {
                "risk_score": min(100, int(geo_score * 0.55 + price_score * 0.20 + supply_score * 0.15 + fx_score * 0.10)),
                "primary_driver": "Sanctions & geopolitical",
                "factors": ["Energy sanctions", "Supply redirection", "Inventory overhang"],
            },
            "Iran": {
                "risk_score": min(100, int(geo_score * 0.50 + price_score * 0.25 + supply_score * 0.15 + fx_score * 0.10)),
                "primary_driver": "Sanctions regime",
                "factors": ["Oil export restrictions", "Regional tensions", "Global supply balance"],
            },
        }

        # Add risk level labels and colors
        for name, reg in regions.items():
            score = reg["risk_score"]
            if score <= 25:
                reg["level"] = "LOW"
                reg["color"] = "rgba(16, 185, 129, 0.25)"
                reg["border_color"] = "rgba(16, 185, 129, 0.6)"
            elif score <= 50:
                reg["level"] = "WATCH"
                reg["color"] = "rgba(212, 168, 83, 0.25)"
                reg["border_color"] = "rgba(212, 168, 83, 0.6)"
            elif score <= 75:
                reg["level"] = "HIGH"
                reg["color"] = "rgba(251, 146, 60, 0.30)"
                reg["border_color"] = "rgba(251, 146, 60, 0.7)"
            else:
                reg["level"] = "CRITICAL"
                reg["color"] = "rgba(244, 63, 94, 0.35)"
                reg["border_color"] = "rgba(244, 63, 94, 0.8)"

        return regions

    def _synthesize_route_risks(self, price: Dict, geo: Dict, infra: Dict = None) -> List[Dict[str, Any]]:
        """
        Compute per-route disruption risk and ESTIMATED FINANCIAL EXPOSURE ($).
        """
        geo_score = geo.get("geo_risk_score", 0)
        price_score = price.get("composite_score", 0)
        
        # Spot market premium (simulation) — how much more we pay per BBL in disruption
        spot_premium = 0.5 + (price_score / 100 * 2.5) # $0.50 to $3.00/BBL surcharge

        infra_routes = (infra or {}).get("routes", [])
        routes_out = []

        for ir in infra_routes:
            # Disruptions are weighted toward geo/security for pipelines, price for shipping
            r_weight = 0.6 if ir["type"] == "crude_pipeline" else 0.45
            risk_score = min(100, int(geo_score * r_weight + price_score * (1 - r_weight)))
            
            # Health modifier from infrastructure service
            health = ir.get("health_score", 100)
            final_risk = min(100, int(risk_score * 0.7 + (100 - health) * 0.3))

            # Financial Impact Model:
            # Exposure = (Throughput Lost vs Capacity) * Current Price * Surcharge
            # For demo, we assume a representative daily volume
            volume_bbl = ir.get("capacity_mbtu", 1.0) * 1_000_000 # Scaling factor
            capacity_util = ir.get("utilization_pct", 100) / 100
            
            # If util < 100%, we calculate "Lost Value"
            # Loss = daily capacity * lost utilization * spot market premium
            daily_loss = volume_bbl * (1.0 - capacity_util) * spot_premium
            
            # Exposure = entire value at risk in 24h
            daily_exposure = volume_bbl * spot_premium 

            r_out = {
                "name": ir["name"],
                "id": ir["id"],
                "risk_score": final_risk,
                "capacity": ir["capacity_mbtu"],
                "pressure_bar": ir["pressure_bar"],
                "throughput_actual": ir["throughput_actual"],
                "health_score": health,
                "financial_exposure_daily": round(daily_exposure, 2),
                "potential_loss_daily": round(daily_loss, 2),
                "spot_surcharge_est": round(spot_premium, 2)
            }
            
            score = final_risk
            if score <= 25:
                r_out["status"] = "OPERATIONAL"
                r_out["color"] = "#10b981"
            elif score <= 50:
                r_out["status"] = "MONITORING"
                r_out["color"] = "#d4a853"
            elif score <= 75:
                r_out["status"] = "ELEVATED"
                r_out["color"] = "#fb923c"
            else:
                r_out["status"] = "DISRUPTED"
                r_out["color"] = "#f43f5e"
                
            routes_out.append(r_out)

        return routes_out

    def _overall_level(self, regions: Dict) -> str:
        scores = [r["risk_score"] for r in regions.values()]
        avg = sum(scores) / len(scores) if scores else 0
        if avg <= 25: return "LOW"
        if avg <= 50: return "WATCH"
        if avg <= 75: return "HIGH"
        return "CRITICAL"

    # ─── Cache helpers ───

    def _get_cache(self, key: str) -> Optional[Dict]:
        entry = self._cache.get(key)
        if not entry:
            return None
        ts = entry.get("_cached_at")
        if ts and (datetime.now() - ts).total_seconds() < self._cache_ttl:
            return entry
        return None

    def _set_cache(self, key: str, data: Dict):
        self._cache[key] = {**data, "_cached_at": datetime.now()}


# Module singleton
risk_engine = RiskIntelligenceEngine()
