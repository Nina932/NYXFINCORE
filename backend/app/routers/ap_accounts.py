from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Dict, Any, Optional
from app.services.ap_automation import ap_engine, ExceptionStatus, ApprovalStatus
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ap", tags=["ap_automation"])

@router.get("/status")
async def get_ap_status():
    """Get high-level stats for the AP dashboard."""
    return ap_engine.get_stats()

@router.get("/pos")
async def list_purchase_orders():
    """List all known Purchase Orders."""
    return ap_engine.store.list_pos()

@router.get("/grns")
async def list_goods_receipts():
    """List all known Goods Receipt Notes."""
    return ap_engine.store.list_grns()

@router.post("/match")
async def match_invoice(invoice_data: Dict[str, Any]):
    """
    Run 3-way match for an invoice.
    Payload: {invoice_number, vendor_name, line_items[], total_amount, po_number?}
    """
    try:
        result = await ap_engine.match_invoice(invoice_data)
        return result
    except Exception as e:
        logger.error(f"Invoice matching failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/exceptions")
async def list_exceptions(status: str = "open"):
    """List match exceptions."""
    all_exc = ap_engine._exception_log
    if status == "all":
        return all_exc
    return [e for e in all_exc if e.get("status") == status]

@router.post("/exceptions/{index}/resolve")
async def resolve_exception(index: int, body: Dict[str, str]):
    """Resolve an exception."""
    resolution = body.get("resolution", "Resolved by user")
    user = body.get("user", "admin")
    result = ap_engine.resolve_exception(index, resolution, user)
    if not result:
        raise HTTPException(status_code=404, detail="Exception index not found")
    return result

@router.get("/approval-queue")
async def get_approval_queue():
    """Get matches pending approval."""
    return ap_engine.get_approval_queue()

@router.post("/approve/{match_id}")
async def approve_match(match_id: str, body: Dict[str, str]):
    """Approve a 3-way match result."""
    user = body.get("user", "admin")
    result = ap_engine.approve_match(match_id, user)
    if not result:
        raise HTTPException(status_code=404, detail="Match ID not found")
    return result

@router.post("/seed")
async def seed_data():
    """Seed the AP engine with sample POs and GRNs based on current financials."""
    try:
        # Try to get financial context for better seeding
        from app.services.data_store import data_store
        companies = data_store.list_companies()
        financials = {}
        if companies:
            co_id = companies[-1]["id"]
            periods = data_store.get_all_periods(co_id)
            if periods:
                financials = data_store.get_financials(co_id, periods[-1]) or {}
        
        return ap_engine.populate_sample_data(financials)
    except Exception as e:
        return ap_engine.populate_sample_data({})
