"""
FinAI Agent Registry — Singleton that tracks all available agents.

The registry is the Supervisor's lookup table:
  1. Agents self-register on import via `registry.register(agent_instance)`
  2. Supervisor queries `registry.get("calc")` or `registry.for_task_type("calculate")`
  3. Health checks via `registry.status()` for the /api/agents/status endpoint

Thread-safe singleton — import from anywhere, always get the same instance.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.agents.base import BaseAgent, AgentTask

logger = logging.getLogger(__name__)


class AgentRegistry:
    """Central registry of all specialized agents.

    Usage:
        from app.agents.registry import registry

        # Register an agent
        registry.register(CalcAgent())

        # Look up by name
        calc = registry.get("calc")

        # Find agent for a task type
        agent = registry.for_task_type("calculate")

        # List all
        all_agents = registry.all()
    """

    _instance: Optional["AgentRegistry"] = None

    def __new__(cls) -> "AgentRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._agents: Dict[str, "BaseAgent"] = {}
            cls._instance._task_type_map: Dict[str, str] = {}  # task_type → agent_name
            cls._instance._initialized = True
            logger.info("AgentRegistry initialized")
        return cls._instance

    # ── Registration ─────────────────────────────────────────────────────

    def register(self, agent: "BaseAgent") -> None:
        """Register an agent instance by its name.

        Also maps all of the agent's declared capabilities to its name,
        so `for_task_type()` lookups work.
        """
        if agent.name in self._agents:
            logger.warning("Agent '%s' already registered — replacing", agent.name)

        self._agents[agent.name] = agent

        for capability in agent.capabilities:
            if capability in self._task_type_map:
                existing = self._task_type_map[capability]
                if existing != agent.name:
                    logger.warning(
                        "Task type '%s' re-assigned: %s → %s",
                        capability, existing, agent.name,
                    )
            self._task_type_map[capability] = agent.name

        logger.info(
            "Registered agent '%s' with capabilities: %s",
            agent.name, agent.capabilities,
        )

    def unregister(self, name: str) -> None:
        """Remove an agent from the registry."""
        agent = self._agents.pop(name, None)
        if agent:
            # Clean up task type mappings
            self._task_type_map = {
                k: v for k, v in self._task_type_map.items() if v != name
            }
            logger.info("Unregistered agent '%s'", name)

    # ── Lookups ──────────────────────────────────────────────────────────

    def get(self, name: str) -> Optional["BaseAgent"]:
        """Get agent by name. Returns None if not found."""
        return self._agents.get(name)

    def for_task_type(self, task_type: str) -> Optional["BaseAgent"]:
        """Find the agent responsible for a given task type."""
        agent_name = self._task_type_map.get(task_type)
        if agent_name:
            return self._agents.get(agent_name)
        return None

    def route(self, task: "AgentTask") -> Optional["BaseAgent"]:
        """Route a task to the appropriate agent.

        Tries task_type lookup first, then falls back to checking
        each agent's `can_handle()` method.
        """
        # Fast path: direct task_type → agent mapping
        agent = self.for_task_type(task.task_type)
        if agent:
            return agent

        # Slow path: ask each agent if it can handle this task
        for agent in self._agents.values():
            if agent.can_handle(task):
                return agent

        return None

    def all(self) -> List["BaseAgent"]:
        """Return all registered agents."""
        return list(self._agents.values())

    def list_agents(self) -> List["BaseAgent"]:
        """Alias for all() — returns all registered agents."""
        return self.all()

    def names(self) -> List[str]:
        """Return all registered agent names."""
        return list(self._agents.keys())

    # ── Status / Monitoring ──────────────────────────────────────────────

    def status(self) -> Dict:
        """Return registry status for monitoring endpoint."""
        return {
            "total_agents": len(self._agents),
            "agents": [
                {
                    "name": agent.name,
                    "description": agent.description,
                    "capabilities": agent.capabilities,
                    "tool_count": len(agent.tools),
                }
                for agent in self._agents.values()
            ],
            "task_type_routing": dict(self._task_type_map),
        }

    def reset(self) -> None:
        """Clear all registrations (for testing)."""
        self._agents.clear()
        self._task_type_map.clear()
        logger.info("AgentRegistry reset — all agents cleared")

    def __len__(self) -> int:
        return len(self._agents)

    def __contains__(self, name: str) -> bool:
        return name in self._agents

    def __repr__(self) -> str:
        return f"AgentRegistry(agents={list(self._agents.keys())})"


# ── Module-level singleton ───────────────────────────────────────────────
registry = AgentRegistry()
