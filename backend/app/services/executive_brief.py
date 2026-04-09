"""
Phase P-3: One-Page Executive Brief
======================================
Single-page landscape PDF for board meetings / quick decisions.

Layout: 6 sections on one A4 landscape page:
  - Health badge + key metrics
  - Diagnosis summary
  - Top 3 actions
  - CFO verdict
"""

from __future__ import annotations

import io
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.config import settings

logger = logging.getLogger(__name__)

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib.enums import TA_CENTER
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable,
    )
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

_NAVY = colors.HexColor("#1B2A4A") if REPORTLAB_AVAILABLE else None
_GOLD = colors.HexColor("#C4A35A") if REPORTLAB_AVAILABLE else None
_WHITE = colors.white if REPORTLAB_AVAILABLE else None
_LIGHT = colors.HexColor("#F5F5F5") if REPORTLAB_AVAILABLE else None
_GRAY = colors.HexColor("#888888") if REPORTLAB_AVAILABLE else None


def _fmt(value, suffix=""):
    """Format value safely."""
    if value is None:
        return "N/A"
    try:
        v = float(value)
        if abs(v) >= 1_000_000:
            return f"{v/1_000_000:.1f}M{suffix}"
        elif abs(v) >= 1_000:
            return f"{v/1_000:.0f}K{suffix}"
        return f"{v:,.1f}{suffix}"
    except (ValueError, TypeError):
        return str(value)


class ExecutiveBriefGenerator:
    """Generates a single-page executive brief PDF."""

    def generate(
        self,
        result_dict: Dict[str, Any],
        company_name: str = None,
        period: str = "FY 2025",
        orientation: str = "landscape",
    ) -> bytes:
        """
        Generate one-page brief.

        Args:
            result_dict: OrchestratorResult.to_dict()
            orientation: "landscape" or "portrait"

        Returns:
            PDF bytes
        """
        company_name = company_name or settings.COMPANY_NAME
        if not REPORTLAB_AVAILABLE:
            raise RuntimeError("reportlab required")

        buf = io.BytesIO()
        page_size = landscape(A4) if orientation == "landscape" else A4
        doc = SimpleDocTemplate(
            buf, pagesize=page_size,
            topMargin=10*mm, bottomMargin=10*mm,
            leftMargin=10*mm, rightMargin=10*mm,
        )

        styles = getSampleStyleSheet()
        gen_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        exec_summary = result_dict.get("executive_summary", {})
        diagnosis = result_dict.get("diagnosis", {})
        decision = result_dict.get("decision", {})
        strategy = result_dict.get("strategy", {})

        elements = []

        # Header row
        header_data = [[
            Paragraph(f"<b>{company_name}</b>", ParagraphStyle(
                'H', fontSize=12, textColor=_NAVY)),
            Paragraph("Financial Health Brief", ParagraphStyle(
                'H2', fontSize=12, textColor=_GOLD, alignment=TA_CENTER)),
            Paragraph(f"{period} | {gen_date}", ParagraphStyle(
                'H3', fontSize=10, textColor=_GRAY, alignment=1)),  # RIGHT
        ]]
        ht = Table(header_data, colWidths=[100*mm, 80*mm, 80*mm] if orientation == "landscape"
                   else [70*mm, 50*mm, 60*mm])
        ht.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        elements.append(ht)
        elements.append(HRFlowable(width="100%", color=_GOLD, thickness=1))
        elements.append(Spacer(1, 3*mm))

        # Key metrics row (4 boxes)
        grade = exec_summary.get("health_grade", "?")
        score = exec_summary.get("health_score", 0)
        diag_data = diagnosis.get("financial_data", {})

        metrics_data = [[
            Paragraph(f"<b>HEALTH</b><br/>{grade} ({score:.0f}/100)", ParagraphStyle(
                'M', fontSize=11, textColor=_NAVY, alignment=TA_CENTER)),
            Paragraph(f"<b>REVENUE</b><br/>{_fmt(diag_data.get('revenue'), ' GEL')}", ParagraphStyle(
                'M', fontSize=11, textColor=_NAVY, alignment=TA_CENTER)),
            Paragraph(f"<b>NET MARGIN</b><br/>{_fmt(diag_data.get('net_margin_pct'), '%')}", ParagraphStyle(
                'M', fontSize=11, textColor=_NAVY, alignment=TA_CENTER)),
            Paragraph(f"<b>CASH RUNWAY</b><br/>{exec_summary.get('cash_runway_months', 0):.0f} months", ParagraphStyle(
                'M', fontSize=11, textColor=_NAVY, alignment=TA_CENTER)),
        ]]

        box_w = 65*mm if orientation == "landscape" else 42*mm
        mt = Table(metrics_data, colWidths=[box_w]*4)
        mt.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 1, _NAVY),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, _GRAY),
            ('BACKGROUND', (0, 0), (-1, -1), _LIGHT),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(mt)
        elements.append(Spacer(1, 4*mm))

        # Strategic Risk Context Row (New)
        proactive = result_dict.get("proactive_analysis", {})
        strat = proactive.get("strategic_exposure", {})
        strat_status = strat.get("status", "healthy").upper()
        strat_color = _GOLD if strat_status == "HEALTHY" else colors.red if strat_status == "CRITICAL" else colors.orange
        
        strat_data = [[
            Paragraph(f"<b>INFRASTRUCTURE HEALTH</b><br/><font color='{strat_color}'>{strat_status}</font>", ParagraphStyle('S', fontSize=9, textColor=_NAVY, alignment=TA_CENTER)),
            Paragraph(f"<b>DAILY CORRIDOR EXPOSURE</b><br/>₾{strat.get('financial_exposure_gel', 0)/1000:.1f}K", ParagraphStyle('S', fontSize=9, textColor=_NAVY, alignment=TA_CENTER)),
            Paragraph(f"<b>MARKET SENTIMENT</b><br/>{strat.get('market_sentiment', 'Neutral').upper()}", ParagraphStyle('S', fontSize=9, textColor=_NAVY, alignment=TA_CENTER)),
            Paragraph(f"<b>AFFECTED ROUTES</b><br/>{', '.join(strat.get('affected_routes', ['None']))}", ParagraphStyle('S', fontSize=8, textColor=_NAVY, alignment=TA_CENTER)),
        ]]
        st = Table(strat_data, colWidths=[box_w]*4)
        st.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 0.5, _GOLD),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
        ]))
        elements.append(st)
        elements.append(Spacer(1, 4*mm))

        # Two-column: Diagnosis + Strategy
        body_style = ParagraphStyle('B', fontSize=9, textColor=colors.black, spaceAfter=2)
        bold_style = ParagraphStyle('BB', fontSize=10, textColor=_NAVY, fontName='Helvetica-Bold')

        # Left column: Key metrics + diagnosis
        left_items = []
        left_items.append(Paragraph("<b>KEY METRICS</b>", bold_style))
        for label, key in [("Gross Margin", "gross_margin_pct"),
                            ("EBITDA Margin", "ebitda_margin_pct"),
                            ("COGS/Revenue", "cogs_to_revenue_pct")]:
            val = diag_data.get(key)
            left_items.append(Paragraph(f"- {label}: {_fmt(val, '%')}", body_style))

        # Right column: Strategy + top actions
        right_items = []
        strategy_name = strategy.get("name", exec_summary.get("strategy_name", "N/A"))
        right_items.append(Paragraph(f"<b>STRATEGY: {strategy_name}</b>", bold_style))

        # Top 3 actions from verdict
        verdict = decision.get("cfo_verdict", {})
        justification = verdict.get("justification", [])[:3]
        if not justification:
            recs = diagnosis.get("recommendations", [])[:3]
            justification = [r.get("action", "") for r in recs]

        for i, action in enumerate(justification, 1):
            text = str(action)[:80]
            right_items.append(Paragraph(f"{i}. {text}", body_style))

        # Build two-column table
        left_para = "<br/>".join([str(p) for p in [""] * len(left_items)])
        body_data = [[left_items, right_items]]
        col_w = 128*mm if orientation == "landscape" else 85*mm

        # We need to flatten — use nested tables
        left_table = Table([[p] for p in left_items])
        right_table = Table([[p] for p in right_items])

        body_table = Table([[left_table, right_table]], colWidths=[col_w, col_w])
        body_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        elements.append(body_table)
        elements.append(Spacer(1, 3*mm))

        # CFO Verdict footer
        conv_grade = verdict.get("conviction_grade", exec_summary.get("conviction_grade", "?"))
        elements.append(HRFlowable(width="100%", color=_GOLD, thickness=1))
        elements.append(Paragraph(
            f"<b>CFO VERDICT: {conv_grade}</b> | "
            f"Strategy: {strategy_name} | "
            f"Alerts: {exec_summary.get('active_alerts', 0)} | "
            f"System: {exec_summary.get('system_health', 'unknown')}",
            ParagraphStyle('Footer', fontSize=10, textColor=_NAVY, alignment=TA_CENTER),
        ))

        doc.build(elements)
        return buf.getvalue()


# Module-level singleton
executive_brief = ExecutiveBriefGenerator()
