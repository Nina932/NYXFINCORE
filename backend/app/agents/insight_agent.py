"""
FinAI Insight Agent — Financial reasoning, anomaly explanation, root-cause analysis.
═══════════════════════════════════════════════════════════════════════════════════════
The Insight Agent is the "why" engine. While CalcAgent computes numbers and DataAgent
parses files, InsightAgent REASONS about the data:

  • Reasoning Chains: step-by-step analysis linking observations to causes
  • Root-Cause Analysis: variance decomposition (volume, price, mix effects)
  • Anomaly Explanation: contextual interpretation of statistical outliers
  • Financial Commentary: intelligent narrative generation for reports
  • Accounting Flow Reasoning: leverages domain knowledge from accounting_intelligence.py

Tools owned (migrated from legacy ai_agent.py):
  - detect_anomalies        → large/negative transaction detection + commentary
  - detect_anomalies_statistical → Z-score, IQR, Benford's Law with reasoning
  - analyze_semantic         → classification confidence + commentary
  - analyze_accounting_flows → flow analysis with reasoning chains
  - search_knowledge         → RAG + domain knowledge search

Architecture:
  Supervisor → InsightAgent.execute(task) → uses accounting_intelligence + narrative_engine
                                          → returns AgentResult with reasoning + narrative
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.agents.base import BaseAgent, AgentTask, AgentContext, AgentResult
from app.models.all_models import (
    Dataset, Transaction, RevenueItem, COGSItem, GAExpenseItem,
    TrialBalanceItem, BalanceSheetItem,
)
from app.services.citation_service import CitationTracker
from app.config import settings

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# REASONING DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ReasoningStep:
    """A single step in a reasoning chain."""
    observation: str       # What we see: "Wholesale petrol margin is -2.3%"
    data_source: str       # Where the data comes from: "IncomeStatement.margin_wholesale_petrol"
    analysis: str          # What it means: "Revenue < COGS → below-cost pricing"
    implications: List[str] = field(default_factory=list)  # ["Market share strategy"]
    confidence: float = 0.8

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ReasoningChain:
    """A complete chain of reasoning about a financial observation."""
    question: str          # "Why is wholesale margin negative?"
    steps: List[ReasoningStep] = field(default_factory=list)
    conclusion: str = ""
    recommendations: List[str] = field(default_factory=list)
    confidence: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "question": self.question,
            "steps": [s.to_dict() for s in self.steps],
            "conclusion": self.conclusion,
            "recommendations": self.recommendations,
            "confidence": self.confidence,
        }

    def to_text(self) -> str:
        parts = [f"Question: {self.question}\n"]
        for i, step in enumerate(self.steps, 1):
            parts.append(f"  Step {i}: {step.observation}")
            parts.append(f"    Source: {step.data_source}")
            parts.append(f"    Analysis: {step.analysis}")
            if step.implications:
                parts.append(f"    Implications: {', '.join(step.implications)}")
        parts.append(f"\nConclusion: {self.conclusion}")
        if self.recommendations:
            parts.append("Recommendations:")
            for r in self.recommendations:
                parts.append(f"  -> {r}")
        return "\n".join(parts)


def _fgel(v: float) -> str:
    """Format financial value."""
    if v is None:
        return "N/A"
    if abs(v) >= 1_000_000:
        return f"{v:,.0f}"
    return f"{v:,.2f}"


def _pct_str(pct: float) -> str:
    """Format percentage change with sign."""
    return f"+{pct:.1f}%" if pct >= 0 else f"{pct:.1f}%"


def _fexact(v: float) -> str:
    """Exact format for accounting values."""
    if v is None:
        return "0.00"
    return f"{v:,.2f}"


# ═══════════════════════════════════════════════════════════════════════════════
# INSIGHT AGENT
# ═══════════════════════════════════════════════════════════════════════════════

# Tools this agent owns — migrated from legacy
INSIGHT_TOOLS = [
    "detect_anomalies",
    "detect_anomalies_statistical",
    "analyze_semantic",
    "analyze_accounting_flows",
    "search_knowledge",
]

# Template fallback responses for when Claude API is unavailable
INSIGHT_TEMPLATE_RESPONSES = {
    "detect_anomalies": (
        "⚠ AI reasoning engine temporarily unavailable.\n\n"
        "Anomaly detection checks for:\n"
        "• Transactions exceeding threshold amounts (potential bulk purchases, intercompany transfers)\n"
        "• Negative amounts (reversals, credit notes, corrections)\n"
        "• Unusual patterns in counterparty or account distribution\n\n"
        "Please try again in a moment for a full AI-powered anomaly analysis with reasoning."
    ),
    "detect_anomalies_statistical": (
        "⚠ AI reasoning engine temporarily unavailable.\n\n"
        "Statistical anomaly detection uses:\n"
        "• Z-score analysis (values > 3σ from mean)\n"
        "• IQR method (values outside 1.5×IQR)\n"
        "• Benford's Law (first-digit distribution test)\n\n"
        "Please try again in a moment for the full statistical analysis."
    ),
    "analyze_semantic": (
        "⚠ AI reasoning engine temporarily unavailable.\n\n"
        "Semantic analysis evaluates data classification confidence across:\n"
        "• Account code recognition and COA mapping\n"
        "• Sheet type detection accuracy\n"
        "• Column mapping completeness\n\n"
        "Please try again in a moment for AI-powered analysis."
    ),
    "analyze_accounting_flows": (
        "⚠ AI reasoning engine temporarily unavailable.\n\n"
        "Accounting flow analysis traces how money flows through the chart of accounts:\n"
        "• Revenue recognition → receivables\n"
        "• Purchase → payables → inventory → COGS\n"
        "• Operating expenses → P&L impact\n\n"
        "Please try again in a moment for detailed flow analysis with reasoning chains."
    ),
    "search_knowledge": (
        "⚠ AI reasoning engine temporarily unavailable.\n\n"
        "Knowledge search covers:\n"
        "• Georgian Chart of Accounts (406 accounts, 9 classes)\n"
        "• Financial flow explanations\n"
        "• Domain-specific accounting rules\n\n"
        "Please try again in a moment."
    ),
}


class InsightAgent(BaseAgent):
    """Financial reasoning and insight generation specialist.

    Owns analysis and reasoning tools. Adds reasoning chains and
    narrative commentary on top of raw data.

    Resilience:
    - Template fallback responses when Claude API is down
    - Health tracking via BaseAgent.safe_execute()
    - API error detection with graceful degradation
    """

    name = "insight"
    description = "Financial reasoning specialist — anomaly explanation, root-cause analysis, narrative"
    capabilities = ["analyze", "reason", "explain", "narrative"]
    tools = []  # Tools are still defined in legacy; InsightAgent delegates to legacy for execution

    @staticmethod
    def _system_prompt():
        return (
            "You are a senior financial analyst specializing in Georgian petroleum distribution companies, "
            f"particularly {settings.COMPANY_NAME}. You have deep expertise in IFRS accounting standards, "
            "Georgian tax regulations (VAT 18%, Estonian-model profit tax 15%, fuel excise duties), "
            "and fuel distribution economics (wholesale vs retail margin dynamics, COGS structure including excise). "
            "You provide concise, actionable financial insights grounded in data."
        )

    INSIGHT_SYSTEM_PROMPT = None  # Use _system_prompt() instead

    def can_handle(self, task: AgentTask) -> bool:
        return (
            task.task_type in self.capabilities
            or task.parameters.get("tool_name") in INSIGHT_TOOLS
        )

    async def _get_external_context(self, context: AgentContext) -> Dict[str, Any]:
        """
        Get external market and competitor data for enhanced insights.

        For company analysis, includes:
        - Real-time fuel prices and competitor pricing
        - Station performance metrics
        - Market share data
        - Economic indicators
        """
        external_context = {}

        try:
            from app.services.external_data import external_data
            async with external_data:
                # Company-specific data
                fuel_prices = await external_data.get_nyx_fuel_prices()
                competitor_data = await external_data.get_competitor_pricing()
                station_metrics = await external_data.get_nyx_station_metrics()

                # Market data
                exchange_rates = await external_data.get_bank_exchange_rates()
                market_indices = await external_data.get_market_indices()
                economic_indicators = await external_data.get_economic_indicators()

                external_context.update({
                    "fuel_prices": fuel_prices,
                    "competitor_pricing": competitor_data,
                    "station_metrics": station_metrics,
                    "exchange_rates": exchange_rates,
                    "market_indices": market_indices,
                    "economic_indicators": economic_indicators,
                    "data_freshness": "real_time"
                })

        except Exception as exc:
            logger.warning("Failed to fetch external data context: %s", exc)
            external_context["error"] = str(exc)
            external_context["data_freshness"] = "unavailable"

        return external_context

    async def execute(self, task: AgentTask, context: AgentContext) -> AgentResult:
        """Execute an insight/analysis task.

        Dispatches to the appropriate method based on tool_name or task_type.

        Resilience:
        - If execution fails with an API error, returns a template response
        - All exceptions are caught and recorded for health tracking
        """
        tool_name = task.parameters.get("tool_name", "")
        params = task.parameters.get("tool_input", task.parameters)
        db = context.db

        # Per-request citation tracker — accumulates provenance for every data point
        tracker = CitationTracker()

        try:
            # Get external context for enhanced insights
            external_context = await self._get_external_context(context)

            if tool_name == "detect_anomalies":
                result_text = await self._detect_anomalies_with_reasoning(params, db, external_context, tracker)
            elif tool_name == "detect_anomalies_statistical":
                result_text = await self._statistical_anomalies_with_reasoning(params, db, external_context, tracker)
            elif tool_name == "analyze_semantic":
                result_text = await self._semantic_analysis_with_reasoning(params, db, external_context, tracker)
            elif tool_name == "analyze_accounting_flows":
                result_text = await self._accounting_flows_with_reasoning(params, db, external_context, tracker)
            elif tool_name == "search_knowledge":
                result_text = await self._search_knowledge(params, db, external_context, tracker)
            elif tool_name == "explain_metric_change":
                result_text = await self._explain_metric_change_with_reasoning(params, db, external_context, tracker)
            elif tool_name == "simulate_scenario":
                result_text = await self._simulate_financial_scenario(params, db, external_context, tracker)
            elif task.task_type == "reason":
                result_text = await self._reason_about_metric(params, db, external_context, tracker)
            elif task.task_type == "narrative":
                result_text = await self._generate_narrative(params, db, external_context, tracker)
            else:
                # Delegate unknown tools to legacy
                return await self._delegate_to_legacy(task, context)

            return self._make_result(
                status="success",
                data={"tool_result": result_text, "tool_name": tool_name},
                narrative=result_text if isinstance(result_text, str) else str(result_text),
                citations=tracker.citations,
            )
        except Exception as e:
            error_str = str(e).lower()
            is_api_error = any(kw in error_str for kw in [
                "rate_limit", "overloaded", "api", "connection",
                "timeout", "500", "502", "503", "504", "529",
            ])

            if is_api_error:
                logger.warning(
                    "InsightAgent API error on '%s': %s — returning template response",
                    tool_name, e,
                )
                return self._api_down_result(tool_name)

            logger.error(f"InsightAgent error on {tool_name}: {e}", exc_info=True)
            return self._error_result(str(e))

    # ── Tool Implementations with Reasoning ───────────────────────────────────

    async def _detect_anomalies_with_reasoning(
        self, params: Dict, db: AsyncSession, external_context: Dict[str, Any],
        tracker: Optional[CitationTracker] = None,
    ) -> str:
        """Detect anomalies AND provide reasoning about them."""
        ds_id = await self._resolve_active_ds(db)
        min_amt = params.get("min_amount", 1_000_000)

        # Large transactions
        q = select(Transaction).where(Transaction.amount >= min_amt)
        if ds_id:
            q = q.where(Transaction.dataset_id == ds_id)
        result = await db.execute(q.order_by(Transaction.amount.desc()).limit(20))
        large = result.scalars().all()

        # Negative amounts
        q_neg = select(Transaction).where(Transaction.amount < 0)
        if ds_id:
            q_neg = q_neg.where(Transaction.dataset_id == ds_id)
        neg_result = await db.execute(q_neg.limit(10))
        negatives = neg_result.scalars().all()

        # Track citations for each transaction queried
        if tracker:
            for t in large:
                tracker.add_db_entity(
                    "transaction",
                    entity_id=t.id or 0,
                    dataset_id=t.dataset_id or ds_id or 0,
                    claim=f"{t.counterparty or 'Unknown'} {_fgel(t.amount)}",
                    value=float(t.amount),
                    period=str(t.date) if t.date else "",
                    source_sheet="Base",
                    account_code=t.acct_dr or "",
                )
            for t in negatives:
                tracker.add_db_entity(
                    "transaction",
                    entity_id=t.id or 0,
                    dataset_id=t.dataset_id or ds_id or 0,
                    claim=f"Negative: {t.counterparty or 'Unknown'} {_fgel(t.amount)}",
                    value=float(t.amount),
                    period=str(t.date) if t.date else "",
                    source_sheet="Base",
                )

        # Build reasoning chain
        chain = ReasoningChain(question=f"What anomalies exist in the transaction data?")

        # Include external market context
        fuel_prices = external_context.get("fuel_prices", {})
        competitor_data = external_context.get("competitor_pricing", {})
        market_indices = external_context.get("market_indices", {})

        if large:
            # Company-specific analysis for large transactions
            largest = large[0]
            market_context = ""
            if fuel_prices and competitor_data:
                avg_market_petrol = competitor_data.get("market_average_petrol", 0)
                if largest.amount > 500000:  # Large fuel purchase
                    market_context = f" Compared to market average petrol price of {_fgel(avg_market_petrol)}, this suggests bulk fuel procurement."

            chain.steps.append(ReasoningStep(
                observation=f"Found {len(large)} transactions exceeding {_fgel(min_amt)}",
                data_source="Transaction table (amount >= threshold)",
                analysis=(
                    f"Large transactions may indicate bulk fuel purchases, intercompany transfers, "
                    f"or station restocking. The largest is {_fgel(largest.amount)} "
                    f"dated {largest.date} for {largest.counterparty or 'Unknown'}."
                    f"{market_context}"
                ),
                implications=[
                    "Review fuel procurement contracts",
                    "Check station restocking patterns",
                    "Verify pricing against market rates"
                ],
                confidence=0.8,
            ))

        if negatives:
            chain.steps.append(ReasoningStep(
                observation=f"Found {len(negatives)} negative-amount transactions",
                data_source="Transaction table (amount < 0)",
                analysis=(
                    "Negative amounts typically represent returns, corrections, or reversals. "
                    "Excessive negatives may indicate data quality issues."
                ),
                implications=["Verify if these are legitimate reversals", "Check for duplicate corrections"],
                confidence=0.6,
            ))

        chain.conclusion = (
            f"Identified {len(large)} large transactions and {len(negatives)} negative entries. "
            f"Analysis incorporates real-time market data: current petrol market average {_fgel(competitor_data.get('market_average_petrol', 0))}. "
            f"These should be cross-referenced with fuel pricing and station performance data for validation."
        )
        chain.confidence = 0.8

        # Format output
        lines = [f"**Anomaly Detection (with reasoning)**\n"]
        lines.append(f"Large transactions (>{_fgel(min_amt)}):")
        for t in large:
            lines.append(f"  {t.date} | {_fgel(t.amount)} | {t.dept or ''} | {(t.cost_class or '')[:30]} | {(t.counterparty or '')[:30]}")

        if negatives:
            lines.append(f"\nNegative amounts ({len(negatives)}):")
            for t in negatives:
                lines.append(f"  {t.date} | {_fgel(t.amount)} | {t.dept or ''}")

        lines.append(f"\n**Reasoning:**\n{chain.to_text()}")
        return "\n".join(lines)

    async def _statistical_anomalies_with_reasoning(self, params: Dict, db: AsyncSession, external_context: Dict[str, Any], tracker: Optional[CitationTracker] = None) -> str:
        """Run statistical anomaly detection with full Z-score implementation and reasoning."""
        # Use the full statistical implementation
        context = AgentContext(db=db)
        raw_result = await self._handle_detect_anomalies_statistical(params, db, context)

        # Auto-extract citations from the tool result
        if tracker:
            try:
                result_dict = json.loads(raw_result) if isinstance(raw_result, str) else raw_result
                if isinstance(result_dict, dict):
                    tracker.extract_from_tool_result("detect_anomalies_statistical", params, result_dict)
            except Exception:
                pass  # Best-effort only

        return raw_result

    async def _handle_detect_anomalies_statistical(
        self, params: Dict, db: AsyncSession, context: AgentContext
    ) -> str:
        """Full statistical anomaly detection using Z-score, IQR, and trend analysis.

        Algorithm:
        1. Build time series for 8 key metrics across all available periods
        2. Compute Z-score for each metric's current value vs. historical mean
        3. Identify top 5 anomalies by Z-score magnitude
        4. Use LLM to generate contextual explanation for top 3 anomalies
        5. Return structured anomaly report
        """
        import statistics
        from sqlalchemy import select, distinct
        from app.models.all_models import Dataset, RevenueItem, COGSItem, GAExpenseItem
        from app.services.income_statement import build_income_statement

        # Get all datasets ordered by period
        all_datasets = (await db.execute(
            select(Dataset).where(Dataset.status == "ready").order_by(Dataset.created_at)
        )).scalars().all()

        if len(all_datasets) < 2:
            return json.dumps({
                "anomalies": [],
                "message": "Need at least 2 datasets for statistical analysis. Upload more periods.",
                "method": "z_score",
            })

        # Build time series for each dataset
        period_metrics: Dict[str, Dict[str, float]] = {}

        for ds in all_datasets:
            try:
                rev = (await db.execute(
                    select(RevenueItem).where(RevenueItem.dataset_id == ds.id)
                )).scalars().all()
                cogs = (await db.execute(
                    select(COGSItem).where(COGSItem.dataset_id == ds.id)
                )).scalars().all()
                ga = (await db.execute(
                    select(GAExpenseItem).where(GAExpenseItem.dataset_id == ds.id)
                )).scalars().all()

                if not rev or not cogs:
                    continue

                stmt = build_income_statement(rev, cogs, ga)
                period_key = ds.period or f"Dataset_{ds.id}"
                period_metrics[period_key] = {
                    "total_revenue": stmt.total_revenue or 0,
                    "total_cogs": stmt.total_cogs or 0,
                    "gross_margin": stmt.total_gross_margin or 0,
                    "gross_margin_pct": (
                        stmt.total_gross_margin / stmt.total_revenue * 100
                        if stmt.total_revenue != 0 else 0
                    ),
                    "wholesale_margin": stmt.margin_wholesale_total or 0,
                    "retail_margin": stmt.margin_retail_total or 0,
                    "ga_expenses": stmt.ga_expenses or 0,
                    "ebitda": stmt.ebitda or 0,
                }
            except Exception as e:
                logger.debug("Anomaly detection: skipping dataset %d: %s", ds.id, e)
                continue

        if len(period_metrics) < 2:
            return json.dumps({
                "anomalies": [],
                "message": "Insufficient parsed data for statistical analysis.",
                "method": "z_score",
            })

        # Compute Z-scores for each metric
        periods = list(period_metrics.keys())
        metrics = list(next(iter(period_metrics.values())).keys())

        anomalies = []
        for metric in metrics:
            values = [period_metrics[p][metric] for p in periods]

            if len(values) < 3:
                continue

            try:
                mean = statistics.mean(values)
                stdev = statistics.stdev(values)

                if stdev == 0:
                    continue

                current_period = periods[-1]
                current_value = values[-1]
                z_score = abs(current_value - mean) / stdev

                if z_score > 1.5:  # Flag anything > 1.5 std devs
                    anomalies.append({
                        "metric": metric,
                        "current_period": current_period,
                        "current_value": round(current_value, 2),
                        "historical_mean": round(mean, 2),
                        "historical_stdev": round(stdev, 2),
                        "z_score": round(z_score, 2),
                        "direction": "above_average" if current_value > mean else "below_average",
                        "severity": "critical" if z_score > 3.0 else "high" if z_score > 2.0 else "medium",
                        "pct_from_mean": round((current_value - mean) / abs(mean) * 100, 1) if mean != 0 else 0,
                    })
            except (statistics.StatisticsError, ZeroDivisionError):
                continue

        # Sort by Z-score magnitude (highest first)
        anomalies.sort(key=lambda x: x["z_score"], reverse=True)
        top_anomalies = anomalies[:5]  # Return top 5

        # LLM explanation for top 3
        explanation = ""
        if top_anomalies:
            try:
                # Get KG context for relevant accounts
                kg_context = ""
                try:
                    from app.services.knowledge_graph import knowledge_graph
                    if knowledge_graph.is_built:
                        for a in top_anomalies[:3]:
                            metric_name = a["metric"]
                            entities = knowledge_graph.query(metric_name, top_k=2)
                            if entities:
                                kg_context += f"\n{metric_name}: " + ", ".join(
                                    e.label_en for e in entities
                                )
                except Exception:
                    pass

                anomaly_data = json.dumps(top_anomalies[:3], indent=2)
                period_summary = f"Periods analyzed: {', '.join(periods)}"

                prompt = f"""Analyze these statistical anomalies in financial data:

{period_summary}
Anomalies detected (sorted by Z-score):
{anomaly_data}
{f'Domain context:{kg_context}' if kg_context else ''}

For each anomaly:
1. What business event could explain this deviation?
2. Is it likely a data quality issue or a real business change?
3. What immediate action (if any) is recommended?

Be specific to Georgian petroleum distribution ({settings.COMPANY_NAME} context).
Keep response concise — 2-3 sentences per anomaly."""

                llm_response = await self.call_llm(
                    system=self._system_prompt(),
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=1500,
                )
                for block in llm_response.content:
                    if hasattr(block, "text"):
                        explanation += block.text

            except Exception as e:
                logger.warning("[InsightAgent] Anomaly explanation LLM failed: %s", e)
                explanation = f"Top anomaly: {top_anomalies[0]['metric']} is {top_anomalies[0]['z_score']:.1f} std devs from mean ({top_anomalies[0]['direction']})."

        result = {
            "anomalies": top_anomalies,
            "total_found": len(anomalies),
            "periods_analyzed": len(period_metrics),
            "periods": periods,
            "method": "z_score",
            "explanation": explanation,
        }

        if not top_anomalies:
            result["message"] = f"No significant anomalies detected across {len(period_metrics)} periods. All metrics within normal range."

        return json.dumps(result, default=str)

    async def _semantic_analysis_with_reasoning(self, params: Dict, db: AsyncSession, external_context: Dict[str, Any], tracker: Optional[CitationTracker] = None) -> str:
        """Run semantic analysis with data-driven reasoning.

        Parses the raw result to extract actual classification metrics and
        builds reasoning steps from real data (not hardcoded boilerplate).
        """
        from app.services.ai_agent import agent as legacy_agent
        raw_result = await legacy_agent.execute_tool("analyze_semantic", params, db)

        if not raw_result or raw_result.startswith("Error"):
            return raw_result or "Semantic analysis unavailable."

        # Parse the result to extract actual classification data
        chain = ReasoningChain(question="How well is the financial data classified?")

        # Extract metrics from the raw result text
        lines = raw_result.split("\n")
        classified_count = 0
        unclassified_count = 0
        total_amount = 0.0
        high_confidence = 0
        low_confidence = 0

        for line in lines:
            lower = line.lower()
            if "classified" in lower and "un" not in lower:
                # Try to extract number from "X classified"
                nums = re.findall(r'(\d+)', line)
                if nums:
                    classified_count = max(classified_count, int(nums[0]))
            elif "unclassified" in lower or "unknown" in lower:
                nums = re.findall(r'(\d+)', line)
                if nums:
                    unclassified_count = max(unclassified_count, int(nums[0]))
            if "confidence" in lower:
                if "high" in lower:
                    nums = re.findall(r'(\d+)', line)
                    if nums:
                        high_confidence = int(nums[0])
                elif "low" in lower:
                    nums = re.findall(r'(\d+)', line)
                    if nums:
                        low_confidence = int(nums[0])

        total = classified_count + unclassified_count
        coverage_pct = (classified_count / total * 100) if total > 0 else 0

        # Build data-driven reasoning steps
        if total > 0:
            chain.steps.append(ReasoningStep(
                observation=f"Classification coverage: {classified_count}/{total} transactions ({coverage_pct:.0f}%)",
                data_source="Semantic Layer analysis result",
                analysis=(
                    f"{'Strong coverage' if coverage_pct >= 85 else 'Moderate coverage' if coverage_pct >= 60 else 'Weak coverage'} "
                    f"— {unclassified_count} transactions remain unclassified. "
                    f"{'Reports should be reliable.' if coverage_pct >= 85 else 'Reports may have accuracy gaps in uncovered areas.'}"
                ),
                implications=(
                    ["Reports are trustworthy for classified segments"] if coverage_pct >= 85
                    else ["Review unclassified transactions to improve report accuracy",
                          "Largest unclassified amounts should be prioritized"]
                ),
                confidence=0.85 if coverage_pct >= 85 else 0.6,
            ))
        else:
            chain.steps.append(ReasoningStep(
                observation="Semantic analysis completed but specific counts not extractable from result format",
                data_source="Semantic Layer analysis",
                analysis="Classification quality depends on COA mapping, counterparty signals, and department codes.",
                confidence=0.5,
            ))

        if high_confidence > 0 or low_confidence > 0:
            chain.steps.append(ReasoningStep(
                observation=f"Confidence distribution: {high_confidence} high, {low_confidence} low",
                data_source="Semantic confidence scores",
                analysis=(
                    f"{'Most transactions have strong classification signals.' if high_confidence > low_confidence else 'Many transactions have weak signals — manual review recommended.'}"
                ),
                confidence=0.8,
            ))

        chain.conclusion = (
            f"Classification {'is robust' if coverage_pct >= 85 else 'needs improvement'} "
            f"with {classified_count} of {total} transactions mapped."
            if total > 0 else "Review the full semantic analysis result for classification details."
        )

        return raw_result + f"\n\n**Reasoning:**\n{chain.to_text()}"

    async def _accounting_flows_with_reasoning(self, params: Dict, db: AsyncSession, external_context: Dict[str, Any], tracker: Optional[CitationTracker] = None) -> str:
        """Analyze accounting flows with reasoning chains."""
        from app.services.accounting_intelligence import accounting_intelligence

        flow_type = params.get("flow_type", "full")
        account_code = params.get("account_code")
        parts = []

        # Account classification with reasoning
        if account_code:
            cls = accounting_intelligence.classify_account(account_code)
            # Cite the knowledge graph lookup
            if tracker:
                tracker.add_knowledge_graph(
                    entity_id=f"coa_{account_code}",
                    entity_type="account",
                    claim=f"Account {account_code}: {cls.label_en or cls.category or 'unclassified'}",
                    account_code=account_code,
                )
            parts.append(
                f"**Account Classification: {account_code}**\n"
                f"  Match level: {cls.match_level} | Confidence: {cls.confidence:.0%}\n"
                f"  Statement: {cls.statement or 'N/A'} | Side: {cls.side or 'N/A'}\n"
                f"  P&L Line: {cls.pl_line or 'N/A'} | Category: {cls.category or 'N/A'}\n"
                f"  Label: {cls.label_en or 'N/A'} ({cls.label_ka or ''})\n"
                f"  Sub: {cls.sub or 'N/A'} | Source: {cls.source}"
            )
            if cls.key_account_info:
                ki = cls.key_account_info
                parts.append(f"  Key account: {ki.get('label', '')} ({ki.get('label_ka', '')}) — flow: {ki.get('flow', '')}")

            # Add reasoning about the account
            chain = ReasoningChain(question=f"What is account {account_code} and how does it flow?")
            chain.steps.append(ReasoningStep(
                observation=f"Account {account_code} classified as {cls.category or 'unknown'} ({cls.statement or '?'})",
                data_source=f"AccountingIntelligence.classify_account (match: {cls.match_level})",
                analysis=(
                    f"This account sits on the {cls.statement or 'unknown'} statement "
                    f"as a {cls.side or 'unknown'} item. "
                    f"{'It flows to the ' + cls.pl_line + ' line.' if cls.pl_line else ''}"
                ),
                confidence=cls.confidence,
            ))
            chain.conclusion = f"Account {account_code} is {cls.label_en or cls.category or 'unclassified'}."
            parts.append(f"\n**Reasoning:**\n{chain.to_text()}")

        # Flow explanation with reasoning
        if flow_type and flow_type != "full":
            flow = accounting_intelligence.explain_financial_flow(flow_type)
            if "title" in flow:
                parts.append(f"\n**{flow['title']}** ({flow.get('title_ka', '')})")
                parts.append(flow.get("description", ""))
                if flow.get("formula"):
                    parts.append(f"  Formula: {flow['formula']}")
                if flow.get("journal_entry"):
                    parts.append(f"  Journal: {flow['journal_entry']}")
                if flow.get("verification"):
                    parts.append(f"  Verification: {flow['verification']}")
                if flow.get("accounts"):
                    accts = flow["accounts"] if isinstance(flow["accounts"], list) else [flow["accounts"]]
                    parts.append(f"  Accounts: {', '.join(accts)}")
            else:
                parts.append(json.dumps(flow, indent=2))

        # Full flow analysis with reasoning
        if flow_type == "full" or (not account_code and not flow_type):
            ds_id = await self._resolve_active_ds(db)
            if ds_id:
                try:
                    analysis = await accounting_intelligence.analyze_dataset_flows(db, ds_id)

                    # Build reasoning chain about the full analysis
                    chain = ReasoningChain(question="What do the accounting flows tell us?")

                    # Coverage assessment
                    chain.steps.append(ReasoningStep(
                        observation=f"Account coverage: {analysis.mapped_accounts}/{analysis.total_accounts} ({analysis.coverage_pct}%)",
                        data_source="AccountingIntelligence.analyze_dataset_flows",
                        analysis=(
                            f"{'Good coverage — most accounts are mapped.' if analysis.coverage_pct >= 90 else 'Coverage gaps exist — some accounts are unmapped, affecting report accuracy.'}"
                        ),
                        confidence=0.9,
                    ))

                    # COGS reconciliation
                    chain.steps.append(ReasoningStep(
                        observation=f"COGS reconciliation variance: {analysis.cogs_variance_pct}%",
                        data_source="COGS Breakdown vs TB 71xx",
                        analysis=(
                            f"{'COGS reconciles within tolerance.' if analysis.cogs_reconciled else 'COGS mismatch detected — breakdown sheet differs from trial balance.'}"
                        ),
                        implications=(
                            ["Data is consistent"] if analysis.cogs_reconciled
                            else ["Investigate missing COGS entries", "Check for unrecorded cost adjustments"]
                        ),
                        confidence=0.9 if analysis.cogs_reconciled else 0.7,
                    ))

                    # BS identity
                    chain.steps.append(ReasoningStep(
                        observation=f"Balance Sheet: {'BALANCED' if analysis.bs_balanced else f'VARIANCE of {_fexact(analysis.bs_variance)}'}",
                        data_source="BS Identity check (A = L + E)",
                        analysis=(
                            f"{'The fundamental accounting equation holds.' if analysis.bs_balanced else 'Balance sheet does not balance — this indicates data integrity issues.'}"
                        ),
                        confidence=1.0 if analysis.bs_balanced else 0.5,
                    ))

                    chain.conclusion = (
                        f"Period: {analysis.period}. Coverage: {analysis.coverage_pct}%. "
                        f"COGS: {'reconciled' if analysis.cogs_reconciled else 'MISMATCH'}. "
                        f"BS: {'balanced' if analysis.bs_balanced else 'UNBALANCED'}. "
                        f"Working capital: current ratio {analysis.current_ratio}."
                    )
                    chain.confidence = min(
                        analysis.coverage_pct / 100,
                        1.0 if analysis.cogs_reconciled else 0.6,
                        1.0 if analysis.bs_balanced else 0.4,
                    )

                    if analysis.warnings:
                        chain.recommendations = [f"Investigate: {w}" for w in analysis.warnings[:5]]

                    # Format the full output (same as legacy but with reasoning)
                    parts.append(f"""
**=== Accounting Flow Analysis ({analysis.period}) ===**

**Account Coverage:** {analysis.mapped_accounts}/{analysis.total_accounts} ({analysis.coverage_pct}%)
  Unmapped: {analysis.unmapped_accounts}{(' — top: ' + ', '.join(u['code'] for u in analysis.unmapped_codes[:5])) if analysis.unmapped_codes else ''}

**Revenue Flow:**
  Gross Revenue: {_fexact(analysis.gross_revenue)} | Returns: {_fexact(analysis.returns_allowances)} | Net: {_fexact(analysis.net_revenue)}
  Segments: {', '.join(f'{k}: {_fexact(v)}' for k, v in analysis.revenue_by_segment.items())}

**COGS Formation:**
  Col K (1610-Sales): {_fexact(analysis.cogs_col6_total)}
  Col L (7310 Selling): {_fexact(analysis.cogs_col7310_total)}
  Col O (8230 Other): {_fexact(analysis.cogs_col8230_total)}
  Breakdown Total: {_fexact(analysis.cogs_breakdown_total)} | TB 71xx: {_fexact(analysis.cogs_tb_71xx_debit)}
  Variance: {analysis.cogs_variance_pct}% {'RECONCILED' if analysis.cogs_reconciled else 'MISMATCH'}

**P&L Waterfall:**
  Net Revenue: {_fexact(analysis.net_revenue)}
  - COGS: {_fexact(analysis.cogs_breakdown_total)}
  = Gross Margin: {_fexact(analysis.gross_margin)}
  - Selling (73xx): {_fexact(analysis.selling_expenses_73xx)}
  - Admin (74xx): {_fexact(analysis.admin_expenses_74xx)}
  = EBITDA: {_fexact(analysis.ebitda)}

**Balance Sheet Identity:**
  Assets: {_fexact(analysis.total_assets)} | Liabilities: {_fexact(analysis.total_liabilities)} | Equity: {_fexact(analysis.total_equity)}
  A = L + E: {'BALANCED' if analysis.bs_balanced else f'VARIANCE: {_fexact(analysis.bs_variance)}'}

**Working Capital:**
  Current Ratio: {analysis.current_ratio}

{'**Warnings:** ' + chr(10).join('  ' + w for w in analysis.warnings) if analysis.warnings else ''}""")

                    parts.append(f"\n**Reasoning Chain:**\n{chain.to_text()}")

                except Exception as e:
                    parts.append(f"Flow analysis error: {str(e)}")
            else:
                parts.append("No active dataset. Upload financial data first.")

        return "\n".join(parts) if parts else "Provide flow_type or account_code parameter."

    async def _search_knowledge(self, params: Dict, db: AsyncSession, external_context: Dict[str, Any], tracker: Optional[CitationTracker] = None) -> str:
        """Search knowledge base — knowledge graph first, then RAG, then legacy.

        Enhanced pipeline:
        1. Query the knowledge graph for structured domain knowledge
        2. Query the vector store for relevant data context (with source provenance)
        3. Fall back to legacy agent if needed
        """
        query = params.get("query", "")
        if not query:
            return "Provide a 'query' parameter to search knowledge."

        parts = []

        # 1. Knowledge graph — structured domain knowledge
        try:
            from app.services.knowledge_graph import knowledge_graph
            if knowledge_graph.is_built:
                entities = knowledge_graph.query(query, max_results=5)
                if entities:
                    parts.append("**Domain Knowledge:**")
                    for entity in entities:
                        label = entity.label_en
                        desc = entity.description[:300] if entity.description else ""
                        if entity.label_ka:
                            label += f" ({entity.label_ka})"
                        parts.append(f"  [{entity.entity_type}] {label}")
                        if desc:
                            parts.append(f"    {desc}")

                        # Cite knowledge graph entity
                        if tracker:
                            tracker.add_knowledge_graph(
                                entity_id=entity.entity_id,
                                entity_type=entity.entity_type,
                                claim=entity.label_en or str(entity.entity_id),
                                account_code=entity.entity_id.replace("coa_", "") if entity.entity_type == "account" else "",
                            )

                        # Show relationships for accounts
                        if entity.entity_type == "account":
                            related = [
                                r for r in entity.relationships
                                if r.relation_type in ("child_of", "parent_of")
                            ][:3]
                            if related:
                                rels = ", ".join(
                                    f"{r.relation_type}: {r.target_id.replace('coa_', '')}"
                                    for r in related
                                )
                                parts.append(f"    Relations: {rels}")

                # Account-specific deep lookup
                codes = re.findall(r'\b(\d{2,4})\b', query)
                for code in codes[:2]:
                    ctx = knowledge_graph.get_context_for_account(code)
                    if ctx.get("classification") and ctx.get("hierarchy"):
                        cls = ctx["classification"]
                        parts.append(
                            f"\n**Account {code} Detail:**"
                            f"\n  Classification: {cls.get('label_en', '?')} "
                            f"({cls.get('statement', '?')}/{cls.get('side', '?')})"
                            f"\n  Hierarchy: {' > '.join(ctx['hierarchy'])}"
                        )
                        if cls.get("pl_line"):
                            parts.append(f"  P&L line: {cls['pl_line']}")
                        for flow in ctx.get("related_flows", [])[:2]:
                            parts.append(
                                f"  Related flow: {flow['title']}"
                                + (f" — {flow['formula']}" if flow.get('formula') else "")
                            )
                        if ctx.get("key_account_info"):
                            ki = ctx["key_account_info"]
                            parts.append(
                                f"  Key account: {ki.get('label', '')} "
                                f"(flow: {ki.get('flow', 'N/A')})"
                            )
        except Exception as e:
            logger.debug(f"Knowledge graph search failed: {e}")

        # 2. Vector store RAG — with source provenance
        try:
            from app.services.vector_store import vector_store
            rag_context, rag_sources = await vector_store.get_context_with_sources(query, db, n_results=5)
            if rag_context:
                parts.append(f"\n{rag_context}")
            # Track citations from vector store results
            if tracker and rag_sources:
                tracker.add_from_vector_sources(rag_sources, query=query)
        except Exception as e:
            logger.debug(f"Vector store search failed: {e}")

        # 3. Legacy fallback if nothing found
        if not parts:
            from app.agents.registry import registry
            legacy = registry.get("legacy")
            if legacy:
                from app.services.ai_agent import agent as legacy_agent
                return await legacy_agent.execute_tool("search_knowledge", params, db)
            return "No relevant knowledge found."

        return "\n".join(parts)

    async def _explain_metric_change_with_reasoning(
        self, params: Dict, db: AsyncSession, external_context: Dict[str, Any],
        tracker: Optional[CitationTracker] = None
    ) -> str:
        """Phase E: Causal analysis for a metric change using FinancialReasoningEngine.

        Produces a structured causal chain grounded in KG knowledge, then passes
        it to Claude for narrative enrichment.
        """
        from app.services.financial_reasoning import reasoning_engine

        metric = params.get("metric", "gross_margin_pct")
        from_val = float(params.get("from_value", 0))
        to_val = float(params.get("to_value", 0))
        period_from = params.get("period_from", "Previous Period")
        period_to = params.get("period_to", "Current Period")
        context = params.get("context", {})

        # Build structured causal chain
        chain = reasoning_engine.explain_metric_change(
            metric=metric,
            from_value=from_val,
            to_value=to_val,
            period_from=period_from,
            period_to=period_to,
            context=context,
        )

        # Add KG context for any referenced entities
        kg_context = ""
        from app.services.knowledge_graph import knowledge_graph
        if knowledge_graph.is_built and chain.kg_entities_used:
            kg_parts = []
            for eid in chain.kg_entities_used[:5]:
                entity = knowledge_graph._entities.get(eid)
                if entity:
                    kg_parts.append(f"[{entity.label_en}]: {entity.description[:200]}")
            if kg_parts:
                kg_context = "\n\nKnowledge Base Context:\n" + "\n".join(kg_parts)

        # Add KG citation
        if tracker:
            tracker.add_knowledge_graph("reasoning_engine", ["financial_reasoning"])

        # If API available, enrich with LLM narrative
        structured_output = chain.narrative + kg_context
        if chain.factors:
            structured_output += "\n\nFactors:\n"
            for f in chain.factors[:3]:
                structured_output += f"• {f.factor}: {f.explanation}\n"
        if chain.recommendations:
            structured_output += "\n\nRecommendations:\n"
            for r in chain.recommendations[:3]:
                structured_output += f"→ {r}\n"

        try:
            system = self._system_prompt() + "\n\nProvide a concise, analytical explanation."
            messages = [{
                "role": "user",
                "content": (
                    f"Based on this structured causal analysis, provide a 3-4 paragraph expert financial commentary:\n\n"
                    f"{structured_output}\n\n"
                    f"Use exact numbers. Reference industry benchmarks. "
                    f"Explain the business implications for a Georgian petroleum distributor."
                )
            }]
            response = await self.call_llm(system=system, messages=messages, max_tokens=800,
                                           tool_name_hint="explain_metric_change")
            if hasattr(response, "content"):
                llm_narrative = "".join(b.text for b in response.content if hasattr(b, "text"))
                return f"{chain.narrative}\n\n{llm_narrative}\n\n{structured_output}"
        except Exception as e:
            logger.warning("LLM enrichment failed for explain_metric_change: %s", e)

        return structured_output

    async def _simulate_financial_scenario(
        self, params: Dict, db: AsyncSession, external_context: Dict[str, Any],
        tracker: Optional[CitationTracker] = None
    ) -> str:
        """Phase E: Simulate a financial scenario using FinancialReasoningEngine."""
        from app.services.financial_reasoning import reasoning_engine

        scenario_name = params.get("scenario_name", "Custom Scenario")
        changes = params.get("changes", {})
        base = params.get("base", {})

        # If no base provided, try to load from active dataset
        if not base:
            ds_id = await self._resolve_active_ds(db)
            if ds_id:
                from app.services.income_statement import build_income_statement
                rev_items = (await db.execute(
                    select(RevenueItem).where(RevenueItem.dataset_id == ds_id)
                )).scalars().all()
                cogs_items = (await db.execute(
                    select(COGSItem).where(COGSItem.dataset_id == ds_id)
                )).scalars().all()
                ga_items = (await db.execute(
                    select(GAExpenseItem).where(GAExpenseItem.dataset_id == ds_id)
                )).scalars().all()
                ds = (await db.execute(
                    select(Dataset).where(Dataset.id == ds_id)
                )).scalar_one_or_none()
                stmt = build_income_statement(rev_items, cogs_items, ga_items,
                                             ds.period if ds else "Unknown")
                base = {
                    "revenue": float(stmt.total_revenue),
                    "cogs": float(stmt.total_cogs),
                    "ga_expenses": float(stmt.ga_expenses),
                    "depreciation": float(stmt.total_depreciation),
                }

        if not base:
            return "No base case data available. Provide base financials or upload a dataset."

        result = reasoning_engine.simulate_scenario(scenario_name, base, changes)

        # Format output
        output = [
            f"## Scenario Analysis: {result.scenario_name}",
            "",
            "### Base Case vs Scenario",
            f"| Metric | Base | Scenario | Change |",
            f"|--------|------|----------|--------|",
            f"| Revenue | {_fgel(result.base_revenue)} | {_fgel(result.scenario_revenue)} | {_pct_str(result.revenue_change_pct)} |",
            f"| Gross Profit | {_fgel(result.base_gross_profit)} | {_fgel(result.scenario_gross_profit)} | {_pct_str(result.gross_profit_change_pct)} |",
            f"| EBITDA | {_fgel(result.base_ebitda)} | {_fgel(result.scenario_ebitda)} | {_pct_str(result.ebitda_change_pct)} |",
            f"| Net Profit | {_fgel(result.base_net_profit)} | {_fgel(result.scenario_net_profit)} | {_pct_str(result.net_profit_change_pct)} |",
            "",
            f"**Risk Level: {result.risk_level.upper()}**",
            "",
            result.narrative,
        ]
        return "\n".join(output)

    async def _reason_about_metric(self, params: Dict, db: AsyncSession, external_context: Dict[str, Any], tracker: Optional[CitationTracker] = None) -> str:
        """Build a reasoning chain about a specific metric.

        Called when the user asks "why" questions about financial metrics.
        """
        from app.services.income_statement import build_income_statement
        from app.services.narrative_engine import narrative_engine

        metric = params.get("metric", "")
        ds_id = await self._resolve_active_ds(db)
        if not ds_id:
            return "No active dataset. Upload financial data first."

        # Build the income statement
        rev = (await db.execute(select(RevenueItem).where(RevenueItem.dataset_id == ds_id))).scalars().all()
        cogs = (await db.execute(select(COGSItem).where(COGSItem.dataset_id == ds_id))).scalars().all()
        ga = (await db.execute(select(GAExpenseItem).where(GAExpenseItem.dataset_id == ds_id))).scalars().all()
        ds = (await db.execute(select(Dataset).where(Dataset.id == ds_id))).scalar_one_or_none()
        stmt = build_income_statement(rev, cogs, ga, ds.period if ds else "Unknown")
        stmt_dict = stmt.to_dict()

        # Track citations for underlying data items
        if tracker:
            period_str = ds.period if ds else ""
            source_file = ds.file_name if ds else ""
            for item in rev[:10]:
                tracker.add_db_entity(
                    "revenue",
                    entity_id=item.id or 0,
                    dataset_id=ds_id,
                    claim=f"{item.product or ''} net {_fgel(item.net or 0)}",
                    value=float(item.net or item.gross or 0),
                    period=period_str,
                    source_file=source_file,
                    source_sheet="Revenue Breakdown",
                )
            for item in cogs[:10]:
                tracker.add_db_entity(
                    "cogs",
                    entity_id=item.id or 0,
                    dataset_id=ds_id,
                    claim=f"COGS {item.product or ''} {_fgel(item.total_cogs or 0)}",
                    value=float(item.total_cogs or 0),
                    period=period_str,
                    source_file=source_file,
                    source_sheet="COGS Breakdown",
                )

        # Generate reasoning chain
        chain = ReasoningChain(question=f"Explain the {metric or 'financial performance'}")

        # Revenue analysis step
        chain.steps.append(ReasoningStep(
            observation=f"Total revenue: {_fgel(stmt.total_revenue)}",
            data_source="IncomeStatement.total_revenue",
            analysis=(
                f"Wholesale contributes {_fgel(stmt.revenue_wholesale_total)} "
                f"({stmt.revenue_wholesale_total / stmt.total_revenue * 100:.0f}% of total) "
                f"and retail contributes {_fgel(stmt.revenue_retail_total)} "
                f"({stmt.revenue_retail_total / stmt.total_revenue * 100:.0f}%)."
                if stmt.total_revenue else "No revenue data available."
            ),
            confidence=0.95,
        ))

        # Margin analysis step
        margin_rate = (stmt.total_gross_margin / stmt.total_revenue * 100) if stmt.total_revenue else 0
        chain.steps.append(ReasoningStep(
            observation=f"Gross margin: {_fgel(stmt.total_gross_margin)} ({margin_rate:.1f}%)",
            data_source="IncomeStatement.total_gross_margin",
            analysis=(
                f"Wholesale margin: {_fgel(stmt.margin_wholesale_total)}, "
                f"Retail margin: {_fgel(stmt.margin_retail_total)}. "
                + (
                    "Wholesale is negative, meaning wholesale products are sold below cost. "
                    "This is often a deliberate volume strategy in fuel distribution."
                    if stmt.margin_wholesale_total < 0
                    else "Both segments are margin-positive."
                )
            ),
            implications=(
                ["Cross-subsidy from retail to wholesale", "Volume-driven pricing strategy"]
                if stmt.margin_wholesale_total < 0
                else ["Healthy margin structure"]
            ),
            confidence=0.85,
        ))

        # EBITDA step
        ebitda_rate = (stmt.ebitda / stmt.total_revenue * 100) if stmt.total_revenue else 0
        chain.steps.append(ReasoningStep(
            observation=f"EBITDA: {_fgel(stmt.ebitda)} ({ebitda_rate:.1f}% margin)",
            data_source="IncomeStatement.ebitda",
            analysis=(
                f"After G&A expenses of {_fgel(stmt.ga_expenses)}, "
                f"EBITDA is {'positive, indicating operational profitability' if stmt.ebitda > 0 else 'negative, indicating the business is not covering its operating costs'}."
            ),
            confidence=0.9,
        ))

        chain.conclusion = (
            f"For {stmt.period}: Revenue {_fgel(stmt.total_revenue)}, "
            f"Gross margin {margin_rate:.1f}%, EBITDA {_fgel(stmt.ebitda)}, "
            f"Net profit {_fgel(stmt.net_profit)}."
        )
        chain.confidence = 0.85

        # Generate narrative section
        section = narrative_engine.generate_metric_explanation(
            metric or "gross_margin",
            getattr(stmt, metric, stmt.total_gross_margin),
            {"total_revenue": stmt.total_revenue},
        )

        return chain.to_text() + f"\n\n**Commentary:**\n{section.body}"

    async def _generate_narrative(self, params: Dict, db: AsyncSession, external_context: Dict[str, Any], tracker: Optional[CitationTracker] = None) -> str:
        """Generate a full narrative for the active dataset's income statement."""
        from app.services.income_statement import build_income_statement
        from app.services.narrative_engine import narrative_engine

        ds_id = await self._resolve_active_ds(db)
        if not ds_id:
            return "No active dataset."

        rev = (await db.execute(select(RevenueItem).where(RevenueItem.dataset_id == ds_id))).scalars().all()
        cogs = (await db.execute(select(COGSItem).where(COGSItem.dataset_id == ds_id))).scalars().all()
        ga = (await db.execute(select(GAExpenseItem).where(GAExpenseItem.dataset_id == ds_id))).scalars().all()
        ds = (await db.execute(select(Dataset).where(Dataset.id == ds_id))).scalar_one_or_none()

        stmt = build_income_statement(rev, cogs, ga, ds.period if ds else "")

        # Track citations for data used in narrative
        if tracker:
            period_str = ds.period if ds else ""
            source_file = ds.file_name if ds else ""
            for item in rev[:10]:
                tracker.add_db_entity(
                    "revenue",
                    entity_id=item.id or 0,
                    dataset_id=ds_id,
                    claim=f"{item.product or ''} net {_fgel(item.net or 0)}",
                    value=float(item.net or item.gross or 0),
                    period=period_str,
                    source_file=source_file,
                    source_sheet="Revenue Breakdown",
                )
            for item in cogs[:10]:
                tracker.add_db_entity(
                    "cogs",
                    entity_id=item.id or 0,
                    dataset_id=ds_id,
                    claim=f"COGS {item.product or ''} {_fgel(item.total_cogs or 0)}",
                    value=float(item.total_cogs or 0),
                    period=period_str,
                    source_file=source_file,
                    source_sheet="COGS Breakdown",
                )

        narrative = narrative_engine.generate_income_statement_narrative(
            stmt.to_dict(), period=ds.period if ds else ""
        )
        return narrative.to_text()

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _resolve_active_ds(self, db: AsyncSession) -> Optional[int]:
        result = await db.execute(select(Dataset.id).where(Dataset.is_active == True).limit(1))
        row = result.first()
        return row[0] if row else None

    async def _delegate_to_legacy(self, task: AgentTask, context: AgentContext) -> AgentResult:
        """Delegate to legacy agent for tools not yet fully migrated."""
        from app.agents.registry import registry
        legacy = registry.get("legacy")
        if legacy:
            return await legacy.execute(task, context)
        return self._error_result("Legacy agent not available")
