"""
FinAI Calc Agent — Financial calculation specialist.

PHASE A-1 UPGRADE: CalcAgent Independence
  CalcAgent now runs its OWN focused Claude call (CALC_SYSTEM_PROMPT, ~600 tokens)
  instead of delegating to the 8,000-token monolithic LegacyAgent prompt.

  When the Supervisor detects a calculation-intent message, it routes the ENTIRE
  interaction to CalcAgent._run_focused_chat(). CalcAgent runs Claude with only
  its 13 tools + focused prompt → much faster responses, lower token cost.

  For tool-level interception (when a specific tool is called from LegacyAgent),
  CalcAgent continues to execute the tool directly via legacy_agent.execute_tool()
  (already the most efficient path).

PHASE B-1 UPGRADE: Multi-Dataset Support
  All calculation tools now accept `dataset_ids: List[int]` for consolidation.
  If multiple IDs provided, results are summed across datasets.

Tool Ownership (13 tools):
  calculate_financials, generate_income_statement, generate_pl_statement,
  generate_balance_sheet, generate_cash_flow, compare_periods,
  deep_financial_analysis, generate_forecast, analyze_trends,
  create_scenario, compare_scenarios, query_trial_balance, query_balance_sheet
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from app.agents.base import BaseAgent, AgentTask, AgentContext, AgentResult
from app.services.citation_service import CitationTracker

logger = logging.getLogger(__name__)


# ── CalcAgent's focused system prompt (~600 tokens instead of ~8000) ─────────
CALC_SYSTEM_PROMPT = """You are the FinAI Calculation Agent — a precision-focused financial math specialist.

ROLE: Execute financial calculations with exact Decimal precision.
SCOPE: Income statements, balance sheets, cash flows, forecasts, scenarios, comparisons.

RULES:
1. All financial figures must be EXACT — never approximate or round in intermediate steps
2. Use the P&L waterfall: Revenue → COGS → Gross Margin → G&A → EBITDA → D&A → EBIT → Finance → EBT → Tax → Net
3. COGS = Column K (account 6) + Column L (account 7310) + Column O (account 8230)
4. Wholesale margins may be NEGATIVE — this is expected (loss-leader strategy)
5. Always use NET revenue (excludes VAT), never GROSS
6. Currency: GEL (Georgian Lari, ₾)

When comparing periods, show absolute change AND percentage change.
When presenting results, include exact figures (e.g., 51,163,022.93) not rounded (₾51.2M).

For multi-dataset requests, use the dataset_ids list to consolidate across periods.
Always cite the dataset source in your response.
"""


# ── Template fallback responses when Claude API is unavailable ───────────────
CALC_TEMPLATE_RESPONSES = {
    "generate_income_statement": (
        "⚠ AI service temporarily unavailable. Here's what I can tell you:\n\n"
        "The Income Statement (P&L) shows the company's financial performance over a period.\n"
        "Key structure: Revenue → COGS → Gross Margin → G&A → EBITDA → D&A → EBIT → "
        "Finance Costs → EBT → Tax → Net Profit.\n\n"
        "Please try again in a moment and I'll generate the full statement with your data."
    ),
    "generate_pl_statement": (
        "⚠ AI service temporarily unavailable. Here's what I can tell you:\n\n"
        "The P&L Statement follows the waterfall: Revenue → COGS → Gross Margin → "
        "Operating Expenses → EBITDA → Net Profit.\n\n"
        "Please try again in a moment for the full analysis."
    ),
    "generate_balance_sheet": (
        "⚠ AI service temporarily unavailable. Here's what I can tell you:\n\n"
        "The Balance Sheet shows Assets = Liabilities + Equity at a point in time.\n"
        "Assets: Current (cash, receivables, inventory) + Non-current (fixed assets).\n"
        "Liabilities: Current (payables, short-term debt) + Non-current (long-term debt).\n\n"
        "Please try again in a moment for the full statement."
    ),
    "generate_cash_flow": (
        "⚠ AI service temporarily unavailable. Here's what I can tell you:\n\n"
        "The Cash Flow Statement has 3 sections:\n"
        "• Operating: Net Income + adjustments (D&A, working capital changes)\n"
        "• Investing: CapEx, acquisitions, asset sales\n"
        "• Financing: Debt changes, equity, dividends\n\n"
        "Please try again in a moment for the full CFS."
    ),
    "calculate_financials": (
        "⚠ AI service temporarily unavailable.\n\n"
        "Financial calculations require the AI engine. Please try again shortly."
    ),
    "deep_financial_analysis": (
        "⚠ AI service temporarily unavailable.\n\n"
        "Deep financial analysis requires the AI engine for reasoning and commentary. "
        "Please try again in a moment."
    ),
    "generate_forecast": (
        "⚠ AI service temporarily unavailable.\n\n"
        "Forecasting requires the AI engine. Please try again shortly."
    ),
    "compare_periods": (
        "⚠ AI service temporarily unavailable.\n\n"
        "Period comparison requires the AI engine for variance analysis. "
        "Please try again in a moment."
    ),
}


# ── Intent keywords for routing ───────────────────────────────────────────────
CALC_INTENT_KEYWORDS = frozenset({
    "income statement", "p&l", "profit and loss", "gross margin",
    "balance sheet", "cash flow", "cfs", "ebitda", "ebit",
    "calculate", "forecast", "scenario", "compare period",
    "revenue", "cogs", "cost of goods", "ga expenses",
    "generate report", "show financials", "financial results",
    "net profit", "gross profit", "operating", "working capital",
    "variance analysis", "period comparison", "trend",
})


class CalcAgent(BaseAgent):
    """Financial calculation specialist agent.

    PHASE A-1: Independent LLM execution with focused 600-token system prompt.
    PHASE B-1: Multi-dataset support for consolidation across periods.

    Execution modes:
    1. FULL CHAT MODE: Supervisor detects calc-intent → CalcAgent._run_focused_chat()
       Uses CALC_SYSTEM_PROMPT + 13 tools. Claude decides which tool to call.
       Far more efficient than LegacyAgent's 8000-token prompt.

    2. TOOL INTERCEPTION MODE: Supervisor intercepts a specific tool call →
       CalcAgent.execute(). Executes tool directly via legacy_agent.execute_tool().
       Already efficient; no additional LLM call needed for known tools.

    Resilience:
    - Template fallback responses when Claude API is down
    - Health tracking via BaseAgent.safe_execute()
    - Circuit breaker: auto-disabled after 5 consecutive failures
    - Response caching: same data + same params = cached result
    """

    name = "calc"
    description = "Financial calculation specialist — P&L, BS, CFS, forecasts, scenarios"
    capabilities = [
        "calculate",
        "generate_statement",
        "compare",
        "forecast",
        "scenario",
    ]

    # Tool names this agent owns
    OWNED_TOOLS = [
        "calculate_financials",
        "generate_income_statement",
        "generate_pl_statement",
        "generate_balance_sheet",
        "generate_cash_flow",
        "compare_periods",
        "deep_financial_analysis",
        "generate_forecast",
        "analyze_trends",
        "create_scenario",
        "compare_scenarios",
        "query_trial_balance",
        "query_balance_sheet",
    ]

    def __init__(self):
        super().__init__()
        self._legacy_agent = None
        self._response_cache = None

    @property
    def legacy_agent(self):
        """Lazy-load the legacy agent for tool execution."""
        if self._legacy_agent is None:
            from app.services.ai_agent import agent
            self._legacy_agent = agent
        return self._legacy_agent

    @property
    def cache(self):
        """Lazy-load the response cache."""
        if self._response_cache is None:
            from app.services.response_cache import response_cache
            self._response_cache = response_cache
        return self._response_cache

    @property
    def tools(self) -> List[dict]:
        """Return only the tool definitions this agent owns."""
        return [
            t for t in self.legacy_agent.tools
            if t.get("name") in self.OWNED_TOOLS
        ]

    def get_template_response(self, tool_name: str) -> Optional[str]:
        """Return a template fallback for when Claude API is unavailable."""
        return CALC_TEMPLATE_RESPONSES.get(tool_name)

    @staticmethod
    def is_calc_intent(message: str) -> bool:
        """Detect if a user message is primarily a calculation request.

        Used by Supervisor to route the full interaction to CalcAgent
        instead of LegacyAgent.

        Navigation keywords take priority — same as Supervisor._detect_intent().
        This prevents "navigate to P&L" from being treated as a calc request.
        """
        msg_lower = message.lower()
        # Nav keywords win — mirror Supervisor._detect_intent() behaviour
        _nav = {"navigate", "go to", "open page", "show page", "take me to", "switch to"}
        if any(kw in msg_lower for kw in _nav):
            return False
        return any(kw in msg_lower for kw in CALC_INTENT_KEYWORDS)

    # ── Full Chat Mode (Phase A-1: CalcAgent Independence) ───────────────────

    async def run_focused_chat(
        self,
        message: str,
        history: List[Dict[str, Any]],
        context: AgentContext,
        stream_ws: Any = None,
    ) -> AgentResult:
        """Run a full calculation chat using CalcAgent's focused system prompt.

        This is the INDEPENDENT mode: CalcAgent handles the entire interaction
        with its 600-token focused prompt instead of LegacyAgent's 8000-token monolith.

        Flow:
          1. Build messages from history + user message
          2. Call Claude with CALC_SYSTEM_PROMPT + calc tools only
          3. Execute any tool calls directly via legacy_agent.execute_tool()
          4. Optionally request InsightAgent narrative for complex outputs
          5. Stream events via ws if provided
          6. Return AgentResult

        Args:
            message: User's current message
            history: Conversation history
            context: AgentContext with db, dataset_ids, etc.
            stream_ws: WebSocket for streaming events (optional)

        Returns:
            AgentResult with narrative and data
        """
        from app.config import settings

        start_time = time.time()
        result = self._make_result()

        # Build the message list
        messages: List[Dict[str, Any]] = []
        for h in history[-10:]:  # Last 10 turns for context
            if isinstance(h, dict) and "role" in h and "content" in h:
                messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": message})

        # Enrich context with dataset info
        system = self._build_system_with_context(CALC_SYSTEM_PROMPT, context)

        # Tool-use agentic loop
        final_text = ""
        tool_calls_made = []
        max_rounds = 5  # Prevent infinite loops

        try:
            # Emit stream start
            if stream_ws:
                await self._safe_ws_send(stream_ws, {"type": "stream_start"})

            for _round in range(max_rounds):
                # Check response cache
                cache_key = self.cache.make_key(
                    "calc_chat",
                    {"msg": message, "round": _round},
                    dataset_hash=self._get_dataset_hash(context),
                )
                cached = self.cache.get(cache_key) if _round == 0 else None

                if cached:
                    final_text = cached
                    logger.info("[CalcAgent] Cache HIT for calc_chat")
                    if stream_ws:
                        await self._safe_ws_send(stream_ws, {
                            "type": "stream_delta", "content": cached,
                        })
                    break

                # Call Claude with focused prompt
                response = await self.call_llm(
                    system=system,
                    messages=messages,
                    tools=self.tools,
                    max_tokens=4096,
                )

                if response.stop_reason == "tool_use":
                    # Execute tool calls
                    tool_results = []
                    for block in response.content:
                        if hasattr(block, "type") and block.type == "tool_use":
                            tool_name = block.name
                            tool_input = block.input or {}

                            # Handle multi-dataset consolidation
                            tool_input = self._apply_multi_dataset(tool_input, context)

                            # Stream tool call event
                            if stream_ws:
                                await self._safe_ws_send(stream_ws, {
                                    "type": "tool_call",
                                    "tool": tool_name,
                                    "input": tool_input,
                                    "agent": "calc",
                                })

                            # Execute the tool
                            try:
                                tool_result = await self.legacy_agent.execute_tool(
                                    tool_name, tool_input, context.db
                                )
                            except Exception as e:
                                tool_result = f"Tool execution error: {e}"
                                logger.error("[CalcAgent] Tool %s failed: %s", tool_name, e)

                            tool_calls_made.append({
                                "tool": tool_name,
                                "input": tool_input,
                                "result": str(tool_result)[:300],
                            })
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": str(tool_result),
                            })

                            # Add citation
                            ds_id = tool_input.get("dataset_id") or context.primary_dataset_id
                            if ds_id:
                                tracker = CitationTracker()
                                tracker.add(
                                    source_type=tool_name,
                                    claim=f"{tool_name} result",
                                    dataset_id=ds_id,
                                    period=tool_input.get("period", context.period),
                                    confidence=1.0,
                                )
                                result.citations.extend(tracker.citations)

                    # Add assistant + tool results to messages
                    messages.append({"role": "assistant", "content": response.content})
                    messages.append({"role": "user", "content": tool_results})

                else:
                    # Final text response
                    for block in response.content:
                        if hasattr(block, "text"):
                            final_text += block.text

                    # Stream the final text
                    if stream_ws and final_text:
                        for chunk in self._chunk_text(final_text, 100):
                            await self._safe_ws_send(stream_ws, {
                                "type": "stream_delta", "content": chunk,
                            })

                    # Cache the result
                    if final_text and _round == 0:
                        self.cache.store(cache_key, final_text, tool_name="calc_chat")

                    break

            # Extract navigation if present
            nav = None
            if "__NAVIGATE_TO__" in final_text:
                import re
                m = re.search(r"__NAVIGATE_TO__(\w+)__END__", final_text)
                if m:
                    nav = m.group(1)

            # Emit stream end
            if stream_ws:
                await self._safe_ws_send(stream_ws, {
                    "type": "stream_end",
                    "tool_calls": tool_calls_made,
                    "navigation": nav,
                    "agent": "calc",
                })

            elapsed_ms = int((time.time() - start_time) * 1000)
            result.status = "success"
            result.narrative = final_text
            result.tool_calls = tool_calls_made
            result.navigation = nav
            result.add_audit(
                action="calc_focused_chat",
                input_summary=message[:200],
                output_summary=final_text[:200],
                duration_ms=elapsed_ms,
            )

        except Exception as e:
            error_str = str(e).lower()
            is_api_error = any(kw in error_str for kw in [
                "rate_limit", "overloaded", "api", "connection", "timeout",
                "500", "502", "503", "504", "529", "credit", "balance",
            ])
            if is_api_error:
                # Don't return template — let supervisor try Ollama direct
                logger.warning("[CalcAgent] LLM unavailable: %s — returning None for Ollama fallback", str(e)[:100])
                result = self._make_result(
                    status="error",
                    narrative="AI service temporarily unavailable",
                    data={"is_template": True, "needs_ollama": True},
                )
                if stream_ws:
                    await self._safe_ws_send(stream_ws, {"type": "stream_end", "tool_calls": [], "navigation": None})
            else:
                logger.error("[CalcAgent] run_focused_chat error: %s", e, exc_info=True)
                result = self._error_result(str(e))

        return result

    # ── Tool Interception Mode (existing, now enhanced) ───────────────────────

    async def execute(self, task: AgentTask, context: AgentContext) -> AgentResult:
        """Execute a calculation task via direct tool interception.

        Called by Supervisor when it intercepts a specific tool call from LegacyAgent.
        Executes tool directly (no extra LLM round-trip needed).

        Resilience:
        - Template fallback responses when Claude API is down
        - Response caching: same params + dataset = cached result
        - Citations added for every calculation
        """
        start_time = time.time()
        result = self._make_result()

        try:
            tool_name = task.parameters.get("tool_name", "")
            tool_input = task.parameters.get("tool_input", {})

            if tool_name and tool_name in self.OWNED_TOOLS:
                # Apply multi-dataset consolidation if needed
                tool_input = self._apply_multi_dataset(tool_input, context)

                # Check response cache
                cache_key = self.cache.make_key(
                    tool_name,
                    tool_input,
                    dataset_hash=self._get_dataset_hash(context),
                )
                cached = self.cache.get(cache_key)
                if cached:
                    logger.info("[CalcAgent] Cache HIT for tool=%s", tool_name)
                    result.status = "success"
                    result.narrative = cached
                    result.data = {"tool_result": cached, "from_cache": True}
                    return result

                # Direct tool execution (bypass Claude entirely for known tools)
                output = await self.legacy_agent.execute_tool(
                    tool_name, tool_input, context.db
                )
                result.status = "success"
                result.narrative = output
                result.data = {"tool_result": output}
                result.tool_calls = [{"tool": tool_name, "input": tool_input, "result": str(output)[:200]}]

                # Cache the result
                self.cache.store(cache_key, str(output), tool_name=tool_name)

                # Add dataset-level citation
                dataset_id = tool_input.get("dataset_id") or context.primary_dataset_id
                if dataset_id:
                    tracker = CitationTracker()
                    tracker.add(
                        source_type=tool_name,
                        claim=f"{tool_name} result",
                        dataset_id=dataset_id,
                        dataset_name=tool_input.get("period", ""),
                        period=tool_input.get("period", context.period),
                        confidence=1.0,
                    )
                    result.citations = tracker.citations

                # Extract navigation if present
                if "__NAVIGATE_TO__" in str(output):
                    import re
                    m = re.search(r"__NAVIGATE_TO__(\w+)__END__", str(output))
                    if m:
                        result.navigation = m.group(1)

                # Try to get InsightAgent narrative for complex outputs
                if tool_name in ("generate_income_statement", "generate_pl_statement",
                                 "generate_mr_report", "deep_financial_analysis"):
                    try:
                        narrative = await self._get_insight_narrative(
                            tool_name, output, context
                        )
                        if narrative:
                            result.data["narrative"] = narrative
                    except Exception as ni_err:
                        logger.debug("[CalcAgent] Insight narrative failed: %s", ni_err)

            else:
                result.status = "error"
                result.error_message = (
                    f"CalcAgent cannot handle tool '{tool_name}'. "
                    f"Owned tools: {self.OWNED_TOOLS}"
                )

        except Exception as e:
            error_str = str(e).lower()
            is_api_error = any(kw in error_str for kw in [
                "rate_limit", "overloaded", "api", "connection",
                "timeout", "500", "502", "503", "504", "529",
            ])
            tool_name = task.parameters.get("tool_name", "")

            if is_api_error:
                logger.warning(
                    "CalcAgent API error on '%s': %s — returning template response",
                    tool_name, e,
                )
                return self._api_down_result(tool_name)

            logger.error("CalcAgent execution error: %s", e, exc_info=True)
            result.status = "error"
            result.error_message = str(e)

        # Audit
        elapsed_ms = int((time.time() - start_time) * 1000)
        result.add_audit(
            action="calc_execute",
            input_summary=f"tool={task.parameters.get('tool_name', 'unknown')}",
            output_summary=(result.narrative or "")[:200],
            duration_ms=elapsed_ms,
        )

        return result

    def can_handle(self, task: AgentTask) -> bool:
        """Check if this agent can handle the given task."""
        tool_name = task.parameters.get("tool_name", "")
        if tool_name in self.OWNED_TOOLS:
            return True
        return task.task_type in self.capabilities

    # ── Internal Helpers ─────────────────────────────────────────────────────

    def _build_system_with_context(
        self, base_prompt: str, context: AgentContext
    ) -> str:
        """Enhance the system prompt with current dataset context."""
        lines = [base_prompt]
        if context.dataset_ids:
            lines.append(f"\nACTIVE DATASETS: IDs {context.dataset_ids}")
        if context.period:
            lines.append(f"CURRENT PERIOD: {context.period}")
        if context.currency:
            lines.append(f"CURRENCY: {context.currency}")
        if len(context.dataset_ids) > 1:
            lines.append(
                f"\nMULTI-DATASET MODE: {len(context.dataset_ids)} datasets available. "
                f"Use dataset_ids=[{', '.join(map(str, context.dataset_ids))}] for consolidation."
            )
        return "\n".join(lines)

    def _apply_multi_dataset(
        self, tool_input: Dict[str, Any], context: AgentContext
    ) -> Dict[str, Any]:
        """Apply multi-dataset IDs to tool input if not already specified.

        For backward compatibility, if tool_input has single dataset_id, keep it.
        If context has multiple datasets and tool_input doesn't specify, add them.
        """
        tool_input = dict(tool_input)  # Don't mutate original

        # If already has dataset_ids list, keep it
        if "dataset_ids" in tool_input:
            return tool_input

        # If has single dataset_id, keep backward compat
        if "dataset_id" in tool_input:
            return tool_input

        # Apply context dataset IDs
        if context.primary_dataset_id:
            tool_input["dataset_id"] = context.primary_dataset_id

        return tool_input

    def _get_dataset_hash(self, context: AgentContext) -> str:
        """Build a hash representing the current dataset state for caching."""
        from app.services.response_cache import ResponseCache
        # Use dataset IDs + period as hash (simple but effective)
        raw = f"{sorted(context.dataset_ids)}:{context.period}"
        import hashlib
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    async def _get_insight_narrative(
        self,
        tool_name: str,
        tool_output: str,
        context: AgentContext,
    ) -> Optional[str]:
        """Request InsightAgent narrative for complex financial outputs.

        Called after a major calculation tool runs.
        Returns narrative string, or None if InsightAgent is unavailable.
        """
        try:
            from app.agents.registry import registry
            from app.agents.base import AgentTask

            insight_agent = registry.get("insight")
            if not insight_agent:
                return None

            insight_task = AgentTask(
                task_type="explain",
                instruction=(
                    f"Generate a brief executive narrative for this {tool_name} output. "
                    f"Focus on key insights, anomalies, and recommendations. Max 3 sentences."
                ),
                parameters={
                    "tool_name": tool_name,
                    "tool_output": tool_output[:2000],  # Truncate for token efficiency
                    "period": context.period,
                    "dataset_ids": context.dataset_ids,
                },
                source_agent="calc",
            )

            insight_result = await insight_agent.execute(insight_task, context)
            if insight_result.is_success and insight_result.narrative:
                return insight_result.narrative

        except Exception as e:
            logger.debug("[CalcAgent] InsightAgent narrative skipped: %s", e)

        return None

    @staticmethod
    def _chunk_text(text: str, chunk_size: int = 100) -> List[str]:
        """Split text into chunks for streaming."""
        return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]

    @staticmethod
    async def _safe_ws_send(ws: Any, data: Dict) -> bool:
        """Send JSON via WebSocket, catching connection errors."""
        try:
            await ws.send_json(data)
            return True
        except Exception as e:
            logger.warning("CalcAgent WebSocket send failed: %s", e)
            return False
