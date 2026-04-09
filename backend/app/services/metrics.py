"""
FinAI Metrics — Prometheus-compatible metrics endpoint
======================================================
Exposes application metrics in Prometheus text format at /metrics.
No external dependency required — uses plain text exposition format.

Metrics collected:
  - HTTP request counts and latencies (by endpoint, method, status)
  - Agent execution counts and durations (by agent name)
  - Flywheel cycle stats
  - Ontology object counts
  - Database query counts
  - LLM call counts (by model, tier)
"""

from __future__ import annotations
import logging
import time
from collections import defaultdict
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Collects application metrics for Prometheus exposition."""

    _instance: Optional["MetricsCollector"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._counters: Dict[str, float] = defaultdict(float)
            cls._instance._gauges: Dict[str, float] = defaultdict(float)
            cls._instance._histograms: Dict[str, list] = defaultdict(list)
            cls._instance._start_time = time.time()
        return cls._instance

    # ── Counter operations ──

    def inc(self, name: str, value: float = 1.0, **labels):
        """Increment a counter."""
        key = self._make_key(name, labels)
        self._counters[key] += value

    def set_gauge(self, name: str, value: float, **labels):
        """Set a gauge value."""
        key = self._make_key(name, labels)
        self._gauges[key] = value

    def observe(self, name: str, value: float, **labels):
        """Record a histogram observation (latency, etc)."""
        key = self._make_key(name, labels)
        self._histograms[key].append(value)
        # Keep only last 1000 observations per key
        if len(self._histograms[key]) > 1000:
            self._histograms[key] = self._histograms[key][-500:]

    def _make_key(self, name: str, labels: dict) -> str:
        if labels:
            label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
            return f"{name}{{{label_str}}}"
        return name

    # ── Prometheus text format exposition ──

    def render_prometheus(self) -> str:
        """Render all metrics in Prometheus text exposition format."""
        lines = []
        lines.append(f"# FinAI Metrics — {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
        lines.append("")

        # Uptime gauge
        uptime = time.time() - self._start_time
        lines.append("# HELP finai_uptime_seconds Time since server start")
        lines.append("# TYPE finai_uptime_seconds gauge")
        lines.append(f"finai_uptime_seconds {uptime:.0f}")
        lines.append("")

        # Counters
        if self._counters:
            for key, value in sorted(self._counters.items()):
                name = key.split("{")[0] if "{" in key else key
                lines.append(f"# TYPE {name} counter")
                lines.append(f"{key} {value}")
            lines.append("")

        # Gauges
        if self._gauges:
            for key, value in sorted(self._gauges.items()):
                name = key.split("{")[0] if "{" in key else key
                lines.append(f"# TYPE {name} gauge")
                lines.append(f"{key} {value}")
            lines.append("")

        # Histograms (simplified: count + sum + avg)
        if self._histograms:
            for key, values in sorted(self._histograms.items()):
                if not values:
                    continue
                name = key.split("{")[0] if "{" in key else key
                lines.append(f"# TYPE {name} summary")
                lines.append(f"{key}_count {len(values)}")
                lines.append(f"{key}_sum {sum(values):.2f}")
                lines.append(f"{key}_avg {sum(values)/len(values):.2f}")
            lines.append("")

        # Collect live system gauges
        self._collect_live_gauges(lines)

        return "\n".join(lines) + "\n"

    def _collect_live_gauges(self, lines: list):
        """Collect live system metrics at render time."""
        # Ontology stats
        try:
            from app.services.ontology_engine import ontology_registry
            lines.append("# HELP finai_ontology_objects Total ontology objects")
            lines.append("# TYPE finai_ontology_objects gauge")
            lines.append(f"finai_ontology_objects {len(ontology_registry._objects)}")

            lines.append("# HELP finai_ontology_types Registered ontology types")
            lines.append("# TYPE finai_ontology_types gauge")
            lines.append(f"finai_ontology_types {len(ontology_registry._types)}")
            lines.append("")
        except Exception:
            pass

        # Agent health
        try:
            from app.agents.registry import registry
            agents = registry._agents
            for name, agent in agents.items():
                if hasattr(agent, 'health'):
                    h = agent.health
                    healthy = 1 if h.is_healthy else 0
                    lines.append(f'finai_agent_healthy{{agent="{name}"}} {healthy}')
                    lines.append(f'finai_agent_calls{{agent="{name}"}} {h.total_calls}')
                    lines.append(f'finai_agent_errors{{agent="{name}"}} {h.total_errors}')
            lines.append("")
        except Exception:
            pass

        # Tool registry
        try:
            from app.orchestration.tool_registry import tool_registry
            lines.append("# HELP finai_tools_registered Total MCP tools registered")
            lines.append("# TYPE finai_tools_registered gauge")
            lines.append(f"finai_tools_registered {len(tool_registry._tools)}")
            lines.append("")
        except Exception:
            pass

        # Flywheel stats
        try:
            from app.services.flywheel_loop import flywheel_loop
            lines.append(f"finai_flywheel_cycles {flywheel_loop._cycle_count}")
            lines.append(f'finai_flywheel_running {1 if flywheel_loop._running else 0}')
            lines.append("")
        except Exception:
            pass

        # Write guard stats
        try:
            from app.services.ontology_write_guard import write_guard
            lines.append(f"finai_writes_total {write_guard._write_count}")
            lines.append(f"finai_write_audit_entries {len(write_guard._audit_log)}")
            lines.append("")
        except Exception:
            pass

    def get_json_summary(self) -> Dict:
        """Get a JSON summary (for the /system page)."""
        summary = {
            "uptime_seconds": round(time.time() - self._start_time),
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histogram_counts": {k: len(v) for k, v in self._histograms.items()},
        }

        # Live stats
        try:
            from app.services.ontology_engine import ontology_registry
            summary["ontology_objects"] = len(ontology_registry._objects)
        except Exception:
            pass

        try:
            from app.orchestration.tool_registry import tool_registry
            summary["tools_registered"] = len(tool_registry._tools)
        except Exception:
            pass

        try:
            from app.services.flywheel_loop import flywheel_loop
            summary["flywheel_cycles"] = flywheel_loop._cycle_count
            summary["flywheel_running"] = flywheel_loop._running
        except Exception:
            pass

        return summary


metrics = MetricsCollector()
