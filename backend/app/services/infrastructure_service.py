"""
infrastructure_service.py — Asset registry and operational state for physical logistics infrastructure.
"""
from typing import Any, Dict, List
from datetime import datetime

class InfrastructureService:
    def __init__(self):
        # Professional Infrastructure Assets
        self.assets = {
            "routes": [
                {
                    "id": "btc_pipeline",
                    "name": "BTC Pipeline (Baku-Tbilisi-Ceyhan)",
                    "type": "crude_pipeline",
                    "commodity": "crude",
                    "capacity_mbtu": 1.2,  # Million BBL/d
                    "financial_weight": 0.45,
                    "nodes": ["Baku", "Tbilisi", "Ceyhan"],
                    "coords": [[49.86, 40.40], [44.82, 41.71], [35.81, 36.88]],
                },
                {
                    "id": "middle_corridor_rail",
                    "name": "Middle Corridor Rail Link",
                    "type": "rail",
                    "commodity": "rail",
                    "capacity_mbtu": 0.4,
                    "financial_weight": 0.20,
                    "nodes": ["Baku", "Alyat", "Gardabani", "Tbilisi"],
                    "coords": [[49.86, 40.40], [49.41, 39.95], [45.08, 41.46], [44.82, 41.71]],
                },
                {
                    "id": "scp_pipeline",
                    "name": "South Caucasus Pipeline (SCP)",
                    "type": "gas_pipeline",
                    "commodity": "gas",
                    "capacity_mbtu": 25,
                    "financial_weight": 0.30,
                    "nodes": ["Baku", "Gardabani", "Erzurum"],
                    "coords": [[49.86, 40.40], [45.08, 41.46], [41.27, 39.90]],
                },
                {
                    "id": "black_sea_shipping_rompetrol",
                    "name": "Constanța-Batumi Lane",
                    "type": "tanker_route",
                    "commodity": "cargo",
                    "capacity_mbtu": 1.5,
                    "financial_weight": 0.15,
                    "nodes": ["Constanța", "Batumi"],
                    "coords": [[28.63, 44.18], [41.63, 41.61]],
                },
                {
                    "id": "wrep_pipeline",
                    "name": "WREP (Baku-Supsa) Pipeline",
                    "type": "crude_pipeline",
                    "commodity": "crude",
                    "capacity_mbtu": 0.15,
                    "financial_weight": 0.10,
                    "nodes": ["Baku", "Supsa"],
                    "coords": [[49.86, 40.40], [42.06, 41.81]],
                },
                {
                    "id": "black_sea_shipping_tanker",
                    "name": "Novorossiysk-Batumi Lane",
                    "type": "tanker_route",
                    "commodity": "cargo",
                    "capacity_mbtu": 1.8,
                    "financial_weight": 0.10,
                    "nodes": ["Novorossiysk", "Batumi"],
                    "coords": [[37.77, 44.72], [41.63, 41.61]],
                },
                {
                    "id": "odesa_lane",
                    "name": "Batumi-Constanța-Odesa Strategic Lane",
                    "type": "tanker_route",
                    "commodity": "cargo",
                    "capacity_mbtu": 1.2,
                    "financial_weight": 0.15,
                    "nodes": ["Batumi", "Constanța", "Odesa"],
                    "coords": [[41.63, 41.61], [28.63, 44.18], [30.72, 46.48]],
                }
            ],
            "hubs": [
                {
                    "id": "baku_extraction", 
                    "name": "Baku Field Hub", 
                    "type": "extraction", 
                    "coord": [49.86, 40.40],
                    "storage_telemetry": {"capacity_bbl": 4200000, "current_fill": 0.82, "temp_c": 28.4}
                },
                {
                    "id": "petromidia_refinery", 
                    "name": "Petromidia Refinery (Năvodari)", 
                    "type": "refinery", 
                    "coord": [28.63, 44.34], "supplier_to": ["rompetrol"],
                    "storage_telemetry": {"capacity_bbl": 1500000, "current_fill": 0.65, "temp_c": 31.2}
                },
                {
                    "id": "burgas_refinery", 
                    "name": "Neftochim Burgas Refinery", 
                    "type": "refinery", 
                    "coord": [27.35, 42.53], "supplier_to": ["lukoil"],
                    "storage_telemetry": {"capacity_bbl": 2800000, "current_fill": 0.74, "temp_c": 29.8}
                },
                {
                    "id": "star_refinery", 
                    "name": "SOCAR STAR Refinery (Aliaga)", 
                    "type": "refinery", 
                    "coord": [26.96, 38.82], "supplier_to": ["socar_trading"],
                    "storage_telemetry": {"capacity_bbl": 3100000, "current_fill": 0.88, "temp_c": 27.5}
                },
                {
                    "id": "aliyev_refinery", 
                    "name": "Heydar Aliyev Refinery (Baku)", 
                    "type": "refinery", 
                    "coord": [49.92, 40.38], "supplier_to": ["socar"],
                    "storage_telemetry": {"capacity_bbl": 2200000, "current_fill": 0.91, "temp_c": 26.9}
                },
                {
                    "id": "batumi_terminal", 
                    "name": "Batumi Terminal Hub", 
                    "type": "port", 
                    "coord": [41.63, 41.61],
                    "storage_telemetry": {
                        "tanks": 12, 
                        "capacity_bbl": 5000000, 
                        "current_fill": 0.76, 
                        "temp_c": 24.5,
                        "pressure_psi": 14.7,
                        "last_inspection": "2026-03-15"
                    }
                },
                {
                    "id": "kulevi_terminal", 
                    "name": "Kulevi Oil terminal", 
                    "type": "port", 
                    "coord": [41.64, 42.26],
                    "storage_telemetry": {"capacity_bbl": 2000000, "current_fill": 0.58, "temp_c": 25.1}
                },
                {"id": "tbilisi_cmd", "name": "NYX Command Center (Tbilisi)", "type": "command", "coord": [44.82, 41.71]},
            ]
        }

    async def get_operational_state(self, situational_risk: Dict[str, Any]) -> Dict[str, Any]:
        """
        Derive high-fidelity operational metrics (Pressure, Throughput)
        from global situational risk and market signals.
        """
        geo_risk = situational_risk.get("geo_signals", {}).get("geo_risk_score", 0)
        price_vol = situational_risk.get("price_signals", {}).get("composite_score", 0)
        
        # Operational Logic: High risk/volatility reduces throughput and increases surge pressure
        disruption_factor = (geo_risk * 0.7 + price_vol * 0.3) / 100
        
        routes_state = []
        for r in self.assets["routes"]:
            utilization = 0.92 - (disruption_factor * 0.4) 
            throughput = r["capacity_mbtu"] * utilization
            pressure = 65 + (disruption_factor * 25) 
            health = max(10, int(100 - (disruption_factor * 90)))
            
            routes_state.append({
                **r,
                "utilization_pct": round(utilization * 100, 1),
                "throughput_actual": round(throughput, 2),
                "pressure_bar": round(pressure, 1),
                "health_score": health,
                "status": "NOMINAL" if health > 75 else "WATCH" if health > 40 else "CRITICAL",
                "vessel_count": int(r["capacity_mbtu"] * 10 * (1-disruption_factor)) if r["type"] == "tanker_route" else 0
            })
            
        return {
            "routes": routes_state,
            "hubs": self.assets["hubs"],
            "last_updated": datetime.now().isoformat()
        }

    def get_telemetry_stream(self, routes_state: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Generates a scrolling 'Signal Feed' for the Digital Twin.
        Simulates raw SCADA/Satellite telemetry logs.
        """
        import random
        logs = []
        for r in routes_state:
            # Pipeline logs
            if r["type"] in ["crude_pipeline", "gas_pipeline"]:
                logs.append({
                    "id": f"tel_{random.randint(1000, 9999)}",
                    "source": r["name"].split(" ")[0],
                    "type": "SCADA",
                    "message": f"Pressure stable at {r['pressure_bar']} bar. Flow: {r['throughput_actual']} unit/h.",
                    "severity": "info" if r["status"] == "NOMINAL" else "warning",
                    "timestamp": datetime.now().strftime("%H:%M:%S")
                })
            # Tanker logs
            elif r["type"] == "tanker_route" and r["vessel_count"] > 0:
                logs.append({
                    "id": f"tel_{random.randint(1000, 9999)}",
                    "source": "AIS-SAT",
                    "type": "VESSEL",
                    "message": f"Detected {r['vessel_count']} strategic shipments in transit. Vectors nominal.",
                    "severity": "info",
                    "timestamp": datetime.now().strftime("%H:%M:%S")
                })
        
        # Add a random systemic heartbeat
        logs.append({
            "id": f"tel_hb",
            "source": "NYX-CORE",
            "type": "SYSTEM",
            "message": "Neural link to infrastructure established. Syncing Digital Twin state...",
            "severity": "info",
            "timestamp": datetime.now().strftime("%H:%M:%S")
        })
        
        return logs

infrastructure_service = InfrastructureService()
