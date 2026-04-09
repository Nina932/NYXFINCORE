"""
StateGraph — LangGraph-compatible graph definition API
=======================================================
Defines nodes (async functions), edges (unconditional or conditional),
compiles into a CompiledGraph for execution.

Usage:
    graph = StateGraph()
    graph.add_node("classify", classify_intent)
    graph.add_node("calc", run_calc_agent)
    graph.add_node("insight", run_insight_agent)
    graph.add_node("merge", merge_results)
    graph.set_entry_point("classify")
    graph.add_conditional_edges("classify", route_fn, {
        "calc": "calc", "insight": "insight", "both": "parallel_calc_insight"
    })
    graph.add_edge("calc", "merge")
    graph.add_edge("insight", "merge")
    graph.set_finish_point("merge")
    compiled = graph.compile()
    result = await compiled.ainvoke({"message": "calculate revenue"})
"""

from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union, Awaitable

logger = logging.getLogger(__name__)

# Sentinel nodes
START = "__start__"
END = "__end__"


@dataclass
class NodeDef:
    """Definition of a graph node."""
    name: str
    fn: Callable[[Dict[str, Any]], Union[Dict[str, Any], Awaitable[Dict[str, Any]]]]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EdgeDef:
    """Unconditional edge: source → target."""
    source: str
    target: str


@dataclass
class ConditionalEdgeDef:
    """Conditional edge: source → router_fn(state) → path_map[key]."""
    source: str
    router_fn: Callable[[Dict[str, Any]], Union[str, Awaitable[str]]]
    path_map: Dict[str, str]  # router_key → target_node_name


class StateGraph:
    """
    LangGraph-compatible state graph builder.

    Nodes are async/sync functions: (state: dict) -> dict (partial state update).
    Edges connect nodes. Conditional edges use a router function to pick the next node.
    """

    def __init__(self, name: str = "default"):
        self.name = name
        self._nodes: Dict[str, NodeDef] = {}
        self._edges: List[EdgeDef] = []
        self._conditional_edges: List[ConditionalEdgeDef] = []
        self._entry_point: Optional[str] = None
        self._finish_points: Set[str] = set()
        self._parallel_groups: Dict[str, List[str]] = {}  # group_name → [node_names]

    def add_node(self, name: str, fn: Callable, **metadata) -> "StateGraph":
        """Register a node with a handler function."""
        if name in (START, END):
            raise ValueError(f"Cannot use reserved name '{name}' as node name")
        if name in self._nodes:
            raise ValueError(f"Node '{name}' already registered")
        self._nodes[name] = NodeDef(name=name, fn=fn, metadata=metadata)
        return self

    def add_edge(self, source: str, target: str) -> "StateGraph":
        """Add unconditional edge: source → target."""
        self._edges.append(EdgeDef(source=source, target=target))
        return self

    def add_conditional_edges(
        self,
        source: str,
        router_fn: Callable[[Dict[str, Any]], Union[str, Awaitable[str]]],
        path_map: Dict[str, str],
    ) -> "StateGraph":
        """Add conditional edge: source → router_fn(state) → path_map[result]."""
        self._conditional_edges.append(ConditionalEdgeDef(
            source=source, router_fn=router_fn, path_map=path_map,
        ))
        return self

    def add_parallel_group(self, group_name: str, node_names: List[str]) -> "StateGraph":
        """Define a group of nodes to execute in parallel."""
        self._parallel_groups[group_name] = node_names
        return self

    def set_entry_point(self, name: str) -> "StateGraph":
        """Set the first node to execute after START."""
        self._entry_point = name
        return self

    def set_finish_point(self, name: str) -> "StateGraph":
        """Mark a node as terminal (connects to END)."""
        self._finish_points.add(name)
        return self

    def compile(self) -> "CompiledGraph":
        """Validate and compile the graph into an executable form."""
        from app.orchestration.compiled_graph import CompiledGraph

        # Validation
        if not self._entry_point:
            raise ValueError("No entry point set. Call set_entry_point()")
        if self._entry_point not in self._nodes:
            raise ValueError(f"Entry point '{self._entry_point}' is not a registered node")

        # Check all edge targets exist
        all_targets = set()
        for e in self._edges:
            if e.source not in self._nodes and e.source != START:
                raise ValueError(f"Edge source '{e.source}' is not a registered node")
            if e.target not in self._nodes and e.target != END:
                raise ValueError(f"Edge target '{e.target}' is not a registered node")
            all_targets.add(e.target)

        for ce in self._conditional_edges:
            if ce.source not in self._nodes and ce.source != START:
                raise ValueError(f"Conditional edge source '{ce.source}' is not a registered node")
            for target in ce.path_map.values():
                if target not in self._nodes and target != END:
                    raise ValueError(f"Conditional edge target '{target}' is not a registered node")
                all_targets.add(target)

        # Build adjacency list
        adjacency: Dict[str, List[Union[str, Tuple[Callable, Dict[str, str]]]]] = {}
        for node_name in self._nodes:
            adjacency[node_name] = []

        # Add START → entry_point
        adjacency[START] = [self._entry_point]

        for e in self._edges:
            adjacency.setdefault(e.source, []).append(e.target)

        for ce in self._conditional_edges:
            adjacency.setdefault(ce.source, []).append((ce.router_fn, ce.path_map))

        # Add finish_points → END
        for fp in self._finish_points:
            adjacency.setdefault(fp, []).append(END)

        logger.info(
            "StateGraph '%s' compiled: %d nodes, %d edges, %d conditional, entry=%s, finish=%s",
            self.name, len(self._nodes), len(self._edges),
            len(self._conditional_edges), self._entry_point, self._finish_points,
        )

        return CompiledGraph(
            name=self.name,
            nodes=dict(self._nodes),
            adjacency=adjacency,
            entry_point=self._entry_point,
            finish_points=self._finish_points,
            parallel_groups=dict(self._parallel_groups),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize graph structure for visualization."""
        nodes = [{"name": n, **nd.metadata} for n, nd in self._nodes.items()]
        edges = [{"source": e.source, "target": e.target, "type": "direct"} for e in self._edges]
        for ce in self._conditional_edges:
            for key, target in ce.path_map.items():
                edges.append({"source": ce.source, "target": target, "type": "conditional", "condition": key})
        return {
            "name": self.name,
            "nodes": nodes,
            "edges": edges,
            "entry_point": self._entry_point,
            "finish_points": list(self._finish_points),
            "parallel_groups": self._parallel_groups,
        }
