"""
FinAI AI Telemetry Service — Real-Time Observability for the Multi-Agent System.
=================================================================================
Tracks every agent decision, LLM call, tool invocation, and KG retrieval so
engineers and operators can debug, tune, and audit the AI layer.

Architecture:
  - In-memory counters (thread-safe via asyncio): zero-latency reads
  - Writes flush to AgentAuditLog (DB) in the background
  - Metrics endpoint exposes live dashboard data

Usage:
    from app.services.telemetry import telemetry

    # Record an agent decision
    telemetry.record_agent_call("calc", "run_focused_chat", duration_ms=142, tokens=320)

    # Record a tool invocation
    telemetry.record_tool_call("generate_income_statement", "calc", cache_hit=False, duration_ms=2400)

    # Record a KG retrieval
    telemetry.record_kg_retrieval("IFRS 15 revenue", results_count=3, duration_ms=1)

    # Expose metrics summary
    summary = telemetry.metrics_summary()
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Data structures ──────────────────────────────────────────────────────────

@dataclass
class AgentCallRecord:
    agent: str
    action: str
    duration_ms: int
    tokens_in: int
    tokens_out: int
    status: str          # success | error | cache_hit | template
    tool_name: Optional[str]
    timestamp: float = field(default_factory=time.time)


@dataclass
class ToolCallRecord:
    tool_name: str
    agent: str
    duration_ms: int
    cache_hit: bool
    status: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class KGRetrievalRecord:
    query: str
    results_count: int
    duration_ms: int
    timestamp: float = field(default_factory=time.time)


# ── Main Telemetry Collector ──────────────────────────────────────────────────

class TelemetryCollector:
    """
    Real-time observability for the FinAI multi-agent system.

    All counters are in-memory (asyncio-safe, single-process).
    Historical records kept in a rolling window (last 1000 events).
    """

    WINDOW_SIZE = 1000   # Rolling window for recent events
    _STARTUP = time.time()

    def __init__(self):
        # ── Lifetime counters ─────────────────────────────────
        self._agent_calls: Dict[str, int] = defaultdict(int)
        self._agent_errors: Dict[str, int] = defaultdict(int)
        self._agent_tokens_in: Dict[str, int] = defaultdict(int)
        self._agent_tokens_out: Dict[str, int] = defaultdict(int)
        self._agent_duration_ms: Dict[str, int] = defaultdict(int)

        self._tool_calls: Dict[str, int] = defaultdict(int)
        self._tool_cache_hits: Dict[str, int] = defaultdict(int)
        self._tool_duration_ms: Dict[str, int] = defaultdict(int)

        self._kg_retrievals: int = 0
        self._kg_results_total: int = 0
        self._kg_duration_ms: int = 0

        self._llm_calls: int = 0
        self._llm_cache_hits: int = 0
        self._llm_ollama_hits: int = 0
        self._llm_template_hits: int = 0
        self._llm_tokens_total: int = 0

        # ── Intent routing counters ───────────────────────────
        self._intent_routed: Dict[str, int] = defaultdict(int)

        # ── Rolling history ───────────────────────────────────
        self._agent_history: Deque[AgentCallRecord] = deque(maxlen=self.WINDOW_SIZE)
        self._tool_history: Deque[ToolCallRecord] = deque(maxlen=self.WINDOW_SIZE)
        self._kg_history: Deque[KGRetrievalRecord] = deque(maxlen=self.WINDOW_SIZE)

        # ── Error log (last 50 errors) ────────────────────────
        self._errors: Deque[Dict[str, Any]] = deque(maxlen=50)

        logger.info("TelemetryCollector initialized")

    # ── Recording methods ─────────────────────────────────────────────────────

    def record_agent_call(
        self,
        agent: str,
        action: str,
        duration_ms: int = 0,
        tokens_in: int = 0,
        tokens_out: int = 0,
        status: str = "success",
        tool_name: Optional[str] = None,
    ) -> None:
        """Record one agent action (LLM call, tool execution, routing decision)."""
        self._agent_calls[agent] += 1
        self._agent_tokens_in[agent] += tokens_in
        self._agent_tokens_out[agent] += tokens_out
        self._agent_duration_ms[agent] += duration_ms

        if status == "error":
            self._agent_errors[agent] += 1

        # Track LLM tier
        if status == "cache_hit":
            self._llm_cache_hits += 1
        elif status == "ollama":
            self._llm_ollama_hits += 1
        elif status == "template":
            self._llm_template_hits += 1
        else:
            self._llm_calls += 1

        self._llm_tokens_total += tokens_in + tokens_out

        record = AgentCallRecord(
            agent=agent,
            action=action,
            duration_ms=duration_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            status=status,
            tool_name=tool_name,
        )
        self._agent_history.append(record)

    def record_tool_call(
        self,
        tool_name: str,
        agent: str,
        duration_ms: int = 0,
        cache_hit: bool = False,
        status: str = "success",
    ) -> None:
        """Record one tool invocation."""
        self._tool_calls[tool_name] += 1
        self._tool_duration_ms[tool_name] += duration_ms
        if cache_hit:
            self._tool_cache_hits[tool_name] += 1

        record = ToolCallRecord(
            tool_name=tool_name,
            agent=agent,
            duration_ms=duration_ms,
            cache_hit=cache_hit,
            status=status,
        )
        self._tool_history.append(record)

    def record_kg_retrieval(
        self,
        query: str,
        results_count: int = 0,
        duration_ms: int = 0,
    ) -> None:
        """Record one knowledge graph query."""
        self._kg_retrievals += 1
        self._kg_results_total += results_count
        self._kg_duration_ms += duration_ms

        record = KGRetrievalRecord(
            query=query[:120],
            results_count=results_count,
            duration_ms=duration_ms,
        )
        self._kg_history.append(record)

    def record_intent_routing(self, intent: str) -> None:
        """Record a supervisor intent classification."""
        self._intent_routed[intent] += 1

    def record_error(
        self,
        agent: str,
        error_type: str,
        message: str,
        context: Optional[Dict] = None,
    ) -> None:
        """Record a system error for the error log."""
        self._agent_errors[agent] += 1
        self._errors.append({
            "agent": agent,
            "error_type": error_type,
            "message": message[:500],
            "context": context or {},
            "timestamp": time.time(),
        })
        logger.warning("[Telemetry] Error recorded: agent=%s type=%s msg=%s", agent, error_type, message[:100])

    # ── Metrics summary ───────────────────────────────────────────────────────

    def metrics_summary(self) -> Dict[str, Any]:
        """Return a complete snapshot of all telemetry metrics."""
        uptime_s = int(time.time() - self._STARTUP)

        # Agent summaries
        agents_summary = {}
        for agent in set(list(self._agent_calls.keys()) + ['legacy', 'calc', 'data', 'insight', 'report']):
            calls = self._agent_calls.get(agent, 0)
            errors = self._agent_errors.get(agent, 0)
            tok_in = self._agent_tokens_in.get(agent, 0)
            tok_out = self._agent_tokens_out.get(agent, 0)
            dur = self._agent_duration_ms.get(agent, 0)
            agents_summary[agent] = {
                "calls": calls,
                "errors": errors,
                "error_rate": round(errors / max(calls, 1), 3),
                "tokens_in": tok_in,
                "tokens_out": tok_out,
                "tokens_total": tok_in + tok_out,
                "avg_duration_ms": round(dur / max(calls, 1)),
            }

        # Top tools by call count
        top_tools = sorted(
            [
                {
                    "tool": t,
                    "calls": c,
                    "cache_hits": self._tool_cache_hits.get(t, 0),
                    "cache_rate": round(self._tool_cache_hits.get(t, 0) / max(c, 1), 3),
                    "avg_ms": round(self._tool_duration_ms.get(t, 0) / max(c, 1)),
                }
                for t, c in self._tool_calls.items()
            ],
            key=lambda x: x["calls"],
            reverse=True,
        )[:15]

        # LLM tier breakdown
        total_llm = self._llm_calls + self._llm_cache_hits + self._llm_ollama_hits + self._llm_template_hits
        llm_summary = {
            "total_calls": total_llm,
            "claude_api_calls": self._llm_calls,
            "cache_hits": self._llm_cache_hits,
            "ollama_calls": self._llm_ollama_hits,
            "template_responses": self._llm_template_hits,
            "tokens_total": self._llm_tokens_total,
            "cache_rate": round(self._llm_cache_hits / max(total_llm, 1), 3),
            "tier_breakdown": {
                "tier1_cache": f"{round(self._llm_cache_hits / max(total_llm, 1) * 100)}%",
                "tier2_claude": f"{round(self._llm_calls / max(total_llm, 1) * 100)}%",
                "tier3_ollama": f"{round(self._llm_ollama_hits / max(total_llm, 1) * 100)}%",
                "tier4_template": f"{round(self._llm_template_hits / max(total_llm, 1) * 100)}%",
            },
        }

        # KG summary
        kg_summary = {
            "total_queries": self._kg_retrievals,
            "total_results": self._kg_results_total,
            "avg_results": round(self._kg_results_total / max(self._kg_retrievals, 1), 1),
            "avg_duration_ms": round(self._kg_duration_ms / max(self._kg_retrievals, 1)),
            "recent_queries": [r.query for r in list(self._kg_history)[-5:]],
        }

        return {
            "uptime_seconds": uptime_s,
            "agents": agents_summary,
            "intent_routing": dict(self._intent_routed),
            "tools": {
                "total_calls": sum(self._tool_calls.values()),
                "unique_tools_used": len(self._tool_calls),
                "top_tools": top_tools,
            },
            "llm": llm_summary,
            "knowledge_graph": kg_summary,
            "errors": {
                "total": sum(self._agent_errors.values()),
                "recent": list(self._errors)[-10:],
            },
        }

    def recent_agent_calls(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return recent agent call records for debugging."""
        records = list(self._agent_history)[-limit:]
        return [
            {
                "agent": r.agent,
                "action": r.action,
                "duration_ms": r.duration_ms,
                "tokens_in": r.tokens_in,
                "tokens_out": r.tokens_out,
                "status": r.status,
                "tool_name": r.tool_name,
                "timestamp": r.timestamp,
            }
            for r in reversed(records)
        ]

    def health_score(self) -> Dict[str, Any]:
        """Compute an AI health score (0-100) based on error rates and performance."""
        total_calls = sum(self._agent_calls.values()) or 1
        total_errors = sum(self._agent_errors.values())
        error_rate = total_errors / total_calls

        # Cache efficiency
        total_llm = self._llm_calls + self._llm_cache_hits + self._llm_ollama_hits + self._llm_template_hits or 1
        cache_rate = self._llm_cache_hits / total_llm

        # Score components (0-100 each)
        error_score = max(0, 100 - error_rate * 500)   # 10% error = -50 pts
        cache_score = min(100, cache_rate * 200)         # 50% cache = 100 pts
        kg_score = min(100, (self._kg_retrievals / max(total_calls, 1)) * 200)  # KG used often = good

        overall = round((error_score * 0.5 + cache_score * 0.3 + kg_score * 0.2))

        return {
            "overall": overall,
            "grade": "A" if overall >= 90 else "B" if overall >= 75 else "C" if overall >= 60 else "D",
            "components": {
                "error_resilience": round(error_score),
                "cache_efficiency": round(cache_score),
                "kg_utilization": round(kg_score),
            },
            "details": {
                "error_rate": round(error_rate, 4),
                "cache_rate": round(cache_rate, 4),
                "total_calls": total_calls,
            },
        }

    def reset(self) -> None:
        """Reset all counters (for testing)."""
        self.__init__()


# ── Module-level singleton ────────────────────────────────────────────────────
telemetry = TelemetryCollector()
