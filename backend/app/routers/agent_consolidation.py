"""
FinAI Agent Consolidation Sub-Router
======================================
IFRS 10 multi-entity consolidation endpoints.
Covers: entity registration, group structure, consolidation runs,
        Signal-Diagnosis-Action analysis, FX rates, IC checks, audit trail.
"""
from fastapi import APIRouter
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)
router = APIRouter()  # NO prefix — parent adds /api/agent

# In-memory audit trail for consolidation runs
_audit_trail: List[Dict[str, Any]] = []


# ---------------------------------------------------------------------------
# 1. POST /agents/consolidation/register-entity
# ---------------------------------------------------------------------------
@router.post("/agents/consolidation/register-entity")
async def register_entity(body: dict):
    """Register a legal entity for consolidation."""
    try:
        from app.services.consolidation import consolidation_engine, Entity

        entity = Entity(
            entity_id=body["entity_id"],
            name=body["name"],
            parent_entity_id=body.get("parent_entity_id"),
            ownership_pct=body.get("ownership_pct", 100.0),
            currency=body.get("currency", "GEL"),
            is_parent=body.get("is_parent", False),
            industry=body.get("industry", "fuel_distribution"),
        )
        eid = consolidation_engine.register_entity(entity)
        return {
            "status": "registered",
            "entity_id": eid,
            "name": entity.name,
            "ownership_pct": entity.ownership_pct,
            "currency": entity.currency,
        }
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# 2. POST /agents/consolidation/set-group
# ---------------------------------------------------------------------------
@router.post("/agents/consolidation/set-group")
async def set_group(body: dict):
    """Set group structure (parent + subsidiaries with ownership)."""
    try:
        from app.services.consolidation import consolidation_engine

        parent_id = body["parent_id"]
        children = body.get("children", [])
        child_tuples = [
            (c["entity_id"], c.get("ownership_pct", 100.0))
            for c in children
        ]
        consolidation_engine.set_group_structure(parent_id, child_tuples)
        return {
            "status": "group_set",
            "parent_id": parent_id,
            "subsidiaries": [
                {"entity_id": eid, "ownership_pct": pct}
                for eid, pct in child_tuples
            ],
        }
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# 3. GET /agents/consolidation/entities
# ---------------------------------------------------------------------------
@router.get("/agents/consolidation/entities")
async def list_entities():
    """List all registered entities."""
    try:
        from app.services.consolidation import consolidation_engine

        entities = consolidation_engine.list_entities()
        return {"entities": entities, "count": len(entities)}
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# 4. POST /agents/consolidation/run
# ---------------------------------------------------------------------------
@router.post("/agents/consolidation/run")
async def run_consolidation(body: dict):
    """Run full IFRS 10 consolidation for a period."""
    try:
        from app.services.consolidation import consolidation_engine

        period = body.get("period", "2024-01")
        fx_rates = body.get("fx_rates")
        if fx_rates:
            consolidation_engine.set_fx_rates(fx_rates)

        result = consolidation_engine.consolidate(period)
        result_dict = result.to_dict()

        # Record in audit trail
        _audit_trail.append({
            "action": "consolidation_run",
            "period": period,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "entity_count": len(result.individual_statements),
            "elimination_count": len(result.eliminations),
            "status": "success",
        })

        return result_dict
    except Exception as e:
        _audit_trail.append({
            "action": "consolidation_run",
            "period": body.get("period", "unknown"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "error",
            "error": str(e),
        })
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# 5. POST /agents/consolidation/analyze
# ---------------------------------------------------------------------------
@router.post("/agents/consolidation/analyze")
async def analyze_consolidation(body: dict):
    """Run full Signal -> Diagnosis -> Action pipeline via ConsolidationAgent."""
    try:
        from app.services.consolidation import consolidation_engine, Entity

        period = body.get("period", "2024-01")

        # Auto-register entities if provided inline
        entities_data = body.get("entities", [])
        for ed in entities_data:
            entity = Entity(
                entity_id=ed["entity_id"],
                name=ed["name"],
                parent_entity_id=ed.get("parent_entity_id"),
                ownership_pct=ed.get("ownership_pct", 100.0),
                currency=ed.get("currency", "GEL"),
                is_parent=ed.get("is_parent", False),
                industry=ed.get("industry", "fuel_distribution"),
            )
            consolidation_engine.register_entity(entity)

        # Try ConsolidationAgent first; fall back to raw consolidation
        try:
            from app.agents.consolidation_agent import consolidation_agent
            analysis = await consolidation_agent.run_consolidation_analysis(period)

            _audit_trail.append({
                "action": "consolidation_analyze",
                "period": period,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "pipeline": "signal_diagnosis_action",
                "status": "success",
            })

            # If analysis is an object with to_dict, convert
            if hasattr(analysis, "to_dict"):
                return analysis.to_dict()
            if isinstance(analysis, dict):
                return analysis
            return {"result": str(analysis)}

        except ImportError:
            logger.warning(
                "ConsolidationAgent not available, falling back to raw consolidation"
            )
            result = consolidation_engine.consolidate(period)
            result_dict = result.to_dict()

            _audit_trail.append({
                "action": "consolidation_analyze",
                "period": period,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "pipeline": "raw_consolidation_fallback",
                "status": "success",
            })

            return {
                "consolidation": result_dict,
                "note": "ConsolidationAgent not yet available; raw consolidation returned.",
            }

    except Exception as e:
        import traceback
        logger.error("Consolidation analyze error: %s\n%s", e, traceback.format_exc())
        _audit_trail.append({
            "action": "consolidation_analyze",
            "period": body.get("period", "unknown"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "error",
            "error": str(e),
        })
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# 6. GET /agents/consolidation/last
# ---------------------------------------------------------------------------
@router.get("/agents/consolidation/last")
async def last_consolidation():
    """Return the last consolidation result."""
    try:
        from app.services.consolidation import consolidation_engine

        result = consolidation_engine.get_last_result()
        if result is None:
            return {"status": "no_consolidation_run", "result": None}
        return result.to_dict()
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# 7. POST /agents/consolidation/fx-rates
# ---------------------------------------------------------------------------
@router.post("/agents/consolidation/fx-rates")
async def update_fx_rates(body: dict):
    """Update FX rates for currency translation."""
    try:
        from app.services.consolidation import consolidation_engine

        rates = body.get("rates", {})
        if not rates:
            return {"error": "No rates provided. Expected {\"rates\": {\"USD\": 2.70, ...}}"}

        consolidation_engine.set_fx_rates(rates)

        _audit_trail.append({
            "action": "fx_rates_update",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "rates_updated": list(rates.keys()),
        })

        return {
            "status": "fx_rates_updated",
            "rates": rates,
        }
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# 8. POST /agents/consolidation/ic-check
# ---------------------------------------------------------------------------
@router.post("/agents/consolidation/ic-check")
async def ic_check(body: dict):
    """Run intercompany reconciliation check between two entities."""
    try:
        from app.services.consolidation import consolidation_engine

        entity_a_id = body["entity_a"]
        entity_b_id = body["entity_b"]
        period = body.get("period", "2024-01")

        # Validate entities exist
        entity_a = consolidation_engine.get_entity(entity_a_id)
        entity_b = consolidation_engine.get_entity(entity_b_id)
        if not entity_a:
            return {"error": f"Entity not found: {entity_a_id}"}
        if not entity_b:
            return {"error": f"Entity not found: {entity_b_id}"}

        # Fetch financials for both entities
        fin_a = entity_a.get_financials(period)
        fin_b = entity_b.get_financials(period)

        # Run IC matching + unmatched identification
        matcher = consolidation_engine._matcher
        eliminations = matcher.match_transactions(
            entity_a_id, fin_a, entity_b_id, fin_b,
        )
        unmatched = matcher.identify_unmatched(
            entity_a_id, fin_a, entity_b_id, fin_b,
        )

        _audit_trail.append({
            "action": "ic_check",
            "entity_a": entity_a_id,
            "entity_b": entity_b_id,
            "period": period,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "eliminations_found": len(eliminations),
            "unmatched_items": len(unmatched),
        })

        return {
            "entity_a": entity_a_id,
            "entity_b": entity_b_id,
            "period": period,
            "eliminations": [e.to_dict() for e in eliminations],
            "unmatched_items": unmatched,
            "summary": {
                "total_eliminations": len(eliminations),
                "total_unmatched": len(unmatched),
                "has_mismatches": len(unmatched) > 0,
            },
        }
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# 9. GET /agents/consolidation/audit-trail
# ---------------------------------------------------------------------------
@router.get("/agents/consolidation/audit-trail")
async def get_audit_trail():
    """Return audit trail of all consolidation operations."""
    try:
        return {
            "audit_trail": list(reversed(_audit_trail)),
            "total_entries": len(_audit_trail),
        }
    except Exception as e:
        return {"error": str(e)}
