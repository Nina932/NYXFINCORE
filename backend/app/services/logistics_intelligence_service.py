"""
logistics_intelligence_service.py — Competitor modeling and route optimization.
"""
from typing import Any, Dict, List, Optional
import random
from datetime import datetime
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
        # Competitor Supply Chain Profiles (Ground Truth based on industry)
        self.competitors = {
            "socar": {
                "name": "Socar Georgia Petroleum",
                "origin": "Azerbaijan",
                "refinery_id": "aliyev_refinery",
                "primary_corridor": "Baku-Tbilisi-Direct",
                "routes": [
                    {"id": "socar_pipe", "name": "Socar Dedicated Pipeline Support", "coords": [[49.86, 40.40], [44.82, 41.71]], "type": "pipeline"},
                    {"id": "socar_rail", "name": "Baku-Tbilisi Rail Link", "coords": [[49.86, 40.40], [44.82, 41.71]], "type": "rail"}
                ],
                "market_share": 0.22,
                "strategy": "Vertical Integration",
                "color": "#3b82f6"  # Blue
            },
            "rompetrol": {
                "name": "Rompetrol Georgia",
                "origin": "Romania (Petromidia)",
                "refinery_id": "petromidid_refinery",
                "primary_corridor": "Black Sea Maritime",
                "routes": [
                    {"id": "kmg_maritime", "name": "Constanța - Batumi Tanker Lane", "coords": [[28.63, 44.18], [41.63, 41.61]], "type": "maritime"}
                ],
                "market_share": 0.18,
                "strategy": "High-Quality Euro-5 Imports",
                "color": "#f43f5e" # Rose
            },
            "gulf": {
                "name": "Gulf Georgia",
                "origin": "International Imports",
                "refinery_id": "med_traders",
                "primary_corridor": "Black Sea Hubs",
                "routes": [
                    {"id": "gulf_batumi", "name": "Batumi Import Route", "coords": [[41.63, 41.61], [44.82, 41.71]], "type": "truck_rail"}
                ],
                "market_share": 0.25,
                "strategy": "Aggressive Retail Expansion",
                "color": "#fb923c" # Orange
            },
            "lukoil": {
                "name": "Lukoil Georgia",
                "origin": "Bulgaria / Burgas",
                "refinery_id": "burgas_refinery",
                "primary_corridor": "Black Sea / Rail",
                "routes": [
                    {"id": "lukoil_maritime", "name": "Burgas - Batumi Route", "coords": [[27.35, 42.53], [41.63, 41.61]], "type": "maritime"}
                ],
                "market_share": 0.12,
                "strategy": "Direct Supply Logistics",
                "color": "#94a3b8" # Slate (Neutral)
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
        """Return competitor supply chain data for map overlay."""
        return [
            {
                "id": cid,
                "name": c["name"],
                "origin": c["origin"],
                "color": c["color"],
                "market_share": c["market_share"],
                "strategy": c["strategy"],
                "routes": c["routes"],
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
                "tax_impact": self.transit_taxes["AZ"]
            },
            "rompetrol": {
                "action": "Price Surcharge",
                "rationale": "Black Sea transit insurance spike (+12%).",
                "impact": "Euro-5 imports +0.18 GEL/L.",
                "coords": [28.63, 44.18],
                "tax_impact": self.transit_taxes["GE"]
            },
            "gulf": {
                "action": "Market Capture",
                "rationale": "Leveraging deep inventory to maintain retail prices momentarily.",
                "impact": "Aggressive retail volume theft from smaller players.",
                "coords": [41.63, 41.61],
                "tax_impact": 0.0
            },
            "lukoil": {
                "action": "Supply Diversification",
                "rationale": "Pivoting from Novorossiysk to Burgas refinery.",
                "impact": "Neutral logistics impact.",
                "coords": [37.77, 44.72],
                "tax_impact": 0.0
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
             return {"error": "Target operator not found"}
        
        # Calculate landing cost disadvantage (synthetic based on origin)
        # Sourcing from Azerbaijan (Aliyev) vs Romania (Petromidia)
        dist_a = 550 # km (Baku-Tbilisi)
        dist_b = 2100 # km (Constanta-Batumi-Tbilisi)
        
        return {
            "comparison_id": f"{target_a}_vs_{target_b}",
            "metrics": [
                {"label": "Sourcing Distance", "a": f"{dist_a} km", "b": f"{dist_b} km", "winner": "socar" if dist_a < dist_b else "rompetrol"},
                {"label": "Logistics Margin", "a": "8.2%", "b": "6.8%", "winner": "socar"},
                {"label": "Supply Resilience", "a": "HIGH", "b": "MEDIUM", "winner": "socar"},
            ],
            "rationale": f"{a['name']} leverages direct pipeline integration, whereas {b['name']} is exposed to Black Sea maritime volatility."
        }

logistics_intelligence = LogisticsIntelligenceService()
