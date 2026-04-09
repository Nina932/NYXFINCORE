"""
Phase N-3: DataStore — Persistent Financial Data Storage
=========================================================
High-level service for saving/retrieving financial data:
  - Companies with industry metadata
  - Financial periods with snapshots
  - Orchestrator run results (JSON + PDF path)
  - Upload history with parsing status

Uses synchronous SQLite for simplicity (no async needed for in-process use).
Structured so switching to PostgreSQL is one env var change.

All financial storage is deterministic — no LLM involvement.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from app.config import settings

logger = logging.getLogger(__name__)

# ── Default DB path ──────────────────────────────────────────────────────────
_DEFAULT_DB = settings.FINAI_STORE_DB


# ═══════════════════════════════════════════════════════════════════
# SCHEMA
# ═══════════════════════════════════════════════════════════════════

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    industry TEXT DEFAULT 'fuel_distribution',
    base_currency TEXT DEFAULT 'GEL',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS financial_periods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    period_name TEXT NOT NULL,
    period_start TEXT,
    period_end TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(company_id, period_name)
);

CREATE TABLE IF NOT EXISTS financial_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period_id INTEGER NOT NULL REFERENCES financial_periods(id),
    field_name TEXT NOT NULL,
    value REAL NOT NULL,
    source_file TEXT,
    uploaded_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_snap_period ON financial_snapshots(period_id);
CREATE INDEX IF NOT EXISTS ix_snap_field ON financial_snapshots(field_name);

CREATE TABLE IF NOT EXISTS orchestrator_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    period_id INTEGER REFERENCES financial_periods(id),
    result_json TEXT NOT NULL,
    pdf_path TEXT,
    health_score REAL,
    health_grade TEXT,
    strategy_name TEXT,
    execution_ms REAL,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_orch_company ON orchestrator_runs(company_id);

CREATE TABLE IF NOT EXISTS upload_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER REFERENCES companies(id),
    filename TEXT NOT NULL,
    file_type TEXT,
    file_size_bytes INTEGER,
    parsed_records INTEGER DEFAULT 0,
    confidence_score INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    error_message TEXT,
    result_json TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
"""


# ═══════════════════════════════════════════════════════════════════
# DATA STORE
# ═══════════════════════════════════════════════════════════════════

class DataStore:
    """
    Persistent financial data storage backed by SQLite.

    Thread-safe via check_same_thread=False + connection-per-call pattern.
    """

    def __init__(self, db_path: str = _DEFAULT_DB):
        self._db_path = db_path
        self._ensure_dir()
        self._init_schema()

    def _ensure_dir(self):
        """Create parent directory if needed."""
        parent = Path(self._db_path).parent
        parent.mkdir(parents=True, exist_ok=True)

    def _conn(self) -> sqlite3.Connection:
        """Get a new connection (connection-per-call for thread safety)."""
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_schema(self):
        """Create tables if they don't exist."""
        conn = self._conn()
        try:
            conn.executescript(_SCHEMA_SQL)
            conn.commit()
            logger.info("DataStore schema initialized: %s", self._db_path)
        finally:
            conn.close()

    # ── Company CRUD ────────────────────────────────────────────────

    def create_company(
        self,
        name: str,
        industry: str = "fuel_distribution",
        base_currency: str = "GEL",
    ) -> int:
        """Create or get existing company, return company_id."""
        conn = self._conn()
        try:
            # Check if company exists first
            row = conn.execute(
                "SELECT id FROM companies WHERE name = ?", (name,)
            ).fetchone()
            if row:
                return row[0]
            cur = conn.execute(
                "INSERT INTO companies (name, industry, base_currency) VALUES (?, ?, ?)",
                (name, industry, base_currency),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def get_company(self, company_id: int) -> Optional[Dict[str, Any]]:
        """Get company by ID."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_companies(self) -> List[Dict[str, Any]]:
        """List all companies."""
        conn = self._conn()
        try:
            rows = conn.execute("SELECT * FROM companies ORDER BY name").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ── Financial Data ──────────────────────────────────────────────

    def save_financials(
        self,
        company_id: int,
        period_name: str,
        data: Dict[str, float],
        source_file: str = "",
    ) -> int:
        """
        Save financial data for a company+period.
        Creates the period if it doesn't exist.
        Returns period_id.
        """
        conn = self._conn()
        try:
            # Upsert period
            conn.execute(
                "INSERT OR IGNORE INTO financial_periods (company_id, period_name) VALUES (?, ?)",
                (company_id, period_name),
            )
            row = conn.execute(
                "SELECT id FROM financial_periods WHERE company_id = ? AND period_name = ?",
                (company_id, period_name),
            ).fetchone()
            period_id = row["id"]

            # Delete old snapshots for this period (replace strategy)
            conn.execute("DELETE FROM financial_snapshots WHERE period_id = ?", (period_id,))

            # ── Ensure EBITDA and Net Profit are correctly derived ──
            gp = data.get("gross_profit", 0)
            ga = data.get("ga_expenses", data.get("admin_expenses", 0))
            selling = data.get("selling_expenses", 0)
            depr = data.get("depreciation", 0)
            ebitda = data.get("ebitda", 0)
            np_ = data.get("net_profit", 0)

            # AUDIT FIX: Do NOT silently rewrite EBITDA. Log discrepancy instead.
            # The old code auto-corrected EBITDA with no user consent or audit trail.
            if ebitda != 0 and gp != 0 and abs(ebitda - gp) < 1.0 and ga > 0:
                calculated_ebitda = gp - abs(ga) - abs(selling)
                variance = abs(ebitda - calculated_ebitda)
                logger.warning(
                    "EBITDA DISCREPANCY: parsed=%.0f, calculated=%.0f (diff=%.0f). "
                    "Keeping PARSED value. Review source file for accuracy.",
                    ebitda, calculated_ebitda, variance,
                )
                # Preserve both values for audit trail
                data["ebitda_parsed"] = ebitda
                data["ebitda_calculated"] = calculated_ebitda
                data["ebitda_confidence"] = "low" if variance > 100 else "high"
                # DO NOT overwrite — keep the original parsed value
            # If EBITDA == gross_profit AND ga == 0, flag it but don't invent numbers
            elif ebitda != 0 and gp != 0 and abs(ebitda - gp) < 1.0 and ga == 0:
                logger.warning(
                    "EBITDA == Gross Profit (%.0f) with no G&A data — expenses may be missing from source file",
                    gp,
                )

            # Insert new snapshots
            now = datetime.now(timezone.utc).isoformat()
            for field_name, value in data.items():
                if isinstance(value, (int, float)):
                    conn.execute(
                        "INSERT INTO financial_snapshots (period_id, field_name, value, source_file, uploaded_at) VALUES (?, ?, ?, ?, ?)",
                        (period_id, field_name, float(value), source_file, now),
                    )

            conn.commit()
            logger.info("Saved %d fields for company=%d period=%s", len(data), company_id, period_name)
            return period_id
        finally:
            conn.close()

    def get_financials(self, company_id: int, period_name: str) -> Dict[str, float]:
        """Retrieve financial data for a company+period."""
        conn = self._conn()
        try:
            rows = conn.execute("""
                SELECT fs.field_name, fs.value
                FROM financial_snapshots fs
                JOIN financial_periods fp ON fs.period_id = fp.id
                WHERE fp.company_id = ? AND fp.period_name = ?
            """, (company_id, period_name)).fetchall()
            return {r["field_name"]: r["value"] for r in rows}
        finally:
            conn.close()

    def get_all_periods(self, company_id: int) -> List[str]:
        """Get all period names for a company, ordered chronologically."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT period_name FROM financial_periods WHERE company_id = ? ORDER BY period_name",
                (company_id,),
            ).fetchall()
            return [r["period_name"] for r in rows]
        finally:
            conn.close()

    def get_history(self, company_id: int) -> List[Dict[str, Any]]:
        """Get all financial periods with record counts."""
        conn = self._conn()
        try:
            rows = conn.execute("""
                SELECT fp.id, fp.period_name, fp.created_at,
                       COUNT(fs.id) as field_count
                FROM financial_periods fp
                LEFT JOIN financial_snapshots fs ON fs.period_id = fp.id
                WHERE fp.company_id = ?
                GROUP BY fp.id
                ORDER BY fp.period_name
            """, (company_id,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_dataset_full(self, period_id: int) -> Dict[str, Any]:
        """Load full financial data for a period (used by dataset switcher)."""
        conn = self._conn()
        try:
            # Get period + company info
            period_row = conn.execute("""
                SELECT fp.id, fp.period_name, fp.company_id, c.name as company
                FROM financial_periods fp
                JOIN companies c ON c.id = fp.company_id
                WHERE fp.id = ?
            """, (period_id,)).fetchone()
            if not period_row:
                return {}
            pr = dict(period_row)

            # Get all financial fields
            rows = conn.execute(
                "SELECT field_name, value FROM financial_snapshots WHERE period_id = ?",
                (period_id,),
            ).fetchall()
            pnl = {}
            balance_sheet = {}
            for r in rows:
                k, v = r["field_name"], r["value"]
                if k.startswith("bs_") or k in ("total_assets", "total_liabilities", "total_equity", "cash", "current_ratio", "debt_to_equity"):
                    balance_sheet[k] = v
                else:
                    pnl[k] = v

            return {
                "company": pr.get("company", ""),
                "period": pr.get("period_name", ""),
                "pnl": pnl,
                "balance_sheet": balance_sheet if balance_sheet else None,
            }
        finally:
            conn.close()

    def list_datasets(self) -> List[Dict[str, Any]]:
        """List all uploaded datasets (company + period + metadata)."""
        conn = self._conn()
        try:
            rows = conn.execute("""
                SELECT c.id as company_id, c.name as company,
                       fp.id as period_id, fp.period_name as period,
                       fp.created_at,
                       COUNT(fs.id) as field_count,
                       MAX(fs.source_file) as source_file,
                       MAX(fs.uploaded_at) as uploaded_at
                FROM companies c
                JOIN financial_periods fp ON fp.company_id = c.id
                LEFT JOIN financial_snapshots fs ON fs.period_id = fp.id
                GROUP BY c.id, fp.id
                ORDER BY fp.created_at DESC
            """).fetchall()
            result = []
            # Fetch upload history for file_size metadata (keyed by filename AND company_id)
            upload_by_filename = {}
            upload_by_company = {}
            try:
                uh_rows = conn.execute(
                    "SELECT company_id, filename, file_size_bytes, file_type, status, parsed_records "
                    "FROM upload_history ORDER BY created_at DESC"
                ).fetchall()
                for uh in uh_rows:
                    uhd = dict(uh)
                    fn = uhd.get("filename", "")
                    cid = uhd.get("company_id")
                    if fn and fn not in upload_by_filename:
                        upload_by_filename[fn] = uhd
                    if cid and cid not in upload_by_company:
                        upload_by_company[cid] = uhd
            except Exception:
                pass
            for r in rows:
                d = dict(r)
                period_id = d.get("period_id", 0)
                company_id_row = d.get("company_id", 0)
                source_file = d.get("source_file") or ""
                # Match upload_history by filename first, then by company_id
                uh_meta = upload_by_filename.get(source_file) or upload_by_company.get(company_id_row) or {}
                display_name = source_file or uh_meta.get("filename") or f"{d.get('company', '')} - {d.get('period', '')}"
                orig_filename = source_file or uh_meta.get("filename", "")
                ext = orig_filename.rsplit(".", 1)[-1] if "." in orig_filename else "xlsx"
                result.append({
                    "id": period_id,
                    "name": display_name,
                    "original_filename": orig_filename,
                    "company": d.get("company", ""),
                    "period": d.get("period", ""),
                    "record_count": d.get("field_count", 0),
                    "file_type": uh_meta.get("file_type", "xlsx"),
                    "file_size": uh_meta.get("file_size_bytes", 0),
                    "extension": ext,
                    "sheet_count": 0,
                    "status": uh_meta.get("status", "ready"),
                    "is_active": False,
                    "is_seed": False,
                    "currency": "GEL",
                    "parse_metadata": None,
                    "created_at": d.get("uploaded_at") or d.get("created_at") or "",
                    "updated_at": None,
                })
            return result
        finally:
            conn.close()

    def delete_dataset(self, period_id: int) -> Dict[str, Any]:
        """Delete a dataset (period) and all related data (snapshots, orchestrator runs)."""
        conn = self._conn()
        try:
            # Get period info first
            row = conn.execute(
                "SELECT fp.id, fp.company_id, fp.period_name, c.name as company "
                "FROM financial_periods fp JOIN companies c ON c.id = fp.company_id "
                "WHERE fp.id = ?", (period_id,)
            ).fetchone()
            if not row:
                return {"deleted": False, "error": f"Dataset {period_id} not found"}

            d = dict(row)
            company_id = d["company_id"]

            # Delete in order: snapshots → orchestrator_runs → upload_history → period
            snap_count = conn.execute(
                "SELECT COUNT(*) FROM financial_snapshots WHERE period_id = ?", (period_id,)
            ).fetchone()[0]
            conn.execute("DELETE FROM financial_snapshots WHERE period_id = ?", (period_id,))

            orch_count = conn.execute(
                "SELECT COUNT(*) FROM orchestrator_runs WHERE period_id = ?", (period_id,)
            ).fetchone()[0]
            conn.execute("DELETE FROM orchestrator_runs WHERE period_id = ?", (period_id,))

            conn.execute("DELETE FROM financial_periods WHERE id = ?", (period_id,))

            # If no more periods for this company, delete the company too
            remaining = conn.execute(
                "SELECT COUNT(*) FROM financial_periods WHERE company_id = ?", (company_id,)
            ).fetchone()[0]
            company_deleted = False
            if remaining == 0:
                conn.execute("DELETE FROM orchestrator_runs WHERE company_id = ?", (company_id,))
                conn.execute("DELETE FROM upload_history WHERE company_id = ?", (company_id,))
                conn.execute("DELETE FROM companies WHERE id = ?", (company_id,))
                company_deleted = True

            conn.commit()
            logger.info("Deleted dataset period_id=%d: %d snapshots, %d orchestrator runs, company_deleted=%s",
                        period_id, snap_count, orch_count, company_deleted)
            return {
                "deleted": True,
                "period_id": period_id,
                "company": d["company"],
                "period": d["period_name"],
                "snapshots_deleted": snap_count,
                "orchestrator_runs_deleted": orch_count,
                "company_deleted": company_deleted,
            }
        except Exception as e:
            logger.error("delete_dataset error: %s", e)
            return {"deleted": False, "error": str(e)}
        finally:
            conn.close()

    # ── Orchestrator Results ────────────────────────────────────────

    def save_orchestrator_result(
        self,
        company_id: int,
        result_dict: Dict[str, Any],
        period_id: Optional[int] = None,
        pdf_path: Optional[str] = None,
    ) -> int:
        """Save an orchestrator run result, return run_id."""
        conn = self._conn()
        try:
            exec_summary = result_dict.get("executive_summary", {})
            cur = conn.execute(
                """INSERT INTO orchestrator_runs
                   (company_id, period_id, result_json, pdf_path,
                    health_score, health_grade, strategy_name, execution_ms)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    company_id,
                    period_id,
                    json.dumps(result_dict, default=str),
                    pdf_path,
                    exec_summary.get("health_score"),
                    exec_summary.get("health_grade"),
                    exec_summary.get("strategy_name"),
                    exec_summary.get("execution_time_ms"),
                ),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def get_last_orchestrator_result(self, company_id: int) -> Optional[Dict[str, Any]]:
        """Get the most recent orchestrator result for a company."""
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT * FROM orchestrator_runs
                   WHERE company_id = ?
                   ORDER BY created_at DESC LIMIT 1""",
                (company_id,),
            ).fetchone()
            if not row:
                return None
            d = dict(row)
            d["result"] = json.loads(d.pop("result_json", "{}"))
            return d
        finally:
            conn.close()

    def get_orchestrator_history(self, company_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent orchestrator runs (metadata only, no full JSON)."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT id, company_id, period_id, pdf_path,
                          health_score, health_grade, strategy_name,
                          execution_ms, created_at
                   FROM orchestrator_runs
                   WHERE company_id = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (company_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ── Upload History ──────────────────────────────────────────────

    def log_upload(
        self,
        filename: str,
        file_type: str,
        file_size: int,
        company_id: Optional[int] = None,
        parsed_records: int = 0,
        confidence: int = 0,
        status: str = "success",
        error_message: str = "",
        result_json: str = "",
    ) -> int:
        """Log a file upload, return upload_id."""
        conn = self._conn()
        try:
            cur = conn.execute(
                """INSERT INTO upload_history
                   (company_id, filename, file_type, file_size_bytes,
                    parsed_records, confidence_score, status, error_message, result_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (company_id, filename, file_type, file_size,
                 parsed_records, confidence, status, error_message, result_json),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def get_upload_history(self, company_id: Optional[int] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent uploads."""
        conn = self._conn()
        try:
            if company_id:
                rows = conn.execute(
                    "SELECT * FROM upload_history WHERE company_id = ? ORDER BY created_at DESC LIMIT ?",
                    (company_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM upload_history ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ── Utilities ───────────────────────────────────────────────────

    def reset(self):
        """Drop and recreate all tables (for testing)."""
        conn = self._conn()
        try:
            conn.executescript("""
                DROP TABLE IF EXISTS upload_history;
                DROP TABLE IF EXISTS orchestrator_runs;
                DROP TABLE IF EXISTS financial_snapshots;
                DROP TABLE IF EXISTS financial_periods;
                DROP TABLE IF EXISTS companies;
            """)
            conn.commit()
        finally:
            conn.close()
        self._init_schema()

    def stats(self) -> Dict[str, int]:
        """Get storage statistics."""
        conn = self._conn()
        try:
            result = {}
            for table in ["companies", "financial_periods", "financial_snapshots",
                          "orchestrator_runs", "upload_history"]:
                row = conn.execute(f"SELECT COUNT(*) as cnt FROM {table}").fetchone()
                result[table] = row["cnt"]
            return result
        finally:
            conn.close()


# Module-level singleton
data_store = DataStore()
