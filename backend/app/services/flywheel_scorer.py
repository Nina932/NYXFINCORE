"""
FlywheelScorer — LLM-as-judge auto-scoring for agent responses
==============================================================
Scores every agent interaction 1-5 on accuracy, relevance, completeness.
Uses 3-tier fallback: Claude → Ollama → heuristic.
"""

from __future__ import annotations
import json
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

SCORING_PROMPT = """Rate this financial AI assistant response on a scale of 1-5.

Criteria:
- Accuracy: Are numbers and financial terms correct?
- Relevance: Does the response answer the user's question?
- Completeness: Does it provide actionable insight, not just data?
- Specificity: Does it reference specific metrics, periods, or accounts?

User question: {prompt}

AI response (first 800 chars): {response}

Return ONLY a JSON object: {{"score": <1-5>, "reasoning": "<one sentence>"}}"""


class FlywheelScorer:
    """Scores agent responses using LLM-as-judge with heuristic fallback."""

    async def score(self, prompt: str, response: str, model: str = "") -> dict:
        """Score a prompt/response pair. Returns {score, reasoning, method}."""
        # Try LLM scoring first
        try:
            result = await self._score_with_llm(prompt, response)
            if result:
                return {**result, "method": "llm_judge"}
        except Exception as e:
            logger.debug("LLM scoring failed: %s", e)

        # Fallback to heuristic
        result = self._score_heuristic(prompt, response)
        return {**result, "method": "heuristic"}

    async def _score_with_llm(self, prompt: str, response: str) -> Optional[dict]:
        """Score using Claude/Ollama as judge."""
        try:
            from app.config import settings
            import anthropic

            client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
            scoring_msg = SCORING_PROMPT.format(
                prompt=prompt[:400],
                response=response[:800],
            )
            result = await client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=100,
                messages=[{"role": "user", "content": scoring_msg}],
            )
            text = result.content[0].text.strip()
            # Parse JSON from response
            match = re.search(r'\{[^}]+\}', text)
            if match:
                data = json.loads(match.group())
                score = max(1, min(5, int(data.get("score", 3))))
                return {"score": score, "reasoning": data.get("reasoning", "")}
        except Exception as e:
            logger.debug("Claude scoring failed: %s", e)

        # Try Ollama fallback
        try:
            from app.services.local_llm import local_llm
            scoring_msg = SCORING_PROMPT.format(
                prompt=prompt[:300],
                response=response[:500],
            )
            result = await local_llm.chat(scoring_msg, system="You are a response quality scorer. Return only JSON.")
            if result:
                text = result if isinstance(result, str) else str(result)
                match = re.search(r'\{[^}]+\}', text)
                if match:
                    data = json.loads(match.group())
                    score = max(1, min(5, int(data.get("score", 3))))
                    return {"score": score, "reasoning": data.get("reasoning", "")}
        except Exception:
            pass

        return None

    def _score_heuristic(self, prompt: str, response: str) -> dict:
        """Fast heuristic scoring when LLM is unavailable."""
        score = 1
        reasons = []

        # Length check (substantive response)
        if len(response) > 100:
            score += 1
            reasons.append("substantive length")

        # Contains numbers/financials
        if re.search(r'[\d,]+\.?\d*', response):
            score += 1
            reasons.append("contains numbers")

        # Contains financial terms
        fin_terms = ["revenue", "profit", "margin", "cogs", "ebitda", "cash", "asset", "liability"]
        if any(t in response.lower() for t in fin_terms):
            score += 1
            reasons.append("financial terms")

        # Doesn't contain error markers
        error_markers = ["error", "failed", "unavailable", "cannot", "I don't have"]
        if not any(m in response.lower() for m in error_markers):
            score += 1
            reasons.append("no errors")

        return {"score": min(5, score), "reasoning": "; ".join(reasons) if reasons else "minimal response"}


flywheel_scorer = FlywheelScorer()
