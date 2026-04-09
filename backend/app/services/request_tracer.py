"""
RequestTracer — Distributed trace IDs for observability
========================================================
Generates X-Trace-Id per request, propagates through agent calls.
"""

from __future__ import annotations
import uuid
import time
import logging
from contextvars import ContextVar
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Context variable for current trace ID (asyncio-safe)
_current_trace_id: ContextVar[str] = ContextVar('trace_id', default='')
_trace_spans: ContextVar[List[Dict]] = ContextVar('trace_spans', default=[])


def new_trace_id() -> str:
    """Generate a new trace ID."""
    return uuid.uuid4().hex[:16]


def get_trace_id() -> str:
    """Get the current request's trace ID."""
    return _current_trace_id.get()


def set_trace_id(trace_id: str):
    """Set the trace ID for the current request."""
    _current_trace_id.set(trace_id)
    _trace_spans.set([])


def add_span(name: str, duration_ms: float = 0, metadata: Optional[Dict] = None):
    """Add a trace span to the current request."""
    spans = _trace_spans.get()
    spans.append({
        "name": name,
        "trace_id": get_trace_id(),
        "timestamp": time.time(),
        "duration_ms": round(duration_ms, 1),
        "metadata": metadata or {},
    })


def get_spans() -> List[Dict]:
    """Get all spans for the current trace."""
    return _trace_spans.get()


class TraceStore:
    """Stores recent traces for debugging."""

    _instance: Optional["TraceStore"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._traces: List[Dict] = []
        return cls._instance

    def record(self, trace_id: str, path: str, method: str, status: int,
               duration_ms: float, spans: List[Dict]):
        """Record a completed trace."""
        self._traces.append({
            "trace_id": trace_id,
            "path": path,
            "method": method,
            "status": status,
            "duration_ms": round(duration_ms, 1),
            "spans": spans,
            "timestamp": time.time(),
        })
        # Keep last 200 traces
        if len(self._traces) > 200:
            self._traces = self._traces[-100:]

    def get_recent(self, limit: int = 20) -> List[Dict]:
        return self._traces[-limit:]

    def get_by_id(self, trace_id: str) -> Optional[Dict]:
        for t in reversed(self._traces):
            if t["trace_id"] == trace_id:
                return t
        return None


trace_store = TraceStore()
