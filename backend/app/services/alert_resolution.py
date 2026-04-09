"""
Alert Resolution Workflow — Decision Tracking for Alerts
=========================================================
Tracks alert lifecycle decisions: acknowledge, resolve, escalate, dismiss.
Stores resolution history, computes resolution stats, and tracks impact.

Deterministic — no LLM calls.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import os
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════

@dataclass
class AlertDecision:
    """A resolution decision for an alert."""
    id: int
    alert_id: int
    decision: str              # acknowledge | resolve | escalate | dismiss
    explanation: str
    resolution_type: str       # root_cause_fixed | workaround | false_positive | accepted_risk | escalated
    resolved_by: str
    resolved_at: str
    impact_metric: Optional[str] = None
    impact_before: Optional[float] = None
    impact_after: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "alert_id": self.alert_id,
            "decision": self.decision,
            "explanation": self.explanation,
            "resolution_type": self.resolution_type,
            "resolved_by": self.resolved_by,
            "resolved_at": self.resolved_at,
            "impact_metric": self.impact_metric,
            "impact_before": self.impact_before,
            "impact_after": self.impact_after,
        }


# ═══════════════════════════════════════════════════════════════════
# SCHEMA
# ═══════════════════════════════════════════════════════════════════

_RESOLUTION_SCHEMA = """
CREATE TABLE IF NOT EXISTS alert_resolutions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_id INTEGER NOT NULL,
    decision TEXT NOT NULL,
    explanation TEXT DEFAULT '',
    resolution_type TEXT DEFAULT 'root_cause_fixed',
    resolved_by TEXT DEFAULT 'user',
    impact_metric TEXT,
    impact_before REAL,
    impact_after REAL,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_ar_alert ON alert_resolutions(alert_id);
"""


# ═══════════════════════════════════════════════════════════════════
# ALERT RESOLUTION MANAGER
# ═══════════════════════════════════════════════════════════════════

class AlertResolutionManager:
    """
    Manages alert resolution decisions with persistence.
    """

    def __init__(self, db_path: str = "data/finai_store.db"):
        self._db_path = db_path
        self._ensure_schema()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self):
        os.makedirs(os.path.dirname(self._db_path) or ".", exist_ok=True)
        conn = self._conn()
        try:
            conn.executescript(_RESOLUTION_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    # ── Resolution CRUD ────────────────────────────────────────────

    def resolve_alert(
        self,
        alert_id: int,
        decision: str,
        explanation: str = "",
        resolution_type: str = "root_cause_fixed",
        resolved_by: str = "user",
    ) -> int:
        """Record a resolution decision for an alert. Returns resolution ID."""
        conn = self._conn()
        try:
            cur = conn.execute(
                """INSERT INTO alert_resolutions
                   (alert_id, decision, explanation, resolution_type, resolved_by)
                   VALUES (?, ?, ?, ?, ?)""",
                (alert_id, decision, explanation, resolution_type, resolved_by),
            )
            conn.commit()
            rid = cur.lastrowid
            logger.info("Alert %d resolved: [%s] %s by %s", alert_id, decision, resolution_type, resolved_by)

            # Also acknowledge the alert in persistent_alerts if it exists
            self._acknowledge_alert(alert_id, conn)

            return rid
        finally:
            conn.close()

    def _acknowledge_alert(self, alert_id: int, conn: sqlite3.Connection):
        """Mark the alert as inactive in the persistent_alerts table."""
        try:
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                "UPDATE persistent_alerts SET is_active = 0, acknowledged_at = ? WHERE id = ?",
                (now, alert_id),
            )
            conn.commit()
        except Exception:
            pass  # Table may not exist

    def escalate_alert(
        self,
        alert_id: int,
        explanation: str = "",
        escalated_by: str = "user",
    ) -> int:
        """Escalate an alert to higher-level review."""
        return self.resolve_alert(
            alert_id=alert_id,
            decision="escalate",
            explanation=explanation,
            resolution_type="escalated",
            resolved_by=escalated_by,
        )

    def get_resolution(self, alert_id: int) -> Optional[AlertDecision]:
        """Get the latest resolution for an alert."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM alert_resolutions WHERE alert_id = ? ORDER BY created_at DESC LIMIT 1",
                (alert_id,),
            ).fetchone()
            return self._row_to_decision(row) if row else None
        finally:
            conn.close()

    def get_all_resolutions(self, limit: int = 50) -> List[AlertDecision]:
        """Get recent resolutions."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM alert_resolutions ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [self._row_to_decision(r) for r in rows]
        finally:
            conn.close()

    def get_resolution_stats(self) -> Dict[str, Any]:
        """Compute resolution statistics."""
        conn = self._conn()
        try:
            total = conn.execute("SELECT COUNT(*) as cnt FROM alert_resolutions").fetchone()["cnt"]

            # Counts by decision type
            decision_counts = {}
            for row in conn.execute(
                "SELECT decision, COUNT(*) as cnt FROM alert_resolutions GROUP BY decision"
            ).fetchall():
                decision_counts[row["decision"]] = row["cnt"]

            # Counts by resolution type
            type_counts = {}
            for row in conn.execute(
                "SELECT resolution_type, COUNT(*) as cnt FROM alert_resolutions GROUP BY resolution_type"
            ).fetchall():
                type_counts[row["resolution_type"]] = row["cnt"]

            # False positive rate
            false_positives = type_counts.get("false_positive", 0)
            fp_rate = round(false_positives / total * 100, 1) if total > 0 else 0

            # Escalation rate
            escalated = decision_counts.get("escalate", 0)
            escalation_rate = round(escalated / total * 100, 1) if total > 0 else 0

            # Resolution rate (resolved + dismiss vs total alerts)
            resolved_count = decision_counts.get("resolve", 0) + decision_counts.get("dismiss", 0)
            resolution_rate = round(resolved_count / total * 100, 1) if total > 0 else 0

            # Avg time to resolve (if we can compute from alert creation to resolution)
            avg_time_hours = self._compute_avg_resolution_time(conn)

            return {
                "total_decisions": total,
                "decision_counts": decision_counts,
                "type_counts": type_counts,
                "false_positive_rate": fp_rate,
                "escalation_rate": escalation_rate,
                "resolution_rate": resolution_rate,
                "avg_time_hours": avg_time_hours,
            }
        finally:
            conn.close()

    def get_alert_impact(self, alert_id: int) -> Dict[str, Any]:
        """Get the impact tracking for a resolved alert."""
        conn = self._conn()
        try:
            resolution = conn.execute(
                "SELECT * FROM alert_resolutions WHERE alert_id = ? ORDER BY created_at DESC LIMIT 1",
                (alert_id,),
            ).fetchone()

            if not resolution:
                return {"alert_id": alert_id, "status": "no_resolution", "impact": None}

            # Get the original alert data
            alert_data = None
            try:
                alert_row = conn.execute(
                    "SELECT * FROM persistent_alerts WHERE id = ?", (alert_id,)
                ).fetchone()
                if alert_row:
                    alert_data = {
                        "metric": alert_row["metric"],
                        "severity": alert_row["severity"],
                        "message": alert_row["message"],
                        "created_at": alert_row["created_at"],
                    }
            except Exception:
                pass

            decision = self._row_to_decision(resolution)
            return {
                "alert_id": alert_id,
                "status": "resolved",
                "decision": decision.to_dict(),
                "alert_data": alert_data,
                "impact": {
                    "metric": decision.impact_metric,
                    "before": decision.impact_before,
                    "after": decision.impact_after,
                    "improved": (
                        decision.impact_after is not None and
                        decision.impact_before is not None and
                        abs(decision.impact_after) < abs(decision.impact_before)
                    ),
                } if decision.impact_metric else None,
            }
        finally:
            conn.close()

    def update_impact(
        self,
        alert_id: int,
        metric: str,
        before_value: float,
        after_value: float,
    ):
        """Update impact tracking for a resolved alert."""
        conn = self._conn()
        try:
            conn.execute(
                """UPDATE alert_resolutions
                   SET impact_metric = ?, impact_before = ?, impact_after = ?
                   WHERE alert_id = ? AND id = (
                       SELECT id FROM alert_resolutions WHERE alert_id = ?
                       ORDER BY created_at DESC LIMIT 1
                   )""",
                (metric, before_value, after_value, alert_id, alert_id),
            )
            conn.commit()
        finally:
            conn.close()

    # ── Internal ───────────────────────────────────────────────────

    def _row_to_decision(self, row: sqlite3.Row) -> AlertDecision:
        return AlertDecision(
            id=row["id"],
            alert_id=row["alert_id"],
            decision=row["decision"],
            explanation=row["explanation"],
            resolution_type=row["resolution_type"],
            resolved_by=row["resolved_by"],
            resolved_at=row["created_at"],
            impact_metric=row["impact_metric"],
            impact_before=row["impact_before"],
            impact_after=row["impact_after"],
        )

    def _compute_avg_resolution_time(self, conn: sqlite3.Connection) -> float:
        """Compute average time between alert creation and resolution."""
        try:
            rows = conn.execute("""
                SELECT ar.created_at as resolved_at, pa.created_at as alert_created
                FROM alert_resolutions ar
                JOIN persistent_alerts pa ON ar.alert_id = pa.id
                ORDER BY ar.created_at DESC LIMIT 100
            """).fetchall()

            if not rows:
                return 0

            from datetime import datetime as dt
            total_hours = 0
            count = 0
            for r in rows:
                try:
                    resolved = dt.fromisoformat(r["resolved_at"].replace("Z", "+00:00"))
                    created = dt.fromisoformat(r["alert_created"].replace("Z", "+00:00"))
                    delta = (resolved - created).total_seconds() / 3600
                    if delta >= 0:
                        total_hours += delta
                        count += 1
                except Exception:
                    pass

            return round(total_hours / count, 1) if count > 0 else 0
        except Exception:
            return 0


# ── Singleton ──────────────────────────────────────────────────────
alert_resolution_manager = AlertResolutionManager()
