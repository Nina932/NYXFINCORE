"""
Structured Report Generation Engine
====================================
Generates professional multi-section financial reports using Nemotron.
Each section is researched and written in parallel, then assembled.

Pipeline: Plan → Research (parallel) → Write (parallel) → Assemble → Polish

Sections:
1. Executive Summary
2. Key Financial Metrics
3. Causal Analysis & Drivers
4. Risk Assessment
5. Strategic Recommendations
6. Appendix (data tables)
"""

import asyncio
import time
import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class ReportSection:
    title: str
    content: str
    data_tables: List[Dict[str, Any]] = field(default_factory=list)
    charts: List[str] = field(default_factory=list)  # chart type hints for frontend
    generation_time_ms: int = 0


@dataclass
class StructuredReport:
    title: str
    company: str
    period: str
    generated_at: str
    sections: List[ReportSection]
    metadata: Dict[str, Any]
    total_generation_time_ms: int = 0

    def to_dict(self) -> Dict:
        return {
            "title": self.title,
            "company": self.company,
            "period": self.period,
            "generated_at": self.generated_at,
            "sections": [asdict(s) for s in self.sections],
            "metadata": self.metadata,
            "total_generation_time_ms": self.total_generation_time_ms,
        }


# Section definitions with prompts
SECTION_SPECS = [
    {
        "id": "executive_summary",
        "title": "Executive Summary",
        "prompt": """Write a concise executive summary (3-4 paragraphs) for {company} for period {period}.
Cover: overall financial health, key performance highlights, main concerns, and strategic outlook.
Use these metrics: Revenue: {revenue}, Gross Profit: {gross_profit}, Gross Margin: {gm_pct}%,
Net Profit: {net_profit}, EBITDA: {ebitda}.
{ontology}
Write in professional CFO-report tone. No bullet points in this section.""",
        "charts": [],
    },
    {
        "id": "key_metrics",
        "title": "Key Financial Metrics",
        "prompt": """Provide detailed analysis of key financial metrics for {company} ({period}).
For each metric, state: current value, benchmark comparison, and brief interpretation.
Metrics: Revenue ({revenue}), COGS ({cogs}), Gross Margin ({gm_pct}%),
Net Profit ({net_profit}), EBITDA ({ebitda}), Total Assets ({total_assets}),
Total Liabilities ({total_liabilities}), D/E Ratio ({de_ratio}).
{ontology}
Format each metric as a brief paragraph.""",
        "charts": ["kpi_cards", "waterfall"],
    },
    {
        "id": "causal_analysis",
        "title": "Causal Analysis & Key Drivers",
        "prompt": """Analyze the key causal drivers behind {company}'s financial performance for {period}.
The COGS ratio is {cogs_ratio}% of revenue. Gross margin is {gm_pct}%.
Explain WHY these numbers are what they are. Consider:
- Cost structure drivers (supplier pricing, volume, mix)
- Revenue drivers (channel mix wholesale vs retail, pricing power)
- Operating leverage effects
- Any anomalies or red flags
{ontology}
Write 3-4 focused paragraphs with specific numbers.""",
        "charts": ["pie_chart", "bar_chart"],
    },
    {
        "id": "risk_assessment",
        "title": "Risk Assessment",
        "prompt": """Provide a comprehensive risk assessment for {company} ({period}).
Current financials: Revenue {revenue}, Net Profit {net_profit}, D/E {de_ratio}.
Monte Carlo stress test shows: P(Loss) = {p_loss}%, VaR 95% = {var_95}, CVaR = {cvar_95}.
Assess:
1. Market risk (oil prices, FX, demand)
2. Credit/liquidity risk (current ratio, cash position)
3. Operational risk (supplier concentration, cost volatility)
4. Regulatory/compliance risk
{ontology}
Rate each risk: Low/Medium/High with brief justification.""",
        "charts": ["risk_matrix"],
    },
    {
        "id": "recommendations",
        "title": "Strategic Recommendations",
        "prompt": """Provide 4-5 prioritized strategic recommendations for {company} ({period}).
Context: Gross margin {gm_pct}%, COGS ratio {cogs_ratio}%, health score {health_score}/100.
For each recommendation include:
- Specific action
- Expected ROI
- Timeline
- Risk level
- Dependencies
{ontology}
Rank by composite value (ROI × probability × urgency). Be specific, not generic.""",
        "charts": ["action_table"],
    },
]


class StructuredReportEngine:
    """Generates multi-section financial reports with parallel LLM calls."""

    def __init__(self):
        self._llm = None

    def _ensure_llm(self):
        if self._llm is None:
            from app.services.local_llm import local_llm
            self._llm = local_llm

    async def generate(
        self,
        financials: Dict[str, float],
        balance_sheet: Optional[Dict[str, float]] = None,
        stress_data: Optional[Dict[str, Any]] = None,
        company: str = "",
        period: str = "",
        health_score: float = 0,
    ) -> StructuredReport:
        """Generate a full structured report with parallel section writing."""
        start = time.time()
        self._ensure_llm()

        # Build template variables
        from app.services.company_ontology import get_company_context
        ontology = get_company_context(company, period)

        revenue = financials.get("revenue", 0)
        cogs = abs(financials.get("cogs", 0))
        gp = financials.get("gross_profit", revenue - cogs)
        np_ = financials.get("net_profit", 0)
        ebitda = financials.get("ebitda", 0)
        gm = financials.get("gross_margin_pct", (gp / revenue * 100 if revenue else 0))
        cogs_ratio = (cogs / revenue * 100) if revenue else 0

        bs = balance_sheet or {}
        ta = bs.get("total_assets", 0)
        tl = bs.get("total_liabilities", 0)
        te = bs.get("total_equity", 0)
        de = (tl / te) if te > 0 else 0

        sd = stress_data or {}
        dist = sd.get("distribution", {})

        template_vars = {
            "company": company or "Company",
            "period": period or "Current",
            "revenue": f"₾{revenue/1e6:.1f}M",
            "cogs": f"₾{cogs/1e6:.1f}M",
            "gross_profit": f"₾{gp/1e6:.1f}M",
            "gm_pct": f"{gm:.1f}",
            "net_profit": f"₾{np_/1e6:.1f}M",
            "ebitda": f"₾{ebitda/1e6:.1f}M",
            "cogs_ratio": f"{cogs_ratio:.1f}",
            "total_assets": f"₾{ta/1e6:.1f}M",
            "total_liabilities": f"₾{tl/1e6:.1f}M",
            "total_equity": f"₾{te/1e6:.1f}M",
            "de_ratio": f"{de:.1f}x",
            "health_score": f"{health_score:.0f}",
            "p_loss": f"{dist.get('probability_loss', 0)*100:.1f}",
            "var_95": f"₾{dist.get('var_95', 0)/1e6:.1f}M",
            "cvar_95": f"₾{dist.get('cvar_95', 0)/1e6:.1f}M",
            "ontology": ontology,
        }

        # Generate all sections in parallel
        tasks = []
        for spec in SECTION_SPECS:
            prompt = spec["prompt"].format(**template_vars)
            tasks.append(self._generate_section(spec["title"], prompt, spec.get("charts", [])))

        sections = await asyncio.gather(*tasks)

        # Add appendix (data tables, no LLM needed)
        appendix = self._build_appendix(financials, balance_sheet, stress_data)
        sections.append(appendix)

        elapsed = int((time.time() - start) * 1000)

        return StructuredReport(
            title=f"Financial Intelligence Report — {company or 'Company'}",
            company=company,
            period=period,
            generated_at=datetime.now(timezone.utc).isoformat(),
            sections=sections,
            metadata={
                "model": "nvidia/nemotron-3-super-120b-a12b",
                "sections_count": len(sections),
                "health_score": health_score,
                "parallel_generation": True,
            },
            total_generation_time_ms=elapsed,
        )

    async def _generate_section(self, title: str, prompt: str, charts: List[str]) -> ReportSection:
        """Generate a single report section using the LLM."""
        start = time.time()
        system = (
            "You are a senior financial analyst writing a professional report section. "
            "Write clear, data-driven prose. Use specific numbers. "
            "Do not use markdown headers — just flowing paragraphs. "
            "Keep the section under 300 words."
        )
        try:
            content = await self._llm.chat(
                system=system,
                messages=[{"role": "user", "content": prompt}],
                complexity="capable",
                max_tokens=1024,
            )
            if not content:
                content = f"[Section generation pending — LLM unavailable. Key data included in prompt above.]"
        except Exception as e:
            logger.error("Report section '%s' failed: %s", title, e)
            content = f"[Section generation failed: {e}]"

        elapsed = int((time.time() - start) * 1000)
        return ReportSection(
            title=title,
            content=content,
            charts=charts,
            generation_time_ms=elapsed,
        )

    def _build_appendix(
        self,
        financials: Dict[str, float],
        balance_sheet: Optional[Dict[str, float]],
        stress_data: Optional[Dict[str, Any]],
    ) -> ReportSection:
        """Build appendix with raw data tables (no LLM needed)."""
        tables = []

        # P&L summary table
        pnl_rows = []
        for key in ["revenue", "cogs", "gross_profit", "ebitda", "net_profit",
                     "ga_expenses", "selling_expenses", "depreciation"]:
            val = financials.get(key)
            if val is not None:
                pnl_rows.append({"metric": key.replace("_", " ").title(), "value": round(val, 0)})
        if pnl_rows:
            tables.append({"name": "P&L Summary", "rows": pnl_rows})

        # Balance sheet table
        if balance_sheet:
            bs_rows = []
            for key in ["total_assets", "total_liabilities", "total_equity",
                         "current_assets", "current_liabilities", "fixed_assets_net"]:
                val = balance_sheet.get(key)
                if val is not None:
                    bs_rows.append({"metric": key.replace("_", " ").title(), "value": round(val, 0)})
            if bs_rows:
                tables.append({"name": "Balance Sheet", "rows": bs_rows})

        # Stress test summary
        if stress_data and stress_data.get("distribution"):
            dist = stress_data["distribution"]
            stress_rows = [
                {"metric": "VaR 95%", "value": round(dist.get("var_95", 0), 0)},
                {"metric": "CVaR (Expected Shortfall)", "value": round(dist.get("cvar_95", 0), 0)},
                {"metric": "P(Loss)", "value": f"{dist.get('probability_loss', 0)*100:.1f}%"},
                {"metric": "Median Outcome", "value": round(dist.get("median", 0), 0)},
                {"metric": "P10 (Downside)", "value": round(dist.get("p10", 0), 0)},
                {"metric": "P90 (Upside)", "value": round(dist.get("p90", 0), 0)},
            ]
            tables.append({"name": "Monte Carlo Stress Test (5,000 simulations)", "rows": stress_rows})

        return ReportSection(
            title="Appendix: Data Tables",
            content="Raw financial data and stress test results used in this report.",
            data_tables=tables,
            charts=[],
            generation_time_ms=0,
        )


# Singleton
structured_report_engine = StructuredReportEngine()
