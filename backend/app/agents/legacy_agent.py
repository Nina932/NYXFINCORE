"""
FinAI Legacy Agent — Wrapper around the existing FinAIAgent.

This adapter allows the existing monolithic FinAIAgent to participate in
the multi-agent system. It wraps the existing chat() and stream_chat()
methods behind the BaseAgent interface.

As tools are migrated to specialized agents (Calc, Data, Insight, Report),
they are removed from LegacyAgent. When all tools are migrated,
LegacyAgent can be retired.

Migration tracking:
  - Phase 2: CalcAgent takes 13 calculation tools
  - Phase 3: DataAgent takes ingestion tools
  - Phase 4: InsightAgent takes analysis tools
  - Phase 5: ReportAgent takes report/export tools
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from app.agents.base import BaseAgent, AgentTask, AgentContext, AgentResult

logger = logging.getLogger(__name__)


class LegacyAgent(BaseAgent):
    """Wraps the existing FinAIAgent for backward compatibility.

    All tools that haven't been migrated to specialized agents
    are handled here via delegation to the original agent.
    """

    name = "legacy"
    description = "Legacy agent — wraps existing FinAIAgent for unmigrated tools"
    capabilities = [
        "chat",           # General conversation
        "navigate",       # UI navigation
        "query",          # Data queries
        "report",         # Report generation (until ReportAgent)
        "analyze",        # Analysis (until InsightAgent)
    ]

    def __init__(self):
        super().__init__()
        self._legacy_agent = None

    @property
    def legacy_agent(self):
        """Lazy-load the existing FinAIAgent singleton."""
        if self._legacy_agent is None:
            from app.services.ai_agent import agent
            self._legacy_agent = agent
        return self._legacy_agent

    @property
    def tools(self) -> List[dict]:
        """Expose all tools from the legacy agent."""
        return self.legacy_agent.tools

    async def execute(self, task: AgentTask, context: AgentContext) -> AgentResult:
        """Execute a task by delegating to the legacy FinAIAgent.

        For streaming tasks (WebSocket), uses stream_chat().
        For non-streaming, uses chat().
        """
        start_time = time.time()
        result = self._make_result()

        try:
            is_streaming = task.parameters.get("stream", False)
            message = task.instruction
            history = task.parameters.get("history", [])

            if is_streaming and context.ws:
                # Streaming via WebSocket — legacy agent handles the full loop
                await self.legacy_agent.stream_chat(
                    message=message,
                    history=history,
                    db=context.db,
                    ws=context.ws,
                )
                # stream_chat sends events directly to WebSocket
                # We just return a minimal result for audit logging
                result.status = "success"
                result.narrative = f"[streamed response for: {message[:100]}]"

            else:
                # Non-streaming — get full response
                response = await self.legacy_agent.chat(
                    message=message,
                    history=history,
                    db=context.db,
                )
                result.status = "success"
                result.narrative = response.get("response", "")
                result.tool_calls = response.get("tool_calls", [])
                result.navigation = response.get("navigation")
                result.data = {"report_data": response.get("report_data")}

        except Exception as e:
            logger.error("LegacyAgent execution error: %s", e, exc_info=True)
            result.status = "error"
            result.error_message = str(e)

        # Audit
        elapsed_ms = int((time.time() - start_time) * 1000)
        result.add_audit(
            action="execute",
            input_summary=task.instruction[:200],
            output_summary=(result.narrative or "")[:200],
            duration_ms=elapsed_ms,
        )

        return result
