"""
FinAI v2 Learning Engine — DB-persisted classification learning.
================================================================
Replaces in-memory Dict cache with async SQLAlchemy CRUD against
the existing LearningRecord model.

Key changes from v1:
- Classifications persist across server restarts via DB
- In-memory cache is a hot-path optimization (loaded from DB on first access)
- Corrections always have confidence 0.95
- sync_to_kg() marks records as applied_to_kg=True to avoid re-sync

Public API:
    from app.services.v2.learning_engine import learning_engine
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass
class AccuracyMetrics:
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
    DB-persisted learning engine.

    Uses LearningRecord table for persistence. In-memory cache provides
    fast lookups for hot-path classification queries.
    """

    def __init__(self):
        self._cache_loaded = False
        self._classification_cache: Dict[str, Dict] = {}
        self._confidence_cache: Dict[str, float] = {}

    async def _ensure_cache(self, db: AsyncSession) -> None:
        """Load cache from DB on first access."""
        if self._cache_loaded:
            return

        from app.models.all_models import LearningRecord

        try:
            result = await db.execute(
                select(LearningRecord).where(
                    LearningRecord.is_active == True,
                    LearningRecord.confidence >= 0.5,
                )
            )
            records = result.scalars().all()
            for r in records:
                code = r.account_code
                existing_conf = self._confidence_cache.get(code, 0.0)
                if r.confidence >= existing_conf:
                    self._classification_cache[code] = r.classification or {}
                    self._confidence_cache[code] = r.confidence or 0.0

            self._cache_loaded = True
            logger.info("Learning cache loaded: %d records from DB", len(records))
        except Exception as e:
            logger.warning("Failed to load learning cache from DB: %s", e)

    async def record_classification(
        self,
        account_code: str,
        classification: Dict[str, Any],
        confidence: float = 0.5,
        source: str = "semantic_enricher",
        db: AsyncSession = None,
    ) -> None:
        """Record a classification result — persists to DB and updates cache."""
        code = account_code.strip()
        if not code:
            return

        # Update in-memory cache
        existing_conf = self._confidence_cache.get(code, 0.0)
        if confidence >= existing_conf:
            self._classification_cache[code] = classification
            self._confidence_cache[code] = confidence

        # Persist to DB
        if db:
            try:
                from app.models.all_models import LearningRecord

                # Upsert: check if record exists for this account_code
                existing = await db.execute(
                    select(LearningRecord).where(
                        LearningRecord.account_code == code,
                        LearningRecord.is_active == True,
                    )
                )
                record = existing.scalar_one_or_none()

                if record:
                    if confidence >= (record.confidence or 0):
                        record.classification = classification
                        record.confidence = confidence
                        record.source = source
                        record.feedback_type = "auto"
                else:
                    record = LearningRecord(
                        account_code=code,
                        classification=classification,
                        confidence=confidence,
                        source=source,
                        feedback_type="auto",
                    )
                    db.add(record)

                await db.flush()
            except Exception as e:
                logger.warning("Failed to persist classification for %s: %s", code, e)

    async def record_correction(
        self,
        account_code: str,
        original: Dict[str, Any],
        corrected: Dict[str, Any],
        source: str = "user",
        db: AsyncSession = None,
    ) -> None:
        """Record a correction — always high confidence (0.95)."""
        code = account_code.strip()
        correction_confidence = 0.95

        # Update cache
        self._classification_cache[code] = corrected
        self._confidence_cache[code] = correction_confidence

        # Persist to DB
        if db:
            try:
                from app.models.all_models import LearningRecord

                existing = await db.execute(
                    select(LearningRecord).where(
                        LearningRecord.account_code == code,
                        LearningRecord.is_active == True,
                    )
                )
                record = existing.scalar_one_or_none()

                if record:
                    record.classification = corrected
                    record.confidence = correction_confidence
                    record.source = source
                    record.feedback_type = "user_correction"
                else:
                    record = LearningRecord(
                        account_code=code,
                        classification=corrected,
                        confidence=correction_confidence,
                        source=source,
                        feedback_type="user_correction",
                    )
                    db.add(record)

                await db.flush()
                logger.info("Correction persisted for %s (source=%s)", code, source)
            except Exception as e:
                logger.warning("Failed to persist correction for %s: %s", code, e)

    async def get_cached_classification(
        self, account_code: str, db: AsyncSession = None
    ) -> Optional[Dict]:
        """Return learned classification if confidence >= 0.8."""
        if db:
            await self._ensure_cache(db)

        code = account_code.strip()
        conf = self._confidence_cache.get(code, 0.0)
        if conf >= 0.8:
            return self._classification_cache.get(code)
        return None

    async def accuracy_report(self, db: AsyncSession) -> Dict[str, Any]:
        """Compute accuracy metrics from DB records."""
        from app.models.all_models import LearningRecord

        # Total counts
        total = (await db.execute(
            select(func.count()).select_from(LearningRecord).where(LearningRecord.is_active == True)
        )).scalar() or 0

        corrections = (await db.execute(
            select(func.count()).select_from(LearningRecord).where(
                LearningRecord.feedback_type == "user_correction",
                LearningRecord.is_active == True,
            )
        )).scalar() or 0

        auto = total - corrections
        overall_accuracy = (auto / total * 100) if total > 0 else 100.0

        # High confidence count
        high_conf = (await db.execute(
            select(func.count()).select_from(LearningRecord).where(
                LearningRecord.confidence >= 0.8,
                LearningRecord.is_active == True,
            )
        )).scalar() or 0

        return {
            "total_classifications": total,
            "total_confirmed_correct": auto,
            "total_corrected": corrections,
            "overall_accuracy_pct": round(overall_accuracy, 2),
            "cached_accounts": len(self._classification_cache),
            "high_confidence_accounts": high_conf,
        }

    async def sync_to_kg(self, db: AsyncSession) -> int:
        """Push unsynced high-confidence classifications to KG. Returns count."""
        from app.models.all_models import LearningRecord

        result = await db.execute(
            select(LearningRecord).where(
                LearningRecord.is_active == True,
                LearningRecord.confidence >= 0.8,
                LearningRecord.applied_to_kg == False,
            )
        )
        records = result.scalars().all()

        count = 0
        try:
            from app.services.knowledge_graph import knowledge_graph, KnowledgeEntity

            if not knowledge_graph.is_built:
                knowledge_graph.build()

            for r in records:
                entity_id = f"learned_classification:{r.account_code}"
                if entity_id in knowledge_graph._entities:
                    continue

                entity = KnowledgeEntity(
                    entity_id=entity_id,
                    entity_type="learned_classification",
                    label_en=f"Learned: {r.account_code} -> {(r.classification or {}).get('description', 'unknown')}",
                    properties={
                        "account_code": r.account_code,
                        "classification": r.classification,
                        "confidence": r.confidence,
                        "source": "learning_engine_v2",
                    },
                )
                knowledge_graph._entities[entity_id] = entity
                if "learned_classification" not in knowledge_graph._index_by_type:
                    knowledge_graph._index_by_type["learned_classification"] = []
                knowledge_graph._index_by_type["learned_classification"].append(entity_id)

                # Mark as synced
                r.applied_to_kg = True
                count += 1

            await db.flush()
        except Exception as e:
            logger.warning("Failed to sync to KG: %s", e)

        return count


# Module singleton
learning_engine = LearningEngine()
