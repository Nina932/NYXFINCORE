"""
Phase Q-1: Financial Chat Engine
===================================
Rule-based NLP query engine for financial questions.
NO LLM needed — uses regex + keyword matching.

Supported intents:
  metric_query     — "What is our gross margin?"
  comparison_query — "How does revenue compare to last period?"
  diagnostic_query — "What are our biggest risks?"
  whatif_query      — "What if revenue increases 20%?"
  report_query     — "Generate a report"
  greeting         — "Hello" / "გამარჯობა"
  unknown          — fallback

Supports English and Georgian bilingual queries.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# METRIC DEFINITIONS (bilingual)
# ═══════════════════════════════════════════════════════════════════

_METRIC_ALIASES: Dict[str, List[str]] = {
    "revenue": [
        "revenue", "sales", "turnover", "top line", "income",
        "შემოსავალი", "გაყიდვები",
    ],
    "cogs": [
        "cogs", "cost of goods", "cost of sales", "direct cost",
        "თვითღირებულება",
    ],
    "gross_profit": [
        "gross profit", "gross income",
        "მთლიანი მოგება",
    ],
    "gross_margin_pct": [
        "gross margin", "gross margin %", "gross margin percent",
        "მთლიანი მარჟა",
    ],
    "net_profit": [
        "net profit", "net income", "bottom line", "net earnings",
        "წმინდა მოგება",
    ],
    "net_margin_pct": [
        "net margin", "net margin %", "net margin percent", "profit margin",
        "წმინდა მარჟა",
    ],
    "ebitda": [
        "ebitda",
        "ებითდა",
    ],
    "ebitda_margin_pct": [
        "ebitda margin", "ebitda margin %",
        "ებითდა მარჟა",
    ],
    "ga_expenses": [
        "g&a", "ga expenses", "admin expenses", "operating expenses", "opex",
        "ადმინისტრაციული ხარჯები", "საოპერაციო ხარჯები",
    ],
    "cogs_to_revenue_pct": [
        "cogs ratio", "cogs to revenue", "cost ratio",
    ],
    "depreciation": [
        "depreciation", "d&a", "amortization",
        "ცვეთა", "ამორტიზაცია",
    ],
    "total_assets": ["total assets", "assets", "აქტივები"],
    "total_liabilities": ["total liabilities", "liabilities", "ვალდებულებები"],
    "total_equity": ["equity", "net worth", "კაპიტალი"],
    "cash": ["cash", "cash balance", "ფულადი სახსრები"],
}

# Reverse index
_ALIAS_TO_METRIC: Dict[str, str] = {}
for _metric, _aliases in _METRIC_ALIASES.items():
    for _alias in _aliases:
        _ALIAS_TO_METRIC[_alias.lower()] = _metric


# ═══════════════════════════════════════════════════════════════════
# INTENT PATTERNS
# ═══════════════════════════════════════════════════════════════════

_INTENT_PATTERNS: Dict[str, List[str]] = {
    "diagnostic_query": [
        r"(?:what\s+are|show)\s+(?:our\s+|the\s+)?(?:biggest\s+)?(?:risks?|problems?|issues?|concerns?)",
        r"why\s+is\s+(?:our\s+|the\s+)?(.+?)\s+(?:declining|dropping|falling|low|negative|bad)",
        r"diagnos(?:e|is|tic)",
        r"health\s+(?:score|check|status|grade)",
        r"what\s+(?:should|do)\s+(?:we|i)\s+(?:worry|care)\s+about",
        # Georgian
        r"რა\s+(?:რისკ|პრობლემ|საფრთხ)",
        r"დიაგნოსტიკა",
        r"ჯანმრთელობ",
    ],
    "comparison_query": [
        r"(?:how\s+does|compare)\s+(.+?)\s+(?:to|with|vs)\s+(?:last|previous|prior)",
        r"is\s+(?:our\s+)?(.+?)\s+(?:improving|growing|declining|decreasing|increasing)",
        r"(.+?)\s+(?:trend|change|growth|decline)",
        # Georgian
        r"(.+?)\s+(?:შედარება|ტრენდი|ცვლილება)",
        r"უმჯობესდება\s+(?:ჩვენი\s+)?(.+?)[\?\.]?$",
    ],
    "whatif_query": [
        r"what\s+(?:if|happens?\s+if)\s+(.+)",
        r"(?:simulate|project|forecast)\s+(.+)",
        r"if\s+(.+?)\s+(?:increases?|decreases?|goes?\s+(?:up|down|to))\s+(.+)",
        r"scenario\s+(.+)",
        # Georgian
        r"რა\s+(?:მოხდება|იქნება)\s+(?:თუ|როცა)\s+(.+)",
    ],
    "action_query": [
        r"(?:run|execute|trigger|start)\s+(?:full\s+)?(?:analysis|orchestrator|pipeline|diagnosis)",
        r"(?:analyze|analyse)\s+(?:this|the|my|data|file|dataset|everything)",
        r"(?:refresh|reload|update)\s+(?:all|data|dashboard|everything|pages)",
        r"(?:move|save)\s+(?:to|it\s+to)\s+(?:dataset|library|store)",
        # Georgian
        r"(?:გაანალიზე|გაუშვი|გაუშვით)\s+",
        r"(?:განახლება|განაახლე|რეფრეშ)",
    ],
    "report_query": [
        r"generate\s+(?:a\s+)?report",
        r"create\s+(?:a\s+|an\s+)?(?:pdf|excel|report|brief|executive)",
        r"(?:export|download)\s+(?:pdf|excel|report)",
        r"show\s+(?:me\s+)?(?:the\s+)?(?:p&?l|income\s+statement|balance\s+sheet)",
        # Georgian
        r"შექმენი?\s+(?:ანგარიშ|რეპორტ)",
        r"გენერაცია\s+(?:pdf|ანგარიშ)",
    ],
    "greeting": [
        r"^(?:hi|hello|hey|good\s+(?:morning|afternoon|evening))[\s!]*$",
        r"^გამარჯობა[\s!]*$",
        r"^სალამი[\s!]*$",
    ],
    # metric_query is LAST — acts as catch-all for "what is X" patterns
    "metric_query": [
        r"what\s+is\s+(?:our\s+|the\s+)?(.+?)[\?\.]?$",
        r"show\s+(?:me\s+)?(?:our\s+|the\s+)?(.+?)[\?\.]?$",
        r"how\s+much\s+is\s+(?:our\s+|the\s+)?(.+?)[\?\.]?$",
        r"tell\s+me\s+(?:about\s+)?(?:our\s+|the\s+)?(.+?)[\?\.]?$",
        # Georgian
        r"რა\s+არის\s+(?:ჩვენი\s+)?(.+?)[\?\.]?$",
        r"რამდენია\s+(?:ჩვენი\s+)?(.+?)[\?\.]?$",
        r"მაჩვენე\s+(.+?)[\?\.]?$",
    ],
}


# ═══════════════════════════════════════════════════════════════════
# ENTITY EXTRACTION
# ═══════════════════════════════════════════════════════════════════

def _extract_metric(text: str) -> Optional[str]:
    """Extract metric name from query text."""
    text_lower = text.lower().strip()

    # Try exact match first
    if text_lower in _ALIAS_TO_METRIC:
        return _ALIAS_TO_METRIC[text_lower]

    # Try contains match
    for alias, metric in _ALIAS_TO_METRIC.items():
        if alias in text_lower:
            return metric

    return None


def _extract_number(text: str) -> Optional[float]:
    """Extract a number (with optional %) from text."""
    match = re.search(r'(\d+(?:\.\d+)?)\s*%?', text)
    if match:
        return float(match.group(1))
    return None


def _extract_whatif_params(text: str) -> Dict[str, Any]:
    """Extract what-if parameters from query."""
    params: Dict[str, Any] = {}
    text_lower = text.lower()

    # Pattern: "revenue increases 20%" or "revenue goes to 60M"
    metric = _extract_metric(text_lower)
    number = _extract_number(text_lower)

    if metric and number:
        if "%" in text or "percent" in text_lower:
            params["metric"] = metric
            params["change_pct"] = number
            if any(w in text_lower for w in ["decrease", "decline", "drop", "reduce", "down"]):
                params["change_pct"] = -number
        else:
            params["metric"] = metric
            params["target_value"] = number

    return params


# ═══════════════════════════════════════════════════════════════════
# RESPONSE FORMATTERS
# ═══════════════════════════════════════════════════════════════════

def _format_value(value: Any, metric: str) -> str:
    """Format a metric value for display."""
    if value is None:
        return "N/A"
    try:
        v = float(value)
        if metric.endswith("_pct"):
            return f"{v:.1f}%"
        elif abs(v) >= 1_000_000:
            return f"{v/1_000_000:,.1f}M GEL"
        elif abs(v) >= 1_000:
            return f"{v:,.0f} GEL"
        return f"{v:,.2f}"
    except (ValueError, TypeError):
        return str(value)


def _metric_display_name(metric: str) -> str:
    """Get human-readable name for a metric."""
    names = {
        "revenue": "Revenue",
        "cogs": "Cost of Goods Sold",
        "gross_profit": "Gross Profit",
        "gross_margin_pct": "Gross Margin",
        "net_profit": "Net Profit",
        "net_margin_pct": "Net Margin",
        "ebitda": "EBITDA",
        "ebitda_margin_pct": "EBITDA Margin",
        "ga_expenses": "G&A Expenses",
        "cogs_to_revenue_pct": "COGS/Revenue Ratio",
        "depreciation": "Depreciation",
        "total_assets": "Total Assets",
        "total_liabilities": "Total Liabilities",
        "total_equity": "Total Equity",
        "cash": "Cash",
    }
    return names.get(metric, metric.replace("_", " ").title())


def _viz_hint(metric: str) -> str:
    """Suggest visualization type."""
    if metric.endswith("_pct"):
        return "gauge"
    elif metric in ("revenue", "net_profit", "ebitda", "cogs"):
        return "bar"
    return "number"


# ═══════════════════════════════════════════════════════════════════
# CHAT ENGINE
# ═══════════════════════════════════════════════════════════════════

@dataclass
class ChatResponse:
    """Structured chat response."""
    intent: str
    answer: str
    data: Dict[str, Any] = field(default_factory=dict)
    visualization_hint: str = "text"
    follow_up_questions: List[str] = field(default_factory=list)
    language: str = "en"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent,
            "answer": self.answer,
            "data": self.data,
            "visualization_hint": self.visualization_hint,
            "follow_up_questions": self.follow_up_questions,
            "language": self.language,
        }


class FinancialChatEngine:
    """
    Rule-based financial query engine.

    No LLM — pure regex + keyword matching for intent classification
    and entity extraction.
    """

    def __init__(self):
        self._financials: Dict[str, float] = {}
        self._previous: Dict[str, float] = {}
        self._balance_sheet: Dict[str, float] = {}

    def set_context(
        self,
        financials: Dict[str, float],
        previous: Optional[Dict[str, float]] = None,
        balance_sheet: Optional[Dict[str, float]] = None,
    ):
        """Set the financial data context for answering queries."""
        self._financials = financials or {}
        self._previous = previous or {}
        self._balance_sheet = balance_sheet or {}

    def query(self, text: str) -> ChatResponse:
        """
        Process a natural language financial query.

        Args:
            text: User query in English or Georgian

        Returns:
            ChatResponse with intent, answer, data, and viz hint
        """
        text = text.strip()
        if not text:
            return ChatResponse("unknown", "Please ask a question.", language="en")

        # Detect language
        lang = "ka" if any(ord(c) >= 0x10D0 and ord(c) <= 0x10FF for c in text) else "en"

        # Classify intent
        intent, match_groups = self._classify_intent(text)

        # Route to handler
        if intent == "metric_query":
            return self._handle_metric(text, match_groups, lang)
        elif intent == "comparison_query":
            return self._handle_comparison(text, match_groups, lang)
        elif intent == "diagnostic_query":
            return self._handle_diagnostic(text, lang)
        elif intent == "whatif_query":
            return self._handle_whatif(text, match_groups, lang)
        elif intent == "action_query":
            return self._handle_action(text, lang)
        elif intent == "report_query":
            return self._handle_report(text, lang)
        elif intent == "greeting":
            return self._handle_greeting(lang)
        else:
            return self._handle_unknown(text, lang)

    # ── Intent Classification ───────────────────────────────────────

    def _classify_intent(self, text: str) -> Tuple[str, List[str]]:
        """Classify query intent using regex patterns."""
        text_lower = text.lower().strip()

        for intent, patterns in _INTENT_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, text_lower)
                if match:
                    return intent, list(match.groups())

        return "unknown", []

    # ── Handlers ────────────────────────────────────────────────────

    def _handle_metric(self, text: str, groups: List[str], lang: str) -> ChatResponse:
        """Handle metric queries."""
        subject = groups[0] if groups else text
        metric = _extract_metric(subject)

        if not metric:
            metric = _extract_metric(text)

        if not metric:
            # No recognized metric — treat as unknown
            return self._handle_unknown(text, lang)

        # Get value
        value = self._financials.get(metric)
        if value is None:
            value = self._balance_sheet.get(metric)

        if value is None:
            return ChatResponse(
                "metric_query",
                f"No data available for {_metric_display_name(metric)}.",
                data={"metric": metric},
                language=lang,
            )

        # Check previous for trend
        prev_value = self._previous.get(metric)
        trend_text = ""
        trend_data: Dict[str, Any] = {}
        if prev_value is not None:
            try:
                change = float(value) - float(prev_value)
                if float(prev_value) != 0:
                    change_pct = change / abs(float(prev_value)) * 100
                else:
                    change_pct = 0
                direction = "up" if change > 0 else "down" if change < 0 else "unchanged"
                if metric.endswith("_pct"):
                    trend_text = f", {direction} {abs(change):.1f} percentage points from previous period"
                else:
                    trend_text = f", {direction} {abs(change_pct):.1f}% from previous period"
                trend_data = {
                    "previous": float(prev_value),
                    "change": change,
                    "change_pct": round(change_pct, 1),
                    "direction": direction,
                }
            except (ValueError, TypeError):
                pass

        formatted = _format_value(value, metric)
        display_name = _metric_display_name(metric)

        answer = f"{display_name} is {formatted}{trend_text}."

        return ChatResponse(
            "metric_query",
            answer,
            data={"metric": metric, "value": value, **trend_data},
            visualization_hint=_viz_hint(metric),
            language=lang,
        )

    def _handle_comparison(self, text: str, groups: List[str], lang: str) -> ChatResponse:
        """Handle comparison queries."""
        subject = groups[0] if groups else text
        metric = _extract_metric(subject)

        if not metric:
            metric = _extract_metric(text)

        if not metric:
            return ChatResponse(
                "comparison_query",
                "Which metric would you like to compare? Try: revenue, margin, profit.",
                language=lang,
            )

        current = self._financials.get(metric)
        previous = self._previous.get(metric)

        if current is None:
            return ChatResponse("comparison_query", f"No current data for {_metric_display_name(metric)}.", language=lang)

        if previous is None:
            return ChatResponse(
                "comparison_query",
                f"Current {_metric_display_name(metric)} is {_format_value(current, metric)}, "
                f"but no previous period data available for comparison.",
                data={"metric": metric, "current": current},
                language=lang,
            )

        try:
            change = float(current) - float(previous)
            change_pct = (change / abs(float(previous)) * 100) if float(previous) != 0 else 0
            trend = "improving" if change > 0 else "declining" if change < 0 else "stable"
        except (ValueError, TypeError):
            change, change_pct, trend = 0, 0, "unknown"

        answer = (
            f"{_metric_display_name(metric)}: "
            f"Current {_format_value(current, metric)} vs "
            f"Previous {_format_value(previous, metric)} "
            f"({'+' if change >= 0 else ''}{change_pct:.1f}% — {trend})."
        )

        return ChatResponse(
            "comparison_query",
            answer,
            data={
                "metric": metric,
                "current": current,
                "previous": previous,
                "change": change,
                "change_pct": round(change_pct, 1),
                "trend": trend,
            },
            visualization_hint="comparison_bar",
            language=lang,
        )

    def _handle_diagnostic(self, text: str, lang: str) -> ChatResponse:
        """Handle diagnostic queries."""
        try:
            from app.services.diagnosis_engine import diagnosis_engine
            report = diagnosis_engine.run_full_diagnosis(
                current_financials=self._financials,
                previous_financials=self._previous or None,
                balance_sheet=self._balance_sheet or None,
            )
            rd = report.to_dict()
            score = rd.get("health_score", 0)
            grade = rd.get("health_grade", "?")
            signals = rd.get("signal_summary", {})
            recs = rd.get("recommendations", [])[:3]
            rec_text = "; ".join(r.get("action", "") for r in recs) if recs else "No specific recommendations."

            answer = (
                f"Health Score: {score:.0f}/100 ({grade}). "
                f"Signals: {signals.get('critical', 0)} critical, "
                f"{signals.get('high', 0)} high, {signals.get('medium', 0)} medium. "
                f"Top actions: {rec_text}"
            )

            return ChatResponse(
                "diagnostic_query", answer,
                data={"health_score": score, "health_grade": grade,
                      "signals": signals, "recommendations": recs},
                visualization_hint="health_gauge",
                language=lang,
            )
        except Exception as e:
            return ChatResponse("diagnostic_query", f"Diagnosis unavailable: {e}", language=lang)

    def _handle_whatif(self, text: str, groups: List[str], lang: str) -> ChatResponse:
        """Handle what-if queries."""
        params = _extract_whatif_params(text)
        metric = params.get("metric")
        change_pct = params.get("change_pct")

        if not metric or change_pct is None:
            return ChatResponse(
                "whatif_query",
                "Please specify a metric and change, e.g., "
                "'What if revenue increases 20%?' or 'What if COGS goes up 10%?'",
                language=lang,
            )

        # Build modified financials
        modified = dict(self._financials)
        original_value = modified.get(metric, 0)
        try:
            new_value = float(original_value) * (1 + change_pct / 100)
            modified[metric] = new_value
        except (ValueError, TypeError):
            return ChatResponse("whatif_query", f"Cannot simulate: invalid {metric} value.", language=lang)

        # Re-derive metrics
        from app.services.smart_excel_parser import compute_derived_metrics
        enriched, _ = compute_derived_metrics(modified)

        # Compare key outputs
        orig_np = self._financials.get("net_profit", 0)
        new_np = enriched.get("net_profit", 0)
        orig_gm = self._financials.get("gross_margin_pct", 0)
        new_gm = enriched.get("gross_margin_pct", 0)

        direction = "increase" if change_pct > 0 else "decrease"
        answer = (
            f"If {_metric_display_name(metric)} {direction}s by {abs(change_pct):.0f}%: "
            f"Net Profit changes from {_format_value(orig_np, 'net_profit')} to "
            f"{_format_value(new_np, 'net_profit')}. "
            f"Gross Margin changes from {_format_value(orig_gm, 'gross_margin_pct')} to "
            f"{_format_value(new_gm, 'gross_margin_pct')}."
        )

        return ChatResponse(
            "whatif_query", answer,
            data={
                "scenario": f"{metric} {direction} {abs(change_pct):.0f}%",
                "original": {metric: original_value, "net_profit": orig_np, "gross_margin_pct": orig_gm},
                "simulated": {metric: new_value, "net_profit": new_np, "gross_margin_pct": new_gm},
            },
            visualization_hint="scenario_comparison",
            language=lang,
        )

    def _handle_action(self, text: str, lang: str) -> ChatResponse:
        """Handle action execution requests — actually runs the orchestrator."""
        text_lower = text.lower()
        action_executed = None
        result_data = {}

        # Determine which action to execute
        if any(kw in text_lower for kw in ["orchestrator", "analysis", "pipeline", "analyze", "analyse", "diagnos"]):
            # Run the full orchestrator
            try:
                from app.services.orchestrator import orchestrator
                financials = dict(self._financials) if self._financials else {}
                previous = dict(self._previous) if self._previous else None

                if not financials or not financials.get("revenue"):
                    return ChatResponse(
                        "action_query",
                        "No financial data loaded. Please upload a dataset first, then ask me to analyze it.",
                        language=lang,
                        data={"action": "orchestrator", "status": "no_data"},
                    )

                orch_result = orchestrator.run(
                    current_financials=financials,
                    previous_financials=previous,
                    balance_sheet=self._balance_sheet,
                    monte_carlo_iterations=200,
                )
                action_executed = "orchestrator"
                rd = orch_result.to_dict()
                summary = rd.get("executive_summary", {})
                result_data = {
                    "action": "orchestrator",
                    "status": "completed",
                    "stages_completed": orch_result.stages_completed,
                    "health_score": summary.get("health_score", 0),
                    "health_grade": summary.get("health_grade", "?"),
                    "strategy": summary.get("strategy_name", "N/A"),
                    "conviction": summary.get("conviction_grade", "?"),
                    "alerts": summary.get("active_alerts", 0),
                    "execution_ms": orch_result.execution_time_ms,
                }

                answer = (
                    f"Full analysis complete in {orch_result.execution_time_ms}ms. "
                    f"Health: {summary.get('health_score', 0):.0f}/100 ({summary.get('health_grade', '?')}). "
                    f"Strategy: {summary.get('strategy_name', 'N/A')}. "
                    f"Conviction: {summary.get('conviction_grade', '?')}. "
                    f"{len(orch_result.stages_completed)} stages completed, {len(orch_result.stages_failed)} failed. "
                    f"Active alerts: {summary.get('active_alerts', 0)}."
                )
            except Exception as e:
                logger.error("Orchestrator execution from chat failed: %s", e)
                answer = f"Analysis failed: {str(e)}"
                result_data = {"action": "orchestrator", "status": "error", "error": str(e)}

        elif any(kw in text_lower for kw in ["refresh", "reload", "update", "განახლება"]):
            answer = (
                "Dashboard refresh triggered. "
                "The frontend should call GET /api/analytics/dashboard to reload all KPIs from the active dataset. "
                "All numbers will update from the database."
            )
            result_data = {
                "action": "refresh",
                "status": "triggered",
                "endpoint": "/api/analytics/dashboard",
                "instruction": "frontend_refresh",
            }
            action_executed = "refresh"

        elif any(kw in text_lower for kw in ["move", "save", "dataset", "store"]):
            answer = (
                "To save data to a dataset, use the Upload page or call POST /api/datasets/upload. "
                "After upload, the dataset will be automatically activated and all pages will refresh."
            )
            result_data = {"action": "save_to_dataset", "endpoint": "/api/datasets/upload"}
            action_executed = "save_hint"

        else:
            answer = "Action understood. Running analysis on your data..."
            result_data = {"action": "generic"}

        return ChatResponse(
            "action_query",
            answer,
            data=result_data,
            visualization_hint="action_result" if action_executed == "orchestrator" else "none",
            follow_up_questions=[
                "What is the health score?",
                "Show me the strategy",
                "Generate a PDF report",
            ] if action_executed == "orchestrator" else [
                "Analyze this data",
                "What are the biggest risks?",
            ],
            language=lang,
        )

    def _handle_report(self, text: str, lang: str) -> ChatResponse:
        """Handle report generation requests."""
        report_type = "full"
        if "brief" in text.lower() or "executive" in text.lower():
            report_type = "executive_brief"
        elif "excel" in text.lower() or "xlsx" in text.lower():
            report_type = "excel"
        elif "p&l" in text.lower() or "income" in text.lower():
            report_type = "income_statement"
        elif "balance" in text.lower():
            report_type = "balance_sheet"

        return ChatResponse(
            "report_query",
            f"Ready to generate {report_type.replace('_', ' ')} report. "
            f"Use the /api/agent/agents/orchestrator/pdf endpoint to download.",
            data={"report_type": report_type, "endpoint": "/api/agent/agents/orchestrator/pdf"},
            visualization_hint="action_button",
            language=lang,
        )

    def _handle_greeting(self, lang: str) -> ChatResponse:
        """Handle greetings."""
        if lang == "ka":
            return ChatResponse("greeting", "გამარჯობა! რით შემიძლია დაგეხმაროთ ფინანსურ ანალიზში?",
                                language="ka")
        return ChatResponse("greeting", "Hello! How can I help you with financial analysis?", language="en")

    def _handle_unknown(self, text: str, lang: str) -> ChatResponse:
        """Handle unrecognized queries."""
        suggestions = [
            "What is our gross margin?",
            "How does revenue compare to last period?",
            "What are our biggest risks?",
            "What if revenue increases 20%?",
            "Generate a report",
        ]
        if lang == "ka":
            answer = "ვერ გავიგე თქვენი კითხვა. სცადეთ: 'რა არის ჩვენი წმინდა მოგება?' ან 'რა რისკები გვაქვს?'"
        else:
            answer = "I'm not sure what you're asking. Try questions like: " + "; ".join(suggestions[:3])

        return ChatResponse("unknown", answer, data={"suggestions": suggestions}, language=lang)


# Module-level singleton
chat_engine = FinancialChatEngine()
