"""
FinAI Agent Monitoring Sub-Router — Slim Core
===============================================
Status, audit, health, metrics, telemetry, KG, reasoning, ingestion,
GL pipeline, learning, benchmarks, forecasting, diagnosis endpoints.

Decisions, orchestrator, and intelligence endpoints were extracted to:
  agent_decisions.py  — decisions, predictions, monitoring, orchestrator, companies
  agent_intelligence.py — deep reasoning, stress test, debate, reports, market data

All routes served under /api/agent prefix (set by parent router in agent.py).
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, Integer
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from app.database import get_db
from app.models.all_models import AgentMemory, Feedback
from app.config import settings
import logging

logger = logging.getLogger(__name__)
router = APIRouter()  # NO prefix — parent adds /api/agent


# ── Multi-Agent Status / Health / Metrics ────────────────────────────────────

@router.get("/agents/status")
async def agents_status():
    """List all registered agents, their capabilities, and health."""
    try:
        from app.agents.supervisor import supervisor
        return supervisor.status()
    except Exception as e:
        return {"error": str(e), "mode": settings.AGENT_MODE}


@router.get("/agents/audit")
async def agents_audit(limit: int = 50, agent_name: str = None, db: AsyncSession = Depends(get_db)):
    """Recent audit log for multi-agent system."""
    from app.models.all_models import AgentAuditLog
    q = select(AgentAuditLog).order_by(AgentAuditLog.created_at.desc()).limit(limit)
    if agent_name:
        q = q.where(AgentAuditLog.agent_name == agent_name)
    result = await db.execute(q)
    entries = result.scalars().all()
    return [e.to_dict() for e in entries]


@router.get("/agents/health")
async def agents_health():
    """Comprehensive health for all agents — circuit breakers, success rates, latency."""
    try:
        from app.agents.supervisor import supervisor
        return supervisor.health()
    except Exception as e:
        return {"error": str(e), "all_healthy": False}


@router.get("/agents/metrics")
async def agents_metrics(db: AsyncSession = Depends(get_db)):
    """Token usage, latency, and error rates across agents."""
    from app.models.all_models import AgentAuditLog
    from sqlalchemy import func as sqlfunc
    result = await db.execute(
        select(
            AgentAuditLog.agent_name,
            sqlfunc.count().label("total_calls"),
            sqlfunc.sum(AgentAuditLog.tokens_input).label("total_input_tokens"),
            sqlfunc.sum(AgentAuditLog.tokens_output).label("total_output_tokens"),
            sqlfunc.avg(AgentAuditLog.duration_ms).label("avg_latency_ms"),
            sqlfunc.sum(sqlfunc.cast(AgentAuditLog.status == "error", Integer)).label("error_count"),
        ).group_by(AgentAuditLog.agent_name)
    )
    rows = result.all()
    return [
        {
            "agent_name": r[0], "total_calls": r[1],
            "total_input_tokens": r[2] or 0, "total_output_tokens": r[3] or 0,
            "avg_latency_ms": round(r[4] or 0, 1),
            "error_count": r[5] or 0,
            "error_rate_pct": round((r[5] or 0) / r[1] * 100, 1) if r[1] > 0 else 0,
        }
        for r in rows
    ]


# ── Knowledge Graph ───────────────────────────────────────────────────────────

@router.get("/agents/knowledge-graph")
async def knowledge_graph_status():
    """Knowledge graph status — entities, types, relationships."""
    try:
        from app.services.knowledge_graph import knowledge_graph
        return knowledge_graph.status()
    except Exception as e:
        return {"error": str(e), "is_built": False}


@router.get("/agents/knowledge-graph/query")
async def knowledge_graph_query(q: str, max_results: int = 10):
    """Query the knowledge graph for financial domain knowledge."""
    try:
        from app.services.knowledge_graph import knowledge_graph
        if not knowledge_graph.is_built:
            knowledge_graph.build()
        entities = knowledge_graph.query(q, max_results=max_results)
        return {"query": q, "results": [e.to_dict() for e in entities], "count": len(entities)}
    except Exception as e:
        return {"error": str(e), "query": q, "results": []}


@router.get("/agents/knowledge-graph/account/{account_code}")
async def knowledge_graph_account(account_code: str):
    """Get comprehensive context for an account code from the knowledge graph."""
    try:
        from app.services.knowledge_graph import knowledge_graph
        if not knowledge_graph.is_built:
            knowledge_graph.build()
        return knowledge_graph.get_context_for_account(account_code)
    except Exception as e:
        return {"error": str(e), "account_code": account_code}


# ── Reasoning ────────────────────────────────────────────────────────────────

@router.post("/agents/reasoning/explain")
async def reasoning_explain(body: dict):
    """Phase E: Causal explanation for a metric change."""
    try:
        from app.services.financial_reasoning import reasoning_engine
        from_val = float(body.get("from_value", 100))
        change = body.get("change")
        to_val = from_val * (1 + float(change) / 100) if change is not None else float(body.get("to_value", from_val))
        chain = reasoning_engine.explain_metric_change(
            metric=body.get("metric", "gross_margin_pct"),
            from_value=from_val, to_value=to_val,
            period_from=body.get("period_from", "Previous"),
            period_to=body.get("period_to", "Current"),
            context=body.get("context", {}),
        )
        return {
            "metric": chain.metric, "from_value": chain.from_value, "to_value": chain.to_value,
            "change_pct": round(chain.change_pct or 0, 2), "severity": chain.severity,
            "primary_cause": chain.primary_cause,
            "factors": [{"factor": f.factor, "direction": f.impact_direction, "magnitude": f.magnitude,
                         "impact_pct": f.impact_pct, "explanation": f.explanation, "accounts": f.account_codes}
                        for f in chain.factors],
            "recommendations": chain.recommendations, "narrative": chain.narrative,
            "kg_entities_used": chain.kg_entities_used,
        }
    except Exception as e:
        return {"error": str(e)}


@router.post("/agents/reasoning/scenario")
async def reasoning_scenario(body: dict):
    """Phase E: Financial scenario simulation (what-if analysis)."""
    try:
        from app.services.financial_reasoning import reasoning_engine
        result = reasoning_engine.simulate_scenario(
            scenario_name=body.get("scenario_name", "Scenario"),
            base=body.get("base", {}), changes=body.get("changes", {}),
        )
        return {
            "scenario_name": result.scenario_name, "risk_level": result.risk_level,
            "base": {"revenue": result.base_revenue, "gross_profit": result.base_gross_profit,
                     "ebitda": result.base_ebitda, "net_profit": result.base_net_profit},
            "scenario": {"revenue": result.scenario_revenue, "gross_profit": result.scenario_gross_profit,
                         "ebitda": result.scenario_ebitda, "net_profit": result.scenario_net_profit},
            "changes_pct": {"revenue": round(result.revenue_change_pct, 2),
                            "gross_profit": round(result.gross_profit_change_pct, 2),
                            "ebitda": round(result.ebitda_change_pct, 2),
                            "net_profit": round(result.net_profit_change_pct, 2)},
            "narrative": result.narrative,
        }
    except Exception as e:
        return {"error": str(e)}


@router.post("/agents/accounting/check")
async def accounting_check(body: dict):
    """Validate P&L and BS for accounting consistency."""
    try:
        from app.services.financial_reasoning import reasoning_engine
        issues = reasoning_engine.detect_accounting_issues(body.get("pl", {}), body.get("bs", {}))
        liquidity = reasoning_engine.build_liquidity_analysis(body.get("bs", {}))
        return {
            "accounting_issues": issues, "issue_count": len(issues),
            "critical_count": sum(1 for i in issues if i["severity"] == "critical"),
            "liquidity": liquidity,
            "overall_health": ("critical" if any(i["severity"] == "critical" for i in issues)
                               else "warning" if issues else "healthy"),
        }
    except Exception as e:
        return {"error": str(e)}


# ── Telemetry ─────────────────────────────────────────────────────────────────

@router.get("/agents/telemetry")
async def agents_telemetry():
    """Real-time AI telemetry — agent calls, LLM tier breakdown, KG usage, health score."""
    try:
        from app.services.telemetry import telemetry
        return {"metrics": telemetry.metrics_summary(), "health": telemetry.health_score()}
    except Exception as e:
        return {"error": str(e)}


@router.get("/agents/telemetry/recent")
async def agents_telemetry_recent(limit: int = 20):
    """Recent agent call records for debugging (last N calls)."""
    try:
        from app.services.telemetry import telemetry
        return {"recent_calls": telemetry.recent_agent_calls(limit=limit), "count": limit}
    except Exception as e:
        return {"error": str(e)}


# ── Collaborative Reasoning Architecture (CRA) ────────────────────────────────

@router.post("/agents/reasoning/collaborative")
async def reasoning_collaborative(body: dict, db: AsyncSession = Depends(get_db)):
    """Run a collaborative multi-agent reasoning session."""
    try:
        from app.services.reasoning_session import reasoning_session
        from app.models.all_models import Dataset

        query = body.get("query", "")
        dataset_ids = body.get("dataset_ids", [])
        period = body.get("period", "")
        currency = body.get("currency", "GEL")

        if not dataset_ids:
            result = await db.execute(select(Dataset).where(Dataset.is_active == True))  # noqa: E712
            active = result.scalars().all()
            dataset_ids = [ds.id for ds in active]

        session_ctx = await reasoning_session.run(
            query=query, db=db, dataset_ids=dataset_ids, period=period, currency=currency,
        )
        return {
            "session": session_ctx.to_dict(),
            "formatted_output": session_ctx.formatted_output,
            "executive_summary": session_ctx.executive_summary,
            "contributing_agents": session_ctx.contributing_agents,
            "confidence": session_ctx.confidence_score,
            "latency_ms": session_ctx.total_latency_ms,
        }
    except Exception as e:
        return {"error": str(e), "formatted_output": "", "confidence": 0.0}


@router.get("/agents/reasoning/cra-status")
async def cra_status():
    """Check CRA availability and capabilities."""
    try:
        from app.services.reasoning_session import reasoning_session, TaskDecomposer
        decomposer = TaskDecomposer()
        return {
            "available": True, "patterns": len(decomposer._PATTERNS),
            "max_steps": 6, "complexity_threshold": 2,
            "capabilities": [
                "margin_analysis", "variance_explanation", "period_comparison",
                "forecasting", "report_generation", "anomaly_detection",
            ],
        }
    except ImportError:
        return {"available": False}


# ── Ingestion Intelligence ────────────────────────────────────────────────────

@router.post("/agents/ingestion/detect")
async def ingestion_detect(body: dict):
    """Detect the schema type of a financial file from sample rows."""
    try:
        from app.services.ingestion_intelligence import IngestionPipeline
        pipeline = IngestionPipeline()
        rows_tuples = [tuple(r) for r in body.get("rows", [])]
        result = pipeline.detect_from_sample(rows_tuples, body.get("filename", "unknown.xlsx"))
        return {
            "schema_type": result.schema_type, "confidence": result.confidence,
            "columns": result.columns, "signals": result.signals,
            "warnings": result.warnings, "row_count": result.row_count,
        }
    except Exception as e:
        return {"error": str(e), "schema_type": "UNKNOWN", "confidence": 0.0}


@router.post("/agents/ingestion/parse-coa")
async def ingestion_parse_coa(body: dict):
    """Parse a 1C Chart of Accounts from row data."""
    try:
        from app.services.onec_interpreter import OneCInterpreter
        interp = OneCInterpreter()
        rows_tpl = [tuple(r) for r in body.get("rows", [])]
        tree = interp._parse_rows(rows_tpl)
        summary = tree.summary()
        return {
            "summary": summary,
            "pl_accounts_sample": [
                {"code": a.code, "name": a.name_ka or a.name_ru, "pl_line": a.ifrs_pl_line}
                for a in tree.filter(ifrs_section="income_statement")[:20]
            ],
            "bs_accounts_sample": [
                {"code": a.code, "name": a.name_ka or a.name_ru,
                 "bs_side": a.ifrs_bs_side, "bs_line": a.ifrs_bs_line}
                for a in tree.filter(ifrs_section="balance_sheet")[:20]
            ],
            "dimension_types": sorted({s for a in tree.accounts for s in a.subkonto_semantics if s}),
            "kg_entities": len(tree.to_kg_entities()),
        }
    except Exception as e:
        return {"error": str(e)}


@router.post("/agents/ingestion/classify-account")
async def ingestion_classify_account(body: dict):
    """Classify a single account code: P&L line, BS section, CF section, normal balance."""
    try:
        from app.services.account_hierarchy import account_hierarchy_builder
        from app.services.knowledge_graph import knowledge_graph
        code = str(body.get("account_code", "")).strip()
        result = account_hierarchy_builder.classify_account(code)
        if not knowledge_graph.is_built:
            knowledge_graph.build()
        kg_entities = knowledge_graph.query(f"account {code}", max_results=3)
        result["kg_matches"] = [{"id": e.entity_id, "label": e.label_en, "type": e.entity_type}
                                 for e in kg_entities]
        return result
    except Exception as e:
        return {"error": str(e)}


@router.post("/agents/ingestion/build-statements")
async def ingestion_build_statements(body: dict):
    """Build P&L, BS, and CF from a list of GL transactions."""
    try:
        from app.services.account_hierarchy import financial_statement_mapper
        stmts = financial_statement_mapper.build_statements(
            body.get("transactions", []),
            period=body.get("period", ""),
            currency=body.get("currency", "GEL"),
        )
        return stmts.to_dict()
    except Exception as e:
        return {"error": str(e)}


# ── GL Pipeline ───────────────────────────────────────────────────────────────

@router.post("/agents/gl/trial-balance")
async def gl_trial_balance(body: dict):
    """Phase G-1: Build trial balance from GL transactions."""
    try:
        from app.services.gl_pipeline import gl_pipeline
        result = gl_pipeline.run_from_transactions(
            body.get("transactions", []),
            period=body.get("period", ""),
            currency=body.get("currency", "GEL"),
        )
        return result.get("trial_balance", {})
    except Exception as e:
        return {"error": str(e)}


@router.post("/agents/gl/full-pipeline")
async def gl_full_pipeline(body: dict):
    """Phase G-1: Full GL → TB → IS → BS → CF pipeline with reconciliation."""
    try:
        from app.services.gl_pipeline import gl_pipeline
        return gl_pipeline.run_from_transactions(
            body.get("transactions", []),
            period=body.get("period", ""),
            currency=body.get("currency", "GEL"),
        )
    except Exception as e:
        return {"error": str(e)}


# ── Learning ──────────────────────────────────────────────────────────────────

@router.get("/agents/learning/accuracy")
async def learning_accuracy(db: AsyncSession = Depends(get_db)):
    """Phase G-2: Return classification accuracy metrics."""
    try:
        from app.services.learning_engine import learning_engine
        try:
            return await learning_engine.accuracy_report(db)
        except TypeError:
            return learning_engine.accuracy_report()
    except Exception as e:
        return {"error": str(e)}


@router.get("/agents/memory")
async def agent_memory(db: AsyncSession = Depends(get_db)):
    """Get agent memory entries — corrections, learned patterns, context."""
    try:
        result = await db.execute(select(AgentMemory).order_by(AgentMemory.id.desc()).limit(50))
        memories = result.scalars().all()
        return {
            "total": len(memories),
            "entries": [
                m.to_dict() if hasattr(m, "to_dict")
                else {"id": m.id, "key": getattr(m, "key", ""),
                      "value": getattr(m, "value", ""), "importance": getattr(m, "importance", 0)}
                for m in memories
            ],
        }
    except Exception as e:
        return {"error": str(e), "total": 0, "entries": []}


@router.post("/agents/learning/sync")
async def learning_sync():
    """Phase G-2: Sync learned classifications to knowledge graph."""
    try:
        from app.services.learning_engine import learning_engine
        count = learning_engine.sync_to_kg()
        return {"synced_entities": count, "status": "ok"}
    except Exception as e:
        return {"error": str(e)}


# ── Benchmarks ────────────────────────────────────────────────────────────────

@router.get("/agents/benchmarks/industries")
async def list_industries():
    """Phase G-3: List all available industry benchmark profiles."""
    try:
        from app.services.benchmark_engine import benchmark_engine
        return {"industries": benchmark_engine.list_industries()}
    except Exception as e:
        return {"error": str(e)}


@router.get("/agents/benchmarks/profile/{industry_id}")
async def get_benchmark_profile(industry_id: str):
    """Phase G-3: Get benchmark profile details for an industry."""
    try:
        from app.services.benchmark_engine import benchmark_engine
        profile = benchmark_engine.get_profile(industry_id)
        if not profile:
            return {"error": f"Industry '{industry_id}' not found"}
        return profile.to_dict()
    except Exception as e:
        return {"error": str(e)}


@router.post("/agents/benchmarks/compare")
async def compare_benchmarks(body: dict):
    """Phase G-3: Compare actual financial metrics against industry benchmarks."""
    try:
        from app.services.benchmark_engine import benchmark_engine
        metrics = body.get("metrics", {})
        industry = body.get("industry", None)
        comparisons = benchmark_engine.compare(metrics, industry_id=industry)
        ind_name = industry or benchmark_engine.get_industry()
        healthy = sum(1 for c in comparisons if c.status == "healthy")
        warning = sum(1 for c in comparisons if c.status == "warning")
        critical = sum(1 for c in comparisons if c.status == "critical")
        total = len(comparisons)
        below = warning + critical
        if total > 0 and below > 0:
            summary = f"Performance is below {ind_name.replace('_', ' ')} industry average on {below} of {total} metrics."
        elif total > 0:
            summary = f"All {total} metrics meet or exceed {ind_name.replace('_', ' ')} industry benchmarks."
        else:
            summary = "No benchmark comparisons available."
        return {
            "industry": ind_name,
            "comparisons": [c.to_dict() for c in comparisons],
            "healthy_count": healthy, "warning_count": warning,
            "critical_count": critical, "summary": summary,
        }
    except Exception as e:
        return {"error": str(e)}


# ── Forecasting ───────────────────────────────────────────────────────────────

@router.post("/agents/forecast/ensemble")
async def ensemble_forecast(body: dict):
    """Phase G-5: Generate ensemble forecast with confidence intervals."""
    try:
        from app.services.forecast_ensemble import forecast_ensemble
        result = forecast_ensemble.ensemble_forecast(
            historical_values=body.get("values", []),
            historical_periods=body.get("periods", []),
            forecast_periods=body.get("forecast_periods", 6),
            confidence_level=body.get("confidence_level", 0.95),
            methods=body.get("methods", None),
        )
        return result.to_dict()
    except Exception as e:
        return {"error": str(e)}


@router.post("/agents/forecast/backtest")
async def forecast_backtest(body: dict):
    """Phase G-5: Backtest forecasting methods and report accuracy."""
    try:
        from app.services.forecast_ensemble import forecast_ensemble
        results = forecast_ensemble.backtest(
            historical_values=body.get("values", []),
            historical_periods=body.get("periods", []),
            holdout_pct=body.get("holdout_pct", 0.2),
            methods=body.get("methods", None),
        )
        forecast_ensemble.update_weights_from_backtest(results)
        return {"methods": [r.to_dict() for r in results], "updated_weights": forecast_ensemble._weights}
    except Exception as e:
        return {"error": str(e)}


# ── Diagnosis ─────────────────────────────────────────────────────────────────

@router.post("/agents/diagnosis/run")
async def diagnosis_run(body: dict):
    """Phase H: Full financial diagnostic engine — interpret, diagnose, recommend."""
    try:
        from app.services.diagnosis_engine import diagnosis_engine
        report = diagnosis_engine.run_full_diagnosis(
            current_financials=body.get("current", {}),
            previous_financials=body.get("previous", None),
            balance_sheet=body.get("balance_sheet", None),
            industry_id=body.get("industry", "fuel_distribution"),
            anomaly_summary=body.get("anomaly_summary", None),
        )
        return report.to_dict()
    except Exception as e:
        return {"error": str(e)}


# ── Include focused sub-routers ───────────────────────────────────────────────


def _include(name: str, import_path: str) -> None:
    """Fault-isolated sub-router include."""
    try:
        import importlib
        mod = importlib.import_module(import_path)
        router.include_router(mod.router)
    except Exception as exc:
        logger.error("MONITORING SUB-ROUTER LOAD FAILED [%s]: %s", name, exc, exc_info=True)


_include("decisions",    "app.routers.agent_decisions")
_include("intelligence", "app.routers.agent_intelligence")
