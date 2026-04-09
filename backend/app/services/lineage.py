"""
FinAI OS — Workflow Lineage Graph (Palantir AIP Lineage Pattern)
=================================================================
Generates the lineage graph showing how all system components connect:
object types, workflows, actions, automations, and dashboards.

Key concepts:
  - LineageNode: A node in the graph (object type, workflow, action, dashboard)
  - LineageEdge: A directed edge (reads, writes, triggers, displays, uses)
  - LineageGraph: Singleton that builds the full connection graph on demand

Each node carries latest metrics (execution count, success rate, p95 latency).
Edges are derived from workflow step definitions, trigger events, and dashboard configs.

Usage:
    from app.services.lineage import lineage_graph

    graph = lineage_graph.build_graph()
    # Returns {"nodes": [...], "edges": [...], "stats": {...}}

    history = lineage_graph.get_node_history("workflow:financial_analysis")
    # Returns execution history for that node
"""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class LineageNode:
    """A node in the lineage graph."""
    node_id: str  # e.g., "object_type:Company", "workflow:financial_analysis"
    node_type: str  # object_type, workflow, action, automation, dashboard
    name: str
    description: str = ""
    icon: str = ""
    execution_count: int = 0
    success_rate: float = 100.0
    p95_latency_ms: float = 0.0
    last_executed: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "name": self.name,
            "description": self.description,
            "icon": self.icon,
            "metrics": {
                "execution_count": self.execution_count,
                "success_rate": round(self.success_rate, 1),
                "p95_latency_ms": round(self.p95_latency_ms, 1),
                "last_executed": self.last_executed,
            },
            "metadata": self.metadata,
        }


@dataclass
class LineageEdge:
    """A directed edge in the lineage graph."""
    source: str  # node_id of source
    target: str  # node_id of target
    relationship: str  # reads, writes, triggers, displays, uses
    label: str = ""
    weight: float = 1.0  # strength/frequency of connection

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "relationship": self.relationship,
            "label": self.label,
            "weight": self.weight,
        }


# =============================================================================
# LINEAGE GRAPH (Singleton)
# =============================================================================

class LineageGraph:
    """
    Builds and serves the complete lineage graph showing how
    all system components connect: object types, workflows,
    actions, automations, and dashboards.
    """

    # Dashboard definitions (hardcoded frontend pages)
    DASHBOARDS = [
        {"id": "dashboard:overview", "name": "Overview Dashboard", "icon": "layout-dashboard",
         "displays": ["Company", "KPI", "RiskSignal", "FinancialStatement"]},
        {"id": "dashboard:pnl", "name": "P&L Analysis", "icon": "trending-up",
         "displays": ["FinancialStatement", "Account", "KPI"]},
        {"id": "dashboard:balance_sheet", "name": "Balance Sheet", "icon": "scale",
         "displays": ["FinancialStatement", "Account"]},
        {"id": "dashboard:revenue", "name": "Revenue Analysis", "icon": "dollar-sign",
         "displays": ["FinancialStatement", "KPI"]},
        {"id": "dashboard:data_transparency", "name": "Data Transparency", "icon": "eye",
         "displays": ["Account", "Dataset"]},
        {"id": "dashboard:captain", "name": "AI Captain", "icon": "bot",
         "displays": ["Company", "FinancialStatement"]},
        {"id": "dashboard:actions", "name": "Action Center", "icon": "zap",
         "displays": ["Action", "RiskSignal"]},
        {"id": "dashboard:ontology", "name": "Ontology Explorer", "icon": "share-2",
         "displays": ["Company", "Account", "KPI", "RiskSignal", "FinancialStatement"]},
    ]

    def __init__(self):
        self._last_build_time: Optional[str] = None
        self._cached_graph: Optional[Dict[str, Any]] = None

    def get_lineage(self, dataset_id: Optional[str] = None) -> Dict[str, Any]:
        """Get lineage for a specific dataset or full graph."""
        # Multi-dataset lineage is computed on the fly; for now returns full system graph
        return self.build_graph()

    def build_graph(self) -> Dict[str, Any]:
        """Build the complete lineage graph by scanning all system components."""
        t0 = time.time()
        nodes: Dict[str, LineageNode] = {}
        edges: List[LineageEdge] = []

        # 1. Object Type nodes from ontology registry
        self._add_object_type_nodes(nodes)

        # 2. Workflow nodes from workflow engine
        self._add_workflow_nodes(nodes, edges)

        # 3. Action nodes from action engine
        self._add_action_nodes(nodes, edges)

        # 4. Automation nodes from workflow triggers
        self._add_automation_nodes(nodes, edges)

        # 5. Dashboard nodes (hardcoded)
        self._add_dashboard_nodes(nodes, edges)

        # 6. Add metrics from activity feed
        self._enrich_with_metrics(nodes)

        build_ms = int((time.time() - t0) * 1000)
        self._last_build_time = datetime.now(timezone.utc).isoformat()

        result = {
            "nodes": [n.to_dict() for n in nodes.values()],
            "edges": [e.to_dict() for e in edges],
            "stats": {
                "node_count": len(nodes),
                "edge_count": len(edges),
                "build_ms": build_ms,
                "built_at": self._last_build_time,
                "node_types": dict(self._count_by(nodes.values(), lambda n: n.node_type)),
                "edge_types": dict(self._count_by(edges, lambda e: e.relationship)),
            },
        }
        self._cached_graph = result
        return result

    def get_node_history(self, node_id: str) -> Dict[str, Any]:
        """Get execution history for a specific node."""
        history = []

        # Check if it's a workflow node
        if node_id.startswith("workflow:"):
            wf_id = node_id.split(":", 1)[1]
            try:
                from app.services.workflow_engine import workflow_engine
                execs = workflow_engine.list_executions(workflow_id=wf_id, limit=50)
                history = execs
            except Exception:
                pass

        # Check activity feed for any node
        try:
            from app.services.activity_feed import activity_feed
            events = activity_feed.get_feed(resource_type=node_id, limit=50)
            if not history:
                history = events
        except Exception:
            pass

        # Check action engine for action nodes
        if node_id.startswith("action:"):
            try:
                from app.services.action_engine import action_engine
                all_actions = action_engine.get_history(limit=50)
                category = node_id.split(":", 1)[1]
                history = [a.to_dict() for a in all_actions if a.category == category]
            except Exception:
                pass

        return {
            "node_id": node_id,
            "history": history[:50],
            "total_entries": len(history),
        }

    # ── Internal builders ────────────────────────────────────────────

    def _add_object_type_nodes(self, nodes: Dict[str, LineageNode]):
        """Add ontology object type nodes."""
        try:
            from app.services.ontology_engine import ontology_registry
            for type_def in ontology_registry.list_types():
                node_id = f"object_type:{type_def.type_id}"
                # Count objects of this type
                objects = ontology_registry.query(type_def.type_id, limit=1000)
                obj_count = len(objects) if objects else 0

                nodes[node_id] = LineageNode(
                    node_id=node_id,
                    node_type="object_type",
                    name=type_def.type_id,
                    description=type_def.description,
                    icon=type_def.icon or "box",
                    metadata={
                        "object_count": obj_count,
                        "property_count": len(type_def.properties_schema),
                        "relationship_count": len(type_def.relationships_schema),
                        "computed_field_count": len(type_def.computed_fields),
                        "color": type_def.color,
                    },
                )
        except Exception as e:
            logger.debug("Could not load ontology types for lineage: %s", e)
            # Add default types even if ontology not initialized
            for t in ["Company", "Account", "KPI", "RiskSignal", "FinancialStatement", "Dataset"]:
                node_id = f"object_type:{t}"
                nodes[node_id] = LineageNode(
                    node_id=node_id, node_type="object_type",
                    name=t, description=f"{t} ontology type", icon="box",
                )

    def _add_workflow_nodes(self, nodes: Dict[str, LineageNode], edges: List[LineageEdge]):
        """Add workflow nodes and derive read/write edges from steps."""
        try:
            from app.services.workflow_engine import workflow_engine

            for wf_info in workflow_engine.list_workflows():
                wf_id = wf_info["workflow_id"]
                node_id = f"workflow:{wf_id}"

                # Get execution stats
                execs = workflow_engine.list_executions(workflow_id=wf_id, limit=100)
                exec_count = len(execs)
                success_count = sum(1 for e in execs if e.get("status") == "completed")
                success_rate = (success_count / exec_count * 100) if exec_count > 0 else 100.0

                durations = [e.get("duration_ms", 0) for e in execs if e.get("duration_ms")]
                p95 = sorted(durations)[int(len(durations) * 0.95)] if durations else 0

                last_exec = execs[0].get("started_at") if execs else None

                nodes[node_id] = LineageNode(
                    node_id=node_id,
                    node_type="workflow",
                    name=wf_info["name"],
                    description=wf_info.get("description", ""),
                    icon="git-branch",
                    execution_count=exec_count,
                    success_rate=success_rate,
                    p95_latency_ms=p95,
                    last_executed=last_exec,
                    metadata={
                        "step_count": wf_info.get("steps", 0),
                        "triggers": wf_info.get("triggers", []),
                        "version": wf_info.get("version", 1),
                    },
                )

                # Derive edges from workflow steps
                wf_def = workflow_engine.get_workflow(wf_id)
                if wf_def:
                    self._derive_workflow_edges(node_id, wf_def, edges)

        except Exception as e:
            logger.debug("Could not load workflows for lineage: %s", e)

    def _derive_workflow_edges(self, wf_node_id: str, wf_def, edges: List[LineageEdge]):
        """Derive read/write/trigger edges from workflow step definitions."""
        from app.services.workflow_engine import StepType

        for step in wf_def.steps:
            if step.step_type == StepType.TOOL:
                tool = step.tool_name or ""
                # search_objects reads an object type
                if "search" in tool or "query" in tool or "aggregate" in tool:
                    # Try to find the target type from input_map
                    target_type = step.input_map.get("type_id", "")
                    if target_type:
                        target_node = f"object_type:{target_type}"
                        edges.append(LineageEdge(
                            source=wf_node_id, target=target_node,
                            relationship="reads",
                            label=f"Step '{step.name}' reads {target_type}",
                        ))
                # propose_action writes to Action
                elif "propose" in tool or "create" in tool or "update" in tool:
                    edges.append(LineageEdge(
                        source=wf_node_id, target=f"action:{step.step_id}",
                        relationship="writes",
                        label=f"Step '{step.name}' creates output",
                    ))

            elif step.step_type == StepType.LLM:
                edges.append(LineageEdge(
                    source=wf_node_id, target=wf_node_id,
                    relationship="uses",
                    label=f"Step '{step.name}' uses LLM",
                    weight=0.5,
                ))

    def _add_action_nodes(self, nodes: Dict[str, LineageNode], edges: List[LineageEdge]):
        """Add action category nodes from the action engine."""
        try:
            from app.services.action_engine import action_engine

            # Group actions by category
            all_actions = action_engine.get_history(limit=200)
            categories: Dict[str, List] = defaultdict(list)
            for action in all_actions:
                categories[action.category].append(action)

            pending = action_engine.get_pending()
            for action in pending:
                categories[action.category].append(action)

            for cat, actions in categories.items():
                node_id = f"action:{cat}"
                completed = sum(1 for a in actions if a.status.value == "completed")
                total = len(actions)

                nodes[node_id] = LineageNode(
                    node_id=node_id,
                    node_type="action",
                    name=cat.replace("_", " ").title(),
                    description=f"Action category: {cat}",
                    icon="zap",
                    execution_count=total,
                    success_rate=(completed / total * 100) if total > 0 else 0,
                    metadata={
                        "pending_count": sum(1 for a in actions if a.status.value in ("proposed", "pending_approval")),
                        "completed_count": completed,
                    },
                )

                # Actions are triggered by workflows
                for wf_id in ["financial_analysis", "invoice_validation"]:
                    wf_node = f"workflow:{wf_id}"
                    if wf_node in nodes:
                        edges.append(LineageEdge(
                            source=wf_node, target=node_id,
                            relationship="triggers",
                            label=f"Workflow triggers {cat} actions",
                            weight=0.3,
                        ))

        except Exception as e:
            logger.debug("Could not load actions for lineage: %s", e)

    def _add_automation_nodes(self, nodes: Dict[str, LineageNode], edges: List[LineageEdge]):
        """Add automation/trigger nodes derived from workflow trigger events."""
        try:
            from app.services.workflow_engine import workflow_engine

            for wf_info in workflow_engine.list_workflows():
                triggers = wf_info.get("triggers", [])
                wf_node = f"workflow:{wf_info['workflow_id']}"

                for trigger_event in triggers:
                    auto_id = f"automation:{trigger_event}"
                    if auto_id not in nodes:
                        nodes[auto_id] = LineageNode(
                            node_id=auto_id,
                            node_type="automation",
                            name=trigger_event.replace("_", " ").title(),
                            description=f"Automation trigger: {trigger_event}",
                            icon="repeat",
                            metadata={"event_type": trigger_event},
                        )

                    edges.append(LineageEdge(
                        source=auto_id, target=wf_node,
                        relationship="triggers",
                        label=f"Event '{trigger_event}' triggers workflow",
                    ))

                    # Connect trigger to the object types they watch
                    if "upload" in trigger_event:
                        edges.append(LineageEdge(
                            source="object_type:Dataset" if "object_type:Dataset" in nodes else auto_id,
                            target=auto_id,
                            relationship="triggers",
                            label="Dataset upload triggers automation",
                        ))
                    if "alert" in trigger_event:
                        if "object_type:RiskSignal" in nodes:
                            edges.append(LineageEdge(
                                source="object_type:RiskSignal",
                                target=auto_id,
                                relationship="triggers",
                                label="Risk signal triggers automation",
                            ))

        except Exception as e:
            logger.debug("Could not load automations for lineage: %s", e)

    def _add_dashboard_nodes(self, nodes: Dict[str, LineageNode], edges: List[LineageEdge]):
        """Add dashboard nodes and their display edges."""
        for dash in self.DASHBOARDS:
            node_id = dash["id"]
            nodes[node_id] = LineageNode(
                node_id=node_id,
                node_type="dashboard",
                name=dash["name"],
                icon=dash["icon"],
                description=f"Frontend page: {dash['name']}",
                metadata={"displays_types": dash["displays"]},
            )

            for obj_type in dash["displays"]:
                target = f"object_type:{obj_type}"
                if target in nodes:
                    edges.append(LineageEdge(
                        source=node_id, target=target,
                        relationship="displays",
                        label=f"{dash['name']} displays {obj_type}",
                    ))

    def _enrich_with_metrics(self, nodes: Dict[str, LineageNode]):
        """Enrich nodes with metrics from the activity feed."""
        try:
            from app.services.activity_feed import activity_feed
            metrics = activity_feed.get_metrics(hours=24)

            for resource_type, stats in metrics.get("by_resource_type", {}).items():
                # Try to match resource_type to a node
                candidates = [
                    f"object_type:{resource_type}",
                    f"workflow:{resource_type}",
                    f"action:{resource_type}",
                ]
                for candidate in candidates:
                    if candidate in nodes:
                        node = nodes[candidate]
                        node.execution_count = max(node.execution_count, stats.get("total_events", 0))
                        node.success_rate = stats.get("success_rate_pct", node.success_rate)
                        node.p95_latency_ms = max(node.p95_latency_ms, stats.get("avg_duration_ms", 0) * 1.5)
                        break
        except Exception:
            pass

    @staticmethod
    def _count_by(items, key_fn) -> Dict[str, int]:
        """Count items by a key function."""
        counts: Dict[str, int] = defaultdict(int)
        for item in items:
            counts[key_fn(item)] += 1
        return counts


# =============================================================================
# SINGLETON
# =============================================================================

lineage_graph = LineageGraph()
