"""
FinAI OS — Ontology Tools for LLM (Palantir AIP Pattern)
=========================================================
Defines typed tool schemas that the LLM can call to interact with the ontology.
Three categories (matching Palantir AIP):
  - Data Tools: search, filter, aggregate ontology objects
  - Logic Tools: invoke computation (forecast, simulate, analyze)
  - Action Tools: propose mutations (create report, flag issue, approve)

Usage:
    from app.services.ontology_tools import ontology_tool_executor, TOOL_DEFINITIONS
    # Give TOOL_DEFINITIONS to the LLM in the system prompt
    # When LLM returns a tool call, execute it:
    result = await ontology_tool_executor.execute(tool_name, parameters)
"""

import logging
import json
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# TOOL DEFINITIONS (given to LLM in system prompt)
# =============================================================================

TOOL_DEFINITIONS = [
    # ── DATA TOOLS (read from ontology) ──
    {
        "name": "search_objects",
        "category": "data",
        "description": "Search ontology objects by type and filters. Returns typed objects with properties.",
        "parameters": {
            "type_id": {"type": "string", "required": True, "description": "Object type: Company, Account, KPI, RiskSignal, Forecast, Action, Benchmark, Standard, FinancialStatement, FinancialPeriod"},
            "filters": {"type": "object", "description": "Property filters, e.g. {'metric': 'gross_margin', 'status': 'breached'}"},
            "limit": {"type": "integer", "default": 10},
        },
    },
    {
        "name": "get_object",
        "category": "data",
        "description": "Get a single ontology object by ID with all properties, computed fields, and relationships.",
        "parameters": {
            "object_id": {"type": "string", "required": True},
        },
    },
    {
        "name": "traverse_relationships",
        "category": "data",
        "description": "Traverse relationships from an object to find connected objects.",
        "parameters": {
            "object_id": {"type": "string", "required": True},
            "relationship": {"type": "string", "description": "Relationship name, e.g. 'has_kpis', 'derived_from'"},
            "depth": {"type": "integer", "default": 1},
        },
    },
    {
        "name": "aggregate_objects",
        "category": "data",
        "description": "Aggregate numeric properties across objects of a type. Returns sum, avg, min, max, count.",
        "parameters": {
            "type_id": {"type": "string", "required": True},
            "property": {"type": "string", "required": True, "description": "Numeric property to aggregate"},
            "filters": {"type": "object", "description": "Optional filters to narrow the set"},
        },
    },
    {
        "name": "query_warehouse",
        "category": "data",
        "description": "Execute an analytical SQL query against the DuckDB warehouse. Only SELECT queries allowed.",
        "parameters": {
            "sql": {"type": "string", "required": True, "description": "SQL SELECT query"},
        },
    },

    # ── LOGIC TOOLS (invoke computation) ──
    {
        "name": "compute_kpi",
        "category": "logic",
        "description": "Compute a KPI from a FinancialStatement object. Returns the computed value.",
        "parameters": {
            "statement_id": {"type": "string", "required": True},
            "kpi_name": {"type": "string", "required": True, "description": "e.g. gross_margin_pct, net_margin_pct, ebitda_margin_pct"},
        },
    },
    {
        "name": "run_sensitivity",
        "category": "logic",
        "description": "Run sensitivity analysis on a metric. Returns impact range.",
        "parameters": {
            "metric": {"type": "string", "required": True},
            "change_pct": {"type": "number", "default": 10},
        },
    },

    # ── ACTION TOOLS (propose mutations — Palantir proposal pattern) ──
    {
        "name": "propose_action",
        "category": "action",
        "description": "Propose a business action for human approval. Does NOT execute immediately.",
        "parameters": {
            "description": {"type": "string", "required": True},
            "category": {"type": "string", "required": True, "enum": ["cost_reduction", "revenue_growth", "risk_mitigation", "capital_optimization", "operational_efficiency"]},
            "roi_estimate": {"type": "number", "default": 0},
            "risk_level": {"type": "string", "default": "medium", "enum": ["low", "medium", "high", "critical"]},
            "parameters": {"type": "object", "description": "Typed parameters for the action category"},
        },
    },
    {
        "name": "create_risk_signal",
        "category": "action",
        "description": "Flag a financial risk signal for monitoring.",
        "parameters": {
            "signal_type": {"type": "string", "required": True},
            "severity": {"type": "string", "required": True, "enum": ["low", "medium", "high", "critical"]},
            "metric": {"type": "string"},
            "message": {"type": "string", "required": True},
        },
    },
]


# =============================================================================
# TOOL EXECUTOR
# =============================================================================

class OntologyToolExecutor:
    """Executes ontology tools called by the LLM."""

    async def execute(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool and return the result."""
        handler = getattr(self, f"_exec_{tool_name}", None)
        if not handler:
            return {"error": f"Unknown tool: {tool_name}"}
        try:
            result = await handler(parameters)
            logger.info(f"Tool executed: {tool_name} → {len(str(result))} chars")
            return result
        except Exception as e:
            logger.error(f"Tool execution error {tool_name}: {e}")
            return {"error": str(e)}

    # ── DATA TOOLS ──

    async def _exec_search_objects(self, params: Dict) -> Dict:
        from app.services.ontology_engine import ontology_registry
        type_id = params.get("type_id", "KPI")
        filters = params.get("filters")
        limit = params.get("limit", 10)
        objects = ontology_registry.query(type_id, filters, limit=limit)
        return {
            "objects": [{"id": o.object_id, "type": o.object_type, "properties": {k: v for k, v in o.properties.items() if not k.startswith("_") and not isinstance(v, (dict, list))}} for o in objects],
            "count": len(objects),
        }

    async def _exec_get_object(self, params: Dict) -> Dict:
        from app.services.ontology_engine import ontology_registry
        obj = ontology_registry.get_object(params["object_id"])
        if not obj:
            return {"error": "Object not found"}
        # Compute all computed fields
        type_def = ontology_registry.get_type(obj.object_type)
        computed = {}
        if type_def:
            for cf_name in type_def.computed_fields:
                val = ontology_registry.get_computed_field(obj.object_id, cf_name)
                if val is not None:
                    computed[cf_name] = round(val, 2) if isinstance(val, float) else val
        return {
            "id": obj.object_id,
            "type": obj.object_type,
            "properties": obj.properties,
            "computed": computed,
            "relationships": obj.relationships,
            "markings": obj.markings,
        }

    async def _exec_traverse_relationships(self, params: Dict) -> Dict:
        from app.services.ontology_engine import ontology_registry
        objects = ontology_registry.traverse(params["object_id"], params.get("relationship"), params.get("depth", 1))
        return {
            "objects": [{"id": o.object_id, "type": o.object_type, "name": o.properties.get("name_en") or o.properties.get("code") or o.properties.get("metric", o.object_id)} for o in objects],
            "count": len(objects),
        }

    async def _exec_aggregate_objects(self, params: Dict) -> Dict:
        from app.services.ontology_engine import ontology_registry
        type_id = params["type_id"]
        prop = params["property"]
        objects = ontology_registry.query(type_id, params.get("filters"), limit=1000)
        values = [o.properties.get(prop) for o in objects if isinstance(o.properties.get(prop), (int, float))]
        if not values:
            return {"error": f"No numeric values found for {prop}"}
        return {
            "count": len(values),
            "sum": sum(values),
            "avg": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
        }

    async def _exec_query_warehouse(self, params: Dict) -> Dict:
        from app.services.warehouse import warehouse
        sql = params.get("sql", "").strip()
        if not sql.upper().startswith("SELECT"):
            return {"error": "Only SELECT queries allowed"}
        results = warehouse.execute(sql)
        return {"results": results[:20], "count": len(results)}

    # ── LOGIC TOOLS ──

    async def _exec_compute_kpi(self, params: Dict) -> Dict:
        from app.services.ontology_engine import ontology_registry
        stmt_id = params["statement_id"]
        kpi_name = params["kpi_name"]
        value = ontology_registry.get_computed_field(stmt_id, kpi_name)
        if value is None:
            return {"error": f"Cannot compute {kpi_name} for {stmt_id}"}
        return {"kpi": kpi_name, "value": round(value, 2), "unit": "%"}

    async def _exec_run_sensitivity(self, params: Dict) -> Dict:
        # Simplified — in production, calls the full sensitivity_analyzer
        metric = params["metric"]
        change = params.get("change_pct", 10)
        return {
            "metric": metric,
            "change_pct": change,
            "upside_impact": f"+{change * 0.8:.1f}%",
            "downside_impact": f"-{change * 1.2:.1f}%",
            "note": "Run full sensitivity analysis via /api/agent/agents/sensitivity/analyze for detailed results",
        }

    # ── ACTION TOOLS (proposal pattern) ──

    async def _exec_propose_action(self, params: Dict) -> Dict:
        from app.services.action_engine import action_engine
        execution = action_engine.propose(
            description=params["description"],
            category=params["category"],
            roi_estimate=params.get("roi_estimate", 0),
            risk_level=params.get("risk_level", "medium"),
            parameters=params.get("parameters", {}),
            requested_by="llm_agent",
        )
        return {
            "status": "proposed",
            "execution_id": execution.execution_id,
            "message": f"Action proposed for human approval: {params['description'][:80]}",
            "next_step": "A human operator must approve this action before it executes.",
        }

    async def _exec_create_risk_signal(self, params: Dict) -> Dict:
        from app.services.ontology_engine import ontology_registry
        risk = ontology_registry.create_object("RiskSignal", {
            "signal_type": params["signal_type"],
            "severity": params["severity"],
            "metric": params.get("metric", ""),
            "message": params["message"],
        })
        return {
            "status": "created",
            "object_id": risk.object_id,
            "signal_type": params["signal_type"],
            "severity": params["severity"],
        }

    def get_tool_prompt_section(self) -> str:
        """Generate the tool definitions section for LLM system prompts."""
        lines = ["## Available Ontology Tools\n"]
        for tool in TOOL_DEFINITIONS:
            lines.append(f"### {tool['name']} ({tool['category']})")
            lines.append(f"{tool['description']}")
            lines.append(f"Parameters: {json.dumps(tool['parameters'], indent=2)}\n")
        return "\n".join(lines)


# Singleton
ontology_tool_executor = OntologyToolExecutor()
