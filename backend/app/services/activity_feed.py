"""
FinAI OS — Activity Feed & Distributed Tracing (Palantir AIP Observability Pattern)
=====================================================================================
Complete activity monitoring system with hierarchical span tracing.

Key concepts:
  - ActivityEvent: A single observable event (function call, action, upload, LLM call)
  - LLMTrace: Detailed trace of an LLM invocation (model, tokens, tool_calls)
  - ActivityFeed: Singleton feed with FIFO in-memory storage (max 10,000 events)
  - Distributed Tracing: trace_id groups related spans, parent_event_id nests them

Usage:
    from app.services.activity_feed import activity_feed

    # Record an event
    event_id = activity_feed.record(
        event_type="function_execution",
        resource_type="FinancialStatement",
        resource_id="company-1-2025-01",
        action="orchestrator_run",
        details={"stages": 7, "company": "NYX Core Thinker"},
        status="success",
        duration_ms=145,
        user_id="user@company.com",
    )

    # Record LLM trace
    activity_feed.record_llm_trace(
        event_id=event_id,
        model="claude-sonnet-4-20250514",
        prompt="Analyze gross margin decline...",
        response="The gross margin declined by 3.2% due to...",
        tokens_in=450, tokens_out=280, duration_ms=820,
    )

    # Get feed
    events = activity_feed.get_feed(resource_type="FinancialStatement", limit=20)

    # Get distributed trace
    trace = activity_feed.get_trace("trace-abc123")

    # Get metrics
    metrics = activity_feed.get_metrics(hours=24)
"""

import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

MAX_EVENTS = 10_000
MAX_TEXT_LEN = 500


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class ActivityEvent:
    """A single observable event in the system."""
    id: str
    event_type: str  # function_execution, action_executed, automation_triggered, llm_call, user_action, upload, system
    resource_type: str  # FinancialStatement, Company, KPI, Workflow, etc.
    resource_id: str
    user_id: str
    action: str  # what happened: "orchestrator_run", "smart_upload", "captain_chat", etc.
    details: Dict[str, Any]
    status: str  # success, failure, warning
    duration_ms: int
    parent_event_id: Optional[str]  # for nesting (sub-spans)
    trace_id: str  # groups related spans into a single trace
    span_order: int  # ordering within a trace
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "event_type": self.event_type,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "user_id": self.user_id,
            "action": self.action,
            "details": self.details,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "parent_event_id": self.parent_event_id,
            "trace_id": self.trace_id,
            "span_order": self.span_order,
            "created_at": self.created_at,
        }


@dataclass
class LLMTrace:
    """Detailed trace of an LLM invocation."""
    id: str
    event_id: str  # FK to ActivityEvent.id
    model: str
    prompt_text: str  # first 500 chars
    response_text: str  # first 500 chars
    tokens_input: int
    tokens_output: int
    tool_calls: List[str]
    duration_ms: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "event_id": self.event_id,
            "model": self.model,
            "prompt_text": self.prompt_text,
            "response_text": self.response_text,
            "tokens_input": self.tokens_input,
            "tokens_output": self.tokens_output,
            "tool_calls": self.tool_calls,
            "duration_ms": self.duration_ms,
        }


# =============================================================================
# ACTIVITY FEED (Singleton)
# =============================================================================

class ActivityFeed:
    """
    In-memory activity feed with FIFO eviction.
    Provides distributed tracing, filtering, metrics, and timeline views.
    """

    def __init__(self):
        self._events: List[ActivityEvent] = []
        self._llm_traces: Dict[str, LLMTrace] = {}  # event_id -> LLMTrace
        self._trace_counter: Dict[str, int] = defaultdict(int)  # trace_id -> span count

    # ── Recording ────────────────────────────────────────────────────

    def record(
        self,
        event_type: str,
        resource_type: str,
        resource_id: str,
        action: str,
        details: Optional[Dict[str, Any]] = None,
        status: str = "success",
        duration_ms: int = 0,
        user_id: str = "system",
        trace_id: Optional[str] = None,
        parent_event_id: Optional[str] = None,
    ) -> str:
        """Record an activity event. Returns the event ID."""
        event_id = f"evt-{uuid.uuid4().hex[:12]}"
        if not trace_id:
            trace_id = f"trace-{uuid.uuid4().hex[:10]}"

        self._trace_counter[trace_id] += 1
        span_order = self._trace_counter[trace_id]

        event = ActivityEvent(
            id=event_id,
            event_type=event_type,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            action=action,
            details=details or {},
            status=status,
            duration_ms=duration_ms,
            parent_event_id=parent_event_id,
            trace_id=trace_id,
            span_order=span_order,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        self._events.append(event)

        # FIFO eviction
        if len(self._events) > MAX_EVENTS:
            evicted = self._events[:len(self._events) - MAX_EVENTS]
            self._events = self._events[-MAX_EVENTS:]
            # Clean up LLM traces for evicted events
            for ev in evicted:
                self._llm_traces.pop(ev.id, None)

        logger.debug("Activity recorded: %s %s/%s [%s] %dms",
                      event_type, resource_type, action, status, duration_ms)
        return event_id

    def record_llm_trace(
        self,
        event_id: str,
        model: str,
        prompt: str,
        response: str,
        tokens_in: int = 0,
        tokens_out: int = 0,
        duration_ms: int = 0,
        tool_calls: Optional[List[str]] = None,
    ) -> str:
        """Record detailed LLM trace for an event. Returns trace ID."""
        trace_id = f"llm-{uuid.uuid4().hex[:10]}"
        trace = LLMTrace(
            id=trace_id,
            event_id=event_id,
            model=model,
            prompt_text=str(prompt)[:MAX_TEXT_LEN],
            response_text=str(response)[:MAX_TEXT_LEN],
            tokens_input=tokens_in,
            tokens_output=tokens_out,
            tool_calls=tool_calls or [],
            duration_ms=duration_ms,
        )
        self._llm_traces[event_id] = trace
        return trace_id

    # ── Querying ─────────────────────────────────────────────────────

    def get_feed(
        self,
        resource_type: Optional[str] = None,
        event_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get activity feed with optional filters."""
        filtered = self._events[:]

        if resource_type:
            filtered = [e for e in filtered if e.resource_type == resource_type]
        if event_type:
            filtered = [e for e in filtered if e.event_type == event_type]
        if status:
            filtered = [e for e in filtered if e.status == status]

        # Reverse chronological
        filtered.sort(key=lambda e: e.created_at, reverse=True)

        page = filtered[offset:offset + limit]
        results = []
        for ev in page:
            d = ev.to_dict()
            # Attach LLM trace if exists
            llm = self._llm_traces.get(ev.id)
            if llm:
                d["llm_trace"] = llm.to_dict()
            results.append(d)

        return results

    def get_trace(self, trace_id: str) -> Dict[str, Any]:
        """Get hierarchical span tree for a distributed trace."""
        spans = [e for e in self._events if e.trace_id == trace_id]
        if not spans:
            return {"trace_id": trace_id, "spans": [], "total_duration_ms": 0}

        spans.sort(key=lambda e: e.span_order)

        # Build hierarchy
        root_spans = []
        children_map: Dict[str, List[Dict]] = defaultdict(list)

        for span in spans:
            span_dict = span.to_dict()
            llm = self._llm_traces.get(span.id)
            if llm:
                span_dict["llm_trace"] = llm.to_dict()
            span_dict["children"] = []

            if span.parent_event_id:
                children_map[span.parent_event_id].append(span_dict)
            else:
                root_spans.append(span_dict)

        # Attach children recursively
        def attach_children(node: Dict):
            node_id = node["id"]
            kids = children_map.get(node_id, [])
            node["children"] = kids
            for kid in kids:
                attach_children(kid)

        for root in root_spans:
            attach_children(root)

        total_duration = sum(s.duration_ms for s in spans)

        return {
            "trace_id": trace_id,
            "spans": root_spans,
            "span_count": len(spans),
            "total_duration_ms": total_duration,
            "started_at": spans[0].created_at if spans else None,
            "status": "failure" if any(s.status == "failure" for s in spans) else "success",
        }

    def get_metrics(self, hours: int = 24) -> Dict[str, Any]:
        """Get aggregated metrics per resource type for the last N hours."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        cutoff_iso = cutoff.isoformat()

        recent = [e for e in self._events if e.created_at >= cutoff_iso]

        # Aggregate by resource_type
        by_resource: Dict[str, Dict] = defaultdict(lambda: {
            "total_events": 0,
            "success_count": 0,
            "failure_count": 0,
            "warning_count": 0,
            "total_duration_ms": 0,
            "avg_duration_ms": 0,
            "event_types": defaultdict(int),
        })

        for ev in recent:
            bucket = by_resource[ev.resource_type]
            bucket["total_events"] += 1
            if ev.status == "success":
                bucket["success_count"] += 1
            elif ev.status == "failure":
                bucket["failure_count"] += 1
            elif ev.status == "warning":
                bucket["warning_count"] += 1
            bucket["total_duration_ms"] += ev.duration_ms
            bucket["event_types"][ev.event_type] += 1

        # Compute averages and finalize
        result = {}
        for rt, bucket in by_resource.items():
            total = bucket["total_events"]
            bucket["avg_duration_ms"] = round(bucket["total_duration_ms"] / total, 1) if total > 0 else 0
            bucket["success_rate_pct"] = round(bucket["success_count"] / total * 100, 1) if total > 0 else 0
            bucket["event_types"] = dict(bucket["event_types"])
            result[rt] = bucket

        # LLM stats
        llm_count = len(self._llm_traces)
        total_input_tokens = sum(t.tokens_input for t in self._llm_traces.values())
        total_output_tokens = sum(t.tokens_output for t in self._llm_traces.values())

        return {
            "period_hours": hours,
            "total_events": len(recent),
            "total_stored_events": len(self._events),
            "by_resource_type": result,
            "llm_stats": {
                "total_calls": llm_count,
                "total_input_tokens": total_input_tokens,
                "total_output_tokens": total_output_tokens,
            },
            "unique_traces": len(set(e.trace_id for e in recent)),
        }

    def get_timeline(self, hours: int = 24) -> Dict[str, Any]:
        """Get hourly event counts for timeline/chart visualization."""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=hours)
        cutoff_iso = cutoff.isoformat()

        recent = [e for e in self._events if e.created_at >= cutoff_iso]

        # Build hourly buckets
        buckets: Dict[str, Dict[str, int]] = {}
        for h in range(hours):
            bucket_time = now - timedelta(hours=hours - h - 1)
            key = bucket_time.strftime("%Y-%m-%dT%H:00:00Z")
            buckets[key] = {"total": 0, "success": 0, "failure": 0, "warning": 0}

        for ev in recent:
            try:
                ev_time = datetime.fromisoformat(ev.created_at.replace("Z", "+00:00"))
                key = ev_time.strftime("%Y-%m-%dT%H:00:00Z")
                if key in buckets:
                    buckets[key]["total"] += 1
                    buckets[key][ev.status] = buckets[key].get(ev.status, 0) + 1
            except (ValueError, KeyError):
                pass

        timeline = [
            {"hour": k, **v}
            for k, v in sorted(buckets.items())
        ]

        return {
            "period_hours": hours,
            "timeline": timeline,
            "total_events": len(recent),
        }


# =============================================================================
# SINGLETON
# =============================================================================

activity_feed = ActivityFeed()


# =============================================================================
# CONTEXT MANAGER for timing
# =============================================================================

class ActivitySpan:
    """Context manager for recording timed activity events."""

    def __init__(
        self,
        event_type: str,
        resource_type: str,
        resource_id: str,
        action: str,
        details: Optional[Dict[str, Any]] = None,
        user_id: str = "system",
        trace_id: Optional[str] = None,
        parent_event_id: Optional[str] = None,
    ):
        self.event_type = event_type
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.action = action
        self.details = details or {}
        self.user_id = user_id
        self.trace_id = trace_id
        self.parent_event_id = parent_event_id
        self._start_time = 0.0
        self.event_id: Optional[str] = None

    def __enter__(self):
        self._start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = int((time.time() - self._start_time) * 1000)
        status = "failure" if exc_type else "success"
        if exc_type:
            self.details["error"] = str(exc_val)[:200]

        self.event_id = activity_feed.record(
            event_type=self.event_type,
            resource_type=self.resource_type,
            resource_id=self.resource_id,
            action=self.action,
            details=self.details,
            status=status,
            duration_ms=duration_ms,
            user_id=self.user_id,
            trace_id=self.trace_id,
            parent_event_id=self.parent_event_id,
        )
        return False  # Don't suppress exceptions
