"""
FinAI Orchestration — LangGraph-inspired State Graph + MCP Tool Registry
========================================================================
Custom lightweight state-graph orchestration system that provides:
  - StateGraph: define nodes + edges + conditional routing (same API as LangGraph)
  - CompiledGraph: execute graphs with checkpointing, streaming, parallel nodes
  - ToolRegistry: MCP-inspired dynamic tool discovery and execution
  - ChatGraph: Graph-based chat routing (replaces keyword routing in supervisor)
"""

from app.orchestration.state_graph import StateGraph, START, END
from app.orchestration.compiled_graph import CompiledGraph
from app.orchestration.tool_registry import ToolRegistry, tool_registry

__all__ = [
    "StateGraph", "START", "END",
    "CompiledGraph",
    "ToolRegistry", "tool_registry",
]
