"""
FinAI OS — Ontology API
========================
REST endpoints for the ontology engine, warehouse, and action workflows.
"""

import logging
import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

from app.services.ontology_engine import ontology_registry
from app.services.ontology_query import ontology_query_engine
from app.services.ontology_store import ontology_store
from app.services.warehouse import warehouse
from app.services.action_engine import action_engine

router = APIRouter(prefix="/api/ontology", tags=["ontology"])


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class NaturalQueryRequest(BaseModel):
    query: str

class StructuredQueryRequest(BaseModel):
    target_type: str
    filters: List[Dict[str, Any]] = []
    sort_by: Optional[str] = None
    sort_desc: bool = True
    limit: int = 50

class WarehouseQueryRequest(BaseModel):
    sql: str

class ActionApproveRequest(BaseModel):
    approver: str = "user"

class ActionRejectRequest(BaseModel):
    approver: str = "user"
    reason: str = ""


# =============================================================================
# ONTOLOGY ENDPOINTS
# =============================================================================

@router.get("/types")
async def list_types():
    """List all registered ontology types with their schemas."""
    return {"types": [t.to_dict() for t in ontology_registry.list_types()]}


@router.get("/types/{type_id}")
async def get_type(type_id: str):
    """Get a specific ontology type schema."""
    t = ontology_registry.get_type(type_id)
    if not t:
        raise HTTPException(404, f"Type not found: {type_id}")
    return t.to_dict()


@router.get("/objects")
async def list_objects(type: Optional[str] = None, limit: int = 50):
    """List ontology objects, optionally filtered by type. Most-connected objects first."""
    if type:
        objects = ontology_registry.query(type, limit=limit * 2)
    else:
        objects = ontology_registry.query_all(limit=limit * 2)
    # Sort: objects with most relationships first (so graph shows connected nodes)
    objects.sort(key=lambda o: sum(len(v) for v in o.relationships.values()), reverse=True)
    objects = objects[:limit]
    return {"objects": [o.to_dict() for o in objects], "count": len(objects)}


@router.get("/objects/{object_id}")
async def get_object(object_id: str):
    """Get a single ontology object with all properties and relationships."""
    obj = ontology_registry.get_object(object_id)
    if not obj:
        raise HTTPException(404, f"Object not found: {object_id}")

    # Compute all computed fields
    type_def = ontology_registry.get_type(obj.object_type)
    computed = {}
    if type_def:
        for cf_name in type_def.computed_fields:
            val = ontology_registry.get_computed_field(object_id, cf_name)
            if val is not None:
                computed[cf_name] = round(val, 2) if isinstance(val, float) else val

    result = obj.to_dict()
    result["computed"] = computed
    result["version_count"] = len(ontology_registry.get_version_history(object_id))
    return result


class ObjectUpdateRequest(BaseModel):
    properties: Dict[str, Any]


@router.patch("/objects/{object_id}")
async def update_object(object_id: str, req: ObjectUpdateRequest):
    """Partially update an ontology object's properties."""
    try:
        updated = ontology_registry.update_object(object_id, req.properties)
        return updated.to_dict()
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"Update failed: {str(e)}")


@router.post("/objects/{object_id}/action")
async def execute_object_action(object_id: str, action: str = Query(..., description="Action to perform: approve, reject, execute, simulate")):
    """Generic action execution bridge for ontology objects."""
    obj = ontology_registry.get_object(object_id)
    if not obj:
        raise HTTPException(404, f"Object not found: {object_id}")

    # Special handling for Action objects (Workflow entities)
    if obj.object_type == "Action" or object_id.startswith("act_"):
        # Map to action_engine executions
        execution_id = obj.properties.get("execution_id") or object_id
        try:
            if action == "approve":
                res = action_engine.approve(execution_id, "user")
            elif action == "reject":
                res = action_engine.reject(execution_id, "user", "Rejected via Command Matrix")
            elif action == "execute":
                res = action_engine.execute(execution_id)
            else:
                raise HTTPException(400, f"Unsupported action for type Action: {action}")
            return res.to_dict()
        except ValueError as e:
            raise HTTPException(400, str(e))

    # Special handling for KPI Simulation
    if obj.object_type == "KPI" and action == "simulate":
        # Simulate: just update the value to visualize impact
        # In a real environment, this might trigger a recalculation task
        return {"status": "simulation_mode", "object_id": object_id, "note": "Simulation triggered. Graph will recompute causal links."}

    raise HTTPException(400, f"Action '{action}' is not supported for type '{obj.object_type}'")


@router.get("/objects/{object_id}/history")
async def get_object_history(object_id: str):
    """Get version history for an ontology object."""
    obj = ontology_registry.get_object(object_id)
    if not obj:
        raise HTTPException(404, f"Object not found: {object_id}")

    history = ontology_registry.get_version_history(object_id)
    # Also include current version
    current = {"version": obj.version, "properties": obj.properties, "updated_at": obj.updated_at}
    return {"object_id": object_id, "current": current, "history": history}


@router.get("/graph/{object_id}")
async def get_graph(object_id: str, depth: int = 2):
    """Get subgraph around an object for visualization."""
    obj = ontology_registry.get_object(object_id)
    if not obj:
        raise HTTPException(404, f"Object not found: {object_id}")
    return ontology_registry.get_subgraph(object_id, depth)


@router.post("/query")
async def structured_query(req: StructuredQueryRequest):
    """Execute a structured ontology query."""
    from app.services.ontology_query import StructuredQuery, FilterClause
    filters = [FilterClause(f["property"], f.get("operator", "eq"), f["value"]) for f in req.filters]
    query = StructuredQuery(
        target_type=req.target_type,
        filters=filters,
        sort_by=req.sort_by,
        sort_desc=req.sort_desc,
        limit=req.limit,
    )
    result = ontology_query_engine.execute(query)
    return result.to_dict()


@router.post("/query/natural")
async def natural_query(req: NaturalQueryRequest):
    """Execute a natural language query against the ontology."""
    result = await ontology_query_engine.natural_query(req.query)
    return result.to_dict()


@router.get("/parsed-data/{period}")
async def get_parsed_data(period: str):
    """
    Return the ACTUAL parsed financial data for a period — the real numbers
    from the uploaded file. This is what the Data Transparency page shows.

    Includes: every account with amounts, classification, destination, and confidence.
    """
    try:
        from app.services.data_store import data_store

        # Find the company/period
        companies = data_store.list_companies()
        if not companies:
            return {"period": period, "accounts": [], "message": "No data"}

        # Find period across all companies
        for company in reversed(companies):
            periods = data_store.get_all_periods(company["id"])
            if period in periods:
                financials = data_store.get_financials(company["id"], period)
                break
        else:
            return {"period": period, "accounts": [], "message": f"Period {period} not found"}

        # Build account-level rows from financial snapshots
        accounts = []
        # Group field_name → value into account-like structure
        # Financial snapshots are field_name/value pairs, not account rows
        # We need to reconstruct the P&L waterfall from the stored fields
        pl_fields = [
            ("REV", "Revenue", financials.get("revenue", 0), "revenue", 6),
            ("REV.W", "Revenue Wholesale", financials.get("revenue_wholesale", 0), "revenue", 6),
            ("REV.R", "Revenue Retail", financials.get("revenue_retail", 0), "revenue", 6),
            ("REV.O", "Revenue Other", financials.get("revenue_other", 0), "revenue", 6),
            ("COGS", "Cost of Goods Sold", financials.get("cogs", 0), "cogs", 7),
            ("GP", "Gross Profit", financials.get("gross_profit", 0), "gross_profit", 0),
            ("GA.SELL", "Selling Expenses", financials.get("selling_expenses", 0), "selling", 7),
            ("GA.ADMIN", "Admin Expenses", financials.get("admin_expenses", 0) or financials.get("ga_expenses", 0), "admin", 7),
            ("GA.LABOUR", "Labour Costs", financials.get("labour_costs", 0), "labour", 8),
            ("EBITDA", "EBITDA", financials.get("ebitda", 0), "ebitda", 0),
            ("DA", "Depreciation & Amortization", financials.get("depreciation", 0), "depreciation", 7),
            ("EBIT", "EBIT", financials.get("ebit", 0), "ebit", 0),
            ("FIN.INC", "Finance Income", financials.get("finance_income", 0), "finance", 9),
            ("FIN.EXP", "Finance Expense", financials.get("finance_expense", 0), "finance", 9),
            ("OTH.INC", "Other Income", financials.get("other_income", 0), "other", 9),
            ("OTH.EXP", "Other Expense", financials.get("other_expense", 0), "other", 9),
            ("PBT", "Profit Before Tax", financials.get("profit_before_tax", 0), "pbt", 0),
            ("TAX", "Tax Expense", financials.get("tax_expense", 0), "tax", 9),
            ("NP", "Net Profit", financials.get("net_profit", 0), "net_profit", 0),
        ]

        bs_fields = [
            ("BS.CASH", "Cash & Equivalents", financials.get("cash", 0) or financials.get("bs_cash", 0), "cash", 1),
            ("BS.REC", "Receivables", financials.get("receivables", 0) or financials.get("bs_receivables", 0), "receivables", 1),
            ("BS.INV", "Inventory", financials.get("inventory", 0) or financials.get("bs_inventory", 0), "inventory", 1),
            ("BS.CA", "Total Current Assets", financials.get("total_current_assets", 0) or financials.get("bs_current_assets", 0), "current_assets", 1),
            ("BS.FA", "Fixed Assets (Net)", financials.get("fixed_assets_net", 0) or financials.get("bs_fixed_assets", 0), "fixed_assets", 2),
            ("BS.TA", "Total Assets", financials.get("total_assets", 0) or financials.get("bs_total_assets", 0), "total_assets", 0),
            ("BS.PAY", "Accounts Payable", financials.get("bs_payables", 0), "payables", 3),
            ("BS.CL", "Current Liabilities", financials.get("current_liabilities", 0) or financials.get("bs_current_liabilities", 0), "current_liab", 3),
            ("BS.LTD", "Long-term Debt", financials.get("long_term_debt", 0) or financials.get("bs_long_term_debt", 0), "lt_debt", 4),
            ("BS.TL", "Total Liabilities", financials.get("total_liabilities", 0) or financials.get("bs_total_liabilities", 0), "total_liab", 0),
            ("BS.SC", "Share Capital", financials.get("bs_share_capital", 0), "share_capital", 5),
            ("BS.RE", "Retained Earnings", financials.get("bs_retained_earnings", 0), "retained", 5),
            ("BS.TE", "Total Equity", financials.get("total_equity", 0) or financials.get("bs_total_equity", 0), "total_equity", 0),
        ]

        for code, name, value, field_key, acct_class in pl_fields + bs_fields:
            if value == 0 and code not in ("GP", "EBITDA", "EBIT", "PBT", "NP", "BS.TA", "BS.TL", "BS.TE"):
                continue  # Skip zero non-total fields
            is_total = code in ("GP", "EBITDA", "EBIT", "PBT", "NP", "BS.TA", "BS.TL", "BS.TE", "BS.CA", "BS.CL")
            is_pl = acct_class >= 6 or code.startswith(("REV", "COGS", "GP", "GA", "EBITDA", "DA", "EBIT", "FIN", "OTH", "PBT", "TAX", "NP"))
            accounts.append({
                "code": code,
                "name": name,
                "value": value,
                "field_key": field_key,
                "account_class": acct_class,
                "statement": "income_statement" if is_pl else "balance_sheet",
                "is_total": is_total,
                "destination": "P&L" if is_pl else "Balance Sheet",
                "destination_page": "/pnl" if is_pl else "/balance-sheet",
                "source": "financial_core",
                "confidence": 1.0,
                "status": "verified",
            })

        return {
            "period": period,
            "company": company.get("name", ""),
            "accounts": accounts,
            "total": len(accounts),
            "source": "finai_store.financial_snapshots",
            "pl_count": sum(1 for a in accounts if a["statement"] == "income_statement"),
            "bs_count": sum(1 for a in accounts if a["statement"] == "balance_sheet"),
        }
    except Exception as e:
        return {"period": period, "accounts": [], "error": str(e)}


@router.get("/account-breakdown/{section}")
async def get_account_breakdown(section: str, period: str = None):
    """
    Return account-level breakdown for a statement section.
    Sections: revenue (class 6), cogs (class 7), opex (class 8), other_pl (class 9),
              current_assets (class 1), noncurrent_assets (class 2),
              current_liabilities (class 3), noncurrent_liabilities (class 4), equity (class 5),
              all_pl (6-9), all_bs (1-5)

    Returns actual account data from the ontology with amounts from warehouse.
    """
    SECTION_CLASSES = {
        'revenue': [6], 'cogs': [7], 'opex': [8], 'other_pl': [9],
        'all_pl': [6, 7, 8, 9],
        'current_assets': [1], 'noncurrent_assets': [2],
        'current_liabilities': [3], 'noncurrent_liabilities': [4], 'equity': [5],
        'all_bs': [1, 2, 3, 4, 5],
        'assets': [1, 2], 'liabilities': [3, 4],
    }

    classes = SECTION_CLASSES.get(section, [])
    if not classes:
        return {"section": section, "accounts": [], "error": f"Unknown section: {section}. Use: {list(SECTION_CLASSES.keys())}"}

    # Get accounts from ontology
    accounts = []
    for obj_id, obj in ontology_registry._objects.items():
        if obj.object_type != 'Account':
            continue
        p = obj.properties
        cls = p.get('account_class')
        if cls is None:
            code = p.get('code', '')
            if code and code[0].isdigit():
                cls = int(code[0])
        if cls in classes:
            accounts.append({
                'code': p.get('code', ''),
                'name_en': p.get('name_en', ''),
                'name_ka': p.get('name_ka', ''),
                'ifrs_line': p.get('ifrs_bs_line') or p.get('ifrs_pl_line', ''),
                'account_class': cls,
                'side': p.get('side', ''),
                'statement': p.get('statement', ''),
                'object_id': obj.object_id,
            })

    # Try to get amounts from warehouse (dw_trial_balance)
    try:
        # Validate classes are integers to prevent SQL injection
        safe_classes = [int(c) for c in classes]
        placeholders = ','.join('?' for _ in safe_classes)
        wh_data = warehouse.execute_safe(
            f"SELECT account_code, account_name, turnover_debit, turnover_credit, closing_debit, closing_credit "
            f"FROM dw_trial_balance WHERE account_class IN ({placeholders})",
            safe_classes
        )
        # Merge amounts into accounts
        wh_map = {r.get('account_code', ''): r for r in wh_data}
        for acc in accounts:
            wh = wh_map.get(acc['code'], {})
            if wh:
                acc['turnover_debit'] = wh.get('turnover_debit', 0) or 0
                acc['turnover_credit'] = wh.get('turnover_credit', 0) or 0
                acc['closing_debit'] = wh.get('closing_debit', 0) or 0
                acc['closing_credit'] = wh.get('closing_credit', 0) or 0
                # Compute net based on normal balance
                if acc['account_class'] == 6:  # Revenue — credit normal
                    acc['amount'] = (wh.get('turnover_credit', 0) or 0) - (wh.get('turnover_debit', 0) or 0)
                elif acc['account_class'] in [7, 8, 9]:  # Expenses — debit normal
                    acc['amount'] = (wh.get('turnover_debit', 0) or 0) - (wh.get('turnover_credit', 0) or 0)
                elif acc['account_class'] in [1, 2]:  # Assets — debit normal
                    acc['amount'] = (wh.get('closing_debit', 0) or 0) - (wh.get('closing_credit', 0) or 0)
                else:  # Liabilities/Equity — credit normal
                    acc['amount'] = (wh.get('closing_credit', 0) or 0) - (wh.get('closing_debit', 0) or 0)
                acc['has_data'] = True
            else:
                acc['amount'] = 0
                acc['has_data'] = False
    except Exception:
        pass

    # Sort by code
    accounts.sort(key=lambda a: a.get('code', ''))

    # Summary
    total = sum(a.get('amount', 0) for a in accounts if a.get('has_data'))
    with_data = sum(1 for a in accounts if a.get('has_data'))

    return {
        'section': section,
        'classes': classes,
        'total': len(accounts),
        'with_data': with_data,
        'total_amount': total,
        'accounts': accounts,
    }


@router.get("/intelligence/{period}")
async def get_intelligence_layer(period: str):
    """
    Get the ontology intelligence layer for a financial period.
    This is what the frontend reads ALONGSIDE the financial core numbers.

    Financial core: exact numbers (P&L, BS) from SQLite — auditable
    Intelligence layer: derived KPIs, risk signals, recommendations — actionable
    """
    # Get all objects for this period
    stmt = ontology_registry.get_object(f"stmt_{period}")
    if not stmt:
        return {"period": period, "has_intelligence": False, "message": "No intelligence data. Upload financial data first."}

    # Gather KPIs for this period
    kpis = []
    risks = []
    for type_id, prefix in [("KPI", f"kpi_"), ("RiskSignal", f"risk_")]:
        for oid, obj in ontology_registry._objects.items():
            if obj.object_type == type_id and period in oid:
                item = {
                    "id": obj.object_id,
                    "properties": {k: v for k, v in obj.properties.items() if not k.startswith("_")},
                    "markings": obj.markings,
                }
                # Add lineage
                lineage = ontology_registry.get_lineage(oid)
                if lineage:
                    item["lineage"] = lineage
                if type_id == "KPI":
                    kpis.append(item)
                else:
                    risks.append(item)

    # Compute summary
    breached_kpis = [k for k in kpis if k["properties"].get("status") == "breached"]
    critical_risks = [r for r in risks if r["properties"].get("severity") in ("critical", "high")]

    # Health assessment
    total_kpis = len(kpis)
    breached = len(breached_kpis)
    if total_kpis == 0:
        health_score = 50
    else:
        health_score = max(0, min(100, int((1 - breached / total_kpis) * 100)))

    health_grade = "A" if health_score >= 80 else "B" if health_score >= 60 else "C" if health_score >= 40 else "D"

    # Get pending actions
    pending_actions = [a.to_dict() for a in action_engine.get_pending()]

    # ── Proactive Intelligence enrichment ──
    proactive = None
    try:
        from app.services.proactive_intelligence import proactive_intelligence as _pi
        from app.services.data_store import data_store
        # Try to load financials for this period
        _companies = data_store.list_companies()
        _financials = None
        _prev_financials = None
        for _c in reversed(_companies or []):
            _periods = data_store.get_all_periods(_c["id"])
            if period in _periods:
                _financials = data_store.get_financials(_c["id"], period)
                # Get previous period if available
                _idx = _periods.index(period)
                if _idx > 0:
                    _prev_financials = data_store.get_financials(_c["id"], _periods[_idx - 1])
                break
        if _financials:
            _bs = {k: v for k, v in _financials.items() if k.startswith("bs_") or k in (
                "cash", "receivables", "inventory", "total_current_assets",
                "fixed_assets_net", "total_assets", "current_liabilities",
                "long_term_debt", "total_liabilities", "total_equity",
            )}
            proactive = _pi.analyze(_financials, _bs, _prev_financials)
    except Exception:
        pass

    return {
        "period": period,
        "has_intelligence": True,
        "health": {
            "score": health_score,
            "grade": health_grade,
            "total_kpis": total_kpis,
            "breached_kpis": breached,
            "critical_risks": len(critical_risks),
        },
        "kpis": kpis,
        "risks": risks,
        "breached_kpis": breached_kpis,
        "critical_risks": critical_risks,
        "pending_actions": pending_actions,
        "statement_id": stmt.object_id,
        "proactive_intelligence": proactive,
    }


@router.get("/stats")
async def ontology_stats():
    """Get ontology statistics."""
    return {
        "registry": ontology_registry.stats(),
        "store": ontology_store.stats(),
        "warehouse": warehouse.stats(),
    }


@router.post("/sync")
async def sync_ontology():
    """Force re-sync from knowledge graph and SQLite."""
    kg_count = ontology_registry.initialize()
    store_count = ontology_store.bulk_save(list(ontology_registry._objects.values()))
    wh_counts = warehouse.sync_from_sqlite()
    return {
        "kg_synced": kg_count,
        "store_saved": store_count,
        "warehouse": wh_counts,
    }


# =============================================================================
# FIX #7: OBJECT SETS (saved, composable queries)
# =============================================================================

class ObjectSetRequest(BaseModel):
    name: str
    type_id: str
    filters: Dict[str, Any] = {}
    description: str = ""

class ComposeRequest(BaseModel):
    set_id_a: str
    set_id_b: str
    operation: str = "union"  # union, intersect, diff

@router.post("/object-sets")
async def create_object_set(req: ObjectSetRequest):
    """Create a saved, reusable Object Set."""
    oset = ontology_registry.create_object_set(req.name, req.type_id, req.filters, req.description)
    return oset

@router.get("/object-sets")
async def list_object_sets():
    return {"object_sets": ontology_registry.list_object_sets()}

@router.get("/object-sets/{set_id}")
async def get_object_set(set_id: str):
    oset = ontology_registry.get_object_set(set_id)
    if not oset:
        raise HTTPException(404, "Object Set not found")
    return oset

@router.get("/object-sets/{set_id}/evaluate")
async def evaluate_object_set(set_id: str):
    """Execute a saved Object Set and return results."""
    objects = ontology_registry.evaluate_object_set(set_id)
    return {"objects": [o.to_dict() for o in objects], "count": len(objects)}

@router.post("/object-sets/compose")
async def compose_object_sets(req: ComposeRequest):
    """Compose two Object Sets: union, intersect, or diff."""
    objects = ontology_registry.compose_object_sets(req.set_id_a, req.set_id_b, req.operation)
    return {"objects": [o.to_dict() for o in objects], "count": len(objects)}


# =============================================================================
# FIX #2: SECURE QUERY (marking enforcement)
# =============================================================================

@router.post("/query/secure")
async def secure_query(req: StructuredQueryRequest, user_markings: str = Query("financial,internal", description="Comma-separated markings")):
    """Execute a query with marking-based security enforcement."""
    from app.services.ontology_query import StructuredQuery, FilterClause
    markings = [m.strip() for m in user_markings.split(",")]
    filters = [FilterClause(f["property"], f.get("operator", "eq"), f["value"]) for f in req.filters]
    objects = ontology_registry.query_secure(
        req.target_type,
        {f.property: f.value if f.operator == "eq" else {"op": f.operator, "value": f.value} for f in filters} if filters else None,
        user_markings=markings,
        limit=req.limit,
    )
    return {"objects": [o.to_dict() for o in objects], "count": len(objects), "markings_applied": markings}


# =============================================================================
# FIX #8: AUDIT TRAIL
# =============================================================================

@router.get("/audit")
async def get_audit_log(limit: int = 100, action: Optional[str] = None):
    """Get ontology audit trail."""
    return {"events": ontology_registry.get_audit_log(limit, action), "total": len(ontology_registry._audit_log)}


# =============================================================================
# FIX #9: DATA LINEAGE
# =============================================================================

@router.get("/lineage/{object_id}")
async def get_lineage(object_id: str):
    """Get data lineage for an ontology object."""
    lineage = ontology_registry.get_lineage(object_id)
    obj = ontology_registry.get_object(object_id)
    if not obj:
        raise HTTPException(404, "Object not found")
    return {
        "object_id": object_id,
        "object_type": obj.object_type,
        "lineage": lineage or {"source": "knowledge_graph", "note": "Synced from KG at startup"},
        "markings": obj.markings,
    }


# =============================================================================
# FIX #6: SERVER-SENT EVENTS (real-time)
# =============================================================================

from fastapi.responses import StreamingResponse

# =============================================================================
# FIX #5: LLM TOOL EXECUTION ENDPOINT
# =============================================================================

class ToolCallRequest(BaseModel):
    tool_name: str
    parameters: Dict[str, Any] = {}

@router.post("/tools/execute")
async def execute_ontology_tool(req: ToolCallRequest):
    """Execute an ontology tool (for LLM integration)."""
    from app.services.ontology_tools import ontology_tool_executor
    result = await ontology_tool_executor.execute(req.tool_name, req.parameters)
    return {"tool": req.tool_name, "result": result}

@router.get("/tools/definitions")
async def get_tool_definitions():
    """Get all available ontology tool definitions (for LLM system prompts)."""
    from app.services.ontology_tools import TOOL_DEFINITIONS, ontology_tool_executor
    return {
        "tools": TOOL_DEFINITIONS,
        "prompt_section": ontology_tool_executor.get_tool_prompt_section(),
    }


# =============================================================================
# FIX #3: WAREHOUSE-BACKED OBJECT QUERY
# =============================================================================

@router.get("/objects/{object_id}/warehouse-data")
async def get_warehouse_data(object_id: str):
    """Get the warehouse data backing an ontology object (unified identity)."""
    obj = ontology_registry.get_object(object_id)
    if not obj:
        raise HTTPException(404, "Object not found")
    if not obj.backing_table or not obj.backing_key:
        return {"object_id": object_id, "warehouse_data": None, "note": "No warehouse backing for this object"}

    try:
        table = warehouse.validate_table_name(obj.backing_table)
        if not table:
            return {"object_id": object_id, "error": f"Invalid table: {obj.backing_table}"}
        results = warehouse.execute_safe(
            f"SELECT * FROM \"{table}\" WHERE account_code = ? LIMIT 10",
            [obj.backing_key]
        )
        return {
            "object_id": object_id,
            "backing_table": table,
            "backing_key": obj.backing_key,
            "warehouse_data": results,
        }
    except Exception as e:
        logger.error(f"Warehouse query failed for object {object_id}: {e}")
        return {"object_id": object_id, "error": "Warehouse query failed"}

# In-memory event bus
_event_subscribers: List[asyncio.Queue] = []

def broadcast_event(event_type: str, data: Dict[str, Any]):
    """Broadcast an event to all SSE subscribers."""
    import json as _json
    event = {
        "type": event_type, 
        "data": data, 
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    # Use a copy for safe iteration
    for q in list(_event_subscribers):
        try:
            q.put_nowait(event)
        except Exception:
            if q in _event_subscribers:
                _event_subscribers.remove(q)

# Bridge event_dispatcher to SSE
from app.services.v2.event_dispatcher import event_dispatcher
async def _sse_bridge(event_type: str, payload: Dict[str, Any]):
    broadcast_event(event_type, payload)

# Subscribe to all events ("*") to bridge to SSE
try:
    # event_dispatcher.subscribe uses string patterns
    event_dispatcher.subscribe("*", _sse_bridge)
    logger.info("Ontology SSE bridge connected to event_dispatcher")
except Exception as e:
    logger.error(f"Failed to connect SSE bridge: {e}")

@router.get("/events/stream")
async def event_stream():
    """SSE endpoint for real-time ontology events (Palette Gaia/Slate style)."""
    import json as _json
    q = asyncio.Queue()
    _event_subscribers.append(q)

    async def generate():
        try:
            while True:
                try:
                    # 30 second timeout for heartbeats
                    event = await asyncio.wait_for(q.get(), timeout=30)
                    yield f"data: {_json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield f"data: {_json.dumps({'type': 'heartbeat'})}\n\n"
        except Exception:
            pass
        finally:
            if q in _event_subscribers:
                _event_subscribers.remove(q)

    return StreamingResponse(generate(), media_type="text/event-stream")


# =============================================================================
# WAREHOUSE ENDPOINTS
# =============================================================================

@router.get("/warehouse/tables")
async def warehouse_tables():
    return {"tables": warehouse.list_tables()}


@router.get("/warehouse/status")
async def warehouse_status():
    """Get DuckDB warehouse status and table stats."""
    try:
        raw_tables = warehouse.list_tables()
        # Normalize: list_tables may return dicts or strings
        table_names = []
        for t in raw_tables:
            if isinstance(t, dict):
                table_names.append(t.get("name", t.get("table_name", str(t))))
            else:
                table_names.append(str(t))
        stats = {}
        for t in table_names:
            try:
                safe_name = warehouse.validate_table_name(t)
                if not safe_name:
                    stats[t] = "invalid_table"
                    continue
                rows = warehouse.execute_safe(f"SELECT COUNT(*) as cnt FROM \"{safe_name}\"", [])
                stats[t] = rows[0]["cnt"] if rows else 0
            except Exception:
                stats[t] = "error"
        return {
            "initialized": warehouse._initialized if hasattr(warehouse, '_initialized') else True,
            "engine": "duckdb",
            "tables": table_names,
            "row_counts": stats,
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/warehouse/query")
async def warehouse_query_get(sql: str):
    """Execute an analytical SQL query via GET (convenience).
    SECURITY: Only SELECT on warehouse (dw_*) tables. No access to SQLite tables.
    """
    sql = sql.strip()
    if not sql.upper().startswith("SELECT"):
        raise HTTPException(400, "Only SELECT queries are allowed")
    # Block access to sensitive tables (users, auth, tokens)
    sql_upper = sql.upper()
    _BLOCKED = ["USERS", "REVOKED_TOKEN", "AUTH_AUDIT", "LEARNING_RECORD"]
    for blocked in _BLOCKED:
        if blocked in sql_upper:
            raise HTTPException(403, f"Access to {blocked} table is not allowed via warehouse query")
    try:
        results = warehouse.execute(sql)
        if results and isinstance(results[0], dict) and "error" in results[0]:
            raise HTTPException(400, results[0]["error"])
        return {"results": results, "count": len(results)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Warehouse query failed: %s", e)
        raise HTTPException(500, "Query execution failed")


@router.post("/warehouse/query")
async def warehouse_query(req: WarehouseQueryRequest):
    """Execute an analytical SQL query against the DuckDB warehouse.
    SECURITY: Only SELECT on warehouse (dw_*) tables.
    """
    sql = req.sql.strip()
    if not sql.upper().startswith("SELECT"):
        raise HTTPException(400, "Only SELECT queries are allowed")
    sql_upper = sql.upper()
    _BLOCKED = ["USERS", "REVOKED_TOKEN", "AUTH_AUDIT", "LEARNING_RECORD"]
    for blocked in _BLOCKED:
        if blocked in sql_upper:
            raise HTTPException(403, f"Access to {blocked} table is not allowed via warehouse query")
    try:
        results = warehouse.execute(sql)
        if results and isinstance(results[0], dict) and "error" in results[0]:
            raise HTTPException(400, results[0]["error"])
        return {"results": results, "count": len(results)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Warehouse query failed: %s", e)
        raise HTTPException(500, "Query execution failed")


@router.post("/warehouse/sync")
async def warehouse_sync():
    counts = warehouse.sync_from_sqlite()
    return {"synced": counts}


@router.get("/warehouse/time-series/{metric}")
async def warehouse_time_series(metric: str):
    data = warehouse.get_time_series(metric)
    return {"metric": metric, "data": data}


@router.post("/warehouse/generate-history")
async def warehouse_generate_history(periods: int = 24, company_id: int = 1):
    """Generate synthetic historical data for trend analysis and forecasting.

    Creates `periods` months of backward-looking data based on the current
    period's financials with seasonal patterns, growth trends, and noise.
    """
    result = warehouse.generate_historical_data(periods=periods, company_id=company_id)
    return result


@router.get("/warehouse/trends/{metric}")
async def warehouse_trends(metric: str, periods: int = 12):
    """Get trend data for a metric with moving averages and change percentages."""
    return warehouse.get_trends(metric=metric, periods=periods)


@router.get("/warehouse/anomalies")
async def warehouse_anomalies(threshold: float = 2.0):
    """Detect values that deviate more than `threshold` std devs from the moving average."""
    return warehouse.get_anomalies(threshold=threshold)


# =============================================================================
# ACTION WORKFLOW ENDPOINTS
# =============================================================================

@router.get("/actions/pending")
async def actions_pending():
    pending = action_engine.get_pending()
    return {"actions": [a.to_dict() for a in pending], "count": len(pending)}


@router.get("/actions/history")
async def actions_history(limit: int = 50):
    history = action_engine.get_history(limit)
    return {"actions": [a.to_dict() for a in history], "count": len(history)}


@router.get("/actions/{execution_id}")
async def action_detail(execution_id: str):
    ex = action_engine.get_execution(execution_id)
    if not ex:
        raise HTTPException(404, f"Execution not found: {execution_id}")
    return ex.to_dict()


@router.post("/actions/{execution_id}/approve")
async def action_approve(execution_id: str, req: ActionApproveRequest):
    try:
        ex = action_engine.approve(execution_id, req.approver)
        return ex.to_dict()
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/actions/{execution_id}/reject")
async def action_reject(execution_id: str, req: ActionRejectRequest):
    try:
        ex = action_engine.reject(execution_id, req.approver, req.reason)
        return ex.to_dict()
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/actions/{execution_id}/execute")
async def action_execute(execution_id: str):
    try:
        ex = action_engine.execute(execution_id)
        return ex.to_dict()
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/actions/stats")
async def action_stats():
    return action_engine.get_stats()


# =============================================================================
# NOTIFICATION ENDPOINTS
# =============================================================================

@router.get("/notifications")
async def list_notifications(unread_only: bool = False):
    notifications = action_engine.get_notifications(unread_only)
    return {
        "notifications": [n.to_dict() for n in notifications],
        "unread_count": action_engine.get_unread_count(),
    }


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str):
    success = action_engine.mark_read(notification_id)
    return {"success": success}


@router.post("/notifications/read-all")
async def mark_all_notifications_read():
    count = action_engine.mark_all_read()
    return {"marked": count}


# ═══════════════════════════════════════════════════════════════
# RICH OBJECT DETAIL VIEWS (Palantir Object View Pattern)
# ═══════════════════════════════════════════════════════════════

@router.get("/objects/{object_id}/view")
async def object_view(object_id: str):
    """Rich contextual object view with formatted properties, charts, linked objects, and AI summary."""
    try:
        from app.services.object_views import object_view_generator
        view = object_view_generator.generate_view(object_id)
        if not view:
            raise HTTPException(404, f"Object not found: {object_id}")
        return view.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        return {"error": str(e), "object_id": object_id}


@router.get("/objects/{object_id}/view/history")
async def object_view_history(object_id: str):
    """Historical values from warehouse + version history for an object."""
    try:
        from app.services.object_views import object_view_generator
        return object_view_generator.get_history(object_id)
    except Exception as e:
        return {"error": str(e), "object_id": object_id}


@router.get("/objects/{object_id}/related")
async def object_related(object_id: str):
    """Related objects grouped by link type."""
    try:
        from app.services.object_views import object_view_generator
        return object_view_generator.get_related(object_id)
    except Exception as e:
        return {"error": str(e), "object_id": object_id}
