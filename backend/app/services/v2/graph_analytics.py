"""
FinAI Graph Analytics — Palantir Foundry-Grade
================================================
This is what makes Palantir Palantir:
1. Object-centric analytics — every entity is an object with computed properties
2. Graph traversal — relationships between objects reveal hidden patterns
3. Impact propagation — changes to one object ripple through the graph
4. Anomaly detection through graph structure (not just values)
5. Cross-entity reasoning — "which accounts affect this KPI?"
"""

import logging
from typing import Dict, Any, List, Optional, Set, Tuple
from collections import defaultdict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class GraphNode:
    id: str
    type: str
    label: str
    properties: Dict[str, Any] = field(default_factory=dict)
    weight: float = 1.0


@dataclass
class GraphEdge:
    source: str
    target: str
    relationship: str
    weight: float = 1.0
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ImpactPath:
    """A path through the graph showing how a change propagates."""
    nodes: List[str]
    edges: List[str]
    total_impact: float
    description: str


class GraphAnalytics:
    """Palantir-grade graph analytics over the ontology."""

    def __init__(self):
        self._nodes: Dict[str, GraphNode] = {}
        self._edges: List[GraphEdge] = []
        self._adjacency: Dict[str, List[Tuple[str, str, float]]] = defaultdict(list)  # node -> [(target, rel, weight)]
        self._reverse_adj: Dict[str, List[Tuple[str, str, float]]] = defaultdict(list)  # node -> [(source, rel, weight)]

    def load_from_ontology(self):
        """Load the full graph from ontology registry."""
        try:
            from app.services.ontology_engine import ontology_registry

            # Check if ontology is initialized
            all_types = ontology_registry.list_types()
            logger.info(f"Graph: ontology has {len(all_types)} types, loading...")

            if not all_types:
                # Try getting objects directly from the internal store
                all_objects = list(ontology_registry._objects.values()) if hasattr(ontology_registry, '_objects') else []
                logger.info(f"Graph: direct access found {len(all_objects)} objects")
                for obj in all_objects:
                    label = (obj.properties.get("name_en") or obj.properties.get("name")
                             or obj.properties.get("code") or obj.properties.get("metric")
                             or obj.object_id)
                    node = GraphNode(
                        id=obj.object_id, type=obj.object_type, label=str(label),
                        properties={k: v for k, v in obj.properties.items()
                                   if not isinstance(v, (dict, list)) and not k.startswith("_")},
                    )
                    self._nodes[obj.object_id] = node
                    for rel_type, targets in (obj.relationships or {}).items():
                        target_list = targets if isinstance(targets, list) else [targets] if isinstance(targets, str) else []
                        for target in target_list:
                            tid = target if isinstance(target, str) else str(target)
                            edge = GraphEdge(source=obj.object_id, target=tid, relationship=rel_type)
                            self._edges.append(edge)
                            self._adjacency[obj.object_id].append((tid, rel_type, 1.0))
                            self._reverse_adj[tid].append((obj.object_id, rel_type, 1.0))
                logger.info(f"Graph loaded via direct access: {len(self._nodes)} nodes, {len(self._edges)} edges")
                return

            # Load via typed query
            for type_def in all_types:
                type_id = type_def.type_id if hasattr(type_def, 'type_id') else str(type_def)
                objects = ontology_registry.query(type_id, limit=5000)
                for obj in objects:
                    label = (obj.properties.get("name_en") or obj.properties.get("name")
                             or obj.properties.get("code") or obj.properties.get("metric")
                             or obj.object_id)
                    node = GraphNode(
                        id=obj.object_id,
                        type=obj.object_type,
                        label=str(label),
                        properties={k: v for k, v in obj.properties.items()
                                   if not isinstance(v, (dict, list)) and not k.startswith("_")},
                        weight=obj.properties.get("value", 1.0) if isinstance(obj.properties.get("value"), (int, float)) else 1.0,
                    )
                    self._nodes[obj.object_id] = node

                    # Build edges from relationships
                    for rel_type, targets in (obj.relationships or {}).items():
                        if isinstance(targets, list):
                            for target in targets:
                                target_id = target if isinstance(target, str) else str(target)
                                edge = GraphEdge(source=obj.object_id, target=target_id, relationship=rel_type)
                                self._edges.append(edge)
                                self._adjacency[obj.object_id].append((target_id, rel_type, 1.0))
                                self._reverse_adj[target_id].append((obj.object_id, rel_type, 1.0))
                        elif isinstance(targets, str):
                            edge = GraphEdge(source=obj.object_id, target=targets, relationship=rel_type)
                            self._edges.append(edge)
                            self._adjacency[obj.object_id].append((targets, rel_type, 1.0))
                            self._reverse_adj[targets].append((obj.object_id, rel_type, 1.0))

            logger.info(f"Graph loaded: {len(self._nodes)} nodes, {len(self._edges)} edges")
        except Exception as e:
            logger.error(f"Failed to load graph: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Graph statistics."""
        if not self._nodes:
            self.load_from_ontology()

        type_counts = defaultdict(int)
        for node in self._nodes.values():
            type_counts[node.type] += 1

        rel_counts = defaultdict(int)
        for edge in self._edges:
            rel_counts[edge.relationship] += 1

        # Find most connected nodes
        degree = defaultdict(int)
        for edge in self._edges:
            degree[edge.source] += 1
            degree[edge.target] += 1

        top_connected = sorted(degree.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            "total_nodes": len(self._nodes),
            "total_edges": len(self._edges),
            "node_types": dict(type_counts),
            "relationship_types": dict(rel_counts),
            "avg_degree": round(sum(degree.values()) / max(len(degree), 1), 2),
            "max_degree": max(degree.values()) if degree else 0,
            "top_connected": [{"id": nid, "degree": d, "label": self._nodes.get(nid, GraphNode(nid, "?", "?")).label} for nid, d in top_connected],
            "density": round(len(self._edges) / max(len(self._nodes) * (len(self._nodes) - 1), 1), 6),
        }

    def get_neighborhood(self, node_id: str, depth: int = 2) -> Dict[str, Any]:
        """Get the neighborhood of a node (BFS to depth N)."""
        if not self._nodes:
            self.load_from_ontology()

        visited: Set[str] = set()
        nodes_out = []
        edges_out = []
        queue = [(node_id, 0)]

        while queue:
            current, d = queue.pop(0)
            if current in visited or d > depth:
                continue
            visited.add(current)

            node = self._nodes.get(current)
            if node:
                nodes_out.append({
                    "id": node.id, "type": node.type, "label": node.label,
                    "depth": d, "properties": node.properties,
                })

            # Outgoing edges
            for target, rel, weight in self._adjacency.get(current, []):
                if target not in visited:
                    edges_out.append({"source": current, "target": target, "relationship": rel, "weight": weight})
                    queue.append((target, d + 1))

            # Incoming edges
            for source, rel, weight in self._reverse_adj.get(current, []):
                if source not in visited:
                    edges_out.append({"source": source, "target": current, "relationship": rel, "weight": weight})
                    queue.append((source, d + 1))

        return {
            "center": node_id,
            "depth": depth,
            "nodes": nodes_out,
            "edges": edges_out,
            "node_count": len(nodes_out),
            "edge_count": len(edges_out),
        }

    def impact_analysis(self, node_id: str, change_pct: float = 10.0) -> Dict[str, Any]:
        """
        Palantir-grade impact analysis: what happens if this entity changes by X%?
        Traces the propagation through the graph.
        """
        if not self._nodes:
            self.load_from_ontology()

        impacted: List[Dict[str, Any]] = []
        visited: Set[str] = set()
        queue = [(node_id, change_pct, 0, [node_id])]

        source_node = self._nodes.get(node_id)
        if not source_node:
            return {"error": f"Node {node_id} not found", "available_types": list(set(n.type for n in self._nodes.values()))}

        while queue:
            current, impact, depth, path = queue.pop(0)
            if current in visited or depth > 4 or abs(impact) < 0.1:
                continue
            visited.add(current)

            node = self._nodes.get(current)
            if node and current != node_id:
                impacted.append({
                    "id": node.id,
                    "type": node.type,
                    "label": node.label,
                    "impact_pct": round(impact, 2),
                    "depth": depth,
                    "path": path,
                    "severity": "high" if abs(impact) > 5 else ("medium" if abs(impact) > 1 else "low"),
                })

            # Propagate with dampening
            dampening = 0.6
            for target, rel, weight in self._adjacency.get(current, []):
                if target not in visited:
                    propagated = impact * dampening * weight
                    queue.append((target, propagated, depth + 1, path + [target]))

        # Sort by absolute impact
        impacted.sort(key=lambda x: abs(x["impact_pct"]), reverse=True)

        return {
            "source": {"id": source_node.id, "type": source_node.type, "label": source_node.label},
            "change_pct": change_pct,
            "total_impacted": len(impacted),
            "high_impact": len([i for i in impacted if i["severity"] == "high"]),
            "medium_impact": len([i for i in impacted if i["severity"] == "medium"]),
            "impacted_entities": impacted[:20],
        }

    def find_anomalies(self) -> Dict[str, Any]:
        """Detect structural anomalies in the graph."""
        if not self._nodes:
            self.load_from_ontology()

        anomalies = []

        # 1. Orphan nodes (no edges)
        connected = set()
        for edge in self._edges:
            connected.add(edge.source)
            connected.add(edge.target)
        orphans = [nid for nid in self._nodes if nid not in connected]
        if len(orphans) > len(self._nodes) * 0.1:
            anomalies.append({
                "type": "orphan_nodes",
                "severity": "warning",
                "count": len(orphans),
                "description": f"{len(orphans)} nodes have no relationships ({len(orphans)/len(self._nodes)*100:.0f}% of graph)",
                "examples": orphans[:5],
            })

        # 2. Self-referencing edges
        self_refs = [e for e in self._edges if e.source == e.target]
        if self_refs:
            anomalies.append({
                "type": "self_reference",
                "severity": "info",
                "count": len(self_refs),
                "description": f"{len(self_refs)} self-referencing relationships found",
            })

        # 3. Highly connected nodes (potential hub issues)
        degree = defaultdict(int)
        for edge in self._edges:
            degree[edge.source] += 1
            degree[edge.target] += 1

        avg_degree = sum(degree.values()) / max(len(degree), 1)
        hubs = [(nid, d) for nid, d in degree.items() if d > avg_degree * 5]
        if hubs:
            anomalies.append({
                "type": "hub_concentration",
                "severity": "info",
                "count": len(hubs),
                "description": f"{len(hubs)} nodes have >5x average connections (potential single points of failure)",
                "examples": [{"id": nid, "degree": d, "label": self._nodes.get(nid, GraphNode(nid,"?","?")).label} for nid, d in sorted(hubs, key=lambda x: x[1], reverse=True)[:5]],
            })

        # 4. Missing reverse relationships
        # If A → B exists but B → A doesn't, flag it for bidirectional types
        bidirectional_types = {"related_to", "correlates_with", "depends_on"}
        missing_reverse = 0
        for edge in self._edges:
            if edge.relationship in bidirectional_types:
                has_reverse = any(
                    e.source == edge.target and e.target == edge.source
                    for e in self._edges
                )
                if not has_reverse:
                    missing_reverse += 1
        if missing_reverse > 0:
            anomalies.append({
                "type": "missing_reverse_relationships",
                "severity": "warning",
                "count": missing_reverse,
                "description": f"{missing_reverse} bidirectional relationships lack reverse edges",
            })

        return {
            "total_anomalies": len(anomalies),
            "anomalies": anomalies,
            "graph_health": "good" if not any(a["severity"] == "warning" for a in anomalies) else "needs_attention",
        }

    def cross_entity_query(self, query: str) -> Dict[str, Any]:
        """
        Natural language-like cross-entity query.
        Examples: "accounts affecting gross_margin", "risks related to revenue"
        """
        if not self._nodes:
            self.load_from_ontology()

        query_lower = query.lower()

        # Find matching nodes
        matches = []
        for node in self._nodes.values():
            score = 0
            searchable = f"{node.id} {node.label} {node.type}".lower()
            for word in query_lower.split():
                if word in searchable:
                    score += 1
            if score > 0:
                matches.append((node, score))

        matches.sort(key=lambda x: x[1], reverse=True)
        top_matches = matches[:10]

        # For top matches, get their neighborhoods
        results = []
        for node, score in top_matches:
            neighbors = []
            for target, rel, _ in self._adjacency.get(node.id, []):
                t_node = self._nodes.get(target)
                if t_node:
                    neighbors.append({"id": t_node.id, "type": t_node.type, "label": t_node.label, "relationship": rel})
            for source, rel, _ in self._reverse_adj.get(node.id, []):
                s_node = self._nodes.get(source)
                if s_node:
                    neighbors.append({"id": s_node.id, "type": s_node.type, "label": s_node.label, "relationship": f"reverse:{rel}"})

            results.append({
                "id": node.id,
                "type": node.type,
                "label": node.label,
                "relevance_score": score,
                "connected_to": neighbors[:10],
                "properties": {k: v for k, v in node.properties.items() if not isinstance(v, (dict, list))},
            })

        return {
            "query": query,
            "total_matches": len(matches),
            "results": results,
        }

    def get_subgraph(self, node_type: str = None, limit: int = 100) -> Dict[str, Any]:
        """Get a subgraph for visualization (D3.js compatible format)."""
        if not self._nodes:
            self.load_from_ontology()

        # Filter nodes
        if node_type:
            filtered_nodes = {nid: n for nid, n in self._nodes.items() if n.type == node_type}
        else:
            filtered_nodes = dict(list(self._nodes.items())[:limit])

        node_ids = set(filtered_nodes.keys())

        # Get edges between filtered nodes
        filtered_edges = [
            e for e in self._edges
            if e.source in node_ids and e.target in node_ids
        ]

        # D3.js format
        return {
            "nodes": [
                {"id": n.id, "type": n.type, "label": n.label, "group": n.type}
                for n in filtered_nodes.values()
            ],
            "links": [
                {"source": e.source, "target": e.target, "relationship": e.relationship, "value": e.weight}
                for e in filtered_edges[:500]
            ],
            "node_count": len(filtered_nodes),
            "edge_count": len(filtered_edges),
        }


# Global instance
graph_analytics = GraphAnalytics()
