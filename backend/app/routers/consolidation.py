from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Dict, Any, Optional
from app.services.consolidation import consolidation_engine, Entity
from app.config import settings
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/consolidation", tags=["consolidation"])

@router.get("/entities")
async def list_entities():
    """List all entities in the consolidation group."""
    return consolidation_engine.list_entities()

@router.get("/status")
async def get_consolidation_status():
    """Get status of the consolidation engine."""
    return {
        "entity_count": len(consolidation_engine._entities),
        "group_structure": [
            {"parent": p, "subsidiaries": s} 
            for p, s in consolidation_engine._group_structures.items()
        ],
        "has_last_result": consolidation_engine.get_last_result() is not None
    }

@router.post("/consolidate")
async def run_consolidation(period: str):
    """Run full consolidation for a period."""
    try:
        result = consolidation_engine.consolidate(period)
        return result.to_dict()
    except Exception as e:
        logger.error(f"Consolidation failed for period {period}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/results/latest")
async def get_latest_result():
    """Get the most recent consolidation result."""
    res = consolidation_engine.get_last_result()
    if not res:
        raise HTTPException(status_code=404, detail="No consolidation run yet")
    return res.to_dict()

@router.post("/seed")
async def seed_consolidation_data(period: str = "2024-01"):
    """
    Seed consolidation engine with synthetic subsidiary data.
    Creates a Parent + 2 Subsidiaries (Georgia & International).
    """
    try:
        from app.services.data_store import data_store
        companies = data_store.list_companies()
        
        if not companies:
            # Create a mock parent if none exists
            parent_id = "1"
            parent_name = f"{settings.COMPANY_NAME} (Parent)"
        else:
            parent = companies[-1]
            parent_id = str(parent["id"])
            parent_name = parent["name"]

        # Register Parent
        consolidation_engine.register_entity(Entity(
            entity_id=parent_id,
            name=parent_name,
            is_parent=True,
            currency="GEL"
        ))

        # Register Subsidiary A (Local, 100%)
        consolidation_engine.register_entity(Entity(
            entity_id="sub_a",
            name="SGP Logistics LLC",
            parent_entity_id=parent_id,
            ownership_pct=100.0,
            currency="GEL"
        ))

        # Register Subsidiary B (International, 80%)
        consolidation_engine.register_entity(Entity(
            entity_id="sub_b",
            name="SGP TRADING UAE",
            parent_entity_id=parent_id,
            ownership_pct=80.0,
            currency="USD"
        ))

        # Define Structure
        consolidation_engine.set_group_structure(
            parent_id, 
            [("sub_a", 100.0), ("sub_b", 80.0)]
        )

        return {"status": "seeded", "parent": parent_name, "subsidiaries": ["SGP Logistics LLC", "SGP TRADING UAE"]}
    except Exception as e:
        logger.error(f"Seeding failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
