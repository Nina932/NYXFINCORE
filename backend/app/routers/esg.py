from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from app.services.esg_engine import esg_engine
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/esg", tags=["esg"])

# All ESG endpoints return a disclaimer until real data integration is built.
_ESG_DISCLAIMER = (
    "PLACEHOLDER: ESG metrics are computed from hardcoded demo data, not real "
    "company inputs. Do not use for audit, reporting, or compliance purposes."
)


@router.get("/dashboard")
async def esg_dashboard():
    """Full ESG dashboard: scores, KPIs, carbon footprint, frameworks, recommendations."""
    try:
        result = esg_engine.get_dashboard()
        if isinstance(result, dict):
            result["_disclaimer"] = _ESG_DISCLAIMER
            result["_data_source"] = "placeholder"
        return result
    except Exception as e:
        logger.error(f"ESG dashboard error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scores")
async def esg_scores():
    """ESG composite and sub-scores with letter rating."""
    try:
        if not esg_engine._score:
            if esg_engine._company_data:
                esg_engine.calculate_esg_score()
            else:
                return {"seeded": False, "message": "No ESG data. Call POST /api/esg/seed first."}
        return esg_engine._score.to_dict()
    except Exception as e:
        logger.error(f"ESG scores error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/carbon")
async def esg_carbon():
    """Carbon footprint breakdown by Scope 1/2/3."""
    try:
        if not esg_engine._carbon:
            if esg_engine._energy_data:
                esg_engine.get_carbon_footprint()
            else:
                return {"seeded": False, "message": "No energy data. Call POST /api/esg/seed first."}
        return esg_engine._carbon.to_dict()
    except Exception as e:
        logger.error(f"ESG carbon error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/kpis")
async def esg_kpis():
    """Sustainability KPIs with targets and progress."""
    try:
        kpis = esg_engine.get_sustainability_kpis()
        if not kpis:
            return {"seeded": False, "kpis": [], "message": "No KPI data. Call POST /api/esg/seed first."}
        return {
            "kpis": [k.to_dict() for k in kpis],
            "count": len(kpis),
            "on_track": sum(1 for k in kpis if k.to_dict()["on_track"]),
            "needs_attention": sum(1 for k in kpis if not k.to_dict()["on_track"]),
        }
    except Exception as e:
        logger.error(f"ESG KPIs error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/seed")
async def seed_esg_data():
    """Seed ESG engine with realistic demo data for a fuel distribution company."""
    try:
        result = esg_engine.seed_demo_data()
        return result
    except Exception as e:
        logger.error(f"ESG seed error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
