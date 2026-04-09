"""
FinAI v2 Monitoring Engine — DB-persisted alerts and rules.
============================================================
Replaces in-memory alert/rule storage with async SQLAlchemy CRUD
against existing Alert and MonitoringRule models.

Key changes from v1:
- Alerts persist across server restarts
- Rules stored in DB (not just in-memory list)
- Cooldown tracked via last_triggered_at column on MonitoringRule
- asyncio.Lock prevents concurrent duplicate alerts
- Dashboard built from DB queries

Public API:
    from app.services.v2.monitoring_engine import monitoring_engine
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import select, func, update, and_
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ── Dataclasses (API-compatible with v1) ───────────────────────────────

@dataclass
class MonitoringAlert:
    alert_type: str
    severity: str
    metric: str
    threshold_value: float
    current_value: float
    message: str
    rule_id: Optional[int] = None
    is_active: bool = True
    created_at: str = ""
    db_id: Optional[int] = None  # v2: DB primary key

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.db_id,
            "alert_type": self.alert_type,
            "severity": self.severity,
            "metric": self.metric,
            "threshold_value": round(self.threshold_value, 2),
            "current_value": round(self.current_value, 2),
            "message": self.message,
            "rule_id": self.rule_id,
            "is_active": self.is_active,
            "created_at": self.created_at,
        }


@dataclass
class MonitoringCheck:
    rule_type: str
    metric: str
    operator: str
    threshold: float
    severity: str = "warning"
    cooldown_minutes: int = 60
    is_enabled: bool = True
    description: str = ""
    db_id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.db_id,
            "rule_type": self.rule_type,
            "metric": self.metric,
            "operator": self.operator,
            "threshold": self.threshold,
            "severity": self.severity,
            "cooldown_minutes": self.cooldown_minutes,
            "is_enabled": self.is_enabled,
            "description": self.description,
        }


@dataclass
class MonitoringDashboard:
    active_alerts: List[Dict[str, Any]] = field(default_factory=list)
    alert_summary: Dict[str, int] = field(default_factory=lambda: {
        "info": 0, "warning": 0, "critical": 0, "emergency": 0
    })
    rules_count: int = 0
    enabled_rules: int = 0
    recent_triggers: List[Dict[str, Any]] = field(default_factory=list)
    system_health: str = "healthy"
    generated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "active_alerts": self.active_alerts,
            "alert_summary": self.alert_summary,
            "rules_count": self.rules_count,
            "enabled_rules": self.enabled_rules,
            "recent_triggers": self.recent_triggers,
            "system_health": self.system_health,
            "generated_at": self.generated_at,
        }


# ── Operator evaluation ───────────────────────────────────────────────

def _evaluate_operator(operator: str, value: float, threshold: float) -> bool:
    ops = {
        "gt": lambda v, t: v > t,
        "lt": lambda v, t: v < t,
        "gte": lambda v, t: v >= t,
        "lte": lambda v, t: v <= t,
        "eq": lambda v, t: abs(v - t) < 0.001,
        "neq": lambda v, t: abs(v - t) >= 0.001,
    }
    fn = ops.get(operator)
    if fn:
        return fn(value, threshold)
    if operator == "deviation_pct" and abs(threshold) > 0.001:
        return abs(value - threshold) / abs(threshold) * 100 > threshold
    return False


# ── Default rules ─────────────────────────────────────────────────────

_DEFAULT_RULES = [
    MonitoringCheck("threshold", "gross_margin_pct", "lt", 0.0, "emergency", 30,
                    description="Negative gross margin indicates pricing below cost"),
    MonitoringCheck("threshold", "net_margin_pct", "lt", -10.0, "critical", 60,
                    description="Net margin below -10% signals severe loss"),
    MonitoringCheck("threshold", "current_ratio", "lt", 1.0, "critical", 60,
                    description="Current ratio below 1.0 indicates liquidity risk"),
    MonitoringCheck("threshold", "debt_to_equity", "gt", 4.0, "warning", 120,
                    description="High leverage exceeds safe threshold"),
    MonitoringCheck("threshold", "ebitda_margin_pct", "lt", -5.0, "critical", 60,
                    description="Negative EBITDA margin indicates operational distress"),
]


# ── DB-backed Monitoring Engine ────────────────────────────────────────

class UnifiedMonitoringEngine:
    """
    DB-persisted monitoring with concurrency-safe alert creation.

    Rules and alerts survive server restarts. Default rules are seeded
    on first use if the rules table is empty.
    """

    def __init__(self):
        self._lock = asyncio.Lock()
        self._defaults_seeded = False

    async def _ensure_defaults(self, db: AsyncSession) -> None:
        """Seed default monitoring rules if table is empty."""
        if self._defaults_seeded:
            return

        from app.models.all_models import MonitoringRule

        count = (await db.execute(
            select(func.count()).select_from(MonitoringRule)
        )).scalar() or 0

        if count == 0:
            for rule in _DEFAULT_RULES:
                db.add(MonitoringRule(
                    rule_type=rule.rule_type,
                    metric=rule.metric,
                    operator=rule.operator,
                    threshold=rule.threshold,
                    severity=rule.severity,
                    cooldown_minutes=rule.cooldown_minutes,
                    is_enabled=rule.is_enabled,
                    description=rule.description,
                ))
            await db.flush()
            logger.info("Seeded %d default monitoring rules", len(_DEFAULT_RULES))

        self._defaults_seeded = True

    async def run_checks(
        self,
        financials: Dict[str, float],
        balance_sheet: Optional[Dict[str, float]] = None,
        dataset_id: Optional[int] = None,
        db: AsyncSession = None,
    ) -> List[MonitoringAlert]:
        """Evaluate all enabled rules against financial metrics."""
        if not db:
            return []

        await self._ensure_defaults(db)
        from app.models.all_models import MonitoringRule, Alert

        # Merge metrics
        all_metrics = dict(financials)
        if balance_sheet:
            ca = balance_sheet.get("total_current_assets", 0)
            cl = balance_sheet.get("total_current_liabilities", 0)
            equity = balance_sheet.get("total_equity", 0)
            total_debt = balance_sheet.get("total_liabilities", 0)

            if cl > 0 and "current_ratio" not in all_metrics:
                all_metrics["current_ratio"] = round(ca / cl, 2)
            if equity != 0 and "debt_to_equity" not in all_metrics:
                all_metrics["debt_to_equity"] = round(total_debt / equity, 2)

        # Load enabled rules
        result = await db.execute(
            select(MonitoringRule).where(MonitoringRule.is_enabled == True)
        )
        rules = result.scalars().all()

        alerts_created = []

        async with self._lock:  # Prevent concurrent duplicate alerts
            for rule in rules:
                metric_value = all_metrics.get(rule.metric)
                if metric_value is None:
                    continue

                if not _evaluate_operator(rule.operator, metric_value, rule.threshold):
                    continue

                # Cooldown check via last_triggered_at
                if rule.last_triggered_at:
                    cooldown_end = rule.last_triggered_at + timedelta(minutes=rule.cooldown_minutes)
                    if datetime.now(timezone.utc) < cooldown_end:
                        continue

                # Create alert in DB
                message = (
                    f"{rule.description or rule.metric}: "
                    f"value={metric_value:.2f} {rule.operator} threshold={rule.threshold:.2f}"
                )

                alert_record = Alert(
                    alert_type=rule.rule_type,
                    severity=rule.severity,
                    metric=rule.metric,
                    threshold_value=rule.threshold,
                    current_value=metric_value,
                    message=message,
                    is_active=True,
                    rule_id=rule.id,
                    dataset_id=dataset_id,
                )
                db.add(alert_record)

                # Update rule's last triggered
                rule.last_triggered_at = datetime.now(timezone.utc)

                alert = MonitoringAlert(
                    alert_type=rule.rule_type,
                    severity=rule.severity,
                    metric=rule.metric,
                    threshold_value=rule.threshold,
                    current_value=metric_value,
                    message=message,
                    rule_id=rule.id,
                    is_active=True,
                    created_at=datetime.now(timezone.utc).isoformat(),
                )
                alerts_created.append(alert)

                logger.info(
                    "Alert: [%s] %s — %s (value=%.2f, threshold=%.2f)",
                    rule.severity.upper(), rule.metric, message,
                    metric_value, rule.threshold,
                )

            await db.flush()

        return alerts_created

    async def get_active_alerts(self, db: AsyncSession) -> List[Dict[str, Any]]:
        """Return all currently active alerts from DB."""
        from app.models.all_models import Alert

        result = await db.execute(
            select(Alert).where(Alert.is_active == True).order_by(Alert.created_at.desc())
        )
        return [a.to_dict() for a in result.scalars().all()]

    async def acknowledge_alert(self, alert_id: int, db: AsyncSession) -> bool:
        """Acknowledge (deactivate) an alert."""
        from app.models.all_models import Alert

        result = await db.execute(select(Alert).where(Alert.id == alert_id))
        alert = result.scalar_one_or_none()
        if not alert:
            return False

        alert.is_active = False
        alert.acknowledged_at = datetime.now(timezone.utc)
        await db.flush()
        return True

    async def add_rule(self, rule: MonitoringCheck, db: AsyncSession) -> int:
        """Add a new monitoring rule. Returns DB ID."""
        from app.models.all_models import MonitoringRule

        record = MonitoringRule(
            rule_type=rule.rule_type,
            metric=rule.metric,
            operator=rule.operator,
            threshold=rule.threshold,
            severity=rule.severity,
            cooldown_minutes=rule.cooldown_minutes,
            is_enabled=rule.is_enabled,
            description=rule.description,
        )
        db.add(record)
        await db.flush()
        return record.id

    async def get_dashboard(self, db: AsyncSession) -> MonitoringDashboard:
        """Build monitoring dashboard from DB state."""
        from app.models.all_models import Alert, MonitoringRule

        await self._ensure_defaults(db)

        # Active alerts
        active_result = await db.execute(
            select(Alert).where(Alert.is_active == True).order_by(Alert.created_at.desc())
        )
        active_alerts = [a.to_dict() for a in active_result.scalars().all()]

        # Alert summary by severity
        summary = {"info": 0, "warning": 0, "critical": 0, "emergency": 0}
        for a in active_alerts:
            sev = a.get("severity", "info")
            summary[sev] = summary.get(sev, 0) + 1

        # Rules count
        rules_total = (await db.execute(
            select(func.count()).select_from(MonitoringRule)
        )).scalar() or 0
        rules_enabled = (await db.execute(
            select(func.count()).select_from(MonitoringRule).where(MonitoringRule.is_enabled == True)
        )).scalar() or 0

        # Recent triggers (last 20 alerts including resolved)
        recent_result = await db.execute(
            select(Alert).order_by(Alert.created_at.desc()).limit(20)
        )
        recent = [a.to_dict() for a in recent_result.scalars().all()]

        # System health
        health = "healthy"
        if summary.get("emergency", 0) > 0:
            health = "emergency"
        elif summary.get("critical", 0) > 0:
            health = "critical"
        elif summary.get("warning", 0) > 0:
            health = "warning"

        return MonitoringDashboard(
            active_alerts=active_alerts,
            alert_summary=summary,
            rules_count=rules_total,
            enabled_rules=rules_enabled,
            recent_triggers=recent,
            system_health=health,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )


# Module singleton
monitoring_engine = UnifiedMonitoringEngine()
