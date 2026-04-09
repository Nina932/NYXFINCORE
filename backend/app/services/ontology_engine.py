"""
FinAI OS — Ontology Engine
==========================
Typed object graph with computed fields, relationships, versioning.
Inspired by Palantir Foundry Ontology SDK.

This wraps the existing FinancialKnowledgeGraph (710+ entities) with a
proper typed object system that supports:
  - Property schemas with validation
  - Typed relationships with cardinality
  - Computed fields (formulas that auto-derive values)
  - Version history for every object mutation
  - Semantic queries via OntologyQueryEngine

Usage:
    from app.services.ontology_engine import ontology_registry

    # At startup (after knowledge_graph.build()):
    ontology_registry.initialize()

    # Query:
    companies = ontology_registry.query("Company", {"industry": "fuel_distribution"})
    kpis = ontology_registry.traverse(company_id, "has_kpis", depth=1)
"""

import logging
import uuid
import json
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


# =============================================================================
# SCHEMA DEFINITIONS
# =============================================================================

class DataType(str, Enum):
    STRING = "string"
    FLOAT = "float"
    INT = "int"
    BOOL = "bool"
    DATETIME = "datetime"
    ENUM = "enum"
    JSON = "json"


class Cardinality(str, Enum):
    ONE_TO_ONE = "one_to_one"
    ONE_TO_MANY = "one_to_many"
    MANY_TO_MANY = "many_to_many"


@dataclass
class PropertyDef:
    """Schema for a single property on an ontology object."""
    name: str
    data_type: DataType
    required: bool = False
    default: Any = None
    description: str = ""
    constraints: Dict[str, Any] = field(default_factory=dict)  # min, max, enum_values


@dataclass
class RelationshipDef:
    """Schema for a relationship type between ontology objects."""
    name: str
    target_type: str  # target OntologyType.type_id
    cardinality: Cardinality = Cardinality.ONE_TO_MANY
    inverse_name: Optional[str] = None
    description: str = ""


@dataclass
class ComputedFieldDef:
    """A derived field computed from other properties."""
    name: str
    data_type: DataType = DataType.FLOAT
    formula: str = ""  # human-readable formula string
    dependencies: List[str] = field(default_factory=list)
    compute_fn: Optional[Callable] = None
    description: str = ""


@dataclass
class OntologyType:
    """
    Type definition for ontology objects.
    Analogous to Palantir's Object Types in the Ontology SDK.
    """
    type_id: str  # "Company", "Account", "KPI", etc.
    description: str = ""
    icon: str = ""  # lucide icon name for frontend
    color: str = ""  # hex color for frontend rendering
    properties_schema: Dict[str, PropertyDef] = field(default_factory=dict)
    relationships_schema: Dict[str, RelationshipDef] = field(default_factory=dict)
    computed_fields: Dict[str, ComputedFieldDef] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type_id": self.type_id,
            "description": self.description,
            "icon": self.icon,
            "color": self.color,
            "properties": {k: {"name": v.name, "type": v.data_type.value, "required": v.required, "description": v.description} for k, v in self.properties_schema.items()},
            "relationships": {k: {"name": v.name, "target_type": v.target_type, "cardinality": v.cardinality.value, "inverse": v.inverse_name, "description": v.description} for k, v in self.relationships_schema.items()},
            "computed_fields": {k: {"name": v.name, "type": v.data_type.value, "formula": v.formula, "description": v.description} for k, v in self.computed_fields.items()},
        }


# =============================================================================
# ONTOLOGY OBJECT
# =============================================================================

@dataclass
class OntologyObject:
    """
    A single instance of an ontology type.
    Analogous to a Palantir Object in Foundry.
    """
    object_id: str
    object_type: str  # references OntologyType.type_id
    version: int = 1
    properties: Dict[str, Any] = field(default_factory=dict)
    relationships: Dict[str, List[str]] = field(default_factory=dict)  # rel_name -> [target_ids]
    markings: List[str] = field(default_factory=list)  # Palantir-style security markings
    backing_table: Optional[str] = None  # FIX #3: warehouse table this object maps to
    backing_key: Optional[str] = None  # FIX #3: key in the warehouse table (e.g., account_code)
    created_at: str = ""
    updated_at: str = ""
    source_entity_id: Optional[str] = None  # link back to KnowledgeEntity

    def __post_init__(self):
        now = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    def get(self, prop: str, default: Any = None) -> Any:
        return self.properties.get(prop, default)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "object_id": self.object_id,
            "object_type": self.object_type,
            "version": self.version,
            "properties": self.properties,
            "relationships": self.relationships,
            "markings": self.markings,
            "backing_table": self.backing_table,
            "backing_key": self.backing_key,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "source_entity_id": self.source_entity_id,
        }

    def to_summary(self) -> str:
        """One-line summary for context injection."""
        name = self.properties.get("name") or self.properties.get("code") or self.object_id
        return f"[{self.object_type}:{self.object_id}] {name}"


# =============================================================================
# ONTOLOGY REGISTRY (Singleton)
# =============================================================================

class OntologyRegistry:
    """
    Central registry for ontology types and objects.
    This is the core of FinAI OS — the typed semantic layer.
    """

    def __init__(self):
        self._types: Dict[str, OntologyType] = {}
        self._objects: Dict[str, OntologyObject] = {}
        self._index_by_type: Dict[str, Set[str]] = {}
        self._index_by_property: Dict[str, Dict[Any, Set[str]]] = {}
        self._version_history: Dict[str, List[Dict[str, Any]]] = {}
        self._object_sets: Dict[str, Dict[str, Any]] = {}  # FIX #7: saved Object Sets
        self._audit_log: List[Dict[str, Any]] = []  # FIX #8: audit trail
        self._initialized = False

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def type_count(self) -> int:
        return len(self._types)

    @property
    def object_count(self) -> int:
        return len(self._objects)

    # ─── Type Registration ───────────────────────────────────────────

    def register_type(self, type_def: OntologyType) -> None:
        self._types[type_def.type_id] = type_def
        if type_def.type_id not in self._index_by_type:
            self._index_by_type[type_def.type_id] = set()
        logger.debug(f"Ontology type registered: {type_def.type_id}")

    def get_type(self, type_id: str) -> Optional[OntologyType]:
        return self._types.get(type_id)

    def list_types(self) -> List[OntologyType]:
        return list(self._types.values())

    # ─── Object CRUD ─────────────────────────────────────────────────

    def create_object(
        self,
        type_id: str,
        properties: Dict[str, Any],
        relationships: Optional[Dict[str, List[str]]] = None,
        object_id: Optional[str] = None,
        source_entity_id: Optional[str] = None,
        backing_table: Optional[str] = None,
        backing_key: Optional[str] = None,
    ) -> OntologyObject:
        if type_id not in self._types:
            raise ValueError(f"Unknown ontology type: {type_id}")

        # Auto-assign markings based on type (Palantir governance pattern)
        MARKING_MAP = {
            "Account": ["financial", "accounting"],
            "FinancialStatement": ["financial", "internal"],
            "KPI": ["financial"],
            "RiskSignal": ["financial", "risk"],
            "Action": ["financial", "decision"],
            "Forecast": ["financial", "projection"],
            "Company": ["internal"],
        }
        markings = MARKING_MAP.get(type_id, ["financial"])

        obj = OntologyObject(
            object_id=object_id or str(uuid.uuid4())[:12],
            object_type=type_id,
            version=1,
            properties=properties,
            relationships=relationships or {},
            markings=markings,
            backing_table=backing_table,
            backing_key=backing_key,
            source_entity_id=source_entity_id,
        )

        # Validate
        errors = self._validate(obj)
        if errors:
            logger.warning(f"Validation warnings for {obj.object_id}: {errors}")

        # Store
        self._objects[obj.object_id] = obj
        self._index_by_type.setdefault(type_id, set()).add(obj.object_id)

        # Property indexes (for fast lookups)
        for prop_name, prop_val in properties.items():
            if isinstance(prop_val, (str, int, float, bool)):
                key = f"{type_id}.{prop_name}"
                self._index_by_property.setdefault(key, {}).setdefault(prop_val, set()).add(obj.object_id)

        # FIX #4: Auto-create inverse edges for bidirectional traversal
        type_def = self._types.get(type_id)
        if type_def and relationships:
            for rel_name, target_ids in relationships.items():
                rel_def = type_def.relationships_schema.get(rel_name)
                if rel_def and rel_def.inverse_name:
                    for tid in target_ids:
                        target_obj = self._objects.get(tid)
                        if target_obj:
                            target_obj.relationships.setdefault(rel_def.inverse_name, [])
                            if obj.object_id not in target_obj.relationships[rel_def.inverse_name]:
                                target_obj.relationships[rel_def.inverse_name].append(obj.object_id)

        # Persist to DuckDB (FIX #1: DuckDB as durable store)
        try:
            from app.services.ontology_store import ontology_store
            if ontology_store._initialized:
                ontology_store.save_object(obj)
        except Exception:
            pass

        # Audit trail (FIX #8)
        self._audit("create", obj.object_id, type_id)

        # Emit event → downstream workflows can react
        try:
            from app.services.v2.event_dispatcher import event_dispatcher
            import asyncio
            asyncio.ensure_future(event_dispatcher.dispatch("ontology_object_created", {
                "object_id": obj.object_id, "object_type": type_id,
                "properties": {k: str(v)[:100] for k, v in (properties or {}).items()},
            }))
        except Exception:
            pass

        return obj

    def update_object(self, object_id: str, properties: Dict[str, Any]) -> OntologyObject:
        obj = self._objects.get(object_id)
        if not obj:
            raise ValueError(f"Object not found: {object_id}")

        # Save version history
        self._version_history.setdefault(object_id, []).append({
            "version": obj.version,
            "properties": dict(obj.properties),
            "updated_at": obj.updated_at,
        })

        # Update
        obj.properties.update(properties)
        obj.version += 1
        obj.updated_at = datetime.now(timezone.utc).isoformat()

        # Persist version + update to DuckDB
        try:
            from app.services.ontology_store import ontology_store
            if ontology_store._initialized:
                ontology_store.save_version(obj)
                ontology_store.save_object(obj)
        except Exception:
            pass

        self._audit("update", object_id, obj.object_type)

        # Emit event + recompute computed fields
        try:
            from app.services.v2.event_dispatcher import event_dispatcher
            import asyncio
            changed_keys = list(properties.keys())
            asyncio.ensure_future(event_dispatcher.dispatch("ontology_object_updated", {
                "object_id": object_id, "object_type": obj.object_type,
                "changed_properties": changed_keys,
            }))

            # Auto-recompute computed fields that depend on changed properties
            obj_type = self._types.get(obj.object_type)
            if obj_type and hasattr(obj_type, 'computed_fields'):
                for cf_name, cf_def in (obj_type.computed_fields or {}).items():
                    if cf_def.compute_fn and any(dep in changed_keys for dep in (cf_def.dependencies or [])):
                        try:
                            new_val = cf_def.compute_fn(obj)
                            obj.properties[cf_name] = new_val
                        except Exception:
                            pass
        except Exception:
            pass

        return obj

    def get_object(self, object_id: str) -> Optional[OntologyObject]:
        return self._objects.get(object_id)

    def get_version_history(self, object_id: str) -> List[Dict[str, Any]]:
        return self._version_history.get(object_id, [])

    # ─── Query ───────────────────────────────────────────────────────

    def query(
        self,
        type_id: str,
        filters: Optional[Dict[str, Any]] = None,
        sort_by: Optional[str] = None,
        sort_desc: bool = True,
        limit: int = 100,
    ) -> List[OntologyObject]:
        candidates = self._index_by_type.get(type_id, set())
        results = []

        for oid in candidates:
            obj = self._objects[oid]
            if filters:
                match = True
                for key, val in filters.items():
                    obj_val = obj.properties.get(key)
                    if isinstance(val, dict):
                        op = val.get("op", "eq")
                        cmp_val = val.get("value")
                        if op == "gt" and not (obj_val is not None and obj_val > cmp_val):
                            match = False
                        elif op == "lt" and not (obj_val is not None and obj_val < cmp_val):
                            match = False
                        elif op == "gte" and not (obj_val is not None and obj_val >= cmp_val):
                            match = False
                        elif op == "lte" and not (obj_val is not None and obj_val <= cmp_val):
                            match = False
                        elif op == "contains" and not (obj_val is not None and str(cmp_val).lower() in str(obj_val).lower()):
                            match = False
                        elif op == "in" and obj_val not in cmp_val:
                            match = False
                    else:
                        if obj_val != val:
                            match = False
                    if not match:
                        break
                if not match:
                    continue
            results.append(obj)

        # Sort
        if sort_by:
            results.sort(key=lambda o: o.properties.get(sort_by, 0) or 0, reverse=sort_desc)

        return results[:limit]

    def query_all(self, filters: Optional[Dict[str, Any]] = None, limit: int = 100) -> List[OntologyObject]:
        """Query across all types."""
        results = []
        for type_id in self._types:
            results.extend(self.query(type_id, filters, limit=limit))
        return results[:limit]

    # ─── Traversal ───────────────────────────────────────────────────

    def traverse(
        self,
        object_id: str,
        relationship: Optional[str] = None,
        depth: int = 1,
    ) -> List[OntologyObject]:
        obj = self._objects.get(object_id)
        if not obj:
            return []

        visited: Set[str] = {object_id}
        result: List[OntologyObject] = []
        queue: List[Tuple[str, int]] = [(object_id, 0)]

        while queue:
            current_id, current_depth = queue.pop(0)
            if current_depth >= depth:
                continue
            current = self._objects.get(current_id)
            if not current:
                continue

            rels = current.relationships
            if relationship:
                target_ids = rels.get(relationship, [])
            else:
                target_ids = []
                for ids in rels.values():
                    target_ids.extend(ids)

            for tid in target_ids:
                if tid not in visited and tid in self._objects:
                    visited.add(tid)
                    result.append(self._objects[tid])
                    queue.append((tid, current_depth + 1))

        return result

    def get_subgraph(self, center_id: str, depth: int = 2) -> Dict[str, Any]:
        """Get nodes + edges around an object for graph visualization."""
        center = self._objects.get(center_id)
        if not center:
            return {"nodes": [], "edges": []}

        nodes = [center]
        edges = []
        visited = {center_id}
        queue = [(center_id, 0)]

        while queue:
            cid, d = queue.pop(0)
            if d >= depth:
                continue
            current = self._objects.get(cid)
            if not current:
                continue

            for rel_name, target_ids in current.relationships.items():
                for tid in target_ids:
                    edges.append({"source": cid, "target": tid, "relationship": rel_name})
                    if tid not in visited and tid in self._objects:
                        visited.add(tid)
                        nodes.append(self._objects[tid])
                        queue.append((tid, d + 1))

        return {
            "nodes": [n.to_dict() for n in nodes],
            "edges": edges,
        }

    # ─── Computed Fields ─────────────────────────────────────────────

    def get_computed_field(self, object_id: str, field_name: str) -> Any:
        obj = self._objects.get(object_id)
        if not obj:
            return None

        type_def = self._types.get(obj.object_type)
        if not type_def:
            return None

        cf = type_def.computed_fields.get(field_name)
        if not cf or not cf.compute_fn:
            return None

        try:
            return cf.compute_fn(obj)
        except Exception as e:
            logger.warning(f"Computed field error {field_name} on {object_id}: {e}")
            return None

    # ─── Validation ──────────────────────────────────────────────────

    def _validate(self, obj: OntologyObject) -> List[str]:
        errors = []
        type_def = self._types.get(obj.object_type)
        if not type_def:
            return [f"Unknown type: {obj.object_type}"]

        for prop_name, prop_def in type_def.properties_schema.items():
            if prop_def.required and prop_name not in obj.properties:
                errors.append(f"Missing required property: {prop_name}")

        return errors

    # ─── FIX #2: Security Context + Marking Enforcement ────────────

    def query_secure(
        self,
        type_id: str,
        filters: Optional[Dict[str, Any]] = None,
        user_markings: Optional[List[str]] = None,
        limit: int = 100,
    ) -> List[OntologyObject]:
        """Query with marking-based security enforcement."""
        results = self.query(type_id, filters, limit=limit * 2)  # over-fetch to account for filtering
        if user_markings is not None:
            # Filter: user must have ALL markings on the object
            results = [
                obj for obj in results
                if all(m in user_markings for m in obj.markings)
            ]
        return results[:limit]

    def check_access(self, object_id: str, user_markings: List[str]) -> bool:
        """Check if user has access to an object based on markings."""
        obj = self._objects.get(object_id)
        if not obj:
            return False
        return all(m in user_markings for m in obj.markings)

    # ─── FIX #7: Object Sets (saved, composable queries) ────────────

    def create_object_set(
        self,
        name: str,
        type_id: str,
        filters: Optional[Dict[str, Any]] = None,
        description: str = "",
    ) -> Dict[str, Any]:
        """Create a saved, reusable Object Set."""
        object_set = {
            "set_id": str(uuid.uuid4())[:12],
            "name": name,
            "type_id": type_id,
            "filters": filters or {},
            "description": description,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._object_sets[object_set["set_id"]] = object_set
        return object_set

    def get_object_set(self, set_id: str) -> Optional[Dict[str, Any]]:
        return self._object_sets.get(set_id)

    def evaluate_object_set(self, set_id: str) -> List[OntologyObject]:
        """Evaluate (execute) a saved Object Set."""
        oset = self._object_sets.get(set_id)
        if not oset:
            return []
        return self.query(oset["type_id"], oset.get("filters"), limit=200)

    def list_object_sets(self) -> List[Dict[str, Any]]:
        return list(self._object_sets.values())

    def compose_object_sets(self, set_id_a: str, set_id_b: str, operation: str = "union") -> List[OntologyObject]:
        """Compose two Object Sets: union, intersect, or diff."""
        a = set(o.object_id for o in self.evaluate_object_set(set_id_a))
        b = set(o.object_id for o in self.evaluate_object_set(set_id_b))
        if operation == "union":
            ids = a | b
        elif operation == "intersect":
            ids = a & b
        elif operation == "diff":
            ids = a - b
        else:
            ids = a | b
        return [self._objects[oid] for oid in ids if oid in self._objects]

    # ─── FIX #8: Audit Trail ────────────────────────────────────────

    def _audit(self, action: str, object_id: str, type_id: str = "", user: str = "system", detail: str = ""):
        """Log an audit event for ontology operations."""
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,  # create, update, delete, query, access_denied
            "object_id": object_id,
            "object_type": type_id,
            "user": user,
            "detail": detail,
        }
        self._audit_log.append(event)
        # Keep last 10000 events in memory
        if len(self._audit_log) > 10000:
            self._audit_log = self._audit_log[-5000:]

    def get_audit_log(self, limit: int = 100, action_filter: Optional[str] = None) -> List[Dict]:
        logs = self._audit_log
        if action_filter:
            logs = [e for e in logs if e["action"] == action_filter]
        return list(reversed(logs[-limit:]))

    # ─── FIX #9: Data Lineage ───────────────────────────────────────

    def set_lineage(self, object_id: str, lineage: Dict[str, Any]) -> None:
        """Set lineage metadata on an object (source_table, source_rows, transform)."""
        obj = self._objects.get(object_id)
        if obj:
            obj.properties["_lineage"] = lineage

    def get_lineage(self, object_id: str) -> Optional[Dict[str, Any]]:
        """Get lineage metadata for an object."""
        obj = self._objects.get(object_id)
        if obj:
            return obj.properties.get("_lineage")
        return None

    # ─── Statistics ──────────────────────────────────────────────────

    def stats(self) -> Dict[str, Any]:
        type_counts = {}
        for type_id, obj_ids in self._index_by_type.items():
            type_counts[type_id] = len(obj_ids)

        rel_count = sum(
            sum(len(ids) for ids in obj.relationships.values())
            for obj in self._objects.values()
        )

        return {
            "types": self.type_count,
            "objects": self.object_count,
            "relationships": rel_count,
            "by_type": type_counts,
            "initialized": self._initialized,
        }

    # ─── Initialize: Register Built-in Types + Sync from KG ─────────

    def initialize(self) -> int:
        """Register all built-in types and sync from knowledge graph."""
        self._register_builtin_types()
        count = self._sync_from_knowledge_graph()
        self._register_nyx_computation_rules()
        self._initialized = True
        logger.info(f"Ontology initialized: {self.type_count} types, {self.object_count} objects, {count} synced from KG")
        return count

    def _register_nyx_computation_rules(self):
        """Register NYX Core Thinker P&L calculation rules as ontology computed fields.

        NYX Core Thinker Calculation Rules:
        - GM (Gross Margin) = Revenue(W+R) - COGS(W+R)
        - TGP (Total Gross Profit) = GM + Other Revenue
        - EBITDA = TGP - GA Expenses
        - EBIT = EBITDA - D&A
        - Net Profit = EBIT - Finance Costs - Tax
        """
        # Add computed fields to the KPI type for NYX-specific calculations
        kpi_type = self._types.get("KPI")
        if not kpi_type:
            return

        def _compute_gross_margin(obj: OntologyObject) -> float:
            rev = obj.properties.get("revenue_wholesale", 0) + obj.properties.get("revenue_retail", 0)
            cogs = obj.properties.get("cogs_wholesale", 0) + obj.properties.get("cogs_retail", 0)
            return rev - cogs

        def _compute_tgp(obj: OntologyObject) -> float:
            gm = obj.properties.get("gross_margin", 0)
            other_rev = obj.properties.get("other_revenue", 0)
            return gm + other_rev

        def _compute_ebitda(obj: OntologyObject) -> float:
            tgp = obj.properties.get("total_gross_profit", 0)
            ga = obj.properties.get("ga_expenses", 0)
            return tgp - abs(ga)

        def _compute_ebit(obj: OntologyObject) -> float:
            ebitda = obj.properties.get("ebitda", 0)
            da = obj.properties.get("depreciation_amortization", 0)
            return ebitda - abs(da)

        # Register NYX Core Thinker KPI objects with computation formulas
        nyx_kpis = [
            {
                "id": "kpi_nyx_gm",
                "metric": "Gross Margin",
                "formula": "Revenue(W+R) - COGS(W+R)",
                "unit": "GEL",
                "compute_fn": _compute_gross_margin,
                "dependencies": ["revenue_wholesale", "revenue_retail", "cogs_wholesale", "cogs_retail"],
            },
            {
                "id": "kpi_nyx_tgp",
                "metric": "Total Gross Profit",
                "formula": "GM + Other Revenue",
                "unit": "GEL",
                "compute_fn": _compute_tgp,
                "dependencies": ["gross_margin", "other_revenue"],
            },
            {
                "id": "kpi_nyx_ebitda",
                "metric": "EBITDA",
                "formula": "TGP - GA Expenses",
                "unit": "GEL",
                "compute_fn": _compute_ebitda,
                "dependencies": ["total_gross_profit", "ga_expenses"],
            },
            {
                "id": "kpi_nyx_ebit",
                "metric": "EBIT",
                "formula": "EBITDA - D&A",
                "unit": "GEL",
                "compute_fn": _compute_ebit,
                "dependencies": ["ebitda", "depreciation_amortization"],
            },
        ]

        for kpi_def in nyx_kpis:
            try:
                self.create_object(
                    "KPI",
                    properties={
                        "metric": kpi_def["metric"],
                        "formula": kpi_def["formula"],
                        "unit": kpi_def["unit"],
                        "value": 0,
                        "status": "on_track",
                        "trend": "stable",
                    },
                    object_id=kpi_def["id"],
                )
            except Exception:
                pass  # Already exists or type not registered yet

        # Add NYX Core Thinker computed fields to FinancialStatement type
        fs_type = self._types.get("FinancialStatement")
        if fs_type:
            fs_type.computed_fields["total_gross_profit"] = ComputedFieldDef(
                "total_gross_profit", DataType.FLOAT,
                "gross_profit + other_revenue",
                ["gross_profit", "other_revenue"],
                lambda obj: (obj.properties.get("gross_profit", 0) or 0) + (obj.properties.get("other_revenue", 0) or 0),
                "NYX TGP = Gross Margin + Other Revenue",
            )
            fs_type.computed_fields["ebit"] = ComputedFieldDef(
                "ebit", DataType.FLOAT,
                "ebitda - depreciation_amortization",
                ["ebitda", "depreciation_amortization"],
                lambda obj: (obj.properties.get("ebitda", 0) or 0) - abs(obj.properties.get("depreciation_amortization", 0) or 0),
                "NYX EBIT = EBITDA - D&A",
            )

        logger.info("NYX computation rules registered: %d KPIs, 2 computed fields", len(nyx_kpis))

    def _register_builtin_types(self):
        """Register the 8 core financial ontology types."""

        # ── Company ──
        self.register_type(OntologyType(
            type_id="Company",
            description="A legal entity or business unit",
            icon="Building2",
            color="#4C90F0",
            properties_schema={
                "name": PropertyDef("name", DataType.STRING, required=True, description="Company name"),
                "industry": PropertyDef("industry", DataType.STRING, description="Industry classification"),
                "currency": PropertyDef("currency", DataType.STRING, default="GEL"),
                "country": PropertyDef("country", DataType.STRING, default="GE"),
            },
            relationships_schema={
                "has_periods": RelationshipDef("has_periods", "FinancialPeriod", Cardinality.ONE_TO_MANY, "belongs_to_company"),
                "has_accounts": RelationshipDef("has_accounts", "Account", Cardinality.ONE_TO_MANY),
            },
        ))

        # ── Account ──
        self.register_type(OntologyType(
            type_id="Account",
            description="Chart of accounts entry (1C/IFRS)",
            icon="BookOpen",
            color="#7961DB",
            properties_schema={
                "code": PropertyDef("code", DataType.STRING, required=True, description="Account code (e.g., 6110)"),
                "name_en": PropertyDef("name_en", DataType.STRING, description="English name"),
                "name_ka": PropertyDef("name_ka", DataType.STRING, description="Georgian name"),
                "statement": PropertyDef("statement", DataType.ENUM, description="BS or PL", constraints={"enum_values": ["balance_sheet", "income_statement", "off_balance"]}),
                "side": PropertyDef("side", DataType.ENUM, description="Normal balance side", constraints={"enum_values": ["debit", "credit"]}),
                "account_class": PropertyDef("account_class", DataType.INT, description="IFRS class (1-9)"),
                "is_postable": PropertyDef("is_postable", DataType.BOOL, default=True),
                "ifrs_section": PropertyDef("ifrs_section", DataType.STRING),
            },
            relationships_schema={
                "parent_of": RelationshipDef("parent_of", "Account", Cardinality.ONE_TO_MANY, "child_of"),
                "child_of": RelationshipDef("child_of", "Account", Cardinality.ONE_TO_ONE, "parent_of"),
                "classifies_as": RelationshipDef("classifies_as", "KPI", Cardinality.ONE_TO_MANY),
            },
        ))

        # ── FinancialPeriod ──
        self.register_type(OntologyType(
            type_id="FinancialPeriod",
            description="A reporting period (month/quarter/year)",
            icon="Calendar",
            color="#00A396",
            properties_schema={
                "period_name": PropertyDef("period_name", DataType.STRING, required=True, description="Period identifier (e.g., 2025-01)"),
                "start_date": PropertyDef("start_date", DataType.STRING),
                "end_date": PropertyDef("end_date", DataType.STRING),
                "dataset_id": PropertyDef("dataset_id", DataType.INT),
                "status": PropertyDef("status", DataType.STRING, default="active"),
            },
            relationships_schema={
                "belongs_to_company": RelationshipDef("belongs_to_company", "Company", Cardinality.ONE_TO_ONE),
                "has_statements": RelationshipDef("has_statements", "FinancialStatement", Cardinality.ONE_TO_MANY),
            },
        ))

        # ── FinancialStatement ──
        def _compute_gross_margin(obj: OntologyObject) -> float:
            rev = obj.properties.get("revenue", 0)
            cogs = obj.properties.get("cogs", 0)
            return (rev - cogs) / rev * 100 if rev else 0

        def _compute_net_margin(obj: OntologyObject) -> float:
            rev = obj.properties.get("revenue", 0)
            net = obj.properties.get("net_profit", 0)
            return net / rev * 100 if rev else 0

        def _compute_ebitda_margin(obj: OntologyObject) -> float:
            rev = obj.properties.get("revenue", 0)
            ebitda = obj.properties.get("ebitda", 0)
            return ebitda / rev * 100 if rev else 0

        self.register_type(OntologyType(
            type_id="FinancialStatement",
            description="P&L, Balance Sheet, Cash Flow, or Trial Balance",
            icon="FileText",
            color="#32A467",
            properties_schema={
                "statement_type": PropertyDef("statement_type", DataType.ENUM, required=True, constraints={"enum_values": ["income_statement", "balance_sheet", "cash_flow", "trial_balance"]}),
                "currency": PropertyDef("currency", DataType.STRING, default="GEL"),
                "revenue": PropertyDef("revenue", DataType.FLOAT),
                "cogs": PropertyDef("cogs", DataType.FLOAT),
                "gross_profit": PropertyDef("gross_profit", DataType.FLOAT),
                "ebitda": PropertyDef("ebitda", DataType.FLOAT),
                "net_profit": PropertyDef("net_profit", DataType.FLOAT),
                "total_assets": PropertyDef("total_assets", DataType.FLOAT),
                "total_liabilities": PropertyDef("total_liabilities", DataType.FLOAT),
                "total_equity": PropertyDef("total_equity", DataType.FLOAT),
            },
            relationships_schema={
                "for_period": RelationshipDef("for_period", "FinancialPeriod", Cardinality.ONE_TO_ONE),
                "has_kpis": RelationshipDef("has_kpis", "KPI", Cardinality.ONE_TO_MANY),
                "has_risks": RelationshipDef("has_risks", "RiskSignal", Cardinality.ONE_TO_MANY),
            },
            computed_fields={
                "gross_margin_pct": ComputedFieldDef("gross_margin_pct", DataType.FLOAT, "((revenue - cogs) / revenue) * 100", ["revenue", "cogs"], _compute_gross_margin),
                "net_margin_pct": ComputedFieldDef("net_margin_pct", DataType.FLOAT, "(net_profit / revenue) * 100", ["revenue", "net_profit"], _compute_net_margin),
                "ebitda_margin_pct": ComputedFieldDef("ebitda_margin_pct", DataType.FLOAT, "(ebitda / revenue) * 100", ["revenue", "ebitda"], _compute_ebitda_margin),
            },
        ))

        # ── KPI ──
        self.register_type(OntologyType(
            type_id="KPI",
            description="Key Performance Indicator",
            icon="Activity",
            color="#EC9A3C",
            properties_schema={
                "metric": PropertyDef("metric", DataType.STRING, required=True),
                "value": PropertyDef("value", DataType.FLOAT),
                "threshold": PropertyDef("threshold", DataType.FLOAT),
                "status": PropertyDef("status", DataType.ENUM, constraints={"enum_values": ["on_track", "at_risk", "breached"]}),
                "trend": PropertyDef("trend", DataType.ENUM, constraints={"enum_values": ["improving", "stable", "declining"]}),
                "unit": PropertyDef("unit", DataType.STRING, default="%"),
                "formula": PropertyDef("formula", DataType.STRING),
            },
            relationships_schema={
                "derived_from": RelationshipDef("derived_from", "FinancialStatement", Cardinality.ONE_TO_ONE),
                "triggers": RelationshipDef("triggers", "RiskSignal", Cardinality.ONE_TO_MANY),
            },
        ))

        # ── RiskSignal ──
        self.register_type(OntologyType(
            type_id="RiskSignal",
            description="Financial risk or anomaly signal",
            icon="AlertTriangle",
            color="#E76A6E",
            properties_schema={
                "signal_type": PropertyDef("signal_type", DataType.STRING, required=True),
                "severity": PropertyDef("severity", DataType.ENUM, required=True, constraints={"enum_values": ["info", "low", "medium", "high", "critical", "emergency"]}),
                "metric": PropertyDef("metric", DataType.STRING),
                "current_value": PropertyDef("current_value", DataType.FLOAT),
                "threshold_value": PropertyDef("threshold_value", DataType.FLOAT),
                "message": PropertyDef("message", DataType.STRING),
            },
            relationships_schema={
                "detected_in": RelationshipDef("detected_in", "FinancialPeriod", Cardinality.ONE_TO_ONE),
                "triggers_action": RelationshipDef("triggers_action", "Action", Cardinality.ONE_TO_MANY),
            },
        ))

        # ── Forecast ──
        self.register_type(OntologyType(
            type_id="Forecast",
            description="Financial prediction/forecast",
            icon="TrendingUp",
            color="#147EB3",
            properties_schema={
                "method": PropertyDef("method", DataType.STRING, required=True),
                "metric": PropertyDef("metric", DataType.STRING, required=True),
                "predicted_value": PropertyDef("predicted_value", DataType.FLOAT),
                "confidence": PropertyDef("confidence", DataType.FLOAT),
                "horizon_months": PropertyDef("horizon_months", DataType.INT),
            },
            relationships_schema={
                "based_on": RelationshipDef("based_on", "FinancialStatement", Cardinality.ONE_TO_ONE),
            },
        ))

        # ── Action (wraps DecisionAction) ──
        self.register_type(OntologyType(
            type_id="Action",
            description="Proposed business action (from Decision Engine)",
            icon="Gavel",
            color="#D1980B",
            properties_schema={
                "description": PropertyDef("description", DataType.STRING, required=True),
                "category": PropertyDef("category", DataType.ENUM, constraints={"enum_values": ["cost_reduction", "revenue_growth", "risk_mitigation", "capital_optimization", "operational_efficiency"]}),
                "status": PropertyDef("status", DataType.ENUM, default="proposed", constraints={"enum_values": ["proposed", "pending_approval", "approved", "executing", "completed", "failed", "rejected"]}),
                "roi_estimate": PropertyDef("roi_estimate", DataType.FLOAT),
                "risk_level": PropertyDef("risk_level", DataType.STRING),
                "composite_score": PropertyDef("composite_score", DataType.FLOAT),
                "expected_impact": PropertyDef("expected_impact", DataType.FLOAT),
            },
            relationships_schema={
                "addresses": RelationshipDef("addresses", "RiskSignal", Cardinality.ONE_TO_MANY),
                "for_company": RelationshipDef("for_company", "Company", Cardinality.ONE_TO_ONE),
            },
        ))

        # ── Benchmark ──
        self.register_type(OntologyType(
            type_id="Benchmark",
            description="Industry benchmark metrics",
            icon="BarChart3",
            color="#00A396",
            properties_schema={
                "industry": PropertyDef("industry", DataType.STRING, required=True),
                "metric": PropertyDef("metric", DataType.STRING, required=True),
                "low": PropertyDef("low", DataType.FLOAT),
                "median": PropertyDef("median", DataType.FLOAT),
                "high": PropertyDef("high", DataType.FLOAT),
            },
        ))

        # ── Standard (IFRS) ──
        self.register_type(OntologyType(
            type_id="Standard",
            description="Accounting standard (IFRS/GAAP)",
            icon="BookMarked",
            color="#738091",
            properties_schema={
                "code": PropertyDef("code", DataType.STRING, required=True),
                "title": PropertyDef("title", DataType.STRING),
                "scope": PropertyDef("scope", DataType.STRING),
            },
        ))

    def _sync_from_knowledge_graph(self) -> int:
        """Convert existing KG entities to typed ontology objects."""
        try:
            from app.services.knowledge_graph import knowledge_graph
        except ImportError:
            logger.warning("Knowledge graph not available for sync")
            return 0

        if not knowledge_graph.is_built:
            return 0

        # Mapping: KG entity_type -> OntologyType type_id
        TYPE_MAP = {
            "account": "Account",
            "coa_account": "Account",
            "ratio": "KPI",
            "formula": "KPI",
            "audit_signal": "RiskSignal",
            "fraud_signal": "RiskSignal",
            "benchmark": "Benchmark",
            "ifrs_standard": "Standard",
        }

        count = 0
        for entity_id, entity in knowledge_graph._entities.items():
            onto_type = TYPE_MAP.get(entity.entity_type)
            if not onto_type:
                continue

            # Build properties from KG entity
            props = dict(entity.properties)
            props["name_en"] = entity.label_en
            if entity.label_ka:
                props["name_ka"] = entity.label_ka
            if entity.description:
                props["description"] = entity.description

            # Map specific fields
            if onto_type == "Account":
                code = props.get("account_code", entity_id.replace("coa_", "").replace("account_", ""))
                props.setdefault("code", code)
                props.setdefault("name_en", entity.label_en)
                # Derive account_class from first digit of code
                if code and code[0].isdigit():
                    props["account_class"] = int(code[0])
                    cls = int(code[0])
                    if cls <= 2:
                        props.setdefault("statement", "balance_sheet")
                        props.setdefault("side", "debit")
                    elif cls <= 4:
                        props.setdefault("statement", "balance_sheet")
                        props.setdefault("side", "credit")
                    elif cls == 5:
                        props.setdefault("statement", "balance_sheet")
                        props.setdefault("side", "credit")
                    elif cls <= 9:
                        props.setdefault("statement", "income_statement")
                        props.setdefault("side", "credit" if cls == 6 else "debit")
            elif onto_type == "KPI":
                props.setdefault("metric", entity.label_en)
                formula = props.pop("formula_str", None) or props.pop("formula", None)
                if formula:
                    props["formula"] = str(formula)
            elif onto_type == "RiskSignal":
                props.setdefault("signal_type", entity.entity_type)
                props.setdefault("severity", props.get("risk_level", "medium"))
            elif onto_type == "Benchmark":
                props.setdefault("industry", props.get("industry_id", "general"))
                props.setdefault("metric", entity.label_en)

            # Convert relationships
            rels: Dict[str, List[str]] = {}
            for rel in entity.relationships:
                rels.setdefault(rel.relation_type, []).append(rel.target_id)

            # FIX #3: Map to warehouse backing table
            bt = None
            bk = None
            if onto_type == "Account":
                bt = "dw_trial_balance"
                bk = props.get("code")
            elif onto_type == "Benchmark":
                bt = "ontology_objects"
                bk = entity_id

            try:
                self.create_object(
                    type_id=onto_type,
                    properties=props,
                    relationships=rels,
                    object_id=entity_id,
                    source_entity_id=entity_id,
                    backing_table=bt,
                    backing_key=bk,
                )
                count += 1
            except Exception as e:
                logger.debug(f"Skip KG entity {entity_id}: {e}")

        # ── Build cross-type relationships ──
        self._build_cross_type_relationships()

        return count

    def _build_cross_type_relationships(self):
        """Create meaningful relationships between ontology objects based on financial logic."""
        accounts = self.query("Account", limit=500)
        kpis = self.query("KPI", limit=100)
        standards = self.query("Standard", limit=20)
        benchmarks = self.query("Benchmark", limit=30)
        risk_signals = self.query("RiskSignal", limit=50)

        # ── Account → KPI relationships ──
        # KPIs that reference specific account classes
        kpi_account_map = {
            "gross_margin": [6, 7],  # Revenue (6) and COGS (7) accounts
            "net_margin": [6, 7, 8, 9],
            "current_ratio": [1, 3],  # Current assets (1) and current liabilities (3)
            "debt_to_equity": [3, 4, 5],  # Liabilities (3,4) and equity (5)
            "asset_turnover": [1, 2, 6],  # Assets (1,2) and revenue (6)
            "cogs_ratio": [6, 7],
            "ebitda_margin": [6, 7, 8],
            "opex_ratio": [7, 8],
        }

        for kpi in kpis:
            metric = (kpi.properties.get("metric", "") or "").lower().replace(" ", "_")
            relevant_classes = []
            for pattern, classes in kpi_account_map.items():
                if pattern in metric:
                    relevant_classes = classes
                    break

            if relevant_classes:
                linked_accounts = [
                    a.object_id for a in accounts
                    if a.properties.get("account_class") in relevant_classes
                ][:10]  # Limit to 10 per KPI
                if linked_accounts:
                    kpi.relationships["derived_from_accounts"] = linked_accounts
                    for aid in linked_accounts:
                        acc = self.get_object(aid)
                        if acc:
                            acc.relationships.setdefault("has_kpi", [])
                            if kpi.object_id not in acc.relationships["has_kpi"]:
                                acc.relationships["has_kpi"].append(kpi.object_id)

        # ── Account → Standard relationships ──
        # Link accounts to relevant IFRS standards based on account class
        standard_account_map = {
            "ias16": [2],     # Property, Plant & Equipment → noncurrent assets
            "ias38": [2],     # Intangible Assets → noncurrent assets
            "ias2": [1],      # Inventories → current assets
            "ias7": [1],      # Cash Flow → cash accounts
            "ias12": [3, 9],  # Income Tax → tax liabilities & tax expense
            "ias21": [1, 3],  # Foreign Currency → monetary items
            "ifrs9": [1, 3],  # Financial Instruments → financial assets/liabilities
            "ifrs16": [2, 3], # Leases → right-of-use assets & lease liabilities
        }

        for std in standards:
            std_id_lower = std.object_id.lower()
            for pattern, classes in standard_account_map.items():
                if pattern in std_id_lower:
                    linked = [
                        a.object_id for a in accounts
                        if a.properties.get("account_class") in classes
                    ][:15]
                    if linked:
                        std.relationships["applies_to_accounts"] = linked
                        for aid in linked:
                            acc = self.get_object(aid)
                            if acc:
                                acc.relationships.setdefault("governed_by_standard", [])
                                if std.object_id not in acc.relationships["governed_by_standard"]:
                                    acc.relationships["governed_by_standard"].append(std.object_id)
                    break

        # ── KPI → RiskSignal relationships ──
        for risk in risk_signals:
            risk_metric = (risk.properties.get("metric", "") or "").lower()
            for kpi in kpis:
                kpi_metric = (kpi.properties.get("metric", "") or "").lower()
                if risk_metric and kpi_metric and (risk_metric in kpi_metric or kpi_metric in risk_metric):
                    risk.relationships.setdefault("triggered_by_kpi", [])
                    if kpi.object_id not in risk.relationships["triggered_by_kpi"]:
                        risk.relationships["triggered_by_kpi"].append(kpi.object_id)
                    kpi.relationships.setdefault("triggers_risk", [])
                    if risk.object_id not in kpi.relationships["triggers_risk"]:
                        kpi.relationships["triggers_risk"].append(risk.object_id)

        # ── KPI → Benchmark relationships ──
        for bench in benchmarks:
            bench_metric = (bench.properties.get("metric", "") or "").lower()
            for kpi in kpis:
                kpi_metric = (kpi.properties.get("metric", "") or "").lower()
                if bench_metric and kpi_metric and (bench_metric in kpi_metric or kpi_metric in bench_metric):
                    bench.relationships.setdefault("benchmarks_kpi", [])
                    if kpi.object_id not in bench.relationships["benchmarks_kpi"]:
                        bench.relationships["benchmarks_kpi"].append(kpi.object_id)
                    kpi.relationships.setdefault("benchmarked_by", [])
                    if bench.object_id not in kpi.relationships["benchmarked_by"]:
                        kpi.relationships["benchmarked_by"].append(bench.object_id)

        # Count relationships
        total_rels = sum(
            sum(len(v) for v in obj.relationships.values())
            for obj in self._objects.values()
        )
        logger.info(f"Ontology: built {total_rels} cross-type relationships")

    def sync_financial_data(self, company_name: str, period: str, pnl: Dict, balance_sheet: Optional[Dict] = None) -> Dict[str, str]:
        """
        Derive ontology intelligence objects FROM financial core data.

        This is the critical Layer 1 → Layer 2 connection:
        - Financial core (TB → Statements → SQLite) is source of truth for NUMBERS
        - Ontology derives KPIs, risk signals, and health assessments FROM those numbers
        - Every ontology object carries lineage back to its source

        Returns dict of created object IDs.
        """
        created = {}

        # ── Company (find or create) ──
        existing = self.query("Company", {"name": company_name}, limit=1)
        if existing:
            company_obj = existing[0]
        else:
            company_obj = self.create_object("Company", {
                "name": company_name,
                "industry": "fuel_distribution",
                "currency": "GEL",
            })
        created["company"] = company_obj.object_id

        # ── Financial Period ──
        period_obj = self.create_object("FinancialPeriod", {
            "period_name": period,
            "status": "active",
        }, {"belongs_to_company": [company_obj.object_id]}, object_id=f"period_{period}")
        created["period"] = period_obj.object_id

        # ── Financial Statement (derived FROM core — carries lineage) ──
        rev = pnl.get("revenue", 0) or 0
        cogs = abs(pnl.get("cogs", 0) or 0)
        gp = pnl.get("gross_profit", 0) or (rev - cogs)
        ebitda = pnl.get("ebitda", 0) or 0
        net = pnl.get("net_profit", 0) or 0
        selling = abs(pnl.get("selling_expenses", 0) or 0)
        admin = abs(pnl.get("admin_expenses", 0) or pnl.get("ga_expenses", 0) or 0)
        depr = abs(pnl.get("depreciation", 0) or 0)

        stmt_props = {
            "statement_type": "income_statement",
            "currency": "GEL",
            "revenue": rev,
            "cogs": cogs,
            "gross_profit": gp,
            "selling_expenses": selling,
            "admin_expenses": admin,
            "ebitda": ebitda,
            "depreciation": depr,
            "net_profit": net,
        }
        if balance_sheet:
            bs = balance_sheet
            stmt_props.update({
                "total_assets": bs.get("total_assets", 0) or 0,
                "total_liabilities": bs.get("total_liabilities", 0) or 0,
                "total_equity": bs.get("total_equity", 0) or 0,
                "cash": bs.get("cash", 0) or bs.get("cash_and_equivalents", 0) or 0,
                "receivables": bs.get("receivables", 0) or 0,
                "inventory": bs.get("inventory", 0) or 0,
                "current_assets": bs.get("current_assets", bs.get("total_current_assets", 0)) or 0,
                "current_liabilities": bs.get("current_liabilities", bs.get("total_current_liabilities", 0)) or 0,
                "fixed_assets": bs.get("fixed_assets_net", 0) or 0,
            })

        stmt_obj = self.create_object("FinancialStatement", stmt_props, {
            "for_period": [period_obj.object_id],
        }, object_id=f"stmt_{period}",
            backing_table="financial_snapshots",
            backing_key=period)
        created["statement"] = stmt_obj.object_id

        # Lineage: trace back to financial core
        self.set_lineage(stmt_obj.object_id, {
            "source": "financial_core",
            "source_table": "finai_store.financial_snapshots",
            "period": period,
            "company": company_name,
            "derived_at": datetime.now(timezone.utc).isoformat(),
            "note": "Deterministic copy from TB→Statement pipeline. Numbers are auditable.",
        })

        # ── KPIs (DERIVED from statement — each carries formula lineage) ──
        kpi_defs = []
        if rev > 0:
            gm_pct = (gp / rev) * 100
            nm_pct = (net / rev) * 100
            em_pct = (ebitda / rev) * 100
            cogs_pct = (cogs / rev) * 100
            opex_pct = ((selling + admin) / rev) * 100

            kpi_defs = [
                ("gross_margin", gm_pct, 10.0, "(gross_profit / revenue) × 100", ["gross_profit", "revenue"]),
                ("net_margin", nm_pct, 0.0, "(net_profit / revenue) × 100", ["net_profit", "revenue"]),
                ("ebitda_margin", em_pct, 5.0, "(ebitda / revenue) × 100", ["ebitda", "revenue"]),
                ("cogs_ratio", cogs_pct, 85.0, "(cogs / revenue) × 100", ["cogs", "revenue"]),
                ("opex_ratio", opex_pct, 25.0, "((selling + admin) / revenue) × 100", ["selling_expenses", "admin_expenses", "revenue"]),
            ]

        if balance_sheet:
            ta = stmt_props.get("total_assets", 0)
            tl = stmt_props.get("total_liabilities", 0)
            te = stmt_props.get("total_equity", 0)
            ca = stmt_props.get("current_assets", 0)
            cl = stmt_props.get("current_liabilities", 0)
            cash = stmt_props.get("cash", 0)

            if te and te != 0:
                kpi_defs.append(("debt_to_equity", abs(tl / te), 3.0, "total_liabilities / total_equity", ["total_liabilities", "total_equity"]))
            if cl and cl != 0:
                kpi_defs.append(("current_ratio", ca / cl, 1.0, "current_assets / current_liabilities", ["current_assets", "current_liabilities"]))
            if rev > 0 and ta > 0:
                kpi_defs.append(("asset_turnover", rev / ta, 0.5, "revenue / total_assets", ["revenue", "total_assets"]))
            # Cash runway (months) — uses total monthly cash outflow, not just net profit
            # Monthly burn = operating expenses (COGS + selling + admin + depr) adjusted for non-cash
            monthly_expenses = cogs + selling + admin  # cash expenses (exclude depreciation — non-cash)
            monthly_revenue = rev
            net_monthly_burn = monthly_expenses - monthly_revenue  # positive = burning cash
            if net_monthly_burn > 0 and cash > 0:
                runway = cash / net_monthly_burn
                kpi_defs.append(("cash_runway_months", round(runway, 1), 6.0, "cash / (monthly_expenses - monthly_revenue)", ["cash", "cogs", "selling_expenses", "admin_expenses", "revenue"]))
            elif net < 0 and cash > 0:
                # Fallback: use net loss as burn rate
                runway = cash / abs(net)
                kpi_defs.append(("cash_runway_months", round(runway, 1), 6.0, "cash / abs(net_loss)", ["cash", "net_profit"]))

        for metric, value, threshold, formula, source_fields in kpi_defs:
            # Determine status and trend
            is_ratio = metric in ("debt_to_equity", "cogs_ratio", "opex_ratio")
            if is_ratio:
                status = "on_track" if value <= threshold else "breached"
            else:
                status = "on_track" if value >= threshold else "breached"
            trend = "stable"  # Would need prior period to determine

            kpi_obj = self.create_object("KPI", {
                "metric": metric,
                "value": round(value, 2),
                "threshold": threshold,
                "status": status,
                "trend": trend,
                "unit": "x" if metric in ("debt_to_equity", "current_ratio", "asset_turnover") else ("months" if "months" in metric else "%"),
                "formula": formula,
            }, {"derived_from": [stmt_obj.object_id]}, object_id=f"kpi_{metric}_{period}")
            created[f"kpi_{metric}"] = kpi_obj.object_id

            # Lineage: exactly how this KPI was computed
            self.set_lineage(kpi_obj.object_id, {
                "source": "derived_from_statement",
                "statement_id": stmt_obj.object_id,
                "formula": formula,
                "source_fields": source_fields,
                "source_values": {f: stmt_props.get(f, 0) for f in source_fields},
                "computed_value": round(value, 2),
                "period": period,
            })

            # Auto-generate risk signals for breached KPIs
            if status == "breached":
                severity = "critical" if (not is_ratio and value < -5) or (is_ratio and value > threshold * 2) else "high" if (not is_ratio and value < 0) or (is_ratio and value > threshold * 1.5) else "medium"
                risk = self.create_object("RiskSignal", {
                    "signal_type": f"{metric}_breach",
                    "severity": severity,
                    "metric": metric,
                    "current_value": round(value, 2),
                    "threshold_value": threshold,
                    "message": f"{metric} at {value:.1f}{'x' if 'ratio' in metric or 'turnover' in metric else '%'} {'exceeds' if is_ratio else 'is below'} threshold of {threshold}",
                }, {
                    "detected_in": [period_obj.object_id],
                }, object_id=f"risk_{metric}_{period}")
                created[f"risk_{metric}"] = risk.object_id

                # Lineage for risk signal
                self.set_lineage(risk.object_id, {
                    "source": "derived_from_kpi",
                    "kpi_id": kpi_obj.object_id,
                    "trigger_condition": f"{'>' if is_ratio else '<'} {threshold}",
                    "actual_value": round(value, 2),
                })

                kpi_obj.relationships.setdefault("triggers", []).append(risk.object_id)

            # Link statement → KPIs
            stmt_obj.relationships["has_kpis"] = [v for k, v in created.items() if k.startswith("kpi_")]
            stmt_obj.relationships["has_risks"] = [v for k, v in created.items() if k.startswith("risk_")]

        # Link company → period
        company_obj.relationships.setdefault("has_periods", []).append(period_obj.object_id)

        return created


# =============================================================================
# SINGLETON
# =============================================================================

ontology_registry = OntologyRegistry()
