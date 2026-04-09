"""
Workshop Router — Dashboard layout CRUD + data source discovery
===============================================================
Palantir Workshop-lite: save/load drag-and-drop dashboard layouts,
discover available data sources for widget binding.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
import json
import logging
import time
import uuid
from typing import List, Optional, Dict, Any
from app.services.workflow_engine import workflow_engine, WorkflowDefinition, WorkflowStep, StepType

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/workshop", tags=["workshop"])

# In-memory layout storage (upgrade to SQLite for production)
_layouts: dict = {}


@router.post("/layouts")
async def create_layout(body: dict):
    """Create a new dashboard layout."""
    layout_id = uuid.uuid4().hex[:12]
    slug = body.get("slug") or body.get("name", "dashboard").lower().replace(" ", "-") + f"-{layout_id[:6]}"
    layout = {
        "id": layout_id,
        "name": body.get("name", "Untitled Dashboard"),
        "slug": slug,
        "grid": body.get("grid", []),  # react-grid-layout format: [{i, x, y, w, h}]
        "widgets": body.get("widgets", []),  # [{id, type, dataSource, props}]
        "created_at": time.time(),
        "updated_at": time.time(),
        "user_id": body.get("user_id", "default"),
        "is_shared": body.get("is_shared", False),
    }
    _layouts[layout_id] = layout
    return layout


@router.get("/layouts")
async def list_layouts(user_id: str = "default"):
    """List all layouts for a user."""
    user_layouts = [l for l in _layouts.values() if l.get("user_id") == user_id]
    shared = [l for l in _layouts.values() if l.get("is_shared") and l.get("user_id") != user_id]
    return {"layouts": user_layouts, "shared": shared}


@router.get("/layouts/{slug}")
async def get_layout(slug: str):
    """Get a layout by slug."""
    for l in _layouts.values():
        if l.get("slug") == slug or l.get("id") == slug:
            return l
    raise HTTPException(404, f"Layout '{slug}' not found")


@router.put("/layouts/{layout_id}")
async def update_layout(layout_id: str, body: dict):
    """Update an existing layout."""
    if layout_id not in _layouts:
        raise HTTPException(404, f"Layout '{layout_id}' not found")
    layout = _layouts[layout_id]
    if "name" in body:
        layout["name"] = body["name"]
    if "grid" in body:
        layout["grid"] = body["grid"]
    if "widgets" in body:
        layout["widgets"] = body["widgets"]
    if "is_shared" in body:
        layout["is_shared"] = body["is_shared"]
    layout["updated_at"] = time.time()
    return layout


@router.delete("/layouts/{layout_id}")
async def delete_layout(layout_id: str):
    """Delete a layout."""
    if layout_id not in _layouts:
        raise HTTPException(404)
    del _layouts[layout_id]
    return {"deleted": True}


@router.get("/datasources")
async def list_datasources():
    """List available data sources for widget binding."""
    sources = [
        # Financial metrics (from dashboard)
        {"id": "metric:revenue", "type": "metric", "label": "Revenue", "format": "currency"},
        {"id": "metric:cogs", "type": "metric", "label": "COGS", "format": "currency"},
        {"id": "metric:gross_profit", "type": "metric", "label": "Gross Profit", "format": "currency"},
        {"id": "metric:net_profit", "type": "metric", "label": "Net Profit", "format": "currency"},
        {"id": "metric:ebitda", "type": "metric", "label": "EBITDA", "format": "currency"},
        {"id": "metric:total_assets", "type": "metric", "label": "Total Assets", "format": "currency"},
        {"id": "metric:total_liabilities", "type": "metric", "label": "Total Liabilities", "format": "currency"},
        {"id": "metric:total_equity", "type": "metric", "label": "Total Equity", "format": "currency"},
        {"id": "metric:cash", "type": "metric", "label": "Cash", "format": "currency"},
        {"id": "metric:gross_margin", "type": "metric", "label": "Gross Margin %", "format": "percentage"},
        {"id": "metric:net_margin", "type": "metric", "label": "Net Margin %", "format": "percentage"},
        {"id": "metric:current_ratio", "type": "metric", "label": "Current Ratio", "format": "number"},
        {"id": "metric:debt_to_equity", "type": "metric", "label": "D/E Ratio", "format": "number"},
        # Ontology queries
        {"id": "ontology:KPI", "type": "ontology", "label": "KPI Objects", "object_type": "KPI"},
        {"id": "ontology:RiskSignal", "type": "ontology", "label": "Risk Signals", "object_type": "RiskSignal"},
        {"id": "ontology:Account", "type": "ontology", "label": "Accounts", "object_type": "Account"},
        # Warehouse SQL
        {"id": "warehouse:revenue_trend", "type": "warehouse", "label": "Revenue Trend (12mo)",
         "sql": "SELECT period_id, value FROM dw_financial_snapshots WHERE field_name='revenue' ORDER BY period_id"},
        {"id": "warehouse:all_metrics", "type": "warehouse", "label": "All Financial Metrics",
         "sql": "SELECT field_name, SUM(value) as total FROM dw_financial_snapshots GROUP BY field_name ORDER BY total DESC"},
        # Alert stream
        {"id": "alerts:active", "type": "alerts", "label": "Active Alerts"},
    ]

    # Add saved Object Sets as data sources
    try:
        from app.services.object_sets import object_set_manager
        for s in object_set_manager.list_sets():
            sources.append({
                "id": f"objectset:{s['set_id']}",
                "type": "objectset",
                "label": f"{s['name']} ({s['object_type']})",
                "set_id": s["set_id"],
                "object_type": s["object_type"],
            })
    except Exception:
        pass

    return {"datasources": sources}


@router.post("/datasources/preview")
async def preview_datasource(body: dict):
    """Execute a data source query and return sample data."""
    source_id = body.get("source_id", "")
    source_type = body.get("type", "")

    if source_type == "metric" or source_id.startswith("metric:"):
        metric = source_id.replace("metric:", "")
        try:
            from app.services.data_store import data_store
            companies = data_store.list_companies()
            if companies:
                co = companies[-1]
                periods = data_store.get_all_periods(co["id"])
                if periods:
                    fin = data_store.get_financials(co["id"], periods[-1])
                    if fin:
                        value = fin.get(metric, 0)
                        # Handle derived metrics
                        if metric == "gross_margin" and fin.get("revenue"):
                            value = round(fin.get("gross_profit", 0) / fin["revenue"] * 100, 1)
                        elif metric == "net_margin" and fin.get("revenue"):
                            value = round(fin.get("net_profit", 0) / fin["revenue"] * 100, 1)
                        return {"value": value, "period": periods[-1], "type": "single_value"}
        except Exception as e:
            return {"error": str(e)}

    elif source_type == "warehouse" or source_id.startswith("warehouse:"):
        sql = body.get("sql", "")
        if not sql:
            # Find predefined query
            sources_resp = await list_datasources()
            for s in sources_resp["datasources"]:
                if s["id"] == source_id:
                    sql = s.get("sql", "")
                    break
        if sql and sql.strip().upper().startswith("SELECT"):
            try:
                from app.services.warehouse import warehouse
                results = warehouse.execute(sql)
                return {"data": results[:50], "count": len(results), "type": "table"}
            except Exception as e:
                return {"error": str(e)}

    elif source_type == "ontology" or source_id.startswith("ontology:"):
        obj_type = body.get("object_type") or source_id.replace("ontology:", "")
        try:
            from app.services.ontology_engine import ontology_registry
            objects = ontology_registry.get_objects_by_type(obj_type)
            return {
                "data": [{"id": o.object_id, "properties": o.properties} for o in objects[:50]],
                "count": len(objects),
                "type": "object_set",
            }
        except Exception as e:
            return {"error": str(e)}

    elif source_type == "objectset" or source_id.startswith("objectset:"):
        set_id = source_id.replace("objectset:", "") if ":" in source_id else body.get("set_id", "")
        try:
            from app.services.object_sets import object_set_manager
            return object_set_manager.resolve_for_widget(set_id)
        except Exception as e:
            return {"error": str(e)}

    return {"error": f"Unknown data source: {source_id}"}


# ═══════════════════════════════════════════════════════════════════
#   WORKFLOW & AUTOMATION (Workshop Builder Core)
# ═══════════════════════════════════════════════════════════════════

@router.get("/workflows")
async def list_workflows():
    """List all available workflow templates."""
    return {"workflows": workflow_engine.list_workflows()}


@router.post("/workflows")
async def create_workflow(body: dict):
    """
    Create a new workflow definition.
    Body format: {workflow_id, name, description, steps: [{step_id, name, type, ...}], triggers: []}
    """
    try:
        steps = []
        for s in body.get("steps", []):
            steps.append(WorkflowStep(
                step_id=s["step_id"],
                name=s["name"],
                step_type=StepType(s.get("type", "tool")),
                tool_name=s.get("tool_name"),
                input_map=s.get("input_map", {}),
                llm_prompt=s.get("llm_prompt"),
                llm_output_schema=s.get("llm_output_schema"),
                condition=s.get("condition"),
                on_true=s.get("on_true"),
                on_false=s.get("on_false"),
                transform_fn=s.get("transform_fn"),
                pause_message=s.get("pause_message"),
            ))
        
        wf_def = WorkflowDefinition(
            workflow_id=body.get("workflow_id") or f"wf_{uuid.uuid4().hex[:8]}",
            name=body.get("name", "Untitled Workflow"),
            description=body.get("description", ""),
            steps=steps,
            trigger_events=body.get("triggers", [])
        )
        workflow_engine.register_workflow(wf_def)
        return {"status": "registered", "workflow_id": wf_def.workflow_id}
    except Exception as e:
        logger.error(f"Failed to create workflow: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/workflows/{workflow_id}/execute")
async def execute_workflow(workflow_id: str, body: dict, background_tasks: BackgroundTasks):
    """Manually trigger a workflow execution."""
    try:
        # We run it in background to avoid blocking the API call for long workflows
        background_tasks.add_task(workflow_engine.execute, workflow_id, body.get("trigger_data", {}))
        return {"status": "queued", "workflow_id": workflow_id}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/executions")
async def list_executions(workflow_id: Optional[str] = None, limit: int = 20):
    """List recent workflow executions and their status."""
    return {"executions": workflow_engine.list_executions(workflow_id, limit)}


@router.get("/executions/{execution_id}")
async def get_execution_details(execution_id: str):
    """Get detailed results for a specific workflow execution."""
    ex = workflow_engine.get_execution(execution_id)
    if not ex:
        raise HTTPException(status_code=404, detail="Execution not found")
    return ex


@router.post("/executions/{execution_id}/resume")
async def resume_workflow(execution_id: str, body: dict):
    """Resume a paused workflow (human-in-the-loop approval)."""
    res = workflow_engine.resume_execution(execution_id, body.get("approval_data"))
    if not res:
        raise HTTPException(status_code=400, detail="Could not resume execution (maybe not paused?)")
    return {"status": "resumed", "execution_id": execution_id}
