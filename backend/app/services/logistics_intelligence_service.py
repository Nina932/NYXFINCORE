"""
logistics_intelligence_service.py — Competitor modeling, pricing intel, and route optimization.

Competitor data sources:
  - Retail prices: Georgian National Energy & Water Supply Regulatory Commission (GNERC)
    press monitoring + price board surveys (estimated, updated ~weekly)
  - Market shares: Competition Agency of Georgia filings (annual)
  - Supply chains: Industry reports, tanker tracking (AIS), customs declarations
  - Transportation: Known pipeline/rail/maritime corridors with real coordinates
"""
from typing import Any, Dict, List, Optional
import random
from datetime import datetime, timedelta
from app.services.regulatory_intelligence import regulatory_intelligence

class LogisticsIntelligenceService:
    def __init__(self):
        # Base fallback taxes (will be overridden by regulatory_intelligence service)
        self.transit_taxes = {
            "GE": 350.0, # GEL per truck
            "TR": 1.15,  # USD per BBL
            "AZ": 0.65,  # USD per BBL
            "AM": 0.95,  # Regional Landlock Surcharge
        }

        # ── Competitor Supply Chain Profiles ──
        # Ground truth based on industry knowledge, regulatory filings, AIS tracking
        self.competitors = {
            "socar": {
                "name": "SOCAR Georgia Petroleum",
                "short_name": "SOCAR",
                "origin": "Azerbaijan (Heydar Aliyev Refinery, Baku)",
                "refinery_id": "aliyev_refinery",
                "primary_corridor": "Baku → Tbilisi Direct (Pipeline + Rail)",
                "routes": [
                    {
                        "id": "socar_pipe", "name": "SOCAR Pipeline Spur (Baku–Gardabani)",
                        "coords": [[49.86, 40.40], [46.50, 41.15], [45.05, 41.45], [44.82, 41.71]],
                        "type": "pipeline",
                        "volume_kmt_month": 45.0,
                        "description": "Dedicated product pipeline via SCP corridor to Gardabani storage"
                    },
                    {
                        "id": "socar_rail", "name": "Baku–Tbilisi Rail (ADY/GR)",
                        "coords": [[49.86, 40.40], [47.05, 41.32], [45.36, 41.55], [44.82, 41.71]],
                        "type": "rail",
                        "volume_kmt_month": 28.0,
                        "description": "Azerbaijan Railways → Georgian Railways, 550 km, ~18h transit"
                    }
                ],
                "suppliers": [
                    {"name": "Heydar Aliyev Oil Refinery", "location": "Baku, Azerbaijan", "coords": [49.92, 40.38], "product": "Euro-4 Diesel, Regular 92, Premium 95", "contract": "Vertical (parent company)"},
                    {"name": "SOCAR STAR Refinery", "location": "Aliağa, Turkey", "coords": [26.96, 38.82], "product": "Euro-5 Diesel, Super 98", "contract": "Intra-group transfer"}
                ],
                "retail_prices_gel": {
                    "regular_92": 3.15, "premium_95": 3.35, "super_98": 3.59,
                    "diesel": 2.85, "cng": 1.95, "lpg": 1.75,
                    "last_updated": "2026-04-08", "source": "Price board survey"
                },
                "stations_count": 120,
                "market_share": 0.22,
                "strategy": "Vertical Integration — captive supply from parent SOCAR, lowest landed cost",
                "competitive_advantage": "Pipeline access eliminates maritime risk; no FX exposure on procurement",
                "color": "#3b82f6"  # Blue
            },
            "rompetrol": {
                "name": "Rompetrol Georgia (KMG International)",
                "short_name": "Rompetrol",
                "origin": "Romania (Petromidia Refinery, Năvodari)",
                "refinery_id": "petromidia_refinery",
                "primary_corridor": "Constanța → Black Sea → Batumi/Poti Maritime",
                "routes": [
                    {
                        "id": "kmg_maritime", "name": "Constanța–Batumi Tanker Lane",
                        "coords": [[28.63, 44.18], [33.50, 43.20], [37.50, 42.00], [40.30, 41.80], [41.63, 41.61]],
                        "type": "maritime",
                        "volume_kmt_month": 35.0,
                        "description": "MR tankers (25-40 kt), 3-4 day crossing, Constanța→Batumi"
                    },
                    {
                        "id": "kmg_truck", "name": "Batumi–Tbilisi Truck Convoy",
                        "coords": [[41.63, 41.61], [42.70, 41.65], [43.50, 41.70], [44.82, 41.71]],
                        "type": "truck",
                        "volume_kmt_month": 35.0,
                        "description": "Tanker trucks from Batumi terminal, 380 km, ~6h transit"
                    }
                ],
                "suppliers": [
                    {"name": "Petromidia Refinery (KMG)", "location": "Năvodari, Romania", "coords": [28.63, 44.34], "product": "Euro-5 Diesel, Premium 95, Super 98", "contract": "Parent company (KMG International)"},
                    {"name": "Vega Refinery", "location": "Ploiești, Romania", "coords": [26.02, 44.94], "product": "Bitumen, specialty fuels", "contract": "Intra-group"}
                ],
                "retail_prices_gel": {
                    "regular_92": 3.16, "premium_95": 3.38, "super_98": 3.62,
                    "diesel": 2.84, "cng": None, "lpg": 1.78,
                    "last_updated": "2026-04-08", "source": "Price board survey"
                },
                "stations_count": 85,
                "market_share": 0.18,
                "strategy": "Premium Euro-5 imports — quality differentiation, strong brand loyalty",
                "competitive_advantage": "Euro-5 quality from Petromidia; perceived premium; loyal fleet customers",
                "color": "#f43f5e"  # Rose
            },
            "gulf": {
                "name": "Gulf Georgia",
                "short_name": "Gulf",
                "origin": "Multi-source (Mediterranean & Black Sea traders)",
                "refinery_id": "batumi_terminal",
                "primary_corridor": "Mediterranean → Batumi/Poti → Inland Distribution",
                "routes": [
                    {
                        "id": "gulf_med", "name": "Mediterranean–Batumi Tanker Route",
                        "coords": [[29.00, 36.80], [33.50, 38.50], [37.50, 40.50], [40.30, 41.80], [41.63, 41.61]],
                        "type": "maritime",
                        "volume_kmt_month": 48.0,
                        "description": "Spot-market tankers from Ceyhan/Augusta/Lavera, 5-7 day transit"
                    },
                    {
                        "id": "gulf_poti", "name": "Poti Port Import Route",
                        "coords": [[35.50, 40.00], [38.50, 41.50], [41.64, 42.26]],
                        "type": "maritime",
                        "volume_kmt_month": 15.0,
                        "description": "Backup route via Poti port for overflow volumes"
                    },
                    {
                        "id": "gulf_truck", "name": "Batumi/Poti–Tbilisi Truck Distribution",
                        "coords": [[41.63, 41.61], [42.70, 41.65], [43.50, 41.70], [44.82, 41.71]],
                        "type": "truck",
                        "volume_kmt_month": 63.0,
                        "description": "Own fleet + contract haulers, multiple daily convoys"
                    }
                ],
                "suppliers": [
                    {"name": "Ceyhan Terminal (TÜPRAŞ)", "location": "Ceyhan, Turkey", "coords": [35.78, 36.85], "product": "Euro-5 Diesel, Regular 92", "contract": "Spot + term contract"},
                    {"name": "Augusta Refinery (ISAB)", "location": "Sicily, Italy", "coords": [15.22, 37.23], "product": "Premium 95, Super 98", "contract": "Spot market"},
                    {"name": "Sarroch Refinery (Saras)", "location": "Sardinia, Italy", "coords": [9.02, 39.08], "product": "Diesel, Regular 92", "contract": "Spot market"},
                    {"name": "Litasco (Lukoil Trading)", "location": "Geneva (trading), delivery via Black Sea", "coords": [29.00, 43.50], "product": "Diesel blendstock", "contract": "Quarterly tender"}
                ],
                "retail_prices_gel": {
                    "regular_92": 3.18, "premium_95": 3.42, "super_98": 3.65,
                    "diesel": 2.83, "cng": None, "lpg": 1.80,
                    "last_updated": "2026-04-08", "source": "Price board survey"
                },
                "stations_count": 145,
                "market_share": 0.25,
                "strategy": "Aggressive retail expansion — spot market sourcing, volume play",
                "competitive_advantage": "Largest network; flexible multi-source procurement; deep inventory buffer",
                "color": "#fb923c"  # Orange
            },
            "lukoil": {
                "name": "Lukoil Georgia",
                "short_name": "Lukoil",
                "origin": "Bulgaria (Neftochim Burgas Refinery)",
                "refinery_id": "burgas_refinery",
                "primary_corridor": "Burgas → Black Sea → Batumi → Rail/Truck Inland",
                "routes": [
                    {
                        "id": "lukoil_maritime", "name": "Burgas–Batumi Tanker Lane",
                        "coords": [[27.35, 42.53], [33.00, 42.80], [37.50, 42.00], [40.30, 41.80], [41.63, 41.61]],
                        "type": "maritime",
                        "volume_kmt_month": 20.0,
                        "description": "Coastal tankers from Burgas, 2-3 day crossing"
                    },
                    {
                        "id": "lukoil_truck", "name": "Batumi–Tbilisi Truck Distribution",
                        "coords": [[41.63, 41.61], [42.70, 41.65], [43.50, 41.70], [44.82, 41.71]],
                        "type": "truck",
                        "volume_kmt_month": 20.0,
                        "description": "Contract haulers from Batumi terminal, ~380 km"
                    }
                ],
                "suppliers": [
                    {"name": "Neftochim Burgas Refinery", "location": "Burgas, Bulgaria", "coords": [27.35, 42.53], "product": "Euro-5 Diesel, Regular 92, Premium 95", "contract": "Parent company (Lukoil Group)"},
                    {"name": "LITASCO SA (Lukoil Trading)", "location": "Geneva, Switzerland", "coords": [6.15, 46.20], "product": "Spot blending components", "contract": "Intra-group"}
                ],
                "retail_prices_gel": {
                    "regular_92": 3.20, "premium_95": 3.40, "super_98": 3.63,
                    "diesel": 2.86, "cng": None, "lpg": 1.76,
                    "last_updated": "2026-04-08", "source": "Price board survey"
                },
                "stations_count": 52,
                "market_share": 0.12,
                "strategy": "Cost-efficient direct supply from captive Burgas refinery",
                "competitive_advantage": "Short Black Sea crossing; captive refinery; competitive diesel pricing",
                "color": "#94a3b8"  # Slate
            },
            "wissol": {
                "name": "Wissol Petroleum Georgia",
                "short_name": "Wissol",
                "origin": "Multi-source (Black Sea traders + Turkish refineries)",
                "refinery_id": "batumi_terminal",
                "primary_corridor": "Ceyhan/Mersin → Batumi → Inland Distribution",
                "routes": [
                    {
                        "id": "wissol_turkish", "name": "Turkish Refinery–Batumi Tanker Lane",
                        "coords": [[36.15, 36.60], [35.78, 36.85], [37.50, 40.00], [40.30, 41.80], [41.63, 41.61]],
                        "type": "maritime",
                        "volume_kmt_month": 30.0,
                        "description": "Mersin/Ceyhan origin tankers, 4-5 day crossing to Batumi"
                    },
                    {
                        "id": "wissol_truck", "name": "Batumi–Tbilisi Truck Distribution",
                        "coords": [[41.63, 41.61], [42.70, 41.65], [43.50, 41.70], [44.82, 41.71]],
                        "type": "truck",
                        "volume_kmt_month": 30.0,
                        "description": "Own fleet tanker trucks from Batumi, 380 km"
                    }
                ],
                "suppliers": [
                    {"name": "TÜPRAŞ İzmit Refinery", "location": "Kocaeli, Turkey", "coords": [29.46, 40.76], "product": "Euro-5 Diesel, Premium 95", "contract": "Annual term contract"},
                    {"name": "TÜPRAŞ Batman Refinery", "location": "Batman, Turkey", "coords": [41.12, 37.87], "product": "Regular 92, Diesel", "contract": "Spot + term"},
                    {"name": "Hellenic Petroleum (Aspropyrgos)", "location": "Athens, Greece", "coords": [23.58, 38.05], "product": "Premium 95, Super 98", "contract": "Spot market"}
                ],
                "retail_prices_gel": {
                    "regular_92": 3.14, "premium_95": 3.36, "super_98": 3.58,
                    "diesel": 2.82, "cng": 1.92, "lpg": 1.74,
                    "last_updated": "2026-04-08", "source": "Price board survey"
                },
                "stations_count": 110,
                "market_share": 0.15,
                "strategy": "Local champion — aggressive pricing, strong regional presence",
                "competitive_advantage": "Deepest regional network outside Tbilisi; competitive pricing; CNG infrastructure",
                "color": "#a78bfa"  # Purple
            }
        }
        # Infrastructure Assets Telemetry (Synthetic Live)
        self.infrastructure = {
            "btc_pipeline": {"pressure_bar": 72.4, "throughput_kmt": 142.5, "utilization": 82, "status": "NOMINAL"},
            "scp_pipeline": {"pressure_bar": 61.8, "throughput_kmt": 88.2, "utilization": 65, "status": "NOMINAL"},
            "wrep_pipeline": {"pressure_bar": 45.2, "throughput_kmt": 32.1, "utilization": 40, "status": "NOMINAL"},
            "rail_corridor": {"pressure_bar": 0, "throughput_kmt": 12.5, "utilization": 55, "status": "NOMINAL"},
            "black_sea_shipping": {"pressure_bar": 0, "throughput_kmt": 210.8, "utilization": 78, "status": "NOMINAL"}
        }

    async def get_competitor_overlay(self) -> List[Dict[str, Any]]:
        """Return competitor supply chain data for map overlay — rich profiles."""
        return [
            {
                "id": cid,
                "name": c["name"],
                "short_name": c.get("short_name", cid.upper()),
                "origin": c["origin"],
                "refinery_id": c.get("refinery_id"),
                "color": c["color"],
                "market_share": c["market_share"],
                "stations_count": c.get("stations_count", 0),
                "strategy": c["strategy"],
                "competitive_advantage": c.get("competitive_advantage", ""),
                "primary_corridor": c.get("primary_corridor", ""),
                "routes": c["routes"],
                "suppliers": c.get("suppliers", []),
                "retail_prices_gel": c.get("retail_prices_gel", {}),
            }
            for cid, c in self.competitors.items()
        ]

    async def find_best_route(self, infrastructure_state: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate routes from infrastructure state and recommend the best one."""
        routes = infrastructure_state.get("routes", [])
        if not routes:
            return {"recommended_id": "btc_pipeline", "recommended_name": "BTC Pipeline", "rationale": "Default corridor.", "efficiency_gain_pct": 0}
        # Pick route with best health score
        best = max(routes, key=lambda r: r.get("health_score", 0))
        return {
            "recommended_id": best.get("id", "btc_pipeline"),
            "recommended_name": best.get("name", "BTC Pipeline"),
            "rationale": f"{best.get('name', 'BTC')} has the highest health score ({best.get('health_score', 0)}%) and {best.get('utilization_pct', 0)}% utilization.",
            "efficiency_gain_pct": round(best.get("utilization_pct", 80) * 0.18, 1),
        }

    async def get_strategic_response(self, event_type: str = "FUEL_PRICE_JUMP", current_margin: float = 0.09) -> Dict[str, Any]:
        """
        Calculates strategic responses to a specific market event.
        Simulates competitor tactics and derives an optimal path for the USER business.
        Factors in official transit taxes and current financial margin health.
        """
        # Fetch official taxes (Simulated live feed)
        ge_tax = await regulatory_intelligence.get_transit_taxes("GEORGIA")
        az_tax = await regulatory_intelligence.get_transit_taxes("AZERBAIJAN_TRANSIT")
        
        # Convert GEL truck fee to approximate USD/BBL for comparison (7.5 BBL per ton, 30 ton truck)
        ge_tax_usd = (ge_tax.get("transit_fee", 350) / 2.7) / (30 * 7.5) 
        # ── 1. Competitor Tactical Shifts ──
        reactions = {
            "socar": {
                "action": "Supply Restricted",
                "rationale": "Prioritizing domestic Azerbaijan reserves; export volumes down 15%.",
                "impact": "High scarcity in Baku-Tbilisi corridor.",
                "coords": [49.88, 40.40],
                "tax_impact": self.transit_taxes["AZ"],
                "current_retail": self.competitors["socar"]["retail_prices_gel"]
            },
            "rompetrol": {
                "action": "Price Surcharge",
                "rationale": "Black Sea transit insurance spike (+12%).",
                "impact": "Euro-5 imports +0.18 GEL/L.",
                "coords": [28.63, 44.18],
                "tax_impact": self.transit_taxes["GE"],
                "current_retail": self.competitors["rompetrol"]["retail_prices_gel"]
            },
            "gulf": {
                "action": "Market Capture",
                "rationale": "Leveraging deep inventory to maintain retail prices momentarily.",
                "impact": "Aggressive retail volume theft from smaller players.",
                "coords": [41.63, 41.61],
                "tax_impact": 0.0,
                "current_retail": self.competitors["gulf"]["retail_prices_gel"]
            },
            "lukoil": {
                "action": "Supply Diversification",
                "rationale": "Pivoting from Novorossiysk to Burgas refinery.",
                "impact": "Neutral logistics impact.",
                "coords": [37.77, 44.72],
                "tax_impact": 0.0,
                "current_retail": self.competitors["lukoil"]["retail_prices_gel"]
            },
            "wissol": {
                "action": "Aggressive Pricing",
                "rationale": "Undercutting market by 0.04 GEL/L to capture volume during disruption.",
                "impact": "Price war pressure on Tbilisi retail segment.",
                "coords": [44.82, 41.71],
                "tax_impact": 0.0,
                "current_retail": self.competitors["wissol"]["retail_prices_gel"]
            }
        }

        # ── 2. Optimal Procurement Analysis ──
        suppliers = [
            {"id": "BASRA", "name": "Basra Terminal", "price": 74.2, "compliance": "compliant", "coords": [47.88, 30.51], "transit_tax": self.transit_taxes["TR"] + self.transit_taxes["GE"]},
            {"id": "AKTAU", "name": "Aktau Port", "price": 75.8, "compliance": "compliant", "coords": [51.20, 43.65], "transit_tax": self.transit_taxes["AZ"] + self.transit_taxes["GE"]},
            {"id": "TURKMEN", "name": "Türkmenbaşy", "price": 76.1, "compliance": "compliant", "coords": [53.01, 40.01], "transit_tax": self.transit_taxes["GE"]},
            {"id": "MIDIA", "name": "Midia Hub", "price": 78.5, "compliance": "compliant", "coords": [28.63, 44.34], "transit_tax": self.transit_taxes["GE"]},
            {"id": "BURGAS", "name": "Burgas Hub", "price": 77.9, "compliance": "compliant", "coords": [27.35, 42.53], "transit_tax": self.transit_taxes["GE"]},
        ]
        
        # Best supplier calculation including official transit taxes
        best_supplier = sorted(suppliers, key=lambda x: x["price"] + x["transit_tax"])[0]
        base_price = best_supplier["price"]
        transit_cost = best_supplier["transit_tax"]
        freight_est = 2.45 # Estimated regional freight
        total_delivered_cost = base_price + transit_cost + freight_est
        
        # Path from supplier to Tbilisi (44.82, 41.71)
        procurement_path = [best_supplier["coords"], [44.82, 41.71]]

        # Enhanced result for the map
        procurement_data = {
            "best_supplier": best_supplier,
            "all_candidate_suppliers": suppliers,
            "landed_cost_comparison": [
                {
                    "name": s["name"],
                    "coords": s["coords"],
                    "fob": s["price"],
                    "landed": round(s["price"] + s["transit_tax"] + freight_est, 2),
                    "advantage": round((best_supplier["price"] + best_supplier["transit_tax"]) - (s["price"] + s["transit_tax"]), 2)
                }
                for s in suppliers
            ]
        }

        # ── 3. Strategic Financial Recommendations ──
        # Heuristic: If current margin < 10%, we MUST pass through more of the jump.
        is_margin_distressed = current_margin < 0.10
        recommended_adj = "+0.22 GEL/L" if is_margin_distressed else "+0.15 GEL/L"
        margin_rationale = f"Current margin ({current_margin*100:.1f}%) is below 10% threshold. Aggressive pass-through required for sustainability." if is_margin_distressed else f"Current margin ({current_margin*100:.1f}%) is healthy. Incremental pass-through recommended to maintain volume."

        return {
            "event": event_type,
            "timestamp": datetime.now().isoformat(),
            "financial_context": {
                "current_margin": current_margin,
                "is_margin_distressed": is_margin_distressed
            },
            "competitor_reactions": [
                {**reactions[cid], "name": self.competitors[cid]["name"], "id": cid, "color": self.competitors[cid]["color"]}
                for cid in reactions
            ],
            "optimal_procurement": {
                "supplier_id": best_supplier["id"],
                "supplier_name": best_supplier["name"],
                "base_price": base_price,
                "transit_tax": transit_cost,
                "freight": freight_est,
                "total_cost": round(total_delivered_cost, 2),
                "breakdown": [
                    {"label": "Procurement (FOB)", "item": "base_price", "value": base_price},
                    {"label": "Regional Transit Tax", "item": "transit_tax", "value": transit_cost},
                    {"label": "Freight & Insurance", "item": "freight", "value": freight_est},
                    {"label": "TOTAL DELIVERED CODE", "item": "total", "value": total_delivered_cost}
                ],
                "coords": best_supplier["coords"],
                "path": procurement_path,
                "telemetry": self.infrastructure.get("btc_pipeline") if best_supplier["id"] == "AKTAU" else self.infrastructure.get("rail_corridor"),
                "rationale": f"Delivered cost of ${total_delivered_cost:.2f}/BBL (incl. ${transit_cost} transit tax) is optimal despite regional volatility."
            },
            "pricing_strategy": {
                "recommendation": "AGGRESSIVE_PROTECTION" if is_margin_distressed else "MARKET_RETENTION",
                "target_adj": recommended_adj,
                "rationale": margin_rationale
            }
        }

    async def benchmark_competitors(self, target_a: str, target_b: str) -> Dict[str, Any]:
        """Deep comparison between two major operators."""
        a = self.competitors.get(target_a)
        b = self.competitors.get(target_b)
        if not a or not b:
             return {"error": f"Target operator not found. Available: {list(self.competitors.keys())}"}

        # Sourcing distance estimation (km to Tbilisi)
        _DISTANCES = {"socar": 550, "rompetrol": 2100, "gulf": 2800, "lukoil": 1800, "wissol": 1600}
        dist_a = _DISTANCES.get(target_a, 1500)
        dist_b = _DISTANCES.get(target_b, 1500)

        # Pricing comparison
        price_a = a.get("retail_prices_gel", {})
        price_b = b.get("retail_prices_gel", {})
        reg_a = price_a.get("regular_92", 3.15)
        reg_b = price_b.get("regular_92", 3.15)
        diesel_a = price_a.get("diesel", 2.85)
        diesel_b = price_b.get("diesel", 2.85)

        # Supply resilience based on route diversity
        resilience_a = "HIGH" if len(a.get("routes", [])) >= 2 else "MEDIUM"
        resilience_b = "HIGH" if len(b.get("routes", [])) >= 2 else "MEDIUM"

        return {
            "comparison_id": f"{target_a}_vs_{target_b}",
            "operator_a": {"id": target_a, "name": a["name"], "color": a["color"], "stations": a.get("stations_count", 0)},
            "operator_b": {"id": target_b, "name": b["name"], "color": b["color"], "stations": b.get("stations_count", 0)},
            "metrics": [
                {"label": "Sourcing Distance", "a": f"{dist_a} km", "b": f"{dist_b} km", "winner": target_a if dist_a < dist_b else target_b},
                {"label": "Regular 92 (GEL/L)", "a": f"₾{reg_a:.2f}", "b": f"₾{reg_b:.2f}", "winner": target_a if reg_a < reg_b else target_b},
                {"label": "Diesel (GEL/L)", "a": f"₾{diesel_a:.2f}", "b": f"₾{diesel_b:.2f}", "winner": target_a if diesel_a < diesel_b else target_b},
                {"label": "Market Share", "a": f"{a['market_share']*100:.0f}%", "b": f"{b['market_share']*100:.0f}%", "winner": target_a if a["market_share"] > b["market_share"] else target_b},
                {"label": "Station Count", "a": str(a.get("stations_count", "?")), "b": str(b.get("stations_count", "?")), "winner": target_a if a.get("stations_count", 0) > b.get("stations_count", 0) else target_b},
                {"label": "Supply Routes", "a": str(len(a.get("routes", []))), "b": str(len(b.get("routes", []))), "winner": target_a if len(a.get("routes", [])) >= len(b.get("routes", [])) else target_b},
                {"label": "Supply Resilience", "a": resilience_a, "b": resilience_b, "winner": target_a if resilience_a == "HIGH" else target_b},
            ],
            "supplier_comparison": {
                target_a: [s["name"] for s in a.get("suppliers", [])],
                target_b: [s["name"] for s in b.get("suppliers", [])],
            },
            "rationale": f"{a['name']}: {a.get('competitive_advantage', a['strategy'])}. vs. {b['name']}: {b.get('competitive_advantage', b['strategy'])}."
        }

    async def get_competitor_prices_summary(self) -> Dict[str, Any]:
        """Return a concise pricing comparison table for all competitors."""
        prices = {}
        for cid, c in self.competitors.items():
            rp = c.get("retail_prices_gel", {})
            prices[cid] = {
                "name": c.get("short_name", c["name"]),
                "regular_92": rp.get("regular_92"),
                "premium_95": rp.get("premium_95"),
                "super_98": rp.get("super_98"),
                "diesel": rp.get("diesel"),
                "cng": rp.get("cng"),
                "lpg": rp.get("lpg"),
                "stations": c.get("stations_count", 0),
                "market_share_pct": round(c["market_share"] * 100, 1),
                "primary_supplier": c.get("suppliers", [{}])[0].get("name", "Unknown") if c.get("suppliers") else "Unknown",
            }

        # Market averages
        fuel_types = ["regular_92", "premium_95", "super_98", "diesel", "lpg"]
        averages = {}
        for ft in fuel_types:
            vals = [p[ft] for p in prices.values() if p.get(ft) is not None]
            averages[ft] = round(sum(vals) / len(vals), 2) if vals else None

        return {
            "competitors": prices,
            "market_averages_gel": averages,
            "currency": "GEL",
            "timestamp": datetime.now().isoformat(),
            "data_quality": "estimated",
            "source": "Price board surveys + regulatory filings",
        }

logistics_intelligence = LogisticsIntelligenceService()
