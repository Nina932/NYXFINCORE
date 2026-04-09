"""
FinAI OS — Data Flywheel (NVIDIA Blueprint Pattern)
=====================================================
Continuously improves AI model performance by learning from production usage.

The flywheel loop:
1. COLLECT — Log every LLM call (prompt, response, model, timing, user feedback)
2. EVALUATE — Score responses using LLM-as-judge or user feedback
3. CURATE — Build training datasets from high-quality interactions
4. OPTIMIZE — Identify which queries could use smaller/faster models
5. DEPLOY — Route optimized queries to fine-tuned or smaller models

This implementation uses the existing telemetry + activity feed infrastructure.
No external dependencies required — runs on the existing Nemotron/Gemini stack.
"""

import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class LLMInteraction:
    """A single LLM interaction logged for the flywheel."""
    interaction_id: str
    timestamp: str
    model: str
    prompt: str
    response: str
    tokens_input: int = 0
    tokens_output: int = 0
    duration_ms: int = 0
    language: str = "en"
    workload_type: str = "general"  # general, analysis, translation, reasoning
    user_feedback: Optional[str] = None  # thumbs_up, thumbs_down, corrected
    quality_score: Optional[float] = None  # 0-1 from LLM-as-judge
    could_use_smaller_model: Optional[bool] = None


@dataclass
class FlywheelStats:
    """Aggregate statistics for the flywheel."""
    total_interactions: int = 0
    by_model: Dict[str, int] = field(default_factory=dict)
    by_workload: Dict[str, int] = field(default_factory=dict)
    by_language: Dict[str, int] = field(default_factory=dict)
    avg_duration_ms: float = 0
    avg_quality_score: float = 0
    positive_feedback_pct: float = 0
    optimization_opportunities: int = 0
    estimated_cost_savings_pct: float = 0


class DataFlywheel:
    """
    Production data flywheel for continuous AI improvement.

    Logs every LLM interaction, evaluates quality, identifies optimization
    opportunities, and builds training datasets for model fine-tuning.
    """

    def __init__(self, max_interactions: int = 10000):
        self._interactions: List[LLMInteraction] = []
        self._max = max_interactions
        self._feedback_counts = {"thumbs_up": 0, "thumbs_down": 0, "corrected": 0}
        self._workload_stats: Dict[str, Dict[str, float]] = defaultdict(lambda: {"count": 0, "total_ms": 0, "total_tokens": 0})

    def log_interaction(
        self,
        interaction_id: str,
        model: str,
        prompt: str,
        response: str,
        tokens_input: int = 0,
        tokens_output: int = 0,
        duration_ms: int = 0,
        language: str = "en",
        workload_type: str = "general",
    ) -> None:
        """Log an LLM interaction for the flywheel."""
        interaction = LLMInteraction(
            interaction_id=interaction_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            model=model,
            prompt=prompt[:500],  # Truncate for storage
            response=response[:500],
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            duration_ms=duration_ms,
            language=language,
            workload_type=workload_type,
        )
        self._interactions.append(interaction)
        if len(self._interactions) > self._max:
            self._interactions = self._interactions[-self._max:]

        # Update workload stats
        ws = self._workload_stats[workload_type]
        ws["count"] += 1
        ws["total_ms"] += duration_ms
        ws["total_tokens"] += tokens_input + tokens_output

    def record_feedback(self, interaction_id: str, feedback: str, corrected_response: str = None) -> bool:
        """Record user feedback on an LLM response."""
        for interaction in reversed(self._interactions):
            if interaction.interaction_id == interaction_id:
                interaction.user_feedback = feedback
                if corrected_response:
                    interaction.response = corrected_response[:500]
                self._feedback_counts[feedback] = self._feedback_counts.get(feedback, 0) + 1
                return True
        return False

    def classify_workloads(self) -> Dict[str, Dict[str, Any]]:
        """
        Analyze interactions to classify workloads and identify optimization opportunities.

        Returns workload profiles with:
        - Average complexity (prompt length, response length)
        - Average duration
        - Model distribution
        - Optimization potential (could a smaller model handle this?)
        """
        workloads: Dict[str, Dict[str, Any]] = {}

        for wtype, stats in self._workload_stats.items():
            if stats["count"] == 0:
                continue

            # Get interactions for this workload
            wl_interactions = [i for i in self._interactions if i.workload_type == wtype]

            avg_prompt_len = sum(len(i.prompt) for i in wl_interactions) / max(len(wl_interactions), 1)
            avg_response_len = sum(len(i.response) for i in wl_interactions) / max(len(wl_interactions), 1)
            avg_duration = stats["total_ms"] / stats["count"]

            # Model distribution
            model_counts: Dict[str, int] = defaultdict(int)
            for i in wl_interactions:
                model_counts[i.model] += 1

            # Optimization potential: short prompts + short responses + fast = could use smaller model
            is_simple = avg_prompt_len < 200 and avg_response_len < 300

            workloads[wtype] = {
                "count": int(stats["count"]),
                "avg_prompt_length": round(avg_prompt_len),
                "avg_response_length": round(avg_response_len),
                "avg_duration_ms": round(avg_duration),
                "avg_tokens_per_call": round(stats["total_tokens"] / stats["count"]),
                "model_distribution": dict(model_counts),
                "optimization_potential": "high" if is_simple else "medium" if avg_prompt_len < 500 else "low",
                "recommended_model": "gemini-2.5-flash" if is_simple else "nemotron-3-super-120b",
            }

        return workloads

    def get_training_candidates(self, min_quality: float = 0.7) -> List[Dict[str, str]]:
        """
        Extract high-quality interactions suitable for fine-tuning a smaller model.

        Returns prompt-response pairs from interactions with positive feedback
        or high quality scores.
        """
        candidates = []
        for interaction in self._interactions:
            # Include if: positive feedback OR high quality score
            is_good = (
                interaction.user_feedback == "thumbs_up" or
                (interaction.quality_score and interaction.quality_score >= min_quality)
            )
            if is_good:
                candidates.append({
                    "prompt": interaction.prompt,
                    "response": interaction.response,
                    "model": interaction.model,
                    "workload_type": interaction.workload_type,
                    "language": interaction.language,
                })
        return candidates

    def get_stats(self) -> Dict[str, Any]:
        """Get flywheel statistics."""
        total = len(self._interactions)
        if total == 0:
            return {"total_interactions": 0, "message": "No interactions logged yet"}

        # Model distribution
        by_model: Dict[str, int] = defaultdict(int)
        by_lang: Dict[str, int] = defaultdict(int)
        total_duration = 0
        quality_scores = []

        for i in self._interactions:
            by_model[i.model] += 1
            by_lang[i.language] += 1
            total_duration += i.duration_ms
            if i.quality_score:
                quality_scores.append(i.quality_score)

        positive = self._feedback_counts.get("thumbs_up", 0)
        negative = self._feedback_counts.get("thumbs_down", 0)
        total_feedback = positive + negative

        workloads = self.classify_workloads()
        optimization_count = sum(1 for w in workloads.values() if w.get("optimization_potential") == "high")

        return {
            "total_interactions": total,
            "by_model": dict(by_model),
            "by_language": dict(by_lang),
            "by_workload": {k: v["count"] for k, v in self._workload_stats.items()},
            "avg_duration_ms": round(total_duration / total),
            "avg_quality_score": round(sum(quality_scores) / max(len(quality_scores), 1), 2),
            "feedback": {
                "total": total_feedback,
                "positive": positive,
                "negative": negative,
                "positive_pct": round(positive / max(total_feedback, 1) * 100, 1),
            },
            "training_candidates": len(self.get_training_candidates()),
            "workload_profiles": workloads,
            "optimization_opportunities": optimization_count,
            "flywheel_health": "active" if total > 10 else "warming_up",
        }

    def export_training_data(self, format: str = "jsonl") -> str:
        """Export training data in JSONL format for fine-tuning."""
        candidates = self.get_training_candidates()
        if format == "jsonl":
            lines = []
            for c in candidates:
                entry = {
                    "messages": [
                        {"role": "system", "content": "You are FinAI, a senior CFO-level financial analyst expert in Georgian 1C accounting and IFRS."},
                        {"role": "user", "content": c["prompt"]},
                        {"role": "assistant", "content": c["response"]},
                    ]
                }
                lines.append(json.dumps(entry, ensure_ascii=False))
            return "\n".join(lines)
        return json.dumps(candidates, ensure_ascii=False, indent=2)


# Singleton
data_flywheel = DataFlywheel()
