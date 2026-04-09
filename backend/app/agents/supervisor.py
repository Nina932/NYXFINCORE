"""
FinAI Supervisor Agent — Orchestrator for multi-agent financial intelligence.
══════════════════════════════════════════════════════════════════════════════

The Supervisor is the ONLY entry point for user requests. It:
1. Receives user messages from WebSocket/HTTP
2. Intercepts tool calls via monkey-patched execute_tool() on the legacy agent
3. Routes each tool call to the correct specialized agent
4. Falls back to the original legacy implementation if the specialist fails
5. Maintains audit trail for compliance
6. Tracks agent health for circuit breaker and monitoring

Architecture:
  User → chat()/stream_chat() → LegacyAgent calls Claude → Claude picks tool_use
       → execute_tool() [INTERCEPTED] → Supervisor routes to CalcAgent/InsightAgent/ReportAgent
       → result flows back into Claude's tool loop → final response to user

  This design preserves Claude's natural tool classification while routing
  actual execution to specialized agents with domain-specific logic.

Resilience:
  - Tool interception: specialized agent failure → auto-fallback to legacy execute_tool
  - Health-aware routing: skip agents with open circuit breakers
  - Per-agent circuit breaker: disable agent after N consecutive failures
  - Supervisor-level error handling wraps everything
  - contextvars prevents re-entrant routing when agents delegate back to legacy
"""

from __future__ import annotations

import contextvars
import time
import uuid
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.agents.base import AgentTask, AgentContext, AgentResult
from app.agents.registry import registry
from app.config import settings
from app.models.all_models import Dataset, AgentAuditLog, AgentMemory

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# CONTEXT VARS
#   _routing_depth  — prevents re-entrant routing when CalcAgent delegates back
#   _request_citations — per-request citation accumulation across all tool calls
# ═══════════════════════════════════════════════════════════════════════════════
_routing_depth = contextvars.ContextVar("supervisor_routing_depth", default=0)
_request_citations: contextvars.ContextVar = contextvars.ContextVar("_request_citations", default=None)


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL → AGENT ROUTING TABLE
# ═══════════════════════════════════════════════════════════════════════════════

# Maps tool names → agent names. This is the primary routing mechanism.
TOOL_ROUTING: Dict[str, str] = {
    # CalcAgent — all computation and financial statement generation
    "calculate_financials":        "calc",
    "generate_income_statement":   "calc",
    "generate_pl_statement":       "calc",
    "generate_balance_sheet":      "calc",
    "generate_cash_flow":          "calc",
    "compare_periods":             "calc",
    "deep_financial_analysis":     "calc",
    "generate_forecast":           "calc",
    "analyze_trends":              "calc",
    "create_scenario":             "calc",
    "compare_scenarios":           "calc",
    "query_trial_balance":         "calc",
    "query_balance_sheet":         "calc",

    # InsightAgent — reasoning, anomaly explanation, narrative, semantic analysis
    "detect_anomalies":            "insight",
    "detect_anomalies_statistical":"insight",
    "analyze_semantic":            "insight",
    "analyze_accounting_flows":    "insight",
    "search_knowledge":            "insight",

    # ReportAgent — report assembly, charts, export
    "generate_mr_report":          "report",
    "save_report_to_db":           "report",
    "generate_chart":              "report",

    # DecisionAgent — decision intelligence, predictions, monitoring (Phase I)
    "generate_actions":           "decision",
    "simulate_action_impact":     "decision",
    "get_decision_report":        "decision",
    "get_predictions":            "decision",
    "get_monitoring_status":      "decision",

    # Everything else → LegacyAgent (until we migrate them)
    "navigate_to_page":            "legacy",
    "query_transactions":          "legacy",
    "analyze_products":            "legacy",
    "search_counterparty":         "legacy",
    "convert_currency":            "legacy",
    "trace_lineage":               "legacy",
    "query_coa":                   "legacy",
}


# Navigation keywords that should always go to legacy (not calc)
_NAV_INTENT_KEYWORDS = frozenset({
    "navigate", "go to", "open page", "show page", "take me to",
    "switch to", "change page", "open the", "navigate to",
})

# Intent categories for pre-routing
_CALC_INTENT_KEYWORDS = frozenset({
    "income statement", "p&l statement", "profit and loss", "gross margin",
    "balance sheet", "cash flow", "cfs", "ebitda", "calculate",
    "forecast", "scenario", "compare period", "compare periods",
    "revenue analysis", "cogs analysis", "cost of goods", "generate statement",
    "net profit", "gross profit", "financial results", "generate report",
    "what is my margin", "what is my revenue", "what is my profit",
    "show financials", "generate income", "generate pl", "generate balance",
    "generate cash", "analyze trends", "analyze trend", "period comparison",
    "variance", "compare january", "compare february", "compare march",
    "compare q1", "compare q2", "compare q3", "compare q4",
    "year over year", "month over month", "period over period",
    "query trial balance", "query balance sheet", "deep financial",
})

_INSIGHT_INTENT_KEYWORDS = frozenset({
    "why", "explain", "reason", "anomaly", "unusual", "abnormal",
    "root cause", "what caused", "why is", "why did", "how come",
    "detect anomalies", "understand", "interpret",
    "what does this mean", "what happened",
})

_MULTI_STEP_PATTERNS = [
    # Patterns that trigger task decomposition
    ("calculate.*and.*explain", ["calc", "insight"]),
    ("generate.*report.*with.*narrative", ["calc", "report", "insight"]),
    ("compare.*and.*analyze", ["calc", "insight"]),
    ("upload.*and.*analyze", ["data", "insight"]),
]


class Supervisor:
    """Orchestrator that routes tool calls to specialized agents.

    The Supervisor installs a tool-level interceptor on the legacy FinAIAgent
    so that when Claude picks a tool_use, the execution is routed to the
    correct specialized agent (CalcAgent, InsightAgent, ReportAgent).

    The legacy agent's chat loop (Claude API call → tool_use → execute_tool)
    remains unchanged. Only execute_tool() is intercepted.

    Resilience features:
    - Tool failure → automatic fallback to legacy execute_tool
    - Health-aware routing: skips agents with open circuit breakers
    - All execution wrapped in supervisor-level error handling
    - Audit logging for every request (success or failure)
    - contextvars prevents infinite re-entrant routing
    """

    def __init__(self):
        self.session_id = uuid.uuid4().hex[:12]
        self._fallback_count = 0
        self._total_requests = 0
        self._tool_calls_routed = 0
        self._tool_calls_intercepted = 0
        self._original_execute_tool = None
        self._installed = False

    # ══════════════════════════════════════════════════════════════════════
    # TOOL ROUTER INSTALLATION — the core multi-agent mechanism
    # ══════════════════════════════════════════════════════════════════════

    def install_tool_router(self):
        """Monkey-patch the legacy agent's execute_tool() with routing logic.

        After this call, every tool call from Claude's chat loop goes through
        the Supervisor's routing, which dispatches to specialized agents.

        Safe to call multiple times (idempotent).
        """
        if self._installed:
            return

        try:
            from app.services.ai_agent import agent as legacy_agent
        except ImportError:
            logger.warning("[Supervisor] Cannot import legacy agent — tool routing disabled")
            return

        # Save original execute_tool for fallback
        self._original_execute_tool = legacy_agent.execute_tool
        supervisor_ref = self

        async def routed_execute_tool(name: str, params: Dict, db: AsyncSession) -> str:
            """Interceptor: routes tool calls to specialized agents."""
            return await supervisor_ref._routed_tool_execute(name, params, db)

        legacy_agent.execute_tool = routed_execute_tool
        self._installed = True
        logger.info(
            "[Supervisor] Tool router installed — %d tools routed to %d agents",
            len(TOOL_ROUTING),
            len(set(v for v in TOOL_ROUTING.values() if v != "legacy")),
        )

    # ══════════════════════════════════════════════════════════════════════
    # CORE ROUTING LOGIC — called for every tool execution
    # ══════════════════════════════════════════════════════════════════════

    async def _routed_tool_execute(
        self,
        tool_name: str,
        tool_params: Dict,
        db: AsyncSession,
    ) -> str:
        """Route a tool call to the correct specialized agent.

        Flow:
        1. Check re-entrancy guard (CalcAgent delegates back to legacy)
        2. Look up designated agent from TOOL_ROUTING
        3. If agent exists and is healthy → execute via safe_execute()
        4. If agent fails or is unhealthy → fallback to original execute_tool
        5. If tool is 'legacy' or unknown → use original directly

        Returns:
            str — tool result (same format as original execute_tool)
        """
        self._tool_calls_intercepted += 1

        # ── Re-entrancy guard ────────────────────────────────────────
        # When CalcAgent executes, it calls legacy_agent.execute_tool()
        # internally. Without this guard, that would route BACK to
        # CalcAgent → infinite loop. contextvars is asyncio-safe.
        depth = _routing_depth.get()
        if depth > 0:
            return await self._original_execute_tool(tool_name, tool_params, db)

        # ── Look up designated agent ─────────────────────────────────
        agent_name = TOOL_ROUTING.get(tool_name)

        # Unknown tool or legacy-routed → use original directly
        if not agent_name or agent_name == "legacy":
            return await self._original_execute_tool(tool_name, tool_params, db)

        # Get the agent instance
        agent = registry.get(agent_name)
        if not agent:
            return await self._original_execute_tool(tool_name, tool_params, db)

        # ── Health check — circuit breaker ────────────────────────────
        if hasattr(agent, "health") and not agent.health.is_healthy:
            logger.warning(
                "[Supervisor] Agent '%s' circuit OPEN for tool '%s' — using legacy",
                agent_name, tool_name,
            )
            self._fallback_count += 1
            return await self._original_execute_tool(tool_name, tool_params, db)

        # ── Execute via specialized agent ─────────────────────────────
        _routing_depth.set(depth + 1)
        start_time = time.time()
        try:
            context = await self._build_context(db, f"Execute tool: {tool_name}", [])

            task = AgentTask(
                task_type="tool_call",
                instruction=f"Execute tool: {tool_name}",
                parameters={
                    "tool_name": tool_name,
                    "tool_input": tool_params,
                },
            )

            result = await agent.safe_execute(task, context)
            elapsed_ms = int((time.time() - start_time) * 1000)

            if result.is_success or result.status == "partial":
                self._tool_calls_routed += 1
                output = result.data.get("tool_result", result.narrative or "Done.")
                logger.info(
                    "[Supervisor] Tool '%s' → %s agent (%dms)",
                    tool_name, agent_name, elapsed_ms,
                )

                # Accumulate citations from this tool call into the request-level list
                if result.citations:
                    accumulated = _request_citations.get()
                    if accumulated is not None:
                        accumulated.extend(result.citations)
                        logger.debug(
                            "[Supervisor] Accumulated %d citations from '%s' (total: %d)",
                            len(result.citations), tool_name, len(accumulated),
                        )

                # Log audit for routed tool calls
                await self._log_audit(
                    db, uuid.uuid4().hex[:12], agent_name, "tool_routed",
                    task, result, elapsed_ms,
                )
                return output

            # Agent returned error status — fallback
            logger.warning(
                "[Supervisor] %s agent FAILED on '%s': %s — falling back to legacy (%dms)",
                agent_name, tool_name, result.error_message, elapsed_ms,
            )
            self._fallback_count += 1

        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.warning(
                "[Supervisor] %s agent EXCEPTION on '%s': %s — falling back to legacy (%dms)",
                agent_name, tool_name, e, elapsed_ms,
            )
            self._fallback_count += 1
        finally:
            _routing_depth.set(depth)

        # ── Fallback to original legacy execution ─────────────────────
        try:
            legacy_result = await self._original_execute_tool(tool_name, tool_params, db)
            # Prepend a notice so users know this came from the fallback path
            fallback_notice = (
                f"[Note: The {agent_name} specialist was unavailable; "
                f"this response was generated via the general-purpose engine.]\n\n"
            )
            if isinstance(legacy_result, str):
                return fallback_notice + legacy_result
            return legacy_result
        except Exception as e:
            return f"Error executing tool '{tool_name}': {e}"

    # ══════════════════════════════════════════════════════════════════════
    # MAIN CHAT ENTRY POINTS
    # ══════════════════════════════════════════════════════════════════════

    async def handle_chat(
        self,
        message: str,
        history: List[Dict],
        db: AsyncSession,
    ) -> Dict:
        """Non-streaming chat handler. Returns same format as legacy agent.chat().

        Flow:
        1. Delegates to LegacyAgent for Claude classification
        2. Claude picks tool_use → execute_tool() [INTERCEPTED] → routed to specialist
        3. Results flow back through Claude's tool loop
        4. Final response returned as dict with citations
        """
        session_id = uuid.uuid4().hex[:12]
        start_time = time.time()
        self._total_requests += 1

        # Initialize per-request citation list (ContextVar so it's asyncio-task-safe)
        request_citations: List[Dict] = []
        _request_citations.set(request_citations)

        # Get the legacy agent
        legacy = registry.get("legacy")
        if not legacy:
            return {
                "response": "Agent system not initialized. Please restart the server.",
                "tool_calls": [],
                "navigation": None,
                "report_data": None,
            }

        # Build context with error handling
        try:
            context = await self._build_context(db, message, history)
        except Exception as e:
            logger.error("Supervisor _build_context failed: %s", e)
            context = AgentContext(db=db, user_message=message, conversation_history=history)

        # Create task
        task = AgentTask(
            task_type="chat",
            instruction=message,
            parameters={"history": history},
        )

        # ── Intent detection via StateGraph (primary) or keywords (fallback) ──
        intent = self._detect_intent(message)
        try:
            from app.services.telemetry import telemetry
            telemetry.record_intent_routing(intent)
        except Exception:
            pass

        # ── StateGraph routing (if compiled) ──
        try:
            from app.orchestration.chat_graph import get_chat_graph
            chat_graph = get_chat_graph()
            if chat_graph:
                graph_result = await chat_graph.ainvoke({
                    "message": message,
                    "context": context,
                    "parameters": {"history": history},
                })
                graph_intent = graph_result.final_state.get("intent", "")
                if graph_intent and graph_intent != "legacy":
                    intent = graph_intent  # Override keyword intent with graph intent
                    logger.info("[Supervisor] StateGraph routed: %s (was: %s)", graph_intent, intent)
        except Exception as e:
            logger.debug("[Supervisor] StateGraph routing unavailable: %s", e)

        # ── Single-agent fast path: try LLM-powered agents FIRST ──────
        # CRA (local computation) is used as FALLBACK only when LLM is unavailable.
        # This ensures users get real AI reasoning, not just metric dumps.
        if intent == "calc" and settings.AGENT_MODE == "multi":
            calc_result = await self._try_calc_agent_direct(message, history, context)
            if calc_result:
                # Check if CalcAgent returned an "AI unavailable" template —
                # fallback to CRA which can compute metrics locally
                narrative = calc_result.narrative or ""
                is_ai_unavailable = (
                    "AI service temporarily unavailable" in narrative
                    or "require the AI engine" in narrative
                    or (not narrative.strip())
                )
                if is_ai_unavailable:
                    logger.info(
                        "[Supervisor] CalcAgent returned AI-unavailable — "
                        "trying Ollama direct, then CRA"
                    )
                    # Try Ollama for real AI reasoning first
                    ollama_result = await self._try_ollama_direct(message, history, db, context)
                    if ollama_result:
                        elapsed_ms = int((time.time() - start_time) * 1000)
                        await self._log_audit(
                            db, session_id, "supervisor",
                            "handle_chat_ollama_direct",
                            task, ollama_result, elapsed_ms,
                        )
                        return {
                            "response": ollama_result.narrative,
                            "tool_calls": [],
                            "navigation": None,
                            "report_data": None,
                            "citations": _request_citations.get() or [],
                        }
                    # Last resort: CRA local computation
                    cra_fallback = await self._try_collaborative_reasoning(
                        message, history, db, context, force=True,
                    )
                    if cra_fallback and (cra_fallback.narrative or "").strip():
                        elapsed_ms = int((time.time() - start_time) * 1000)
                        await self._log_audit(
                            db, session_id, "supervisor",
                            "handle_chat_cra_fallback",
                            task, cra_fallback, elapsed_ms,
                        )
                        return {
                            "response": cra_fallback.narrative,
                            "tool_calls": cra_fallback.tool_calls,
                            "navigation": cra_fallback.navigation,
                            "report_data": cra_fallback.data.get("report_data"),
                            "citations": _request_citations.get() or [],
                            "cra_session": cra_fallback.data.get("cra_session"),
                        }

                if calc_result.citations:
                    accumulated = _request_citations.get()
                    if accumulated is not None:
                        accumulated.extend(calc_result.citations)
                elapsed_ms = int((time.time() - start_time) * 1000)
                await self._log_audit(
                    db, session_id, "supervisor", "handle_chat_calc_direct",
                    task, calc_result, elapsed_ms,
                )
                return {
                    "response": calc_result.narrative,
                    "tool_calls": calc_result.tool_calls,
                    "navigation": calc_result.navigation,
                    "report_data": calc_result.data.get("report_data"),
                    "citations": _request_citations.get() or [],
                }

        # Execute via legacy agent (tool calls are INTERCEPTED by our router)
        try:
            result = await legacy.safe_execute(task, context)
        except Exception as e:
            logger.error("Supervisor handle_chat failed: %s", e, exc_info=True)
            result = AgentResult(
                agent_name="supervisor",
                status="error",
                error_message=str(e),
                narrative="I encountered an unexpected error. Please try again.",
            )

        # If legacy also returned empty/error, try Ollama direct, then CRA as last resort
        legacy_narrative = result.narrative or ""
        if (not legacy_narrative.strip()
            or "AI service temporarily unavailable" in legacy_narrative
            or result.status == "error"):
            logger.info("[Supervisor] Legacy agent empty/error — trying Ollama direct")
            # Try Ollama directly with financial context
            ollama_result = await self._try_ollama_direct(message, history, db, context)
            if ollama_result:
                result = ollama_result
            else:
                # Last resort: CRA local computation
                logger.info("[Supervisor] Ollama unavailable — trying CRA as last resort")
                cra_last = await self._try_collaborative_reasoning(
                    message, history, db, context, force=True,
                )
                if cra_last and (cra_last.narrative or "").strip():
                    result = cra_last

        # Log audit
        elapsed_ms = int((time.time() - start_time) * 1000)
        await self._log_audit(
            db, session_id, "supervisor", "handle_chat",
            task, result, elapsed_ms,
        )

        return {
            "response": result.narrative,
            "tool_calls": result.tool_calls,
            "navigation": result.navigation,
            "report_data": result.data.get("report_data") if result.data else None,
            "citations": _request_citations.get() or [],
            "cra_session": result.data.get("cra_session") if result.data else None,
        }

    # ── WebSocket Streaming Chat ─────────────────────────────────────────

    async def stream_chat(
        self,
        message: str,
        history: List[Dict],
        db: AsyncSession,
        ws: Any,
    ) -> None:
        """Streaming chat via WebSocket. Same protocol as legacy agent.

        Events emitted:
          {"type": "stream_start"}
          {"type": "stream_delta", "content": "..."}
          {"type": "tool_call", "tool": "...", "input": {...}, "result": "..."}
          {"type": "stream_end", "tool_calls": [...], "navigation": "..."}
          {"type": "citations", "citations": [...]}   ← NEW: source provenance

        Tool calls within the stream are INTERCEPTED and routed to specialized agents
        via the installed tool router (same mechanism as handle_chat).
        """
        session_id = uuid.uuid4().hex[:12]
        start_time = time.time()
        self._total_requests += 1

        # Initialize per-request citation list (asyncio-task-safe via ContextVar)
        request_citations: List[Dict] = []
        _request_citations.set(request_citations)

        # Build context with error handling
        try:
            context = await self._build_context(db, message, history, ws=ws)
        except Exception as e:
            logger.error("Supervisor _build_context failed during stream: %s", e)
            context = AgentContext(
                db=db, user_message=message, conversation_history=history, ws=ws,
            )

        # Get the legacy agent for streaming
        legacy = registry.get("legacy")
        if not legacy:
            await self._safe_ws_send(ws, {"type": "error", "content": "Agent system not initialized"})
            return

        # Create task
        task = AgentTask(
            task_type="chat",
            instruction=message,
            parameters={"history": history, "stream": True},
        )

        # ── Intent detection: route calc requests to CalcAgent's focused mode ──
        # This bypasses the 8000-token LegacyAgent prompt for calculation requests
        intent = self._detect_intent(message)
        if intent == "calc" and settings.AGENT_MODE == "multi":
            calc_result = await self._try_calc_agent_direct(message, history, context, ws=ws)
            if calc_result:
                # Accumulate citations from CalcAgent's focused run
                if calc_result.citations:
                    accumulated = _request_citations.get()
                    if accumulated is not None:
                        accumulated.extend(calc_result.citations)
                # Send citations event
                accumulated_citations = _request_citations.get() or []
                if calc_result.citations:
                    await self._safe_ws_send(ws, {
                        "type": "citations",
                        "citations": accumulated_citations,
                        "count": len(accumulated_citations),
                    })
                # Audit
                elapsed_ms = int((time.time() - start_time) * 1000)
                await self._log_audit(
                    db, session_id, "supervisor", "stream_chat_calc_direct",
                    task, calc_result, elapsed_ms,
                )
                return
            # CalcAgent unavailable — fall through to legacy

        # Execute streaming with supervisor-level error handling
        # Tool calls inside stream_chat are INTERCEPTED by the installed router
        try:
            result = await legacy.safe_execute(task, context)
        except Exception as e:
            logger.error("Supervisor stream_chat failed: %s", e, exc_info=True)
            self._fallback_count += 1
            # Send error to client gracefully
            await self._safe_ws_send(ws, {"type": "stream_start"})
            await self._safe_ws_send(ws, {
                "type": "stream_delta",
                "content": "I encountered an error processing your request. Please try again.",
            })
            await self._safe_ws_send(ws, {
                "type": "stream_end",
                "tool_calls": [],
                "navigation": None,
            })
            result = AgentResult(
                agent_name="supervisor",
                status="error",
                error_message=str(e),
            )

        # Send accumulated citations as a dedicated WebSocket event
        # The frontend can use this to render a citations panel below the response
        accumulated_citations = _request_citations.get() or []
        if accumulated_citations:
            await self._safe_ws_send(ws, {
                "type": "citations",
                "citations": accumulated_citations,
                "count": len(accumulated_citations),
            })
            logger.info(
                "[Supervisor] Sent %d citations for session %s",
                len(accumulated_citations), session_id,
            )

        # Log audit
        elapsed_ms = int((time.time() - start_time) * 1000)
        await self._log_audit(
            db, session_id, "supervisor", "stream_chat",
            task, result, elapsed_ms,
        )

    # ══════════════════════════════════════════════════════════════════════
    # TOOL ROUTING HELPERS (public API for direct tool calls)
    # ══════════════════════════════════════════════════════════════════════

    def route_tool(self, tool_name: str) -> Optional[str]:
        """Determine which agent should handle a given tool call."""
        return TOOL_ROUTING.get(tool_name)

    def get_agent_for_tool(self, tool_name: str) -> Any:
        """Get the agent instance for a tool. Health-aware with fallback."""
        agent_name = self.route_tool(tool_name)
        if agent_name:
            agent = registry.get(agent_name)
            if agent:
                if hasattr(agent, "health") and not agent.health.is_healthy:
                    logger.warning(
                        "[Supervisor] Agent '%s' unhealthy for '%s' — fallback to legacy",
                        agent_name, tool_name,
                    )
                    self._fallback_count += 1
                    return registry.get("legacy")
                return agent
        return None

    async def execute_tool_with_fallback(
        self,
        tool_name: str,
        tool_params: Dict,
        db: AsyncSession,
    ) -> str:
        """Execute a tool with automatic agent fallback (public API).

        Can be called directly by routers or other code that needs
        to execute a tool outside the Claude chat loop.
        """
        return await self._routed_tool_execute(tool_name, tool_params, db)

    # ══════════════════════════════════════════════════════════════════════
    # INTERNAL HELPERS
    # ══════════════════════════════════════════════════════════════════════

    @staticmethod
    async def _safe_ws_send(ws: Any, data: Dict) -> bool:
        """Send JSON via WebSocket, catching connection errors."""
        try:
            await ws.send_json(data)
            return True
        except Exception as e:
            logger.warning("WebSocket send failed: %s", e)
            return False

    async def _build_context(
        self,
        db: AsyncSession,
        message: str,
        history: List[Dict],
        ws: Any = None,
    ) -> AgentContext:
        """Build shared context for agent execution.

        Queries the database for active datasets and builds context
        with period, currency, dataset IDs, and relevant AgentMemory entries.
        """
        from datetime import datetime
        from sqlalchemy import or_

        # Get active dataset(s)
        active_datasets = []
        dataset_ids = []
        period = ""
        currency = "GEL"
        try:
            result = await db.execute(
                select(Dataset).where(Dataset.is_active == True)   # noqa: E712
            )
            active_datasets = result.scalars().all()
            dataset_ids = [ds.id for ds in active_datasets]
            if active_datasets:
                period = active_datasets[0].period or ""
                currency = active_datasets[0].currency or "GEL"
        except Exception as e:
            logger.debug("[Supervisor] Dataset query failed: %s", e)
            try:
                await db.rollback()
            except Exception:
                pass

        # Load relevant AgentMemory entries
        # NOTE: Skipped — agent_memory table schema mismatch with ORM model
        # causes session corruption. Memory context is non-essential for chat.
        memory_context = {}

        ctx = AgentContext(
            db=db,
            dataset_ids=dataset_ids,
            period=period,
            currency=currency,
            user_message=message,
            conversation_history=history,
            ws=ws,
        )
        if memory_context:
            ctx.accumulated_results["agent_memory"] = memory_context
        return ctx

    async def _log_audit(
        self,
        db: AsyncSession,
        session_id: str,
        agent_name: str,
        action: str,
        task: AgentTask,
        result: AgentResult,
        duration_ms: int,
    ) -> None:
        """Persist an audit log entry (non-blocking, skips if DB schema mismatched)."""
        try:
            # Test session health first
            from sqlalchemy import text
            await db.execute(text("SELECT 1"))
        except Exception:
            try:
                await db.rollback()
            except Exception:
                pass
            return  # Session is dirty, skip audit to not corrupt further

        try:
            entry = AgentAuditLog(
                session_id=session_id,
                agent_name=agent_name,
                action=action,
                task_type=task.task_type,
                task_id=task.task_id,
                parent_task_id=task.parent_task_id,
                input_summary=task.instruction[:500],
                output_summary=(result.narrative or "")[:500],
                status=result.status,
                error_message=result.error_message[:500] if result.error_message else None,
                duration_ms=duration_ms,
                dataset_id=None,
            )
            db.add(entry)

            # ── Agent Memory: Record decision for learning ──
            # Every agent interaction becomes a memory that future interactions can reference.
            # This is how the system LEARNS from experience over time.
            if result.status == "success" and result.narrative:
                try:
                    from app.models.all_models import AgentMemory
                    memory = AgentMemory(
                        memory_type="decision",
                        content=f"[{agent_name}] Q: {task.instruction[:100]} → A: {(result.narrative or '')[:150]}",
                        context={
                            "agent": agent_name,
                            "action": action,
                            "task_type": task.task_type,
                            "duration_ms": duration_ms,
                            "session_id": session_id,
                        },
                        importance=7,  # Must be >= 6 for _build_context to read it
                        is_active=True,
                    )
                    db.add(memory)
                except Exception:
                    pass  # Memory recording is non-blocking

            await db.commit()
        except Exception as e:
            logger.warning("Failed to log audit: %s", e)
            try:
                await db.rollback()
            except Exception:
                pass

    # ══════════════════════════════════════════════════════════════════════
    # OLLAMA DIRECT — Real AI reasoning via local model
    # ══════════════════════════════════════════════════════════════════════

    async def _try_ollama_direct(
        self,
        message: str,
        history: List[Dict],
        db: AsyncSession,
        context: AgentContext,
    ) -> Optional[AgentResult]:
        """Try direct Ollama call with financial context for real AI reasoning."""
        try:
            from app.services.local_llm import local_llm
            if not await local_llm.is_available():
                return None

            # Build rich financial context from the database
            financial_context = await self._build_financial_context(db, context)

            system_prompt = f"""You are FinAI, an expert financial intelligence analyst.

You analyze financial data with precision. Always cite specific numbers and their sources.

CURRENT DATA (from database):
{financial_context}

RULES:
1. CITE SOURCES: When referencing a number, say where it comes from (e.g., "Revenue ₾113.1M [from 34 revenue items in January 2025 dataset]")
2. CAUSAL REASONING: Explain WHY metrics are what they are, not just what they are
3. BENCHMARKS: Compare to fuel distribution industry norms (gross margin 7-12%, EBITDA 4-8%, current ratio >1.5)
4. ACTIONS: Suggest specific, actionable steps — not generic advice
5. CURRENCY: Use Georgian Lari (GEL, ₾)
6. STRUCTURE: Use headers (##), bullet points, and bold for key numbers"""

            messages = []
            for h in history[-5:]:
                if isinstance(h, dict) and "role" in h:
                    messages.append({"role": h["role"], "content": h["content"]})
            messages.append({"role": "user", "content": message})

            logger.info("[Supervisor] Ollama direct: sending to Mistral 7B...")
            response = await local_llm.chat(
                system=system_prompt,
                messages=messages,
                complexity="capable",
                max_tokens=2048,
            )

            if response and len(response.strip()) > 50:
                logger.info("[Supervisor] Ollama direct: got %d chars response", len(response))
                return AgentResult(
                    agent_name="ollama_direct",
                    status="success",
                    narrative=response,
                    data={"source": "ollama_mistral_7b"},
                )
            return None
        except Exception as e:
            logger.warning("[Supervisor] Ollama direct failed: %s", e)
            return None

    async def _build_financial_context(self, db: AsyncSession, context: AgentContext) -> str:
        """Build a rich financial context string from ALL available datasets."""
        try:
            from sqlalchemy import select, func
            from app.models.all_models import (
                Transaction, RevenueItem, BudgetLine, Dataset,
                BalanceSheetItem, TrialBalanceItem,
            )

            # Get ALL datasets ordered by active first, then most recent
            all_ds_q = await db.execute(
                select(Dataset).order_by(Dataset.is_active.desc(), Dataset.id.desc()).limit(5)
            )
            datasets = all_ds_q.scalars().all()
            if not datasets:
                return "No financial data available."

            lines = ["=== AVAILABLE DATASETS ==="]
            for ds in datasets:
                txn_count = (await db.execute(
                    select(func.count(Transaction.id)).where(Transaction.dataset_id == ds.id)
                )).scalar() or 0
                rev_count = (await db.execute(
                    select(func.count(RevenueItem.id)).where(RevenueItem.dataset_id == ds.id)
                )).scalar() or 0
                bs_count = (await db.execute(
                    select(func.count(BalanceSheetItem.id)).where(BalanceSheetItem.dataset_id == ds.id)
                )).scalar() or 0
                tb_count = (await db.execute(
                    select(func.count(TrialBalanceItem.id)).where(TrialBalanceItem.dataset_id == ds.id)
                )).scalar() or 0
                active = " [ACTIVE]" if ds.is_active else ""
                lines.append(f"DS#{ds.id}: {ds.name}{active} | {ds.period} | txn={txn_count} rev={rev_count} bs={bs_count} tb={tb_count}")

            # Primary dataset: active one, or first seed
            ds = datasets[0]
            lines.append(f"\n=== PRIMARY DATASET: {ds.name} ({ds.period}) ===")

            # Revenue from this dataset
            rev_q = await db.execute(
                select(func.sum(RevenueItem.net), func.sum(RevenueItem.gross), func.count(RevenueItem.id))
                .where(RevenueItem.dataset_id == ds.id)
            )
            rev_net, rev_gross, rev_count = rev_q.one()
            rev_net = rev_net or 0

            # All transactions (including synthetic) from active dataset
            all_txn_q = await db.execute(
                select(Transaction.type, func.sum(Transaction.amount), func.count(Transaction.id))
                .where(Transaction.dataset_id == ds.id)
                .group_by(Transaction.type)
            )
            txn_by_type = {row[0]: {"total": row[1] or 0, "count": row[2]} for row in all_txn_q.all()}

            # Budget items
            bud_q = await db.execute(
                select(BudgetLine.line_item, BudgetLine.budget_amount)
                .where(BudgetLine.dataset_id == ds.id)
            )
            budget = {row[0]: row[1] for row in bud_q.all()}
            cogs = budget.get('COGS', 0) or 0

            # Revenue segments
            seg_q = await db.execute(
                select(RevenueItem.segment, func.sum(RevenueItem.net))
                .where(RevenueItem.dataset_id == ds.id)
                .group_by(RevenueItem.segment)
            )
            segments = {row[0]: row[1] for row in seg_q.all()}

            # Trial Balance summary (top accounts by turnover)
            tb_q = await db.execute(
                select(TrialBalanceItem.account_code, TrialBalanceItem.account_name,
                       TrialBalanceItem.turnover_debit, TrialBalanceItem.turnover_credit,
                       TrialBalanceItem.closing_debit, TrialBalanceItem.closing_credit)
                .where(TrialBalanceItem.dataset_id == ds.id)
                .order_by((TrialBalanceItem.turnover_debit + TrialBalanceItem.turnover_credit).desc())
                .limit(15)
            )
            tb_items = tb_q.all()

            # Balance Sheet summary
            bs_q = await db.execute(
                select(BalanceSheetItem.ifrs_line_item, BalanceSheetItem.closing_balance)
                .where(BalanceSheetItem.dataset_id == ds.id)
                .order_by(func.abs(BalanceSheetItem.closing_balance).desc())
                .limit(10)
            )
            bs_items = bs_q.all()

            # Build context
            gm = rev_net - cogs
            gm_pct = (gm / rev_net * 100) if rev_net > 0 else 0

            lines.append(f"Source: {ds.name} | Period: {ds.period} | Company: {ds.company or 'N/A'}")
            if rev_net > 0:
                lines.append(f"Revenue (net): ₾{rev_net:,.0f} [from {rev_count} items]")
                lines.append(f"COGS: ₾{cogs:,.0f} | Gross Margin: ₾{gm:,.0f} ({gm_pct:.1f}%)")
            for seg, val in segments.items():
                if seg and val:
                    lines.append(f"  Segment '{seg}': ₾{val:,.0f}")

            # Transaction summary by type
            for txn_type, info in txn_by_type.items():
                lines.append(f"Transactions [{txn_type}]: ₾{info['total']:,.0f} ({info['count']} entries)")

            # Budget items
            for key in ['Revenue Wholesale', 'Revenue Retial', 'COGS Wholesale', 'COGS Retial',
                        'Gr. Margin Wholesale', 'Gr. Margin Retial']:
                if key in budget and budget[key]:
                    lines.append(f"  Budget '{key}': ₾{budget[key]:,.0f}")

            # Top Trial Balance accounts
            if tb_items:
                lines.append(f"\n=== TOP TRIAL BALANCE ACCOUNTS (from {ds.name}) ===")
                for code, name, td, tc, cd, cc in tb_items[:10]:
                    net = (td or 0) - (tc or 0)
                    lines.append(f"  {code} {(name or '')[:30]}: turnover ₾{abs(net):,.0f} | closing ₾{((cd or 0) - (cc or 0)):,.0f}")

            # Balance Sheet items
            if bs_items:
                lines.append(f"\n=== KEY BALANCE SHEET ITEMS (from {ds.name}) ===")
                for ifrs_line, closing in bs_items[:8]:
                    if ifrs_line and closing:
                        lines.append(f"  {ifrs_line}: ₾{closing:,.0f}")

            return "\n".join(lines)
        except Exception as e:
            logger.warning("Failed to build financial context: %s", e)
            return "Financial data unavailable due to a database error."

    # ══════════════════════════════════════════════════════════════════════
    # COLLABORATIVE REASONING ARCHITECTURE (CRA)
    # ══════════════════════════════════════════════════════════════════════

    async def _try_collaborative_reasoning(
        self,
        message: str,
        history: List[Dict],
        db: AsyncSession,
        context: AgentContext,
        ws: Any = None,
        force: bool = False,
    ) -> Optional[AgentResult]:
        """Attempt collaborative multi-agent reasoning for complex queries.

        CRA activates when query complexity >= COMPLEXITY_THRESHOLD.
        Returns AgentResult if CRA handled it, None to fall back to single-agent.

        Args:
            force: If True, skip complexity check (used as fallback when AI is unavailable).
        """
        try:
            from app.services.reasoning_session import reasoning_session

            if not force and not reasoning_session.should_use_cra(message):
                return None

            logger.info("[Supervisor] CRA activated for: %s...", message[:60])

            # Stream CRA start event
            if ws:
                await self._safe_ws_send(ws, {
                    "type": "cra_start",
                    "message": "Collaborative analysis in progress...",
                })

            # Run the collaborative reasoning session
            session_ctx = await reasoning_session.run(
                query=message,
                db=db,
                dataset_ids=context.dataset_ids,
                period=context.period,
                currency=context.currency,
                history=history,
            )

            # Stream CRA completion
            if ws:
                await self._safe_ws_send(ws, {
                    "type": "cra_complete",
                    "agents": session_ctx.contributing_agents,
                    "metrics_count": len(session_ctx.metrics),
                    "insights_count": len(session_ctx.insights),
                    "latency_ms": session_ctx.total_latency_ms,
                    "confidence": session_ctx.confidence_score,
                })

            # Build AgentResult from session
            result = AgentResult(
                agent_name="supervisor",
                status="success" if session_ctx.formatted_output else "partial",
                narrative=session_ctx.formatted_output or session_ctx.executive_summary,
                data={
                    "cra_session": session_ctx.to_dict(),
                    "is_collaborative": True,
                },
            )

            # Track CRA usage in telemetry
            try:
                from app.services.telemetry import telemetry
                telemetry.record_agent_call(
                    "supervisor", "cra_session",
                    duration_ms=session_ctx.total_latency_ms,
                    status="success",
                    tool_name="collaborative_reasoning",
                )
            except Exception:
                pass

            return result

        except ImportError:
            logger.debug("[Supervisor] CRA module not available")
            return None
        except Exception as e:
            logger.warning("[Supervisor] CRA failed: %s — falling back to single-agent", e)
            return None

    # ══════════════════════════════════════════════════════════════════════
    # INTENT DETECTION & TASK DECOMPOSITION
    # ══════════════════════════════════════════════════════════════════════

    @staticmethod
    def _detect_intent(message: str) -> str:
        """Detect the primary intent of a user message.

        Returns:
            "calc" | "insight" | "data" | "report" | "chat"
        """
        msg_lower = message.lower()

        # Navigation always goes to legacy (highest priority check)
        if any(kw in msg_lower for kw in _NAV_INTENT_KEYWORDS):
            return "chat"

        if any(kw in msg_lower for kw in _CALC_INTENT_KEYWORDS):
            return "calc"
        if any(kw in msg_lower for kw in _INSIGHT_INTENT_KEYWORDS):
            return "insight"
        if any(kw in msg_lower for kw in ["upload", "import", "ingest", "load file"]):
            return "data"
        if any(kw in msg_lower for kw in ["generate report", "export", "save report", "mr report"]):
            return "report"
        return "chat"

    def _build_memory_prefix(self, context: AgentContext) -> str:
        """Build a memory context prefix for system prompts.

        Converts accumulated AgentMemory entries into a concise context block
        that can be prepended to any agent's system prompt.
        """
        mem = context.accumulated_results.get("agent_memory", {})
        entries = mem.get("entries", [])
        if not entries:
            return ""

        lines = ["[KNOWN FACTS from previous sessions:"]
        for e in entries[:5]:  # Max 5 to keep token count low
            lines.append(f"  - [{e['type']}, importance={e['importance']}] {e['content']}")
        lines.append("]")
        return "\n".join(lines)

    async def _try_calc_agent_direct(
        self,
        message: str,
        history: List[Dict],
        context: AgentContext,
        ws: Any = None,
    ) -> Optional[AgentResult]:
        """Try routing the full interaction to CalcAgent's focused mode.

        Returns:
            AgentResult if CalcAgent handled it, None if it should fall back to legacy.
        """
        try:
            calc_agent = registry.get("calc")
            if not calc_agent:
                return None
            if hasattr(calc_agent, "health") and not calc_agent.health.is_healthy:
                logger.warning("[Supervisor] CalcAgent circuit open — using legacy")
                return None

            logger.info("[Supervisor] Routing to CalcAgent focused mode for: %s...", message[:50])
            result = await calc_agent.run_focused_chat(
                message=message,
                history=history,
                context=context,
                stream_ws=ws,
            )
            return result
        except AttributeError:
            # CalcAgent doesn't have run_focused_chat (old version)
            return None
        except Exception as e:
            logger.warning("[Supervisor] CalcAgent direct routing failed: %s — falling back", e)
            return None

    # ══════════════════════════════════════════════════════════════════════
    # STATUS & HEALTH
    # ══════════════════════════════════════════════════════════════════════

    def status(self) -> Dict:
        """Return supervisor status for monitoring endpoint."""
        cra_available = False
        try:
            from app.services.reasoning_session import reasoning_session
            cra_available = True
        except ImportError:
            pass

        return {
            "mode": settings.AGENT_MODE,
            "session_id": self.session_id,
            "registry": registry.status(),
            "routing_table_size": len(TOOL_ROUTING),
            "tool_router_installed": self._installed,
            "cra_available": cra_available,
        }

    def health(self) -> Dict:
        """Return comprehensive health info for all agents."""
        agent_health = {}
        for agent in registry.all():
            if hasattr(agent, "health_status"):
                agent_health[agent.name] = agent.health_status()
            elif hasattr(agent, "health"):
                agent_health[agent.name] = agent.health.to_dict()
            else:
                agent_health[agent.name] = {"status": "unknown"}

        return {
            "supervisor": {
                "total_requests": self._total_requests,
                "tool_calls_intercepted": self._tool_calls_intercepted,
                "tool_calls_routed": self._tool_calls_routed,
                "fallback_count": self._fallback_count,
                "fallback_rate": (
                    round(self._fallback_count / max(self._tool_calls_intercepted, 1), 3)
                ),
                "routing_rate": (
                    round(self._tool_calls_routed / max(self._tool_calls_intercepted, 1), 3)
                ),
                "tool_router_installed": self._installed,
            },
            "agents": agent_health,
            "all_healthy": all(
                h.get("is_healthy", True)
                for h in agent_health.values()
                if isinstance(h, dict)
            ),
        }


# ── Module-level singleton ───────────────────────────────────────────────
supervisor = Supervisor()
