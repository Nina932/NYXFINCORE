# ADR-005: Template Narratives as Primary, LLM as Secondary

**Status**: Accepted
**Date**: 2026-04-12
**Context**: The system must produce financial narratives even when no LLM API is available.

## Decision

Template-based narratives are the primary output. LLM-generated narratives are an enhancement layer that enriches templates when available.

## Rationale

- **Reliability**: LLM APIs have latency spikes, rate limits, and outages. Financial reports cannot depend on external API availability.
- **Cost**: Claude/GPT API calls cost money. Template narratives are free.
- **Auditability**: Template outputs are deterministic and reproducible. LLM outputs vary between runs.
- **Speed**: Templates generate in < 1ms. LLM calls take 2-30 seconds.
- **Georgian language**: The template system supports Georgian (ქართული) output natively. Not all LLMs handle Georgian well.

## Implementation

The `reasoner_node` in `app/graph/nodes.py` implements a 3-tier fallback:

1. **Tier 1 — Claude API**: Best quality, highest cost. Uses Anthropic API.
2. **Tier 2 — NVIDIA Gemma/Ollama**: Local or hosted, lower cost.
3. **Tier 3 — Template fallback**: Always available, deterministic, zero cost.

All tiers produce the same output structure: `{summary, insights, confidence}`. The `llm_model_used` field in the response indicates which tier was used.

## Consequences

- Templates must be maintained alongside LLM prompts.
- Template quality sets the floor — the system is useful even without any LLM.
- LLM output is marked with the model used, enabling quality comparison.
- When the circuit breaker degrades to HALF_OPEN, LLM output is marked `provisional`.
