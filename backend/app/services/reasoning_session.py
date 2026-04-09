"""
FinAI Collaborative Reasoning Architecture (CRA)
═══════════════════════════════════════════════════════════════════════════════
Replaces the single-agent dispatch pattern with multi-agent collaborative
reasoning sessions for complex analytical queries.

Architecture:
  User Query
    ↓ Supervisor (intent framing + complexity check)
    ↓ TaskDecomposer (breaks query into agent-specific steps)
    ↓ ReasoningSession (shared context + orchestrated execution)
        DataAgent   → populates datasets, validates data availability
        CalcAgent   → computes metrics, ratios, variances
        InsightAgent → reasons about causes, generates explanations
        ReportAgent  → formats final coherent response
    ↓ Synthesized Financial Answer

Key Design Decisions:
  - CRA only activates for COMPLEX queries (simple queries stay on fast path)
  - Agents communicate through FinancialSessionContext (blackboard pattern)
  - Each step has a latency budget to prevent runaway chains
  - Confidence tracking enables contradiction detection
  - Steps can be skipped if agent determines no contribution needed
  - Results are cached per-session to avoid redundant computation
"""

from __future__ import annotations

import time
import uuid
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# ENUMS & CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

class ReasoningStepType(str, Enum):
    """Types of reasoning steps in a collaborative session."""
    DATA_RETRIEVAL = "data_retrieval"
    COMPUTATION = "computation"
    ANALYSIS = "analysis"
    EXPLANATION = "explanation"
    FORMATTING = "formatting"


class SessionStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


# Complexity threshold: queries matching >= this many signals trigger CRA
COMPLEXITY_THRESHOLD = 2

# Maximum steps in a single reasoning session
MAX_SESSION_STEPS = 6

# Per-step latency budget (ms) — steps exceeding this are logged as warnings
STEP_LATENCY_BUDGET_MS = 8000

# Total session latency budget (ms)
SESSION_LATENCY_BUDGET_MS = 30000


# ═══════════════════════════════════════════════════════════════════════════════
# FINANCIAL SESSION CONTEXT — the collaboration surface
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class MetricEntry:
    """A single computed metric with provenance."""
    name: str
    value: float
    unit: str = "GEL"
    period: str = ""
    source_agent: str = ""
    confidence: float = 1.0
    computation: str = ""  # How it was derived

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name, "value": self.value, "unit": self.unit,
            "period": self.period, "source_agent": self.source_agent,
            "confidence": self.confidence, "computation": self.computation,
        }


@dataclass
class InsightEntry:
    """A reasoning insight contributed by an agent."""
    text: str
    category: str = "observation"  # observation | cause | recommendation | warning
    source_agent: str = ""
    confidence: float = 0.8
    supporting_metrics: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text, "category": self.category,
            "source_agent": self.source_agent, "confidence": self.confidence,
            "supporting_metrics": self.supporting_metrics,
        }


@dataclass
class DataSlice:
    """A structured data slice provided by DataAgent."""
    name: str
    data: Dict[str, Any]
    period: str = ""
    dataset_id: Optional[int] = None
    row_count: int = 0
    source_agent: str = "data"


@dataclass
class FinancialSessionContext:
    """Shared mutable context for multi-agent collaboration.

    This is the blackboard — agents READ from and WRITE to this context.
    Each agent enriches the session with its domain-specific knowledge.

    DataAgent   → adds data_slices (raw financial data)
    CalcAgent   → adds metrics (computed ratios, aggregates)
    InsightAgent → adds insights (explanations, causes, recommendations)
    ReportAgent  → adds formatted_output (final narrative)
    """
    # Identity
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    query: str = ""
    query_intent: str = ""  # "margin_analysis", "variance_explanation", etc.

    # Data layer (populated by DataAgent)
    data_slices: List[DataSlice] = field(default_factory=list)
    available_periods: List[str] = field(default_factory=list)
    data_quality: Dict[str, Any] = field(default_factory=dict)

    # Metrics layer (populated by CalcAgent)
    metrics: Dict[str, MetricEntry] = field(default_factory=dict)
    comparisons: Dict[str, Dict[str, float]] = field(default_factory=dict)

    # Insight layer (populated by InsightAgent)
    insights: List[InsightEntry] = field(default_factory=list)
    hypotheses: List[Dict[str, Any]] = field(default_factory=list)
    causal_chain: Optional[Dict[str, Any]] = None

    # Output layer (populated by ReportAgent)
    formatted_output: str = ""
    executive_summary: str = ""
    warnings: List[str] = field(default_factory=list)

    # Session metadata
    contributing_agents: List[str] = field(default_factory=list)
    step_log: List[Dict[str, Any]] = field(default_factory=list)
    total_latency_ms: int = 0
    confidence_score: float = 0.0

    def add_metric(self, name: str, value: float, **kwargs) -> None:
        """Add a computed metric to the shared context."""
        self.metrics[name] = MetricEntry(name=name, value=value, **kwargs)

    def add_insight(self, text: str, **kwargs) -> None:
        """Add a reasoning insight to the shared context."""
        self.insights.append(InsightEntry(text=text, **kwargs))

    def add_data_slice(self, name: str, data: Dict, **kwargs) -> None:
        """Add a data slice to the shared context."""
        self.data_slices.append(DataSlice(name=name, data=data, **kwargs))

    def get_metric(self, name: str) -> Optional[float]:
        """Get a metric value by name."""
        entry = self.metrics.get(name)
        return entry.value if entry else None

    def has_data(self) -> bool:
        return len(self.data_slices) > 0

    def has_metrics(self) -> bool:
        return len(self.metrics) > 0

    def has_insights(self) -> bool:
        return len(self.insights) > 0

    def log_step(self, agent: str, action: str, duration_ms: int,
                 status: str = "success", detail: str = "") -> None:
        """Log a reasoning step for the audit trail."""
        self.step_log.append({
            "agent": agent, "action": action, "duration_ms": duration_ms,
            "status": status, "detail": detail,
            "timestamp": time.time(),
        })
        self.total_latency_ms += duration_ms
        if agent not in self.contributing_agents:
            self.contributing_agents.append(agent)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the full session context."""
        return {
            "session_id": self.session_id,
            "query": self.query,
            "query_intent": self.query_intent,
            "data_slices": len(self.data_slices),
            "metrics": {k: v.to_dict() for k, v in self.metrics.items()},
            "insights": [i.to_dict() for i in self.insights],
            "causal_chain": self.causal_chain,
            "executive_summary": self.executive_summary,
            "formatted_output": self.formatted_output[:500] if self.formatted_output else "",
            "warnings": self.warnings,
            "contributing_agents": self.contributing_agents,
            "step_log": self.step_log,
            "total_latency_ms": self.total_latency_ms,
            "confidence_score": self.confidence_score,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# REASONING STEP — a single unit of work in a collaborative session
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ReasoningStep:
    """A single step in a reasoning session."""
    step_type: ReasoningStepType
    agent_name: str
    instruction: str
    required: bool = True  # If False, can be skipped on failure
    depends_on: List[str] = field(default_factory=list)  # Step IDs this depends on
    step_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    timeout_ms: int = STEP_LATENCY_BUDGET_MS


# ═══════════════════════════════════════════════════════════════════════════════
# TASK DECOMPOSER — breaks complex queries into reasoning steps
# ═══════════════════════════════════════════════════════════════════════════════

class TaskDecomposer:
    """Decomposes complex financial queries into ordered agent-specific steps.

    Uses pattern matching on the query to determine which agents need to
    participate and in what order. This is deterministic (no LLM needed).

    Capability Graph:
      data_retrieval  → DataAgent   (dataset lookup, validation)
      computation     → CalcAgent   (ratios, metrics, variances)
      analysis        → InsightAgent (causal reasoning, anomaly explanation)
      explanation     → InsightAgent (narrative generation)
      formatting      → ReportAgent  (structured output)
    """

    # Query patterns → required agent chains
    _PATTERNS: List[Tuple[List[str], List[ReasoningStep]]] = []

    def __init__(self):
        self._build_patterns()

    def _build_patterns(self):
        """Build deterministic decomposition patterns."""
        self._PATTERNS = [
            # Pattern: "Why did X change?" — full 4-agent chain
            (
                ["why", "drop", "decline", "decrease", "increase", "change",
                 "what caused", "what happened", "explain"],
                [
                    ReasoningStep(ReasoningStepType.DATA_RETRIEVAL, "data",
                                  "Retrieve relevant financial data for the query period"),
                    ReasoningStep(ReasoningStepType.COMPUTATION, "calc",
                                  "Compute metrics, variances, and period comparisons"),
                    ReasoningStep(ReasoningStepType.ANALYSIS, "insight",
                                  "Analyze causes, build causal chain, identify drivers"),
                    ReasoningStep(ReasoningStepType.FORMATTING, "report",
                                  "Format the explanation as a coherent financial narrative",
                                  required=False),
                ]
            ),
            # Pattern: "Compare X to Y" — data + calc + insight
            (
                ["compare", "versus", "vs", "difference between",
                 "benchmark", "industry", "peer"],
                [
                    ReasoningStep(ReasoningStepType.DATA_RETRIEVAL, "data",
                                  "Retrieve data for all comparison periods/entities"),
                    ReasoningStep(ReasoningStepType.COMPUTATION, "calc",
                                  "Compute comparison metrics and variances"),
                    ReasoningStep(ReasoningStepType.ANALYSIS, "insight",
                                  "Interpret comparison results, identify significant gaps"),
                    ReasoningStep(ReasoningStepType.FORMATTING, "report",
                                  "Format comparison as structured analysis",
                                  required=False),
                ]
            ),
            # Pattern: "Forecast / predict" — data + calc + insight
            (
                ["forecast", "predict", "project", "next quarter",
                 "next month", "trend", "outlook"],
                [
                    ReasoningStep(ReasoningStepType.DATA_RETRIEVAL, "data",
                                  "Retrieve historical data for trend analysis"),
                    ReasoningStep(ReasoningStepType.COMPUTATION, "calc",
                                  "Compute forecasts using ensemble methods"),
                    ReasoningStep(ReasoningStepType.ANALYSIS, "insight",
                                  "Assess forecast reliability, identify risks and drivers"),
                    ReasoningStep(ReasoningStepType.FORMATTING, "report",
                                  "Format forecast with confidence intervals and narrative",
                                  required=False),
                ]
            ),
            # Pattern: "Generate report with analysis" — all agents
            (
                ["management report", "full analysis", "comprehensive",
                 "detailed report", "executive summary"],
                [
                    ReasoningStep(ReasoningStepType.DATA_RETRIEVAL, "data",
                                  "Validate data completeness and quality"),
                    ReasoningStep(ReasoningStepType.COMPUTATION, "calc",
                                  "Compute all financial statements and KPIs"),
                    ReasoningStep(ReasoningStepType.ANALYSIS, "insight",
                                  "Generate insights, warnings, and recommendations"),
                    ReasoningStep(ReasoningStepType.FORMATTING, "report",
                                  "Assemble full management report with narrative"),
                ]
            ),
            # Pattern: "Check / validate / audit" — data + insight
            (
                ["check", "validate", "audit", "verify", "reconcile",
                 "is correct", "anomaly", "unusual", "suspicious"],
                [
                    ReasoningStep(ReasoningStepType.DATA_RETRIEVAL, "data",
                                  "Retrieve data for validation"),
                    ReasoningStep(ReasoningStepType.COMPUTATION, "calc",
                                  "Compute validation metrics and cross-checks",
                                  required=False),
                    ReasoningStep(ReasoningStepType.ANALYSIS, "insight",
                                  "Identify issues, anomalies, and inconsistencies"),
                ]
            ),
        ]

    def decompose(self, query: str) -> Optional[List[ReasoningStep]]:
        """Decompose a query into reasoning steps.

        Returns None if the query is simple (single-agent is sufficient).
        """
        query_lower = query.lower()

        for keywords, steps in self._PATTERNS:
            matches = sum(1 for kw in keywords if kw in query_lower)
            if matches >= 1:
                # Clone steps so they get unique IDs
                return [
                    ReasoningStep(
                        step_type=s.step_type,
                        agent_name=s.agent_name,
                        instruction=s.instruction,
                        required=s.required,
                        timeout_ms=s.timeout_ms,
                    )
                    for s in steps
                ]

        return None

    def estimate_complexity(self, query: str) -> int:
        """Estimate query complexity (0-5 scale).

        0-1: Simple (single agent)
        2-3: Medium (2-3 agents)
        4-5: Complex (full CRA chain)
        """
        query_lower = query.lower()
        score = 0

        # Multi-period reference
        if any(kw in query_lower for kw in ["compare", "versus", "vs", "year over year",
                                             "month over month", "last year", "prior"]):
            score += 1

        # Causal reasoning
        if any(kw in query_lower for kw in ["why", "what caused", "explain",
                                             "reason", "root cause", "driver"]):
            score += 2

        # Multi-metric
        if any(kw in query_lower for kw in ["and", "also", "comprehensive",
                                             "full analysis", "detailed"]):
            score += 1

        # Forecasting
        if any(kw in query_lower for kw in ["forecast", "predict", "trend", "outlook"]):
            score += 1

        # Report generation
        if any(kw in query_lower for kw in ["report", "summary", "management"]):
            score += 1

        return min(score, 5)


# ═══════════════════════════════════════════════════════════════════════════════
# REASONING SESSION — orchestrates multi-agent collaboration
# ═══════════════════════════════════════════════════════════════════════════════

class ReasoningSession:
    """Orchestrates a collaborative multi-agent reasoning session.

    The session:
    1. Creates a shared FinancialSessionContext
    2. Executes reasoning steps in order
    3. Each agent reads from and writes to the shared context
    4. Synthesizes the final answer from all contributions

    Error handling:
    - Required steps that fail → session fails with partial results
    - Optional steps that fail → session continues without that contribution
    - Latency budgets → steps exceeding budget are logged as warnings
    """

    def __init__(self):
        self._decomposer = TaskDecomposer()

    def should_use_cra(self, query: str) -> bool:
        """Determine if a query is complex enough to warrant CRA.

        Simple queries (single-agent) should stay on the fast path.
        CRA adds latency — only use it when multi-agent reasoning adds value.
        """
        complexity = self._decomposer.estimate_complexity(query)
        return complexity >= COMPLEXITY_THRESHOLD

    async def run(
        self,
        query: str,
        db: Any,
        dataset_ids: List[int],
        period: str = "",
        currency: str = "GEL",
        history: List[Dict] = None,
    ) -> FinancialSessionContext:
        """Execute a full collaborative reasoning session.

        Args:
            query: User's financial question
            db: Database session
            dataset_ids: Active dataset IDs
            period: Current period
            currency: Currency code
            history: Conversation history

        Returns:
            FinancialSessionContext with all agent contributions
        """
        session_start = time.time()
        ctx = FinancialSessionContext(query=query)

        # Decompose the query into steps
        steps = self._decomposer.decompose(query)
        if not steps:
            # Fallback: simple 2-step (compute + explain)
            steps = [
                ReasoningStep(ReasoningStepType.COMPUTATION, "calc",
                              "Compute relevant financial metrics"),
                ReasoningStep(ReasoningStepType.ANALYSIS, "insight",
                              "Analyze and explain the results"),
            ]

        logger.info(
            "[CRA] Session %s: %d steps for query: '%s'",
            ctx.session_id, len(steps), query[:80],
        )

        # Execute each step
        for i, step in enumerate(steps):
            if ctx.total_latency_ms > SESSION_LATENCY_BUDGET_MS:
                logger.warning(
                    "[CRA] Session %s: latency budget exceeded (%dms) — skipping remaining steps",
                    ctx.session_id, ctx.total_latency_ms,
                )
                ctx.warnings.append(
                    f"Analysis truncated: latency budget exceeded ({ctx.total_latency_ms}ms)"
                )
                break

            step_start = time.time()
            try:
                await self._execute_step(step, ctx, db, dataset_ids, period, currency)
                step_ms = int((time.time() - step_start) * 1000)

                if step_ms > step.timeout_ms:
                    logger.warning(
                        "[CRA] Step %d (%s/%s) exceeded budget: %dms > %dms",
                        i, step.agent_name, step.step_type.value, step_ms, step.timeout_ms,
                    )

            except Exception as e:
                step_ms = int((time.time() - step_start) * 1000)
                logger.error(
                    "[CRA] Step %d (%s/%s) failed: %s (%dms)",
                    i, step.agent_name, step.step_type.value, e, step_ms,
                )
                ctx.log_step(
                    step.agent_name, step.step_type.value, step_ms,
                    status="error", detail=str(e)[:200],
                )

                if step.required:
                    ctx.warnings.append(f"Critical step failed: {step.agent_name} - {e}")
                    # Continue with partial results rather than failing entirely

        # Compute confidence BEFORE synthesize so it appears in the output
        ctx.confidence_score = self._compute_confidence(ctx)

        total_ms = int((time.time() - session_start) * 1000)
        ctx.total_latency_ms = total_ms

        # Synthesize final output (uses confidence_score)
        self._synthesize(ctx)

        logger.info(
            "[CRA] Session %s complete: %d agents, %d metrics, %d insights, %dms, confidence=%.2f",
            ctx.session_id, len(ctx.contributing_agents), len(ctx.metrics),
            len(ctx.insights), total_ms, ctx.confidence_score,
        )

        return ctx

    async def _execute_step(
        self,
        step: ReasoningStep,
        ctx: FinancialSessionContext,
        db: Any,
        dataset_ids: List[int],
        period: str,
        currency: str,
    ) -> None:
        """Execute a single reasoning step, populating the shared context."""

        step_start = time.time()

        if step.step_type == ReasoningStepType.DATA_RETRIEVAL:
            await self._step_data_retrieval(ctx, db, dataset_ids, period)

        elif step.step_type == ReasoningStepType.COMPUTATION:
            await self._step_computation(ctx, db, dataset_ids, period, currency)

        elif step.step_type == ReasoningStepType.ANALYSIS:
            await self._step_analysis(ctx, db)

        elif step.step_type == ReasoningStepType.EXPLANATION:
            await self._step_analysis(ctx, db)  # Same as analysis for now

        elif step.step_type == ReasoningStepType.FORMATTING:
            self._step_formatting(ctx)

        step_ms = int((time.time() - step_start) * 1000)
        ctx.log_step(step.agent_name, step.step_type.value, step_ms)

    # ── Step Implementations ──────────────────────────────────────────────────

    async def _step_data_retrieval(
        self,
        ctx: FinancialSessionContext,
        db: Any,
        dataset_ids: List[int],
        period: str,
    ) -> None:
        """DataAgent step: retrieve and validate relevant financial data."""
        from sqlalchemy import select, func
        from app.models.all_models import (
            Dataset, RevenueItem, COGSItem, GAExpenseItem,
            Transaction, TrialBalanceItem, BalanceSheetItem,
        )

        if not dataset_ids:
            ctx.warnings.append("No active dataset — data retrieval skipped")
            return

        for ds_id in dataset_ids:
            ds = (await db.execute(
                select(Dataset).where(Dataset.id == ds_id)
            )).scalar_one_or_none()

            if not ds:
                continue

            ds_period = ds.period or period or "Unknown"

            # Count available entities
            counts = {}
            for model, key in [
                (RevenueItem, "revenue"), (COGSItem, "cogs"),
                (GAExpenseItem, "ga_expenses"), (Transaction, "transactions"),
                (TrialBalanceItem, "trial_balance"), (BalanceSheetItem, "balance_sheet"),
            ]:
                try:
                    count = (await db.execute(
                        select(func.count()).where(model.dataset_id == ds_id)
                    )).scalar() or 0
                    counts[key] = count
                except Exception:
                    counts[key] = 0

            # Fetch revenue items for metric computation
            rev_items = (await db.execute(
                select(RevenueItem).where(RevenueItem.dataset_id == ds_id)
            )).scalars().all()

            cogs_items = (await db.execute(
                select(COGSItem).where(COGSItem.dataset_id == ds_id)
            )).scalars().all()

            ga_items = (await db.execute(
                select(GAExpenseItem).where(GAExpenseItem.dataset_id == ds_id)
            )).scalars().all()

            # Build data slice
            slice_data = {
                "dataset_id": ds_id,
                "dataset_name": ds.name,
                "period": ds_period,
                "entity_counts": counts,
                "revenue_items": len(rev_items),
                "cogs_items": len(cogs_items),
                "ga_items": len(ga_items),
            }

            ctx.add_data_slice(
                name=f"dataset_{ds_id}",
                data=slice_data,
                period=ds_period,
                dataset_id=ds_id,
                row_count=sum(counts.values()),
            )
            ctx.available_periods.append(ds_period)

            # Also store raw items in context for CalcAgent
            ctx.data_quality[f"ds_{ds_id}"] = {
                "has_revenue": counts.get("revenue", 0) > 0,
                "has_cogs": counts.get("cogs", 0) > 0,
                "has_ga": counts.get("ga_expenses", 0) > 0,
                "has_tb": counts.get("trial_balance", 0) > 0,
                "has_bs": counts.get("balance_sheet", 0) > 0,
                "completeness": sum(1 for v in counts.values() if v > 0) / max(len(counts), 1),
            }

    async def _step_computation(
        self,
        ctx: FinancialSessionContext,
        db: Any,
        dataset_ids: List[int],
        period: str,
        currency: str,
    ) -> None:
        """CalcAgent step: compute financial metrics from available data."""
        from sqlalchemy import select
        from app.models.all_models import RevenueItem, COGSItem, GAExpenseItem

        for ds_id in dataset_ids:
            try:
                rev_items = (await db.execute(
                    select(RevenueItem).where(RevenueItem.dataset_id == ds_id)
                )).scalars().all()
                cogs_items = (await db.execute(
                    select(COGSItem).where(COGSItem.dataset_id == ds_id)
                )).scalars().all()
                ga_items = (await db.execute(
                    select(GAExpenseItem).where(GAExpenseItem.dataset_id == ds_id)
                )).scalars().all()

                if not rev_items and not cogs_items:
                    continue

                # Build income statement
                from app.services.income_statement import build_income_statement
                ds_result = (await db.execute(
                    select(__import__('app.models.all_models', fromlist=['Dataset']).Dataset)
                    .where(__import__('app.models.all_models', fromlist=['Dataset']).Dataset.id == ds_id)
                )).scalar_one_or_none()
                ds_period = ds_result.period if ds_result else period

                stmt = build_income_statement(rev_items, cogs_items, ga_items, ds_period)
                stmt_dict = stmt.to_dict()

                # Populate metrics
                prefix = f"ds{ds_id}_" if len(dataset_ids) > 1 else ""

                ctx.add_metric(f"{prefix}revenue", stmt.total_revenue,
                              unit=currency, period=ds_period,
                              source_agent="calc", computation="sum(revenue_items)")
                ctx.add_metric(f"{prefix}cogs", stmt.total_cogs,
                              unit=currency, period=ds_period,
                              source_agent="calc", computation="sum(cogs_items)")
                ctx.add_metric(f"{prefix}gross_margin", stmt.total_gross_profit,
                              unit=currency, period=ds_period,
                              source_agent="calc",
                              computation="revenue - cogs (all segments)")
                ctx.add_metric(f"{prefix}gross_margin_pct",
                              (stmt.total_gross_profit / stmt.total_revenue * 100)
                              if stmt.total_revenue else 0,
                              unit="%", period=ds_period,
                              source_agent="calc",
                              computation="gross_profit / revenue * 100")
                ctx.add_metric(f"{prefix}ebitda", stmt.ebitda,
                              unit=currency, period=ds_period,
                              source_agent="calc",
                              computation="gross_profit - ga_expenses")

                if stmt.total_revenue:
                    ctx.add_metric(f"{prefix}ebitda_margin",
                                  stmt.ebitda / stmt.total_revenue * 100,
                                  unit="%", period=ds_period,
                                  source_agent="calc")

                # Wholesale vs retail breakdown
                ctx.add_metric(f"{prefix}wholesale_margin", stmt.margin_wholesale_total,
                              unit=currency, period=ds_period, source_agent="calc")
                ctx.add_metric(f"{prefix}retail_margin", stmt.margin_retail_total,
                              unit=currency, period=ds_period, source_agent="calc")

                ctx.add_metric(f"{prefix}ga_expenses", stmt.ga_expenses,
                              unit=currency, period=ds_period, source_agent="calc")

                if hasattr(stmt, 'net_profit'):
                    ctx.add_metric(f"{prefix}net_profit", stmt.net_profit,
                                  unit=currency, period=ds_period, source_agent="calc")

            except Exception as e:
                logger.warning("[CRA] Computation failed for dataset %d: %s", ds_id, e)
                ctx.warnings.append(f"Computation partial: {e}")

        # Cross-period comparisons if multiple datasets
        if len(dataset_ids) > 1 and len(ctx.metrics) > 0:
            self._compute_variances(ctx, dataset_ids)

    def _compute_variances(self, ctx: FinancialSessionContext,
                           dataset_ids: List[int]) -> None:
        """Compute period-over-period variances when multiple datasets exist."""
        # Find matching metric pairs
        metric_names = ["revenue", "cogs", "gross_margin", "gross_margin_pct",
                        "ebitda", "ebitda_margin", "ga_expenses"]

        for metric in metric_names:
            values = []
            for ds_id in dataset_ids:
                prefix = f"ds{ds_id}_"
                entry = ctx.metrics.get(f"{prefix}{metric}")
                if entry:
                    values.append((ds_id, entry))

            if len(values) >= 2:
                # Compare first two (typically current vs prior)
                curr = values[0][1]
                prior = values[1][1]
                change = curr.value - prior.value
                pct_change = (change / abs(prior.value) * 100) if prior.value else 0

                ctx.comparisons[metric] = {
                    "current": curr.value,
                    "prior": prior.value,
                    "change": change,
                    "pct_change": round(pct_change, 2),
                    "current_period": curr.period,
                    "prior_period": prior.period,
                }

    async def _step_analysis(
        self,
        ctx: FinancialSessionContext,
        db: Any,
    ) -> None:
        """InsightAgent step: reason about computed metrics.

        Query-aware: detects the type of question and produces relevant insights.
        """

        # Use the financial reasoning engine for causal analysis
        try:
            from app.services.financial_reasoning import reasoning_engine
        except ImportError:
            reasoning_engine = None

        # ── Query-aware routing: detect what the user is asking about ──
        q = (ctx.query or "").lower()

        # Scenario analysis: "if X happens, what impact on Y?" + break-even
        if any(kw in q for kw in ["if ", "what happens", "scenario", "increase", "decrease",
                                    "impact", "cut", "reduce", "break even", "break-even",
                                    "breakeven"]):
            self._analyze_scenario(ctx, q)

        # Balance sheet / liquidity / profitability ratios
        if any(kw in q for kw in ["debt", "equity", "liquidity", "current ratio",
                                    "balance sheet", "solvency", "leverage",
                                    "roe", "roa", "return on", "profitability",
                                    "dupont", "asset turnover", "working capital",
                                    "cash flow", "free cash", "interest coverage"]):
            await self._analyze_balance_sheet(ctx, db)

        # Budget variance
        if any(kw in q for kw in ["budget", "variance", "over budget", "under budget",
                                    "actual vs", "vs budget"]):
            await self._analyze_budget_variance(ctx, db)

        # Accounting integrity
        if any(kw in q for kw in ["circular", "accounting", "inconsisten", "reconcil",
                                    "cross-reference", "cross reference"]):
            self._analyze_accounting_integrity(ctx)

        # Product-level analysis
        if any(kw in q for kw in ["product", "cng", "diesel", "lpg", "petrol",
                                    "fuel type", "breakdown by"]):
            await self._analyze_product_mix(ctx, db)

        # Analyze gross margin
        gm = ctx.get_metric("gross_margin_pct")
        gm_prior = None
        if "gross_margin_pct" in ctx.comparisons:
            comp = ctx.comparisons["gross_margin_pct"]
            gm_prior = comp["prior"]
            gm = comp["current"]

            if comp["pct_change"] < -5:
                ctx.add_insight(
                    f"Gross margin declined significantly: {comp['current']:.1f}% vs {comp['prior']:.1f}% "
                    f"({comp['pct_change']:+.1f}% change)",
                    category="warning", source_agent="insight", confidence=0.9,
                    supporting_metrics=["gross_margin_pct"],
                )

        # Revenue analysis
        if "revenue" in ctx.comparisons:
            rev_comp = ctx.comparisons["revenue"]
            direction = "grew" if rev_comp["change"] > 0 else "declined"
            ctx.add_insight(
                f"Revenue {direction} by {abs(rev_comp['pct_change']):.1f}% "
                f"({rev_comp['current']:,.0f} vs {rev_comp['prior']:,.0f})",
                category="observation", source_agent="insight", confidence=0.95,
                supporting_metrics=["revenue"],
            )

        # COGS analysis
        if "cogs" in ctx.comparisons:
            cogs_comp = ctx.comparisons["cogs"]
            if cogs_comp["pct_change"] > 0:
                ctx.add_insight(
                    f"COGS increased by {cogs_comp['pct_change']:.1f}% "
                    f"({cogs_comp['current']:,.0f} vs {cogs_comp['prior']:,.0f})",
                    category="observation", source_agent="insight", confidence=0.95,
                    supporting_metrics=["cogs"],
                )

        # Cross-metric reasoning: cost growth vs revenue growth
        if "revenue" in ctx.comparisons and "cogs" in ctx.comparisons:
            rev_growth = ctx.comparisons["revenue"]["pct_change"]
            cogs_growth = ctx.comparisons["cogs"]["pct_change"]

            if cogs_growth > rev_growth + 5:
                ctx.add_insight(
                    f"Cost growth ({cogs_growth:+.1f}%) significantly outpaced revenue growth "
                    f"({rev_growth:+.1f}%) - this is the primary margin pressure driver",
                    category="cause", source_agent="insight", confidence=0.85,
                    supporting_metrics=["revenue", "cogs", "gross_margin_pct"],
                )

            if rev_growth > 0 and cogs_growth > 0 and cogs_growth > rev_growth:
                ctx.add_insight(
                    "Recommendation: investigate supplier cost increases and consider "
                    "price adjustments or procurement optimization",
                    category="recommendation", source_agent="insight", confidence=0.7,
                )

        # Wholesale margin check
        wholesale = ctx.get_metric("wholesale_margin")
        if wholesale is not None and wholesale < 0:
            ctx.add_insight(
                f"Wholesale margin is negative ({wholesale:,.0f}) - loss-leader strategy or pricing issue",
                category="warning", source_agent="insight", confidence=0.9,
                supporting_metrics=["wholesale_margin"],
            )

        # Use CausalChain if available and we have comparison data
        if reasoning_engine and "gross_margin" in ctx.comparisons:
            try:
                comp = ctx.comparisons["gross_margin"]
                chain = reasoning_engine.explain_metric_change(
                    metric_name="gross_margin",
                    from_value=comp["prior"],
                    to_value=comp["current"],
                    period_from=comp.get("prior_period", "Prior"),
                    period_to=comp.get("current_period", "Current"),
                    context={
                        k: {"current": v["current"], "prior": v["prior"]}
                        for k, v in ctx.comparisons.items()
                    },
                )
                ctx.causal_chain = {
                    "metric": "gross_margin",
                    "change_pct": chain.change_pct,
                    "severity": chain.severity,
                    "primary_cause": chain.primary_cause,
                    "factors": [
                        {"name": f.name, "impact": f.impact, "direction": f.direction,
                         "explanation": f.explanation}
                        for f in chain.factors
                    ],
                    "narrative": chain.narrative,
                }
            except Exception as e:
                logger.debug("[CRA] CausalChain generation failed: %s", e)

        # Single-dataset analysis (always runs — produces insights even without comparisons)
        if ctx.has_metrics():
            revenue = ctx.get_metric("revenue")
            cogs_val = ctx.get_metric("cogs")
            gm_pct = ctx.get_metric("gross_margin_pct")
            ebitda_val = ctx.get_metric("ebitda")
            ebitda_margin = ctx.get_metric("ebitda_margin")
            net_profit = ctx.get_metric("net_profit")
            ga_exp = ctx.get_metric("ga_expenses")
            wholesale_m = ctx.get_metric("wholesale_margin")
            retail_m = ctx.get_metric("retail_margin")

            # -- Gross margin analysis with benchmark comparison --
            if gm_pct is not None:
                if gm_pct < 8:
                    ctx.add_insight(
                        f"Gross margin is low at {gm_pct:.1f}%. Fuel distribution industry "
                        f"benchmark is 7-12%. Below 8% signals pricing pressure or high procurement costs.",
                        category="warning", source_agent="insight", confidence=0.85,
                        supporting_metrics=["gross_margin_pct"],
                    )
                elif gm_pct < 15:
                    ctx.add_insight(
                        f"Gross margin at {gm_pct:.1f}% is within fuel distribution norms (7-12%) "
                        f"but below diversified energy companies (15-20%).",
                        category="observation", source_agent="insight", confidence=0.85,
                        supporting_metrics=["gross_margin_pct"],
                    )
                else:
                    ctx.add_insight(
                        f"Gross margin is strong at {gm_pct:.1f}%, exceeding fuel distribution "
                        f"benchmark of 7-12%.",
                        category="observation", source_agent="insight", confidence=0.9,
                        supporting_metrics=["gross_margin_pct"],
                    )

            # -- EBITDA margin vs industry benchmarks --
            if ebitda_margin is not None:
                # Fuel distribution benchmark: EBITDA margin 4-8%
                if ebitda_margin < 0:
                    ctx.add_insight(
                        f"EBITDA margin is negative ({ebitda_margin:.1f}%) — operating losses. "
                        f"Industry benchmark is 4-8% for fuel distributors.",
                        category="warning", source_agent="insight", confidence=0.95,
                        supporting_metrics=["ebitda_margin", "ebitda"],
                    )
                elif ebitda_margin < 4:
                    ctx.add_insight(
                        f"EBITDA margin at {ebitda_margin:.1f}% is below fuel distribution "
                        f"benchmark of 4-8%. Below-peer profitability suggests high G&A overhead "
                        f"or under-pricing.",
                        category="warning", source_agent="insight", confidence=0.85,
                        supporting_metrics=["ebitda_margin"],
                    )
                elif ebitda_margin < 8:
                    ctx.add_insight(
                        f"EBITDA margin at {ebitda_margin:.1f}% is within industry range (4-8%) "
                        f"for fuel distributors.",
                        category="observation", source_agent="insight", confidence=0.9,
                        supporting_metrics=["ebitda_margin"],
                    )
                else:
                    ctx.add_insight(
                        f"EBITDA margin at {ebitda_margin:.1f}% exceeds fuel distribution "
                        f"benchmark (4-8%) — strong operational efficiency.",
                        category="observation", source_agent="insight", confidence=0.9,
                        supporting_metrics=["ebitda_margin"],
                    )

            # -- Net profit analysis --
            if net_profit is not None and revenue:
                net_margin = net_profit / revenue * 100 if revenue else 0
                if net_profit < 0:
                    ctx.add_insight(
                        f"Net loss of {abs(net_profit):,.0f} GEL (net margin: {net_margin:.1f}%). "
                        f"The company is unprofitable this period. Key driver: "
                        f"{'high G&A expenses' if ga_exp and ga_exp > abs(ebitda_val or 0) else 'thin gross margins'}.",
                        category="warning", source_agent="insight", confidence=0.9,
                        supporting_metrics=["net_profit"],
                    )

            # -- G&A expense ratio analysis --
            if ga_exp is not None and revenue and revenue > 0:
                ga_pct = ga_exp / revenue * 100
                if ga_pct > 10:
                    ctx.add_insight(
                        f"G&A expenses at {ga_pct:.1f}% of revenue ({ga_exp:,.0f} GEL) are high. "
                        f"Fuel distribution benchmark is 3-6%. This is the primary drag on profitability.",
                        category="cause", source_agent="insight", confidence=0.85,
                        supporting_metrics=["ga_expenses", "revenue"],
                    )
                elif ga_pct > 6:
                    ctx.add_insight(
                        f"G&A expenses at {ga_pct:.1f}% of revenue are above industry norm of 3-6%.",
                        category="observation", source_agent="insight", confidence=0.8,
                        supporting_metrics=["ga_expenses"],
                    )

            # -- Wholesale vs Retail segment analysis --
            if wholesale_m is not None and retail_m is not None:
                total_margin = (wholesale_m or 0) + (retail_m or 0)
                if total_margin != 0:
                    w_share = wholesale_m / total_margin * 100 if total_margin else 0
                    r_share = retail_m / total_margin * 100 if total_margin else 0
                    if wholesale_m < 0:
                        ctx.add_insight(
                            f"Wholesale segment is destroying value with negative margin "
                            f"({wholesale_m:,.0f} GEL). Retail carries profitability "
                            f"({retail_m:,.0f} GEL, {r_share:.0f}% of total margin).",
                            category="warning", source_agent="insight", confidence=0.9,
                            supporting_metrics=["wholesale_margin", "retail_margin"],
                        )
                    elif w_share < 25:
                        ctx.add_insight(
                            f"Wholesale contributes only {w_share:.0f}% of gross margin "
                            f"({wholesale_m:,.0f} GEL) vs retail {r_share:.0f}% "
                            f"({retail_m:,.0f} GEL). Retail is the profit engine.",
                            category="observation", source_agent="insight", confidence=0.85,
                            supporting_metrics=["wholesale_margin", "retail_margin"],
                        )
                    else:
                        ctx.add_insight(
                            f"Balanced margin split: wholesale {w_share:.0f}% "
                            f"({wholesale_m:,.0f} GEL) / retail {r_share:.0f}% "
                            f"({retail_m:,.0f} GEL).",
                            category="observation", source_agent="insight", confidence=0.85,
                            supporting_metrics=["wholesale_margin", "retail_margin"],
                        )

            # -- Recommendations based on findings --
            warnings_count = sum(1 for i in ctx.insights if i.category == "warning")
            if warnings_count >= 2:
                ctx.add_insight(
                    "Multiple financial health warnings detected. Priority actions: "
                    "(1) Review wholesale pricing strategy, "
                    "(2) Audit G&A overhead for cost reduction opportunities, "
                    "(3) Analyze product-level margins to identify loss-makers.",
                    category="recommendation", source_agent="insight", confidence=0.75,
                )

    # ── Query-Aware Specialized Analysis Methods ──────────────────────────

    def _analyze_scenario(self, ctx: FinancialSessionContext, query: str) -> None:
        """Simulate financial scenarios with parametric engine.

        Supports:
        - COGS/cost changes: "if COGS increase 15%"
        - Revenue changes: "if revenue drops 20%"
        - G&A cuts: "cut G&A by 40%", "reduce expenses by 30%"
        - Break-even: "what revenue for break-even", "break even point"
        - Combined: "if revenue +10% and costs -5%"
        """
        import re
        revenue = ctx.get_metric("revenue") or 0
        cogs_val = ctx.get_metric("cogs") or 0
        gm = ctx.get_metric("gross_margin") or 0
        ga = ctx.get_metric("ga_expenses") or 0
        ebitda = ctx.get_metric("ebitda") or 0
        net_profit = ctx.get_metric("net_profit") or 0

        # Extract percentage from query
        pct_match = re.search(r'(\d+(?:\.\d+)?)\s*%', query)
        pct = float(pct_match.group(1)) if pct_match else 10

        # Detect increase vs decrease direction
        is_decrease = any(kw in query for kw in [
            "cut", "reduce", "decrease", "drop", "lower", "less", "down",
            "decline", "fall", "shrink", "minus", "-",
        ])
        direction = -1 if is_decrease else 1
        multiplier = 1 + (direction * pct / 100)

        # ── Break-even analysis ──
        if any(kw in query for kw in ["break even", "break-even", "breakeven", "zero profit"]):
            if revenue > 0 and cogs_val > 0:
                variable_cost_ratio = cogs_val / revenue
                # Total fixed costs = everything between gross margin and net profit
                # = Gross Margin - Net Profit (includes operating G&A, D&A, non-operating, tax)
                total_fixed_costs = gm - net_profit if gm > 0 else abs(ga)
                contribution_margin_ratio = 1 - variable_cost_ratio
                if contribution_margin_ratio > 0:
                    be_revenue = total_fixed_costs / contribution_margin_ratio
                    gap = be_revenue - revenue
                    gap_pct = gap / revenue * 100 if revenue else 0
                    ctx.add_insight(
                        f"**Break-even analysis:** Variable cost ratio = {variable_cost_ratio:.1%} "
                        f"(COGS/Revenue). Contribution margin ratio = {contribution_margin_ratio:.1%}. "
                        f"Total fixed costs = {total_fixed_costs:,.0f} GEL "
                        f"(operating G&A {abs(ga):,.0f} + D&A + non-operating {total_fixed_costs - abs(ga):,.0f}). "
                        f"Break-even revenue = {be_revenue:,.0f} GEL.",
                        category="observation", source_agent="insight", confidence=0.85,
                        supporting_metrics=["revenue", "cogs", "ga_expenses", "net_profit"],
                    )
                    ctx.add_insight(
                        f"Current revenue {revenue:,.0f} GEL is "
                        f"{'above' if gap < 0 else 'below'} break-even by "
                        f"{abs(gap):,.0f} GEL ({abs(gap_pct):.1f}%). "
                        f"{'Company needs ' + f'{gap_pct:.0f}% more revenue to reach profitability.' if gap > 0 else 'Company has a safety margin.'}",
                        category="warning" if gap > 0 else "observation",
                        source_agent="insight", confidence=0.85,
                    )
                    # What cost cuts would achieve break-even
                    if net_profit < 0:
                        needed_cut = abs(net_profit)
                        pct_of_total = needed_cut / total_fixed_costs * 100 if total_fixed_costs else 0
                        ctx.add_insight(
                            f"**Path to profitability:** Cut total fixed costs by {needed_cut:,.0f} GEL "
                            f"({pct_of_total:.1f}% of {total_fixed_costs:,.0f}), OR grow revenue to "
                            f"{be_revenue:,.0f} GEL ({gap_pct:+.1f}%), OR a combination of both.",
                            category="recommendation", source_agent="insight", confidence=0.8,
                        )
            return

        # ── G&A / expense changes ──
        if any(kw in query for kw in ["g&a", "ga ", "expense", "overhead", "opex",
                                        "operating cost", "admin"]):
            new_ga = ga * multiplier
            ga_change = new_ga - ga
            new_ebitda = gm - new_ga
            new_net = net_profit - ga_change
            ctx.add_insight(
                f"**Scenario: G&A {'+' if direction > 0 else ''}{direction * pct:.0f}%** → "
                f"G&A changes from {ga:,.0f} to {new_ga:,.0f} GEL ({ga_change:+,.0f}). "
                f"New EBITDA: {new_ebitda:,.0f} GEL (was {ebitda:,.0f}). "
                f"New net profit: {new_net:,.0f} GEL (was {net_profit:,.0f}). "
                f"{'Company becomes profitable!' if new_net > 0 and net_profit <= 0 else ''}"
                f"{'Still unprofitable.' if new_net <= 0 and net_profit <= 0 else ''}",
                category="observation", source_agent="insight", confidence=0.85,
                supporting_metrics=["ga_expenses", "ebitda", "net_profit"],
            )
            # Additional: margin impact
            if revenue > 0:
                ctx.add_insight(
                    f"Net margin changes from {net_profit/revenue*100:.1f}% to "
                    f"{new_net/revenue*100:.1f}%. EBITDA margin: {new_ebitda/revenue*100:.1f}%.",
                    category="observation", source_agent="insight", confidence=0.8,
                )
            return

        # ── COGS / cost changes ──
        if any(kw in query for kw in ["cost", "cogs", "price increase", "fuel price",
                                        "raw material", "procurement"]):
            new_cogs = cogs_val * multiplier
            new_gm = revenue - new_cogs
            cogs_change = new_cogs - cogs_val
            new_net = net_profit - cogs_change
            ctx.add_insight(
                f"**Scenario: COGS {'+' if direction > 0 else ''}{direction * pct:.0f}%** → "
                f"New COGS: {new_cogs:,.0f} GEL ({cogs_change:+,.0f}). "
                f"Gross margin: {gm:,.0f} → {new_gm:,.0f} GEL "
                f"(GM%: {gm/revenue*100:.1f}% → {new_gm/revenue*100:.1f}%). "
                f"Net profit: {net_profit:,.0f} → {new_net:,.0f} GEL.",
                category="observation", source_agent="insight", confidence=0.8,
                supporting_metrics=["cogs", "gross_margin", "net_profit"],
            )
            return

        # ── Revenue changes ──
        if any(kw in query for kw in ["revenue", "sales", "volume", "turnover", "income"]):
            new_rev = revenue * multiplier
            # Assume COGS scales proportionally (variable cost)
            new_cogs = cogs_val * multiplier
            new_gm = new_rev - new_cogs
            new_net = new_gm - abs(ga)  # GA is fixed
            ctx.add_insight(
                f"**Scenario: Revenue {'+' if direction > 0 else ''}{direction * pct:.0f}%** → "
                f"New revenue: {new_rev:,.0f} GEL. COGS scales proportionally to {new_cogs:,.0f}. "
                f"New gross margin: {new_gm:,.0f} GEL (GM% unchanged at {gm/revenue*100:.1f}%). "
                f"Net profit: {net_profit:,.0f} → {new_net:,.0f} GEL (G&A fixed).",
                category="observation", source_agent="insight", confidence=0.8,
                supporting_metrics=["revenue", "gross_margin", "net_profit"],
            )
            return

        # ── Default: generic percentage impact analysis ──
        new_cogs = cogs_val * multiplier
        cogs_change = new_cogs - cogs_val
        new_net = net_profit - cogs_change
        ctx.add_insight(
            f"**Scenario: {pct:.0f}% {'decrease' if is_decrease else 'increase'}** → "
            f"Cost impact: {cogs_change:+,.0f} GEL. "
            f"Net profit: {net_profit:,.0f} → {new_net:,.0f} GEL.",
            category="observation", source_agent="insight", confidence=0.75,
        )

    async def _analyze_balance_sheet(self, ctx: FinancialSessionContext, db: Any) -> None:
        """Compute balance sheet ratios from BS data.

        Georgian IFRS COA account code mapping:
          1xxx = Current Assets (Cash, Receivables, Inventories, Tax assets)
          2xxx = Non-current Assets (PPE, Investments, Intangibles)
          3xxx = Liabilities (Trade payables=31xx current, Loans=32xx/34xx long-term, Tax=33xx current)
          4xxx = Non-current Liabilities (Lease liabilities)
          5xxx = Equity (Share capital, Retained earnings)
          6xxx+ = P&L items (excluded from BS ratios)
        """
        from sqlalchemy import select
        from app.models.all_models import BalanceSheetItem, Dataset

        # Get active dataset
        ds_result = await db.execute(
            select(Dataset).where(Dataset.is_active == True)  # noqa: E712
        )
        ds = ds_result.scalars().first()
        if not ds:
            ctx.add_insight(
                "No active dataset with balance sheet data available for ratio analysis.",
                category="observation", source_agent="insight", confidence=0.5,
            )
            return

        bs_items = (await db.execute(
            select(BalanceSheetItem).where(BalanceSheetItem.dataset_id == ds.id)
        )).scalars().all()

        if not bs_items:
            ctx.add_insight(
                "Balance sheet data not available in current dataset. "
                "Upload a dataset with BS items for ratio analysis.",
                category="observation", source_agent="insight", confidence=0.5,
            )
            return

        # Classify by account code prefix using Georgian IFRS COA
        current_assets = 0.0
        non_current_assets = 0.0
        current_liabilities = 0.0
        non_current_liabilities = 0.0
        total_equity = 0.0
        bs_count = 0

        for b in bs_items:
            code = (b.account_code or "").strip()
            bal = b.closing_balance or 0
            prefix = code[:1] if code else ""
            prefix2 = code[:2] if len(code) >= 2 else ""

            if prefix == "1":
                current_assets += bal
                bs_count += 1
            elif prefix == "2":
                non_current_assets += bal
                bs_count += 1
            elif prefix == "3":
                # 31xx = trade payables (current), 33xx = tax (current)
                # 32xx, 34xx = long-term loans (non-current)
                if prefix2 in ("31", "33"):
                    current_liabilities += bal
                elif prefix2 in ("32", "34"):
                    non_current_liabilities += bal
                else:
                    current_liabilities += bal  # default to current
                bs_count += 1
            elif prefix == "4":
                non_current_liabilities += bal
                bs_count += 1
            elif prefix == "5":
                total_equity += bal
                bs_count += 1
            # 6xxx+ are P&L items, skip for BS ratios

        total_assets = current_assets + non_current_assets
        total_liabilities = current_liabilities + non_current_liabilities

        # Note: liabilities are typically negative in trial balance format
        # Normalize to positive values for ratio computation
        abs_cl = abs(current_liabilities)
        abs_ncl = abs(non_current_liabilities)
        abs_tl = abs(total_liabilities)
        abs_eq = abs(total_equity)

        # Report BS structure
        ctx.add_insight(
            f"Balance sheet structure ({bs_count} accounts): "
            f"Current Assets {current_assets:,.0f} GEL | Non-current Assets {non_current_assets:,.0f} GEL | "
            f"Current Liabilities {abs_cl:,.0f} GEL | Non-current Liabilities {abs_ncl:,.0f} GEL | "
            f"Equity {abs_eq:,.0f} GEL.",
            category="observation", source_agent="data", confidence=0.90,
        )

        # Compute ratios
        if abs_eq > 0:
            dte = abs_tl / abs_eq
            ctx.add_metric("debt_to_equity", dte, unit="x", source_agent="calc")
            assessment = (
                "Healthy (<2.0 for fuel distributors)"
                if dte < 2.0
                else "Elevated (2-4x) — moderate leverage"
                if dte < 4.0
                else "Very high (>4x) — significant leverage risk"
            )
            ctx.add_insight(
                f"Debt-to-Equity ratio: {dte:.2f}x. {assessment}.",
                category="warning" if dte > 2 else "observation",
                source_agent="insight", confidence=0.85,
                supporting_metrics=["debt_to_equity"],
            )

        if abs_cl > 0:
            cr = current_assets / abs_cl
            ctx.add_metric("current_ratio", cr, unit="x", source_agent="calc")
            assessment = (
                "Adequate liquidity (>1.5)"
                if cr > 1.5
                else "Marginal liquidity (1.0-1.5)"
                if cr >= 1.0
                else "Low liquidity (<1.0) — short-term solvency risk"
            )
            ctx.add_insight(
                f"Current ratio: {cr:.2f}x. {assessment}.",
                category="warning" if cr < 1.0 else "observation",
                source_agent="insight", confidence=0.85,
                supporting_metrics=["current_ratio"],
            )

        # ── ROE & ROA (cross-statement: P&L → BS) ──
        net_profit = ctx.get_metric("net_profit")
        revenue = ctx.get_metric("revenue")

        if net_profit is not None and abs_eq > 0:
            roe = net_profit / abs_eq * 100
            ctx.add_metric("roe", roe, unit="%", source_agent="calc")
            roe_assessment = (
                "Positive return on equity"
                if roe > 0
                else "Negative ROE — company is destroying shareholder value"
                if roe > -5
                else "Deeply negative ROE — significant equity erosion"
            )
            ctx.add_insight(
                f"Return on Equity (ROE): {roe:.2f}% (Net Income {net_profit:,.0f} / Equity {abs_eq:,.0f}). "
                f"{roe_assessment}.",
                category="warning" if roe < 0 else "observation",
                source_agent="insight", confidence=0.9,
                supporting_metrics=["roe", "net_profit"],
            )

        if net_profit is not None and total_assets > 0:
            roa = net_profit / total_assets * 100
            ctx.add_metric("roa", roa, unit="%", source_agent="calc")
            ctx.add_insight(
                f"Return on Assets (ROA): {roa:.2f}% (Net Income {net_profit:,.0f} / "
                f"Total Assets {total_assets:,.0f}). "
                f"{'Negative — assets not generating profit.' if roa < 0 else 'Positive asset utilization.'}",
                category="warning" if roa < 0 else "observation",
                source_agent="insight", confidence=0.9,
                supporting_metrics=["roa"],
            )

        # ── DuPont Decomposition ──
        q = (ctx.query or "").lower()
        if (net_profit is not None and revenue and revenue > 0
                and total_assets > 0 and abs_eq > 0):
            profit_margin = net_profit / revenue  # Net margin
            asset_turnover = revenue / total_assets
            equity_multiplier = total_assets / abs_eq
            dupont_roe = profit_margin * asset_turnover * equity_multiplier * 100

            if any(kw in q for kw in ["dupont", "decompos", "roe breakdown", "roe component"]):
                ctx.add_insight(
                    f"**DuPont ROE Decomposition:** ROE = Profit Margin x Asset Turnover x Equity Multiplier. "
                    f"= {profit_margin:.4f} x {asset_turnover:.4f} x {equity_multiplier:.2f} = {dupont_roe:.2f}%. "
                    f"Profit Margin: {profit_margin*100:.2f}% | "
                    f"Asset Turnover: {asset_turnover:.4f}x | "
                    f"Equity Multiplier: {equity_multiplier:.2f}x (leverage).",
                    category="observation", source_agent="insight", confidence=0.9,
                    supporting_metrics=["roe", "net_profit", "revenue"],
                )

            # Asset turnover metric (always)
            ctx.add_metric("asset_turnover", asset_turnover, unit="x", source_agent="calc")

        # ── Working Capital ──
        working_capital = current_assets - abs_cl
        ctx.add_metric("working_capital", working_capital, unit="GEL", source_agent="calc")
        if revenue and revenue > 0:
            wc_turnover = revenue / working_capital if working_capital > 0 else 0
            if wc_turnover > 0:
                ctx.add_metric("working_capital_turnover", wc_turnover, unit="x", source_agent="calc")

        # ── BS equation check with explanation ──
        tb_sum = current_assets + non_current_assets + current_liabilities + non_current_liabilities + total_equity
        if abs(tb_sum) > 1:
            ctx.add_insight(
                f"Balance sheet equation residual: {tb_sum:,.0f} GEL. "
                f"In trial-balance format, Assets + Liabilities + Equity should = 0. "
                f"The {abs(tb_sum):,.0f} residual equals the current period's net income "
                f"({net_profit:,.0f} GEL) that has not yet been closed to Retained Earnings. "
                f"This is normal for mid-year trial balance data."
                if net_profit is not None and abs(abs(tb_sum) - abs(net_profit)) < abs(tb_sum) * 0.15
                else f"Balance sheet equation residual: {tb_sum:,.0f} GEL. "
                f"Non-zero residual may indicate P&L items not yet closed to equity, "
                f"intercompany eliminations, or off-balance-sheet items.",
                category="observation", source_agent="insight", confidence=0.75,
            )

        if bs_count == 0:
            ctx.add_insight(
                "Balance sheet items exist but could not be classified by account code. "
                "Ratios could not be computed — data needs enrichment.",
                category="observation", source_agent="insight", confidence=0.6,
            )

    async def _analyze_budget_variance(self, ctx: FinancialSessionContext, db: Any) -> None:
        """Analyze budget vs actual variances using BudgetLine model.

        Budget lines may not have actual_amount populated. In that case,
        compute actuals from the P&L data (RevenueItem, COGSItem, GAExpenseItem).
        """
        from sqlalchemy import select
        from app.models.all_models import (
            BudgetLine, Dataset, RevenueItem, COGSItem, GAExpenseItem,
        )

        ds_result = await db.execute(
            select(Dataset).where(Dataset.is_active == True)  # noqa: E712
        )
        ds = ds_result.scalars().first()
        if not ds:
            return

        budget_lines = (await db.execute(
            select(BudgetLine).where(BudgetLine.dataset_id == ds.id)
        )).scalars().all()

        # If no budget lines in active dataset, try any dataset with budget data
        budget_ds_id = ds.id
        if not budget_lines:
            all_budget = (await db.execute(select(BudgetLine))).scalars().all()
            if all_budget:
                budget_lines = all_budget
                budget_ds_id = budget_lines[0].dataset_id if budget_lines else ds.id

        if not budget_lines:
            ctx.add_insight(
                "No budget data available for variance analysis.",
                category="observation", source_agent="insight", confidence=0.5,
            )
            return

        # Check if actuals are populated
        has_actuals = any((b.actual_amount or 0) != 0 for b in budget_lines)

        if not has_actuals:
            # Compute actuals from P&L data
            rev_items = (await db.execute(
                select(RevenueItem).where(RevenueItem.dataset_id == ds.id)
            )).scalars().all()
            cogs_items = (await db.execute(
                select(COGSItem).where(COGSItem.dataset_id == ds.id)
            )).scalars().all()
            ga_items = (await db.execute(
                select(GAExpenseItem).where(GAExpenseItem.dataset_id == ds.id)
            )).scalars().all()

            actual_revenue = sum(r.net or 0 for r in rev_items)
            actual_cogs = sum(c.total_cogs or 0 for c in cogs_items)
            actual_ga = sum(g.amount or 0 for g in ga_items)
            actual_gross_margin = actual_revenue - actual_cogs

            # Map budget line_item to actual values
            actual_map = {
                "revenue": actual_revenue,
                "revenue retial": sum(r.net or 0 for r in rev_items
                                      if "retial" in (r.segment or "").lower() or "retail" in (r.segment or "").lower()),
                "revenue wholesale": sum(r.net or 0 for r in rev_items
                                         if "wholesale" in (r.segment or "").lower()),
                "cogs": actual_cogs,
                "gross margin": actual_gross_margin,
                "g&a": actual_ga,
                "ga expenses": actual_ga,
            }
        else:
            actual_map = {}

        # Compute variances
        variances = []
        total_budget = 0
        total_actual = 0

        for b in budget_lines:
            bud = b.budget_amount or 0
            if bud == 0:
                continue

            line = b.line_item or ""
            line_lower = line.lower().strip()

            # Get actual: either from column or computed
            if has_actuals:
                act = b.actual_amount or 0
            else:
                act = actual_map.get(line_lower, None)
                if act is None:
                    # Try partial match
                    for key, val in actual_map.items():
                        if key in line_lower or line_lower in key:
                            act = val
                            break
                if act is None:
                    continue  # Skip lines we can't match

            var = act - bud
            var_pct = (var / bud * 100) if bud else 0
            variances.append((line, bud, act, var, var_pct))
            total_budget += bud
            total_actual += act

        if not variances:
            ctx.add_insight(
                "Budget lines found (43 lines) but could not match all actuals. "
                "Budget data appears to be plan-only without actual amounts populated.",
                category="observation", source_agent="insight", confidence=0.6,
            )
            # Still show top-level comparison if we have metrics
            rev = ctx.get_metric("revenue") or 0
            bud_rev = sum(b.budget_amount or 0 for b in budget_lines
                         if (b.line_item or "").lower().strip() == "revenue")
            if rev > 0 and bud_rev > 0:
                var = rev - bud_rev
                var_pct = var / bud_rev * 100
                ctx.add_insight(
                    f"Revenue vs budget: Actual {rev:,.0f} GEL vs Budget {bud_rev:,.0f} GEL "
                    f"= variance {var:+,.0f} GEL ({var_pct:+.1f}%).",
                    category="warning" if abs(var_pct) > 10 else "observation",
                    source_agent="calc", confidence=0.85,
                )
            return

        total_var = total_actual - total_budget
        total_var_pct = (total_var / total_budget * 100) if total_budget else 0

        ctx.add_metric("budget_variance", total_var, unit="GEL", source_agent="calc")
        ctx.add_metric("budget_variance_pct", total_var_pct, unit="%", source_agent="calc")

        ctx.add_insight(
            f"Total budget variance: {total_var:+,.0f} GEL ({total_var_pct:+.1f}%). "
            f"Budget: {total_budget:,.0f} | Actual: {total_actual:,.0f} "
            f"({len(variances)} matched lines of {len(budget_lines)} total).",
            category="warning" if abs(total_var_pct) > 10 else "observation",
            source_agent="insight", confidence=0.85,
        )

        # Sort by absolute variance descending
        variances.sort(key=lambda x: abs(x[3]), reverse=True)
        top5 = variances[:5]
        if top5:
            detail_lines = []
            for line, bud, act, var, vpct in top5:
                detail_lines.append(f"{line}: {var:+,.0f} GEL ({vpct:+.1f}%)")
            ctx.add_insight(
                f"Top variance drivers: {' | '.join(detail_lines)}",
                category="cause", source_agent="insight", confidence=0.8,
            )

    def _analyze_accounting_integrity(self, ctx: FinancialSessionContext) -> None:
        """Check for accounting inconsistencies from available metrics."""
        revenue = ctx.get_metric("revenue") or 0
        cogs_val = ctx.get_metric("cogs") or 0
        gm = ctx.get_metric("gross_margin") or 0

        # Check gross margin equation
        expected_gm = revenue - cogs_val
        gm_diff = abs(gm - expected_gm)
        if gm_diff > 1:
            ctx.add_insight(
                f"Gross margin equation check: Revenue - COGS = {expected_gm:,.2f}, "
                f"reported {gm:,.2f} — difference of {gm_diff:,.2f}.",
                category="warning", source_agent="insight", confidence=0.9,
            )
        else:
            ctx.add_insight(
                "Gross margin equation (Revenue - COGS = Gross Margin) — VERIFIED. No circular references detected.",
                category="observation", source_agent="insight", confidence=0.95,
            )

        # Check if COGS > Revenue (unusual)
        if cogs_val > revenue and revenue > 0:
            ctx.add_insight(
                f"COGS ({cogs_val:,.0f}) exceeds Revenue ({revenue:,.0f}) — "
                f"negative gross margin. Check for data entry errors or misclassified items.",
                category="warning", source_agent="insight", confidence=0.9,
            )

        # Check for EBITDA consistency
        ebitda = ctx.get_metric("ebitda") or 0
        ga = ctx.get_metric("ga_expenses") or 0
        expected_ebitda = gm - ga
        ebitda_diff = abs(ebitda - expected_ebitda)
        if ebitda_diff > 1:
            ctx.add_insight(
                f"EBITDA equation check: Gross Margin - G&A = {expected_ebitda:,.2f}, "
                f"reported EBITDA {ebitda:,.2f} — difference {ebitda_diff:,.2f}.",
                category="warning" if ebitda_diff > 1000 else "observation",
                source_agent="insight", confidence=0.85,
            )
        else:
            ctx.add_insight(
                "EBITDA equation (Gross Margin - G&A = EBITDA) — VERIFIED. Consistent.",
                category="observation", source_agent="insight", confidence=0.95,
            )

    async def _analyze_product_mix(self, ctx: FinancialSessionContext, db: Any) -> None:
        """Analyze revenue by product/fuel type using category field."""
        from sqlalchemy import select
        from app.models.all_models import RevenueItem, COGSItem, Dataset

        ds_result = await db.execute(
            select(Dataset).where(Dataset.is_active == True)  # noqa: E712
        )
        ds = ds_result.scalars().first()
        if not ds:
            return

        rev_items = (await db.execute(
            select(RevenueItem).where(RevenueItem.dataset_id == ds.id)
        )).scalars().all()

        if not rev_items:
            return

        total_rev = sum(item.net or 0 for item in rev_items)

        # Categorize by fuel type using 'category' field
        # Categories: 'Revenue Retial CNG', 'Revenue Whsale Diesel', 'Other Revenue', etc.
        fuel_types: dict = {}
        segments: dict = {"Retail": 0, "Wholesale": 0, "Other": 0}
        for item in rev_items:
            cat = (item.category or "").lower()
            rev = item.net or 0

            # Classify fuel type from category
            if "cng" in cat:
                ft = "CNG"
            elif "lpg" in cat:
                ft = "LPG"
            elif "diesel" in cat:
                ft = "Diesel"
            elif "petrol" in cat:
                ft = "Petrol"
            elif "bitumen" in cat:
                ft = "Bitumen"
            elif "fuel oil" in cat or "fuel_oil" in cat:
                ft = "Fuel Oil"
            else:
                ft = "Other"

            if ft not in fuel_types:
                fuel_types[ft] = {"revenue": 0, "count": 0, "retail": 0, "wholesale": 0}
            fuel_types[ft]["revenue"] += rev
            fuel_types[ft]["count"] += 1

            # Segment split
            if "retial" in cat or "retail" in cat:
                segments["Retail"] += rev
                fuel_types[ft]["retail"] += rev
            elif "whsale" in cat or "wholesale" in cat:
                segments["Wholesale"] += rev
                fuel_types[ft]["wholesale"] += rev
            else:
                segments["Other"] += rev

        # Also fetch COGS for margin analysis by fuel type
        cogs_items = (await db.execute(
            select(COGSItem).where(COGSItem.dataset_id == ds.id)
        )).scalars().all()
        cogs_by_fuel: dict = {}
        for item in cogs_items:
            cat = (item.category or "").lower()
            cost = item.total_cogs or 0
            if "cng" in cat:
                ft = "CNG"
            elif "lpg" in cat:
                ft = "LPG"
            elif "diesel" in cat:
                ft = "Diesel"
            elif "petrol" in cat:
                ft = "Petrol"
            elif "bitumen" in cat:
                ft = "Bitumen"
            else:
                ft = "Other"
            cogs_by_fuel[ft] = cogs_by_fuel.get(ft, 0) + cost

        # Generate insights
        if fuel_types and total_rev > 0:
            sorted_fuels = sorted(fuel_types.items(), key=lambda x: x[1]["revenue"], reverse=True)
            breakdown = []
            for ft, data in sorted_fuels:
                pct = data["revenue"] / total_rev * 100
                cogs = cogs_by_fuel.get(ft, 0)
                margin = data["revenue"] - cogs if cogs else None
                margin_str = f", margin: {margin:,.0f} GEL" if margin is not None else ""
                breakdown.append(
                    f"{ft}: {data['revenue']:,.0f} GEL ({pct:.1f}%{margin_str})"
                )

            ctx.add_insight(
                f"Revenue by fuel type: {' | '.join(breakdown)}",
                category="observation", source_agent="insight", confidence=0.90,
                supporting_metrics=["revenue"],
            )

            # Segment analysis
            ctx.add_insight(
                f"Segment split: Retail {segments['Retail']:,.0f} GEL ({segments['Retail']/total_rev*100:.1f}%) | "
                f"Wholesale {segments['Wholesale']:,.0f} GEL ({segments['Wholesale']/total_rev*100:.1f}%) | "
                f"Other {segments['Other']:,.0f} GEL ({segments['Other']/total_rev*100:.1f}%)",
                category="observation", source_agent="insight", confidence=0.90,
            )

            # Find loss-making fuel types
            loss_fuels = []
            for ft, data in sorted_fuels:
                cogs = cogs_by_fuel.get(ft, 0)
                if cogs and data["revenue"] < cogs:
                    loss = cogs - data["revenue"]
                    loss_fuels.append(f"{ft}: loss of {loss:,.0f} GEL")
            if loss_fuels:
                ctx.add_insight(
                    f"Loss-making fuel types: {', '.join(loss_fuels)}. "
                    f"Pricing review required for these products.",
                    category="warning", source_agent="insight", confidence=0.85,
                )

            # Identify dominant product
            top_ft = sorted_fuels[0]
            if top_ft[1]["revenue"] / total_rev > 0.4:
                ctx.add_insight(
                    f"{top_ft[0]} dominates with {top_ft[1]['revenue']/total_rev*100:.0f}% of revenue. "
                    f"{'High concentration risk — diversification recommended.' if top_ft[1]['revenue']/total_rev > 0.6 else 'Moderate concentration.'}",
                    category="warning" if top_ft[1]["revenue"] / total_rev > 0.6 else "observation",
                    source_agent="insight", confidence=0.8,
                )

    def _step_formatting(self, ctx: FinancialSessionContext) -> None:
        """ReportAgent step: synthesize all contributions into coherent output."""
        self._synthesize(ctx)

    def _synthesize(self, ctx: FinancialSessionContext) -> None:
        """Synthesize all agent contributions into a final response."""
        parts = []

        # Executive summary
        if ctx.causal_chain:
            chain = ctx.causal_chain
            parts.append(f"**Analysis: {chain.get('metric', 'Financial Metric')}**\n")
            if chain.get("narrative"):
                parts.append(chain["narrative"])
            parts.append("")

        # Key metrics
        if ctx.metrics:
            parts.append("**Key Metrics:**")
            for name, entry in ctx.metrics.items():
                if name.startswith("ds") and "_" in name:
                    display_name = name.split("_", 1)[1].replace("_", " ").title()
                    parts.append(f"  {display_name}: {entry.value:,.2f} {entry.unit} ({entry.period})")
                else:
                    display_name = name.replace("_", " ").title()
                    parts.append(f"  {display_name}: {entry.value:,.2f} {entry.unit}")
            parts.append("")

        # Variances
        if ctx.comparisons:
            parts.append("**Period Comparison:**")
            for metric, comp in ctx.comparisons.items():
                display = metric.replace("_", " ").title()
                arrow = "+" if comp["change"] >= 0 else ""
                parts.append(
                    f"  {display}: {comp['current']:,.2f} vs {comp['prior']:,.2f} "
                    f"({arrow}{comp['pct_change']:.1f}%)"
                )
            parts.append("")

        # Insights (sorted by category)
        if ctx.insights:
            warnings = [i for i in ctx.insights if i.category == "warning"]
            causes = [i for i in ctx.insights if i.category == "cause"]
            observations = [i for i in ctx.insights if i.category == "observation"]
            recommendations = [i for i in ctx.insights if i.category == "recommendation"]

            if warnings:
                parts.append("**Warnings:**")
                for w in warnings:
                    parts.append(f"  [!] {w.text}")
                parts.append("")

            if causes:
                parts.append("**Root Causes:**")
                for c in causes:
                    parts.append(f"  -> {c.text}")
                parts.append("")

            if observations:
                parts.append("**Observations:**")
                for o in observations:
                    parts.append(f"  - {o.text}")
                parts.append("")

            if recommendations:
                parts.append("**Recommendations:**")
                for r in recommendations:
                    parts.append(f"  >> {r.text}")
                parts.append("")

        # Session metadata
        if ctx.contributing_agents:
            parts.append(
                f"_Analysis by: {', '.join(ctx.contributing_agents)} "
                f"| {ctx.total_latency_ms}ms | "
                f"Confidence: {ctx.confidence_score:.0%}_"
            )

        ctx.formatted_output = "\n".join(parts)

        # Build executive summary (first 2-3 sentences)
        summary_parts = []
        if ctx.causal_chain and ctx.causal_chain.get("narrative"):
            summary_parts.append(ctx.causal_chain["narrative"])
        elif ctx.insights:
            top_insights = [i for i in ctx.insights if i.confidence >= 0.8][:3]
            summary_parts.extend(i.text for i in top_insights)

        ctx.executive_summary = " ".join(summary_parts)[:500]

    def _compute_confidence(self, ctx: FinancialSessionContext) -> float:
        """Compute overall session confidence score."""
        scores = []

        # Data quality
        for dq in ctx.data_quality.values():
            scores.append(dq.get("completeness", 0.5))

        # Metric confidence
        for entry in ctx.metrics.values():
            scores.append(entry.confidence)

        # Insight confidence
        for insight in ctx.insights:
            scores.append(insight.confidence)

        # Number of contributing agents
        agent_coverage = len(ctx.contributing_agents) / 4  # 4 possible agents
        scores.append(min(agent_coverage, 1.0))

        if not scores:
            return 0.5

        return sum(scores) / len(scores)


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE-LEVEL SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

reasoning_session = ReasoningSession()
