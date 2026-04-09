"""
FinAI OS — Ontology Store (DuckDB)
===================================
Persists ontology objects to DuckDB for analytical queries + versioning.
Supports Parquet export/import.

Usage:
    from app.services.ontology_store import ontology_store
    ontology_store.initialize()
    ontology_store.save_object(obj)
    results = ontology_store.query_analytical("SELECT * FROM ontology_objects WHERE object_type = 'KPI'")
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import duckdb
    HAS_DUCKDB = True
except ImportError:
    HAS_DUCKDB = False
    logger.warning("DuckDB not installed — ontology store will use in-memory only")


class OntologyStore:
    """DuckDB-backed persistence for ontology objects with versioning."""

    def __init__(self, db_path: str = "data/finai_ontology.duckdb"):
        self._db_path = db_path
        self._conn = None
        self._initialized = False

    def initialize(self) -> bool:
        if self._initialized and self._conn:
            return True
        if not HAS_DUCKDB:
            logger.warning("DuckDB not available, skipping ontology store init")
            return False

        os.makedirs(os.path.dirname(self._db_path) or "data", exist_ok=True)
        abs_path = os.path.abspath(self._db_path)

        # Clean stale lock files
        for ext in (".wal", ".tmp"):
            try: os.remove(abs_path + ext)
            except OSError: pass

        # Try file-backed, fallback to in-memory
        for path in [abs_path, ":memory:"]:
            try:
                self._conn = duckdb.connect(path)
                self._create_schema()
                self._initialized = True
                self._db_path = path
                logger.info(f"Ontology store initialized at {path}")
                return True
            except Exception as e:
                logger.warning(f"Ontology store connect to {path}: {e}")
        logger.error("Ontology store: all init attempts failed")
        return False

    def _create_schema(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS ontology_objects (
                object_id VARCHAR PRIMARY KEY,
                object_type VARCHAR NOT NULL,
                version INTEGER NOT NULL DEFAULT 1,
                properties JSON NOT NULL,
                relationships JSON NOT NULL,
                source_entity_id VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self._conn.execute("""
            CREATE SEQUENCE IF NOT EXISTS ontology_versions_seq START 1
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS ontology_versions (
                id INTEGER DEFAULT (nextval('ontology_versions_seq')),
                object_id VARCHAR NOT NULL,
                version INTEGER NOT NULL,
                properties JSON NOT NULL,
                changed_by VARCHAR DEFAULT 'system',
                changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS ontology_edges (
                source_id VARCHAR NOT NULL,
                relationship VARCHAR NOT NULL,
                target_id VARCHAR NOT NULL,
                metadata JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (source_id, relationship, target_id)
            )
        """)

        # Indexes
        try:
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_obj_type ON ontology_objects(object_type)")
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_ver_oid ON ontology_versions(object_id)")
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_edge_src ON ontology_edges(source_id)")
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_edge_tgt ON ontology_edges(target_id)")
        except Exception:
            pass

    # ─── Object Persistence ──────────────────────────────────────────

    def save_object(self, obj) -> None:
        if not self._conn:
            return
        self._conn.execute("""
            INSERT OR REPLACE INTO ontology_objects
            (object_id, object_type, version, properties, relationships, source_entity_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            obj.object_id, obj.object_type, obj.version,
            json.dumps(obj.properties), json.dumps(obj.relationships),
            obj.source_entity_id, obj.created_at, obj.updated_at,
        ])

    def save_version(self, obj, changed_by: str = "system") -> None:
        if not self._conn:
            return
        self._conn.execute("""
            INSERT INTO ontology_versions (object_id, version, properties, changed_by)
            VALUES (?, ?, ?, ?)
        """, [obj.object_id, obj.version, json.dumps(obj.properties), changed_by])

    def save_edge(self, source_id: str, relationship: str, target_id: str, metadata: Optional[Dict] = None) -> None:
        if not self._conn:
            return
        self._conn.execute("""
            INSERT OR IGNORE INTO ontology_edges (source_id, relationship, target_id, metadata)
            VALUES (?, ?, ?, ?)
        """, [source_id, relationship, target_id, json.dumps(metadata or {})])

    def bulk_save(self, objects: list) -> int:
        if not self._conn:
            return 0
        count = 0
        for obj in objects:
            self.save_object(obj)
            count += 1
        return count

    # ─── Queries ─────────────────────────────────────────────────────

    def load_all(self, type_id: Optional[str] = None) -> List[Dict]:
        if not self._conn:
            return []
        if type_id:
            result = self._conn.execute(
                "SELECT * FROM ontology_objects WHERE object_type = ?", [type_id]
            ).fetchdf()
        else:
            result = self._conn.execute("SELECT * FROM ontology_objects").fetchdf()
        return result.to_dict(orient="records") if len(result) > 0 else []

    def query_analytical(self, sql: str) -> List[Dict]:
        if not self._conn:
            return []
        try:
            result = self._conn.execute(sql).fetchdf()
            return result.to_dict(orient="records") if len(result) > 0 else []
        except Exception as e:
            logger.error(f"DuckDB query error: {e}")
            return []

    def get_version_history(self, object_id: str) -> List[Dict]:
        if not self._conn:
            return []
        result = self._conn.execute(
            "SELECT * FROM ontology_versions WHERE object_id = ? ORDER BY version DESC", [object_id]
        ).fetchdf()
        return result.to_dict(orient="records") if len(result) > 0 else []

    def get_diff(self, object_id: str, v1: int, v2: int) -> Dict:
        if not self._conn:
            return {}
        rows = self._conn.execute(
            "SELECT version, properties FROM ontology_versions WHERE object_id = ? AND version IN (?, ?) ORDER BY version",
            [object_id, v1, v2]
        ).fetchall()
        if len(rows) < 2:
            return {"error": "Not enough versions found"}
        p1 = json.loads(rows[0][1]) if isinstance(rows[0][1], str) else rows[0][1]
        p2 = json.loads(rows[1][1]) if isinstance(rows[1][1], str) else rows[1][1]
        diff = {}
        all_keys = set(list(p1.keys()) + list(p2.keys()))
        for k in all_keys:
            if p1.get(k) != p2.get(k):
                diff[k] = {"from": p1.get(k), "to": p2.get(k)}
        return {"object_id": object_id, "from_version": v1, "to_version": v2, "changes": diff}

    # ─── Parquet Export/Import ───────────────────────────────────────

    def export_parquet(self, type_id: str, output_path: str) -> str:
        if not self._conn:
            return ""
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        self._conn.execute(f"""
            COPY (SELECT * FROM ontology_objects WHERE object_type = '{type_id}')
            TO '{output_path}' (FORMAT PARQUET)
        """)
        logger.info(f"Exported {type_id} to {output_path}")
        return output_path

    def import_parquet(self, file_path: str) -> int:
        if not self._conn:
            return 0
        self._conn.execute(f"""
            INSERT INTO ontology_objects
            SELECT * FROM read_parquet('{file_path}')
        """)
        count = self._conn.execute("SELECT changes()").fetchone()[0]
        logger.info(f"Imported {count} objects from {file_path}")
        return count

    # ─── Stats ───────────────────────────────────────────────────────

    def stats(self) -> Dict[str, Any]:
        if not self._conn:
            return {"initialized": False, "engine": "none"}
        try:
            obj_count = self._conn.execute("SELECT COUNT(*) FROM ontology_objects").fetchone()[0]
            ver_count = self._conn.execute("SELECT COUNT(*) FROM ontology_versions").fetchone()[0]
            edge_count = self._conn.execute("SELECT COUNT(*) FROM ontology_edges").fetchone()[0]
            type_counts = self._conn.execute(
                "SELECT object_type, COUNT(*) as cnt FROM ontology_objects GROUP BY object_type ORDER BY cnt DESC"
            ).fetchdf().to_dict(orient="records")
            return {
                "initialized": True,
                "engine": "duckdb",
                "db_path": self._db_path,
                "objects": obj_count,
                "versions": ver_count,
                "edges": edge_count,
                "by_type": {r["object_type"]: r["cnt"] for r in type_counts},
            }
        except Exception as e:
            return {"initialized": True, "engine": "duckdb", "error": str(e)}


# =============================================================================
# SINGLETON
# =============================================================================

ontology_store = OntologyStore()
