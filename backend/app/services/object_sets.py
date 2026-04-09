"""
ObjectSets — Palantir-style persistent named collections of ontology objects
============================================================================
Object sets are saved, named, shareable filtered collections that can be
used as data sources for Workshop widgets and API queries.

Usage:
    from app.services.object_sets import object_set_manager

    # Create a set
    set_id = object_set_manager.create("High Risk KPIs", "KPI",
        filters=[{"property": "status", "operator": "eq", "value": "breached"}])

    # Resolve (execute the query)
    objects = object_set_manager.resolve(set_id)

    # Use as Workshop data source
    data = object_set_manager.resolve_for_widget(set_id)
"""

from __future__ import annotations
import logging
import uuid
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ObjectSet:
    """A named, persistent collection defined by a query over ontology objects."""
    set_id: str
    name: str
    object_type: str  # e.g. "KPI", "RiskSignal", "Account"
    filters: List[Dict[str, Any]] = field(default_factory=list)
    sort_by: str = ""
    sort_desc: bool = True
    limit: int = 100
    owner: str = "default"
    is_shared: bool = False
    created_at: float = 0.0
    updated_at: float = 0.0
    description: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.time()
            self.updated_at = self.created_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "set_id": self.set_id,
            "name": self.name,
            "object_type": self.object_type,
            "filters": self.filters,
            "sort_by": self.sort_by,
            "sort_desc": self.sort_desc,
            "limit": self.limit,
            "owner": self.owner,
            "is_shared": self.is_shared,
            "description": self.description,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class ObjectSetManager:
    """Manages persistent object sets with live resolution against the ontology."""

    _instance: Optional["ObjectSetManager"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._sets: Dict[str, ObjectSet] = {}
            cls._instance._initialize_defaults()
        return cls._instance

    def _initialize_defaults(self):
        """Create default object sets."""
        defaults = [
            ("breached-kpis", "Breached KPIs", "KPI",
             [{"property": "status", "operator": "eq", "value": "breached"}],
             "KPIs that have breached their threshold"),
            ("critical-risks", "Critical Risk Signals", "RiskSignal",
             [{"property": "severity", "operator": "eq", "value": "high"}],
             "High-severity risk signals requiring attention"),
            ("all-accounts", "Chart of Accounts", "Account",
             [], "Complete chart of accounts"),
            ("all-benchmarks", "Industry Benchmarks", "Benchmark",
             [], "Industry benchmark profiles"),
        ]
        for set_id, name, obj_type, filters, desc in defaults:
            self._sets[set_id] = ObjectSet(
                set_id=set_id, name=name, object_type=obj_type,
                filters=filters, description=desc, is_shared=True,
            )

    def create(
        self, name: str, object_type: str,
        filters: Optional[List[Dict]] = None,
        owner: str = "default", description: str = "",
        sort_by: str = "", limit: int = 100,
    ) -> str:
        """Create a new object set. Returns set_id."""
        set_id = uuid.uuid4().hex[:10]
        self._sets[set_id] = ObjectSet(
            set_id=set_id, name=name, object_type=object_type,
            filters=filters or [], owner=owner, description=description,
            sort_by=sort_by, limit=limit,
        )
        return set_id

    def get(self, set_id: str) -> Optional[ObjectSet]:
        return self._sets.get(set_id)

    def list_sets(self, owner: str = "") -> List[Dict]:
        """List all object sets, optionally filtered by owner."""
        sets = list(self._sets.values())
        if owner:
            sets = [s for s in sets if s.owner == owner or s.is_shared]
        return [s.to_dict() for s in sets]

    def update(self, set_id: str, **kwargs) -> bool:
        s = self._sets.get(set_id)
        if not s:
            return False
        for k, v in kwargs.items():
            if hasattr(s, k):
                setattr(s, k, v)
        s.updated_at = time.time()
        return True

    def delete(self, set_id: str) -> bool:
        if set_id in self._sets:
            del self._sets[set_id]
            return True
        return False

    def resolve(self, set_id: str) -> List[Dict[str, Any]]:
        """Execute the object set query and return matching objects."""
        obj_set = self._sets.get(set_id)
        if not obj_set:
            return []

        try:
            from app.services.ontology_engine import ontology_registry
            objects = ontology_registry.get_objects_by_type(obj_set.object_type)

            # Apply filters
            for f in obj_set.filters:
                prop = f.get("property", "")
                op = f.get("operator", "eq")
                val = f.get("value")
                filtered = []
                for o in objects:
                    obj_val = o.properties.get(prop)
                    if op == "eq" and obj_val == val:
                        filtered.append(o)
                    elif op == "ne" and obj_val != val:
                        filtered.append(o)
                    elif op == "gt" and obj_val is not None and obj_val > val:
                        filtered.append(o)
                    elif op == "lt" and obj_val is not None and obj_val < val:
                        filtered.append(o)
                    elif op == "contains" and val and str(val).lower() in str(obj_val).lower():
                        filtered.append(o)
                    elif op == "exists" and obj_val is not None:
                        filtered.append(o)
                objects = filtered

            # Sort
            if obj_set.sort_by:
                objects.sort(
                    key=lambda o: o.properties.get(obj_set.sort_by, 0) or 0,
                    reverse=obj_set.sort_desc,
                )

            # Limit
            objects = objects[:obj_set.limit]

            return [
                {"object_id": o.object_id, "type": o.object_type, "properties": o.properties}
                for o in objects
            ]
        except Exception as e:
            logger.error("ObjectSet resolve error: %s", e)
            return []

    def resolve_for_widget(self, set_id: str) -> Dict[str, Any]:
        """Resolve and format for Workshop widget consumption."""
        obj_set = self._sets.get(set_id)
        if not obj_set:
            return {"error": f"Object set '{set_id}' not found"}

        objects = self.resolve(set_id)
        return {
            "set_id": set_id,
            "name": obj_set.name,
            "object_type": obj_set.object_type,
            "count": len(objects),
            "data": objects,
            "type": "object_set",
        }

    def status(self) -> Dict:
        return {
            "total_sets": len(self._sets),
            "sets": [s.to_dict() for s in self._sets.values()],
        }


object_set_manager = ObjectSetManager()
