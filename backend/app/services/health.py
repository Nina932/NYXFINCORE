"""
FinAI Health Check — Comprehensive service health inspection.
==============================================================
Probes every service listed in the service manifest and returns a
structured report with per-service status.

Usage:
    from app.services.health import get_full_health

    result = await get_full_health()
    # {
    #   "status": "healthy" | "degraded" | "unhealthy",
    #   "version": "2.0.0",
    #   "services": { "<name>": {"status": ..., "details": ..., "required": ...}, ... }
    # }

Design rules:
  - Every probe is wrapped in try/except so a single broken import or
    flaky service can never crash the health endpoint.
  - Async checks that hit the network (Ollama, Redis) use short timeouts
    so the endpoint stays responsive.
  - The overall status is ``unhealthy`` only when a *required* service is
    down.  Optional service failures result in ``degraded``.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict

from app.services.service_manifest import SERVICE_MANIFEST

logger = logging.getLogger(__name__)

# ── Individual service probes ──────────────────────────────────────────


async def _check_database() -> Dict[str, str]:
    """Probe the primary database."""
    try:
        from app.database import check_db_health
        result = await check_db_health()
        if result.get("status") == "healthy":
            db_type = result.get("database_type", "unknown")
            version = result.get("version", "")
            return {"status": "healthy", "details": f"{db_type} {version}"}
        return {"status": "unavailable", "details": result.get("error", "unknown error")}
    except Exception as exc:
        return {"status": "unavailable", "details": str(exc)}


async def _check_vector_store() -> Dict[str, str]:
    """Probe ChromaDB / LlamaIndex vector store."""
    try:
        from app.services.vector_store import vector_store
        if vector_store.is_initialized:
            backend = "LlamaIndex+Postgres" if getattr(vector_store, "_llamaindex", False) else "fallback"
            return {"status": "healthy", "details": f"Initialized (backend: {backend})"}
        return {"status": "unavailable", "details": "Not initialized"}
    except Exception as exc:
        return {"status": "unavailable", "details": str(exc)}


async def _check_ollama() -> Dict[str, str]:
    """Probe Ollama local LLM with a 2-second timeout."""
    try:
        from app.services.local_llm import local_llm
        # is_available() does an HTTP call to Ollama; wrap with timeout
        available = await asyncio.wait_for(local_llm.is_available(), timeout=2.0)
        if available:
            status_info = local_llm.get_status()  # sync method
            best = status_info.get("best_model", "unknown")
            model_count = len(status_info.get("models_available", []))
            return {
                "status": "healthy",
                "details": f"{model_count} model(s), best: {best}",
            }
        return {"status": "unavailable", "details": "Ollama not reachable or no models"}
    except asyncio.TimeoutError:
        return {"status": "unavailable", "details": "Ollama probe timed out (>2s)"}
    except Exception as exc:
        return {"status": "unavailable", "details": str(exc)}


async def _check_redis_cache() -> Dict[str, str]:
    """Probe Redis cache backend."""
    try:
        from app.config import settings
        if not getattr(settings, "REDIS_ENABLED", False):
            return {"status": "unavailable", "details": "Redis disabled in settings (using in-memory cache)"}
        from app.services.cache import cache_service
        if not cache_service._initialized:
            return {"status": "unavailable", "details": "Cache service not initialized"}
        # Check if the backend is actually Redis (not InMemoryCache fallback)
        from app.services.cache import RedisCache
        if isinstance(cache_service._backend, RedisCache):
            try:
                r = await asyncio.wait_for(cache_service._backend._get_redis(), timeout=2.0)
                await asyncio.wait_for(r.ping(), timeout=2.0)
                return {"status": "healthy", "details": "Redis connected and responding"}
            except Exception as exc:
                return {"status": "degraded", "details": f"Redis configured but unreachable: {exc}"}
        return {"status": "healthy", "details": "In-memory cache active (Redis not configured)"}
    except Exception as exc:
        return {"status": "unavailable", "details": str(exc)}


async def _check_knowledge_graph() -> Dict[str, str]:
    """Probe the financial knowledge graph."""
    try:
        from app.services.knowledge_graph import knowledge_graph
        if knowledge_graph.is_built:
            count = knowledge_graph.entity_count
            return {"status": "healthy", "details": f"{count} entities indexed"}
        return {"status": "unavailable", "details": "Knowledge graph not built"}
    except Exception as exc:
        return {"status": "unavailable", "details": str(exc)}


async def _check_ontology() -> Dict[str, str]:
    """Probe the FinAI OS ontology engine."""
    try:
        from app.services.ontology_engine import ontology_registry
        if getattr(ontology_registry, "_initialized", False):
            types = ontology_registry.type_count
            objects = ontology_registry.object_count
            return {
                "status": "healthy",
                "details": f"{types} types, {objects} objects",
            }
        return {"status": "unavailable", "details": "Ontology not initialized"}
    except Exception as exc:
        return {"status": "unavailable", "details": str(exc)}


async def _check_data_warehouse() -> Dict[str, str]:
    """Probe the DuckDB analytical warehouse."""
    try:
        from app.services.warehouse import warehouse as finai_warehouse
        if finai_warehouse._initialized:
            path = getattr(finai_warehouse, "_db_path", "unknown")
            return {"status": "healthy", "details": f"Initialized at {path}"}
        return {"status": "unavailable", "details": "Warehouse not initialized"}
    except Exception as exc:
        return {"status": "unavailable", "details": str(exc)}


async def _check_report_scheduler() -> Dict[str, str]:
    """Probe the report scheduler."""
    try:
        from app.config import settings
        if not getattr(settings, "SCHEDULER_ENABLED", False):
            return {"status": "unavailable", "details": "Scheduler disabled in settings"}
        from app.services.scheduler import report_scheduler
        if report_scheduler.is_running:
            interval = report_scheduler.check_interval
            return {"status": "healthy", "details": f"Running (interval: {interval}s)"}
        return {"status": "unavailable", "details": "Scheduler not running"}
    except Exception as exc:
        return {"status": "unavailable", "details": str(exc)}


async def _check_multi_agent_system() -> Dict[str, str]:
    """Probe the multi-agent system registry."""
    try:
        from app.config import settings
        from app.agents.registry import AgentRegistry
        registry = AgentRegistry()
        agents = registry.names()
        if agents:
            return {
                "status": "healthy",
                "details": f"{len(agents)} agents registered: {', '.join(agents)}",
            }
        if settings.AGENT_MODE == "multi":
            return {"status": "degraded", "details": "Multi-agent mode enabled but no agents registered"}
        return {"status": "unavailable", "details": "Agent system not initialized"}
    except Exception as exc:
        return {"status": "unavailable", "details": str(exc)}


async def _check_anthropic_api() -> Dict[str, str]:
    """Check if Anthropic API key is configured (no live call)."""
    try:
        from app.config import settings
        if settings.ANTHROPIC_API_KEY:
            model = settings.ANTHROPIC_MODEL
            # Mask key for display: show first 8 and last 4 chars
            key = settings.ANTHROPIC_API_KEY
            masked = f"{key[:8]}...{key[-4:]}" if len(key) > 12 else "***"
            return {
                "status": "healthy",
                "details": f"Key configured ({masked}), model: {model}",
            }
        return {"status": "unavailable", "details": "ANTHROPIC_API_KEY not set"}
    except Exception as exc:
        return {"status": "unavailable", "details": str(exc)}


async def _check_smtp() -> Dict[str, str]:
    """Check if SMTP email is configured (no live call)."""
    try:
        from app.config import settings
        if getattr(settings, "SMTP_ENABLED", False):
            host = settings.SMTP_HOST
            port = settings.SMTP_PORT
            user = settings.SMTP_USER
            has_password = bool(settings.SMTP_PASSWORD)
            if user and has_password:
                return {
                    "status": "healthy",
                    "details": f"Configured: {host}:{port} (user: {user})",
                }
            return {
                "status": "degraded",
                "details": f"SMTP enabled but credentials incomplete ({host}:{port})",
            }
        return {"status": "unavailable", "details": "SMTP disabled in settings"}
    except Exception as exc:
        return {"status": "unavailable", "details": str(exc)}


# ── Probe dispatch table ──────────────────────────────────────────────

_PROBES = {
    "database": _check_database,
    "vector_store": _check_vector_store,
    "ollama": _check_ollama,
    "redis_cache": _check_redis_cache,
    "knowledge_graph": _check_knowledge_graph,
    "ontology": _check_ontology,
    "data_warehouse": _check_data_warehouse,
    "report_scheduler": _check_report_scheduler,
    "multi_agent_system": _check_multi_agent_system,
    "anthropic_api": _check_anthropic_api,
    "smtp": _check_smtp,
}


# ── Main entry point ──────────────────────────────────────────────────


async def get_full_health() -> Dict[str, Any]:
    """Check all services and return comprehensive health status.

    Returns a dict with:
      - ``status``: overall platform health (healthy / degraded / unhealthy)
      - ``version``: application version
      - ``checked_at_ms``: wall-clock time the check took
      - ``services``: per-service breakdown
    """
    from app.config import settings

    start = time.monotonic()

    # Run all probes concurrently
    service_names = list(_PROBES.keys())
    results = await asyncio.gather(
        *[_PROBES[name]() for name in service_names],
        return_exceptions=True,
    )

    services: Dict[str, Dict[str, Any]] = {}
    for name, result in zip(service_names, results):
        manifest_entry = SERVICE_MANIFEST.get(name, {})
        required = manifest_entry.get("required", False)

        if isinstance(result, Exception):
            services[name] = {
                "status": "unavailable",
                "details": f"Probe crashed: {result}",
                "required": required,
            }
        else:
            services[name] = {
                **result,
                "required": required,
            }

    # Compute overall status
    required_down = any(
        s["status"] != "healthy"
        for name, s in services.items()
        if s.get("required")
    )
    any_degraded = any(
        s["status"] in ("degraded", "unavailable")
        for s in services.values()
    )

    if required_down:
        overall = "unhealthy"
    elif any_degraded:
        overall = "degraded"
    else:
        overall = "healthy"

    elapsed_ms = round((time.monotonic() - start) * 1000, 1)

    return {
        "status": overall,
        "version": getattr(settings, "APP_VERSION", "2.0.0"),
        "env": settings.APP_ENV,
        "agent_mode": settings.AGENT_MODE,
        "checked_at_ms": elapsed_ms,
        "services": services,
    }
