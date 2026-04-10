"""
FinAI Agent Chat Sub-Router
=============================
Core chat, status, captain, commands, memory, and feedback endpoints.
Extracted from agent.py for maintainability.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from app.database import get_db
from app.models.all_models import AgentMemory, Feedback
from app.services.ai_agent import agent
from app.config import settings
import logging

logger = logging.getLogger(__name__)
router = APIRouter()  # NO prefix — parent adds /api/agent


def _guarded_save_financials(company_id, period, financials, source_file=None, user="api"):
    """Route all financial writes through OntologyWriteGuard."""
    try:
        from app.services.ontology_write_guard import write_guard
        write_guard.write_financials(company_id, period, financials, user=user)
    except Exception:
        from app.services.data_store import data_store
        data_store.save_financials(company_id, period, financials, source_file)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000)
    history: Optional[List[Dict[str, Any]]] = Field(default=[], max_length=50)


class MemoryCreate(BaseModel):
    content:     str
    memory_type: str = "fact"
    importance:  int = 5


class FeedbackCreate(BaseModel):
    feedback_type:   str           # up | dn | correction
    message_content: Optional[str] = None
    user_question:   Optional[str] = None
    correction_text: Optional[str] = None


@router.get("/status")
async def agent_status():
    """Check agent readiness — used by frontend to show/hide API key banner."""
    has_any_llm = bool(
        settings.ANTHROPIC_API_KEY or settings.NVIDIA_API_KEY_GEMMA
        or settings.NVIDIA_API_KEY or settings.GEMINI_API_KEY
    )
    primary_model = (
        "gemma-4-31b-it (NVIDIA)" if settings.NVIDIA_API_KEY_GEMMA
        else settings.ANTHROPIC_MODEL if settings.ANTHROPIC_API_KEY
        else "gemini-2.5-flash (Google)" if settings.GEMINI_API_KEY
        else "none"
    )
    status = {
        "status":  "ready" if has_any_llm else "no_api_key",
        "model":   primary_model,
        "api_key": "configured" if has_any_llm else "missing",
        "agent_mode": settings.AGENT_MODE,
    }
    # Include multi-agent registry status
    try:
        from app.agents.registry import registry
        status["agents"] = registry.status()
    except Exception:
        pass
    # Ollama local LLM status
    try:
        from app.services.local_llm import local_llm
        status["ollama"] = local_llm.get_status()
    except Exception:
        status["ollama"] = {"available": False}
    # Captain routing status
    try:
        from app.services.local_llm import captain_llm
        status["captain"] = captain_llm.get_status()
    except Exception:
        status["captain"] = {"captain_enabled": False}
    return status


# ── FinAI Captain Chat (Hybrid Routing) ─────────────────────────────────


class CaptainChatRequest(BaseModel):
    message: str
    use_nemo_retriever: bool = False
    lang: str = "en"


@router.post("/captain/chat")
async def captain_chat(req: CaptainChatRequest, db: AsyncSession = Depends(get_db)):
    """FinAI Captain — hybrid LLM routing for the sidebar assistant.

    Routes intelligently between:
      - Claude Sonnet 4 (Georgian fluency + intent + UI actions)
      - Nemotron 3 Super 120B (deep financial reasoning + agentic)
      - Qwen3 local via Ollama (fast, free fallback)
    """
    if not req.message.strip():
        raise HTTPException(400, "Message cannot be empty")

    import time as _time_captain
    _t0_captain = _time_captain.time()
    try:
        from app.services.local_llm import captain_llm

        # Extract the actual user question and selected period from the frontend
        # context blob.  The frontend sends:
        #   "System: FinAI OS...\nPeriod: September 2025\n...\nUser's question: <q>"
        raw_message = req.message.strip()
        user_q_marker = "User's question: "
        selected_period = None
        if user_q_marker in raw_message:
            user_message = raw_message[raw_message.rindex(user_q_marker) + len(user_q_marker):].strip()
            # Extract the dashboard period so we query the right data
            import re
            period_match = re.search(r"Period:\s*(.+)", raw_message)
            if period_match:
                selected_period = period_match.group(1).strip()
            logger.info(
                "Captain: extracted question (%d chars) from context blob (%d chars), period=%s",
                len(user_message), len(raw_message), selected_period,
            )
        else:
            user_message = raw_message
            logger.info("Captain: raw message (%d chars), no context blob detected", len(user_message))

        # Build context from current financial data — use the dashboard's
        # selected period when available so the AI answers about the same
        # data the user is looking at.
        context = {}
        try:
            from app.services.data_store import data_store
            companies = data_store.list_companies()
            if companies:
                co = companies[-1]
                co_id = co["id"]
                periods = data_store.get_all_periods(co_id)
                if periods:
                    # Use the period the dashboard is showing, or fall back to latest
                    target_period = None
                    if selected_period:
                        # Fuzzy match: "September 2025" → "2025-09" or exact match
                        for p in periods:
                            if selected_period.lower() in p.lower() or p.lower() in selected_period.lower():
                                target_period = p
                                break
                    if not target_period:
                        target_period = periods[-1]
                    fin = data_store.get_financials(co_id, target_period)
                    if fin:
                        context = {
                            "company": co.get("name", "Unknown"),
                            "period": target_period,
                            "periods_available": periods,
                            "revenue": fin.get("revenue", 0),
                            "cogs": fin.get("cogs", 0) or (fin.get("revenue", 0) - fin.get("gross_profit", 0)),
                            "gross_profit": fin.get("gross_profit", 0),
                            "net_profit": fin.get("net_profit", 0),
                            "ebitda": fin.get("ebitda", 0),
                            "total_assets": fin.get("total_assets", 0),
                            "total_liabilities": fin.get("total_liabilities", 0),
                            "total_equity": fin.get("total_equity", 0),
                            "cash": fin.get("cash", 0),
                            "gross_margin_pct": round(fin.get("gross_profit", 0) / fin.get("revenue", 1) * 100, 1) if fin.get("revenue") else 0,
                            "net_margin_pct": round(fin.get("net_profit", 0) / fin.get("revenue", 1) * 100, 1) if fin.get("revenue") else 0,
                        }
        except Exception:
            pass

        result = await captain_llm.route_and_call(
            message=user_message,
            context=context,
            use_nemo_retriever=req.use_nemo_retriever,
            lang=req.lang,
        )
        # Record activity event for captain chat
        try:
            from app.services.activity_feed import activity_feed
            _dur_c = int((_time_captain.time() - _t0_captain) * 1000)
            _model_c = result.get("model", "unknown") if isinstance(result, dict) else "unknown"
            _evt_id_c = activity_feed.record(
                event_type="llm_call", resource_type="Captain",
                resource_id="captain-chat", action="captain_chat",
                details={"model": _model_c, "lang": req.lang, "message_len": len(req.message)},
                status="success", duration_ms=_dur_c,
            )
            activity_feed.record_llm_trace(
                event_id=_evt_id_c, model=_model_c,
                prompt=req.message,
                response=str(result.get("content", ""))[:500] if isinstance(result, dict) else "",
                duration_ms=_dur_c,
            )
        except Exception:
            pass

        # Log to data flywheel for continuous improvement
        try:
            from app.services.data_flywheel import data_flywheel
            import uuid
            _content_c = result.get("content", "") if isinstance(result, dict) else ""
            _wtype = "translation" if req.lang == "ka" else "analysis" if any(k in req.message.lower() for k in ["analyze","explain","why","forecast"]) else "general"
            data_flywheel.log_interaction(
                interaction_id=str(uuid.uuid4())[:12],
                model=_model_c,
                prompt=req.message,
                response=_content_c,
                duration_ms=_dur_c,
                language=req.lang or "en",
                workload_type=_wtype,
            )
        except Exception:
            pass
        return result
    except Exception as e:
        logger.error(f"Captain chat error: {e}", exc_info=True)
        try:
            from app.services.activity_feed import activity_feed
            activity_feed.record(
                event_type="llm_call", resource_type="Captain",
                resource_id="captain-chat", action="captain_chat",
                details={"error": str(e)[:200]}, status="failure",
                duration_ms=int((_time_captain.time() - _t0_captain) * 1000),
            )
        except Exception:
            pass
        return {
            "model": "error",
            "content": "Captain encountered an error. Please try again.",
            "language": "en",
        }


@router.post("/chat")
async def chat(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    """Send message to FinAI agent. Returns response + tool_calls + navigation hint.

    Intelligence stack (auto-fallback):
      Tier 1: ResponseCache (instant, free)
      Tier 2: Claude API (cloud, best quality) — requires ANTHROPIC_API_KEY
      Tier 3: Ollama local model with Mistral 7B (offline, good quality)
      Tier 4: Template responses (always available, no AI)
    """
    if not req.message.strip():
        raise HTTPException(400, "Message cannot be empty")

    # Check if ANY intelligence tier is available
    has_api_key = bool(
        settings.ANTHROPIC_API_KEY or settings.NVIDIA_API_KEY_GEMMA
        or settings.NVIDIA_API_KEY or settings.GEMINI_API_KEY
    )
    ollama_available = False
    try:
        from app.services.local_llm import local_llm
        ollama_available = await local_llm.is_available()
    except Exception:
        pass

    if not has_api_key and not ollama_available:
        logger.warning("No LLM API key and no Ollama — using template responses only")

    try:
        if settings.AGENT_MODE == "multi":
            from app.agents.supervisor import supervisor
            result = await supervisor.handle_chat(req.message, req.history or [], db)
        else:
            result = await agent.chat(req.message, req.history or [], db)
        return result
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        # If Claude API failed and Ollama unavailable, give helpful error
        if "api_key" in str(e).lower() or "authentication" in str(e).lower():
            return {
                "response": (
                    "I'm running without an AI model right now. "
                    "To enable full AI capabilities, either:\n"
                    "1. Set `ANTHROPIC_API_KEY` in your .env file (Claude API)\n"
                    "2. Install Ollama (ollama.com) and run `ollama pull mistral:7b` for free local AI\n\n"
                    "Meanwhile, I can still navigate pages, show financial data, "
                    "generate reports, and run calculations using the built-in tools."
                ),
                "tools_used": [],
                "intent": "system",
            }
        raise HTTPException(500, f"Agent error: {str(e)}")


@router.post("/command")
async def agent_command(body: dict):
    """V11: Intelligent command router. Sidebar types a command, this runs the right agents.
    Examples: 'analyze data', 'generate report', 'show revenue breakdown', 'run orchestrator',
              'what if revenue drops 20%', 'რა არის მარჟა?'
    """
    import asyncio
    import re as _re
    import time as _time_cmd
    _cmd_start = _time_cmd.time()
    command = str(body.get("command", "")).strip().lower()
    if not command:
        return {"error": "Empty command"}

    _cmd_result = None
    try:
        from app.services.data_store import data_store
        from app.services.financial_chat import FinancialChatEngine

        # Get current financial context
        companies = data_store.list_companies()
        financials = {}
        company_name = "Unknown"
        period = "Unknown"
        company_id = 0

        if companies:
            # Find richest company
            best = companies[-1]
            best_score = 0
            for c in reversed(companies):
                periods = data_store.get_all_periods(c["id"])
                if periods:
                    fin = data_store.get_financials(c["id"], periods[-1])
                    score = len(fin or {})
                    orch = data_store.get_last_orchestrator_result(c["id"])
                    if orch:
                        score += 100
                    if score > best_score:
                        best_score = score
                        best = c
            company_id = best["id"]
            company_name = best.get("name", "Unknown")
            periods = data_store.get_all_periods(company_id)
            if periods:
                period = periods[-1]
                financials = data_store.get_financials(company_id, period) or {}

        # ── Route command to right agent ──

        # Run full pipeline
        if any(kw in command for kw in ["analyze", "run pipeline", "orchestrat", "full analysis", "გააანალიზ"]):
            from app.orchestrator.orchestrator_v3 import orchestrator_v3
            result = await orchestrator_v3.run_full_pipeline(
                company_id=company_id, period=period,
                financials=financials, company_name=company_name,
            )
            _cmd_result = {
                "command_type": "orchestrator",
                "response": result.get("user_message", "Analysis complete"),
                "llm_summary": result.get("llm_reasoning", {}).get("summary", ""),
                "insights": result.get("insights", [])[:5],
                "company_character": result.get("company_character", {}),
                "alerts": result.get("alerts", []),
                "suggestions": result.get("suggestions", []),
                "execution_ms": result.get("execution_ms", 0),
                "llm_model": result.get("llm_model_used", ""),
                "stages": result.get("stages_completed", []),
            }

        # Revenue report with product breakdown (MUST be before generic report)
        elif any(kw in command for kw in ["revenue report", "revenue breakdown", "product breakdown",
                                         "product classification", "შემოსავლის რეპორტი", "პროდუქტების"]):
            # Get breakdown data from upload history
            uploads = data_store.get_upload_history(company_id) if hasattr(data_store, 'get_upload_history') else []
            revenue_breakdown = []
            for u in reversed(uploads):
                if isinstance(u, dict) and u.get("result_json"):
                    import json as _jmod
                    try:
                        rj = _jmod.loads(u["result_json"]) if isinstance(u["result_json"], str) else u["result_json"]
                        if rj.get("revenue_breakdown"):
                            revenue_breakdown = rj["revenue_breakdown"]
                            break
                    except Exception:
                        pass

            if not revenue_breakdown:
                _cmd_result = {"command_type": "revenue_report", "response": "No product-level revenue data found. Upload a file with Revenue Breakdown sheet."}
            else:
                # Group by category
                categories = {}
                grand_total = 0
                for item in revenue_breakdown:
                    cat = item.get("category", "Other")
                    categories.setdefault(cat, {"products": [], "total": 0})
                    categories[cat]["products"].append(item)
                    net = item.get("net_revenue", 0)
                    categories[cat]["total"] += net
                    grand_total += net

                # Build structured response
                lines = [f"REVENUE REPORT — {company_name} — {period}", f"Total Net Revenue: {grand_total:,.0f} GEL", ""]
                table_data = []
                for cat in sorted(categories.keys(), key=lambda c: -categories[c]["total"]):
                    cat_data = categories[cat]
                    cat_pct = (cat_data["total"] / grand_total * 100) if grand_total else 0
                    lines.append(f"{'='*50}")
                    lines.append(f"{cat} ({len(cat_data['products'])} products) — {cat_data['total']:,.0f} GEL ({cat_pct:.1f}%)")
                    lines.append(f"{'='*50}")
                    for p in sorted(cat_data["products"], key=lambda x: -x.get("net_revenue", 0)):
                        name = p.get("product", "?")[:40]
                        net = p.get("net_revenue", 0)
                        gross = p.get("gross_amount", 0)
                        vat = p.get("vat", 0)
                        pct_of_cat = (net / cat_data["total"] * 100) if cat_data["total"] else 0
                        lines.append(f"  {name:40s} Net: {net:>12,.0f} GEL  ({pct_of_cat:5.1f}%)")
                        table_data.append({"product": name, "category": cat, "gross": gross, "vat": vat, "net": net, "pct": round(pct_of_cat, 1)})
                    lines.append("")

                _cmd_result = {
                    "command_type": "revenue_report",
                    "response": "\n".join(lines),
                    "data": {
                        "categories": {cat: {"total": d["total"], "count": len(d["products"]), "pct": round(d["total"]/grand_total*100, 1) if grand_total else 0} for cat, d in categories.items()},
                        "products": table_data,
                        "grand_total": grand_total,
                    },
                    "navigate": "revenue",
                }

        # Generate report (generic)
        elif any(kw in command for kw in ["report", "pdf", "excel", "რეპორტ", "ანგარიშ"]):
            from app.services.pdf_report import pdf_generator
            orch_raw = data_store.get_last_orchestrator_result(company_id)
            if isinstance(orch_raw, dict):
                inner = orch_raw.get("result")
                if isinstance(inner, str):
                    import json
                    inner = json.loads(inner)
                orch_data = inner if isinstance(inner, dict) else orch_raw
            else:
                orch_data = {}

            if orch_data.get("orchestrator_legacy"):
                pdf_bytes = pdf_generator.generate_from_orchestrator(orch_data["orchestrator_legacy"], company_name)
                import os
                os.makedirs("exports", exist_ok=True)
                path = f"exports/{company_name.replace(' ','_')}_{period}_Report.pdf"
                with open(path, "wb") as f:
                    f.write(pdf_bytes)
                _cmd_result = {"command_type": "report", "response": f"PDF report generated: {path} ({len(pdf_bytes):,} bytes)", "file_path": path}
            else:
                _cmd_result = {"command_type": "report", "response": "Cannot generate report — run full analysis first (upload data with revenue + COGS)."}

        # What-if scenario (MUST be before revenue/margin to avoid keyword collision)
        elif any(kw in command for kw in ["what if", "what-if", "scenario", "რა მოხდება"]):
            pct_match = _re.search(r'(\d+)%?', command)
            pct = int(pct_match.group(1)) if pct_match else 10
            direction = -1 if any(w in command for w in ["drop", "decrease", "decline", "fall", "down", "შემცირ"]) else 1
            rev = financials.get("revenue", 0)
            cogs = financials.get("cogs", 0)
            if rev:
                new_rev = rev * (1 + direction * pct / 100)
                new_gp = new_rev - cogs
                old_gp = rev - cogs
                _cmd_result = {
                    "command_type": "what_if",
                    "response": f"What-if: Revenue {'drops' if direction < 0 else 'increases'} {pct}%\n\n"
                               f"  Revenue: {rev:,.0f} -> {new_rev:,.0f} GEL\n"
                               f"  Gross Profit: {old_gp:,.0f} -> {new_gp:,.0f} GEL\n"
                               f"  Margin: {old_gp/rev*100:.1f}% -> {new_gp/new_rev*100:.1f}%\n"
                               f"  Impact: {'Loss of' if direction < 0 else 'Gain of'} {abs(new_rev - rev):,.0f} GEL revenue",
                }
            else:
                _cmd_result = {"command_type": "what_if", "response": "No revenue data available for simulation. Upload financial data first."}

        # Revenue analysis
        elif any(kw in command for kw in ["revenue", "შემოსავ"]):
            rev = financials.get("revenue", 0)
            retail = financials.get("revenue_revenue_retail", 0)
            wholesale = financials.get("revenue_revenue_wholesale", 0)
            _cmd_result = {
                "command_type": "revenue",
                "response": f"Revenue: {rev:,.0f} GEL (Retail: {retail:,.0f}, Wholesale: {wholesale:,.0f}). Navigate to Revenue page for full breakdown.",
                "data": {"revenue": rev, "retail": retail, "wholesale": wholesale},
                "navigate": "revenue",
            }

        # Balance sheet
        elif any(kw in command for kw in ["balance sheet", "ბალანს", "assets", "აქტივ"]):
            bs_keys = {k[3:]: v for k, v in financials.items() if k.startswith("bs_")}
            _cmd_result = {
                "command_type": "balance_sheet",
                "response": f"Assets: {bs_keys.get('total_assets',0):,.0f}, Liabilities: {bs_keys.get('total_liabilities',0):,.0f}, Equity: {bs_keys.get('total_equity',0):,.0f}",
                "data": bs_keys,
                "navigate": "bs",
            }

        # P&L / margin questions
        elif any(kw in command for kw in ["p&l", "pnl", "margin", "profit", "მოგება", "მარჟა", "ზარალ"]):
            rev = financials.get("revenue", 0)
            cogs = financials.get("cogs", 0)
            gp = financials.get("gross_profit", rev - cogs if rev and cogs else 0)
            margin = financials.get("gross_margin_pct", (gp / rev * 100) if rev else 0)
            _cmd_result = {
                "command_type": "pnl",
                "response": f"Revenue: {rev:,.0f}, COGS: {cogs:,.0f}, Gross Profit: {gp:,.0f} ({margin:.1f}% margin). Navigate to P&L page for full statement.",
                "navigate": "pl",
            }

        # (what-if moved above revenue check to avoid keyword collision)

        else:
            # Financial chat (rule-based, fallback for everything else)
            chat = FinancialChatEngine()
            chat.set_context(financials)
            chat_result = chat.query(command)
            _cmd_result = {
                "command_type": "chat",
                "response": chat_result.answer if hasattr(chat_result, 'answer') else str(chat_result),
                "data": chat_result.data_points if hasattr(chat_result, 'data_points') else {},
            }

    except Exception as e:
        import traceback
        _cmd_result = {"command_type": "error", "response": f"Command failed: {str(e)}", "trace": traceback.format_exc()[:500]}

    # Log every command interaction to the data flywheel
    _log_command_to_flywheel(command, _cmd_result, _cmd_start)
    return _cmd_result


def _log_command_to_flywheel(command: str, response_data: dict, start_time: float) -> None:
    """Log a /command interaction to the data flywheel for continuous improvement."""
    try:
        import time as _t
        from app.services.data_flywheel import data_flywheel
        _elapsed = int((_t.time() - start_time) * 1000)
        _resp_str = response_data.get("response", "") or ""
        # Classify workload type from command_type
        _cmd_type = response_data.get("command_type", "general")
        _wtype_map = {
            "orchestrator": "analysis", "what_if": "reasoning",
            "revenue": "analysis", "pnl": "analysis", "balance_sheet": "analysis",
            "report": "analysis", "revenue_report": "analysis",
            "chat": "general", "error": "general",
        }
        _wtype = _wtype_map.get(_cmd_type, "general")
        # Detect Georgian language
        _lang = "ka" if any('\u10d0' <= c <= '\u10ff' for c in command) else "en"
        data_flywheel.log_interaction(
            interaction_id=f"cmd_{int(_t.time() * 1000)}",
            model="command-router",
            prompt=command,
            response=_resp_str,
            duration_ms=_elapsed,
            tokens_input=len(command.split()),
            tokens_output=len(_resp_str.split()),
            language=_lang,
            workload_type=_wtype,
        )
    except Exception as e:
        logger.warning("Flywheel logging failed for /command: %s", e)


@router.get("/memory")
async def list_memory(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AgentMemory).where(AgentMemory.is_active == True)
        .order_by(AgentMemory.created_at.desc()).limit(100)
    )
    items = result.scalars().all()
    return [{"id":m.id,"type":m.memory_type,"content":m.content,"importance":m.importance,"created_at":m.created_at.isoformat() if m.created_at else None} for m in items]


@router.post("/memory")
async def add_memory(payload: MemoryCreate, db: AsyncSession = Depends(get_db)):
    m = AgentMemory(content=payload.content, memory_type=payload.memory_type, importance=payload.importance)
    db.add(m)
    await db.commit()
    return {"id": m.id, "content": m.content, "type": m.memory_type}


@router.delete("/memory")
async def clear_memory(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AgentMemory))
    for m in result.scalars().all():
        await db.delete(m)
    await db.commit()
    return {"message": "Agent memory cleared"}


@router.post("/feedback")
async def submit_feedback(payload: FeedbackCreate, db: AsyncSession = Depends(get_db)):
    fb = Feedback(
        feedback_type=payload.feedback_type,
        message_content=payload.message_content,
        user_question=payload.user_question,
        correction_text=payload.correction_text,
    )
    db.add(fb)

    # Auto-save corrections to agent memory
    if payload.feedback_type == "correction" and payload.correction_text:
        db.add(AgentMemory(
            memory_type="correction",
            content=f"CORRECTION: {payload.correction_text}",
            importance=8,
        ))

    await db.commit()
    return {"message": "Feedback saved", "type": payload.feedback_type}


@router.get("/feedback/stats")
async def feedback_stats(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Feedback))
    all_fb = result.scalars().all()
    pos = sum(1 for f in all_fb if f.feedback_type == "up")
    neg = sum(1 for f in all_fb if f.feedback_type == "dn")
    corrections = sum(1 for f in all_fb if f.feedback_type == "correction")
    total = pos + neg
    accuracy = pos / total * 100 if total > 0 else 0
    return {
        "total": len(all_fb),
        "positive": pos,
        "negative": neg,
        "corrections": corrections,
        "accuracy_pct": round(accuracy, 1),
    }
