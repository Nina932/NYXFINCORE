"""
FinAI Narrative Engine — Template + LLM-powered financial commentary.
═══════════════════════════════════════════════════════════════════════
Generates natural-language narratives for financial statements, metrics,
and analysis results. Two modes:

1. **Template-based**: Fast, deterministic commentary for common patterns
   (margin analysis, segment commentary, period comparison). No API call.

2. **LLM-powered**: Rich, contextual narratives for novel observations or
   when template output needs enhancement. Uses Claude API.

Used by:
  - InsightAgent: attaches narrative to reasoning chains
  - Income Statement: auto-commentary on P&L generation
  - Report Agent (future): executive summary sheets

Supports EN and KA (Georgian) output.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from decimal import Decimal

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class NarrativeSection:
    """A single section of a narrative (e.g., revenue commentary)."""
    title: str
    body: str
    severity: str = "info"       # info | warning | critical | positive
    data_points: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "title": self.title,
            "body": self.body,
            "severity": self.severity,
            "data_points": self.data_points,
        }


@dataclass
class FinancialNarrative:
    """Complete narrative for a financial report or analysis."""
    report_type: str             # income_statement | balance_sheet | analysis | comparison
    period: str
    language: str = "en"
    executive_summary: str = ""
    sections: List[NarrativeSection] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "report_type": self.report_type,
            "period": self.period,
            "language": self.language,
            "executive_summary": self.executive_summary,
            "sections": [s.to_dict() for s in self.sections],
            "recommendations": self.recommendations,
            "warnings": self.warnings,
        }

    def to_text(self) -> str:
        """Render the full narrative as plain text."""
        parts = []
        if self.executive_summary:
            parts.append(f"Executive Summary\n{self.executive_summary}\n")
        for s in self.sections:
            icon = {"warning": "⚠", "critical": "🔴", "positive": "✅"}.get(s.severity, "•")
            parts.append(f"{icon} {s.title}\n{s.body}\n")
        if self.recommendations:
            parts.append("Recommendations:")
            for r in self.recommendations:
                parts.append(f"  → {r}")
        if self.warnings:
            parts.append("\nWarnings:")
            for w in self.warnings:
                parts.append(f"  ⚠ {w}")
        return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _fmt(value: float, currency: str = "GEL") -> str:
    """Format a financial value with thousands separator."""
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:,.2f}M {currency}"
    elif abs(value) >= 1_000:
        return f"{value / 1_000:,.1f}K {currency}"
    return f"{value:,.2f} {currency}"


def _pct(value: float, total: float) -> str:
    """Percentage of total."""
    if total == 0:
        return "N/A"
    return f"{value / total * 100:.1f}%"


def _margin_pct(margin: float, revenue: float) -> str:
    """Margin as percentage of revenue."""
    if revenue == 0:
        return "N/A"
    return f"{margin / revenue * 100:.1f}%"


def _change_desc(current: float, previous: float) -> str:
    """Describe a change between two values."""
    if previous == 0:
        return "new" if current > 0 else "unchanged"
    delta = current - previous
    pct = delta / abs(previous) * 100
    direction = "increased" if delta > 0 else "decreased"
    return f"{direction} by {_fmt(abs(delta))} ({abs(pct):.1f}%)"


# ═══════════════════════════════════════════════════════════════════════════════
# TEMPLATE-BASED NARRATIVE GENERATORS
# ═══════════════════════════════════════════════════════════════════════════════

class NarrativeEngine:
    """Generates financial narratives using templates and optionally LLM."""

    def generate_income_statement_narrative(
        self,
        stmt_dict: Dict[str, Any],
        period: str = "",
        language: str = "en",
    ) -> FinancialNarrative:
        """Generate a full narrative for an income statement.

        Args:
            stmt_dict: IncomeStatement.to_dict() output
            period: e.g. "January 2025"
            language: "en" or "ka"

        Returns:
            FinancialNarrative with executive summary and sections
        """
        narrative = FinancialNarrative(
            report_type="income_statement",
            period=period or stmt_dict.get("period", ""),
            language=language,
        )

        rev = stmt_dict.get("revenue", {})
        cogs = stmt_dict.get("cogs", {})
        margins = stmt_dict.get("margins", {})
        total_rev = rev.get("total", 0)
        total_cogs = cogs.get("total", 0)
        gross_margin = margins.get("total_gross_margin", 0)
        gross_profit = margins.get("total_gross_profit", 0)
        ebitda = stmt_dict.get("ebitda", 0)
        net_profit = stmt_dict.get("net_profit", 0)
        ga = stmt_dict.get("ga_expenses", 0)

        # ── Executive Summary ─────────────────────────────────────────
        margin_rate = (gross_margin / total_rev * 100) if total_rev else 0
        ebitda_rate = (ebitda / total_rev * 100) if total_rev else 0
        net_rate = (net_profit / total_rev * 100) if total_rev else 0

        narrative.executive_summary = (
            f"For {period or 'the period'}, total revenue reached {_fmt(total_rev)} "
            f"with a gross margin of {_fmt(gross_margin)} ({margin_rate:.1f}% of revenue). "
            f"After operating expenses of {_fmt(ga)}, EBITDA stands at {_fmt(ebitda)} "
            f"({ebitda_rate:.1f}% margin). "
            f"Net profit is {_fmt(net_profit)} ({net_rate:.1f}% net margin)."
        )

        # ── Revenue Composition ───────────────────────────────────────
        ws_rev = rev.get("wholesale", {}).get("total", 0)
        rt_rev = rev.get("retail", {}).get("total", 0)
        other_rev = rev.get("other", 0)

        rev_body = (
            f"Revenue totals {_fmt(total_rev)}, split between "
            f"wholesale ({_fmt(ws_rev)}, {_pct(ws_rev, total_rev)}) and "
            f"retail ({_fmt(rt_rev)}, {_pct(rt_rev, total_rev)})"
        )
        if other_rev:
            rev_body += f", plus other revenue of {_fmt(other_rev)}"
        rev_body += "."

        # Identify dominant fuel types
        ws = rev.get("wholesale", {})
        rt = rev.get("retail", {})
        fuel_lines = []
        for fuel in ["petrol", "diesel", "cng", "lpg", "bitumen"]:
            ws_val = ws.get(fuel, 0)
            rt_val = rt.get(fuel, 0)
            total_fuel = ws_val + rt_val
            if total_fuel > 0:
                fuel_lines.append((fuel.capitalize(), total_fuel))
        fuel_lines.sort(key=lambda x: -x[1])
        if fuel_lines:
            top = fuel_lines[0]
            rev_body += f" {top[0]} is the largest revenue driver at {_fmt(top[1])} ({_pct(top[1], total_rev)})."

        narrative.sections.append(NarrativeSection(
            title="Revenue Composition",
            body=rev_body,
            severity="info",
            data_points={"wholesale": ws_rev, "retail": rt_rev, "other": other_rev},
        ))

        # ── Margin Analysis ───────────────────────────────────────────
        ws_margin = margins.get("wholesale", {}).get("total", 0)
        rt_margin = margins.get("retail", {}).get("total", 0)

        margin_body = f"Gross margin is {_fmt(gross_margin)} ({margin_rate:.1f}% of revenue). "

        # Check for negative margins
        neg_segments = []
        for segment in ["wholesale", "retail"]:
            seg_margins = margins.get(segment, {})
            for fuel in ["petrol", "diesel", "cng", "lpg", "bitumen"]:
                val = seg_margins.get(fuel, 0)
                if val < 0:
                    neg_segments.append((f"{segment.capitalize()} {fuel.capitalize()}", val))

        if ws_margin >= 0 and rt_margin >= 0:
            margin_body += (
                f"Both segments are profitable: wholesale margin {_fmt(ws_margin)} "
                f"({_margin_pct(ws_margin, ws_rev)}), retail margin {_fmt(rt_margin)} "
                f"({_margin_pct(rt_margin, rt_rev)})."
            )
            severity = "positive"
        elif ws_margin < 0 and rt_margin >= 0:
            margin_body += (
                f"Wholesale segment is operating at a loss ({_fmt(ws_margin)}), "
                f"while retail remains profitable ({_fmt(rt_margin)}, {_margin_pct(rt_margin, rt_rev)}). "
                f"This pattern is consistent with a market-share or volume-driven strategy "
                f"where wholesale pricing is set below cost to secure supply agreements, "
                f"cross-subsidized by higher retail margins."
            )
            severity = "warning"
        elif rt_margin < 0:
            margin_body += (
                f"Retail segment is operating at a loss ({_fmt(rt_margin)}), "
                f"which is unusual and warrants investigation. "
                f"Wholesale margin: {_fmt(ws_margin)}."
            )
            severity = "critical"
        else:
            margin_body += (
                f"Wholesale margin: {_fmt(ws_margin)}, Retail margin: {_fmt(rt_margin)}."
            )
            severity = "info"

        if neg_segments:
            narrative.warnings.extend(
                f"{seg} margin is NEGATIVE ({_fmt(val)})" for seg, val in neg_segments
            )

        narrative.sections.append(NarrativeSection(
            title="Margin Analysis",
            body=margin_body,
            severity=severity,
            data_points={"wholesale_margin": ws_margin, "retail_margin": rt_margin, "margin_rate": round(margin_rate, 1)},
        ))

        # ── Operating Expenses (G&A) ─────────────────────────────────
        ga_breakdown = stmt_dict.get("ga_breakdown", {})
        ga_body = f"General & administrative expenses total {_fmt(ga)}"
        if ga and total_rev:
            ga_body += f" ({ga / total_rev * 100:.1f}% of revenue)"
        ga_body += "."

        if ga_breakdown:
            # Sort by value descending, show top 3
            sorted_ga = sorted(ga_breakdown.items(), key=lambda x: -abs(x[1]))[:3]
            if sorted_ga:
                top_items = ", ".join(f"{k} ({_fmt(v)})" for k, v in sorted_ga)
                ga_body += f" Top cost drivers: {top_items}."

        narrative.sections.append(NarrativeSection(
            title="Operating Expenses",
            body=ga_body,
            severity="info",
            data_points={"ga_total": ga, "ga_pct_of_revenue": round(ga / total_rev * 100, 1) if total_rev else 0},
        ))

        # ── EBITDA & Profitability ────────────────────────────────────
        da = stmt_dict.get("da_expenses", 0)
        ebit = stmt_dict.get("ebit", 0)
        fin_net = stmt_dict.get("finance_net", 0)
        tax = stmt_dict.get("tax_expense", 0)

        profit_body = (
            f"EBITDA is {_fmt(ebitda)} ({ebitda_rate:.1f}% margin). "
            f"After depreciation & amortization of {_fmt(da)}, "
            f"EBIT reaches {_fmt(ebit)}."
        )
        if fin_net:
            profit_body += f" Net finance costs: {_fmt(abs(fin_net))}."
        if tax:
            profit_body += f" Tax expense: {_fmt(tax)}."
        profit_body += f" Bottom line: net profit of {_fmt(net_profit)} ({net_rate:.1f}% net margin)."

        profit_severity = "positive" if net_profit > 0 else ("critical" if net_profit < -abs(total_rev * 0.05) else "warning")
        narrative.sections.append(NarrativeSection(
            title="EBITDA & Profitability",
            body=profit_body,
            severity=profit_severity,
            data_points={"ebitda": ebitda, "ebit": ebit, "net_profit": net_profit},
        ))

        # ── Recommendations ───────────────────────────────────────────
        if margin_rate < 5:
            narrative.recommendations.append(
                "Gross margin below 5% is thin. Review pricing strategy and cost structure."
            )
        if ebitda_rate < 3:
            narrative.recommendations.append(
                "EBITDA margin below 3% leaves little buffer. Consider operating cost optimization."
            )
        if neg_segments:
            narrative.recommendations.append(
                "Investigate segments with negative margins. Determine if this is strategic "
                "(volume play) or structural (pricing / procurement issue)."
            )
        if ga and total_rev and (ga / total_rev > 0.15):
            narrative.recommendations.append(
                f"G&A expenses represent {ga / total_rev * 100:.0f}% of revenue, which is high. "
                f"Review for cost reduction opportunities."
            )

        return narrative

    def generate_comparison_narrative(
        self,
        stmt1_dict: Dict, stmt2_dict: Dict,
        period1: str, period2: str,
        language: str = "en",
    ) -> FinancialNarrative:
        """Generate narrative for period-over-period comparison."""
        narrative = FinancialNarrative(
            report_type="comparison",
            period=f"{period1} vs {period2}",
            language=language,
        )

        rev1 = stmt1_dict.get("revenue", {}).get("total", 0)
        rev2 = stmt2_dict.get("revenue", {}).get("total", 0)
        gm1 = stmt1_dict.get("margins", {}).get("total_gross_margin", 0)
        gm2 = stmt2_dict.get("margins", {}).get("total_gross_margin", 0)
        ebitda1 = stmt1_dict.get("ebitda", 0)
        ebitda2 = stmt2_dict.get("ebitda", 0)
        np1 = stmt1_dict.get("net_profit", 0)
        np2 = stmt2_dict.get("net_profit", 0)

        narrative.executive_summary = (
            f"Comparing {period1} to {period2}: "
            f"Revenue {_change_desc(rev2, rev1)}. "
            f"Gross margin {_change_desc(gm2, gm1)}. "
            f"EBITDA {_change_desc(ebitda2, ebitda1)}. "
            f"Net profit {_change_desc(np2, np1)}."
        )

        # Revenue trend
        rev_delta = rev2 - rev1
        rev_body = (
            f"Revenue moved from {_fmt(rev1)} ({period1}) to {_fmt(rev2)} ({period2}), "
            f"a change of {_fmt(rev_delta)}. "
        )
        # Break down by segment
        ws1 = stmt1_dict.get("revenue", {}).get("wholesale", {}).get("total", 0)
        ws2 = stmt2_dict.get("revenue", {}).get("wholesale", {}).get("total", 0)
        rt1 = stmt1_dict.get("revenue", {}).get("retail", {}).get("total", 0)
        rt2 = stmt2_dict.get("revenue", {}).get("retail", {}).get("total", 0)
        if ws1 and ws2:
            rev_body += f"Wholesale {_change_desc(ws2, ws1)}. "
        if rt1 and rt2:
            rev_body += f"Retail {_change_desc(rt2, rt1)}."

        narrative.sections.append(NarrativeSection(
            title="Revenue Trend",
            body=rev_body,
            severity="positive" if rev_delta > 0 else "warning",
        ))

        # Margin trend
        margin_delta = gm2 - gm1
        m_body = f"Gross margin {_change_desc(gm2, gm1)}. "
        mr1 = (gm1 / rev1 * 100) if rev1 else 0
        mr2 = (gm2 / rev2 * 100) if rev2 else 0
        m_body += f"Margin rate moved from {mr1:.1f}% to {mr2:.1f}%."
        if mr2 < mr1 and rev2 > rev1:
            m_body += " Revenue grew but margins compressed, suggesting price pressure or rising input costs."

        narrative.sections.append(NarrativeSection(
            title="Margin Trend",
            body=m_body,
            severity="positive" if margin_delta > 0 else "warning",
        ))

        return narrative

    def generate_metric_explanation(
        self,
        metric_name: str,
        metric_value: float,
        context: Dict[str, Any],
        language: str = "en",
    ) -> NarrativeSection:
        """Generate a narrative explanation for a single metric.

        Common metrics: gross_margin, ebitda, net_profit, current_ratio,
        inventory_turnover, working_capital, etc.
        """
        total_rev = context.get("total_revenue", 0)

        templates = {
            "gross_margin": lambda: NarrativeSection(
                title="Gross Margin Analysis",
                body=(
                    f"Gross margin stands at {_fmt(metric_value)} "
                    f"({_margin_pct(metric_value, total_rev)} of revenue). "
                    + (
                        "This is a healthy margin indicating good cost management."
                        if total_rev and metric_value / total_rev > 0.1
                        else "This margin is thin and warrants close monitoring of COGS."
                    )
                ),
                severity="positive" if metric_value > 0 else "warning",
                data_points={"value": metric_value, "pct": round(metric_value / total_rev * 100, 1) if total_rev else 0},
            ),
            "ebitda": lambda: NarrativeSection(
                title="EBITDA Analysis",
                body=(
                    f"EBITDA is {_fmt(metric_value)} "
                    f"({_margin_pct(metric_value, total_rev)} margin). "
                    + (
                        "Positive EBITDA indicates the core business generates cash before financing and tax."
                        if metric_value > 0
                        else "Negative EBITDA means the core business is consuming cash. Urgent review needed."
                    )
                ),
                severity="positive" if metric_value > 0 else "critical",
                data_points={"value": metric_value},
            ),
            "net_profit": lambda: NarrativeSection(
                title="Net Profit Analysis",
                body=(
                    f"Net profit is {_fmt(metric_value)} "
                    f"({_margin_pct(metric_value, total_rev)} net margin). "
                    + (
                        "The company is profitable after all costs, interest, and taxes."
                        if metric_value > 0
                        else "The company recorded a net loss. Review margin structure and financing costs."
                    )
                ),
                severity="positive" if metric_value > 0 else "critical",
                data_points={"value": metric_value},
            ),
            "current_ratio": lambda: NarrativeSection(
                title="Liquidity (Current Ratio)",
                body=(
                    f"Current ratio is {metric_value:.2f}x. "
                    + (
                        "Above 1.5x indicates comfortable liquidity."
                        if metric_value >= 1.5
                        else "Below 1.5x. The company may face short-term liquidity pressure."
                        if metric_value >= 1.0
                        else "Below 1.0x — current liabilities exceed current assets. Liquidity risk is elevated."
                    )
                ),
                severity="positive" if metric_value >= 1.5 else ("warning" if metric_value >= 1.0 else "critical"),
                data_points={"value": metric_value},
            ),
            "inventory_turnover": lambda: NarrativeSection(
                title="Inventory Turnover",
                body=(
                    f"Inventory turns over {metric_value:.1f}x per period. "
                    + (
                        "Good turnover indicates efficient inventory management."
                        if metric_value >= 4
                        else "Low turnover suggests excess inventory or slow-moving stock."
                    )
                ),
                severity="positive" if metric_value >= 4 else "warning",
                data_points={"value": metric_value},
            ),
        }

        generator = templates.get(metric_name)
        if generator:
            return generator()

        # Fallback: generic metric explanation
        return NarrativeSection(
            title=f"{metric_name.replace('_', ' ').title()} Analysis",
            body=f"{metric_name.replace('_', ' ').title()} is {_fmt(metric_value)}.",
            severity="info",
            data_points={"value": metric_value},
        )

    async def generate_llm_narrative(
        self,
        data_summary: str,
        prompt_context: str = "",
        language: str = "en",
    ) -> str:
        """Generate a rich narrative using Claude LLM.

        Used when template-based generation is insufficient or for
        novel/complex observations that need reasoning.

        Args:
            data_summary: Structured data as text to narrate
            prompt_context: Additional context (e.g., what to focus on)
            language: "en" or "ka"

        Returns:
            Generated narrative text
        """
        try:
            from anthropic import AsyncAnthropic
            from app.config import settings

            if not settings.ANTHROPIC_API_KEY:
                return "(LLM narrative unavailable — API key not configured)"

            client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

            lang_instruction = (
                "Write in Georgian (ქართული)." if language == "ka"
                else "Write in English."
            )

            response = await client.messages.create(
                model=settings.ANTHROPIC_MODEL,
                max_tokens=1024,
                system=(
                    "You are a senior financial analyst writing executive commentary. "
                    "Be precise with numbers, identify key drivers, flag concerns, "
                    "and provide actionable insights. Keep it concise (2-4 paragraphs). "
                    f"{lang_instruction}"
                ),
                messages=[{
                    "role": "user",
                    "content": (
                        f"Write financial commentary for the following data:\n\n"
                        f"{data_summary}\n\n"
                        f"{prompt_context}"
                    ),
                }],
            )
            return response.content[0].text

        except Exception as e:
            logger.warning(f"LLM narrative generation failed: {e}")
            return f"(Narrative generation unavailable: {e})"


# Module-level singleton
narrative_engine = NarrativeEngine()
