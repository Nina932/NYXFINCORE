"""
Phase M: PDF Report Generator
===============================
Generates professional-grade financial PDF reports from Orchestrator output.

Uses fpdf2 (FPDF) — lightweight, no external dependencies, production-grade.

Reports include:
    - Executive Summary (health score, verdict, strategy)
    - P&L Overview (revenue, margins, net profit)
    - CFO Verdict with justification
    - Strategy phases with timeline
    - Monitoring alerts and KPI status
    - Sensitivity analysis summary
    - Analogy matches

All data comes from OrchestratorResult — no LLM calls in this module.
"""

import io
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.config import settings

logger = logging.getLogger(__name__)

try:
    from fpdf import FPDF
    FPDF_AVAILABLE = True
except ImportError:
    FPDF_AVAILABLE = False
    logger.warning("fpdf2 not installed — PDF generation unavailable")


# ═══════════════════════════════════════════════════════════════════
# COLOR PALETTE
# ═══════════════════════════════════════════════════════════════════

_COLORS = {
    "primary": (33, 37, 41),       # dark gray
    "secondary": (108, 117, 125),  # medium gray
    "accent": (0, 123, 255),       # blue
    "success": (40, 167, 69),      # green
    "warning": (255, 193, 7),      # yellow
    "danger": (220, 53, 69),       # red
    "light": (248, 249, 250),      # light gray bg
    "white": (255, 255, 255),
    "black": (0, 0, 0),
}

_HEALTH_COLORS = {
    "A": _COLORS["success"],
    "B": _COLORS["accent"],
    "C": _COLORS["warning"],
    "D": _COLORS["danger"],
    "F": _COLORS["danger"],
}


# ═══════════════════════════════════════════════════════════════════
# PDF BUILDER
# ═══════════════════════════════════════════════════════════════════

def _sanitize(text: str) -> str:
    """Sanitize text for Helvetica (Latin-1 only). Replace unsupported chars."""
    if not text:
        return ""
    # Replace common unicode with ASCII equivalents
    replacements = {
        '\u2014': '--', '\u2013': '-', '\u2018': "'", '\u2019': "'",
        '\u201c': '"', '\u201d': '"', '\u2026': '...', '\u2022': '-',
        '\u2030': '%%', '\u20ac': 'EUR', '\u00a0': ' ',
    }
    for uni, asc in replacements.items():
        text = text.replace(uni, asc)
    # Drop anything not in Latin-1
    return text.encode('latin-1', errors='replace').decode('latin-1')


class FinancialPDFReport(FPDF if FPDF_AVAILABLE else object):
    """Professional financial intelligence PDF report."""

    def __init__(self):
        if not FPDF_AVAILABLE:
            raise RuntimeError("fpdf2 is required for PDF generation. Install: pip install fpdf2")
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_auto_page_break(auto=True, margin=20)
        self._company = "FinAI Intelligence Report"
        self._generated_at = ""
        self._font_name = "Helvetica"

        # Note: fpdf2 has issues with Georgian Unicode glyphs.
        # For Georgian content, use generate_reportlab_pdf() instead.
        # This fpdf2 generator sanitizes non-Latin text for compatibility.

    def header(self):
        """Page header with company name and line."""
        self.set_font(self._font_name, "B", 10)
        self.set_text_color(*_COLORS["secondary"])
        self.cell(0, 8, self._company, align="L")
        self.cell(0, 8, self._generated_at, align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*_COLORS["accent"])
        self.set_line_width(0.5)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def footer(self):
        """Page footer with page number."""
        self.set_y(-15)
        self.set_font(self._font_name, "I", 8)
        self.set_text_color(*_COLORS["secondary"])
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

    # ── Section helpers ─────────────────────────────────────────────

    def _section_title(self, title: str):
        """Add a section title with underline."""
        self.ln(4)
        self.set_font(self._font_name, "B", 14)
        self.set_text_color(*_COLORS["primary"])
        self.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*_COLORS["accent"])
        self.set_line_width(0.3)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(3)

    def _subsection(self, title: str):
        """Add a subsection heading."""
        self.set_font(self._font_name, "B", 11)
        self.set_text_color(*_COLORS["primary"])
        self.cell(0, 7, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def _body_text(self, text: str):
        """Add body text."""
        self.set_font(self._font_name, "", 10)
        self.set_text_color(*_COLORS["primary"])
        self.multi_cell(0, 5, _sanitize(text))
        self.ln(1)

    def _metric_row(self, label: str, value: str, color=None):
        """Add a label: value row."""
        self.set_font(self._font_name, "", 10)
        self.set_text_color(*_COLORS["secondary"])
        self.cell(70, 6, _sanitize(label))
        self.set_font(self._font_name, "B", 10)
        self.set_text_color(*(color or _COLORS["primary"]))
        self.cell(0, 6, _sanitize(value), new_x="LMARGIN", new_y="NEXT")

    def _bullet(self, text: str):
        """Add a bullet point."""
        self.set_font(self._font_name, "", 9)
        self.set_text_color(*_COLORS["primary"])
        self.cell(5, 5, "-")
        self.multi_cell(175, 5, _sanitize(text))

    def _badge(self, text: str, color: tuple):
        """Add a colored badge/pill."""
        self.set_fill_color(*color)
        self.set_text_color(*_COLORS["white"])
        self.set_font(self._font_name, "B", 9)
        w = self.get_string_width(text) + 6
        self.cell(w, 6, text, fill=True)
        self.set_text_color(*_COLORS["primary"])

    def _table(self, headers: List[str], rows: List[List[str]], col_widths: Optional[List[int]] = None):
        """Add a simple table."""
        widths = col_widths or [int(190 / len(headers))] * len(headers)

        # Header
        self.set_font(self._font_name, "B", 9)
        self.set_fill_color(*_COLORS["light"])
        self.set_text_color(*_COLORS["primary"])
        for i, h in enumerate(headers):
            self.cell(widths[i], 7, _sanitize(h), border=1, fill=True)
        self.ln()

        # Rows
        self.set_font(self._font_name, "", 9)
        for row in rows:
            for i, cell in enumerate(row):
                self.cell(widths[i], 6, _sanitize(str(cell)[:30]), border=1)
            self.ln()
        self.ln(2)


# ═══════════════════════════════════════════════════════════════════
# REPORT GENERATOR
# ═══════════════════════════════════════════════════════════════════

class PDFReportGenerator:
    """Generates PDF reports from Orchestrator output."""

    def generate_from_orchestrator(
        self,
        result_dict: Dict[str, Any],
        company_name: str = None,
        output_path: Optional[str] = None,
    ) -> bytes:
        """
        Generate a full financial intelligence PDF report.

        Args:
            result_dict: OrchestratorResult.to_dict() output
            company_name: Company name for header
            output_path: Optional file path to save PDF (also returns bytes)

        Returns:
            PDF bytes (can be served as HTTP response)
        """
        company_name = company_name or settings.COMPANY_NAME
        if not FPDF_AVAILABLE:
            raise RuntimeError("fpdf2 required. Install: pip install fpdf2")

        pdf = FinancialPDFReport()
        pdf._company = company_name
        pdf._generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        pdf.alias_nb_pages()

        # ── Title page ──────────────────────────────────────────────
        pdf.add_page()
        pdf.ln(30)
        pdf.set_font(pdf._font_name, "B", 28)
        pdf.set_text_color(*_COLORS["primary"])
        pdf.cell(0, 15, "Financial Intelligence Report", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(5)
        pdf.set_font(pdf._font_name, "", 14)
        pdf.set_text_color(*_COLORS["secondary"])
        pdf.cell(0, 10, _sanitize(company_name), align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(5)
        pdf.set_font(pdf._font_name, "I", 11)
        pdf.cell(0, 8, f"Generated: {pdf._generated_at}", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(15)

        # Executive summary box
        exec_summary = result_dict.get("executive_summary", {})
        self._add_executive_summary(pdf, exec_summary)

        # ── Diagnosis ───────────────────────────────────────────────
        pdf.add_page()
        diagnosis = result_dict.get("diagnosis", {})
        if diagnosis:
            self._add_diagnosis_section(pdf, diagnosis)

        # ── Decision + Verdict ──────────────────────────────────────
        decision = result_dict.get("decision", {})
        if decision:
            self._add_decision_section(pdf, decision)

        # ── P&L Summary Table ──────────────────────────────────────
        financials = result_dict.get("financials", result_dict.get("current", {}))
        if financials and financials.get("revenue", 0) > 0:
            pdf.add_page()
            self._add_pnl_table(pdf, financials)

        # ── Strategy ────────────────────────────────────────────────
        strategy = result_dict.get("strategy", {})
        if strategy:
            pdf.add_page()
            self._add_strategy_section(pdf, strategy)

        # ── Simulation Results ─────────────────────────────────────
        simulation = result_dict.get("simulation", {})
        if simulation:
            self._add_simulation_section(pdf, simulation)

        # ── Monitoring ──────────────────────────────────────────────
        monitoring = result_dict.get("monitoring", {})
        if monitoring:
            pdf.add_page()
            self._add_monitoring_section(pdf, monitoring)

        # ── Analogy ─────────────────────────────────────────────────
        analogy = result_dict.get("analogy", {})
        if analogy:
            self._add_analogy_section(pdf, analogy)

        # ── Output ──────────────────────────────────────────────────
        pdf_bytes = pdf.output()

        if output_path:
            with open(output_path, "wb") as f:
                f.write(pdf_bytes)
            logger.info("PDF report saved: %s (%d bytes)", output_path, len(pdf_bytes))

        return pdf_bytes

    # ── Section builders ────────────────────────────────────────────

    def _add_executive_summary(self, pdf: FinancialPDFReport, summary: Dict):
        """Add executive summary section."""
        pdf._section_title("Executive Summary")

        health = summary.get("health_score", 0)
        grade = summary.get("health_grade", "?")
        color = _HEALTH_COLORS.get(grade[0] if grade else "F", _COLORS["danger"])

        pdf._metric_row("Financial Health Score:", f"{health:.0f}/100 ({grade})", color)
        pdf._metric_row("Conviction Grade:", summary.get("conviction_grade", "N/A"))
        pdf._metric_row("Strategy:", summary.get("strategy_name", "N/A"))
        pdf._metric_row("System Health:", summary.get("system_health", "unknown"))
        pdf._metric_row("Cash Runway:", f"{summary.get('cash_runway_months', 0):.0f} months")
        pdf._metric_row("Do-Nothing Cost:",
                          f"{summary.get('do_nothing_cost', 0):,.0f} GEL")
        pdf._metric_row("Pipeline Stages:",
                          f"{summary.get('stages_completed', 0)}/{summary.get('stages_completed', 0) + summary.get('stages_failed', 0)}")

    def _add_diagnosis_section(self, pdf: FinancialPDFReport, diagnosis: Dict):
        """Add diagnosis section."""
        pdf._section_title("Financial Diagnosis")

        score = diagnosis.get("health_score", 0)
        grade = diagnosis.get("health_grade", "?")
        pdf._metric_row("Health Score:", f"{score:.0f}/100 ({grade})")

        # Signal summary
        signals = diagnosis.get("signal_summary", {})
        if signals:
            pdf._subsection("Signal Summary")
            for sev in ["critical", "high", "medium", "low"]:
                count = signals.get(sev, 0)
                if count > 0:
                    pdf._metric_row(f"  {sev.title()}:", str(count),
                                      _COLORS["danger"] if sev in ("critical", "high") else None)

        # Top diagnoses
        diagnoses = diagnosis.get("diagnoses", [])[:5]
        if diagnoses:
            pdf._subsection("Top Diagnoses")
            for d in diagnoses:
                signal = d.get("signal", {})
                pdf._bullet(
                    f"{signal.get('metric', '?')}: {signal.get('description', '')}"
                )

        # Top recommendations
        recs = diagnosis.get("recommendations", [])[:5]
        if recs:
            pdf._subsection("Recommendations")
            for r in recs:
                pdf._bullet(f"[{r.get('priority', '?').upper()}] {r.get('action', '')}")

    def _add_decision_section(self, pdf: FinancialPDFReport, decision: Dict):
        """Add decision intelligence section."""
        pdf._section_title("Decision Intelligence")

        pdf._metric_row("Actions Evaluated:", str(decision.get("actions_evaluated", 0)))

        verdict = decision.get("cfo_verdict")
        if verdict:
            pdf._subsection("CFO Verdict")
            pdf.set_font(pdf._font_name, "B", 10)
            pdf.set_text_color(*_COLORS["accent"])
            statement = verdict.get("verdict_statement", "")
            # Truncate safely for PDF
            if len(statement) > 200:
                statement = statement[:197] + "..."
            pdf.multi_cell(0, 5, _sanitize(statement))
            pdf.ln(2)

            conv_score = verdict.get('conviction_score', 0)
            try: conv_score = float(conv_score)
            except (ValueError, TypeError): conv_score = 0
            pdf._metric_row("Conviction:", f"{verdict.get('conviction_grade', '?')} ({conv_score:.0%})")
            pdf._metric_row("Time Pressure:", str(verdict.get("time_pressure", "normal")))
            dnc = verdict.get('do_nothing_cost', 0)
            try: dnc = float(dnc)
            except (ValueError, TypeError): dnc = 0
            pdf._metric_row("Do-Nothing Cost:", f"{dnc:,.0f} GEL")

            # Justification bullets
            justification = verdict.get("justification", [])
            if justification:
                pdf._subsection("Justification")
                for j in justification[:5]:
                    if len(j) > 150:
                        j = j[:147] + "..."
                    pdf._bullet(j)

            # Risk
            risk = verdict.get("risk_acknowledgment", "")
            if risk:
                pdf._subsection("Risk Acknowledgment")
                if len(risk) > 200:
                    risk = risk[:197] + "..."
                pdf._body_text(risk)

    def _add_strategy_section(self, pdf: FinancialPDFReport, strategy: Dict):
        """Add strategy section."""
        pdf._section_title("Strategic Plan")

        pdf._metric_row("Strategy:", strategy.get("name", "N/A"))
        pdf._metric_row("Duration:", f"{strategy.get('total_duration_days', 0)} days")
        pdf._metric_row("Investment:", f"{strategy.get('total_investment', 0):,.0f} GEL")
        pdf._metric_row("Expected ROI:", f"{strategy.get('overall_roi', 0):.1f}x")

        phases = strategy.get("phases", [])
        if phases:
            pdf._subsection("Phases")
            headers = ["#", "Phase", "Duration", "Profit Delta"]
            rows = []
            for p in phases:
                rows.append([
                    str(p.get("phase_number", "")),
                    p.get("phase_name", "").title(),
                    f"{p.get('duration_days', 0)} days",
                    f"{p.get('expected_profit_delta', 0):,.0f}",
                ])
            pdf._table(headers, rows, [10, 60, 50, 70])

    def _add_monitoring_section(self, pdf: FinancialPDFReport, monitoring: Dict):
        """Add monitoring section."""
        pdf._section_title("Monitoring Status")

        alerts = monitoring.get("alerts", {})
        pdf._metric_row("Active Alerts:", str(alerts.get("active", 0)))
        pdf._metric_row("Critical:", str(alerts.get("critical", 0)),
                          _COLORS["danger"] if alerts.get("critical", 0) > 0 else None)
        pdf._metric_row("System Health:", monitoring.get("system_health", "unknown"))

        kpi = monitoring.get("kpi", {})
        if kpi:
            pdf._metric_row("KPIs On Track:", str(kpi.get("on_track", 0)))
            pdf._metric_row("KPIs Missed:", str(kpi.get("missed", 0)),
                              _COLORS["danger"] if kpi.get("missed", 0) > 0 else None)

        runway = monitoring.get("cash_runway", {})
        if runway:
            pdf._metric_row("Cash Runway:", f"{runway.get('months', 0):.0f} months ({runway.get('risk', '?')})")

    def _add_analogy_section(self, pdf: FinancialPDFReport, analogy: Dict):
        """Add analogy base section."""
        pdf._section_title("Historical Analogies")

        pdf._metric_row("Dominant Strategy:", analogy.get("dominant_strategy", "N/A"))
        conf = analogy.get('confidence', 0)
        try: conf = float(conf)
        except (ValueError, TypeError): conf = 0
        pdf._metric_row("Confidence:", f"{conf:.0%}")
        pdf._metric_row("Matches Found:", str(len(analogy.get("matches", []))))

        matches = analogy.get("matches", [])[:3]
        if matches:
            pdf._subsection("Top Analogous Situations")
            headers = ["Similarity", "Industry", "Strategy", "ROI"]
            rows = []
            for m in matches:
                meta = m.get("metadata", {})
                sim = m.get('similarity_score', 0)
                try: sim = float(sim)
                except (ValueError, TypeError): sim = 0
                roi = meta.get('roi', 0)
                try: roi = float(roi)
                except (ValueError, TypeError): roi = 0
                rows.append([
                    f"{sim:.1%}",
                    str(meta.get("industry", "?"))[:15],
                    str(meta.get("strategy_outcome", "?"))[:20],
                    f"{roi:.1f}x",
                ])
            pdf._table(headers, rows, [35, 45, 70, 40])


    def _add_pnl_table(self, pdf: FinancialPDFReport, financials: Dict):
        """Add P&L summary table."""
        pdf._section_title("Profit & Loss Summary")

        def _fmt(v):
            if v is None or v == 0:
                return "-"
            return f"{v:,.0f}" if abs(v) >= 1 else f"{v:.2f}"

        lines = [
            ("Revenue", financials.get("revenue", 0), True),
            ("  Wholesale", financials.get("revenue_wholesale", 0), False),
            ("  Retail", financials.get("revenue_retail", 0), False),
            ("COGS", -abs(financials.get("cogs", 0)), False),
            ("Gross Profit", financials.get("gross_profit", 0), True),
            ("Selling Expenses", -abs(financials.get("selling_expenses", 0)), False),
            ("Admin Expenses", -abs(financials.get("admin_expenses", 0)), False),
            ("EBITDA", financials.get("ebitda", 0), True),
            ("Depreciation", -abs(financials.get("depreciation", 0)), False),
            ("EBIT", financials.get("ebit", 0), True),
            ("Other Income", financials.get("other_income", 0), False),
            ("Other Expense", -abs(financials.get("other_expense", 0)), False),
            ("Profit Before Tax", financials.get("profit_before_tax", 0), True),
            ("Net Profit", financials.get("net_profit", 0), True),
        ]

        # Calculate margins
        rev = financials.get("revenue", 1)
        for label, amount, is_total in lines:
            if amount == 0 and not is_total and "Wholesale" not in label and "Retail" not in label:
                continue
            if is_total:
                pdf.set_font(pdf._font_name, "B", 10)
            else:
                pdf.set_font(pdf._font_name, "", 9)

            pct = f"{(amount / rev * 100):.1f}%" if rev and amount else ""
            color = _COLORS["success"] if amount > 0 else _COLORS["danger"] if amount < 0 else _COLORS["secondary"]
            pdf.set_text_color(*_COLORS["primary"])
            pdf.cell(80, 6, _sanitize(label))
            pdf.set_text_color(*color)
            pdf.cell(50, 6, _sanitize(f"GEL {_fmt(amount)}"), align="R")
            pdf.set_text_color(*_COLORS["secondary"])
            pdf.cell(30, 6, _sanitize(pct), align="R")
            pdf.ln()

        # Key ratios
        pdf.ln(5)
        pdf._subsection("Key Ratios")
        gm = (financials.get("gross_profit", 0) / rev * 100) if rev else 0
        nm = (financials.get("net_profit", 0) / rev * 100) if rev else 0
        em = (financials.get("ebitda", 0) / rev * 100) if rev else 0
        pdf._metric_row("Gross Margin:", f"{gm:.1f}%",
                          _COLORS["success"] if gm > 0 else _COLORS["danger"])
        pdf._metric_row("EBITDA Margin:", f"{em:.1f}%",
                          _COLORS["success"] if em > 0 else _COLORS["danger"])
        pdf._metric_row("Net Margin:", f"{nm:.1f}%",
                          _COLORS["success"] if nm > 0 else _COLORS["danger"])

    def _add_simulation_section(self, pdf: FinancialPDFReport, simulation: Dict):
        """Add Monte Carlo / sensitivity simulation results."""
        pdf._section_title("Risk Simulation")

        mc = simulation.get("monte_carlo", {})
        if mc:
            pdf._subsection("Monte Carlo Analysis")
            pdf._metric_row("Iterations:", str(mc.get("iterations", 0)))
            pdf._metric_row("Mean Net Profit:", f"GEL {mc.get('mean_net_profit', 0):,.0f}")
            pdf._metric_row("Median:", f"GEL {mc.get('median_net_profit', 0):,.0f}")
            pdf._metric_row("P5 (Worst):", f"GEL {mc.get('p5_net_profit', 0):,.0f}",
                              _COLORS["danger"])
            pdf._metric_row("P95 (Best):", f"GEL {mc.get('p95_net_profit', 0):,.0f}",
                              _COLORS["success"])
            var95 = mc.get("var_95", mc.get("p5_net_profit", 0))
            if var95 < 0:
                pdf._metric_row("Value at Risk (95%):", f"GEL {abs(var95):,.0f}",
                                  _COLORS["danger"])

        sens = simulation.get("sensitivity", {})
        bands = sens.get("bands", [])
        if bands:
            pdf._subsection("Sensitivity Analysis")
            pdf._metric_row("Most Sensitive:", sens.get("most_sensitive_variable", "?"))
            pdf._metric_row("Least Sensitive:", sens.get("least_sensitive_variable", "?"))
            headers = ["Variable", "Best Case", "Worst Case", "Range"]
            rows = []
            for b in bands[:6]:
                best = b.get("upside_net_profit", b.get("max_net_profit", 0))
                worst = b.get("downside_net_profit", b.get("min_net_profit", 0))
                rows.append([
                    b.get("variable", "?"),
                    f"GEL {best:,.0f}",
                    f"GEL {worst:,.0f}",
                    f"GEL {abs(best - worst):,.0f}",
                ])
            pdf._table(headers, rows, [40, 40, 40, 40])


# Module-level singleton
pdf_generator = PDFReportGenerator()


# ═══════════════════════════════════════════════════════════════════
#   ReportLab-based PDF Generator (Georgian Unicode support)
# ═══════════════════════════════════════════════════════════════════

def generate_reportlab_pdf(data: dict, company: str = "FinAI") -> bytes:
    """Generate a PDF report using ReportLab with full Georgian Unicode support."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.lib.colors import HexColor
        import io, os

        # Register Georgian-capable fonts
        font_configs = [
            ("FinAI", "C:/Windows/Fonts/tahoma.ttf"),
            ("FinAIBold", "C:/Windows/Fonts/tahomabd.ttf"),
        ]
        for name, path in font_configs:
            if os.path.exists(path):
                try:
                    pdfmetrics.registerFont(TTFont(name, path))
                except Exception as e:
                    logger.debug("Font registration failed for %s: %s", name, e)

        font = "FinAI" if "FinAI" in [f.fontName for f in pdfmetrics.getRegisteredFontNames() if hasattr(f, 'fontName')] else "Helvetica"
        font_bold = "FinAIBold" if font == "FinAI" else "Helvetica-Bold"

        # Try to use registered fonts
        try:
            pdfmetrics.getFont("FinAI")
            font = "FinAI"
            font_bold = "FinAIBold"
        except Exception as e:
            logger.debug("Custom font loading failed, using Helvetica: %s", e)
            font = "Helvetica"
            font_bold = "Helvetica-Bold"

        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        width, height = A4
        margin = 40
        y = height - margin

        # Colors
        blue = HexColor("#2563EB")
        green = HexColor("#10B981")
        red = HexColor("#EF4444")
        gray = HexColor("#64748B")
        dark = HexColor("#1E293B")

        def draw_header():
            nonlocal y
            c.setFont(font_bold, 18)
            c.setFillColor(dark)
            c.drawString(margin, y, company)
            y -= 20
            c.setFont(font, 10)
            c.setFillColor(gray)
            from datetime import datetime, timezone
            c.drawString(margin, y, f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
            y -= 5
            c.setStrokeColor(blue)
            c.setLineWidth(1)
            c.line(margin, y, width - margin, y)
            y -= 20

        def section_title(title):
            nonlocal y
            if y < 80:
                c.showPage()
                y = height - margin
            c.setFont(font_bold, 14)
            c.setFillColor(blue)
            c.drawString(margin, y, title)
            y -= 18

        def text_line(text, size=10, bold=False, color=None, indent=0):
            nonlocal y
            if y < 40:
                c.showPage()
                y = height - margin
            c.setFont(font_bold if bold else font, size)
            c.setFillColor(color or dark)
            c.drawString(margin + indent, y, str(text))
            y -= size + 4

        def metric_row(label, value, color=None):
            nonlocal y
            if y < 40:
                c.showPage()
                y = height - margin
            c.setFont(font, 10)
            c.setFillColor(gray)
            c.drawString(margin + 10, y, label)
            c.setFont(font_bold, 11)
            c.setFillColor(color or dark)
            c.drawRightString(width - margin, y, str(value))
            y -= 16

        # ── Page 1: Title + Executive Summary ──
        draw_header()

        section_title("Financial Intelligence Report")
        text_line(f"Company: {company}", 12, bold=True)

        fin = data.get("financials", data.get("current", {}))
        diag = data.get("diagnosis", {})
        health = diag.get("health_score", data.get("health_score", "N/A"))
        grade = diag.get("health_grade", data.get("health_grade", ""))

        y -= 10
        section_title("Executive Summary")
        text_line(f"Financial Health Score: {health}/100 ({grade})", 12, bold=True)

        exec_summary = data.get("executive_summary", "")
        if isinstance(exec_summary, dict):
            exec_summary = exec_summary.get("narrative", str(exec_summary))
        if exec_summary:
            # Word wrap
            words = str(exec_summary).split()
            line = ""
            for w in words:
                if len(line + w) > 90:
                    text_line(line, 10)
                    line = w + " "
                else:
                    line += w + " "
            if line.strip():
                text_line(line, 10)

        # ── P&L Summary ──
        y -= 10
        section_title("Profit & Loss Summary")
        rev = fin.get("revenue", 0)
        cogs = abs(fin.get("cogs", 0))
        gp = fin.get("gross_profit", rev - cogs)
        net = fin.get("net_profit", 0)
        ebitda = fin.get("ebitda", 0)

        def fmt(n):
            if abs(n) >= 1e6: return f"₾{n/1e6:,.1f}M"
            if abs(n) >= 1e3: return f"₾{n/1e3:,.0f}K"
            return f"₾{n:,.0f}"

        metric_row("Revenue", fmt(rev))
        metric_row("COGS", fmt(-cogs), red)
        metric_row("Gross Profit", fmt(gp), green if gp > 0 else red)
        metric_row("EBITDA", fmt(ebitda), green if ebitda > 0 else red)
        metric_row("Net Profit", fmt(net), green if net > 0 else red)

        gm = (gp / rev * 100) if rev else 0
        nm = (net / rev * 100) if rev else 0
        y -= 5
        metric_row("Gross Margin", f"{gm:.1f}%")
        metric_row("Net Margin", f"{nm:.1f}%", green if nm > 0 else red)

        # ── Strategy ──
        strat = data.get("strategy", {})
        if strat:
            y -= 10
            section_title("Strategy")
            text_line(f"Recommended: {strat.get('name', 'N/A')}", 11, bold=True)
            for phase in strat.get("phases", [])[:3]:
                text_line(f"• {phase.get('name', '')}: {phase.get('duration_days', 0)} days", 10, indent=10)

        # ── Monitoring ──
        mon = data.get("monitoring", {})
        alerts = mon.get("alerts", [])
        if alerts:
            y -= 10
            section_title(f"Active Alerts ({len(alerts)})")
            for alert in alerts[:5]:
                sev = alert.get("severity", "info")
                color = red if sev == "critical" else HexColor("#F59E0B") if sev == "warning" else gray
                text_line(f"[{sev.upper()}] {alert.get('message', alert.get('metric', 'Alert'))}", 10, color=color, indent=10)

        # ── Analogy ──
        analogy = data.get("analogy", {})
        if analogy and analogy.get("matches"):
            y -= 10
            section_title("Historical Analogies")
            text_line(f"Dominant Strategy: {analogy.get('dominant_strategy', 'N/A')}", 11, bold=True)

        c.save()
        buf.seek(0)
        return buf.read()

    except ImportError:
        logger.warning("ReportLab not available — falling back to fpdf2")
        return pdf_generator.generate_from_orchestrator(data, company)
    except Exception as e:
        logger.error(f"ReportLab PDF error: {e}")
        return pdf_generator.generate_from_orchestrator(data, company)
