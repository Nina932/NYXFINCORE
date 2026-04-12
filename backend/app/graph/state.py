"""
FinAI LangGraph State — Shared state flowing through all agent nodes.
Every node reads from and writes to this typed dict.
"""

from typing import Any, Dict, List, Optional, TypedDict


class FinAIState(TypedDict, total=False):
    # Input
    command: str                          # User command / query
    company_id: int
    company_name: str
    period: str
    file_path: Optional[str]             # Uploaded file path (if any)

    # Data extraction
    extracted_financials: Dict[str, Any]  # Revenue, COGS, etc. from analyzer
    line_items: List[Dict]               # Detailed account-level items
    balance_sheet: Dict[str, Any]
    revenue_breakdown: List[Dict]
    cogs_breakdown: List[Dict]
    data_type: str                        # full_financials, expenses_only, etc.

    # Calculation (deterministic — Decimal math)
    calculated_metrics: Dict[str, Any]    # P&L, margins, ratios

    # Intelligence (reconstruction engine)
    completeness: Dict[str, Any]
    insights: List[Dict]
    company_character: Dict[str, Any]
    suggestions: List[Dict]
    revenue_estimate: Optional[Dict]

    # LLM reasoning (narrative only — never numbers)
    llm_narrative: str
    llm_model_used: str
    llm_confidence: float

    # Cross-period memory
    period_deltas: Dict[str, Any]
    previous_periods: List[Dict]

    # Orchestrator legacy (7-stage pipeline if full data)
    orchestrator_result: Optional[Dict]

    # Anomalies
    anomalies: List[Dict]

    # What-if scenarios
    whatif_scenarios: Dict[str, Any]

    # Alerts
    alerts: List[Dict]

    # Report
    report_path: Optional[str]

    # Circuit breaker (data integrity)
    circuit_breaker_status: Dict[str, Any]  # CircuitBreaker.status_summary()

    # Flow control
    status: str                           # extracting → calculating → reasoning → done
    stages_completed: List[str]
    stages_failed: List[str]
    reasoning_trace: List[str]
    execution_ms: int
