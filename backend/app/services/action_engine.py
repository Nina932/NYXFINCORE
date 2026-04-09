"""
FinAI OS — Action Engine (Workflow State Machine)
==================================================
Human-in-the-loop action approval system.
Extends existing DecisionEngine with execution workflows.

State machine: proposed → pending_approval → approved → executing → completed/failed/rejected

Usage:
    from app.services.action_engine import action_engine
    execution = action_engine.propose("Restructure debt", "capital_optimization", 27.8, "low")
    action_engine.approve(execution.execution_id, "user@company.com")
    action_engine.execute(execution.execution_id)
"""

import logging
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class ActionStatus(str, Enum):
    PROPOSED = "proposed"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


@dataclass
class ActionExecution:
    execution_id: str
    description: str
    category: str
    roi_estimate: float = 0.0
    risk_level: str = "medium"
    expected_impact: float = 0.0
    composite_score: float = 0.0
    parameters: Dict[str, Any] = field(default_factory=dict)  # FIX #10: typed action parameters
    validation_errors: List[str] = field(default_factory=list)
    status: ActionStatus = ActionStatus.PROPOSED
    requested_by: str = "system"
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[Dict] = None
    rejection_reason: Optional[str] = None
    created_at: str = ""
    source_action_id: Optional[int] = None  # FK to decision_actions if applicable

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "description": self.description,
            "category": self.category,
            "roi_estimate": self.roi_estimate,
            "risk_level": self.risk_level,
            "expected_impact": self.expected_impact,
            "composite_score": self.composite_score,
            "parameters": self.parameters,
            "validation_errors": self.validation_errors,
            "status": self.status.value if isinstance(self.status, ActionStatus) else self.status,
            "requested_by": self.requested_by,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "result": self.result,
            "rejection_reason": self.rejection_reason,
            "created_at": self.created_at,
            "source_action_id": self.source_action_id,
        }


@dataclass
class Notification:
    notification_id: str
    notification_type: str  # action_proposed, action_approved, alert_triggered, report_ready
    title: str
    message: str
    link: str = ""
    is_read: bool = False
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict:
        return {
            "id": self.notification_id,
            "type": self.notification_type,
            "title": self.title,
            "message": self.message,
            "link": self.link,
            "is_read": self.is_read,
            "created_at": self.created_at,
        }


# FIX #10: Typed action parameter schemas per category
ACTION_PARAM_SCHEMAS: Dict[str, Dict[str, str]] = {
    "cost_reduction": {
        "target_area": "string",  # e.g., "admin", "operations", "procurement"
        "reduction_pct": "float",  # target reduction percentage
        "timeline_months": "int",
    },
    "revenue_growth": {
        "growth_channel": "string",  # e.g., "retail", "wholesale", "new_market"
        "target_increase_pct": "float",
        "investment_required": "float",
    },
    "risk_mitigation": {
        "risk_type": "string",
        "mitigation_strategy": "string",
        "urgency": "string",  # low, medium, high, critical
    },
    "capital_optimization": {
        "optimization_type": "string",  # e.g., "debt_restructure", "working_capital"
        "target_metric": "string",
        "expected_improvement": "float",
    },
    "operational_efficiency": {
        "process_area": "string",
        "efficiency_target_pct": "float",
    },
}


class ActionEngine:
    """Manages action lifecycle with human-in-the-loop approval."""

    def __init__(self):
        self._executions: Dict[str, ActionExecution] = {}
        self._notifications: List[Notification] = []

    # ─── Propose ─────────────────────────────────────────────────────

    def _broadcast(self, event_type: str, data: dict):
        """Broadcast event via SSE (FIX #6)."""
        try:
            from app.routers.ontology import broadcast_event
            broadcast_event(event_type, data)
        except Exception:
            pass

    def _validate_params(self, category: str, parameters: Dict) -> List[str]:
        """FIX #10: Validate typed action parameters against schema."""
        errors = []
        schema = ACTION_PARAM_SCHEMAS.get(category, {})
        for param_name, param_type in schema.items():
            if param_name in parameters:
                val = parameters[param_name]
                if param_type == "float" and not isinstance(val, (int, float)):
                    errors.append(f"{param_name} must be a number")
                elif param_type == "int" and not isinstance(val, int):
                    errors.append(f"{param_name} must be an integer")
                elif param_type == "string" and not isinstance(val, str):
                    errors.append(f"{param_name} must be a string")
        return errors

    def propose(
        self,
        description: str,
        category: str,
        roi_estimate: float = 0.0,
        risk_level: str = "medium",
        expected_impact: float = 0.0,
        composite_score: float = 0.0,
        parameters: Optional[Dict[str, Any]] = None,
        auto_approve: bool = False,
        requested_by: str = "system",
        source_action_id: Optional[int] = None,
    ) -> ActionExecution:
        params = parameters or {}
        validation_errors = self._validate_params(category, params)

        execution = ActionExecution(
            execution_id=str(uuid.uuid4())[:12],
            description=description,
            category=category,
            roi_estimate=roi_estimate,
            risk_level=risk_level,
            expected_impact=expected_impact,
            composite_score=composite_score,
            parameters=params,
            validation_errors=validation_errors,
            status=ActionStatus.PENDING_APPROVAL if not auto_approve else ActionStatus.APPROVED,
            requested_by=requested_by,
            source_action_id=source_action_id,
        )

        if auto_approve:
            execution.approved_by = "auto"
            execution.approved_at = datetime.now(timezone.utc).isoformat()

        self._executions[execution.execution_id] = execution

        # Broadcast real-time event (FIX #6)
        self._broadcast("action_proposed", {"execution_id": execution.execution_id, "category": category, "description": description[:80]})

        # Notify
        self._notify(
            "action_proposed",
            f"New Action: {category}",
            description[:100],
            f"/actions",
        )

        logger.info(f"Action proposed: {execution.execution_id} — {description[:60]}")
        return execution

    # ─── Approve ─────────────────────────────────────────────────────

    def approve(self, execution_id: str, approver: str) -> ActionExecution:
        ex = self._executions.get(execution_id)
        if not ex:
            raise ValueError(f"Execution not found: {execution_id}")
        if ex.status not in (ActionStatus.PROPOSED, ActionStatus.PENDING_APPROVAL):
            raise ValueError(f"Cannot approve: current status is {ex.status}")

        ex.status = ActionStatus.APPROVED
        ex.approved_by = approver
        ex.approved_at = datetime.now(timezone.utc).isoformat()

        self._notify("action_approved", "Action Approved", f"{ex.description[:80]} approved by {approver}", "/actions")
        logger.info(f"Action approved: {execution_id} by {approver}")
        self._broadcast("action_approved", {"execution_id": execution_id, "approver": approver})
        return ex

    # ─── Reject ──────────────────────────────────────────────────────

    def reject(self, execution_id: str, approver: str, reason: str = "") -> ActionExecution:
        ex = self._executions.get(execution_id)
        if not ex:
            raise ValueError(f"Execution not found: {execution_id}")

        ex.status = ActionStatus.REJECTED
        ex.approved_by = approver
        ex.rejection_reason = reason
        ex.completed_at = datetime.now(timezone.utc).isoformat()

        self._notify("action_rejected", "Action Rejected", f"{ex.description[:80]} — {reason}", "/actions")
        return ex

    # ─── Execute ─────────────────────────────────────────────────────

    def execute(self, execution_id: str) -> ActionExecution:
        ex = self._executions.get(execution_id)
        if not ex:
            raise ValueError(f"Execution not found: {execution_id}")
        if ex.status != ActionStatus.APPROVED:
            raise ValueError(f"Cannot execute: status is {ex.status}")

        ex.status = ActionStatus.EXECUTING
        ex.started_at = datetime.now(timezone.utc).isoformat()

        # Simulate execution (in production: call actual services)
        try:
            ex.result = {
                "executed": True,
                "roi_achieved": ex.roi_estimate * 0.85,  # conservative estimate
                "notes": f"Action '{ex.description[:40]}...' simulated successfully",
            }
            ex.status = ActionStatus.COMPLETED
            ex.completed_at = datetime.now(timezone.utc).isoformat()
            self._notify("action_completed", "Action Completed", f"{ex.description[:80]}", "/actions")
        except Exception as e:
            ex.status = ActionStatus.FAILED
            ex.result = {"error": str(e)}
            ex.completed_at = datetime.now(timezone.utc).isoformat()

        return ex

    # ─── Query ───────────────────────────────────────────────────────

    def get_pending(self) -> List[ActionExecution]:
        return [e for e in self._executions.values() if e.status in (ActionStatus.PROPOSED, ActionStatus.PENDING_APPROVAL)]

    def get_history(self, limit: int = 50) -> List[ActionExecution]:
        all_execs = sorted(self._executions.values(), key=lambda e: e.created_at, reverse=True)
        return all_execs[:limit]

    def get_execution(self, execution_id: str) -> Optional[ActionExecution]:
        return self._executions.get(execution_id)

    def get_stats(self) -> Dict[str, int]:
        counts = {}
        for ex in self._executions.values():
            s = ex.status.value if isinstance(ex.status, ActionStatus) else ex.status
            counts[s] = counts.get(s, 0) + 1
        return counts

    # ─── Notifications ───────────────────────────────────────────────

    def _notify(self, ntype: str, title: str, message: str, link: str = ""):
        self._notifications.append(Notification(
            notification_id=str(uuid.uuid4())[:12],
            notification_type=ntype,
            title=title,
            message=message,
            link=link,
        ))

    def get_notifications(self, unread_only: bool = False) -> List[Notification]:
        if unread_only:
            return [n for n in self._notifications if not n.is_read]
        return list(reversed(self._notifications[-50:]))

    def get_unread_count(self) -> int:
        return sum(1 for n in self._notifications if not n.is_read)

    def mark_read(self, notification_id: str) -> bool:
        for n in self._notifications:
            if n.notification_id == notification_id:
                n.is_read = True
                return True
        return False

    def mark_all_read(self) -> int:
        count = 0
        for n in self._notifications:
            if not n.is_read:
                n.is_read = True
                count += 1
        return count

    # ─── Sync from Decision Engine ───────────────────────────────────

    def sync_from_decisions(self, decision_report: Dict) -> List[ActionExecution]:
        """Convert DecisionEngine output to pending action executions."""
        created = []
        actions = decision_report.get("actions", [])
        for action in actions:
            ex = self.propose(
                description=action.get("description", "Unnamed action"),
                category=action.get("category", "operational_efficiency"),
                roi_estimate=action.get("roi_estimate", 0),
                risk_level=action.get("risk_level", "medium"),
                expected_impact=action.get("expected_impact", 0),
                composite_score=action.get("composite_score", 0),
            )
            created.append(ex)
        return created


# Singleton
action_engine = ActionEngine()
