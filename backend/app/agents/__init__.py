"""FinAI Multi-Agent System — Specialized agents for financial intelligence.

Agents are registered on import. The Supervisor routes tasks to them.

Usage:
    from app.agents import supervisor, registry

    # In WebSocket handler:
    await supervisor.stream_chat(message, history, db, ws)

    # Check registered agents:
    print(registry.status())
"""

from app.agents.registry import registry


def initialize_agents() -> None:
    """Register all specialized agents with the registry.

    Called once during app startup (in main.py lifespan).
    Safe to call multiple times — agents with same name are replaced.
    """
    from app.agents.legacy_agent import LegacyAgent
    from app.agents.calc_agent import CalcAgent
    from app.agents.data_agent import DataAgent
    from app.agents.insight_agent import InsightAgent
    from app.agents.report_agent import ReportAgent

    # Register all 5 specialized agents
    agents = [LegacyAgent(), CalcAgent(), DataAgent(), InsightAgent(), ReportAgent()]
    for agent in agents:
        registry.register(agent)

    # Auto-register all agent tools into MCP-style ToolRegistry
    try:
        from app.orchestration.tool_registry import tool_registry
        for agent in agents:
            if hasattr(agent, 'tools') and agent.tools:
                count = tool_registry.register_agent_tools(
                    agent_name=agent.name,
                    tools=agent.tools,
                    handler=agent.safe_execute if hasattr(agent, 'safe_execute') else None,
                )
                if count > 0:
                    import logging
                    logging.getLogger(__name__).info("ToolRegistry: %d tools from %s", count, agent.name)
    except Exception:
        pass  # ToolRegistry is optional

    # Compile chat graph
    try:
        from app.orchestration.chat_graph import compile_chat_graph
        compile_chat_graph()
    except Exception:
        pass
