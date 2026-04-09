"""
citation_service.py — Source provenance tracking for FinAI AI responses.

Every figure the AI produces must be traceable to its exact source:
  - For DB-backed data: dataset → sheet → row → entity_id
  - For vector-store context: the matching document with its metadata
  - For calculations: the formula + input values used
  - For external data: the API + timestamp

Citation Structure (each entry in AgentResult.citations):
{
    "ref":          "①",          # Display symbol (① ② ③ ...)
    "claim":        "Diesel COGS was 12.4M GEL",  # What was said
    "value":        12400000.0,   # Numeric value if applicable
    "source_type":  "revenue" | "transaction" | "cogs" | "ga_expense" |
                    "budget" | "vector_search" | "knowledge_graph" |
                    "calculation" | "external_api",
    "dataset_id":   3,
    "dataset_name": "January 2025",
    "entity_id":    1234,         # DB primary key of the row
    "source_file":  "NYX_Jan2025.xlsx",
    "source_sheet": "Revenue Breakdown",
    "source_row":   42,           # Excel row number if known
    "account_code": "611",
    "period":       "January 2025",
    "confidence":   0.95,
    "display_label": "Jan 2025 · Revenue Breakdown · row 42",
}

Usage:
    tracker = CitationTracker()

    # Track a vector search result
    tracker.add_from_vector_sources(sources, query)

    # Track a specific DB entity
    tracker.add_db_entity("revenue", entity_id=42, dataset_id=3,
                           dataset_name="Jan 2025", source_file="...",
                           source_sheet="Revenue Breakdown",
                           value=12_400_000, claim="Diesel revenue net")

    # Get all collected citations
    citations = tracker.citations   # List[Dict]
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Citation reference symbols  ① ② ③ ④ ⑤ ⑥ ⑦ ⑧ ⑨ ⑩ ...
_REF_SYMBOLS = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"


def _ref_symbol(n: int) -> str:
    """Return circled number ① for n=1, ② for n=2 ... ⑳ for n=20, [n] beyond."""
    if 1 <= n <= len(_REF_SYMBOLS):
        return _REF_SYMBOLS[n - 1]
    return f"[{n}]"


class CitationTracker:
    """
    Collects source citations during a single agent execution.

    Instantiate one per request/task. Call `add_*` methods as data is
    retrieved, then read `.citations` at the end to get the full list.
    """

    def __init__(self):
        self._citations: List[Dict[str, Any]] = []
        self._seen: set = set()   # deduplicate by (source_type, entity_id)

    @property
    def citations(self) -> List[Dict[str, Any]]:
        return list(self._citations)

    @property
    def count(self) -> int:
        return len(self._citations)

    # ------------------------------------------------------------------
    # Core add method
    # ------------------------------------------------------------------

    def add(
        self,
        source_type: str,
        *,
        claim: str = "",
        value: Optional[float] = None,
        entity_id: Optional[int] = None,
        dataset_id: Optional[int] = None,
        dataset_name: str = "",
        source_file: str = "",
        source_sheet: str = "",
        source_row: Optional[int] = None,
        account_code: str = "",
        period: str = "",
        confidence: float = 1.0,
        extra: Optional[Dict] = None,
    ) -> str:
        """
        Add a citation. Returns the reference symbol (e.g. "①").

        Deduplicates: if the same (source_type, entity_id) was already
        added, returns the existing reference symbol without duplicating.
        """
        dedup_key = (source_type, entity_id)
        for existing in self._citations:
            if (existing["source_type"], existing.get("entity_id")) == dedup_key and entity_id is not None:
                return existing["ref"]

        ref_num = len(self._citations) + 1
        ref = _ref_symbol(ref_num)

        parts = []
        if period:
            parts.append(period)
        if source_sheet:
            parts.append(source_sheet)
        if source_row:
            parts.append(f"row {source_row}")
        display_label = " · ".join(parts) if parts else source_type

        citation: Dict[str, Any] = {
            "ref":          ref,
            "claim":        claim,
            "value":        value,
            "source_type":  source_type,
            "entity_id":    entity_id,
            "dataset_id":   dataset_id,
            "dataset_name": dataset_name,
            "source_file":  source_file,
            "source_sheet": source_sheet,
            "source_row":   source_row,
            "account_code": account_code,
            "period":       period,
            "confidence":   confidence,
            "display_label": display_label,
        }
        if extra:
            citation.update(extra)

        self._citations.append(citation)
        return ref

    # ------------------------------------------------------------------
    # Convenience builders
    # ------------------------------------------------------------------

    def add_from_vector_sources(
        self,
        sources: List[Dict[str, Any]],
        query: str = "",
    ) -> List[str]:
        """
        Add citations from vector store search result metadata.

        `sources` is the list returned by `get_context_with_sources()`.
        Returns list of ref symbols in insertion order.
        """
        refs = []
        for src in sources:
            source_type = src.get("source_type") or src.get("source") or "vector_search"
            ref = self.add(
                source_type=source_type,
                entity_id=src.get("entity_id"),
                dataset_id=src.get("dataset_id"),
                dataset_name=src.get("dataset_name", ""),
                source_file=src.get("source_file", ""),
                source_sheet=src.get("source_sheet", ""),
                period=src.get("period", ""),
                account_code=src.get("account_code", ""),
                value=src.get("amount") or src.get("net") or src.get("gross"),
                claim=src.get("content", ""),
                confidence=float(src.get("score", 0.8)),
                extra={
                    "product":      src.get("product"),
                    "dept":         src.get("dept"),
                    "counterparty": src.get("counterparty"),
                    "segment":      src.get("segment"),
                },
            )
            refs.append(ref)
        return refs

    def add_db_entity(
        self,
        source_type: str,
        entity_id: int,
        dataset_id: int,
        *,
        claim: str = "",
        value: Optional[float] = None,
        dataset_name: str = "",
        source_file: str = "",
        source_sheet: str = "",
        source_row: Optional[int] = None,
        account_code: str = "",
        period: str = "",
        **kwargs,
    ) -> str:
        """Add a citation for a specific DB record."""
        return self.add(
            source_type=source_type,
            claim=claim,
            value=value,
            entity_id=entity_id,
            dataset_id=dataset_id,
            dataset_name=dataset_name,
            source_file=source_file,
            source_sheet=source_sheet,
            source_row=source_row,
            account_code=account_code,
            period=period,
            extra=kwargs or None,
        )

    def add_calculation(
        self,
        formula: str,
        result: float,
        inputs: Dict[str, Any],
        claim: str = "",
    ) -> str:
        """Add a citation for a computed/derived value."""
        return self.add(
            source_type="calculation",
            claim=claim or formula,
            value=result,
            confidence=1.0,
            extra={"formula": formula, "inputs": inputs},
        )

    def add_external_api(
        self,
        api_name: str,
        endpoint: str,
        value: float,
        claim: str = "",
        data_quality: str = "live",
    ) -> str:
        """Add a citation for an external API data point."""
        return self.add(
            source_type="external_api",
            claim=claim,
            value=value,
            confidence=1.0 if data_quality == "live" else 0.6,
            extra={
                "api_name":    api_name,
                "endpoint":    endpoint,
                "data_quality": data_quality,
            },
        )

    def add_knowledge_graph(
        self,
        entity_id: str,
        entity_type: str,
        claim: str = "",
        account_code: str = "",
    ) -> str:
        """Add a citation for a knowledge graph lookup."""
        return self.add(
            source_type="knowledge_graph",
            claim=claim,
            account_code=account_code,
            confidence=1.0,
            extra={
                "kg_entity_id":   entity_id,
                "kg_entity_type": entity_type,
            },
        )

    # ------------------------------------------------------------------
    # Bulk extraction from tool result data
    # ------------------------------------------------------------------

    def extract_from_tool_result(
        self,
        tool_name: str,
        tool_params: Dict[str, Any],
        tool_result: Any,
    ) -> List[str]:
        """
        Auto-extract citations from a known tool's result structure.

        Handles the main FinAI tools:
        - analyze_revenue, analyze_cogs, analyze_expenses, analyze_pl
        - get_transactions, search_counterparty
        - detect_anomalies, run_scenario
        """
        refs = []
        dataset_id = tool_params.get("dataset_id") or tool_params.get("dataset")
        period = tool_params.get("period", "")

        if not isinstance(tool_result, dict):
            return refs

        # Revenue analysis tools
        if tool_name in ("analyze_revenue",):
            items = tool_result.get("items") or tool_result.get("revenue_items") or []
            for item in items[:10]:  # cap at 10 citations per tool
                if isinstance(item, dict):
                    ref = self.add_db_entity(
                        "revenue",
                        entity_id=item.get("id", 0),
                        dataset_id=dataset_id or 0,
                        claim=f"{item.get('product', '')} net {item.get('net', 0):,.0f}",
                        value=item.get("net") or item.get("gross"),
                        period=period,
                        source_sheet="Revenue Breakdown",
                    )
                    refs.append(ref)

        elif tool_name in ("analyze_cogs",):
            items = tool_result.get("items") or tool_result.get("cogs_items") or []
            for item in items[:10]:
                if isinstance(item, dict):
                    ref = self.add_db_entity(
                        "cogs",
                        entity_id=item.get("id", 0),
                        dataset_id=dataset_id or 0,
                        claim=f"COGS {item.get('product', '')} {item.get('total_cogs', 0):,.0f}",
                        value=item.get("total_cogs"),
                        period=period,
                        source_sheet="COGS Breakdown",
                    )
                    refs.append(ref)

        elif tool_name in ("get_transactions", "search_counterparty"):
            txns = tool_result.get("transactions") or tool_result.get("items") or []
            for txn in txns[:8]:
                if isinstance(txn, dict):
                    ref = self.add_db_entity(
                        "transaction",
                        entity_id=txn.get("id", 0),
                        dataset_id=dataset_id or 0,
                        claim=f"{txn.get('counterparty', '')} {txn.get('amount', 0):,.0f}",
                        value=txn.get("amount"),
                        period=period,
                        source_sheet="Base",
                        extra={
                            "dept":         txn.get("dept"),
                            "cost_class":   txn.get("cost_class"),
                            "counterparty": txn.get("counterparty"),
                            "acct_dr":      txn.get("acct_dr"),
                            "acct_cr":      txn.get("acct_cr"),
                        },
                    )
                    refs.append(ref)

        return refs


# Module-level singleton — replaced per-request as needed
citation_tracker = CitationTracker()
