"""
FinAI OS -- ESG & Sustainability Engine
========================================
Environmental, Social, Governance scoring and sustainability KPI tracking.

STATUS: PLACEHOLDER / COMING SOON
All ESG metrics are currently computed from hardcoded demo data, not from
real company inputs. Do NOT rely on any ESG scores, carbon footprints, or
sustainability KPIs for audit, reporting, or investment decisions until
this module is connected to real data sources.

Features (planned):
  - Carbon footprint calculator (Scope 1, 2, 3 emissions)
  - ESG score calculator (0-100) with E/S/G sub-scores
  - Sustainability KPI tracker (energy intensity, waste diversion, water, diversity)
  - GRI / SASB framework alignment checker
  - Letter ratings (A+ to F)

Usage:
    from app.services.esg_engine import esg_engine

    report = esg_engine.calculate_esg_score(company_data)
    carbon = esg_engine.get_carbon_footprint(energy_data)
    kpis   = esg_engine.get_sustainability_kpis()
"""

import logging
import math
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class CarbonFootprint:
    """Carbon emissions breakdown by GHG Protocol scopes."""
    scope1: float = 0.0       # Direct emissions (owned vehicles, on-site fuel combustion)
    scope2: float = 0.0       # Indirect energy (purchased electricity, heating)
    scope3: float = 0.0       # Value chain (transport, business travel, waste)
    total: float = 0.0
    unit: str = "tCO2e"       # Tonnes of CO2 equivalent
    intensity: float = 0.0    # tCO2e per million revenue
    yoy_change_pct: float = 0.0
    reduction_target: float = 0.0
    target_year: int = 2030

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scope1": round(self.scope1, 1),
            "scope2": round(self.scope2, 1),
            "scope3": round(self.scope3, 1),
            "total": round(self.total, 1),
            "unit": self.unit,
            "intensity": round(self.intensity, 2),
            "yoy_change_pct": round(self.yoy_change_pct, 1),
            "reduction_target": round(self.reduction_target, 1),
            "target_year": self.target_year,
            "scope_breakdown": {
                "scope1_pct": round(self.scope1 / max(self.total, 1) * 100, 1),
                "scope2_pct": round(self.scope2 / max(self.total, 1) * 100, 1),
                "scope3_pct": round(self.scope3 / max(self.total, 1) * 100, 1),
            },
        }


@dataclass
class SustainabilityKPI:
    """A single sustainability KPI with target tracking."""
    kpi_id: str
    name: str
    category: str              # environmental, social, governance
    value: float
    target: float
    unit: str
    trend: str = "stable"      # improving, stable, declining
    description: str = ""
    framework: str = "GRI"     # GRI, SASB, TCFD
    framework_ref: str = ""    # e.g. GRI 302-3

    def to_dict(self) -> Dict[str, Any]:
        progress = min(self.value / max(self.target, 0.001) * 100, 100) if self.target > 0 else 0
        # For KPIs where lower is better (emissions, waste, etc.)
        if self.kpi_id in ("energy_intensity", "water_intensity", "waste_to_landfill",
                            "lost_time_injury", "gender_pay_gap"):
            progress = max(0, min(100, (1 - self.value / max(self.target * 2, 0.001)) * 100))
            if self.value <= self.target:
                progress = 100
        return {
            "kpi_id": self.kpi_id,
            "name": self.name,
            "category": self.category,
            "value": round(self.value, 2),
            "target": round(self.target, 2),
            "unit": self.unit,
            "progress_pct": round(progress, 1),
            "trend": self.trend,
            "description": self.description,
            "framework": self.framework,
            "framework_ref": self.framework_ref,
            "on_track": progress >= 75,
        }


@dataclass
class ESGScore:
    """ESG composite and sub-scores."""
    environmental: float = 0.0
    social: float = 0.0
    governance: float = 0.0
    composite: float = 0.0
    rating: str = "N/A"
    methodology: str = "FinAI ESG Scoring v1.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "environmental": round(self.environmental, 1),
            "social": round(self.social, 1),
            "governance": round(self.governance, 1),
            "composite": round(self.composite, 1),
            "rating": self.rating,
            "methodology": self.methodology,
            "sub_ratings": {
                "environmental": _score_to_rating(self.environmental),
                "social": _score_to_rating(self.social),
                "governance": _score_to_rating(self.governance),
            },
        }


@dataclass
class FrameworkAlignment:
    """GRI / SASB alignment status."""
    framework: str
    total_indicators: int
    aligned: int
    partial: int
    not_aligned: int
    coverage_pct: float
    key_gaps: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "framework": self.framework,
            "total_indicators": self.total_indicators,
            "aligned": self.aligned,
            "partial": self.partial,
            "not_aligned": self.not_aligned,
            "coverage_pct": round(self.coverage_pct, 1),
            "key_gaps": self.key_gaps,
        }


@dataclass
class ESGReport:
    """Full ESG assessment report."""
    score: ESGScore = field(default_factory=ESGScore)
    carbon: CarbonFootprint = field(default_factory=CarbonFootprint)
    kpis: List[SustainabilityKPI] = field(default_factory=list)
    frameworks: List[FrameworkAlignment] = field(default_factory=list)
    recommendations: List[Dict[str, Any]] = field(default_factory=list)
    generated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score.to_dict(),
            "carbon": self.carbon.to_dict(),
            "kpis": [k.to_dict() for k in self.kpis],
            "frameworks": [f.to_dict() for f in self.frameworks],
            "recommendations": self.recommendations,
            "generated_at": self.generated_at or datetime.now(timezone.utc).isoformat(),
        }


# ============================================================================
# HELPERS
# ============================================================================

def _score_to_rating(score: float) -> str:
    """Convert 0-100 score to letter rating."""
    if score >= 90:
        return "A+"
    elif score >= 80:
        return "A"
    elif score >= 70:
        return "B+"
    elif score >= 60:
        return "B"
    elif score >= 50:
        return "C+"
    elif score >= 40:
        return "C"
    elif score >= 30:
        return "D"
    else:
        return "F"


# Emission factors (simplified, tCO2e per unit)
EMISSION_FACTORS = {
    "natural_gas_m3": 0.00203,       # tCO2e per m3
    "diesel_litre": 0.002676,        # tCO2e per litre
    "gasoline_litre": 0.002315,      # tCO2e per litre
    "lpg_litre": 0.001554,           # tCO2e per litre
    "fuel_oil_litre": 0.003174,      # tCO2e per litre
    "electricity_kwh": 0.000233,     # tCO2e per kWh (Georgia grid average)
    "district_heating_kwh": 0.000198,
    "air_travel_km": 0.000255,       # tCO2e per passenger-km
    "road_freight_tkm": 0.000062,    # tCO2e per tonne-km
    "waste_kg": 0.000467,            # tCO2e per kg (landfill)
    "water_m3": 0.000344,            # tCO2e per m3
}


# ============================================================================
# ESG ENGINE
# ============================================================================

class ESGEngine:
    """Singleton ESG scoring and sustainability tracking engine."""

    _instance: Optional["ESGEngine"] = None

    def __new__(cls) -> "ESGEngine":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._company_data: Dict[str, Any] = {}
        self._energy_data: Dict[str, Any] = {}
        self._kpis: List[SustainabilityKPI] = []
        self._carbon: Optional[CarbonFootprint] = None
        self._score: Optional[ESGScore] = None
        self._seeded = False
        logger.info("ESGEngine initialized.")

    # ------------------------------------------------------------------
    # CARBON FOOTPRINT
    # ------------------------------------------------------------------

    def get_carbon_footprint(self, energy_data: Optional[Dict[str, Any]] = None) -> CarbonFootprint:
        """Calculate carbon footprint from energy consumption data.

        energy_data keys:
          scope1: { fuel_type: quantity_in_native_unit, ... }
          scope2: { electricity_kwh: float, heating_kwh: float }
          scope3: { air_travel_km: float, road_freight_tkm: float, waste_kg: float, ... }
          revenue: float (for intensity calc)
          prior_total: float (for YoY comparison)
        """
        if energy_data:
            self._energy_data = deepcopy(energy_data)
        data = self._energy_data
        if not data:
            return CarbonFootprint()

        # Scope 1 — direct emissions
        scope1 = 0.0
        for fuel, qty in data.get("scope1", {}).items():
            factor = EMISSION_FACTORS.get(fuel, 0.002)
            scope1 += qty * factor

        # Scope 2 — purchased energy
        scope2 = 0.0
        for source, qty in data.get("scope2", {}).items():
            factor = EMISSION_FACTORS.get(source, 0.000233)
            scope2 += qty * factor

        # Scope 3 — value chain
        scope3 = 0.0
        for source, qty in data.get("scope3", {}).items():
            factor = EMISSION_FACTORS.get(source, 0.0003)
            scope3 += qty * factor

        total = scope1 + scope2 + scope3
        revenue = data.get("revenue", 1_000_000)
        intensity = total / max(revenue / 1_000_000, 0.001)

        prior = data.get("prior_total", total * 1.05)
        yoy = ((total - prior) / max(prior, 1)) * 100

        self._carbon = CarbonFootprint(
            scope1=scope1,
            scope2=scope2,
            scope3=scope3,
            total=total,
            intensity=intensity,
            yoy_change_pct=yoy,
            reduction_target=total * 0.55,  # 45% reduction target by 2030
            target_year=2030,
        )
        return self._carbon

    # ------------------------------------------------------------------
    # ESG SCORING
    # ------------------------------------------------------------------

    def calculate_esg_score(self, company_data: Optional[Dict[str, Any]] = None) -> ESGReport:
        """Calculate ESG composite score and generate full report.

        company_data keys:
          environmental: { emissions_reduction_pct, renewable_energy_pct, waste_diversion_pct,
                           water_recycled_pct, env_incidents, env_investment_pct }
          social: { employee_turnover_pct, training_hours_per_employee,
                    diversity_pct, safety_incident_rate, community_investment_pct,
                    living_wage_compliance }
          governance: { board_independence_pct, female_board_pct, ethics_violations,
                        audit_committee_meetings, whistleblower_reports,
                        anti_corruption_training_pct, data_breach_count }
          energy_data: { ... } (passed to get_carbon_footprint)
        """
        if company_data:
            self._company_data = deepcopy(company_data)
        data = self._company_data
        if not data:
            return ESGReport()

        # Calculate carbon footprint if energy data is provided
        if "energy_data" in data:
            self.get_carbon_footprint(data["energy_data"])

        # -- Environmental Score (0-100) --
        env = data.get("environmental", {})
        e_scores = []
        e_scores.append(min(env.get("emissions_reduction_pct", 0) * 2, 100))
        e_scores.append(min(env.get("renewable_energy_pct", 0), 100))
        e_scores.append(min(env.get("waste_diversion_pct", 0), 100))
        e_scores.append(min(env.get("water_recycled_pct", 0) * 1.5, 100))
        incidents = env.get("env_incidents", 5)
        e_scores.append(max(100 - incidents * 15, 0))
        e_scores.append(min(env.get("env_investment_pct", 0) * 10, 100))
        env_score = sum(e_scores) / max(len(e_scores), 1)

        # -- Social Score (0-100) --
        soc = data.get("social", {})
        s_scores = []
        turnover = soc.get("employee_turnover_pct", 20)
        s_scores.append(max(100 - turnover * 3, 0))
        s_scores.append(min(soc.get("training_hours_per_employee", 0) * 2, 100))
        s_scores.append(min(soc.get("diversity_pct", 0) * 2, 100))
        safety = soc.get("safety_incident_rate", 5)
        s_scores.append(max(100 - safety * 20, 0))
        s_scores.append(min(soc.get("community_investment_pct", 0) * 20, 100))
        s_scores.append(min(soc.get("living_wage_compliance", 0), 100))
        soc_score = sum(s_scores) / max(len(s_scores), 1)

        # -- Governance Score (0-100) --
        gov = data.get("governance", {})
        g_scores = []
        g_scores.append(min(gov.get("board_independence_pct", 0) * 1.2, 100))
        g_scores.append(min(gov.get("female_board_pct", 0) * 2.5, 100))
        violations = gov.get("ethics_violations", 3)
        g_scores.append(max(100 - violations * 25, 0))
        g_scores.append(min(gov.get("audit_committee_meetings", 0) * 12.5, 100))
        g_scores.append(min(gov.get("anti_corruption_training_pct", 0), 100))
        breaches = gov.get("data_breach_count", 2)
        g_scores.append(max(100 - breaches * 30, 0))
        gov_score = sum(g_scores) / max(len(g_scores), 1)

        # -- Composite (weighted) --
        composite = env_score * 0.40 + soc_score * 0.30 + gov_score * 0.30

        self._score = ESGScore(
            environmental=env_score,
            social=soc_score,
            governance=gov_score,
            composite=composite,
            rating=_score_to_rating(composite),
        )

        # -- Framework alignment --
        frameworks = self._assess_frameworks(data)

        # -- Recommendations --
        recommendations = self._generate_recommendations(
            env_score, soc_score, gov_score, env, soc, gov
        )

        return ESGReport(
            score=self._score,
            carbon=self._carbon or CarbonFootprint(),
            kpis=self._kpis,
            frameworks=frameworks,
            recommendations=recommendations,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    # ------------------------------------------------------------------
    # KPIs
    # ------------------------------------------------------------------

    def get_sustainability_kpis(self) -> List[SustainabilityKPI]:
        """Return current sustainability KPIs."""
        return self._kpis

    def set_kpis(self, kpis: List[SustainabilityKPI]):
        """Overwrite the KPI list."""
        self._kpis = kpis

    # ------------------------------------------------------------------
    # FRAMEWORK ALIGNMENT
    # ------------------------------------------------------------------

    def _assess_frameworks(self, data: Dict[str, Any]) -> List[FrameworkAlignment]:
        """Assess GRI and SASB alignment from available data."""
        frameworks = []

        # GRI Standards alignment
        gri_indicators = 34  # Core GRI Standards indicators
        env_keys = len(data.get("environmental", {}))
        soc_keys = len(data.get("social", {}))
        gov_keys = len(data.get("governance", {}))
        total_keys = env_keys + soc_keys + gov_keys

        aligned = min(total_keys, int(gri_indicators * 0.7))
        partial = min(max(total_keys - aligned, 0), int(gri_indicators * 0.2))
        not_aligned = gri_indicators - aligned - partial

        gaps = []
        if "emissions_reduction_pct" not in data.get("environmental", {}):
            gaps.append("GRI 305: Emissions reduction target not set")
        if "community_investment_pct" not in data.get("social", {}):
            gaps.append("GRI 413: Community engagement metrics missing")
        if "whistleblower_reports" not in data.get("governance", {}):
            gaps.append("GRI 205: Anti-corruption whistleblower data missing")
        if not self._carbon or self._carbon.total == 0:
            gaps.append("GRI 305-1/2/3: Carbon footprint not calculated")

        frameworks.append(FrameworkAlignment(
            framework="GRI",
            total_indicators=gri_indicators,
            aligned=aligned,
            partial=partial,
            not_aligned=not_aligned,
            coverage_pct=(aligned + partial * 0.5) / gri_indicators * 100,
            key_gaps=gaps[:5],
        ))

        # SASB (industry-specific: Oil & Gas Distribution)
        sasb_total = 18
        sasb_aligned = min(total_keys, int(sasb_total * 0.6))
        sasb_partial = min(max(total_keys - sasb_aligned, 0), int(sasb_total * 0.25))
        sasb_not = sasb_total - sasb_aligned - sasb_partial

        sasb_gaps = []
        if not self._energy_data:
            sasb_gaps.append("EM-MD-110a.1: Scope 1 emissions from distribution")
        if "safety_incident_rate" not in data.get("social", {}):
            sasb_gaps.append("EM-MD-540a.1: Process safety incident reporting")

        frameworks.append(FrameworkAlignment(
            framework="SASB",
            total_indicators=sasb_total,
            aligned=sasb_aligned,
            partial=sasb_partial,
            not_aligned=sasb_not,
            coverage_pct=(sasb_aligned + sasb_partial * 0.5) / sasb_total * 100,
            key_gaps=sasb_gaps[:5],
        ))

        return frameworks

    # ------------------------------------------------------------------
    # RECOMMENDATIONS
    # ------------------------------------------------------------------

    def _generate_recommendations(
        self, env_score: float, soc_score: float, gov_score: float,
        env: Dict, soc: Dict, gov: Dict
    ) -> List[Dict[str, Any]]:
        """Generate prioritized ESG improvement recommendations."""
        recs: List[Dict[str, Any]] = []

        # Environmental recommendations
        if env.get("renewable_energy_pct", 0) < 30:
            recs.append({
                "priority": "high",
                "category": "environmental",
                "title": "Increase Renewable Energy Adoption",
                "description": "Current renewable energy share is below 30%. Target 50% by 2027 through solar panel installation at storage facilities and green energy procurement.",
                "impact": "Could reduce Scope 2 emissions by 40% and improve E-score by 15 points.",
                "estimated_cost": "GEL 2-5M",
                "timeline": "18-24 months",
                "framework_ref": "GRI 302-1, SASB EM-MD-130a.1",
            })

        if env.get("waste_diversion_pct", 0) < 70:
            recs.append({
                "priority": "medium",
                "category": "environmental",
                "title": "Improve Waste Diversion Rate",
                "description": "Implement comprehensive recycling program for fuel storage facility waste, including oil-contaminated materials recovery.",
                "impact": "Target 85% diversion rate, reducing landfill costs by 30%.",
                "estimated_cost": "GEL 500K-1M",
                "timeline": "6-12 months",
                "framework_ref": "GRI 306-4",
            })

        if env.get("emissions_reduction_pct", 0) < 20:
            recs.append({
                "priority": "critical",
                "category": "environmental",
                "title": "Accelerate Emissions Reduction Program",
                "description": "Deploy vapor recovery systems at fuel terminals, electrify fleet vehicles, optimize logistics routes for fuel efficiency.",
                "impact": "Potential 25-30% Scope 1 reduction within 2 years.",
                "estimated_cost": "GEL 3-8M",
                "timeline": "12-24 months",
                "framework_ref": "GRI 305-5, TCFD Strategy",
            })

        # Social recommendations
        if soc.get("training_hours_per_employee", 0) < 30:
            recs.append({
                "priority": "medium",
                "category": "social",
                "title": "Expand Employee Training Programs",
                "description": "Increase average training hours to 40+ per employee annually, focusing on safety, digital skills, and sustainability awareness.",
                "impact": "Improves retention by ~15% and S-score by 10 points.",
                "estimated_cost": "GEL 300K-600K annually",
                "timeline": "Ongoing",
                "framework_ref": "GRI 404-1",
            })

        if soc.get("diversity_pct", 0) < 35:
            recs.append({
                "priority": "high",
                "category": "social",
                "title": "Strengthen Diversity & Inclusion",
                "description": "Set targets for gender diversity in management (40% by 2028), implement inclusive hiring practices, establish mentorship programs.",
                "impact": "Drives innovation and improves S-score by 12 points.",
                "estimated_cost": "GEL 200K-400K",
                "timeline": "12-36 months",
                "framework_ref": "GRI 405-1, SASB HC-330a.1",
            })

        # Governance recommendations
        if gov.get("board_independence_pct", 0) < 60:
            recs.append({
                "priority": "high",
                "category": "governance",
                "title": "Increase Board Independence",
                "description": "Appoint additional independent directors to achieve 60%+ board independence ratio, per OECD Corporate Governance Principles.",
                "impact": "Enhances investor confidence and G-score by 15 points.",
                "estimated_cost": "Minimal (governance restructuring)",
                "timeline": "6-12 months",
                "framework_ref": "GRI 102-22",
            })

        if gov.get("anti_corruption_training_pct", 0) < 90:
            recs.append({
                "priority": "medium",
                "category": "governance",
                "title": "Expand Anti-Corruption Training",
                "description": "Achieve 100% staff anti-corruption training coverage with annual refresher courses and supply chain due diligence.",
                "impact": "Reduces compliance risk and improves G-score by 8 points.",
                "estimated_cost": "GEL 100K-200K",
                "timeline": "3-6 months",
                "framework_ref": "GRI 205-2",
            })

        # Sort: critical > high > medium > low
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        recs.sort(key=lambda r: priority_order.get(r["priority"], 99))

        return recs

    # ------------------------------------------------------------------
    # DEMO DATA SEEDING
    # ------------------------------------------------------------------

    def seed_demo_data(self) -> Dict[str, Any]:
        """Populate engine with realistic demo data for a fuel distribution company."""
        # Company ESG data (NYX Core Thinker-like fuel distributor)
        company_data = {
            "environmental": {
                "emissions_reduction_pct": 12.5,
                "renewable_energy_pct": 18.0,
                "waste_diversion_pct": 62.0,
                "water_recycled_pct": 45.0,
                "env_incidents": 2,
                "env_investment_pct": 3.5,
            },
            "social": {
                "employee_turnover_pct": 14.2,
                "training_hours_per_employee": 24.0,
                "diversity_pct": 28.0,
                "safety_incident_rate": 1.8,
                "community_investment_pct": 1.2,
                "living_wage_compliance": 94.0,
            },
            "governance": {
                "board_independence_pct": 55.0,
                "female_board_pct": 22.0,
                "ethics_violations": 1,
                "audit_committee_meetings": 6,
                "whistleblower_reports": 3,
                "anti_corruption_training_pct": 78.0,
                "data_breach_count": 0,
            },
            "energy_data": {
                "scope1": {
                    "diesel_litre": 2_850_000,
                    "gasoline_litre": 1_200_000,
                    "natural_gas_m3": 450_000,
                    "lpg_litre": 380_000,
                },
                "scope2": {
                    "electricity_kwh": 8_500_000,
                    "district_heating_kwh": 1_200_000,
                },
                "scope3": {
                    "air_travel_km": 350_000,
                    "road_freight_tkm": 12_000_000,
                    "waste_kg": 280_000,
                    "water_m3": 95_000,
                },
                "revenue": 185_000_000,
                "prior_total": 12_800,
            },
        }

        # Sustainability KPIs
        kpis = [
            SustainabilityKPI(
                kpi_id="energy_intensity",
                name="Energy Intensity",
                category="environmental",
                value=0.42,
                target=0.35,
                unit="GJ / GEL M revenue",
                trend="improving",
                description="Total energy consumed per million GEL revenue",
                framework="GRI",
                framework_ref="GRI 302-3",
            ),
            SustainabilityKPI(
                kpi_id="renewable_share",
                name="Renewable Energy Share",
                category="environmental",
                value=18.0,
                target=30.0,
                unit="%",
                trend="improving",
                description="Share of total energy from renewable sources",
                framework="GRI",
                framework_ref="GRI 302-1",
            ),
            SustainabilityKPI(
                kpi_id="carbon_intensity",
                name="Carbon Intensity",
                category="environmental",
                value=68.5,
                target=55.0,
                unit="tCO2e / GEL M",
                trend="improving",
                description="GHG emissions per million GEL revenue",
                framework="GRI",
                framework_ref="GRI 305-4",
            ),
            SustainabilityKPI(
                kpi_id="waste_diversion",
                name="Waste Diversion Rate",
                category="environmental",
                value=62.0,
                target=80.0,
                unit="%",
                trend="improving",
                description="Percentage of waste diverted from landfill",
                framework="GRI",
                framework_ref="GRI 306-4",
            ),
            SustainabilityKPI(
                kpi_id="water_intensity",
                name="Water Intensity",
                category="environmental",
                value=0.51,
                target=0.40,
                unit="m3 / GEL M revenue",
                trend="stable",
                description="Water consumption per million GEL revenue",
                framework="GRI",
                framework_ref="GRI 303-5",
            ),
            SustainabilityKPI(
                kpi_id="employee_training",
                name="Training Hours",
                category="social",
                value=24.0,
                target=40.0,
                unit="hrs / employee",
                trend="improving",
                description="Average training hours per employee per year",
                framework="GRI",
                framework_ref="GRI 404-1",
            ),
            SustainabilityKPI(
                kpi_id="gender_diversity",
                name="Gender Diversity",
                category="social",
                value=28.0,
                target=40.0,
                unit="% women in management",
                trend="improving",
                description="Percentage of women in management positions",
                framework="GRI",
                framework_ref="GRI 405-1",
            ),
            SustainabilityKPI(
                kpi_id="lost_time_injury",
                name="Lost Time Injury Rate",
                category="social",
                value=1.8,
                target=1.0,
                unit="per 200K hrs",
                trend="improving",
                description="Number of lost time injuries per 200,000 hours worked",
                framework="SASB",
                framework_ref="SASB EM-MD-320a.1",
            ),
            SustainabilityKPI(
                kpi_id="living_wage",
                name="Living Wage Compliance",
                category="social",
                value=94.0,
                target=100.0,
                unit="%",
                trend="stable",
                description="Percentage of workforce paid above living wage",
                framework="GRI",
                framework_ref="GRI 202-1",
            ),
            SustainabilityKPI(
                kpi_id="board_independence",
                name="Board Independence",
                category="governance",
                value=55.0,
                target=66.0,
                unit="% independent",
                trend="stable",
                description="Percentage of independent board members",
                framework="GRI",
                framework_ref="GRI 102-22",
            ),
            SustainabilityKPI(
                kpi_id="anticorruption_training",
                name="Anti-Corruption Training",
                category="governance",
                value=78.0,
                target=100.0,
                unit="% employees",
                trend="improving",
                description="Employees who completed anti-corruption training",
                framework="GRI",
                framework_ref="GRI 205-2",
            ),
            SustainabilityKPI(
                kpi_id="data_privacy",
                name="Data Privacy Compliance",
                category="governance",
                value=96.0,
                target=100.0,
                unit="% compliance",
                trend="stable",
                description="Compliance rate with data protection regulations",
                framework="SASB",
                framework_ref="SASB TC-SI-220a.1",
            ),
        ]

        self._kpis = kpis
        self._company_data = company_data

        # Calculate scores
        report = self.calculate_esg_score(company_data)

        self._seeded = True
        logger.info(
            "ESG demo data seeded: composite=%.1f (%s), carbon=%.1f tCO2e, %d KPIs",
            report.score.composite, report.score.rating,
            report.carbon.total, len(kpis),
        )

        return {
            "status": "seeded",
            "composite_score": round(report.score.composite, 1),
            "rating": report.score.rating,
            "carbon_total": round(report.carbon.total, 1),
            "kpi_count": len(kpis),
        }

    # ------------------------------------------------------------------
    # DASHBOARD (aggregated)
    # ------------------------------------------------------------------

    def get_dashboard(self) -> Dict[str, Any]:
        """Return full ESG dashboard data."""
        if not self._score:
            if self._company_data:
                self.calculate_esg_score()
            else:
                return {"seeded": False, "message": "No ESG data. Call POST /api/esg/seed first."}

        report = ESGReport(
            score=self._score or ESGScore(),
            carbon=self._carbon or CarbonFootprint(),
            kpis=self._kpis,
            frameworks=self._assess_frameworks(self._company_data),
            recommendations=self._generate_recommendations(
                self._score.environmental if self._score else 0,
                self._score.social if self._score else 0,
                self._score.governance if self._score else 0,
                self._company_data.get("environmental", {}),
                self._company_data.get("social", {}),
                self._company_data.get("governance", {}),
            ),
        )
        result = report.to_dict()
        result["seeded"] = self._seeded
        return result


# Module-level singleton
esg_engine = ESGEngine()
