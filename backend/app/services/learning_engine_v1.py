"""
learning_engine.py -- Persistent Learning Pipeline
====================================================
Converts feedback, corrections, and classification results into
permanent knowledge that improves future accuracy.

Pipeline:
  1. Record classification results with confidence
  2. Record user/LLM corrections (override previous)
  3. Sync learned classifications to KG as entities
  4. Track accuracy metrics per account prefix
  5. Provide cached lookups for SemanticEnricher

Phase G-2 of the FinAI Full System Upgrade.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ClassificationFeedback:
    """A single piece of feedback about an account classification."""
    account_code: str
    original_classification: Dict[str, Any]
    corrected_classification: Optional[Dict[str, Any]] = None
    feedback_type: str = "auto"  # "auto" | "user_correction" | "llm_refinement"
    confidence: float = 0.0
    source: str = ""


@dataclass
class AccuracyMetrics:
    """Accuracy metrics for a classification prefix or category."""
    prefix: str
    total_classifications: int = 0
    confirmed_correct: int = 0
    corrected: int = 0

    @property
    def accuracy_pct(self) -> float:
        if self.total_classifications == 0:
            return 100.0
        return (self.confirmed_correct / self.total_classifications) * 100

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prefix": self.prefix,
            "total_classifications": self.total_classifications,
            "confirmed_correct": self.confirmed_correct,
            "corrected": self.corrected,
            "accuracy_pct": round(self.accuracy_pct, 2),
        }


class LearningEngine:
    """
    Persistent learning pipeline for the FinAI system.

    In-memory cache provides instant lookups. DB persistence (via
    LearningRecord model) ensures cross-session learning. KG sync
    makes learned classifications available for semantic search.
    """

    def __init__(self):
        self._classification_cache: Dict[str, Dict] = {}  # account_code -> classification
        self._confidence_cache: Dict[str, float] = {}     # account_code -> confidence
        self._prefix_accuracy: Dict[str, AccuracyMetrics] = {}
        self._corrections_count: int = 0

    def record_classification(
        self,
        account_code: str,
        classification: Dict[str, Any],
        confidence: float = 0.5,
        source: str = "semantic_enricher",
    ) -> None:
        """Record a classification result for accuracy tracking."""
        code = account_code.strip()
        # Only update if new confidence is higher or no existing
        existing_conf = self._confidence_cache.get(code, 0.0)
        if confidence >= existing_conf:
            self._classification_cache[code] = classification
            self._confidence_cache[code] = confidence

        # Update prefix accuracy
        prefix = code[:2] if len(code) >= 2 else code[:1]
        if prefix not in self._prefix_accuracy:
            self._prefix_accuracy[prefix] = AccuracyMetrics(prefix=prefix)
        self._prefix_accuracy[prefix].total_classifications += 1
        if source != "user_correction":
            self._prefix_accuracy[prefix].confirmed_correct += 1

    def record_correction(
        self,
        account_code: str,
        original: Dict[str, Any],
        corrected: Dict[str, Any],
        source: str = "user",
    ) -> None:
        """Record a user or LLM correction, updating both cache and metrics."""
        code = account_code.strip()
        # Corrections always get high confidence
        correction_confidence = 0.95

        self._classification_cache[code] = corrected
        self._confidence_cache[code] = correction_confidence
        self._corrections_count += 1

        # Update prefix accuracy
        prefix = code[:2] if len(code) >= 2 else code[:1]
        if prefix not in self._prefix_accuracy:
            self._prefix_accuracy[prefix] = AccuracyMetrics(prefix=prefix)
        self._prefix_accuracy[prefix].corrected += 1

    def get_cached_classification(self, account_code: str) -> Optional[Dict]:
        """Return learned classification if confidence >= 0.8."""
        code = account_code.strip()
        conf = self._confidence_cache.get(code, 0.0)
        if conf >= 0.8:
            return self._classification_cache.get(code)
        return None

    async def ingest_feedback(self, db) -> int:
        """
        Scan AgentMemory (type='correction') and Feedback (type='correction')
        for unprocessed items. Convert to learned classifications.
        Returns number of new classifications learned.
        """
        count = 0
        try:
            from sqlalchemy import select
            from app.models.all_models import AgentMemory, Feedback

            # Check AgentMemory for corrections
            result = await db.execute(
                select(AgentMemory).where(
                    AgentMemory.memory_type == "correction",
                    AgentMemory.is_active == True,
                )
            )
            memories = result.scalars().all()
            for mem in memories:
                if mem.context and isinstance(mem.context, dict):
                    code = mem.context.get("account_code", "")
                    if code:
                        self.record_correction(
                            code,
                            original=mem.context.get("original", {}),
                            corrected=mem.context.get("corrected", mem.context),
                            source="agent_memory",
                        )
                        count += 1

            # Check Feedback for corrections
            result = await db.execute(
                select(Feedback).where(Feedback.feedback_type == "correction")
            )
            feedbacks = result.scalars().all()
            for fb in feedbacks:
                if fb.correction_text:
                    # Parse simple "code: classification" format
                    parts = fb.correction_text.split(":", 1)
                    if len(parts) == 2:
                        code = parts[0].strip()
                        if code and len(code) <= 20:
                            self.record_correction(
                                code,
                                original={},
                                corrected={"description": parts[1].strip()},
                                source="user_feedback",
                            )
                            count += 1
        except Exception as e:
            logger.warning("Failed to ingest feedback: %s", e)

        return count

    def sync_to_kg(self) -> int:
        """Push learned classifications as KG entities. Returns count of entities added."""
        count = 0
        try:
            from app.services.knowledge_graph import knowledge_graph
            if not knowledge_graph.is_built:
                knowledge_graph.build()

            for code, classification in self._classification_cache.items():
                conf = self._confidence_cache.get(code, 0.0)
                if conf < 0.8:
                    continue

                entity_id = f"learned_classification:{code}"
                # Check if already exists
                if entity_id in knowledge_graph._entities:
                    continue

                from app.services.knowledge_graph import KnowledgeEntity
                entity = KnowledgeEntity(
                    entity_id=entity_id,
                    entity_type="learned_classification",
                    label_en=f"Learned: {code} -> {classification.get('description', classification.get('bs_pl', 'unknown'))}",
                    properties={
                        "account_code": code,
                        "classification": classification,
                        "confidence": conf,
                        "source": "learning_engine",
                    },
                )
                knowledge_graph._entities[entity_id] = entity
                # Update type index
                if "learned_classification" not in knowledge_graph._index_by_type:
                    knowledge_graph._index_by_type["learned_classification"] = []
                knowledge_graph._index_by_type["learned_classification"].append(entity_id)
                count += 1

        except Exception as e:
            logger.warning("Failed to sync to KG: %s", e)

        return count

    def accuracy_report(self) -> Dict[str, Any]:
        """Return accuracy metrics grouped by prefix and overall."""
        prefix_data = {}
        total_cls = 0
        total_correct = 0
        total_corrected = 0

        for prefix, metrics in self._prefix_accuracy.items():
            prefix_data[prefix] = metrics.to_dict()
            total_cls += metrics.total_classifications
            total_correct += metrics.confirmed_correct
            total_corrected += metrics.corrected

        overall_accuracy = (total_correct / total_cls * 100) if total_cls > 0 else 100.0

        return {
            "total_classifications": total_cls,
            "total_confirmed_correct": total_correct,
            "total_corrected": total_corrected,
            "overall_accuracy_pct": round(overall_accuracy, 2),
            "cached_accounts": len(self._classification_cache),
            "high_confidence_accounts": sum(1 for c in self._confidence_cache.values() if c >= 0.8),
            "by_prefix": prefix_data,
        }

    async def export_learning_data(self) -> List[Dict]:
        """Export all learning records for backup/transfer."""
        records = []
        for code in self._classification_cache:
            records.append({
                "account_code": code,
                "classification": self._classification_cache[code],
                "confidence": self._confidence_cache.get(code, 0.0),
                "exported_at": datetime.now(timezone.utc).isoformat(),
            })
        return records


# Module singleton
learning_engine = LearningEngine()
