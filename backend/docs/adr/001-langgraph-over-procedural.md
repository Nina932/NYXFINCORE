# ADR-001: LangGraph Over Procedural Orchestration

**Status**: Accepted
**Date**: 2026-04-12
**Context**: Three competing orchestration frameworks existed in the codebase.

## Decision

Use LangGraph (Framework 2, `app/graph/`) as the single canonical pipeline. Deprecate OrchestratorV3 (`app/orchestrator/orchestrator_v3.py`) and the custom StateGraph (`app/orchestration/`).

## Rationale

- LangGraph is an industry-standard library with community support, documentation, and upgrade path.
- The 10-node graph already includes anomaly detection, what-if simulation, and report generation — more complete than the 7-stage procedural pipeline.
- Conditional routing via `add_conditional_edges` is architecturally superior to procedural if-checks.
- `FinAIState` TypedDict provides type safety for data flowing between nodes.
- The circuit breaker pattern integrates cleanly as a conditional node.

## Consequences

- OrchestratorV3 is marked deprecated and will be removed after migration.
- Any unique logic in OrchestratorV3 not present in LangGraph nodes must be ported.
- All new pipeline features must be added as LangGraph nodes.
