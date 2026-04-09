"""
FinAI v2 PDF Report — Georgian Unicode support via DejaVu Sans.
================================================================
Key fix from v1: _sanitize() no longer strips Georgian characters.
Uses fpdf2 with DejaVu Sans TTF (supports Georgian, Cyrillic, Latin).

Public API:
    from app.services.v2.pdf_report import generate_pdf_report
"""

from __future__ import annotations

import io
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings

logger = logging.getLogger(__name__)

try:
    from fpdf import FPDF
    FPDF_AVAILABLE = True
except ImportError:
    FPDF_AVAILABLE = False

# Font paths — DejaVu Sans supports Georgian, Cyrillic, Latin
# Try multiple font locations
_PROJECT_ROOT = Path(__file__).parent.parent.parent
_FONT_DIR = _PROJECT_ROOT / "static" / "fonts"
if not _FONT_DIR.exists():
    _FONT_DIR = _PROJECT_ROOT.parent / "static" / "fonts"  # backend/static/fonts
_FONT_REGULAR = _FONT_DIR / "DejaVuSans.ttf"
_FONT_BOLD = _FONT_DIR / "DejaVuSans-Bold.ttf"


def _sanitize(text: str) -> str:
    """Sanitize text while PRESERVING Georgian characters.

    v1 bug: encoded to latin-1 which destroyed all Georgian text.
    v2 fix: only strip control characters, keep all Unicode.
    """
    if not text:
        return ""
    # Remove control characters but keep all printable Unicode (including Georgian)
    return "".join(c for c in str(text) if c.isprintable() or c in ("\n", "\t"))


class FinancialPDFReport(FPDF if FPDF_AVAILABLE else object):
    """Professional financial PDF with Georgian text support."""

    def __init__(self):
        if not FPDF_AVAILABLE:
            raise RuntimeError("fpdf2 required. Install: pip install fpdf2")
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_auto_page_break(auto=True, margin=20)
        self._company = "FinAI Intelligence Report"
        self._setup_fonts()

    def _setup_fonts(self):
        """Register DejaVu Sans for Georgian Unicode support."""
        if _FONT_REGULAR.exists():
            self.add_font("DejaVu", "", str(_FONT_REGULAR))
            self.add_font("DejaVu", "B", str(_FONT_BOLD))
            self._font_family = "DejaVu"
            logger.info("PDF: DejaVu Sans loaded (Georgian support enabled)")
        else:
            self._font_family = "Helvetica"
            logger.warning(
                "PDF: DejaVu Sans not found at %s — falling back to Helvetica "
                "(Georgian text will NOT render correctly)", _FONT_DIR,
            )

    def _set_font(self, style: str = "", size: int = 10):
        """Set font with Georgian-safe family."""
        self.set_font(self._font_family, style, size)

    # ── Building blocks ───────────────────────────────────────────────

    def add_title(self, title: str):
        self._set_font("B", 16)
        self.cell(0, 10, _sanitize(title), align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(3)

    def add_subtitle(self, subtitle: str):
        self._set_font("B", 12)
        self.set_text_color(60, 60, 60)
        self.cell(0, 8, _sanitize(subtitle), new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0, 0, 0)
        self.ln(2)

    def add_paragraph(self, text: str):
        self._set_font("", 9)
        self.multi_cell(0, 5, _sanitize(text))
        self.ln(2)

    def add_kv(self, label: str, value: str):
        self._set_font("B", 9)
        self.cell(70, 6, _sanitize(label))
        self._set_font("", 9)
        self.cell(0, 6, _sanitize(value), new_x="LMARGIN", new_y="NEXT")

    def add_section_header(self, text: str):
        self.ln(3)
        self._set_font("B", 11)
        self.set_fill_color(230, 240, 250)
        self.cell(0, 7, f"  {_sanitize(text)}", fill=True, new_x="LMARGIN", new_y="NEXT")
        self._set_font("", 9)
        self.ln(2)

    def add_bullet(self, text: str):
        self._set_font("", 9)
        x = self.get_x()
        self.cell(5, 5, "-")
        self.multi_cell(175, 5, _sanitize(text))
        self.ln(1)

    def add_table(self, headers: List[str], rows: List[List[Any]],
                   widths: Optional[List[int]] = None):
        if not headers:
            return
        if not widths:
            total = 185
            widths = [total // len(headers)] * len(headers)
            widths[-1] = total - sum(widths[:-1])

        # Header
        self._set_font("B", 8)
        self.set_fill_color(50, 70, 100)
        self.set_text_color(255, 255, 255)
        for i, h in enumerate(headers):
            self.cell(widths[i], 7, _sanitize(h), border=1, fill=True)
        self.ln()

        # Rows
        self._set_font("", 8)
        self.set_text_color(0, 0, 0)
        for row_idx, row in enumerate(rows[:50]):  # Limit to 50 rows
            if row_idx % 2:
                self.set_fill_color(245, 245, 245)
            else:
                self.set_fill_color(255, 255, 255)
            for i, cell in enumerate(row):
                self.cell(widths[i], 6, _sanitize(str(cell)[:40]), border=1, fill=True)
            self.ln()


def generate_pdf_report(
    report_data: Dict[str, Any],
    company_name: str = None,
    report_type: str = "Financial Intelligence Report",
) -> bytes:
    """Generate a PDF report from orchestrator/diagnostic data.

    Returns PDF as bytes (can be saved to file or sent as HTTP response).
    """
    company_name = company_name or settings.COMPANY_NAME
    if not FPDF_AVAILABLE:
        raise RuntimeError("fpdf2 required for PDF generation")

    pdf = FinancialPDFReport()
    pdf.add_page()

    # Header
    pdf.add_title(report_type)
    pdf.add_kv("Company:", company_name)
    pdf.add_kv("Generated:", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))
    pdf.add_kv("Period:", report_data.get("period", "N/A"))
    pdf.ln(5)

    # Executive Summary
    summary = report_data.get("executive_summary", report_data.get("summary", ""))
    if summary:
        pdf.add_section_header("Executive Summary")
        if isinstance(summary, dict):
            for k, v in summary.items():
                pdf.add_kv(k.replace("_", " ").title() + ":", str(v))
        else:
            pdf.add_paragraph(str(summary))

    # Diagnosis
    diagnosis = report_data.get("diagnosis", {})
    if diagnosis:
        pdf.add_section_header("Financial Diagnosis")
        health = diagnosis.get("health_score", "N/A")
        pdf.add_kv("Health Score:", f"{health}/100")
        signals = diagnosis.get("signals", diagnosis.get("diagnoses", []))
        if signals:
            for sig in signals[:10]:
                if isinstance(sig, dict):
                    msg = sig.get("message", sig.get("signal", {}).get("metric", str(sig)))
                    pdf.add_bullet(str(msg)[:200])

    # Decision Actions
    decision = report_data.get("decision", {})
    actions = decision.get("top_actions", [])
    if actions:
        pdf.add_section_header("Recommended Actions")
        headers = ["#", "Action", "Category", "ROI", "Risk"]
        rows = []
        for i, a in enumerate(actions[:10], 1):
            rows.append([
                str(i),
                str(a.get("description", ""))[:50],
                a.get("category", ""),
                str(a.get("roi_estimate", "")),
                a.get("risk_level", ""),
            ])
        pdf.add_table(headers, rows, [8, 90, 35, 25, 25])

    # CFO Verdict
    verdict = decision.get("cfo_verdict", {})
    if verdict:
        pdf.add_section_header("CFO Verdict")
        pdf.add_kv("Grade:", verdict.get("conviction_grade", "N/A"))
        pdf.add_paragraph(verdict.get("verdict_statement", ""))
        for j in verdict.get("justification", []):
            pdf.add_bullet(str(j))

    # Strategy
    strategy = report_data.get("strategy", {}).get("strategy", {})
    phases = strategy.get("phases", [])
    if phases:
        pdf.add_section_header("Strategic Plan")
        for p in phases:
            pdf.add_kv(
                f"Phase {p.get('phase_number', '?')}: {p.get('phase_name', '')}",
                p.get("description", "")[:100],
            )

    # Monitoring
    monitoring = report_data.get("monitoring", {})
    alerts = monitoring.get("active_alerts", [])
    if alerts:
        pdf.add_section_header("Active Alerts")
        for a in alerts[:10]:
            pdf.add_bullet(f"[{a.get('severity', 'info').upper()}] {a.get('message', '')[:150]}")

    # Footer
    pdf.ln(10)
    pdf._set_font("", 7)
    pdf.set_text_color(128, 128, 128)
    pdf.cell(0, 5, "Generated by FinAI v2 Financial Intelligence Platform", align="C")

    return pdf.output()
