"""
FinAI Agent Base — Protocol definitions for multi-agent orchestration.
══════════════════════════════════════════════════════════════════════════

Defines the communication protocol between agents:
- AgentTask: what needs to be done
- AgentContext: shared state across agents
- AgentResult: what an agent produced
- BaseAgent: abstract base for all agents
- AgentHealth: per-agent health tracking with circuit breaker

Architecture:
  Supervisor routes tasks → specialized agents execute → results flow back
  Each agent owns specific tools and has a focused system prompt.
  Agents communicate via structured AgentTask/AgentResult, not free text.

Resilience:
  - Retry with exponential backoff for transient API failures
  - Circuit breaker: auto-disable agent after N consecutive failures
  - Template fallback responses when Claude API is unavailable
  - Health monitoring with success/failure rate tracking
"""

from __future__ import annotations

import asyncio
import uuid
import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from anthropic import AsyncAnthropic
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# RESILIENCE CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

LLM_MAX_RETRIES = 3                    # Max retries for transient API failures
LLM_RETRY_BASE_DELAY = 1.0            # Base delay (seconds) for exponential backoff
LLM_RETRY_MAX_DELAY = 10.0            # Max delay cap (seconds)
CIRCUIT_BREAKER_THRESHOLD = 5         # Consecutive failures before circuit opens
CIRCUIT_BREAKER_RESET_SECONDS = 120   # Time before circuit resets to half-open


# ═══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES — Agent Communication Protocol
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class AgentTask:
    """A unit of work routed to an agent by the Supervisor."""

    task_type: str              # "ingest" | "calculate" | "analyze" | "report" | "chat"
    instruction: str            # Natural language or structured command
    parameters: Dict[str, Any] = field(default_factory=dict)
    source_agent: str = "supervisor"
    priority: int = 5           # 1 (low) — 10 (critical)
    parent_task_id: Optional[str] = None  # For sub-task chains
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def sub_task(self, task_type: str, instruction: str, **params) -> "AgentTask":
        """Create a child task linked to this one."""
        return AgentTask(
            task_type=task_type,
            instruction=instruction,
            parameters=params,
            source_agent=self.source_agent,
            priority=self.priority,
            parent_task_id=self.task_id,
        )


@dataclass
class AgentContext:
    """Shared state passed through an agent pipeline.

    Multiple datasets are supported: `dataset_ids` can hold several IDs
    for cross-period analysis, consolidation, or multi-file processing.
    """

    db: AsyncSession
    dataset_ids: List[int] = field(default_factory=list)
    period: str = ""
    currency: str = "GEL"
    user_message: str = ""
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    accumulated_results: Dict[str, Any] = field(default_factory=dict)
    ws: Optional[Any] = None  # WebSocket for streaming (if available)

    @property
    def primary_dataset_id(self) -> Optional[int]:
        """First (active) dataset, for backward-compat with single-DS code."""
        return self.dataset_ids[0] if self.dataset_ids else None

    def with_result(self, key: str, value: Any) -> "AgentContext":
        """Return a copy of this context with an additional accumulated result."""
        new_results = {**self.accumulated_results, key: value}
        return AgentContext(
            db=self.db,
            dataset_ids=list(self.dataset_ids),
            period=self.period,
            currency=self.currency,
            user_message=self.user_message,
            conversation_history=list(self.conversation_history),
            accumulated_results=new_results,
            ws=self.ws,
        )


@dataclass
class AuditEntry:
    """Single audit log entry for agent activity tracking."""

    agent_name: str
    action: str
    input_summary: str = ""
    output_summary: str = ""
    tokens_used: int = 0
    duration_ms: int = 0
    status: str = "success"
    timestamp: float = field(default_factory=time.time)


@dataclass
class AgentHealth:
    """Per-agent health tracking for circuit breaker and monitoring."""
    total_calls: int = 0
    success_count: int = 0
    error_count: int = 0
    consecutive_failures: int = 0
    last_error: str = ""
    last_error_time: float = 0.0
    last_success_time: float = 0.0
    total_latency_ms: int = 0
    circuit_open: bool = False       # True = agent is disabled
    circuit_open_since: float = 0.0  # When circuit was opened

    @property
    def success_rate(self) -> float:
        return self.success_count / self.total_calls if self.total_calls > 0 else 1.0

    @property
    def avg_latency_ms(self) -> float:
        return self.total_latency_ms / self.total_calls if self.total_calls > 0 else 0.0

    @property
    def is_healthy(self) -> bool:
        """Check if agent is healthy (circuit closed or reset timeout passed)."""
        if not self.circuit_open:
            return True
        # Check if reset timeout has passed (half-open)
        elapsed = time.time() - self.circuit_open_since
        if elapsed >= CIRCUIT_BREAKER_RESET_SECONDS:
            return True  # Allow a trial call
        return False

    def record_success(self, latency_ms: int) -> None:
        self.total_calls += 1
        self.success_count += 1
        self.consecutive_failures = 0
        self.last_success_time = time.time()
        self.total_latency_ms += latency_ms
        # Reset circuit if it was half-open and succeeded
        if self.circuit_open:
            self.circuit_open = False
            logger.info("Circuit breaker CLOSED (agent recovered)")

    def record_failure(self, error: str, latency_ms: int = 0) -> None:
        self.total_calls += 1
        self.error_count += 1
        self.consecutive_failures += 1
        self.last_error = error[:200]
        self.last_error_time = time.time()
        self.total_latency_ms += latency_ms
        # Open circuit breaker after threshold
        if self.consecutive_failures >= CIRCUIT_BREAKER_THRESHOLD and not self.circuit_open:
            self.circuit_open = True
            self.circuit_open_since = time.time()
            logger.warning(
                "Circuit breaker OPEN after %d consecutive failures: %s",
                self.consecutive_failures, error[:100],
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_calls": self.total_calls,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "success_rate": round(self.success_rate, 3),
            "avg_latency_ms": round(self.avg_latency_ms, 1),
            "consecutive_failures": self.consecutive_failures,
            "circuit_open": self.circuit_open,
            "last_error": self.last_error,
            "is_healthy": self.is_healthy,
        }


@dataclass
class AgentResult:
    """Output from an agent execution.

    Fields:
    - data: structured output (dicts, lists, numbers)
    - narrative: natural-language summary for the user
    - citations: source provenance for every figure the AI references.
      Each entry: {ref, claim, value, source_type, dataset_id, entity_id,
                   source_file, source_sheet, source_row, account_code,
                   period, confidence, display_label}
    - sub_tasks: if the agent needs to delegate work to other agents
    - navigation: optional UI page to navigate to
    - chart: optional chart JSON for inline rendering
    - audit_log: tracking entries for compliance
    """

    agent_name: str
    status: str = "success"         # "success" | "partial" | "error" | "needs_input"
    data: Dict[str, Any] = field(default_factory=dict)
    narrative: str = ""
    citations: List[Dict[str, Any]] = field(default_factory=list)
    sub_tasks: List[AgentTask] = field(default_factory=list)
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    navigation: Optional[str] = None      # e.g. "pl", "bs"
    chart: Optional[Dict[str, Any]] = None
    audit_log: List[AuditEntry] = field(default_factory=list)
    error_message: str = ""

    @property
    def is_success(self) -> bool:
        return self.status == "success"

    def add_audit(self, action: str, **kwargs) -> None:
        self.audit_log.append(AuditEntry(
            agent_name=self.agent_name,
            action=action,
            **kwargs,
        ))


# ── Response wrapper classes for cache/Ollama hits ────────────────────────────

class _CachedResponse:
    """Mimics Anthropic response object for cached results."""

    def __init__(self, text: str):
        self.stop_reason = "end_turn"
        self.content = [_TextBlock(text)]
        self.usage = _Usage(0, 0)


class _OllamaResponse:
    """Mimics Anthropic response object for Ollama results."""

    def __init__(self, text: str):
        self.stop_reason = "end_turn"
        self.content = [_TextBlock(text)]
        self.usage = _Usage(0, 0)


class _Gemma4Response:
    """Mimics Anthropic response object for Gemma 4 results."""

    def __init__(self, text: str):
        self.stop_reason = "end_turn"
        self.content = [_TextBlock(text)]
        self.usage = _Usage(0, 0)


class _TextBlock:
    """Mimics Anthropic text content block."""

    def __init__(self, text: str):
        self.type = "text"
        self.text = text


class _Usage:
    """Mimics Anthropic usage object."""

    def __init__(self, input_tokens: int, output_tokens: int):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


# ═══════════════════════════════════════════════════════════════════════════════
# BASE AGENT — Abstract class all agents inherit from
# ═══════════════════════════════════════════════════════════════════════════════

class BaseAgent(ABC):
    """Abstract base for all FinAI agents.

    Each agent must define:
    - name: unique identifier ("data", "calc", "insight", "report")
    - capabilities: list of task_types it can handle
    - tools: Anthropic tool definitions it owns
    - execute(): main logic

    Built-in resilience:
    - call_llm() retries with exponential backoff on transient errors
    - Health tracking with circuit breaker pattern
    - safe_execute() wraps execute() with error handling + health recording
    """

    name: str = "base"
    description: str = "Base agent"
    capabilities: List[str] = []
    tools: List[dict] = []

    def __init__(self):
        self._client: Optional[AsyncAnthropic] = None
        self.health = AgentHealth()

    @property
    def client(self) -> AsyncAnthropic:
        """Lazy-init Anthropic client (shared across calls)."""
        if self._client is None:
            from app.config import settings
            self._client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        return self._client

    # ── Abstract interface ──────────────────────────────────────────────────

    @abstractmethod
    async def execute(self, task: AgentTask, context: AgentContext) -> AgentResult:
        """Execute a task and return structured result.

        Implementations should:
        1. Validate the task matches their capabilities
        2. Build a focused system prompt (NOT the full 8K monolith)
        3. Call tools or LLM as needed
        4. Return AgentResult with data + narrative + audit log
        """
        ...

    # ── Resilient execution wrapper ──────────────────────────────────────

    async def safe_execute(self, task: AgentTask, context: AgentContext) -> AgentResult:
        """Execute with health tracking and circuit breaker.

        Wraps execute() with:
        - Circuit breaker check (refuse if circuit is open)
        - Latency measurement
        - Success/failure recording for health stats
        - Structured error result on unhandled exceptions
        """
        # Circuit breaker: refuse if agent is unhealthy
        if not self.health.is_healthy:
            logger.warning(
                "[%s] Circuit breaker OPEN — refusing task %s",
                self.name, task.task_type,
            )
            return self._error_result(
                f"Agent '{self.name}' is temporarily unavailable "
                f"(circuit breaker open after {self.health.consecutive_failures} failures). "
                f"Will retry automatically in {CIRCUIT_BREAKER_RESET_SECONDS}s."
            )

        start = time.time()
        try:
            result = await self.execute(task, context)
            latency = int((time.time() - start) * 1000)

            if result.status == "error":
                self.health.record_failure(result.error_message, latency)
            else:
                self.health.record_success(latency)

            return result

        except Exception as e:
            latency = int((time.time() - start) * 1000)
            self.health.record_failure(str(e), latency)
            logger.error(
                "[%s] Unhandled exception in execute: %s", self.name, e,
                exc_info=True,
            )
            return self._error_result(f"Agent '{self.name}' error: {str(e)}")

    # ── Shared LLM helper with retry ──────────────────────────────────────

    async def call_llm(
        self,
        system: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[dict]] = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        cache_key: Optional[str] = None,
        tool_name_hint: str = "",
    ) -> Any:
        """Call LLM with retry, exponential backoff, multi-LLM fallback, and caching.

        Five-tier intelligence stack:
          Tier 1: ResponseCache — instant, free (for repeated identical queries)
          Tier 2: Gemma 4 31B IT via NVIDIA API — primary, Georgian-capable
          Tier 3: Claude API — cloud, best quality, with retry + backoff
          Tier 4: Ollama/Nemotron — offline resilience or cloud deep reasoning
          Tier 5: Template responses — handled by subclass _api_down_result()

        Retry logic (Tier 2):
        - Retries on: rate limits (429), server errors (5xx), connection errors
        - Does NOT retry on: auth errors (401), bad request (400), validation
        - Exponential backoff: 1s, 2s, 4s (capped at 10s)

        Args:
            system: System prompt
            messages: Conversation messages
            tools: Tool definitions (optional)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            cache_key: Optional cache key; if None, no caching. Use response_cache.make_key()
            tool_name_hint: Tool name for cache TTL lookup and logging

        Returns the raw Anthropic message response (Tier 2) or a mock-like object (Tier 3).
        """
        from app.config import settings

        _t0 = time.time()
        
        try:
            from app.services.language_context import get_language
            lang = get_language()
            if lang == "ka":
                system += "\n\nCRITICAL INSTRUCTION: You MUST translate ALL generated content, labels, narrative, and output text to Georgian strictly. Ensure JSON keys remain in English but all textual values must be in Georgian."
        except Exception:
            pass

        # ── Tier 1: Response Cache ────────────────────────────────────────────
        if cache_key:
            try:
                from app.services.response_cache import response_cache
                cached = response_cache.get(cache_key)
                if cached:
                    # Return a cache-hit wrapper that mimics Anthropic response format
                    logger.debug("[%s] LLM cache HIT (key=%s...)", self.name, cache_key[:12])
                    try:
                        from app.services.telemetry import telemetry
                        telemetry.record_agent_call(self.name, "call_llm",
                            duration_ms=int((time.time()-_t0)*1000), status="cache_hit",
                            tool_name=tool_name_hint)
                    except Exception:
                        pass
                    return _CachedResponse(cached)
            except ImportError:
                pass

        # ── Tier 2: Gemma 4 via NVIDIA API (primary, Georgian-capable) ────────
        try:
            from app.services.local_llm import local_llm
            gemma4_text = await local_llm._try_gemma4(
                system=system, messages=messages, max_tokens=max_tokens,
            )
            if gemma4_text:
                logger.info("[%s] Gemma 4 primary LLM succeeded (%d chars)", self.name, len(gemma4_text))

                # Store in cache
                if cache_key:
                    try:
                        from app.services.response_cache import response_cache
                        response_cache.store(cache_key, gemma4_text, tool_name=tool_name_hint)
                    except Exception:
                        pass

                # Telemetry
                try:
                    from app.services.telemetry import telemetry
                    telemetry.record_agent_call(self.name, "call_llm",
                        duration_ms=int((time.time()-_t0)*1000),
                        status="gemma4", tool_name=tool_name_hint)
                except Exception:
                    pass

                return _Gemma4Response(gemma4_text)
        except Exception as gemma4_err:
            logger.debug("[%s] Gemma 4 unavailable: %s", self.name, gemma4_err)

        kwargs = dict(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
            temperature=temperature,
        )
        if tools:
            kwargs["tools"] = tools

        # ── Tier 3: Claude API with retry ─────────────────────────────────────
        last_error = None
        for attempt in range(LLM_MAX_RETRIES + 1):
            start = time.time()
            try:
                response = await self.client.messages.create(**kwargs)

                elapsed_ms = int((time.time() - start) * 1000)
                input_tokens = getattr(response.usage, "input_tokens", 0)
                output_tokens = getattr(response.usage, "output_tokens", 0)

                if attempt > 0:
                    logger.info(
                        "[%s] LLM call succeeded on retry %d: %d+%d tokens, %dms",
                        self.name, attempt, input_tokens, output_tokens, elapsed_ms,
                    )
                else:
                    logger.info(
                        "[%s] LLM call: %d input + %d output tokens, %dms",
                        self.name, input_tokens, output_tokens, elapsed_ms,
                    )

                # Store in cache if key provided
                if cache_key:
                    try:
                        from app.services.response_cache import response_cache
                        text = ""
                        for block in response.content:
                            if hasattr(block, "text"):
                                text += block.text
                        if text:
                            response_cache.store(cache_key, text, tool_name=tool_name_hint)
                    except Exception:
                        pass

                # Telemetry: Claude API success
                try:
                    from app.services.telemetry import telemetry
                    telemetry.record_agent_call(
                        self.name, "call_llm",
                        duration_ms=elapsed_ms,
                        tokens_in=input_tokens,
                        tokens_out=output_tokens,
                        status="success",
                        tool_name=tool_name_hint,
                    )
                except Exception:
                    pass

                return response

            except Exception as e:
                elapsed_ms = int((time.time() - start) * 1000)
                last_error = e
                error_str = str(e).lower()

                # Determine if error is retryable
                is_retryable = any(kw in error_str for kw in [
                    "rate_limit", "overloaded", "529",
                    "timeout", "connection", "server_error",
                    "500", "502", "503", "504",
                ])

                # Also check for specific Anthropic exceptions
                error_type = type(e).__name__
                if error_type in ("RateLimitError", "InternalServerError",
                                  "APIConnectionError", "APITimeoutError"):
                    is_retryable = True

                if not is_retryable or attempt >= LLM_MAX_RETRIES:
                    logger.error(
                        "[%s] LLM call failed (attempt %d/%d, %dms): %s",
                        self.name, attempt + 1, LLM_MAX_RETRIES + 1,
                        elapsed_ms, e,
                    )
                    # Don't raise yet — try Ollama fallback
                    break

                # Exponential backoff
                delay = min(
                    LLM_RETRY_BASE_DELAY * (2 ** attempt),
                    LLM_RETRY_MAX_DELAY,
                )
                logger.warning(
                    "[%s] LLM call failed (attempt %d/%d): %s. Retrying in %.1fs...",
                    self.name, attempt + 1, LLM_MAX_RETRIES + 1,
                    error_type, delay,
                )
                await asyncio.sleep(delay)

        # ── Tier 4: Ollama/Nemotron Fallback ──────────────────────────────────
        # Try Ollama even for tool-based calls (it will produce text-only response)
        if last_error is not None:
            try:
                from app.services.local_llm import local_llm
                if await local_llm.is_available():
                    logger.info("[%s] Claude API failed — trying Ollama local model", self.name)

                    # Select complexity based on max_tokens
                    complexity = "capable" if max_tokens > 2048 else "balanced" if max_tokens > 512 else "fast"

                    ollama_text = await local_llm.chat(
                        system=system,
                        messages=messages,
                        complexity=complexity,
                        max_tokens=min(max_tokens, 2048),
                    )

                    if ollama_text:
                        logger.info("[%s] Ollama fallback succeeded (%d chars)", self.name, len(ollama_text))
                        try:
                            from app.services.telemetry import telemetry
                            telemetry.record_agent_call(self.name, "call_llm",
                                duration_ms=int((time.time()-_t0)*1000),
                                status="ollama", tool_name=tool_name_hint)
                        except Exception:
                            pass
                        return _OllamaResponse(ollama_text)
            except Exception as ollama_err:
                logger.warning("[%s] Ollama fallback failed: %s", self.name, ollama_err)

        # ── Tier 5: Raise original error ──────────────────────────────────────
        # Subclasses handle this with _api_down_result() and template responses
        if last_error:
            raise last_error

        # Should not reach here
        raise RuntimeError(f"[{self.name}] LLM call failed with unknown error")

    # ── Utility helpers ─────────────────────────────────────────────────────

    def can_handle(self, task: AgentTask) -> bool:
        """Check if this agent can handle the given task type."""
        return task.task_type in self.capabilities

    def _make_result(self, **kwargs) -> AgentResult:
        """Convenience factory pre-filling agent_name."""
        return AgentResult(agent_name=self.name, **kwargs)

    def _error_result(self, message: str) -> AgentResult:
        """Return a standardized error result."""
        return AgentResult(
            agent_name=self.name,
            status="error",
            error_message=message,
        )

    def health_status(self) -> Dict[str, Any]:
        """Return health status for monitoring."""
        return {
            "agent": self.name,
            "capabilities": self.capabilities,
            **self.health.to_dict(),
        }

    def get_template_response(self, tool_name: str) -> Optional[str]:
        """Return a template fallback response when the Claude API is unavailable.

        Override in subclasses to provide tool-specific template responses.
        Returns None if no template is available (caller should show generic error).
        """
        return None

    def _api_down_result(self, tool_name: str) -> AgentResult:
        """Return a graceful result when Claude API is down.

        Uses template responses if available, then tries KG-powered contextual
        response, otherwise returns a generic 'service unavailable' message.
        """
        template = self.get_template_response(tool_name)
        if template:
            return AgentResult(
                agent_name=self.name,
                status="partial",
                data={"tool_result": template, "is_template": True},
                narrative=template,
            )

        # Try KG-powered contextual response
        kg_response = self._build_kg_response(tool_name)
        if kg_response:
            return AgentResult(
                agent_name=self.name,
                status="partial",
                data={"tool_result": kg_response, "is_kg_response": True},
                narrative=kg_response,
            )

        return AgentResult(
            agent_name=self.name,
            status="error",
            error_message="AI service temporarily unavailable. Please try again in a moment.",
            narrative="I'm temporarily unable to process this request due to an AI service issue. "
                      "Your data is safe — please try again in a moment.",
        )

    def _build_kg_response(self, tool_name: str) -> Optional[str]:
        """Build an intelligent response using the Knowledge Graph when LLM is unavailable.

        Queries relevant KG entities and formats them into a structured financial narrative.
        """
        try:
            from app.services.knowledge_graph import knowledge_graph

            # Map tool names to search queries
            query_map = {
                "calculate_financials": "financial calculation revenue profit margin",
                "generate_income_statement": "income statement profit loss IFRS",
                "generate_balance_sheet": "balance sheet assets liabilities equity IFRS",
                "generate_cash_flow": "cash flow operating investing financing",
                "compare_periods": "period comparison variance analysis trend",
                "generate_forecast": "forecast prediction trend extrapolation",
                "detect_anomalies": "anomaly detection unusual transaction fraud signal",
                "analyze_trends": "trend analysis time series financial",
                "create_scenario": "scenario simulation what-if analysis",
                "search_knowledge": "financial knowledge IFRS accounting standard",
            }

            query = query_map.get(tool_name, f"{tool_name} financial analysis")
            results = knowledge_graph.query(query, max_results=8)

            if not results:
                return None

            # Build structured response
            sections = []
            sections.append(f"## Financial Intelligence Analysis\n")
            sections.append(f"*Based on {len(results)} knowledge graph entities*\n")

            # Group by entity type
            by_type = {}
            for r in results:
                etype = r.get("entity_type", "general")
                if etype not in by_type:
                    by_type[etype] = []
                by_type[etype].append(r)

            type_labels = {
                "ratio": "Financial Ratios", "formula": "Key Formulas",
                "ifrs_standard": "IFRS Standards", "account": "Relevant Accounts",
                "benchmark": "Industry Benchmarks", "audit_signal": "Audit Signals",
                "flow": "Financial Flows", "concept": "Key Concepts",
                "regulation": "Regulatory Framework", "fraud_signal": "Risk Indicators",
            }

            for etype, entities in by_type.items():
                label = type_labels.get(etype, etype.replace("_", " ").title())
                sections.append(f"\n### {label}")
                for e in entities[:3]:
                    name = e.get("label_en", e.get("entity_id", ""))
                    desc = e.get("description", "")
                    if name:
                        sections.append(f"- **{name}**: {desc[:120]}" if desc else f"- **{name}**")

            sections.append(f"\n---\n*Analysis powered by FinAI Knowledge Graph ({knowledge_graph.entity_count} entities)*")
            return "\n".join(sections)

        except Exception as e:
            logger.debug(f"KG response failed: {e}")
            return None
