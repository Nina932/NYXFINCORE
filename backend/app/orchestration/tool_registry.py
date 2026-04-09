"""
ToolRegistry — MCP-inspired dynamic tool discovery and execution
================================================================
Agents register their tools here. Other agents or external systems
can discover and execute tools dynamically (Model Context Protocol pattern).
"""

from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class ToolInfo:
    """Metadata about a registered tool."""
    name: str
    description: str
    input_schema: Dict[str, Any]
    owner_agent: str
    tags: List[str] = field(default_factory=list)
    version: str = "1.0"
    handler: Optional[Callable] = field(default=None, repr=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "owner_agent": self.owner_agent,
            "tags": self.tags,
            "version": self.version,
        }


class ToolRegistry:
    """
    Singleton registry for MCP-style tool discovery.

    Agents register their tools on startup. Tools can be discovered
    by name, tag, or free-text query. Execution dispatches to the
    owning agent's handler.
    """

    _instance: Optional["ToolRegistry"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools: Dict[str, ToolInfo] = {}
            cls._instance._by_agent: Dict[str, List[str]] = {}
            cls._instance._by_tag: Dict[str, Set[str]] = {}
            cls._instance._initialized = False
        return cls._instance

    def register_tool(
        self,
        name: str,
        description: str = "",
        input_schema: Optional[Dict[str, Any]] = None,
        owner_agent: str = "unknown",
        tags: Optional[List[str]] = None,
        handler: Optional[Callable] = None,
        version: str = "1.0",
    ) -> None:
        """Register a tool for discovery."""
        tool = ToolInfo(
            name=name,
            description=description,
            input_schema=input_schema or {},
            owner_agent=owner_agent,
            tags=tags or [],
            handler=handler,
            version=version,
        )
        self._tools[name] = tool

        # Index by agent
        self._by_agent.setdefault(owner_agent, []).append(name)

        # Index by tags
        for tag in tool.tags:
            self._by_tag.setdefault(tag, set()).add(name)

    def register_agent_tools(self, agent_name: str, tools: List[Dict[str, Any]], handler: Optional[Callable] = None) -> int:
        """Bulk-register all tools from an agent definition."""
        count = 0
        for tool_def in tools:
            name = tool_def.get("name", "")
            if not name:
                continue
            self.register_tool(
                name=name,
                description=tool_def.get("description", ""),
                input_schema=tool_def.get("input_schema", tool_def.get("parameters", {})),
                owner_agent=agent_name,
                tags=tool_def.get("tags", []),
                handler=handler,
            )
            count += 1
        return count

    def discover(
        self,
        query: str = "",
        tags: Optional[List[str]] = None,
        owner: Optional[str] = None,
        limit: int = 50,
    ) -> List[ToolInfo]:
        """Discover tools by query string, tags, or owner agent."""
        candidates = list(self._tools.values())

        # Filter by owner
        if owner:
            candidates = [t for t in candidates if t.owner_agent == owner]

        # Filter by tags (any match)
        if tags:
            tag_set = set(tags)
            candidates = [t for t in candidates if tag_set.intersection(t.tags)]

        # Filter by query (name or description match)
        if query:
            q = query.lower()
            candidates = [
                t for t in candidates
                if q in t.name.lower() or q in t.description.lower()
            ]

        return candidates[:limit]

    def get_tool(self, name: str) -> Optional[ToolInfo]:
        """Get a specific tool by exact name."""
        return self._tools.get(name)

    def list_by_agent(self, agent_name: str) -> List[ToolInfo]:
        """Get all tools owned by an agent."""
        names = self._by_agent.get(agent_name, [])
        return [self._tools[n] for n in names if n in self._tools]

    def list_all_tags(self) -> List[str]:
        """Get all unique tags across all tools."""
        return sorted(self._by_tag.keys())

    async def execute(self, tool_name: str, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Any:
        """Execute a tool by name, dispatching to its handler."""
        tool = self._tools.get(tool_name)
        if not tool:
            raise ValueError(f"Tool '{tool_name}' not found in registry")
        if not tool.handler:
            raise ValueError(f"Tool '{tool_name}' has no handler registered")

        import inspect
        if inspect.iscoroutinefunction(tool.handler):
            return await tool.handler(tool_name, params, context or {})
        else:
            return tool.handler(tool_name, params, context or {})

    def status(self) -> Dict[str, Any]:
        """Get registry status for monitoring."""
        return {
            "total_tools": len(self._tools),
            "agents": {
                agent: len(tools) for agent, tools in self._by_agent.items()
            },
            "tags": {tag: len(names) for tag, names in self._by_tag.items()},
            "tools": [t.to_dict() for t in self._tools.values()],
        }

    def reset(self):
        """Clear all registered tools (for testing)."""
        self._tools.clear()
        self._by_agent.clear()
        self._by_tag.clear()


# Singleton instance
tool_registry = ToolRegistry()
