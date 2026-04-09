"""
Phase Q-2: Persistent Alert Manager
======================================
DB-backed alert system with:
  - Configurable alert rules per company
  - Auto-trigger on data upload and orchestrator run
  - Severity levels: CRITICAL, WARNING, INFO
  - Acknowledgement workflow
  - Threshold configuration

Uses DataStore's SQLite backend for persistence.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════

@dataclass
class AlertRecord:
    """A single alert record."""
    alert_id: int
    company_id: Optional[int]
    alert_type: str            # threshold_breach | data_upload | report_generated | period_close
    severity: str              # critical | warning | info
    metric: str
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    acknowledged_at: Optional[str] = None
    is_active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "company_id": self.company_id,
            "alert_type": self.alert_type,
            "severity": self.severity,
            "metric": self.metric,
            "message": self.message,
            "data": self.data,
            "created_at": self.created_at,
            "acknowledged_at": self.acknowledged_at,
            "is_active": self.is_active,
        }


@dataclass
class AlertRule:
    """Configurable alert threshold rule."""
    rule_id: int
    metric: str
    operator: str              # gt | lt | gte | lte
    threshold: float
    severity: str
    message_template: str
    is_enabled: bool = True
    company_id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "metric": self.metric,
            "operator": self.operator,
            "threshold": self.threshold,
            "severity": self.severity,
            "message_template": self.message_template,
            "is_enabled": self.is_enabled,
            "company_id": self.company_id,
        }


# ═══════════════════════════════════════════════════════════════════
# SCHEMA
# ═══════════════════════════════════════════════════════════════════

_ALERT_SCHEMA = """
CREATE TABLE IF NOT EXISTS persistent_alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER,
    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    metric TEXT DEFAULT '',
    message TEXT NOT NULL,
    data_json TEXT DEFAULT '{}',
    is_active INTEGER DEFAULT 1,
    acknowledged_at TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_pa_active ON persistent_alerts(is_active);
CREATE INDEX IF NOT EXISTS ix_pa_severity ON persistent_alerts(severity);
CREATE INDEX IF NOT EXISTS ix_pa_company ON persistent_alerts(company_id);

CREATE TABLE IF NOT EXISTS alert_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER,
    metric TEXT NOT NULL,
    operator TEXT NOT NULL,
    threshold REAL NOT NULL,
    severity TEXT DEFAULT 'warning',
    message_template TEXT NOT NULL,
    is_enabled INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);
"""


# ═══════════════════════════════════════════════════════════════════
# DEFAULT RULES
# ═══════════════════════════════════════════════════════════════════

_DEFAULT_RULES = [
    # CRITICAL
    ("cash_runway_months", "lt", 3.0, "critical", "Cash runway below 3 months - immediate action required"),
    ("net_margin_pct", "lt", -20.0, "critical", "Net loss exceeds 20% of revenue - severe financial distress"),
    # WARNING
    ("gross_margin_pct", "lt", 10.0, "warning", "Gross margin below 10% - pricing or cost pressure"),
    ("net_margin_pct", "lt", 0.0, "warning", "Company is operating at a net loss"),
    ("cogs_to_revenue_pct", "gt", 90.0, "warning", "COGS exceeds 90% of revenue - margin erosion"),
    ("debt_to_equity", "gt", 4.0, "warning", "Leverage ratio exceeds 4x - high financial risk"),
]


# ═══════════════════════════════════════════════════════════════════
# OPERATOR EVALUATION
# ═══════════════════════════════════════════════════════════════════

def _eval_op(op: str, value: float, threshold: float) -> bool:
    """Evaluate a comparison operator."""
    if op == "gt":
        return value > threshold
    elif op == "lt":
        return value < threshold
    elif op == "gte":
        return value >= threshold
    elif op == "lte":
        return value <= threshold
    return False


# ═══════════════════════════════════════════════════════════════════
# PERSISTENT ALERT MANAGER
# ═══════════════════════════════════════════════════════════════════

class PersistentAlertManager:
    """
    DB-backed alert manager.

    Stores alerts in SQLite, supports acknowledgement,
    configurable rules, and auto-triggering.
    """

    def __init__(self, db_path: str = "data/finai_store.db"):
        self._db_path = db_path
        self._ensure_schema()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self):
        """Create tables and load defaults if needed."""
        import os
        os.makedirs(os.path.dirname(self._db_path) or ".", exist_ok=True)
        conn = self._conn()
        try:
            conn.executescript(_ALERT_SCHEMA)
            # Load default rules if table is empty
            count = conn.execute("SELECT COUNT(*) as cnt FROM alert_rules").fetchone()["cnt"]
            if count == 0:
                for metric, op, thresh, sev, msg in _DEFAULT_RULES:
                    conn.execute(
                        "INSERT INTO alert_rules (metric, operator, threshold, severity, message_template) VALUES (?, ?, ?, ?, ?)",
                        (metric, op, thresh, sev, msg),
                    )
            conn.commit()
        finally:
            conn.close()

    # ── Alert CRUD ──────────────────────────────────────────────────

    def create_alert(
        self,
        alert_type: str,
        severity: str,
        metric: str,
        message: str,
        data: Optional[Dict] = None,
        company_id: Optional[int] = None,
    ) -> int:
        """Create a new alert, return alert_id."""
        conn = self._conn()
        try:
            cur = conn.execute(
                """INSERT INTO persistent_alerts (company_id, alert_type, severity, metric, message, data_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (company_id, alert_type, severity, metric, message, json.dumps(data or {})),
            )
            conn.commit()
            aid = cur.lastrowid
            logger.info("Alert created: [%s] %s — %s", severity, metric, message)
            return aid
        finally:
            conn.close()

    def get_active_alerts(
        self,
        severity: Optional[str] = None,
        company_id: Optional[int] = None,
    ) -> List[AlertRecord]:
        """Get active (unacknowledged) alerts, optionally filtered."""
        conn = self._conn()
        try:
            query = "SELECT * FROM persistent_alerts WHERE is_active = 1"
            params: List[Any] = []
            if severity:
                query += " AND severity = ?"
                params.append(severity)
            if company_id is not None:
                query += " AND company_id = ?"
                params.append(company_id)
            query += " ORDER BY created_at DESC"

            rows = conn.execute(query, params).fetchall()
            return [self._row_to_alert(r) for r in rows]
        finally:
            conn.close()

    def acknowledge_alert(self, alert_id: int) -> bool:
        """Mark an alert as acknowledged."""
        conn = self._conn()
        try:
            now = datetime.now(timezone.utc).isoformat()
            cur = conn.execute(
                "UPDATE persistent_alerts SET is_active = 0, acknowledged_at = ? WHERE id = ?",
                (now, alert_id),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def get_alert_history(self, limit: int = 50, company_id: Optional[int] = None) -> List[AlertRecord]:
        """Get all alerts (including acknowledged)."""
        conn = self._conn()
        try:
            if company_id is not None:
                rows = conn.execute(
                    "SELECT * FROM persistent_alerts WHERE company_id = ? ORDER BY created_at DESC LIMIT ?",
                    (company_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM persistent_alerts ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [self._row_to_alert(r) for r in rows]
        finally:
            conn.close()

    def _row_to_alert(self, row: sqlite3.Row) -> AlertRecord:
        d = dict(row)
        return AlertRecord(
            alert_id=d["id"],
            company_id=d.get("company_id"),
            alert_type=d["alert_type"],
            severity=d["severity"],
            metric=d.get("metric", ""),
            message=d["message"],
            data=json.loads(d.get("data_json", "{}")),
            created_at=d.get("created_at", ""),
            acknowledged_at=d.get("acknowledged_at"),
            is_active=bool(d.get("is_active", 1)),
        )

    # ── Rules ───────────────────────────────────────────────────────

    def get_rules(self, company_id: Optional[int] = None) -> List[AlertRule]:
        """Get all alert rules."""
        conn = self._conn()
        try:
            if company_id is not None:
                rows = conn.execute(
                    "SELECT * FROM alert_rules WHERE company_id = ? OR company_id IS NULL ORDER BY severity",
                    (company_id,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM alert_rules ORDER BY severity").fetchall()

            result = []
            for r in rows:
                d = dict(r)
                result.append(AlertRule(
                    rule_id=d["id"],
                    metric=d["metric"],
                    operator=d["operator"],
                    threshold=d["threshold"],
                    severity=d["severity"],
                    message_template=d["message_template"],
                    is_enabled=bool(d.get("is_enabled", 1)),
                    company_id=d.get("company_id"),
                ))
            return result
        finally:
            conn.close()

    def add_rule(
        self,
        metric: str,
        operator: str,
        threshold: float,
        severity: str,
        message: str,
        company_id: Optional[int] = None,
    ) -> int:
        """Add a new alert rule, return rule_id."""
        conn = self._conn()
        try:
            cur = conn.execute(
                "INSERT INTO alert_rules (company_id, metric, operator, threshold, severity, message_template) VALUES (?, ?, ?, ?, ?, ?)",
                (company_id, metric, operator, threshold, severity, message),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def update_rule(self, rule_id: int, updates: Dict[str, Any]) -> bool:
        """Update a rule by ID."""
        conn = self._conn()
        try:
            allowed = {"metric", "operator", "threshold", "severity", "message_template", "is_enabled"}
            sets = []
            params = []
            for k, v in updates.items():
                if k in allowed:
                    sets.append(f"{k} = ?")
                    params.append(v)
            if not sets:
                return False
            params.append(rule_id)
            cur = conn.execute(f"UPDATE alert_rules SET {', '.join(sets)} WHERE id = ?", params)
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    # ── Auto-Trigger ────────────────────────────────────────────────

    def evaluate_financials(
        self,
        financials: Dict[str, float],
        balance_sheet: Optional[Dict[str, float]] = None,
        company_id: Optional[int] = None,
    ) -> List[AlertRecord]:
        """
        Run all enabled rules against financials and create alerts for violations.

        Returns list of newly created alerts.
        """
        all_metrics = dict(financials)
        if balance_sheet:
            ca = balance_sheet.get("total_current_assets", 0)
            cl = balance_sheet.get("total_current_liabilities", 0)
            equity = balance_sheet.get("total_equity", 0)
            total_debt = balance_sheet.get("total_liabilities", 0)
            if cl > 0 and "current_ratio" not in all_metrics:
                all_metrics["current_ratio"] = round(ca / cl, 2)
            if equity > 0 and "debt_to_equity" not in all_metrics:
                all_metrics["debt_to_equity"] = round(total_debt / equity, 2)
            all_metrics.update(balance_sheet)

        rules = self.get_rules(company_id)
        new_alerts: List[AlertRecord] = []

        for rule in rules:
            if not rule.is_enabled:
                continue
            value = all_metrics.get(rule.metric)
            if value is None:
                continue

            if _eval_op(rule.operator, float(value), rule.threshold):
                msg = f"{rule.message_template} (current: {value:.2f}, threshold: {rule.threshold:.2f})"
                aid = self.create_alert(
                    alert_type="threshold_breach",
                    severity=rule.severity,
                    metric=rule.metric,
                    message=msg,
                    data={"value": value, "threshold": rule.threshold, "rule_id": rule.rule_id},
                    company_id=company_id,
                )
                # Retrieve the created alert
                alerts = self.get_active_alerts()
                created = next((a for a in alerts if a.alert_id == aid), None)
                if created:
                    new_alerts.append(created)

        return new_alerts

    def create_info_alert(self, event: str, message: str, company_id: Optional[int] = None) -> int:
        """Create an info-level alert for events (upload, report, close)."""
        return self.create_alert("event", "info", event, message, company_id=company_id)

    # ── Utilities ───────────────────────────────────────────────────

    def clear_all(self):
        """Clear all alerts and rules (for testing)."""
        conn = self._conn()
        try:
            conn.execute("DELETE FROM persistent_alerts")
            conn.execute("DELETE FROM alert_rules")
            conn.commit()
        finally:
            conn.close()
        self._ensure_schema()

    def alert_count(self, active_only: bool = True) -> int:
        """Count alerts."""
        conn = self._conn()
        try:
            if active_only:
                r = conn.execute("SELECT COUNT(*) as cnt FROM persistent_alerts WHERE is_active = 1").fetchone()
            else:
                r = conn.execute("SELECT COUNT(*) as cnt FROM persistent_alerts").fetchone()
            return r["cnt"]
        finally:
            conn.close()


# Module-level singleton
alert_manager = PersistentAlertManager()
