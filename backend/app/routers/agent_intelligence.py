"""
FinAI Agent Intelligence Sub-Router
=====================================
Deep reasoning, stress tests, debate, structured reports,
pipeline info, market data, knowledge stats, and audit trail.
Extracted from agent_monitoring.py for maintainability.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, Dict, Any
from app.database import get_db
from app.models.all_models import Feedback
from app.config import settings
import logging

logger = logging.getLogger(__name__)
router = APIRouter()  # NO prefix — parent adds /api/agent


@router.post("/agents/reason")
async def run_deep_reasoning(body: dict):
    """Run deep causal reasoning analysis on financial data."""
    try:
        from app.services.deep_reasoning_engine import deep_reasoning_engine
        result = deep_reasoning_engine.analyze(
            financials=body.get("financials", {}),
            balance_sheet=body.get("balance_sheet", {}),
            period=body.get("period", ""),
            company=body.get("company", ""),
        )
        return result.to_dict()
    except Exception as e:
        logger.error("deep_reasoning error: %s", e, exc_info=True)
        return {"error": str(e)}


@router.post("/agents/stress-test")
async def run_stress_test(body: dict):
    """Run correlated Monte-Carlo stress test."""
    try:
        from app.services.stress_test_engine import stress_test_engine
        result = stress_test_engine.run(
            base_financials=body.get("financials", {}),
            n_simulations=body.get("simulations", 5000),
            seed=body.get("seed", None),
        )
        return result.to_dict()
    except Exception as e:
        logger.error("stress_test error: %s", e, exc_info=True)
        return {"error": str(e)}


@router.post("/agents/debate")
async def run_debate(body: dict):
    """Run multi-agent debate (Proposer → Critic → Resolver)."""
    try:
        from app.services.debate_engine import debate_engine
        result = await debate_engine.run_debate(
            financials=body.get("financials", {}),
            balance_sheet=body.get("balance_sheet", {}),
            period=body.get("period", ""),
            company=body.get("company", ""),
        )
        return result.to_dict()
    except Exception as e:
        logger.error("debate error: %s", e, exc_info=True)
        return {"error": str(e)}


@router.post("/agents/report/generate")
async def generate_structured_report(body: dict):
    """Generate a professional multi-section financial report using Nemotron."""
    try:
        from app.services.structured_report_engine import structured_report_engine
        from app.services.stress_test_engine import stress_test_engine

        stress_data = None
        try:
            stress_result = stress_test_engine.run(body.get("financials", {}), n_simulations=2000)
            stress_data = stress_result.to_dict()
        except Exception:
            pass

        result = await structured_report_engine.generate(
            financials=body.get("financials", {}),
            balance_sheet=body.get("balance_sheet", {}),
            stress_data=stress_data,
            company=body.get("company", ""),
            period=body.get("period", ""),
            health_score=body.get("health_score", 0),
        )
        return result.to_dict()
    except Exception as e:
        logger.error("structured_report error: %s", e, exc_info=True)
        return {"error": str(e)}


@router.get("/agents/workflow/pipeline")
async def get_pipeline_info():
    """Return the LangGraph pipeline structure for visualization."""
    return {
        "nodes": [
            {"id": "data_extractor", "label": "Data Extractor", "type": "input",
             "description": "Parse Excel, detect sheets, extract financials"},
            {"id": "calculator", "label": "Calculator", "type": "process",
             "description": "Compute ratios, margins, derived metrics"},
            {"id": "insight_engine", "label": "Insight Engine", "type": "process",
             "description": "Detect signals, classify severity"},
            {"id": "memory", "label": "Memory", "type": "storage",
             "description": "Store company context, prior periods"},
            {"id": "orchestrator", "label": "Orchestrator", "type": "decision",
             "description": "7-stage pipeline: diagnosis → decision → strategy"},
            {"id": "anomaly_detector", "label": "Anomaly Detector", "type": "process",
             "description": "Z-score, IQR, Benford's Law checks"},
            {"id": "whatif_simulator", "label": "What-If Simulator", "type": "process",
             "description": "Scenario simulation, sensitivity analysis"},
            {"id": "reasoner", "label": "Reasoner (LLM)", "type": "llm",
             "description": "Nemotron 3 Super — causal narrative, explanations"},
            {"id": "alerts", "label": "Alert Engine", "type": "output",
             "description": "KPI monitoring, threshold checks, notifications"},
            {"id": "report_generator", "label": "Report Generator", "type": "output",
             "description": "PDF/Excel/structured report output"},
        ],
        "edges": [
            {"from": "data_extractor", "to": "calculator"},
            {"from": "calculator", "to": "insight_engine"},
            {"from": "insight_engine", "to": "memory"},
            {"from": "memory", "to": "orchestrator", "condition": "full_data"},
            {"from": "memory", "to": "reasoner", "condition": "partial_data"},
            {"from": "orchestrator", "to": "anomaly_detector"},
            {"from": "anomaly_detector", "to": "whatif_simulator"},
            {"from": "whatif_simulator", "to": "reasoner"},
            {"from": "reasoner", "to": "alerts"},
            {"from": "alerts", "to": "report_generator"},
        ],
        "agents": [
            {"id": "supervisor", "name": "Supervisor", "tools": 33,
             "description": "Intent routing, task dispatch"},
            {"id": "calc", "name": "CalcAgent",
             "capabilities": ["calculate", "generate_statement", "compare", "forecast"]},
            {"id": "data", "name": "DataAgent",
             "capabilities": ["ingest", "classify", "data_quality"]},
            {"id": "insight", "name": "InsightAgent",
             "capabilities": ["analyze", "reason", "explain"]},
            {"id": "report", "name": "ReportAgent",
             "capabilities": ["report", "export", "chart"]},
            {"id": "legacy", "name": "LegacyAgent",
             "capabilities": ["chat", "navigate", "query"]},
        ],
        "knowledge_sources": [
            {"id": "kg", "name": "Knowledge Graph", "entities": 710,
             "types": "accounts, ratios, IFRS rules, benchmarks"},
            {"id": "vector", "name": "ChromaDB Vector Store", "documents": 2344,
             "types": "financial rules, agent memories"},
            {"id": "ontology", "name": "Company Ontology",
             "description": f"{settings.COMPANY_NAME}-specific accounting rules, 7110 COGS, IFRS 15"},
            {"id": "coa", "name": "Chart of Accounts", "accounts": 406,
             "format": "Georgian IFRS + Russian 1C hybrid"},
        ],
        "llm_stack": [
            {"tier": 1, "provider": "NVIDIA", "model": "Gemma 4 31B IT",
             "context": "Primary — Georgian-capable", "status": "active"},
            {"tier": 2, "provider": "NVIDIA", "model": "Nemotron Super 120B",
             "context": "Complex reasoning", "status": "active"},
            {"tier": 3, "provider": "Google", "model": "Gemini 2.0 Flash",
             "context": "Georgian translation", "status": "active"},
            {"tier": 4, "provider": "Anthropic", "model": "Claude Sonnet 4",
             "context": "Fallback", "status": "configured"},
            {"tier": 5, "provider": "Ollama", "model": "Qwen 2.5 3B",
             "context": "Local fallback", "status": "available"},
            {"tier": 6, "provider": "Templates", "model": "Rule-based",
             "context": "Always available", "status": "always"},
        ],
    }


@router.get("/agents/market-data")
async def get_market_data():
    """Fetch live market data: NBG rates, oil prices, Georgia macro, forex."""
    try:
        from app.services.market_data_service import market_data_service
        return await market_data_service.get_all()
    except Exception as e:
        return {"error": str(e)}


@router.get("/agents/market-data/context")
async def get_market_context():
    """Get compact market context string for LLM injection."""
    try:
        from app.services.market_data_service import market_data_service
        context = await market_data_service.get_market_context_for_llm()
        return {"context": context}
    except Exception as e:
        return {"error": str(e)}


@router.get("/agents/knowledge/stats")
async def get_knowledge_stats():
    """Return knowledge graph statistics for the explorer."""
    try:
        from app.services.knowledge_graph import knowledge_graph
        entities = knowledge_graph._entities
        type_counts: dict = {}
        sample_entities = []
        for eid, entity in entities.items():
            etype = getattr(entity, "entity_type", "unknown")
            type_counts[etype] = type_counts.get(etype, 0) + 1
            if len(sample_entities) < 50:
                sample_entities.append({
                    "id": eid,
                    "type": etype,
                    "label": getattr(entity, "label", eid),
                    "description": getattr(entity, "description", "")[:100],
                })
        return {
            "total_entities": len(entities),
            "type_counts": dict(sorted(type_counts.items(), key=lambda x: -x[1])),
            "sample_entities": sample_entities,
            "relations_count": len(getattr(knowledge_graph, "relations", [])),
        }
    except Exception as e:
        return {"error": str(e), "total_entities": 0, "type_counts": {}, "sample_entities": []}


# ── Structured Feedback ───────────────────────────────────────────────────────

class InsightFeedback(BaseModel):
    trace_id: str
    insight_index: int = 0
    correct: bool = True
    comment: Optional[str] = None
    corrected_value: Optional[Dict[str, Any]] = None


@router.post("/agents/feedback")
async def submit_insight_feedback(fb: InsightFeedback, db: AsyncSession = Depends(get_db)):
    """Submit structured feedback on an AI insight or recommendation."""
    try:
        feedback = Feedback(
            user_input=f"trace:{fb.trace_id}:insight:{fb.insight_index}",
            agent_response=f"correct={fb.correct}",
            rating=5 if fb.correct else 1,
            comment=fb.comment or "",
        )
        db.add(feedback)
        await db.commit()
        if not fb.correct:
            logger.info(
                "FEEDBACK CORRECTION: trace=%s insight=%d comment=%s corrected=%s",
                fb.trace_id, fb.insight_index, fb.comment, fb.corrected_value,
            )
        return {"status": "feedback_received", "trace_id": fb.trace_id}
    except Exception as e:
        logger.error("feedback error: %s", e)
        return {"error": str(e)}


@router.get("/agents/audit/logs")
async def get_audit_logs(db: AsyncSession = Depends(get_db)):
    """Get recent feedback and reasoning traces as audit log."""
    try:
        result = await db.execute(
            select(Feedback).order_by(Feedback.id.desc()).limit(50)
        )
        rows = result.scalars().all()
        logs = [{
            "id": row.id,
            "trace_id": row.user_input or "",
            "stage": "feedback",
            "decision": row.agent_response or "",
            "confidence": (row.rating or 0) * 20,
            "comment": row.comment or "",
            "timestamp": row.created_at.isoformat() if hasattr(row, "created_at") and row.created_at else "",
        } for row in rows]
        return {"logs": logs, "total": len(logs)}
    except Exception as e:
        logger.error("audit_logs error: %s", e)
        return {"logs": [], "total": 0, "error": str(e)}
