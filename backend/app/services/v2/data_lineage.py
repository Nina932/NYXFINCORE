"""
Data Lineage Tracker
=====================
Captures the full lineage of how data flows through the system:
- Source file -> parsed rows -> classified accounts -> journal entries -> posting lines -> financial statements

Complements the existing DataLineage model (file-to-entity mapping) with a
general-purpose transformation lineage graph (TransformationLineage model).

Public API:
    from app.services.v2.data_lineage import data_lineage_tracker
    await data_lineage_tracker.record_lineage(db, "dataset", 1, "journal_entry", 5, "ingestion", {"rows": 42})
    chain = await data_lineage_tracker.get_lineage_chain(db, "posting_line", 10)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select, or_, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class DataLineageTracker:
    """
    Tracks data transformations as a directed graph.

    Each edge records: source_type/source_id -> target_type/target_id
    with a transformation label and optional metadata.
    """

    async def record_lineage(
        self,
        db: AsyncSession,
        source_type: str,
        source_id: int,
        target_type: str,
        target_id: int,
        transformation: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Record a single transformation step in the data lineage.

        Args:
            db: Async database session
            source_type: Type of the source entity (e.g., "dataset", "parsed_row", "journal_entry")
            source_id: ID of the source entity
            target_type: Type of the target entity (e.g., "journal_entry", "posting_line")
            target_id: ID of the target entity
            transformation: Label describing the transformation (e.g., "ingestion", "classification", "posting")
            metadata: Optional JSON-serializable dict with extra details

        Returns:
            Dict with the created lineage record.
        """
        from app.models.all_models import TransformationLineage

        record = TransformationLineage(
            source_type=source_type,
            source_id=source_id,
            target_type=target_type,
            target_id=target_id,
            transformation=transformation,
            metadata_json=json.dumps(metadata) if metadata else None,
            created_at=datetime.now(timezone.utc),
        )
        db.add(record)
        await db.flush()

        logger.debug(
            "Lineage: %s#%d -> %s#%d via '%s'",
            source_type, source_id, target_type, target_id, transformation,
        )

        return {
            "id": record.id,
            "source_type": source_type,
            "source_id": source_id,
            "target_type": target_type,
            "target_id": target_id,
            "transformation": transformation,
            "metadata": metadata,
        }

    async def record_lineage_bulk(
        self,
        db: AsyncSession,
        records: List[Dict[str, Any]],
    ) -> int:
        """
        Record multiple lineage steps at once.

        Args:
            records: List of dicts with keys:
                source_type, source_id, target_type, target_id, transformation, metadata (optional)

        Returns:
            Number of records created.
        """
        from app.models.all_models import TransformationLineage

        now = datetime.now(timezone.utc)
        entries = []
        for r in records:
            entry = TransformationLineage(
                source_type=r["source_type"],
                source_id=r["source_id"],
                target_type=r["target_type"],
                target_id=r["target_id"],
                transformation=r["transformation"],
                metadata_json=json.dumps(r.get("metadata")) if r.get("metadata") else None,
                created_at=now,
            )
            entries.append(entry)

        db.add_all(entries)
        await db.flush()
        return len(entries)

    async def get_lineage_chain(
        self,
        db: AsyncSession,
        entity_type: str,
        entity_id: int,
        direction: str = "backward",
        max_depth: int = 10,
    ) -> Dict[str, Any]:
        """
        Trace the lineage chain for an entity.

        Args:
            db: Async database session
            entity_type: Type of entity to trace
            entity_id: ID of entity to trace
            direction: "backward" traces to sources, "forward" traces to targets
            max_depth: Maximum number of hops to follow

        Returns:
            Dict with the full lineage chain and metadata.
        """
        from app.models.all_models import TransformationLineage

        chain = []
        visited = set()
        queue = [(entity_type, entity_id, 0)]

        while queue:
            current_type, current_id, depth = queue.pop(0)
            node_key = (current_type, current_id)

            if node_key in visited or depth > max_depth:
                continue
            visited.add(node_key)

            if direction == "backward":
                # Find records where this entity is the target
                result = await db.execute(
                    select(TransformationLineage).where(
                        TransformationLineage.target_type == current_type,
                        TransformationLineage.target_id == current_id,
                    )
                )
            else:
                # Find records where this entity is the source
                result = await db.execute(
                    select(TransformationLineage).where(
                        TransformationLineage.source_type == current_type,
                        TransformationLineage.source_id == current_id,
                    )
                )

            records = result.scalars().all()
            for r in records:
                meta = None
                if r.metadata_json:
                    try:
                        meta = json.loads(r.metadata_json)
                    except (json.JSONDecodeError, TypeError):
                        meta = r.metadata_json

                chain.append({
                    "id": r.id,
                    "source_type": r.source_type,
                    "source_id": r.source_id,
                    "target_type": r.target_type,
                    "target_id": r.target_id,
                    "transformation": r.transformation,
                    "metadata": meta,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "depth": depth,
                })

                # Queue the next hop
                if direction == "backward":
                    next_key = (r.source_type, r.source_id)
                    if next_key not in visited:
                        queue.append((r.source_type, r.source_id, depth + 1))
                else:
                    next_key = (r.target_type, r.target_id)
                    if next_key not in visited:
                        queue.append((r.target_type, r.target_id, depth + 1))

        # Also check the existing DataLineage table for file-origin info
        origin_info = await self._get_origin_info(db, entity_type, entity_id)

        return {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "direction": direction,
            "chain": chain,
            "chain_length": len(chain),
            "origin_info": origin_info,
            "lineage_summary": self._build_summary(chain, entity_type, entity_id, direction),
        }

    async def get_lineage_graph(
        self,
        db: AsyncSession,
        entity_type: str,
        entity_id: int,
    ) -> Dict[str, Any]:
        """
        Build a full bidirectional lineage graph for an entity.
        Returns both upstream (sources) and downstream (targets).
        """
        backward = await self.get_lineage_chain(db, entity_type, entity_id, "backward")
        forward = await self.get_lineage_chain(db, entity_type, entity_id, "forward")

        return {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "upstream": backward["chain"],
            "downstream": forward["chain"],
            "origin_info": backward["origin_info"],
            "total_nodes": len(backward["chain"]) + len(forward["chain"]) + 1,
        }

    async def _get_origin_info(
        self,
        db: AsyncSession,
        entity_type: str,
        entity_id: int,
    ) -> Optional[Dict[str, Any]]:
        """Check existing DataLineage table for file-origin information."""
        from app.models.all_models import DataLineage

        try:
            result = await db.execute(
                select(DataLineage).where(
                    DataLineage.entity_type == entity_type,
                    DataLineage.entity_id == entity_id,
                ).limit(1)
            )
            record = result.scalar_one_or_none()
            if record:
                return {
                    "source_file": record.source_file,
                    "source_sheet": record.source_sheet,
                    "source_row": record.source_row,
                    "source_column": record.source_column,
                    "classification_rule": record.classification_rule,
                    "classification_confidence": record.classification_confidence,
                    "transform_chain": record.transform_chain,
                }
        except Exception as e:
            logger.debug("Could not fetch origin info: %s", e)

        return None

    def _build_summary(
        self,
        chain: List[Dict],
        entity_type: str,
        entity_id: int,
        direction: str,
    ) -> str:
        """Build a human-readable lineage summary."""
        if not chain:
            return f"No {direction} lineage found for {entity_type}#{entity_id}"

        if direction == "backward":
            # Build path from origin to entity
            steps = []
            for c in reversed(chain):
                steps.append(f"{c['source_type']}#{c['source_id']}")
            steps.append(f"{entity_type}#{entity_id}")
            return " -> ".join(steps)
        else:
            steps = [f"{entity_type}#{entity_id}"]
            for c in chain:
                steps.append(f"{c['target_type']}#{c['target_id']}")
            return " -> ".join(steps)


    async def migrate_from_data_lineage(self, db: AsyncSession) -> Dict[str, Any]:
        """
        Populate transformation_lineage from the existing data_lineage table.

        The data_lineage table has ~50K records with file-origin info.
        We create transformation_lineage edges for each record:
        dataset -> entity (entity_type/entity_id) via 'ingestion'.
        """
        from app.models.all_models import DataLineage, TransformationLineage
        from sqlalchemy import func

        # Check existing transformation_lineage count
        existing = await db.execute(select(func.count(TransformationLineage.id)))
        existing_count = existing.scalar() or 0

        # Get all data_lineage records
        result = await db.execute(select(DataLineage))
        records = result.scalars().all()

        now = datetime.now(timezone.utc)
        created = 0
        batch = []

        for rec in records:
            if not rec.dataset_id or not rec.entity_id:
                continue

            entry = TransformationLineage(
                source_type="dataset",
                source_id=rec.dataset_id,
                target_type=rec.entity_type or "unknown",
                target_id=rec.entity_id,
                transformation="ingestion",
                metadata_json=json.dumps({
                    "source_file": rec.source_file,
                    "source_sheet": rec.source_sheet,
                    "source_row": rec.source_row,
                    "source_column": rec.source_column,
                }) if rec.source_file else None,
                created_at=now,
            )
            batch.append(entry)
            created += 1

            # Batch insert every 500
            if len(batch) >= 500:
                db.add_all(batch)
                await db.flush()
                batch = []

        if batch:
            db.add_all(batch)
            await db.flush()

        await db.commit()

        return {
            "migrated": created,
            "source_table": "data_lineage",
            "target_table": "transformation_lineage",
            "previously_existing": existing_count,
        }


# Module singleton
data_lineage_tracker = DataLineageTracker()
