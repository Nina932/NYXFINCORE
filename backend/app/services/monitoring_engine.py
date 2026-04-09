"""
SHIM: Re-exports from app.services.v2.monitoring_engine (DB-persisted, async).
Original v1 code preserved in monitoring_engine_v1.py.
"""
from app.services.v2.monitoring_engine import (  # noqa: F401
    monitoring_engine,
    UnifiedMonitoringEngine,
    MonitoringAlert,
    MonitoringCheck,
    MonitoringDashboard,
)
