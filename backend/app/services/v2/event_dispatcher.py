"""
FinAI Foundry — Event Dispatcher
==================================
The GLUE between ontology mutations, journal postings, and workflow execution.

When any event fires (journal posted, object updated, alert triggered):
1. Broadcast to WebSocket clients (existing realtime_manager)
2. Check workflow trigger registry for matching workflows
3. Auto-execute matching workflows with event context
4. Log the event + execution result for audit trail

This is what makes the system REACTIVE — not just a passive data store.

Public API:
    from app.services.v2.event_dispatcher import event_dispatcher
    await event_dispatcher.dispatch("journal_posted", {"entry_id": 42, ...})
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class EventDispatcher:
    """
    Central event bus. Connects:
    - realtime_manager (WebSocket broadcast)
    - workflow_engine (auto-trigger workflows)
    - custom subscribers (any async callback)
    """

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._event_log: List[Dict] = []
        self._max_log = 500
        self._dispatch_count = 0

    def subscribe(self, event_pattern: str, callback: Callable):
        """Register a callback for an event type.

        Args:
            event_pattern: Event type string (e.g., "journal_posted", "ontology_*")
            callback: Async function(event_type, payload) to call
        """
        self._subscribers[event_pattern].append(callback)
        logger.info("Event subscription: %s → %s", event_pattern, callback.__qualname__)

    async def dispatch(self, event_type: str, payload: Optional[Dict[str, Any]] = None):
        """
        Fire an event through the entire system:
        1. Log it
        2. Broadcast to WebSocket clients
        3. Execute matching workflow triggers
        4. Call custom subscribers
        """
        payload = payload or {}
        self._dispatch_count += 1

        event_record = {
            "event_type": event_type,
            "payload": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dispatch_id": self._dispatch_count,
            "results": [],
        }

        logger.info("EVENT DISPATCHED: %s (dispatch #%d)", event_type, self._dispatch_count)

        # 1. Broadcast to WebSocket clients
        try:
            from app.services.realtime import realtime_manager
            await realtime_manager.emit(event_type, payload)
            event_record["results"].append({"target": "websocket", "status": "ok"})
        except Exception as e:
            logger.warning("WebSocket broadcast failed for %s: %s", event_type, e)
            event_record["results"].append({"target": "websocket", "status": "error", "error": str(e)})

        # 2. Auto-trigger matching workflows
        try:
            from app.services.workflow_engine import workflow_engine
            executions = await workflow_engine.on_event(event_type, payload)
            for ex in executions:
                event_record["results"].append({
                    "target": f"workflow:{ex.workflow_id}",
                    "status": ex.status,
                    "execution_id": ex.execution_id,
                })
                logger.info("  → Workflow triggered: %s (status=%s)", ex.workflow_id, ex.status)
        except Exception as e:
            logger.warning("Workflow trigger failed for %s: %s", event_type, e)
            event_record["results"].append({"target": "workflow", "status": "error", "error": str(e)})

        # 3. Call custom subscribers (exact match)
        for callback in self._subscribers.get(event_type, []):
            try:
                await callback(event_type, payload)
                event_record["results"].append({"target": callback.__qualname__, "status": "ok"})
            except Exception as e:
                logger.warning("Subscriber %s failed for %s: %s", callback.__qualname__, event_type, e)

        # 4. Call wildcard subscribers (e.g., "ontology_*" matches "ontology_object_updated")
        for pattern, callbacks in self._subscribers.items():
            if pattern.endswith("*") and event_type.startswith(pattern[:-1]):
                for callback in callbacks:
                    try:
                        await callback(event_type, payload)
                    except Exception as e:
                        logger.warning("Wildcard subscriber failed: %s", e)

        # Store in log
        self._event_log.append(event_record)
        if len(self._event_log) > self._max_log:
            self._event_log = self._event_log[-self._max_log:]

        return event_record

    def get_recent_events(self, limit: int = 50, event_type: str = None) -> List[Dict]:
        """Get recent events from the log."""
        events = self._event_log
        if event_type:
            events = [e for e in events if e["event_type"] == event_type]
        return events[-limit:]

    def stats(self) -> Dict[str, Any]:
        """Event dispatcher statistics."""
        type_counts = defaultdict(int)
        for e in self._event_log:
            type_counts[e["event_type"]] += 1

        return {
            "total_dispatched": self._dispatch_count,
            "log_size": len(self._event_log),
            "subscriber_count": sum(len(cbs) for cbs in self._subscribers.values()),
            "event_types_seen": dict(type_counts),
        }


# Module singleton
event_dispatcher = EventDispatcher()
