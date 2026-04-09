"""
FinAI OS — Ontology Query Engine
=================================
Semantic query layer: natural language → structured query → execute against ontology.
Inspired by Palantir's Object Query Language.

Usage:
    from app.services.ontology_query import ontology_query_engine

    result = await ontology_query_engine.natural_query("companies with declining gross margin")
    result = ontology_query_engine.structured_query(StructuredQuery(
        target_type="KPI",
        filters=[FilterClause("status", "eq", "breached")],
    ))
"""

import re
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.services.ontology_engine import ontology_registry, OntologyObject

logger = logging.getLogger(__name__)


# =============================================================================
# QUERY TYPES
# =============================================================================

@dataclass
class FilterClause:
    property: str
    operator: str  # eq, gt, lt, gte, lte, contains, in, not_in, ne
    value: Any

    def to_dict(self) -> Dict:
        return {"property": self.property, "operator": self.operator, "value": self.value}


@dataclass
class TraversalClause:
    relationship: str
    target_type: Optional[str] = None
    depth: int = 1
    filters: List[FilterClause] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "relationship": self.relationship,
            "target_type": self.target_type,
            "depth": self.depth,
            "filters": [f.to_dict() for f in self.filters],
        }


@dataclass
class StructuredQuery:
    target_type: str
    filters: List[FilterClause] = field(default_factory=list)
    traversals: List[TraversalClause] = field(default_factory=list)
    computed_filters: List[FilterClause] = field(default_factory=list)
    sort_by: Optional[str] = None
    sort_desc: bool = True
    limit: int = 50

    def to_dict(self) -> Dict:
        return {
            "target_type": self.target_type,
            "filters": [f.to_dict() for f in self.filters],
            "traversals": [t.to_dict() for t in self.traversals],
            "computed_filters": [f.to_dict() for f in self.computed_filters],
            "sort_by": self.sort_by,
            "sort_desc": self.sort_desc,
            "limit": self.limit,
        }


@dataclass
class QueryResult:
    objects: List[OntologyObject]
    count: int
    execution_ms: float
    query: StructuredQuery
    explanation: str = ""

    def to_dict(self) -> Dict:
        return {
            "objects": [o.to_dict() for o in self.objects],
            "count": self.count,
            "execution_ms": round(self.execution_ms, 2),
            "query": self.query.to_dict(),
            "explanation": self.explanation,
        }


# =============================================================================
# INTENT PATTERNS (Rule-based NL → StructuredQuery)
# =============================================================================

# Pattern: (regex, handler_fn_name)
INTENT_PATTERNS = [
    # Margin/KPI patterns
    (r"(?:show|find|list|get)\s+(?:companies?|firms?)\s+with\s+(?:declining|falling|dropping)\s+(?:gross\s+)?margin",
     "companies_declining_margin"),
    (r"(?:declining|falling|low)\s+(?:gross\s+)?margin",
     "declining_margin_kpis"),
    (r"(?:breached|violated|failed)\s+(?:kpi|threshold|target)s?",
     "breached_kpis"),

    # Risk/Anomaly patterns
    (r"(?:anomal|risk|signal|alert|warning)(?:ies|s)?\s+(?:in|for|of)\s+(?:revenue|income)",
     "revenue_risk_signals"),
    (r"(?:all|active|critical|high)\s+(?:risk|alert|signal|anomal)(?:ies|s)?",
     "active_risks"),

    # Account patterns
    (r"(?:account|coa)\s+(\d{4})",
     "account_by_code"),
    (r"(?:revenue|income)\s+accounts?",
     "revenue_accounts"),
    (r"(?:expense|cost)\s+accounts?",
     "expense_accounts"),

    # Action patterns
    (r"(?:pending|proposed|recommended)\s+actions?",
     "pending_actions"),
    (r"(?:approved|completed)\s+actions?",
     "approved_actions"),

    # Explain patterns
    (r"explain\s+(?:ebitda|margin|profit|revenue|loss)\s+(?:drop|decline|change)",
     "explain_metric_change"),

    # Forecast patterns
    (r"(?:forecast|predict|projection)s?\s+(?:for|of)\s+(\w+)",
     "forecasts_for_metric"),

    # Benchmark patterns
    (r"(?:benchmark|industry|compare)\s+(?:for|of|against)\s+(\w+)",
     "benchmarks_for_industry"),

    # General type queries
    (r"(?:all|list|show|get)\s+(companies|accounts|kpis?|risks?|forecasts?|actions?|statements?|periods?|benchmarks?|standards?)",
     "list_by_type"),
]

# Type name aliases
TYPE_ALIASES = {
    "companies": "Company", "company": "Company", "firms": "Company",
    "accounts": "Account", "account": "Account", "coa": "Account",
    "kpis": "KPI", "kpi": "KPI", "metrics": "KPI",
    "risks": "RiskSignal", "risk": "RiskSignal", "signals": "RiskSignal", "anomalies": "RiskSignal",
    "forecasts": "Forecast", "forecast": "Forecast", "predictions": "Forecast",
    "actions": "Action", "action": "Action", "decisions": "Action",
    "statements": "FinancialStatement", "statement": "FinancialStatement",
    "periods": "FinancialPeriod", "period": "FinancialPeriod",
    "benchmarks": "Benchmark", "benchmark": "Benchmark",
    "standards": "Standard", "standard": "Standard",
}


# =============================================================================
# QUERY ENGINE
# =============================================================================

class OntologyQueryEngine:
    """
    Semantic query engine over the ontology registry.
    Translates natural language to structured queries and executes them.
    """

    def __init__(self):
        self._compiled_patterns = [(re.compile(p, re.IGNORECASE), handler) for p, handler in INTENT_PATTERNS]

    def parse_query(self, nl_query: str) -> StructuredQuery:
        """Parse natural language into a structured ontology query."""
        nl = nl_query.strip().lower()

        # Try each pattern
        for pattern, handler_name in self._compiled_patterns:
            match = pattern.search(nl)
            if match:
                handler = getattr(self, f"_intent_{handler_name}", None)
                if handler:
                    return handler(match, nl)

        # Fallback: try to extract a type name
        for alias, type_id in TYPE_ALIASES.items():
            if alias in nl:
                return StructuredQuery(target_type=type_id, limit=50)

        # Final fallback: search all objects
        return StructuredQuery(target_type="KPI", limit=20)

    def execute(self, query: StructuredQuery) -> QueryResult:
        """Execute a structured query against the ontology registry."""
        start = time.time()

        # Convert FilterClauses to registry filter format
        filters = {}
        for fc in query.filters:
            if fc.operator == "eq":
                filters[fc.property] = fc.value
            else:
                filters[fc.property] = {"op": fc.operator, "value": fc.value}

        # Main query
        objects = ontology_registry.query(
            type_id=query.target_type,
            filters=filters if filters else None,
            sort_by=query.sort_by,
            sort_desc=query.sort_desc,
            limit=query.limit,
        )

        # Apply traversals
        if query.traversals:
            traversed = []
            for obj in objects:
                for trav in query.traversals:
                    related = ontology_registry.traverse(obj.object_id, trav.relationship, trav.depth)
                    if trav.filters:
                        related = self._apply_filters(related, trav.filters)
                    traversed.extend(related)
            if query.traversals and not query.filters:
                objects = traversed
            else:
                objects.extend(traversed)

        # Apply computed field filters
        if query.computed_filters:
            filtered = []
            for obj in objects:
                match = True
                for cf in query.computed_filters:
                    val = ontology_registry.get_computed_field(obj.object_id, cf.property)
                    if val is None:
                        match = False
                        break
                    if not self._compare(val, cf.operator, cf.value):
                        match = False
                        break
                if match:
                    filtered.append(obj)
            objects = filtered

        # Deduplicate
        seen = set()
        unique = []
        for obj in objects:
            if obj.object_id not in seen:
                seen.add(obj.object_id)
                unique.append(obj)
        objects = unique[:query.limit]

        elapsed = (time.time() - start) * 1000
        explanation = self._explain(query, len(objects))

        return QueryResult(
            objects=objects,
            count=len(objects),
            execution_ms=elapsed,
            query=query,
            explanation=explanation,
        )

    async def natural_query(self, nl_query: str) -> QueryResult:
        """Full pipeline: NL → parse → execute."""
        query = self.parse_query(nl_query)
        return self.execute(query)

    # ─── Intent Handlers ─────────────────────────────────────────────

    def _intent_companies_declining_margin(self, match, nl) -> StructuredQuery:
        return StructuredQuery(
            target_type="KPI",
            filters=[
                FilterClause("metric", "contains", "margin"),
                FilterClause("trend", "eq", "declining"),
            ],
        )

    def _intent_declining_margin_kpis(self, match, nl) -> StructuredQuery:
        return StructuredQuery(
            target_type="KPI",
            filters=[FilterClause("trend", "eq", "declining")],
            sort_by="value",
            sort_desc=False,
        )

    def _intent_breached_kpis(self, match, nl) -> StructuredQuery:
        return StructuredQuery(
            target_type="KPI",
            filters=[FilterClause("status", "eq", "breached")],
            sort_by="value",
            sort_desc=False,
        )

    def _intent_revenue_risk_signals(self, match, nl) -> StructuredQuery:
        return StructuredQuery(
            target_type="RiskSignal",
            filters=[FilterClause("metric", "contains", "revenue")],
            sort_by="severity",
        )

    def _intent_active_risks(self, match, nl) -> StructuredQuery:
        severity = "critical" if "critical" in nl else "high" if "high" in nl else None
        filters = []
        if severity:
            filters.append(FilterClause("severity", "eq", severity))
        return StructuredQuery(target_type="RiskSignal", filters=filters, sort_by="severity")

    def _intent_account_by_code(self, match, nl) -> StructuredQuery:
        code = match.group(1)
        return StructuredQuery(
            target_type="Account",
            filters=[FilterClause("code", "contains", code)],
        )

    def _intent_revenue_accounts(self, match, nl) -> StructuredQuery:
        return StructuredQuery(
            target_type="Account",
            filters=[FilterClause("account_class", "eq", 6)],
        )

    def _intent_expense_accounts(self, match, nl) -> StructuredQuery:
        return StructuredQuery(
            target_type="Account",
            filters=[FilterClause("account_class", "in", [7, 8])],
        )

    def _intent_pending_actions(self, match, nl) -> StructuredQuery:
        return StructuredQuery(
            target_type="Action",
            filters=[FilterClause("status", "in", ["proposed", "pending_approval"])],
            sort_by="composite_score",
        )

    def _intent_approved_actions(self, match, nl) -> StructuredQuery:
        return StructuredQuery(
            target_type="Action",
            filters=[FilterClause("status", "in", ["approved", "completed"])],
        )

    def _intent_explain_metric_change(self, match, nl) -> StructuredQuery:
        return StructuredQuery(
            target_type="RiskSignal",
            sort_by="severity",
            limit=10,
        )

    def _intent_forecasts_for_metric(self, match, nl) -> StructuredQuery:
        metric = match.group(1) if match.lastindex else ""
        filters = [FilterClause("metric", "contains", metric)] if metric else []
        return StructuredQuery(target_type="Forecast", filters=filters)

    def _intent_benchmarks_for_industry(self, match, nl) -> StructuredQuery:
        industry = match.group(1) if match.lastindex else ""
        filters = [FilterClause("industry", "contains", industry)] if industry else []
        return StructuredQuery(target_type="Benchmark", filters=filters)

    def _intent_list_by_type(self, match, nl) -> StructuredQuery:
        type_name = match.group(1).lower().strip()
        type_id = TYPE_ALIASES.get(type_name, "KPI")
        return StructuredQuery(target_type=type_id, limit=50)

    # ─── Helpers ─────────────────────────────────────────────────────

    def _apply_filters(self, objects: List[OntologyObject], filters: List[FilterClause]) -> List[OntologyObject]:
        result = []
        for obj in objects:
            match = True
            for fc in filters:
                val = obj.properties.get(fc.property)
                if not self._compare(val, fc.operator, fc.value):
                    match = False
                    break
            if match:
                result.append(obj)
        return result

    def _compare(self, val: Any, op: str, target: Any) -> bool:
        if val is None:
            return False
        try:
            if op == "eq":
                return val == target
            elif op == "ne":
                return val != target
            elif op == "gt":
                return float(val) > float(target)
            elif op == "lt":
                return float(val) < float(target)
            elif op == "gte":
                return float(val) >= float(target)
            elif op == "lte":
                return float(val) <= float(target)
            elif op == "contains":
                return str(target).lower() in str(val).lower()
            elif op == "in":
                return val in target
            elif op == "not_in":
                return val not in target
        except (ValueError, TypeError):
            return False
        return False

    def _explain(self, query: StructuredQuery, result_count: int) -> str:
        parts = [f"Search {query.target_type} objects"]
        if query.filters:
            filter_strs = [f"{f.property} {f.operator} {f.value}" for f in query.filters]
            parts.append(f"where {' AND '.join(filter_strs)}")
        if query.traversals:
            trav_strs = [f"→ {t.relationship}" for t in query.traversals]
            parts.append(f"traverse {', '.join(trav_strs)}")
        if query.sort_by:
            parts.append(f"sorted by {query.sort_by} {'DESC' if query.sort_desc else 'ASC'}")
        parts.append(f"→ {result_count} results")
        return " | ".join(parts)


# =============================================================================
# SINGLETON
# =============================================================================

ontology_query_engine = OntologyQueryEngine()
