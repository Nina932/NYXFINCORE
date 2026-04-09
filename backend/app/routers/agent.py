"""
FinAI Agent Router — Aggregator
=================================
Thin aggregator: delegates all endpoint logic to sub-routers.

  Sub-router              | Endpoints
  ------------------------+------------------------------------------------
  agent_chat.py           | /chat, /status, /captain, /memory, /feedback
  agent_monitoring.py     | /agents/status, KG, reasoning, telemetry, orch
  agent_dashboard.py      | /dashboard, /compare, /strategy, KPIs
  agent_upload.py         | /upload, /smart-upload, /parse-excel
  agent_services.py       | /currency, /workflow, /activity, /company360
  agent_datasets.py       | /datasets, /classifications, /connectors
  agent_decisions.py      | /decisions, /predictions, /monitoring rules
  agent_intelligence.py   | /reason, /stress-test, /debate, /audit-trail
  agent_consolidation.py  | /consolidation (register, group, run, analyze)
"""
from fastapi import APIRouter
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent", tags=["agent"])


def _include(sub_name: str, import_path: str):
    """Fault-isolated sub-router include — logs errors instead of crashing."""
    try:
        import importlib
        mod = importlib.import_module(import_path)
        router.include_router(mod.router)
        logger.debug("Agent sub-router loaded: %s", sub_name)
    except Exception as exc:
        logger.error(
            "AGENT SUB-ROUTER LOAD FAILED [%s] from %s: %s",
            sub_name, import_path, exc, exc_info=True,
        )


_include("chat",       "app.routers.agent_chat")
_include("monitoring", "app.routers.agent_monitoring")
_include("dashboard",  "app.routers.agent_dashboard")
_include("upload",     "app.routers.agent_upload")
_include("services",   "app.routers.agent_services")
_include("datasets",     "app.routers.agent_datasets")
_include("decisions",    "app.routers.agent_decisions")
_include("intelligence", "app.routers.agent_intelligence")
_include("consolidation", "app.routers.agent_consolidation")
