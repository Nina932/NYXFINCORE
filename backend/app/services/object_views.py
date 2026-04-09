"""
FinAI OS — Rich Object Detail Views (Palantir Object View Pattern)
===================================================================
Generates rich, contextual views for ontology objects with formatted
properties, linked objects, chart configs, and AI-generated summaries.

Key concepts:
  - ObjectViewGenerator: creates rich views for any ontology object type
  - ObjectView: structured response with prominent properties, linked objects,
    embedded chart configs, and deterministic AI summaries
  - Property formatting: currency (color-coded), percentage, status badges,
    relative dates

Usage:
    from app.services.object_views import object_view_generator

    view = object_view_generator.generate_view("company-1")
    # Returns ObjectView with properties, charts, linked objects, actions
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class FormattedProperty:
    """A formatted property for display."""
    name: str
    value: Any
    format: str = "text"  # text, currency, percentage, status, date, number
    color_rule: Optional[str] = None  # green_positive, red_negative, threshold, badge

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "format": self.format,
            "color_rule": self.color_rule,
        }


@dataclass
class LinkedObject:
    """A linked ontology object reference."""
    id: str
    type: str
    display_name: str
    key_property: Optional[Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "display_name": self.display_name,
            "key_property": self.key_property,
        }


@dataclass
class ChartConfig:
    """Embedded chart configuration for frontend rendering."""
    chart_type: str  # line, bar, pie, gauge, sparkline
    title: str
    data: Any  # chart-specific data payload

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chart_type": self.chart_type,
            "title": self.title,
            "data": self.data,
        }


@dataclass
class ObjectView:
    """Rich detail view for an ontology object."""
    object_id: str
    object_type: str
    display_name: str
    icon: str
    prominent_properties: List[FormattedProperty]
    properties: List[FormattedProperty]
    linked_objects: Dict[str, List[LinkedObject]]
    charts: List[ChartConfig]
    actions: List[Dict[str, str]]
    ai_summary: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "object_id": self.object_id,
            "object_type": self.object_type,
            "display_name": self.display_name,
            "icon": self.icon,
            "prominent_properties": [p.to_dict() for p in self.prominent_properties],
            "properties": [p.to_dict() for p in self.properties],
            "linked_objects": {
                link_type: [lo.to_dict() for lo in objects]
                for link_type, objects in self.linked_objects.items()
            },
            "charts": [c.to_dict() for c in self.charts],
            "actions": self.actions,
            "ai_summary": self.ai_summary,
        }


# =============================================================================
# FORMATTING HELPERS
# =============================================================================

def format_currency(value: float, currency: str = "GEL") -> str:
    """Format a number as currency with M/K suffix."""
    if value is None:
        return "N/A"
    sign = "" if value >= 0 else "-"
    abs_val = abs(value)
    if abs_val >= 1_000_000:
        return f"{sign}{currency[0] if currency == 'GEL' else '$'}{abs_val/1_000_000:.1f}M"
    elif abs_val >= 1_000:
        return f"{sign}{currency[0] if currency == 'GEL' else '$'}{abs_val/1_000:.1f}K"
    else:
        return f"{sign}{currency[0] if currency == 'GEL' else '$'}{abs_val:,.0f}"


def format_percentage(value: float) -> str:
    """Format as percentage."""
    if value is None:
        return "N/A"
    return f"{value:.1f}%"


def format_relative_date(iso_str: str) -> str:
    """Format an ISO date as relative time."""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        diff = now - dt
        if diff.days == 0:
            hours = diff.seconds // 3600
            if hours == 0:
                minutes = diff.seconds // 60
                return f"{minutes} minutes ago" if minutes > 1 else "just now"
            return f"{hours} hours ago"
        elif diff.days == 1:
            return "yesterday"
        elif diff.days < 7:
            return f"{diff.days} days ago"
        elif diff.days < 30:
            return f"{diff.days // 7} weeks ago"
        else:
            return dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return str(iso_str)


def color_for_value(value: float, thresholds: Dict[str, float] = None) -> str:
    """Determine color based on value and thresholds."""
    if thresholds:
        if value >= thresholds.get("green", float("inf")):
            return "green"
        elif value >= thresholds.get("yellow", float("-inf")):
            return "yellow"
        else:
            return "red"
    # Default: positive green, negative red
    if value > 0:
        return "green"
    elif value < 0:
        return "red"
    return "neutral"


# =============================================================================
# OBJECT VIEW GENERATOR
# =============================================================================

class ObjectViewGenerator:
    """Generates rich, contextual views for ontology objects."""

    # Icon mapping per type
    TYPE_ICONS = {
        "Company": "building-2",
        "Account": "receipt",
        "KPI": "gauge",
        "RiskSignal": "alert-triangle",
        "FinancialStatement": "file-text",
        "Dataset": "database",
        "Workflow": "git-branch",
        "Action": "zap",
    }

    def generate_view(self, object_id: str) -> Optional[ObjectView]:
        """Generate a rich view for any ontology object."""
        try:
            from app.services.ontology_engine import ontology_registry
        except ImportError:
            return None

        obj = ontology_registry.get_object(object_id)
        if not obj:
            return None

        # Dispatch to type-specific generator
        generators = {
            "Company": self._generate_company_view,
            "Account": self._generate_account_view,
            "KPI": self._generate_kpi_view,
            "RiskSignal": self._generate_risk_view,
            "FinancialStatement": self._generate_statement_view,
        }

        generator_fn = generators.get(obj.object_type, self._generate_generic_view)
        return generator_fn(obj)

    def get_history(self, object_id: str) -> Dict[str, Any]:
        """Get historical values from warehouse for an object."""
        try:
            from app.services.ontology_engine import ontology_registry
            from app.services.warehouse import warehouse
        except ImportError:
            return {"object_id": object_id, "history": []}

        obj = ontology_registry.get_object(object_id)
        if not obj:
            return {"object_id": object_id, "history": []}

        # Try warehouse query based on backing table
        history = []
        if obj.backing_table and warehouse._initialized:
            try:
                key_col = obj.backing_key or "id"
                key_val = obj.properties.get("code") or obj.object_id
                rows = warehouse.execute(
                    f"SELECT * FROM {obj.backing_table} WHERE {key_col} = ? ORDER BY created_at DESC LIMIT 100",
                    [key_val]
                )
                history = rows if rows else []
            except Exception:
                pass

        # Also include version history from ontology
        versions = ontology_registry.get_version_history(object_id)

        return {
            "object_id": object_id,
            "object_type": obj.object_type,
            "warehouse_history": history,
            "version_history": versions,
        }

    def get_related(self, object_id: str) -> Dict[str, Any]:
        """Get related objects grouped by link type."""
        try:
            from app.services.ontology_engine import ontology_registry
        except ImportError:
            return {"object_id": object_id, "related": {}}

        obj = ontology_registry.get_object(object_id)
        if not obj:
            return {"object_id": object_id, "related": {}}

        related = {}
        for rel_name, target_ids in obj.relationships.items():
            group = []
            for tid in target_ids:
                target = ontology_registry.get_object(tid)
                if target:
                    name = (target.properties.get("name_ka")
                            or target.properties.get("name_en")
                            or target.properties.get("name")
                            or target.properties.get("metric")
                            or target.properties.get("code")
                            or tid)
                    key_prop = None
                    if target.object_type == "KPI":
                        key_prop = target.properties.get("value")
                    elif target.object_type == "Account":
                        key_prop = target.properties.get("balance")
                    group.append(LinkedObject(
                        id=tid,
                        type=target.object_type,
                        display_name=str(name),
                        key_property=key_prop,
                    ))
            if group:
                related[rel_name] = [lo.to_dict() for lo in group]

        return {
            "object_id": object_id,
            "object_type": obj.object_type,
            "related": related,
            "total_links": sum(len(v) for v in related.values()),
        }

    # ── Type-specific generators ─────────────────────────────────────

    def _generate_company_view(self, obj) -> ObjectView:
        """Rich view for a Company object."""
        props = obj.properties
        name = props.get("name", "Unknown Company")
        industry = props.get("industry", "unknown")

        # Gather data from data_store
        health_score = None
        kpi_summary = {}
        risk_count = 0
        action_count = 0
        periods = []

        try:
            from app.services.data_store import data_store
            companies = data_store.list_companies()
            company_id = None
            for c in companies:
                if name.lower() in c.get("name", "").lower():
                    company_id = c["id"]
                    break

            if company_id:
                periods = data_store.get_all_periods(company_id)
                if periods:
                    fin = data_store.get_financials(company_id, periods[-1])
                    if fin:
                        kpi_summary = {
                            "revenue": fin.get("revenue", 0),
                            "gross_margin": fin.get("gross_margin_pct", 0),
                            "ebitda": fin.get("ebitda", 0),
                            "net_profit": fin.get("net_profit", 0),
                        }
                # Get orchestrator result for health score
                orch = data_store.get_last_orchestrator_result(company_id) if company_id else None
                if isinstance(orch, dict):
                    inner = orch.get("result")
                    if isinstance(inner, str):
                        import json
                        try:
                            inner = json.loads(inner)
                        except Exception:
                            inner = {}
                    if isinstance(inner, dict):
                        health_score = inner.get("health_score") or inner.get("company_character", {}).get("health_score")
        except Exception:
            pass

        try:
            from app.services.monitoring_engine import monitoring_engine
            alerts = monitoring_engine.get_active_alerts() if hasattr(monitoring_engine, 'get_active_alerts') else []
            risk_count = len(alerts)
        except Exception:
            pass

        try:
            from app.services.action_engine import action_engine
            action_count = len(action_engine.get_pending())
        except Exception:
            pass

        prominent = [
            FormattedProperty("Revenue", format_currency(kpi_summary.get("revenue", 0)), "currency", "green_positive"),
            FormattedProperty("Gross Margin", format_percentage(kpi_summary.get("gross_margin", 0)), "percentage",
                              "threshold" if kpi_summary.get("gross_margin", 0) < 15 else None),
            FormattedProperty("Health Score", health_score or "N/A", "status",
                              "badge"),
            FormattedProperty("Active Risks", risk_count, "number", "red_negative" if risk_count > 0 else None),
        ]

        all_props = [
            FormattedProperty("Industry", industry, "text"),
            FormattedProperty("Periods Available", len(periods), "number"),
            FormattedProperty("EBITDA", format_currency(kpi_summary.get("ebitda", 0)), "currency", "green_positive"),
            FormattedProperty("Net Profit", format_currency(kpi_summary.get("net_profit", 0)), "currency", "green_positive"),
            FormattedProperty("Pending Actions", action_count, "number"),
            FormattedProperty("Last Updated", format_relative_date(obj.updated_at), "date"),
        ]

        # Linked objects
        linked = {}
        if obj.relationships:
            for rel_name, target_ids in obj.relationships.items():
                linked_list = []
                try:
                    from app.services.ontology_engine import ontology_registry
                    for tid in target_ids[:10]:
                        target = ontology_registry.get_object(tid)
                        if target:
                            linked_list.append(LinkedObject(
                                id=tid, type=target.object_type,
                                display_name=str(target.properties.get("name", tid)),
                                key_property=target.properties.get("value"),
                            ))
                except Exception:
                    pass
                if linked_list:
                    linked[rel_name] = linked_list

        charts = []
        if kpi_summary.get("revenue"):
            charts.append(ChartConfig(
                chart_type="gauge",
                title="Gross Margin",
                data={"value": kpi_summary.get("gross_margin", 0), "min": 0, "max": 100,
                      "thresholds": [15, 25, 40]},
            ))

        # Deterministic AI summary
        rev = kpi_summary.get("revenue", 0)
        margin = kpi_summary.get("gross_margin", 0)
        health = health_score or "unknown"
        summary = (
            f"{name} operates in the {industry.replace('_', ' ')} sector. "
            f"Current revenue stands at {format_currency(rev)} with a {margin:.1f}% gross margin. "
            f"Health status: {health}. "
            f"{'No active risks detected.' if risk_count == 0 else f'{risk_count} active risk(s) require attention.'} "
            f"{action_count} pending action(s) in the queue."
        )

        return ObjectView(
            object_id=obj.object_id,
            object_type="Company",
            display_name=name,
            icon=self.TYPE_ICONS.get("Company", "building-2"),
            prominent_properties=prominent,
            properties=all_props,
            linked_objects={k: v for k, v in linked.items()},
            charts=charts,
            actions=[
                {"action": "run_analysis", "label": "Run Full Analysis", "icon": "play"},
                {"action": "generate_report", "label": "Generate Report", "icon": "file-text"},
                {"action": "view_kpis", "label": "View KPIs", "icon": "bar-chart"},
                {"action": "view_risks", "label": "View Risks", "icon": "alert-triangle"},
            ],
            ai_summary=summary,
        )

    def _generate_account_view(self, obj) -> ObjectView:
        """Rich view for an Account object."""
        props = obj.properties
        code = props.get("code", "")
        name_ka = props.get("name_ka") or props.get("name", "")
        name_ru = props.get("name_ru", "")
        ifrs_class = props.get("ifrs_classification") or props.get("classification", "")
        balance = props.get("balance", 0)

        # Get KG context for richer data
        kg_context = {}
        try:
            from app.services.knowledge_graph import knowledge_graph
            if knowledge_graph.is_built:
                kg_context = knowledge_graph.get_context_for_account(code)
        except Exception:
            pass

        prominent = [
            FormattedProperty("Account Code", code, "text"),
            FormattedProperty("Balance", format_currency(balance), "currency", "green_positive"),
            FormattedProperty("IFRS Classification", ifrs_class, "status", "badge"),
        ]

        all_props = [
            FormattedProperty("Name (Georgian)", name_ka, "text"),
            FormattedProperty("Name (Russian)", name_ru, "text"),
            FormattedProperty("Normal Balance", props.get("normal_balance", "debit"), "text"),
            FormattedProperty("BS Section", props.get("bs_section", "N/A"), "text"),
            FormattedProperty("PL Line", props.get("pl_line", "N/A"), "text"),
            FormattedProperty("Last Updated", format_relative_date(obj.updated_at), "date"),
        ]

        # Related KPIs and standards from KG
        linked = {}
        if kg_context.get("related_ratios"):
            linked["related_ratios"] = [
                LinkedObject(id=r.get("id", ""), type="KPI",
                             display_name=r.get("label", ""), key_property=r.get("formula"))
                for r in kg_context.get("related_ratios", [])[:5]
            ]
        if kg_context.get("ifrs_standards"):
            linked["ifrs_standards"] = [
                LinkedObject(id=s.get("id", ""), type="Standard",
                             display_name=s.get("label", ""), key_property=None)
                for s in kg_context.get("ifrs_standards", [])[:5]
            ]

        summary = (
            f"Account {code}: {name_ka or name_ru}. "
            f"Classified as {ifrs_class}. "
            f"Current balance: {format_currency(balance)}."
        )

        return ObjectView(
            object_id=obj.object_id,
            object_type="Account",
            display_name=f"{code} - {name_ka or name_ru}",
            icon=self.TYPE_ICONS.get("Account", "receipt"),
            prominent_properties=prominent,
            properties=all_props,
            linked_objects=linked,
            charts=[],
            actions=[
                {"action": "view_transactions", "label": "View Transactions", "icon": "list"},
                {"action": "reclassify", "label": "Reclassify Account", "icon": "edit"},
            ],
            ai_summary=summary,
        )

    def _generate_kpi_view(self, obj) -> ObjectView:
        """Rich view for a KPI object."""
        props = obj.properties
        name = props.get("name", "Unknown KPI")
        value = props.get("value", 0)
        target = props.get("target")
        formula = props.get("formula", "")
        unit = props.get("unit", "")

        # Determine status
        status = "on_track"
        if target is not None:
            try:
                if isinstance(target, (int, float)) and isinstance(value, (int, float)):
                    if value < target * 0.8:
                        status = "breached"
                    elif value < target * 0.95:
                        status = "warning"
            except (TypeError, ValueError):
                pass

        # Determine trend
        trend = props.get("trend", "stable")
        previous = props.get("previous_value")
        if previous is not None and isinstance(value, (int, float)) and isinstance(previous, (int, float)):
            if value > previous:
                trend = "up"
            elif value < previous:
                trend = "down"

        fmt = "percentage" if unit == "%" else "currency" if unit in ("GEL", "USD") else "number"

        prominent = [
            FormattedProperty("Current Value",
                              format_percentage(value) if fmt == "percentage" else
                              format_currency(value) if fmt == "currency" else value,
                              fmt,
                              "green_positive" if status == "on_track" else "red_negative"),
            FormattedProperty("Target",
                              format_percentage(target) if fmt == "percentage" and target else
                              format_currency(target) if fmt == "currency" and target else (target or "N/A"),
                              fmt),
            FormattedProperty("Status", status, "status", "badge"),
            FormattedProperty("Trend", trend, "status", "badge"),
        ]

        all_props = [
            FormattedProperty("Formula", formula, "text"),
            FormattedProperty("Unit", unit, "text"),
            FormattedProperty("Previous Value", previous if previous is not None else "N/A", fmt),
            FormattedProperty("Last Updated", format_relative_date(obj.updated_at), "date"),
        ]

        # Source accounts
        linked = {}
        source_accounts = props.get("source_accounts", [])
        if source_accounts and isinstance(source_accounts, list):
            linked["source_accounts"] = [
                LinkedObject(id=f"account-{a}", type="Account",
                             display_name=str(a), key_property=None)
                for a in source_accounts[:10]
            ]

        charts = []
        if isinstance(value, (int, float)):
            charts.append(ChartConfig(
                chart_type="gauge",
                title=name,
                data={"value": value, "target": target,
                      "min": 0, "max": (target or value) * 1.5 if target or value else 100,
                      "status": status},
            ))

        summary = (
            f"KPI '{name}' is currently at {value}{unit}. "
            f"Target: {target if target is not None else 'not set'}. "
            f"Status: {status}, trend: {trend}. "
            f"{'Formula: ' + formula + '.' if formula else ''}"
        )

        return ObjectView(
            object_id=obj.object_id,
            object_type="KPI",
            display_name=name,
            icon=self.TYPE_ICONS.get("KPI", "gauge"),
            prominent_properties=prominent,
            properties=all_props,
            linked_objects=linked,
            charts=charts,
            actions=[
                {"action": "set_target", "label": "Set Target", "icon": "target"},
                {"action": "view_history", "label": "View History", "icon": "clock"},
                {"action": "create_alert", "label": "Create Alert Rule", "icon": "bell"},
            ],
            ai_summary=summary,
        )

    def _generate_risk_view(self, obj) -> ObjectView:
        """Rich view for a RiskSignal object."""
        props = obj.properties
        signal_type = props.get("type") or props.get("signal_type", "unknown")
        severity = props.get("severity", "warning")
        current = props.get("current_value", 0)
        threshold = props.get("threshold", 0)
        message = props.get("message", "")

        prominent = [
            FormattedProperty("Signal Type", signal_type, "text"),
            FormattedProperty("Severity", severity, "status", "badge"),
            FormattedProperty("Current Value", current, "number",
                              "red_negative" if severity in ("critical", "emergency") else "yellow"),
            FormattedProperty("Threshold", threshold, "number"),
        ]

        all_props = [
            FormattedProperty("Message", message, "text"),
            FormattedProperty("Metric", props.get("metric", "N/A"), "text"),
            FormattedProperty("Created At", format_relative_date(obj.created_at), "date"),
        ]

        # Recommended actions
        actions_list = props.get("recommended_actions", [])
        linked = {}
        if actions_list:
            linked["recommended_actions"] = [
                LinkedObject(id=f"action-{i}", type="Action",
                             display_name=str(a), key_property=None)
                for i, a in enumerate(actions_list[:5])
            ]

        # Affected KPIs
        affected = props.get("affected_kpis", [])
        if affected:
            linked["affected_kpis"] = [
                LinkedObject(id=f"kpi-{k}", type="KPI",
                             display_name=str(k), key_property=None)
                for k in affected[:5]
            ]

        summary = (
            f"Risk signal: {signal_type} (severity: {severity}). "
            f"Current value {current} vs threshold {threshold}. "
            f"{message}"
        )

        return ObjectView(
            object_id=obj.object_id,
            object_type="RiskSignal",
            display_name=f"{severity.upper()}: {signal_type}",
            icon=self.TYPE_ICONS.get("RiskSignal", "alert-triangle"),
            prominent_properties=prominent,
            properties=all_props,
            linked_objects=linked,
            charts=[],
            actions=[
                {"action": "acknowledge", "label": "Acknowledge", "icon": "check"},
                {"action": "create_action", "label": "Create Action", "icon": "zap"},
                {"action": "snooze", "label": "Snooze", "icon": "clock"},
            ],
            ai_summary=summary,
        )

    def _generate_statement_view(self, obj) -> ObjectView:
        """Rich view for a FinancialStatement object."""
        props = obj.properties
        period = props.get("period", "Unknown")
        company = props.get("company", "")

        revenue = props.get("revenue", 0)
        cogs = props.get("cogs", 0)
        gross_profit = props.get("gross_profit", revenue - cogs if revenue and cogs else 0)
        gross_margin = (gross_profit / revenue * 100) if revenue else 0
        ebitda = props.get("ebitda", 0)
        net_profit = props.get("net_profit", 0)

        # Prior period comparison
        prev_revenue = props.get("prev_revenue")
        rev_change = None
        if prev_revenue and isinstance(prev_revenue, (int, float)) and prev_revenue != 0:
            rev_change = ((revenue - prev_revenue) / abs(prev_revenue)) * 100

        health_score = props.get("health_score")

        prominent = [
            FormattedProperty("Revenue", format_currency(revenue), "currency", "green_positive"),
            FormattedProperty("Gross Margin", format_percentage(gross_margin), "percentage",
                              "red_negative" if gross_margin < 15 else "green_positive"),
            FormattedProperty("Net Profit", format_currency(net_profit), "currency",
                              "green_positive" if net_profit >= 0 else "red_negative"),
            FormattedProperty("Health Score", health_score or "N/A", "status", "badge"),
        ]

        all_props = [
            FormattedProperty("Period", period, "text"),
            FormattedProperty("Company", company, "text"),
            FormattedProperty("COGS", format_currency(cogs), "currency"),
            FormattedProperty("Gross Profit", format_currency(gross_profit), "currency", "green_positive"),
            FormattedProperty("EBITDA", format_currency(ebitda), "currency", "green_positive"),
            FormattedProperty("Revenue Change", format_percentage(rev_change) if rev_change is not None else "N/A",
                              "percentage", "green_positive" if (rev_change or 0) >= 0 else "red_negative"),
        ]

        charts = [
            ChartConfig(
                chart_type="bar",
                title="P&L Waterfall",
                data={
                    "labels": ["Revenue", "COGS", "Gross Profit", "EBITDA", "Net Profit"],
                    "values": [revenue, -abs(cogs), gross_profit, ebitda, net_profit],
                    "colors": ["green", "red", "blue", "blue", "green" if net_profit >= 0 else "red"],
                },
            ),
        ]

        # Key ratios
        ratios = {}
        if revenue:
            ratios["gross_margin"] = round(gross_margin, 1)
            ratios["ebitda_margin"] = round(ebitda / revenue * 100, 1) if ebitda else 0
            ratios["net_margin"] = round(net_profit / revenue * 100, 1) if net_profit else 0

        if ratios:
            charts.append(ChartConfig(
                chart_type="gauge",
                title="Key Margins",
                data=ratios,
            ))

        summary = (
            f"Financial statement for {company or 'company'}, period {period}. "
            f"Revenue: {format_currency(revenue)}, gross margin: {gross_margin:.1f}%, "
            f"net profit: {format_currency(net_profit)}. "
            f"{'Revenue grew ' + format_percentage(rev_change) + ' vs prior period. ' if rev_change is not None else ''}"
            f"{'Health: ' + str(health_score) + '.' if health_score else ''}"
        )

        return ObjectView(
            object_id=obj.object_id,
            object_type="FinancialStatement",
            display_name=f"{company} - {period}",
            icon=self.TYPE_ICONS.get("FinancialStatement", "file-text"),
            prominent_properties=prominent,
            properties=all_props,
            linked_objects={},
            charts=charts,
            actions=[
                {"action": "compare_periods", "label": "Compare Periods", "icon": "git-compare"},
                {"action": "generate_pdf", "label": "Generate PDF", "icon": "download"},
                {"action": "run_analysis", "label": "Run Analysis", "icon": "play"},
            ],
            ai_summary=summary,
        )

    def _generate_generic_view(self, obj) -> ObjectView:
        """Fallback view for any unrecognized object type."""
        props = obj.properties
        name = props.get("name") or props.get("label") or props.get("code") or obj.object_id

        prominent = []
        all_props = []
        for key, val in props.items():
            fp = FormattedProperty(key, val, "text")
            if len(prominent) < 4:
                prominent.append(fp)
            else:
                all_props.append(fp)

        linked = {}
        for rel_name, target_ids in obj.relationships.items():
            linked_list = []
            try:
                from app.services.ontology_engine import ontology_registry
                for tid in target_ids[:10]:
                    target = ontology_registry.get_object(tid)
                    if target:
                        linked_list.append(LinkedObject(
                            id=tid, type=target.object_type,
                            display_name=str(target.properties.get("name", tid)),
                        ))
            except Exception:
                linked_list.append(LinkedObject(id=tid, type="unknown", display_name=tid))
            if linked_list:
                linked[rel_name] = linked_list

        summary = f"{obj.object_type} object '{name}' with {len(props)} properties and {sum(len(v) for v in obj.relationships.values())} relationships."

        return ObjectView(
            object_id=obj.object_id,
            object_type=obj.object_type,
            display_name=str(name),
            icon=self.TYPE_ICONS.get(obj.object_type, "box"),
            prominent_properties=prominent,
            properties=all_props,
            linked_objects=linked,
            charts=[],
            actions=[
                {"action": "view_graph", "label": "View Graph", "icon": "share-2"},
            ],
            ai_summary=summary,
        )


# =============================================================================
# SINGLETON
# =============================================================================

object_view_generator = ObjectViewGenerator()
