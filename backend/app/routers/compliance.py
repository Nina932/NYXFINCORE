from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Dict, Any, Optional
from app.services.monitoring_engine_v1 import monitoring_engine
from app.services.auth_audit_v1 import auth_audit
from app.services.lineage import lineage_graph
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/compliance", tags=["compliance"])

@router.get("/dashboard")
async def get_compliance_dashboard():
    """Get full monitoring and compliance dashboard."""
    return monitoring_engine.get_dashboard().to_dict()

@router.get("/alerts")
async def list_active_alerts():
    """List all active compliance and monitoring alerts."""
    alerts = monitoring_engine.alert_manager.get_active_alerts()
    return [a.to_dict() for a in alerts]

@router.get("/audit-log")
async def get_audit_log(limit: int = 100):
    """Get the authentication and access audit log."""
    # Note: in a real app, 'db' would be injected via Depends
    # For now, we use the in-memory fallback which is populated during the session
    return await auth_audit.get_recent_events(None, limit=limit)

@router.get("/lineage")
async def get_data_lineage(dataset_id: Optional[str] = None):
    """Get data lineage for a specific dataset or the entire system."""
    try:
        if dataset_id:
            return lineage_graph.get_lineage(dataset_id)
        return lineage_graph.build_graph()
    except Exception as e:
        return {"nodes": [], "edges": [], "error": str(e)}

@router.post("/check")
async def run_compliance_check(period: str = "current"):
    """Trigger a manual compliance and monitoring check."""
    try:
        # Get latest financials for checking
        from app.services.data_store import data_store
        companies = data_store.list_companies()
        if not companies:
            raise HTTPException(status_code=404, detail="No companies found")
        
        co_id = companies[-1]["id"]
        if period == "current":
            periods = data_store.get_all_periods(co_id)
            period = periods[-1] if periods else "2024-01"
            
        financials = data_store.get_financials(co_id, period) or {}
        bs = data_store.get_balance_sheet(co_id, period) or {}
        
        alerts = monitoring_engine.run_checks(financials, bs)
        return {"status": "checked", "new_alerts": len(alerts), "period": period}
    except Exception as e:
        logger.error(f"Compliance check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/kpis")
async def get_kpi_status():
    """Get status of all KPIs against targets."""
    # We need financials to evaluate
    from app.services.data_store import data_store
    companies = data_store.list_companies()
    if not companies:
        return []
    
    co_id = companies[-1]["id"]
    periods = data_store.get_all_periods(co_id)
    if not periods:
        return []
        
    financials = data_store.get_financials(co_id, periods[-1]) or {}
    return [s.to_dict() for s in monitoring_engine.kpi_watcher.evaluate(financials)]
