"""
Phase I: Real-Time Monitoring Engine
======================================
Continuous anomaly detection, proactive alerting, automated report triggering.

Components:
    AlertManager       — Alert lifecycle (create, dedup, acknowledge, cooldown)
    MonitoringEngine   — Rule evaluation against financial metrics
    ProactiveReporter  — Auto-triggers diagnostic reports on critical signals

Rules:
    - ALL threshold checks are deterministic
    - Cooldown-based deduplication prevents alert storms
    - No LLM involved in monitoring decisions
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# DATACLASSES
# ═══════════════════════════════════════════════════════════════════

@dataclass
class MonitoringAlert:
    """An alert triggered by a monitoring rule."""
    alert_type: str        # threshold_breach|anomaly_spike|forecast_deviation|bs_violation
    severity: str          # info|warning|critical|emergency
    metric: str
    threshold_value: float
    current_value: float
    message: str
    rule_id: Optional[int] = None
    is_active: bool = True
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
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
    """A configurable monitoring rule definition."""
    rule_type: str         # threshold|anomaly|forecast_deviation|bs_equation
    metric: str
    operator: str          # gt|lt|gte|lte|eq|neq|deviation_pct
    threshold: float
    severity: str = "warning"
    cooldown_minutes: int = 60
    is_enabled: bool = True
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
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
    """Complete monitoring state snapshot."""
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


# ═══════════════════════════════════════════════════════════════════
# ALERT MANAGER
# ═══════════════════════════════════════════════════════════════════

class AlertManager:
    """Manages alert lifecycle with cooldown-based deduplication."""

    _SEVERITY_RANK = {"info": 0, "warning": 1, "critical": 2, "emergency": 3}

    def __init__(self):
        self._active_alerts: List[MonitoringAlert] = []
        self._alert_history: List[MonitoringAlert] = []
        self._cooldown_tracker: Dict[str, float] = {}  # "rule_type:metric" -> last_trigger_time

    def create_alert(
        self,
        alert_type: str,
        severity: str,
        metric: str,
        threshold: float,
        current: float,
        message: str,
        cooldown_minutes: int = 60,
        rule_id: Optional[int] = None,
    ) -> Optional[MonitoringAlert]:
        """
        Create an alert if not in cooldown for this rule+metric combination.

        Returns:
            MonitoringAlert if created, None if in cooldown.
        """
        cooldown_key = f"{alert_type}:{metric}"

        if self._is_in_cooldown(cooldown_key, cooldown_minutes):
            return None

        alert = MonitoringAlert(
            alert_type=alert_type,
            severity=severity,
            metric=metric,
            threshold_value=threshold,
            current_value=current,
            message=message,
            rule_id=rule_id,
            is_active=True,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        self._active_alerts.append(alert)
        self._alert_history.append(alert)
        self._cooldown_tracker[cooldown_key] = time.time()

        logger.info("Alert created: [%s] %s — %s (value=%.2f, threshold=%.2f)",
                     severity.upper(), metric, message, current, threshold)
        return alert

    def _is_in_cooldown(self, key: str, cooldown_minutes: int) -> bool:
        """Check if a rule+metric is still in cooldown."""
        last_trigger = self._cooldown_tracker.get(key)
        if last_trigger is None:
            return False
        elapsed = time.time() - last_trigger
        return elapsed < (cooldown_minutes * 60)

    def acknowledge_alert(self, alert_index: int) -> bool:
        """Mark an active alert as acknowledged."""
        if 0 <= alert_index < len(self._active_alerts):
            self._active_alerts[alert_index].is_active = False
            return True
        return False

    def get_active_alerts(self) -> List[MonitoringAlert]:
        """Return all currently active (unacknowledged) alerts."""
        return [a for a in self._active_alerts if a.is_active]

    def get_alerts_by_severity(self, severity: str) -> List[MonitoringAlert]:
        """Filter active alerts by severity level."""
        return [a for a in self._active_alerts if a.is_active and a.severity == severity]

    def get_alert_history(self, limit: int = 50) -> List[MonitoringAlert]:
        """Return recent alert history."""
        return self._alert_history[-limit:]

    def clear_resolved(self):
        """Remove inactive alerts from the active list."""
        self._active_alerts = [a for a in self._active_alerts if a.is_active]

    def reset(self):
        """Clear all alerts and cooldowns (for testing)."""
        self._active_alerts.clear()
        self._alert_history.clear()
        self._cooldown_tracker.clear()


# ═══════════════════════════════════════════════════════════════════
# OPERATOR EVALUATION
# ═══════════════════════════════════════════════════════════════════

def _evaluate_operator(operator: str, value: float, threshold: float) -> bool:
    """Evaluate a comparison operator between value and threshold."""
    if operator == "gt":
        return value > threshold
    elif operator == "lt":
        return value < threshold
    elif operator == "gte":
        return value >= threshold
    elif operator == "lte":
        return value <= threshold
    elif operator == "eq":
        return abs(value - threshold) < 0.001
    elif operator == "neq":
        return abs(value - threshold) >= 0.001
    elif operator == "deviation_pct":
        if abs(threshold) < 0.001:
            return False
        deviation = abs(value - threshold) / abs(threshold) * 100
        return deviation > threshold
    return False


# ═══════════════════════════════════════════════════════════════════
# MONITORING ENGINE
# ═══════════════════════════════════════════════════════════════════

class MonitoringEngine:
    """
    Evaluates monitoring rules against financial metrics and generates alerts.

    All checks are deterministic — no LLM calls.
    """

    def __init__(self):
        self.alert_manager = AlertManager()
        self._rules: List[MonitoringCheck] = []
        self._load_default_rules()

    def _load_default_rules(self):
        """Load built-in financial monitoring rules."""
        defaults = [
            MonitoringCheck(
                rule_type="threshold",
                metric="gross_margin_pct",
                operator="lt",
                threshold=0.0,
                severity="emergency",
                cooldown_minutes=30,
                description="Negative gross margin indicates pricing below cost",
            ),
            MonitoringCheck(
                rule_type="threshold",
                metric="net_margin_pct",
                operator="lt",
                threshold=-10.0,
                severity="critical",
                cooldown_minutes=60,
                description="Net margin below -10% signals severe loss",
            ),
            MonitoringCheck(
                rule_type="threshold",
                metric="current_ratio",
                operator="lt",
                threshold=1.0,
                severity="critical",
                cooldown_minutes=60,
                description="Current ratio below 1.0 indicates liquidity risk",
            ),
            MonitoringCheck(
                rule_type="threshold",
                metric="debt_to_equity",
                operator="gt",
                threshold=4.0,
                severity="warning",
                cooldown_minutes=120,
                description="High leverage exceeds safe threshold",
            ),
            MonitoringCheck(
                rule_type="threshold",
                metric="ebitda_margin_pct",
                operator="lt",
                threshold=-5.0,
                severity="critical",
                cooldown_minutes=60,
                description="Negative EBITDA margin indicates operational distress",
            ),
        ]
        self._rules.extend(defaults)

    def run_checks(
        self,
        financials: Dict[str, float],
        balance_sheet: Optional[Dict[str, float]] = None,
    ) -> List[MonitoringAlert]:
        """
        Evaluate all enabled rules against provided financial metrics.

        Args:
            financials: P&L metrics {revenue, cogs, gross_margin_pct, net_margin_pct, ...}
            balance_sheet: BS metrics {total_current_assets, total_current_liabilities, total_equity, ...}

        Returns:
            List of newly generated alerts.
        """
        # Merge financials and balance_sheet metrics
        all_metrics = dict(financials)
        if balance_sheet:
            # Compute derived ratios if not already present
            ca = balance_sheet.get("total_current_assets", 0)
            cl = balance_sheet.get("total_current_liabilities", 0)
            equity = balance_sheet.get("total_equity", 0)
            total_debt = balance_sheet.get("total_liabilities", 0)

            if cl > 0 and "current_ratio" not in all_metrics:
                all_metrics["current_ratio"] = round(ca / cl, 2)
            if equity > 0 and "debt_to_equity" not in all_metrics:
                all_metrics["debt_to_equity"] = round(total_debt / equity, 2)
            elif equity <= 0 and total_debt > 0:
                all_metrics["debt_to_equity"] = 999.0

            all_metrics.update(balance_sheet)

        new_alerts: List[MonitoringAlert] = []

        for i, rule in enumerate(self._rules):
            if not rule.is_enabled:
                continue

            value = all_metrics.get(rule.metric)
            if value is None:
                continue

            if _evaluate_operator(rule.operator, value, rule.threshold):
                message = (
                    f"{rule.description or rule.metric}: "
                    f"current value {value:.2f} {rule.operator} threshold {rule.threshold:.2f}"
                )
                alert = self.alert_manager.create_alert(
                    alert_type=rule.rule_type,
                    severity=rule.severity,
                    metric=rule.metric,
                    threshold=rule.threshold,
                    current=value,
                    message=message,
                    cooldown_minutes=rule.cooldown_minutes,
                    rule_id=i,
                )
                if alert:
                    new_alerts.append(alert)

        # BS equation check
        if balance_sheet:
            assets = balance_sheet.get("total_assets", 0)
            liabilities = balance_sheet.get("total_liabilities", 0)
            equity = balance_sheet.get("total_equity", 0)
            if assets > 0 and abs(assets - liabilities - equity) > 1.0:
                alert = self.alert_manager.create_alert(
                    alert_type="bs_violation",
                    severity="critical",
                    metric="bs_equation",
                    threshold=0.0,
                    current=round(assets - liabilities - equity, 2),
                    message=f"Balance sheet equation violated: Assets ({assets:.0f}) != Liabilities ({liabilities:.0f}) + Equity ({equity:.0f})",
                    cooldown_minutes=30,
                )
                if alert:
                    new_alerts.append(alert)

        logger.info("Monitoring check complete: %d new alerts from %d rules",
                     len(new_alerts), sum(1 for r in self._rules if r.is_enabled))
        return new_alerts

    def add_rule(self, rule: MonitoringCheck):
        """Add a new monitoring rule."""
        self._rules.append(rule)
        logger.info("Monitoring rule added: %s %s %s %.2f (%s)",
                     rule.metric, rule.operator, rule.threshold, rule.threshold, rule.severity)

    def remove_rule(self, index: int) -> bool:
        """Remove a rule by index."""
        if 0 <= index < len(self._rules):
            removed = self._rules.pop(index)
            logger.info("Monitoring rule removed: %s", removed.metric)
            return True
        return False

    def update_rule(self, index: int, updates: Dict[str, Any]) -> bool:
        """Update a rule by index with partial dict."""
        if 0 <= index < len(self._rules):
            rule = self._rules[index]
            for key, val in updates.items():
                if hasattr(rule, key):
                    setattr(rule, key, val)
            return True
        return False

    def get_rules(self) -> List[MonitoringCheck]:
        """Return all monitoring rules."""
        return list(self._rules)


# ═══════════════════════════════════════════════════════════════════
# PROACTIVE REPORTER
# ═══════════════════════════════════════════════════════════════════

class ProactiveReporter:
    """Auto-triggers diagnostic reports when critical alerts are detected."""

    _TRIGGER_SEVERITIES = {"critical", "emergency"}

    def should_trigger_report(self, alerts: List[MonitoringAlert]) -> bool:
        """Return True if any alert warrants an automatic diagnostic report."""
        return any(a.severity in self._TRIGGER_SEVERITIES for a in alerts)

    def generate_triggered_report(
        self,
        financials: Dict[str, float],
        alerts: List[MonitoringAlert],
        balance_sheet: Optional[Dict[str, float]] = None,
        industry_id: str = "fuel_distribution",
    ) -> Dict[str, Any]:
        """
        Auto-generate a diagnostic report in response to critical alerts.

        Returns:
            Dict with diagnostic_report + triggering_alerts.
        """
        try:
            from app.services.diagnosis_engine import diagnosis_engine

            report = diagnosis_engine.run_full_diagnosis(
                current_financials=financials,
                balance_sheet=balance_sheet,
                industry_id=industry_id,
            )
            return {
                "triggered_by": [a.to_dict() for a in alerts if a.severity in self._TRIGGER_SEVERITIES],
                "diagnostic_report": report.to_dict(),
                "auto_generated": True,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            logger.error("Proactive report generation failed: %s", e)
            return {
                "triggered_by": [a.to_dict() for a in alerts if a.severity in self._TRIGGER_SEVERITIES],
                "diagnostic_report": None,
                "auto_generated": True,
                "error": str(e),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }


# ═══════════════════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════════════════

class MonitoringDashboardBuilder:
    """Builds the monitoring dashboard from engine state."""

    def build(self, engine: 'MonitoringEngine') -> MonitoringDashboard:
        """Build a full dashboard snapshot."""
        active = engine.alert_manager.get_active_alerts()
        history = engine.alert_manager.get_alert_history(limit=20)

        summary = {"info": 0, "warning": 0, "critical": 0, "emergency": 0}
        for a in active:
            if a.severity in summary:
                summary[a.severity] += 1

        # Determine system health
        if summary["emergency"] > 0:
            health = "emergency"
        elif summary["critical"] > 0:
            health = "critical"
        elif summary["warning"] > 0:
            health = "warning"
        else:
            health = "healthy"

        enabled = sum(1 for r in engine._rules if r.is_enabled)

        return MonitoringDashboard(
            active_alerts=[a.to_dict() for a in active],
            alert_summary=summary,
            rules_count=len(engine._rules),
            enabled_rules=enabled,
            recent_triggers=[a.to_dict() for a in history[-10:]],
            system_health=health,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )


# ═══════════════════════════════════════════════════════════════════
# UNIFIED MONITORING ENGINE (with dashboard + proactive reporter)
# ═══════════════════════════════════════════════════════════════════

class UnifiedMonitoringEngine(MonitoringEngine):
    """Extends MonitoringEngine with dashboard and proactive reporting."""

    def __init__(self):
        super().__init__()
        self.reporter = ProactiveReporter()
        self._dashboard_builder = MonitoringDashboardBuilder()

    def run_checks_with_report(
        self,
        financials: Dict[str, float],
        balance_sheet: Optional[Dict[str, float]] = None,
        industry_id: str = "fuel_distribution",
    ) -> Dict[str, Any]:
        """
        Run checks and auto-generate report if critical alerts are found.

        Returns:
            Dict with alerts + optional auto-generated report.
        """
        alerts = self.run_checks(financials, balance_sheet)

        result: Dict[str, Any] = {
            "alerts": [a.to_dict() for a in alerts],
            "alert_count": len(alerts),
        }

        if alerts and self.reporter.should_trigger_report(alerts):
            report = self.reporter.generate_triggered_report(
                financials, alerts, balance_sheet, industry_id,
            )
            result["proactive_report"] = report

        return result

    def get_dashboard(self) -> MonitoringDashboard:
        """Get full monitoring dashboard."""
        return self._dashboard_builder.build(self)

    def reset(self):
        """Clear all state (for testing)."""
        self.alert_manager.reset()
        self._rules.clear()
        self._load_default_rules()


# ═══════════════════════════════════════════════════════════════════
# Phase J-3: KPI WATCHER + CASH RUNWAY + EXPENSE SPIKE DETECTION
# ═══════════════════════════════════════════════════════════════════

@dataclass
class KPITarget:
    """A KPI with a target value to track against."""
    metric: str
    target_value: float
    direction: str = "above"   # above|below — whether target is min or max
    description: str = ""
    tolerance_pct: float = 5.0  # within 5% = on track

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric": self.metric,
            "target_value": round(self.target_value, 2),
            "direction": self.direction,
            "description": self.description,
            "tolerance_pct": self.tolerance_pct,
        }


@dataclass
class KPIStatus:
    """Current status of a KPI against its target."""
    metric: str
    target: float
    actual: float
    variance_pct: float
    status: str               # on_track|at_risk|missed|exceeded
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric": self.metric,
            "target": round(self.target, 2),
            "actual": round(self.actual, 2),
            "variance_pct": round(self.variance_pct, 2),
            "status": self.status,
            "description": self.description,
        }


@dataclass
class CashRunway:
    """Cash runway analysis."""
    cash_balance: float
    monthly_burn_rate: float
    runway_months: float
    runway_days: int
    risk_level: str           # safe|caution|warning|critical|emergency
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cash_balance": round(self.cash_balance, 2),
            "monthly_burn_rate": round(self.monthly_burn_rate, 2),
            "runway_months": round(self.runway_months, 1),
            "runway_days": self.runway_days,
            "risk_level": self.risk_level,
            "message": self.message,
        }


class KPIWatcher:
    """Tracks KPIs against targets and detects variance."""

    def __init__(self):
        self._targets: List[KPITarget] = []
        self._load_defaults()

    def _load_defaults(self):
        """Load default KPI targets for fuel distribution."""
        self._targets = [
            KPITarget("gross_margin_pct", 15.0, "above", "Gross margin target"),
            KPITarget("net_margin_pct", 5.0, "above", "Net margin target"),
            KPITarget("ebitda_margin_pct", 8.0, "above", "EBITDA margin target"),
            KPITarget("current_ratio", 1.5, "above", "Liquidity target"),
            KPITarget("debt_to_equity", 2.5, "below", "Leverage ceiling"),
            KPITarget("cogs_to_revenue_pct", 85.0, "below", "Cost efficiency target"),
        ]

    def add_target(self, target: KPITarget):
        """Add a custom KPI target."""
        self._targets.append(target)

    def evaluate(self, financials: Dict[str, float]) -> List[KPIStatus]:
        """Evaluate all KPIs against current financials."""
        statuses: List[KPIStatus] = []
        for target in self._targets:
            actual = financials.get(target.metric)
            if actual is None:
                continue

            if abs(target.target_value) > 0.001:
                variance_pct = round(
                    (actual - target.target_value) / abs(target.target_value) * 100, 2)
            else:
                variance_pct = 0.0

            # Determine status
            if target.direction == "above":
                if actual >= target.target_value:
                    status = "exceeded" if variance_pct > target.tolerance_pct else "on_track"
                elif abs(variance_pct) <= target.tolerance_pct:
                    status = "at_risk"
                else:
                    status = "missed"
            else:  # below
                if actual <= target.target_value:
                    status = "on_track" if abs(variance_pct) <= target.tolerance_pct else "exceeded"
                elif abs(variance_pct) <= target.tolerance_pct:
                    status = "at_risk"
                else:
                    status = "missed"

            statuses.append(KPIStatus(
                metric=target.metric,
                target=target.target_value,
                actual=actual,
                variance_pct=variance_pct,
                status=status,
                description=target.description,
            ))

        return statuses

    def get_targets(self) -> List[KPITarget]:
        return list(self._targets)

    def reset(self):
        self._targets.clear()
        self._load_defaults()


class CashRunwayCalculator:
    """Calculates cash runway and generates alerts."""

    _RISK_THRESHOLDS = [
        (12, "safe", "Cash runway exceeds 12 months — healthy position"),
        (6, "caution", "Cash runway 6-12 months — monitor closely"),
        (3, "warning", "Cash runway 3-6 months — take action to extend"),
        (1, "critical", "Cash runway under 3 months — immediate intervention required"),
        (0, "emergency", "Cash depleted or negative — emergency funding required"),
    ]

    def calculate(
        self,
        cash_balance: float,
        monthly_revenue: float,
        monthly_expenses: float,
    ) -> CashRunway:
        """
        Calculate cash runway based on burn rate.

        Args:
            cash_balance: current cash + equivalents
            monthly_revenue: average monthly revenue (cash inflow)
            monthly_expenses: average monthly total expenses (cash outflow)
        """
        burn_rate = monthly_expenses - monthly_revenue  # positive = burning cash

        if burn_rate <= 0:
            # Company is cash-flow positive
            return CashRunway(
                cash_balance=cash_balance,
                monthly_burn_rate=0,
                runway_months=999,
                runway_days=999 * 30,
                risk_level="safe",
                message="Company is cash-flow positive. No burn rate concern.",
            )

        if cash_balance <= 0:
            return CashRunway(
                cash_balance=cash_balance,
                monthly_burn_rate=burn_rate,
                runway_months=0,
                runway_days=0,
                risk_level="emergency",
                message=f"Cash depleted. Monthly burn: {burn_rate:,.0f} GEL. Immediate funding required.",
            )

        runway_months = round(cash_balance / burn_rate, 1)
        runway_days = int(runway_months * 30)

        risk = "safe"
        message = ""
        for threshold_months, level, msg in self._RISK_THRESHOLDS:
            if runway_months >= threshold_months:
                risk = level
                message = f"{msg}. Runway: {runway_months:.1f} months ({runway_days} days). Burn rate: {burn_rate:,.0f} GEL/month."
                break

        return CashRunway(
            cash_balance=cash_balance,
            monthly_burn_rate=burn_rate,
            runway_months=runway_months,
            runway_days=runway_days,
            risk_level=risk,
            message=message,
        )


class ExpenseSpikeDetector:
    """Detects month-over-month expense spikes."""

    def detect(
        self,
        current_expenses: Dict[str, float],
        previous_expenses: Dict[str, float],
        spike_threshold_pct: float = 15.0,
    ) -> List[Dict[str, Any]]:
        """
        Detect expense categories that spiked beyond threshold.

        Args:
            current_expenses: {category: amount} for current period
            previous_expenses: {category: amount} for previous period
            spike_threshold_pct: % increase threshold to flag
        """
        spikes: List[Dict[str, Any]] = []

        for category, current in current_expenses.items():
            previous = previous_expenses.get(category, 0)
            if abs(previous) < 0.01:
                if current > 0:
                    spikes.append({
                        "category": category,
                        "current": round(current, 2),
                        "previous": 0,
                        "change_pct": 100.0,
                        "severity": "high",
                        "message": f"New expense category: {category} at {current:,.0f} GEL",
                    })
                continue

            change_pct = round((current - previous) / abs(previous) * 100, 2)

            if change_pct > spike_threshold_pct:
                severity = "critical" if change_pct > 50 else "high" if change_pct > 30 else "medium"
                spikes.append({
                    "category": category,
                    "current": round(current, 2),
                    "previous": round(previous, 2),
                    "change_pct": change_pct,
                    "severity": severity,
                    "message": f"{category} increased {change_pct:.1f}% ({previous:,.0f} -> {current:,.0f} GEL)",
                })

        spikes.sort(key=lambda s: s["change_pct"], reverse=True)
        return spikes


# Attach new components to monitoring singleton
monitoring_engine = UnifiedMonitoringEngine()
monitoring_engine.kpi_watcher = KPIWatcher()
monitoring_engine.cash_runway = CashRunwayCalculator()
monitoring_engine.expense_spike = ExpenseSpikeDetector()
