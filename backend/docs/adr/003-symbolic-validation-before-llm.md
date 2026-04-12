# ADR-003: Symbolic Constraint Validation Before LLM Reasoning

**Status**: Accepted
**Date**: 2026-04-12
**Context**: LLMs can hallucinate financial numbers. We need mathematical guarantees before narrative generation.

## Decision

All GAAP integrity checks (BS equation, TB balance, revenue consistency) run as deterministic, symbolic validation *before* the LLM reasoning node. The LLM explains validated numbers — it never computes or validates them.

## Rationale

- An LLM told "assets are 1M, liabilities 500K, equity 300K" might not flag the 200K imbalance.
- Symbolic checks are exact, reproducible, and auditable. LLM checks are probabilistic.
- The circuit breaker pattern (ADR-001) halts the pipeline if symbolic checks fail, preventing the LLM from generating narratives on corrupt data.
- This separation of concerns (compute vs. explain) is critical for financial product liability.

## Implementation

1. **Reconstruction engine** (`insight_engine` node): Validates completeness, flags missing fields.
2. **Circuit breaker** (`circuit_breaker_check` node): Checks BS equation, NaN/Inf, completeness threshold.
3. **Reasoner** (`reasoner` node): Only runs if circuit breaker passes. Receives pre-validated, pre-computed metrics.

## Consequences

- The LLM never sees raw, unvalidated data.
- Pipeline may halt on bad data — this is a feature, not a bug.
- LLM prompts include pre-computed metrics as context, reducing hallucination risk.
