"""
FinAI v2 Knowledge Graph — DB-persisted, restart-safe.
=======================================================
Wraps the existing v1 KG (2,579 lines of domain knowledge) with
a DB persistence layer for dynamic entities (patterns, corrections,
learned classifications).

Architecture:
- Static domain knowledge (COA, IFRS, benchmarks, formulas): rebuilt from
  hardcoded rules on startup (fast, deterministic, ~710 entities)
- Dynamic entities (patterns, corrections): persisted to DB via
  KnowledgeEntityRecord/KnowledgeRelationRecord models
- On startup: load dynamic entities from DB → merge with static build
- Hot-path lookups use in-memory cache (unchanged performance)

Key changes from v1:
- Dynamic entities survive server restarts
- add_dataset_pattern() and add_user_correction() persist to DB
- New: persist_dynamic_to_db() / load_dynamic_from_db()
- Thread-safe entity addition via consistent indexing

Public API:
    from app.services.v2.knowledge_graph import knowledge_graph
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Import v1 classes for compatibility
from app.services.knowledge_graph import (
    KnowledgeEntity,
    KnowledgeRelation,
    FinancialKnowledgeGraph as V1KnowledgeGraph,
)


class PersistentKnowledgeGraph(V1KnowledgeGraph):
    """
    Extends v1 KG with DB persistence for dynamic entities.

    Static domain knowledge is rebuilt from hardcoded rules (v1 behavior).
    Dynamic entities (patterns, corrections, learned classifications)
    are persisted to the knowledge_entities table and survive restarts.
    """

    _DYNAMIC_TYPES = {"pattern", "correction", "learned_classification"}

    def __init__(self) -> None:
        super().__init__()
        self._db_synced = False

    async def build_with_persistence(self, db: AsyncSession) -> int:
        """Build KG from static rules, then merge dynamic entities from DB."""
        # 1. Build static knowledge (v1 behavior)
        count = self.build()

        # 2. Load dynamic entities from DB
        dynamic_count = await self._load_dynamic_from_db(db)

        logger.info(
            "KG v2 built: %d static + %d dynamic = %d total entities",
            count - dynamic_count, dynamic_count, self.entity_count,
        )
        self._db_synced = True
        return self.entity_count

    async def _load_dynamic_from_db(self, db: AsyncSession) -> int:
        """Load dynamic entities from DB and merge into in-memory graph."""
        from app.models.all_models import KnowledgeEntityRecord, KnowledgeRelationRecord

        try:
            # Load dynamic entities
            result = await db.execute(
                select(KnowledgeEntityRecord).where(
                    KnowledgeEntityRecord.is_dynamic == True
                )
            )
            records = result.scalars().all()

            count = 0
            for r in records:
                if r.entity_id in self._entities:
                    continue  # Already loaded from preserved state

                entity = KnowledgeEntity(
                    entity_id=r.entity_id,
                    entity_type=r.entity_type,
                    label_en=r.label_en or "",
                    label_ka=r.label_ka or "",
                    description=r.description or "",
                    properties=r.properties or {},
                )

                # Load relationships for this entity
                rel_result = await db.execute(
                    select(KnowledgeRelationRecord).where(
                        KnowledgeRelationRecord.source_entity_id == r.entity_id
                    )
                )
                for rel in rel_result.scalars().all():
                    entity.relationships.append(KnowledgeRelation(
                        relation_type=rel.relation_type,
                        target_id=rel.target_entity_id,
                        label=rel.label or "",
                    ))

                self._add_entity(entity)
                count += 1

            if count > 0:
                logger.info("Loaded %d dynamic entities from DB", count)
            return count

        except Exception as e:
            logger.warning("Failed to load dynamic entities from DB: %s", e)
            return 0

    async def persist_entity_to_db(
        self, entity: KnowledgeEntity, db: AsyncSession
    ) -> None:
        """Persist a single dynamic entity to DB."""
        from app.models.all_models import KnowledgeEntityRecord, KnowledgeRelationRecord

        try:
            # Upsert entity
            existing = await db.execute(
                select(KnowledgeEntityRecord).where(
                    KnowledgeEntityRecord.entity_id == entity.entity_id
                )
            )
            record = existing.scalar_one_or_none()

            if record:
                record.entity_type = entity.entity_type
                record.label_en = entity.label_en
                record.label_ka = entity.label_ka
                record.description = entity.description
                record.properties = entity.properties
                record.is_dynamic = entity.entity_type in self._DYNAMIC_TYPES
            else:
                record = KnowledgeEntityRecord(
                    entity_id=entity.entity_id,
                    entity_type=entity.entity_type,
                    label_en=entity.label_en,
                    label_ka=entity.label_ka,
                    description=entity.description,
                    properties=entity.properties,
                    is_dynamic=entity.entity_type in self._DYNAMIC_TYPES,
                )
                db.add(record)

            # Persist relationships
            for rel in entity.relationships:
                rel_exists = await db.execute(
                    select(KnowledgeRelationRecord).where(
                        KnowledgeRelationRecord.source_entity_id == entity.entity_id,
                        KnowledgeRelationRecord.target_entity_id == rel.target_id,
                        KnowledgeRelationRecord.relation_type == rel.relation_type,
                    )
                )
                if not rel_exists.scalar_one_or_none():
                    db.add(KnowledgeRelationRecord(
                        source_entity_id=entity.entity_id,
                        target_entity_id=rel.target_id,
                        relation_type=rel.relation_type,
                        label=rel.label,
                    ))

            await db.flush()
        except Exception as e:
            logger.warning("Failed to persist entity %s: %s", entity.entity_id, e)

    async def add_dataset_pattern_persistent(
        self,
        pattern_type: str,
        metric: str,
        description: str,
        properties: Dict[str, Any],
        db: AsyncSession,
    ) -> str:
        """Add a dataset pattern and persist to DB."""
        import hashlib
        entity_id = f"pattern_{hashlib.md5(f'{pattern_type}:{metric}:{description[:50]}'.encode()).hexdigest()[:10]}"

        entity = KnowledgeEntity(
            entity_id=entity_id,
            entity_type="pattern",
            label_en=f"Pattern: {description[:80]}",
            description=description,
            properties={"pattern_type": pattern_type, "metric": metric, **properties},
        )

        # Add to in-memory graph
        self._add_entity(entity)

        # Persist to DB
        await self.persist_entity_to_db(entity, db)

        return entity_id

    async def add_user_correction_persistent(
        self,
        account_code: str,
        correction: Dict[str, Any],
        source: str,
        db: AsyncSession,
    ) -> str:
        """Add a user correction and persist to DB."""
        entity_id = f"correction:{account_code}"

        entity = KnowledgeEntity(
            entity_id=entity_id,
            entity_type="correction",
            label_en=f"Correction: {account_code} -> {correction.get('description', '')}",
            properties={
                "account_code": account_code,
                "correction": correction,
                "source": source,
            },
        )

        self._add_entity(entity)
        await self.persist_entity_to_db(entity, db)

        # Also update code index
        self._index_by_code[account_code] = entity_id

        return entity_id

    # Override v1 methods to also persist when DB is available

    def add_dataset_pattern(
        self,
        pattern_type: str,
        metric: str,
        description: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> str:
        """v1-compatible sync method — adds to memory only.
        Use add_dataset_pattern_persistent() for DB persistence.
        """
        import hashlib
        entity_id = f"pattern_{hashlib.md5(f'{pattern_type}:{metric}:{description[:50]}'.encode()).hexdigest()[:10]}"

        entity = KnowledgeEntity(
            entity_id=entity_id,
            entity_type="pattern",
            label_en=f"Pattern: {description[:80]}",
            description=description,
            properties={"pattern_type": pattern_type, "metric": metric, **(properties or {})},
        )
        self._add_entity(entity)
        return entity_id

    def add_user_correction(
        self,
        account_code: str,
        correction: Dict[str, Any],
        source: str = "user",
    ) -> str:
        """v1-compatible sync method — memory only."""
        entity_id = f"correction:{account_code}"
        entity = KnowledgeEntity(
            entity_id=entity_id,
            entity_type="correction",
            label_en=f"Correction: {account_code}",
            properties={"account_code": account_code, "correction": correction, "source": source},
        )
        self._add_entity(entity)
        self._index_by_code[account_code] = entity_id
        return entity_id

    async def persist_all_dynamic_to_db(self, db: AsyncSession) -> int:
        """Persist all dynamic entities from memory to DB (bulk sync)."""
        count = 0
        for eid, entity in self._entities.items():
            if entity.entity_type in self._DYNAMIC_TYPES:
                await self.persist_entity_to_db(entity, db)
                count += 1
        logger.info("Persisted %d dynamic entities to DB", count)
        return count

    def status(self) -> Dict[str, Any]:
        """Enhanced status with persistence info."""
        base_status = super().status()
        base_status["db_synced"] = self._db_synced
        base_status["dynamic_entities"] = sum(
            1 for e in self._entities.values()
            if e.entity_type in self._DYNAMIC_TYPES
        )
        return base_status


# Module-level singleton
knowledge_graph = PersistentKnowledgeGraph()
