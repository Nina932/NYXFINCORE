"""
Orchestration Router — Graph status, tool discovery, graph execution
====================================================================
Exposes the StateGraph + ToolRegistry via REST endpoints.
"""

from fastapi import APIRouter
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/orchestration", tags=["orchestration"])


@router.get("/graph/status")
async def graph_status():
    """Get compiled graph structures and health."""
    try:
        from app.orchestration.chat_graph import get_chat_graph
        chat = get_chat_graph()
        return {
            "graphs": {
                "chat": chat.to_dict() if chat else None,
            },
            "status": "compiled",
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.get("/tools/discover")
async def discover_tools(query: str = "", tags: str = "", owner: str = ""):
    """MCP-style tool discovery. Search by query, tags, or owner agent."""
    from app.orchestration.tool_registry import tool_registry

    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    owner_filter = owner if owner else None

    tools = tool_registry.discover(query=query, tags=tag_list, owner=owner_filter)
    return {
        "tools": [t.to_dict() for t in tools],
        "count": len(tools),
        "registry_stats": tool_registry.status(),
    }


@router.get("/tools/status")
async def tools_status():
    """Get full tool registry status."""
    from app.orchestration.tool_registry import tool_registry
    return tool_registry.status()


@router.post("/graph/run")
async def run_graph(body: dict):
    """Execute a named graph with initial state."""
    graph_name = body.get("graph", "chat")
    initial_state = body.get("state", {})

    if graph_name == "chat":
        from app.orchestration.chat_graph import get_chat_graph
        graph = get_chat_graph()
    else:
        return {"error": f"Unknown graph: {graph_name}"}

    if not graph:
        return {"error": f"Graph '{graph_name}' not compiled"}

    result = await graph.ainvoke(initial_state)
    return {
        "run_id": result.run_id,
        "final_state": {k: v for k, v in result.final_state.items() if not k.startswith("__")},
        "steps": [{"node": name, "duration_ms": round(dur, 1)} for name, dur in result.steps],
        "total_ms": round(result.total_ms, 1),
        "interrupted": result.interrupted,
        "interrupt_reason": result.interrupt_reason,
    }


@router.post("/graph/stream")
async def stream_graph(body: dict):
    """Execute graph and return all intermediate steps."""
    graph_name = body.get("graph", "chat")
    initial_state = body.get("state", {})

    if graph_name == "chat":
        from app.orchestration.chat_graph import get_chat_graph
        graph = get_chat_graph()
    else:
        return {"error": f"Unknown graph: {graph_name}"}

    steps = []
    async for node_name, state in graph.astream(initial_state):
        steps.append({
            "node": node_name,
            "state_keys": list(state.keys()),
            "agent_name": state.get("agent_name"),
            "agent_result_preview": str(state.get("agent_result", ""))[:200],
        })

    return {"steps": steps, "count": len(steps)}


# ── Object Sets (Palantir pattern) ──

@router.get("/object-sets")
async def list_object_sets(owner: str = ""):
    """List all object sets."""
    from app.services.object_sets import object_set_manager
    return {"sets": object_set_manager.list_sets(owner)}


@router.post("/object-sets")
async def create_object_set(body: dict):
    """Create a new named object set."""
    from app.services.object_sets import object_set_manager
    set_id = object_set_manager.create(
        name=body.get("name", "Untitled"),
        object_type=body.get("object_type", "KPI"),
        filters=body.get("filters", []),
        owner=body.get("owner", "default"),
        description=body.get("description", ""),
        sort_by=body.get("sort_by", ""),
        limit=body.get("limit", 100),
    )
    return {"set_id": set_id}


@router.get("/object-sets/{set_id}")
async def get_object_set(set_id: str):
    """Get object set definition."""
    from app.services.object_sets import object_set_manager
    s = object_set_manager.get(set_id)
    if not s:
        from fastapi import HTTPException
        raise HTTPException(404, f"Object set '{set_id}' not found")
    return s.to_dict()


@router.get("/object-sets/{set_id}/resolve")
async def resolve_object_set(set_id: str):
    """Resolve an object set — execute the query and return matching objects."""
    from app.services.object_sets import object_set_manager
    return object_set_manager.resolve_for_widget(set_id)


@router.delete("/object-sets/{set_id}")
async def delete_object_set(set_id: str):
    """Delete an object set."""
    from app.services.object_sets import object_set_manager
    return {"deleted": object_set_manager.delete(set_id)}


# ── Write Guard ──

# ── Dynamic Tool Registration (MCP pattern) ──

@router.post("/tools/register")
async def register_tool(body: dict):
    """Dynamically register a tool at runtime (true MCP pattern)."""
    from app.orchestration.tool_registry import tool_registry
    tool_registry.register_tool(
        name=body.get("name", ""),
        description=body.get("description", ""),
        input_schema=body.get("input_schema", {}),
        owner_agent=body.get("owner_agent", "external"),
        tags=body.get("tags", []),
        version=body.get("version", "1.0"),
    )
    return {"registered": True, "name": body.get("name"), "total_tools": len(tool_registry._tools)}


# ── Request Tracing ──

@router.get("/traces")
async def list_traces(limit: int = 20):
    """Get recent request traces with spans."""
    from app.services.request_tracer import trace_store
    return {"traces": trace_store.get_recent(limit)}


@router.get("/traces/{trace_id}")
async def get_trace(trace_id: str):
    """Get a specific trace by ID."""
    from app.services.request_tracer import trace_store
    trace = trace_store.get_by_id(trace_id)
    if not trace:
        from fastapi import HTTPException
        raise HTTPException(404, f"Trace '{trace_id}' not found")
    return trace


# ── Alert Rules ──

@router.get("/alerts/rules")
async def list_alert_rules():
    """Get active metric alert rules."""
    rules = [
        {"id": "error_rate", "metric": "finai_http_requests_total{status='500'}", "operator": "gt",
         "threshold": 10, "window": "5m", "severity": "critical",
         "description": "Error rate exceeds 10 errors in 5 minutes"},
        {"id": "agent_circuit_open", "metric": "finai_agent_healthy", "operator": "eq",
         "threshold": 0, "window": "instant", "severity": "critical",
         "description": "Agent circuit breaker is open (unhealthy)"},
        {"id": "slow_requests", "metric": "finai_http_request_duration_ms_avg", "operator": "gt",
         "threshold": 5000, "window": "5m", "severity": "warning",
         "description": "Average request latency exceeds 5 seconds"},
        {"id": "flywheel_stalled", "metric": "finai_flywheel_running", "operator": "eq",
         "threshold": 0, "window": "instant", "severity": "warning",
         "description": "Flywheel background loop is not running"},
        {"id": "scoring_queue_backlog", "metric": "flywheel_scoring_queue", "operator": "gt",
         "threshold": 100, "window": "instant", "severity": "warning",
         "description": "Flywheel scoring queue exceeds 100 pending items"},
    ]
    return {"rules": rules, "count": len(rules)}


# ── A/B Model Evaluation ──

@router.get("/ab-eval/status")
async def ab_eval_status():
    """Get A/B evaluation status for model comparison."""
    try:
        from app.services.data_flywheel import data_flywheel
        interactions = data_flywheel._interactions
        by_model: dict = {}
        for i in interactions:
            model = i.model or "unknown"
            if model not in by_model:
                by_model[model] = {"count": 0, "scored": 0, "total_quality": 0.0, "avg_quality": 0.0}
            by_model[model]["count"] += 1
            if i.quality_score is not None:
                by_model[model]["scored"] += 1
                by_model[model]["total_quality"] += i.quality_score

        for model, stats in by_model.items():
            if stats["scored"] > 0:
                stats["avg_quality"] = round(stats["total_quality"] / stats["scored"], 3)

        return {
            "models": by_model,
            "total_interactions": len(interactions),
            "recommendation": _get_model_recommendation(by_model),
        }
    except Exception as e:
        return {"error": str(e)}


def _get_model_recommendation(by_model: dict) -> str:
    """Recommend which model to promote based on quality scores."""
    if not by_model:
        return "No data yet — need interactions to evaluate"

    scored_models = {m: s for m, s in by_model.items() if s["scored"] >= 3}
    if not scored_models:
        summary = ", ".join(m + "=" + str(s["scored"]) for m, s in by_model.items())
        return "Need at least 3 scored interactions per model (have: " + summary + ")"

    best = max(scored_models.items(), key=lambda x: x[1]["avg_quality"])
    bname, bstats = best
    return f"Best model: {bname} (avg quality: {bstats['avg_quality']:.2f} from {bstats['scored']} samples)"


@router.get("/write-guard/status")
async def write_guard_status():
    """Get ontology write guard audit status."""
    from app.services.ontology_write_guard import write_guard
    return write_guard.status()


@router.get("/write-guard/audit")
async def write_guard_audit(limit: int = 50):
    """Get write audit log."""
    from app.services.ontology_write_guard import write_guard
    return {"entries": write_guard.get_audit_log(limit)}
