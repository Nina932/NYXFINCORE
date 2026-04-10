"""
FinAI Service Manifest — Authoritative registry of all platform services.
=========================================================================
Documents every service the platform depends on, marking each as required
or optional.  Used by:

  1. ``app.services.health.get_full_health()`` to know which failures are
     critical vs. acceptable degradation.
  2. ``GET /api/system/services`` to expose the catalog at runtime.

Each entry carries a ``check`` callable key (populated by the health
module at import time) so the manifest remains a plain data structure
that can be imported without side-effects.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Literal, Optional

ServiceStatus = Literal["healthy", "degraded", "unavailable", "unchecked"]


SERVICE_MANIFEST: Dict[str, Dict[str, Any]] = {
    "database": {
        "required": True,
        "description": (
            "SQLite or PostgreSQL -- primary data store for all transactional "
            "and analytical data."
        ),
        "docs_url": None,
    },
    "vector_store": {
        "required": False,
        "description": (
            "ChromaDB / LlamaIndex vector store for RAG semantic search. "
            "Without it: AI chat loses contextual grounding but still works "
            "via template responses."
        ),
        "docs_url": None,
    },
    "ollama": {
        "required": False,
        "description": (
            "Ollama local LLM service for offline AI inference. "
            "Without it: falls back to cloud APIs (Claude, NVIDIA, Gemini) "
            "or template responses."
        ),
        "docs_url": "http://localhost:11434",
    },
    "redis_cache": {
        "required": False,
        "description": (
            "Redis cache backend for high-throughput caching. "
            "Without it: in-memory dict cache is used automatically."
        ),
        "docs_url": None,
    },
    "knowledge_graph": {
        "required": False,
        "description": (
            "In-memory financial knowledge graph (710+ entities). "
            "Without it: AI responses lack deep financial domain knowledge."
        ),
        "docs_url": None,
    },
    "ontology": {
        "required": False,
        "description": (
            "FinAI OS ontology engine -- typed object graph with computed "
            "fields, relationships, and versioning."
        ),
        "docs_url": None,
    },
    "data_warehouse": {
        "required": False,
        "description": (
            "DuckDB analytical warehouse for OLAP queries. "
            "Without it: all analytics run directly against the OLTP database."
        ),
        "docs_url": None,
    },
    "report_scheduler": {
        "required": False,
        "description": (
            "Background scheduler for automated report generation and email "
            "delivery. Without it: reports must be triggered manually."
        ),
        "docs_url": None,
    },
    "multi_agent_system": {
        "required": False,
        "description": (
            "Multi-agent AI system (Supervisor + specialized agents). "
            "Without it: falls back to legacy monolithic FinAIAgent."
        ),
        "docs_url": None,
    },
    "anthropic_api": {
        "required": False,
        "description": (
            "Anthropic Claude LLM API for AI chat and reasoning. "
            "Without it: chat is unavailable but all deterministic financial "
            "APIs (P&L, Balance Sheet, GL Pipeline, Forecasting) remain fully "
            "operational."
        ),
        "docs_url": "https://docs.anthropic.com",
    },
    "smtp": {
        "required": False,
        "description": (
            "SMTP email service for sending scheduled reports. "
            "Without it: reports can be generated but not emailed."
        ),
        "docs_url": None,
    },
}


def get_manifest_summary() -> list[dict[str, Any]]:
    """Return the manifest as a list of dicts suitable for JSON serialization."""
    return [
        {
            "service": name,
            "required": entry["required"],
            "description": entry["description"],
            "docs_url": entry.get("docs_url"),
        }
        for name, entry in SERVICE_MANIFEST.items()
    ]
