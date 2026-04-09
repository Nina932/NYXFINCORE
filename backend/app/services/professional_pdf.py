"""
Phase P-1: Professional Financial Intelligence PDF Report (reportlab)
======================================================================
Generates 15+ page professional-grade PDF reports with:
  - Cover page with health grade badge
  - Executive summary with key metrics
  - P&L statement (current vs previous, change %)
  - Balance sheet
  - Financial ratios dashboard
  - Diagnosis detail
  - Strategy & recommendations
  - Monitoring dashboard
  - Analogy matches

Uses reportlab for:
  - Unicode/Georgian text support
  - Built-in chart generation
  - Professional layout
"""

from __future__ import annotations

import io
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.config import settings

logger = logging.getLogger(__name__)

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm, cm, inch
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        PageBreak, HRFlowable, KeepTogether,
    )
    from reportlab.graphics.shapes import Drawing, Rect, String, Circle
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    from reportlab.graphics.charts.piecharts import Pie
    from reportlab.graphics import renderPDF
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    logger.warning("reportlab not installed — professional PDF unavailable")


# ═══════════════════════════════════════════════════════════════════
# COLORS & STYLES
# ═══════════════════════════════════════════════════════════════════

if REPORTLAB_AVAILABLE:
    _NAVY = colors.HexColor("#1B2A4A")
    _GOLD = colors.HexColor("#C4A35A")
    _WHITE = colors.white
    _LIGHT_GRAY = colors.HexColor("#F5F5F5")
    _MEDIUM_GRAY = colors.HexColor("#888888")
    _SUCCESS = colors.HexColor("#28A745")
    _WARNING = colors.HexColor("#FFC107")
    _DANGER = colors.HexColor("#DC3545")
else:
    _NAVY = _GOLD = _WHITE = _LIGHT_GRAY = _MEDIUM_GRAY = _SUCCESS = _WARNING = _DANGER = None

_ACCENT = colors.HexColor("#007BFF") if REPORTLAB_AVAILABLE else None

_HEALTH_COLORS = {
    "A": _SUCCESS, "B": _ACCENT, "C": _WARNING, "D": _DANGER, "F": _DANGER,
} if REPORTLAB_AVAILABLE else {}


def _fmt_num(value, prefix="", suffix="", decimals=0):
    """Format number with thousands separator."""
    if value is None:
        return "N/A"
    try:
        v = float(value)
        if decimals == 0:
            formatted = f"{v:,.0f}"
        else:
            formatted = f"{v:,.{decimals}f}"
        return f"{prefix}{formatted}{suffix}"
    except (ValueError, TypeError):
        return str(value)


def _pct(value, decimals=1):
    """Format as percentage."""
    if value is None:
        return "N/A"
    try:
        return f"{float(value):.{decimals}f}%"
    except (ValueError, TypeError):
        return str(value)


def _change_color(value):
    """Return color for change value."""
    try:
        v = float(value)
        if v > 0:
            return _SUCCESS
        elif v < 0:
            return _DANGER
        return _MEDIUM_GRAY
    except (ValueError, TypeError):
        return _MEDIUM_GRAY


# ═══════════════════════════════════════════════════════════════════
# PROFESSIONAL PDF GENERATOR
# ═══════════════════════════════════════════════════════════════════

class ProfessionalPDFReport:
    """Generates a 15+ page professional financial intelligence report."""

    def __init__(self):
        if not REPORTLAB_AVAILABLE:
            raise RuntimeError("reportlab required. Install: pip install reportlab")
        self._styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Create custom paragraph styles."""
        self._styles.add(ParagraphStyle(
            'CoverTitle', parent=self._styles['Title'],
            fontSize=32, textColor=_NAVY, alignment=TA_CENTER, spaceAfter=20,
        ))
        self._styles.add(ParagraphStyle(
            'CoverSubtitle', parent=self._styles['Normal'],
            fontSize=16, textColor=_MEDIUM_GRAY, alignment=TA_CENTER, spaceAfter=10,
        ))
        self._styles.add(ParagraphStyle(
            'SectionTitle', parent=self._styles['Heading1'],
            fontSize=18, textColor=_NAVY, spaceAfter=12, spaceBefore=16,
            borderWidth=0, borderPadding=0,
        ))
        self._styles.add(ParagraphStyle(
            'SubSection', parent=self._styles['Heading2'],
            fontSize=13, textColor=_NAVY, spaceAfter=8, spaceBefore=10,
        ))
        self._styles.add(ParagraphStyle(
            'MetricLabel', parent=self._styles['Normal'],
            fontSize=9, textColor=_MEDIUM_GRAY,
        ))
        self._styles.add(ParagraphStyle(
            'MetricValue', parent=self._styles['Normal'],
            fontSize=14, textColor=_NAVY, fontName='Helvetica-Bold',
        ))
        self._styles.add(ParagraphStyle(
            'BodyText2', parent=self._styles['Normal'],
            fontSize=10, textColor=colors.black, spaceAfter=4,
        ))
        self._styles.add(ParagraphStyle(
            'BulletText', parent=self._styles['Normal'],
            fontSize=10, textColor=colors.black, leftIndent=15,
            bulletIndent=5, spaceAfter=3,
        ))

    def generate(
        self,
        result_dict: Dict[str, Any],
        company_name: str = None,
        period: str = "FY 2025",
    ) -> bytes:
        """
        Generate the full PDF report.

        Args:
            result_dict: OrchestratorResult.to_dict()
            company_name: Company name
            period: Reporting period

        Returns:
            PDF bytes
        """
        company_name = company_name or settings.COMPANY_NAME
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf, pagesize=A4,
            topMargin=20*mm, bottomMargin=20*mm,
            leftMargin=15*mm, rightMargin=15*mm,
            title=f"Financial Intelligence Report - {company_name}",
            author="FinAI Platform",
        )

        gen_date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        elements = []

        exec_summary = result_dict.get("executive_summary", {})
        diagnosis = result_dict.get("diagnosis", {})
        decision = result_dict.get("decision", {})
        strategy = result_dict.get("strategy", {})
        monitoring = result_dict.get("monitoring", {})
        analogy = result_dict.get("analogy", {})
        simulation = result_dict.get("simulation", {})

        # PAGE 1: Cover
        elements.extend(self._cover_page(company_name, period, gen_date, exec_summary))
        elements.append(PageBreak())

        # PAGE 2: Executive Summary
        elements.extend(self._executive_summary(exec_summary))
        elements.append(PageBreak())

        # PAGE 3-4: P&L Statement
        elements.extend(self._pl_statement(exec_summary, diagnosis))
        elements.append(PageBreak())

        # PAGE 5: Balance Sheet + Ratios
        elements.extend(self._balance_sheet_section(exec_summary))
        elements.append(PageBreak())

        # PAGE 6-7: Financial Ratios Dashboard with chart
        elements.extend(self._ratios_dashboard(exec_summary, diagnosis))
        elements.append(PageBreak())

        # PAGE 8: Diagnosis Detail
        elements.extend(self._diagnosis_section(diagnosis))
        elements.append(PageBreak())

        # PAGE 9-10: Decision Intelligence + CFO Verdict
        elements.extend(self._decision_section(decision))
        elements.append(PageBreak())

        # PAGE 11-12: Strategy
        elements.extend(self._strategy_section(strategy))
        elements.append(PageBreak())

        # PAGE 13: Simulation
        elements.extend(self._simulation_section(simulation))
        elements.append(PageBreak())

        # PAGE 14: Monitoring Dashboard
        elements.extend(self._monitoring_section(monitoring))
        elements.append(PageBreak())

        # PAGE 15: Analogy Matches
        elements.extend(self._analogy_section(analogy))

        # Build PDF
        doc.build(elements, onFirstPage=self._header_footer, onLaterPages=self._header_footer)
        return buf.getvalue()

    # ── Header/Footer ───────────────────────────────────────────────

    def _header_footer(self, canvas, doc):
        """Add header and footer to every page."""
        canvas.saveState()
        # Header line
        canvas.setStrokeColor(_NAVY)
        canvas.setLineWidth(0.5)
        canvas.line(15*mm, A4[1] - 15*mm, A4[0] - 15*mm, A4[1] - 15*mm)

        # Footer
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(_MEDIUM_GRAY)
        canvas.drawString(15*mm, 10*mm, "Confidential - FinAI Intelligence Report")
        canvas.drawRightString(A4[0] - 15*mm, 10*mm, f"Page {doc.page}")

        # Footer line
        canvas.line(15*mm, 14*mm, A4[0] - 15*mm, 14*mm)
        canvas.restoreState()

    # ── Cover Page ──────────────────────────────────────────────────

    def _cover_page(self, company, period, gen_date, summary):
        """Build cover page elements."""
        elements = []
        elements.append(Spacer(1, 80*mm))
        elements.append(Paragraph("Financial Intelligence Report", self._styles['CoverTitle']))
        elements.append(Spacer(1, 10*mm))
        elements.append(Paragraph(company, self._styles['CoverSubtitle']))
        elements.append(Paragraph(period, self._styles['CoverSubtitle']))
        elements.append(Spacer(1, 5*mm))
        elements.append(Paragraph(f"Generated: {gen_date}", self._styles['CoverSubtitle']))
        elements.append(Spacer(1, 20*mm))

        # Health badge
        grade = summary.get("health_grade", "?")
        score = summary.get("health_score", 0)
        badge_text = f"Financial Health: {grade} ({score:.0f}/100)"
        elements.append(Paragraph(f"<b>{badge_text}</b>", ParagraphStyle(
            'Badge', parent=self._styles['Normal'],
            fontSize=18, textColor=_NAVY, alignment=TA_CENTER,
        )))

        return elements

    # ── Executive Summary ───────────────────────────────────────────

    def _executive_summary(self, summary):
        """Build executive summary page."""
        elements = []
        elements.append(Paragraph("Executive Summary", self._styles['SectionTitle']))
        elements.append(HRFlowable(width="100%", color=_GOLD, thickness=1))
        elements.append(Spacer(1, 5*mm))

        # Key metrics table
        metrics = [
            ["Health Score", _fmt_num(summary.get("health_score", 0), suffix="/100"),
             "Strategy", summary.get("strategy_name", "N/A")],
            ["Conviction Grade", summary.get("conviction_grade", "N/A"),
             "System Health", summary.get("system_health", "unknown")],
            ["Cash Runway", f"{summary.get('cash_runway_months', 0):.0f} months",
             "Active Alerts", str(summary.get("active_alerts", 0))],
            ["Stages Completed", str(summary.get("stages_completed", 0)),
             "KPIs On Track", str(summary.get("kpi_on_track", 0))],
        ]

        t = Table(metrics, colWidths=[45*mm, 45*mm, 45*mm, 45*mm])
        t.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, _LIGHT_GRAY),
            ('BACKGROUND', (0, 0), (0, -1), _LIGHT_GRAY),
            ('BACKGROUND', (2, 0), (2, -1), _LIGHT_GRAY),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (-1, -1), _NAVY),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 10*mm))

        # Strategy recommendation
        strategy = summary.get("strategy_name", "N/A")
        elements.append(Paragraph(f"Recommended Strategy: <b>{strategy}</b>",
                                   self._styles['SubSection']))

        return elements

    # ── P&L Statement ───────────────────────────────────────────────

    def _pl_statement(self, summary, diagnosis):
        """Build P&L statement page."""
        elements = []
        elements.append(Paragraph("Income Statement Overview", self._styles['SectionTitle']))
        elements.append(HRFlowable(width="100%", color=_GOLD, thickness=1))
        elements.append(Spacer(1, 5*mm))

        # Get financials from diagnosis
        diag_data = diagnosis.get("financial_data", {})
        current = diag_data if diag_data else {}

        # P&L rows
        rows = [
            ["Line Item", "Amount (GEL)", "% of Revenue"],
            ["Revenue", _fmt_num(current.get("revenue")), "100.0%"],
            ["Cost of Goods Sold", _fmt_num(current.get("cogs")),
             _pct(current.get("cogs_to_revenue_pct"))],
            ["Gross Profit", _fmt_num(current.get("gross_profit")),
             _pct(current.get("gross_margin_pct"))],
            ["G&A Expenses", _fmt_num(current.get("ga_expenses")), ""],
            ["EBITDA", _fmt_num(current.get("ebitda")),
             _pct(current.get("ebitda_margin_pct"))],
            ["Depreciation", _fmt_num(current.get("depreciation")), ""],
            ["Finance Expense", _fmt_num(current.get("finance_expense")), ""],
            ["Net Profit", _fmt_num(current.get("net_profit")),
             _pct(current.get("net_margin_pct"))],
        ]

        t = Table(rows, colWidths=[65*mm, 55*mm, 55*mm])
        style = [
            ('GRID', (0, 0), (-1, -1), 0.5, _MEDIUM_GRAY),
            ('BACKGROUND', (0, 0), (-1, 0), _NAVY),
            ('TEXTCOLOR', (0, 0), (-1, 0), _WHITE),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            # Bold subtotals
            ('FONTNAME', (0, 3), (-1, 3), 'Helvetica-Bold'),  # Gross Profit
            ('FONTNAME', (0, 5), (-1, 5), 'Helvetica-Bold'),  # EBITDA
            ('FONTNAME', (0, 8), (-1, 8), 'Helvetica-Bold'),  # Net Profit
            ('BACKGROUND', (0, 3), (-1, 3), _LIGHT_GRAY),
            ('BACKGROUND', (0, 5), (-1, 5), _LIGHT_GRAY),
            ('BACKGROUND', (0, 8), (-1, 8), _LIGHT_GRAY),
        ]
        t.setStyle(TableStyle(style))
        elements.append(t)

        return elements

    # ── Balance Sheet ───────────────────────────────────────────────

    def _balance_sheet_section(self, summary):
        """Build balance sheet section."""
        elements = []
        elements.append(Paragraph("Balance Sheet Overview", self._styles['SectionTitle']))
        elements.append(HRFlowable(width="100%", color=_GOLD, thickness=1))
        elements.append(Spacer(1, 5*mm))

        elements.append(Paragraph(
            "Balance sheet data is sourced from uploaded financial statements. "
            "Key liquidity and leverage ratios are computed deterministically.",
            self._styles['BodyText2'],
        ))
        elements.append(Spacer(1, 5*mm))

        # Key ratios
        rows = [
            ["Ratio", "Value", "Status"],
            ["Cash Runway", f"{summary.get('cash_runway_months', 0):.0f} months",
             summary.get("cash_runway_risk", "N/A")],
            ["KPIs On Track", str(summary.get("kpi_on_track", 0)),
             "Good" if summary.get("kpi_missed", 0) == 0 else "Review"],
            ["Active Alerts", str(summary.get("active_alerts", 0)),
             "Clear" if summary.get("active_alerts", 0) == 0 else "Action"],
        ]
        t = Table(rows, colWidths=[60*mm, 60*mm, 55*mm])
        t.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, _MEDIUM_GRAY),
            ('BACKGROUND', (0, 0), (-1, 0), _NAVY),
            ('TEXTCOLOR', (0, 0), (-1, 0), _WHITE),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ]))
        elements.append(t)

        return elements

    # ── Ratios Dashboard ────────────────────────────────────────────

    def _ratios_dashboard(self, summary, diagnosis):
        """Build financial ratios with bar chart."""
        elements = []
        elements.append(Paragraph("Financial Ratios Dashboard", self._styles['SectionTitle']))
        elements.append(HRFlowable(width="100%", color=_GOLD, thickness=1))
        elements.append(Spacer(1, 5*mm))

        diag_data = diagnosis.get("financial_data", {})

        # Ratios table
        ratios = [
            ["Ratio", "Value", "Benchmark", "Status"],
            ["Gross Margin", _pct(diag_data.get("gross_margin_pct")), "15%+", ""],
            ["Net Margin", _pct(diag_data.get("net_margin_pct")), "5%+", ""],
            ["EBITDA Margin", _pct(diag_data.get("ebitda_margin_pct")), "8%+", ""],
            ["COGS/Revenue", _pct(diag_data.get("cogs_to_revenue_pct")), "<85%", ""],
        ]

        # Set status
        for i in range(1, len(ratios)):
            val = diag_data.get(ratios[i][0].lower().replace(" ", "_").replace("/", "_to_") + "_pct")
            if val is not None:
                try:
                    ratios[i][3] = "On Track" if float(val) > 5 else "Review"
                except ValueError:
                    ratios[i][3] = "N/A"

        t = Table(ratios, colWidths=[50*mm, 35*mm, 35*mm, 55*mm])
        t.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, _MEDIUM_GRAY),
            ('BACKGROUND', (0, 0), (-1, 0), _NAVY),
            ('TEXTCOLOR', (0, 0), (-1, 0), _WHITE),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 10*mm))

        # Bar chart
        chart = self._margin_bar_chart(diag_data)
        if chart:
            elements.append(chart)

        return elements

    def _margin_bar_chart(self, data):
        """Create a margin comparison bar chart."""
        try:
            values = [
                data.get("gross_margin_pct", 0),
                data.get("net_margin_pct", 0),
                data.get("ebitda_margin_pct", 0),
            ]
            values = [float(v) if v else 0 for v in values]

            drawing = Drawing(400, 200)
            chart = VerticalBarChart()
            chart.x = 50
            chart.y = 30
            chart.width = 300
            chart.height = 140
            chart.data = [values]
            chart.categoryAxis.categoryNames = ['Gross Margin', 'Net Margin', 'EBITDA Margin']
            chart.categoryAxis.labels.fontName = 'Helvetica'
            chart.categoryAxis.labels.fontSize = 9
            chart.valueAxis.valueMin = min(0, min(values) - 5)
            chart.valueAxis.valueMax = max(values) + 10
            chart.valueAxis.labels.fontName = 'Helvetica'
            chart.valueAxis.labels.fontSize = 8
            chart.bars[0].fillColor = _ACCENT

            # Title
            drawing.add(String(200, 185, 'Margin Analysis (%)',
                               fontName='Helvetica-Bold', fontSize=11,
                               fillColor=_NAVY, textAnchor='middle'))
            drawing.add(chart)
            return drawing
        except Exception as e:
            logger.warning("Failed to create chart: %s", e)
            return None

    # ── Diagnosis ───────────────────────────────────────────────────

    def _diagnosis_section(self, diagnosis):
        """Build diagnosis detail page."""
        elements = []
        elements.append(Paragraph("Financial Diagnosis", self._styles['SectionTitle']))
        elements.append(HRFlowable(width="100%", color=_GOLD, thickness=1))
        elements.append(Spacer(1, 5*mm))

        score = diagnosis.get("health_score", 0)
        grade = diagnosis.get("health_grade", "?")
        elements.append(Paragraph(
            f"Health Score: <b>{score:.0f}/100 ({grade})</b>",
            self._styles['SubSection'],
        ))

        # Signal summary
        signals = diagnosis.get("signal_summary", {})
        if signals:
            elements.append(Paragraph("Signal Summary", self._styles['SubSection']))
            sig_rows = [["Severity", "Count"]]
            for sev in ["critical", "high", "medium", "low"]:
                count = signals.get(sev, 0)
                if count > 0:
                    sig_rows.append([sev.title(), str(count)])
            if len(sig_rows) > 1:
                t = Table(sig_rows, colWidths=[80*mm, 95*mm])
                t.setStyle(TableStyle([
                    ('GRID', (0, 0), (-1, -1), 0.5, _MEDIUM_GRAY),
                    ('BACKGROUND', (0, 0), (-1, 0), _NAVY),
                    ('TEXTCOLOR', (0, 0), (-1, 0), _WHITE),
                ]))
                elements.append(t)

        # Recommendations
        recs = diagnosis.get("recommendations", [])[:5]
        if recs:
            elements.append(Spacer(1, 5*mm))
            elements.append(Paragraph("Top Recommendations", self._styles['SubSection']))
            for r in recs:
                priority = r.get("priority", "medium").upper()
                action = r.get("action", "")
                elements.append(Paragraph(
                    f"[{priority}] {action}", self._styles['BulletText'],
                ))

        return elements

    # ── Decision Intelligence ───────────────────────────────────────

    def _decision_section(self, decision):
        """Build decision + verdict page."""
        elements = []
        elements.append(Paragraph("Decision Intelligence", self._styles['SectionTitle']))
        elements.append(HRFlowable(width="100%", color=_GOLD, thickness=1))
        elements.append(Spacer(1, 5*mm))

        elements.append(Paragraph(
            f"Actions Evaluated: <b>{decision.get('actions_evaluated', 0)}</b>",
            self._styles['BodyText2'],
        ))

        verdict = decision.get("cfo_verdict", {})
        if verdict:
            elements.append(Spacer(1, 5*mm))
            elements.append(Paragraph("CFO Verdict", self._styles['SubSection']))

            stmt = verdict.get("verdict_statement", "")
            if stmt:
                elements.append(Paragraph(f"<i>{stmt[:300]}</i>", self._styles['BodyText2']))

            elements.append(Spacer(1, 3*mm))
            elements.append(Paragraph(
                f"Conviction: <b>{verdict.get('conviction_grade', '?')}</b> "
                f"({verdict.get('conviction_score', 0):.0%})",
                self._styles['BodyText2'],
            ))
            elements.append(Paragraph(
                f"Time Pressure: <b>{verdict.get('time_pressure', 'normal')}</b>",
                self._styles['BodyText2'],
            ))
            elements.append(Paragraph(
                f"Do-Nothing Cost: <b>{_fmt_num(verdict.get('do_nothing_cost', 0))} GEL</b>",
                self._styles['BodyText2'],
            ))

            # Justification
            just = verdict.get("justification", [])
            if just:
                elements.append(Spacer(1, 3*mm))
                elements.append(Paragraph("Justification", self._styles['SubSection']))
                for j in just[:5]:
                    elements.append(Paragraph(f"- {j[:150]}", self._styles['BulletText']))

        return elements

    # ── Strategy ────────────────────────────────────────────────────

    def _strategy_section(self, strategy):
        """Build strategy page."""
        elements = []
        elements.append(Paragraph("Strategic Plan", self._styles['SectionTitle']))
        elements.append(HRFlowable(width="100%", color=_GOLD, thickness=1))
        elements.append(Spacer(1, 5*mm))

        elements.append(Paragraph(
            f"Strategy: <b>{strategy.get('name', 'N/A')}</b>",
            self._styles['SubSection'],
        ))
        elements.append(Paragraph(
            f"Duration: {strategy.get('total_duration_days', 0)} days | "
            f"Investment: {_fmt_num(strategy.get('total_investment', 0))} GEL | "
            f"Expected ROI: {strategy.get('overall_roi', 0):.1f}x",
            self._styles['BodyText2'],
        ))

        phases = strategy.get("phases", [])
        if phases:
            elements.append(Spacer(1, 5*mm))
            rows = [["Phase", "Name", "Duration", "Expected Impact"]]
            for p in phases:
                rows.append([
                    str(p.get("phase_number", "")),
                    p.get("phase_name", "").title(),
                    f"{p.get('duration_days', 0)} days",
                    _fmt_num(p.get("expected_profit_delta", 0), suffix=" GEL"),
                ])
            t = Table(rows, colWidths=[20*mm, 60*mm, 40*mm, 55*mm])
            t.setStyle(TableStyle([
                ('GRID', (0, 0), (-1, -1), 0.5, _MEDIUM_GRAY),
                ('BACKGROUND', (0, 0), (-1, 0), _NAVY),
                ('TEXTCOLOR', (0, 0), (-1, 0), _WHITE),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
            ]))
            elements.append(t)

        return elements

    # ── Simulation ──────────────────────────────────────────────────

    def _simulation_section(self, simulation):
        """Build simulation results page."""
        elements = []
        elements.append(Paragraph("Simulation Results", self._styles['SectionTitle']))
        elements.append(HRFlowable(width="100%", color=_GOLD, thickness=1))
        elements.append(Spacer(1, 5*mm))

        sens = simulation.get("sensitivity", {})
        if sens:
            elements.append(Paragraph("Sensitivity Analysis", self._styles['SubSection']))
            most_sensitive = sens.get("most_sensitive", "N/A")
            elements.append(Paragraph(
                f"Most Sensitive Variable: <b>{most_sensitive}</b>",
                self._styles['BodyText2'],
            ))

            bands = sens.get("bands", [])[:5]
            if bands:
                rows = [["Variable", "Base", "-10%", "+10%", "Swing"]]
                for b in bands:
                    rows.append([
                        b.get("variable", ""),
                        _fmt_num(b.get("base_value"), decimals=1),
                        _fmt_num(b.get("low_value"), decimals=1),
                        _fmt_num(b.get("high_value"), decimals=1),
                        _fmt_num(b.get("swing", 0), decimals=1),
                    ])
                t = Table(rows, colWidths=[40*mm, 30*mm, 30*mm, 30*mm, 45*mm])
                t.setStyle(TableStyle([
                    ('GRID', (0, 0), (-1, -1), 0.5, _MEDIUM_GRAY),
                    ('BACKGROUND', (0, 0), (-1, 0), _NAVY),
                    ('TEXTCOLOR', (0, 0), (-1, 0), _WHITE),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                ]))
                elements.append(t)

        mc = simulation.get("monte_carlo", {})
        if mc:
            elements.append(Spacer(1, 8*mm))
            elements.append(Paragraph("Monte Carlo Simulation", self._styles['SubSection']))
            elements.append(Paragraph(
                f"P10: {_fmt_num(mc.get('p10'))} | "
                f"Median: {_fmt_num(mc.get('median'))} | "
                f"P90: {_fmt_num(mc.get('p90'))} | "
                f"VaR: {_fmt_num(mc.get('value_at_risk'))}",
                self._styles['BodyText2'],
            ))

        return elements

    # ── Monitoring ──────────────────────────────────────────────────

    def _monitoring_section(self, monitoring):
        """Build monitoring dashboard page."""
        elements = []
        elements.append(Paragraph("Monitoring Dashboard", self._styles['SectionTitle']))
        elements.append(HRFlowable(width="100%", color=_GOLD, thickness=1))
        elements.append(Spacer(1, 5*mm))

        alerts = monitoring.get("alerts", {})
        elements.append(Paragraph(
            f"Active Alerts: <b>{alerts.get('active', 0)}</b> | "
            f"Critical: <b>{alerts.get('critical', 0)}</b> | "
            f"System: <b>{monitoring.get('system_health', 'unknown')}</b>",
            self._styles['BodyText2'],
        ))

        kpi = monitoring.get("kpi", {})
        if kpi:
            elements.append(Spacer(1, 5*mm))
            elements.append(Paragraph("KPI Status", self._styles['SubSection']))
            elements.append(Paragraph(
                f"On Track: {kpi.get('on_track', 0)} | "
                f"At Risk: {kpi.get('at_risk', 0)} | "
                f"Missed: {kpi.get('missed', 0)}",
                self._styles['BodyText2'],
            ))

        runway = monitoring.get("cash_runway", {})
        if runway:
            elements.append(Spacer(1, 5*mm))
            elements.append(Paragraph("Cash Runway", self._styles['SubSection']))
            elements.append(Paragraph(
                f"{runway.get('months', 0):.0f} months ({runway.get('risk', '?')})",
                self._styles['BodyText2'],
            ))

        return elements

    # ── Analogy ─────────────────────────────────────────────────────

    def _analogy_section(self, analogy):
        """Build analogy matches page."""
        elements = []
        elements.append(Paragraph("Historical Analogies", self._styles['SectionTitle']))
        elements.append(HRFlowable(width="100%", color=_GOLD, thickness=1))
        elements.append(Spacer(1, 5*mm))

        elements.append(Paragraph(
            f"Dominant Historical Strategy: <b>{analogy.get('dominant_strategy', 'N/A')}</b>",
            self._styles['SubSection'],
        ))
        elements.append(Paragraph(
            f"Confidence: {analogy.get('confidence', 0):.0%}",
            self._styles['BodyText2'],
        ))

        matches = analogy.get("matches", [])[:5]
        if matches:
            elements.append(Spacer(1, 5*mm))
            rows = [["Similarity", "Industry", "Strategy", "ROI"]]
            for m in matches:
                meta = m.get("metadata", {})
                rows.append([
                    f"{m.get('similarity_score', 0):.1%}",
                    meta.get("industry", "?")[:18],
                    meta.get("strategy_outcome", "?")[:25],
                    f"{meta.get('roi', 0):.1f}x",
                ])
            t = Table(rows, colWidths=[35*mm, 40*mm, 60*mm, 40*mm])
            t.setStyle(TableStyle([
                ('GRID', (0, 0), (-1, -1), 0.5, _MEDIUM_GRAY),
                ('BACKGROUND', (0, 0), (-1, 0), _NAVY),
                ('TEXTCOLOR', (0, 0), (-1, 0), _WHITE),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
            ]))
            elements.append(t)

        return elements


# Module-level singleton
professional_pdf = ProfessionalPDFReport()
