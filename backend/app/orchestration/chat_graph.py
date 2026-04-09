"""
ChatGraph — Graph-based chat routing (replaces keyword routing in supervisor)
=============================================================================
Defines: START → intent_classifier → conditional → [agent nodes] → merge → END
Reuses existing agents via registry, preserving all BaseAgent patterns.
"""

from __future__ import annotations
import logging
import re
from typing import Any, Dict, Optional

from app.orchestration.state_graph import StateGraph, START, END

logger = logging.getLogger(__name__)

# ── Intent keywords (migrated from supervisor.py) ──
_NAV_KEYWORDS = {
    "navigate", "go to", "open page", "show page", "take me to",
    "switch to", "change page", "open the",
}
_CALC_KEYWORDS = {
    "income statement", "balance sheet", "cash flow", "p&l", "profit and loss",
    "trial balance", "financial statement", "forecast", "scenario",
    "calculate", "compute", "margin", "profit", "revenue", "cogs",
    "budget", "variance", "compare period", "ratio", "ebitda",
    "deep analysis", "full analysis", "comprehensive",
}
_INSIGHT_KEYWORDS = {
    "why", "explain", "reason", "anomaly", "unusual", "root cause",
    "detect anomalies", "insight", "what happened", "investigate",
    "trend", "pattern",
}
_REPORT_KEYWORDS = {
    "report", "generate report", "mr report", "management report",
    "export", "pdf", "document",
}
_DECISION_KEYWORDS = {
    "decision", "action", "recommend", "strategy", "what should",
    "cfo verdict", "priority", "invest",
}

_MULTI_STEP_PATTERNS = [
    (r"calculate.*and.*explain", ["calc", "insight"]),
    (r"generate.*report.*with.*narrative", ["calc", "report", "insight"]),
    (r"compare.*and.*analyze", ["calc", "insight"]),
    (r"analyze.*and.*recommend", ["insight", "decision"]),
]


def classify_intent(state: Dict[str, Any]) -> Dict[str, Any]:
    """Classify user message intent for routing."""
    message = state.get("message", "").lower()

    # Check multi-step patterns first
    for pattern, agents in _MULTI_STEP_PATTERNS:
        if re.search(pattern, message, re.IGNORECASE):
            return {"intent": "multi", "target_agents": agents}

    # Navigation → legacy
    for kw in _NAV_KEYWORDS:
        if kw in message:
            return {"intent": "legacy"}

    # Specific agent intents
    for kw in _CALC_KEYWORDS:
        if kw in message:
            return {"intent": "calc"}

    for kw in _INSIGHT_KEYWORDS:
        if kw in message:
            return {"intent": "insight"}

    for kw in _REPORT_KEYWORDS:
        if kw in message:
            return {"intent": "report"}

    for kw in _DECISION_KEYWORDS:
        if kw in message:
            return {"intent": "decision"}

    # Default to legacy (general chat)
    return {"intent": "legacy"}


def route_by_intent(state: Dict[str, Any]) -> str:
    """Router function for conditional edges."""
    intent = state.get("intent", "legacy")
    if intent == "multi":
        return "multi_agent"
    return intent


async def run_calc_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Execute CalcAgent via registry."""
    try:
        from app.agents.registry import registry as agent_registry
        agent = agent_registry.get("calc")
        if not agent:
            return {"agent_result": "CalcAgent not available", "agent_name": "calc"}

        from app.agents.base import AgentTask, AgentContext
        task = AgentTask(
            task_type="calculate",
            instruction=state.get("message", ""),
            parameters=state.get("parameters", {}),
        )
        # Create minimal context
        result = await agent.safe_execute(task, state.get("context"))
        return {
            "agent_result": result.narrative if result else "",
            "agent_data": result.data if result else {},
            "agent_name": "calc",
            "agent_status": result.status if result else "error",
        }
    except Exception as e:
        logger.error("CalcAgent node failed: %s", e)
        return {"agent_result": str(e), "agent_name": "calc", "agent_status": "error"}


async def run_insight_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Execute InsightAgent via registry."""
    try:
        from app.agents.registry import registry as agent_registry
        agent = agent_registry.get("insight")
        if not agent:
            return {"agent_result": "InsightAgent not available", "agent_name": "insight"}

        from app.agents.base import AgentTask
        task = AgentTask(
            task_type="analyze",
            instruction=state.get("message", ""),
            parameters=state.get("parameters", {}),
        )
        result = await agent.safe_execute(task, state.get("context"))
        return {
            "agent_result": result.narrative if result else "",
            "agent_data": result.data if result else {},
            "agent_name": "insight",
            "agent_status": result.status if result else "error",
        }
    except Exception as e:
        logger.error("InsightAgent node failed: %s", e)
        return {"agent_result": str(e), "agent_name": "insight", "agent_status": "error"}


async def run_report_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Execute ReportAgent via registry."""
    try:
        from app.agents.registry import registry as agent_registry
        agent = agent_registry.get("report")
        if not agent:
            return {"agent_result": "ReportAgent not available", "agent_name": "report"}

        from app.agents.base import AgentTask
        task = AgentTask(task_type="report", instruction=state.get("message", ""), parameters={})
        result = await agent.safe_execute(task, state.get("context"))
        return {
            "agent_result": result.narrative if result else "",
            "agent_data": result.data if result else {},
            "agent_name": "report",
        }
    except Exception as e:
        return {"agent_result": str(e), "agent_name": "report", "agent_status": "error"}


async def run_decision_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Execute DecisionAgent via registry."""
    try:
        from app.agents.registry import registry as agent_registry
        agent = agent_registry.get("decision")
        if not agent:
            return {"agent_result": "DecisionAgent not available", "agent_name": "decision"}

        from app.agents.base import AgentTask
        task = AgentTask(task_type="decide", instruction=state.get("message", ""), parameters={})
        result = await agent.safe_execute(task, state.get("context"))
        return {
            "agent_result": result.narrative if result else "",
            "agent_data": result.data if result else {},
            "agent_name": "decision",
        }
    except Exception as e:
        return {"agent_result": str(e), "agent_name": "decision", "agent_status": "error"}


async def run_legacy_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Fallback to legacy agent (general chat via Claude)."""
    return {
        "agent_result": "",  # Will be filled by supervisor's existing chat path
        "agent_name": "legacy",
        "use_legacy_chat": True,
    }


async def run_multi_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Execute multiple agents in sequence, passing accumulated results between them.

    Each agent receives the previous agent's output in accumulated_results,
    enabling chained reasoning (e.g., calc computes metrics → insight explains them).
    """
    target_agents = state.get("target_agents", [])
    results = []
    accumulated = {}  # Shared state passed between chained agents

    from app.agents.registry import registry as agent_registry
    from app.agents.base import AgentTask

    context = state.get("context")

    for agent_name in target_agents:
        agent = agent_registry.get(agent_name)
        if not agent:
            results.append(f"[{agent_name}] Not available")
            continue

        # Pass accumulated results from prior agents via parameters
        params = dict(state.get("parameters", {}))
        params["accumulated_results"] = accumulated
        params["prior_agents"] = [r.split("]")[0].replace("[", "") for r in results]

        task = AgentTask(
            task_type="multi_step",
            instruction=state.get("message", ""),
            parameters=params,
        )

        # If context supports accumulated_results, update it
        if context and hasattr(context, 'accumulated_results'):
            context.accumulated_results.update(accumulated)

        try:
            result = await agent.safe_execute(task, context)
            if result:
                if result.narrative:
                    results.append(f"[{agent_name}] {result.narrative}")
                # Accumulate structured data for next agent
                if result.data:
                    accumulated[agent_name] = result.data
                    accumulated[f"{agent_name}_narrative"] = result.narrative or ""
        except Exception as e:
            results.append(f"[{agent_name}] Error: {e}")

    return {
        "agent_result": "\n\n".join(results),
        "agent_data": accumulated,
        "agent_name": "multi",
        "agent_status": "success" if results else "error",
    }


def input_guardrails(state: Dict[str, Any]) -> Dict[str, Any]:
    """Input safety guardrails — check for PII, prompt injection, malicious content.

    NeMo Guardrails equivalent: validates input before agent processing.
    """
    message = state.get("message", "")
    violations = []

    # PII detection (basic patterns)
    import re
    if re.search(r'\b\d{3}-\d{2}-\d{4}\b', message):  # SSN
        violations.append("pii_ssn")
    if re.search(r'\b\d{16}\b', message):  # Credit card
        violations.append("pii_credit_card")
    if re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', message):
        # Email is OK in financial context, but log it
        pass

    # Prompt injection detection
    injection_patterns = [
        r'ignore\s+(previous|above|all)\s+(instructions|prompts)',
        r'you\s+are\s+now\s+a',
        r'pretend\s+to\s+be',
        r'system\s*:\s*',
        r'<\s*script',
    ]
    for pattern in injection_patterns:
        if re.search(pattern, message, re.IGNORECASE):
            violations.append("prompt_injection")
            break

    # SQL injection in financial queries
    sql_patterns = [r";\s*DROP\s", r";\s*DELETE\s", r"UNION\s+SELECT", r"--\s*$"]
    for pattern in sql_patterns:
        if re.search(pattern, message, re.IGNORECASE):
            violations.append("sql_injection")
            break

    if violations:
        logger.warning("Input guardrails triggered: %s for message: %s", violations, message[:100])
        return {
            "guardrail_violations": violations,
            "guardrail_blocked": True,
            "agent_result": f"Request blocked by safety guardrails: {', '.join(violations)}",
            "agent_name": "guardrails",
            "intent": "__blocked__",
        }

    return {"guardrail_violations": [], "guardrail_blocked": False}


def output_guardrails(state: Dict[str, Any]) -> Dict[str, Any]:
    """Output safety guardrails — validate agent response before returning to user.

    Checks for hallucination markers, sensitive data leakage, and response quality.
    """
    response = state.get("agent_result", "")
    warnings = []

    if not response or len(response.strip()) < 5:
        warnings.append("empty_response")

    # Check for hallucination markers (confident claims about unknown data)
    hallucination_phrases = [
        "I can confirm that", "the records show", "according to our data",
    ]
    if any(p in response.lower() for p in hallucination_phrases):
        # Only flag if we don't actually have data context
        if not state.get("context"):
            warnings.append("potential_hallucination")

    # Check for exposed credentials/keys in response
    import re
    if re.search(r'(api[_-]?key|secret|password|token)\s*[:=]\s*\S+', response, re.IGNORECASE):
        warnings.append("credential_leak")
        # Redact
        response = re.sub(
            r'(api[_-]?key|secret|password|token)\s*[:=]\s*\S+',
            r'\1=***REDACTED***',
            response, flags=re.IGNORECASE,
        )

    return {
        "guardrail_output_warnings": warnings,
        "agent_result": response,  # Potentially redacted
    }


def merge_results(state: Dict[str, Any]) -> Dict[str, Any]:
    """Merge agent results into final response."""
    return {
        "completed": True,
        "response": state.get("agent_result", ""),
    }


# ── Graph Definition ──
_compiled_chat_graph = None


def build_chat_graph() -> StateGraph:
    """Build the chat routing graph.

    Flow: input_guardrails → classify → conditional → [agents] → output_guardrails → merge
    """
    graph = StateGraph(name="chat")

    graph.add_node("input_guard", input_guardrails)
    graph.add_node("classify", classify_intent)
    graph.add_node("calc", run_calc_node)
    graph.add_node("insight", run_insight_node)
    graph.add_node("report", run_report_node)
    graph.add_node("decision", run_decision_node)
    graph.add_node("legacy", run_legacy_node)
    graph.add_node("multi_agent", run_multi_agent_node)
    graph.add_node("output_guard", output_guardrails)
    graph.add_node("merge", merge_results)

    graph.set_entry_point("input_guard")

    # Input guardrails → classify (or block)
    graph.add_conditional_edges("input_guard", lambda s: "__blocked__" if s.get("guardrail_blocked") else "pass", {
        "__blocked__": "merge",  # Skip agents entirely if blocked
        "pass": "classify",
    })

    graph.add_conditional_edges("classify", route_by_intent, {
        "calc": "calc",
        "insight": "insight",
        "report": "report",
        "decision": "decision",
        "legacy": "legacy",
        "multi_agent": "multi_agent",
    })

    # All agent nodes → output_guardrails → merge
    for node in ["calc", "insight", "report", "decision", "legacy", "multi_agent"]:
        graph.add_edge(node, "output_guard")
    graph.add_edge("output_guard", "merge")

    graph.set_finish_point("merge")

    return graph


def compile_chat_graph():
    """Compile and cache the chat graph."""
    global _compiled_chat_graph
    graph = build_chat_graph()
    _compiled_chat_graph = graph.compile()
    logger.info("Chat graph compiled: %d nodes", len(_compiled_chat_graph._nodes))
    return _compiled_chat_graph


def get_chat_graph():
    """Get the compiled chat graph (compile on first access)."""
    global _compiled_chat_graph
    if _compiled_chat_graph is None:
        compile_chat_graph()
    return _compiled_chat_graph
