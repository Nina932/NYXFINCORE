"""
CompiledGraph — Executable graph with async support, checkpointing, streaming
=============================================================================
Walks the graph from START, executes node functions, follows edges (conditional
or unconditional), supports parallel execution and human-in-the-loop interrupts.
"""

from __future__ import annotations
import asyncio
import inspect
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Set, Tuple, Union

from app.orchestration.state_graph import NodeDef, START, END

logger = logging.getLogger(__name__)


@dataclass
class GraphCheckpoint:
    """Snapshot of graph execution state at a given node."""
    run_id: str
    node_name: str
    state: Dict[str, Any]
    timestamp: float
    step_index: int


@dataclass
class GraphRunResult:
    """Result of a complete graph execution."""
    run_id: str
    final_state: Dict[str, Any]
    steps: List[Tuple[str, float]]  # (node_name, duration_ms)
    total_ms: float
    interrupted: bool = False
    interrupt_reason: Optional[str] = None


class CompiledGraph:
    """
    Compiled, executable state graph.

    Supports:
    - ainvoke(): async single-shot execution, returns final state
    - astream(): async generator yielding (node_name, state) after each step
    - Parallel node execution via asyncio.gather
    - Human-in-the-loop: nodes can return {"__interrupt__": "reason"} to pause
    - Checkpointing: stores state after each node for debugging/replay
    """

    def __init__(
        self,
        name: str,
        nodes: Dict[str, NodeDef],
        adjacency: Dict[str, List],
        entry_point: str,
        finish_points: Set[str],
        parallel_groups: Dict[str, List[str]],
    ):
        self.name = name
        self._nodes = nodes
        self._adjacency = adjacency
        self._entry_point = entry_point
        self._finish_points = finish_points
        self._parallel_groups = parallel_groups
        self._checkpoints: Dict[str, List[GraphCheckpoint]] = {}
        self._max_steps = 50  # Safety limit

    async def _execute_node(self, node_name: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single node function, handling sync/async."""
        node_def = self._nodes.get(node_name)
        if not node_def:
            raise ValueError(f"Node '{node_name}' not found in compiled graph")

        fn = node_def.fn
        if inspect.iscoroutinefunction(fn):
            result = await fn(state)
        else:
            result = fn(state)

        if not isinstance(result, dict):
            raise TypeError(f"Node '{node_name}' must return a dict, got {type(result)}")

        return result

    async def _execute_parallel(self, node_names: List[str], state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute multiple nodes in parallel, merge their state updates."""
        tasks = [self._execute_node(name, dict(state)) for name in node_names]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        merged = {}
        for name, result in zip(node_names, results):
            if isinstance(result, Exception):
                logger.error("Parallel node '%s' failed: %s", name, result)
                merged[f"_error_{name}"] = str(result)
            else:
                merged.update(result)

        return merged

    def _get_next_nodes(self, current_node: str, state: Dict[str, Any]) -> List[str]:
        """Determine next node(s) from adjacency list."""
        successors = self._adjacency.get(current_node, [])
        next_nodes = []

        for successor in successors:
            if isinstance(successor, str):
                next_nodes.append(successor)
            elif isinstance(successor, tuple):
                # Conditional edge: (router_fn, path_map)
                router_fn, path_map = successor
                try:
                    if inspect.iscoroutinefunction(router_fn):
                        # Can't await here synchronously — will be handled in async path
                        key = router_fn  # Store for async resolution
                    else:
                        key = router_fn(state)
                    if isinstance(key, str):
                        target = path_map.get(key, path_map.get("__default__"))
                        if target:
                            next_nodes.append(target)
                        else:
                            logger.warning("Router returned '%s' but no matching path in %s", key, list(path_map.keys()))
                except Exception as e:
                    logger.error("Router function failed: %s", e)

        return next_nodes

    async def _resolve_next_nodes_async(self, current_node: str, state: Dict[str, Any]) -> List[str]:
        """Async version of _get_next_nodes that can await router functions."""
        successors = self._adjacency.get(current_node, [])
        next_nodes = []

        for successor in successors:
            if isinstance(successor, str):
                next_nodes.append(successor)
            elif isinstance(successor, tuple):
                router_fn, path_map = successor
                try:
                    if inspect.iscoroutinefunction(router_fn):
                        key = await router_fn(state)
                    else:
                        key = router_fn(state)
                    if isinstance(key, str):
                        target = path_map.get(key, path_map.get("__default__"))
                        if target:
                            next_nodes.append(target)
                except Exception as e:
                    logger.error("Router function failed: %s", e)

        return next_nodes

    async def ainvoke(self, initial_state: Dict[str, Any]) -> GraphRunResult:
        """Execute the full graph asynchronously. Returns final state."""
        run_id = uuid.uuid4().hex[:12]
        state = dict(initial_state)
        state["__run_id__"] = run_id
        steps: List[Tuple[str, float]] = []
        t0 = time.time()

        current_nodes = [self._entry_point]
        step_count = 0
        self._checkpoints[run_id] = []

        while current_nodes and step_count < self._max_steps:
            step_count += 1

            # Filter out END
            active = [n for n in current_nodes if n != END]
            if not active:
                break

            # Check for parallel groups
            parallel_group = None
            for group_name, group_nodes in self._parallel_groups.items():
                if set(active) == set(group_nodes):
                    parallel_group = group_name
                    break

            if parallel_group and len(active) > 1:
                # Parallel execution
                t_step = time.time()
                update = await self._execute_parallel(active, state)
                dur = (time.time() - t_step) * 1000
                state.update(update)
                for n in active:
                    steps.append((n, dur / len(active)))

                # Get next nodes from all parallel nodes
                all_next = []
                for n in active:
                    all_next.extend(await self._resolve_next_nodes_async(n, state))
                current_nodes = list(set(all_next))
            else:
                # Sequential execution (one node at a time)
                node_name = active[0]
                t_step = time.time()

                try:
                    update = await self._execute_node(node_name, state)
                    dur = (time.time() - t_step) * 1000
                    steps.append((node_name, dur))

                    # Check for interrupt
                    if "__interrupt__" in update:
                        reason = update.pop("__interrupt__")
                        state.update(update)
                        self._checkpoints[run_id].append(GraphCheckpoint(
                            run_id=run_id, node_name=node_name,
                            state=dict(state), timestamp=time.time(),
                            step_index=step_count,
                        ))
                        return GraphRunResult(
                            run_id=run_id, final_state=state, steps=steps,
                            total_ms=(time.time() - t0) * 1000,
                            interrupted=True, interrupt_reason=reason,
                        )

                    state.update(update)
                except Exception as e:
                    logger.error("Node '%s' failed: %s", node_name, e)
                    state[f"_error_{node_name}"] = str(e)
                    dur = (time.time() - t_step) * 1000
                    steps.append((node_name, dur))

                # Checkpoint
                self._checkpoints[run_id].append(GraphCheckpoint(
                    run_id=run_id, node_name=node_name,
                    state=dict(state), timestamp=time.time(),
                    step_index=step_count,
                ))

                # Determine next nodes
                current_nodes = await self._resolve_next_nodes_async(node_name, state)

        total_ms = (time.time() - t0) * 1000
        logger.info("Graph '%s' run %s completed in %.0fms (%d steps)", self.name, run_id, total_ms, step_count)

        return GraphRunResult(
            run_id=run_id, final_state=state, steps=steps, total_ms=total_ms,
        )

    async def astream(self, initial_state: Dict[str, Any]) -> AsyncGenerator[Tuple[str, Dict[str, Any]], None]:
        """Execute graph and yield (node_name, state_after_node) after each step."""
        run_id = uuid.uuid4().hex[:12]
        state = dict(initial_state)
        state["__run_id__"] = run_id

        current_nodes = [self._entry_point]
        step_count = 0

        while current_nodes and step_count < self._max_steps:
            step_count += 1
            active = [n for n in current_nodes if n != END]
            if not active:
                break

            node_name = active[0]
            try:
                update = await self._execute_node(node_name, state)
                if "__interrupt__" in update:
                    reason = update.pop("__interrupt__")
                    state.update(update)
                    yield (f"__interrupt__:{node_name}", state)
                    return
                state.update(update)
            except Exception as e:
                state[f"_error_{node_name}"] = str(e)

            yield (node_name, dict(state))
            current_nodes = await self._resolve_next_nodes_async(node_name, state)

    def get_checkpoints(self, run_id: str) -> List[GraphCheckpoint]:
        """Get execution checkpoints for a given run."""
        return self._checkpoints.get(run_id, [])

    async def resume(self, run_id: str, state_update: Dict[str, Any]) -> GraphRunResult:
        """Resume an interrupted graph from the last checkpoint."""
        checkpoints = self._checkpoints.get(run_id)
        if not checkpoints:
            raise ValueError(f"No checkpoints found for run {run_id}")

        last = checkpoints[-1]
        state = dict(last.state)
        state.update(state_update)

        # Get next nodes from the interrupted node
        current_nodes = await self._resolve_next_nodes_async(last.node_name, state)

        # Continue execution
        steps = []
        t0 = time.time()
        step_count = last.step_index

        while current_nodes and step_count < self._max_steps:
            step_count += 1
            active = [n for n in current_nodes if n != END]
            if not active:
                break

            node_name = active[0]
            t_step = time.time()
            try:
                update = await self._execute_node(node_name, state)
                dur = (time.time() - t_step) * 1000
                steps.append((node_name, dur))
                if "__interrupt__" in update:
                    reason = update.pop("__interrupt__")
                    state.update(update)
                    return GraphRunResult(
                        run_id=run_id, final_state=state, steps=steps,
                        total_ms=(time.time() - t0) * 1000,
                        interrupted=True, interrupt_reason=reason,
                    )
                state.update(update)
            except Exception as e:
                state[f"_error_{node_name}"] = str(e)
                dur = (time.time() - t_step) * 1000
                steps.append((node_name, dur))

            current_nodes = await self._resolve_next_nodes_async(node_name, state)

        return GraphRunResult(
            run_id=run_id, final_state=state, steps=steps,
            total_ms=(time.time() - t0) * 1000,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for API/visualization."""
        nodes = []
        for name, nd in self._nodes.items():
            nodes.append({"name": name, **nd.metadata})
        edges = []
        for source, successors in self._adjacency.items():
            for s in successors:
                if isinstance(s, str):
                    edges.append({"source": source, "target": s, "type": "direct"})
                elif isinstance(s, tuple):
                    _, path_map = s
                    for cond, target in path_map.items():
                        edges.append({"source": source, "target": target, "type": "conditional", "condition": cond})
        return {
            "name": self.name,
            "nodes": nodes,
            "edges": edges,
            "entry_point": self._entry_point,
            "finish_points": list(self._finish_points),
            "parallel_groups": self._parallel_groups,
        }
