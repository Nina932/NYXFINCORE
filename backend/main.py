"""
FinAI Financial Intelligence Platform — FastAPI Backend
Serves the React frontend (localhost:3000) and all API endpoints.
WebSocket streaming chat + Redis caching + full financial AI.
"""
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from pathlib import Path
import json as _json
import logging, time, os, sys


class UnicodeJSONResponse(JSONResponse):
    """JSON response that preserves Unicode characters (Georgian, Russian, etc.)."""
    media_type = "application/json; charset=utf-8"

    def render(self, content) -> bytes:
        return _json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
        ).encode("utf-8")

# Fix Windows console encoding for Georgian/Russian text
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from app.config import settings
from app.auth import decode_token
from app.database import init_db, AsyncSessionLocal, engine
from app.services.seed_data import seed_database
from app.routers import datasets, analytics, agent, reports
from app.routers import schemas
from app.routers import tools  # new
from app.routers import advanced  # advanced features (forecasting, scenarios, anomalies, etc.)
from app.routers import mr_reports  # MR report generation + exchange rates
from app.routers import auth_router           # JWT authentication
from app.routers import external_data_router  # Live market data endpoints
from app.routers import documents_router      # Document intelligence (PDF/Word/Excel RAG)
from app.routers import ontology as ontology_router  # FinAI OS: Ontology + Warehouse + Actions
from app.routers import journal_router               # SOR: Journal entries, periods, profitability
from app.routers import ap_accounts as ap_router      # AP Automation: 3-way matching
from app.routers import consolidation as consolidation_router # Multi-entity consolidation
from app.routers import compliance as compliance_router       # Monitoring, Audit, Lineage
from app.routers import esg as esg_router                    # ESG & Sustainability
from app.routers import subledger as subledger_router         # Sub-Ledger: AR/AP aging
from app.routers import company360 as company360_router       # Company 360 view

from app.logging_config import setup_logging
setup_logging()
logger = logging.getLogger("finai")

from app.telemetry import setup_telemetry
setup_telemetry(engine=engine.sync_engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("FinAI starting...")

    # ── Security warnings ──────────────────────────────────────────
    if not settings.REQUIRE_AUTH:
        if settings.APP_ENV != "development":
            logger.critical(
                "REQUIRE_AUTH=False in non-development environment (%s). "
                "All endpoints are publicly accessible! Set REQUIRE_AUTH=True.",
                settings.APP_ENV,
            )
        else:
            logger.warning(
                "REQUIRE_AUTH=False — authentication is disabled. "
                "This is acceptable only for local development."
            )

    # ── LLM availability check ─────────────────────────────────────
    if not settings.ANTHROPIC_API_KEY:
        logger.warning(
            "ANTHROPIC_API_KEY is not set. The conversational AI chat will be unavailable. "
            "All deterministic financial APIs (P&L, Balance Sheet, Cash Flow, GL Pipeline, "
            "Forecasting, Anomaly Detection) remain fully operational."
        )

    await init_db()
    async with AsyncSessionLocal() as db:
        await seed_database(db)

    # ── Initialize RAG vector store + knowledge graph ────────────
    try:
        from app.services.vector_store import vector_store
        await vector_store.initialize()
        logger.info("Vector store initialized.")

        # Build knowledge graph and index all domain knowledge
        kg_result = await vector_store.index_knowledge_graph()
        kg_entities = kg_result.get("graph_entities", 0)
        kg_indexed = kg_result.get("indexed", 0)
        kg_source = kg_result.get("source", "unknown")
        logger.info(
            "Knowledge graph: %d entities, %d indexed (source: %s).",
            kg_entities, kg_indexed, kg_source,
        )
    except Exception as e:
        logger.warning(f"Vector store init skipped: {e}")

    # ── Initialize FinAI OS: Ontology ────────────────────────────
    logger.info("Starting ontology init...")
    try:
        from app.services.ontology_engine import ontology_registry
        from app.services.ontology_store import ontology_store
        count = ontology_registry.initialize()
        ontology_store.initialize()
        ontology_store.bulk_save(list(ontology_registry._objects.values()))
        logger.info(f"FinAI OS: ontology ({count} objects) ready.")
    except Exception as e:
        logger.warning(f"Ontology init: {e}")

    # ── Initialize Data Warehouse (separate from ontology) ─────
    logger.info("Starting warehouse init...")
    try:
        from app.services.warehouse import warehouse as finai_warehouse
        finai_warehouse.initialize()
        if finai_warehouse._initialized:
            logger.info(f"Data warehouse ready at {finai_warehouse._db_path}")
        else:
            logger.warning("Data warehouse: init returned False")
    except Exception as e:
        logger.warning(f"Warehouse init: {e}")

    # ── Initialize cache service ─────────────────────────────────
    try:
        from app.services.cache import cache_service
        await cache_service.initialize()
        logger.info("Cache service initialized.")
    except Exception as e:
        logger.warning(f"Cache init skipped: {e}")

    # ── Start report scheduler ───────────────────────────────────
    try:
        if settings.SCHEDULER_ENABLED:
            from app.services.scheduler import report_scheduler
            await report_scheduler.start()
            logger.info("Report scheduler started.")
    except Exception as e:
        logger.warning(f"Scheduler start skipped: {e}")

    # ── Initialize multi-agent system ────────────────────────────
    try:
        from app.agents import initialize_agents
        initialize_agents()
        logger.info("Multi-agent system initialized (mode: %s).", settings.AGENT_MODE)

        # Install tool-level routing (Supervisor intercepts execute_tool)
        if settings.AGENT_MODE == "multi":
            from app.agents.supervisor import supervisor
            supervisor.install_tool_router()
            logger.info("Supervisor tool router installed.")
    except Exception as e:
        logger.warning("Agent system init skipped: %s", e)

    # ── Index agent memories into RAG + knowledge graph ───────
    try:
        from app.services.vector_store import vector_store
        async with AsyncSessionLocal() as db:
            mem_result = await vector_store.index_agent_memories(db)
            mem_count = mem_result.get("indexed", 0)
            if mem_count > 0:
                logger.info("Agent memories indexed: %d documents.", mem_count)
    except Exception as e:
        logger.debug("Agent memory indexing skipped: %s", e)

    # ── Ollama/Local LLM check ─────────────────────────────────
    try:
        from app.services.local_llm import local_llm
        ollama_ok = await local_llm.is_available()
        if ollama_ok:
            status = local_llm.get_status()
            logger.info("Ollama available: %s (best: %s)", status['models_available'], status['best_model'])
        else:
            logger.info("Ollama not available — using Claude API or templates only.")
    except Exception as e:
        logger.debug("Ollama check failed: %s", e)

    # ── Start Data Flywheel background loop ─────────────────────
    _flywheel_task = None
    try:
        from app.services.flywheel_loop import flywheel_loop
        import asyncio
        _flywheel_task = asyncio.create_task(flywheel_loop.start_background())
        logger.info("Data Flywheel background loop started (interval: 300s).")
    except Exception as e:
        logger.debug("Flywheel loop start skipped: %s", e)

    logger.info("FinAI ready.")
    yield

    # ── Shutdown ─────────────────────────────────────────────────
    try:
        from app.services.flywheel_loop import flywheel_loop
        flywheel_loop.stop()
        if _flywheel_task:
            _flywheel_task.cancel()
    except Exception:
        pass
    try:
        from app.services.cache import cache_service
        await cache_service.close()
    except Exception:
        pass
    try:
        from app.services.scheduler import report_scheduler
        await report_scheduler.stop()
    except Exception:
        pass
    logger.info("FinAI shutting down.")


app = FastAPI(
    title="FinAI Financial Intelligence API",
    description=f"{settings.COMPANY_NAME} — Financial AI Platform",
    version="2.0.0",
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url="/api/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
    default_response_class=UnicodeJSONResponse,
)

if getattr(settings, "OTEL_MODE", "disabled").lower() != "disabled":
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        HTTPXClientInstrumentor().instrument()
    except Exception as e:
        logger.warning(f"FastAPI/HTTPX telemetry instrumentation failed: {e}")

# CORS — restrict methods to explicit list
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)

# Global auth enforcement (must be added AFTER CORS so preflight works)
from app.middleware.auth_middleware import AuthMiddleware  # noqa: E402
app.add_middleware(AuthMiddleware)

# Rate limiting (must be after auth so auth runs first)
from app.middleware.rate_limiter import RateLimiterMiddleware  # noqa: E402
app.add_middleware(RateLimiterMiddleware)

# Request timing
@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    start = time.time()

    # Generate trace ID
    try:
        from app.services.request_tracer import new_trace_id, set_trace_id, get_spans, trace_store
        trace_id = request.headers.get("X-Trace-Id") or new_trace_id()
        set_trace_id(trace_id)
    except Exception:
        trace_id = ""

    # Set request language dynamically
    try:
        from app.services.language_context import set_language
        lang = request.headers.get("Accept-Language", "en")
        if lang.startswith("ka"):
            set_language("ka")
        else:
            set_language("en")
    except Exception:
        pass

    response = await call_next(request)
    ms = (time.time() - start) * 1000
    response.headers["X-Process-Time"] = f"{ms:.0f}ms"
    if trace_id:
        response.headers["X-Trace-Id"] = trace_id

    if ms > 2000:
        logger.warning(f"Slow request: {request.method} {request.url.path} took {ms:.0f}ms (trace={trace_id})")

    # Record metrics for Prometheus
    try:
        from app.services.metrics import metrics
        path = request.url.path
        method = request.method
        status = response.status_code
        metrics.inc("finai_http_requests_total", method=method, status=str(status))
        metrics.observe("finai_http_request_duration_ms", ms, method=method, path=path[:50])
    except Exception:
        pass

    # Record trace
    try:
        if trace_id:
            spans = get_spans()
            trace_store.record(trace_id, request.url.path, request.method, response.status_code, ms, spans)
    except Exception:
        pass

    return response

# Security headers
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

# Global error handler
@app.exception_handler(Exception)
async def global_error_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    msg = str(exc) if settings.DEBUG else "Internal server error"
    return JSONResponse(status_code=500, content={"detail": msg})

# ── Prometheus metrics endpoint ──
@app.get("/metrics", tags=["observability"])
async def prometheus_metrics():
    """Prometheus-compatible metrics endpoint for Grafana/alerting."""
    from app.services.metrics import metrics
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(metrics.render_prometheus(), media_type="text/plain; charset=utf-8")


@app.get("/metrics/json", tags=["observability"])
async def metrics_json():
    """JSON metrics summary for the System Status page."""
    from app.services.metrics import metrics
    return metrics.get_json_summary()


# Routers
app.include_router(datasets.router)
app.include_router(analytics.router)
app.include_router(agent.router)
app.include_router(reports.router)
app.include_router(schemas.router)
app.include_router(tools.router)       # ← custom tools endpoint
app.include_router(advanced.router)    # ← advanced features (forecast, scenarios, anomalies, etc.)
app.include_router(mr_reports.router)  # ← MR report generation + exchange rates
app.include_router(auth_router.router)            # ← JWT auth (register/login/me)
app.include_router(external_data_router.router)   # ← live market data endpoints
app.include_router(documents_router.router)       # ← document intelligence (PDF/Word/Excel RAG)
app.include_router(ontology_router.router)         # ← FinAI OS: Ontology + Warehouse + Actions
app.include_router(journal_router.router)          # ← SOR: Journal entries, periods, profitability
app.include_router(ap_router.router)               # ← AP Automation: 3-way matching
app.include_router(consolidation_router.router)    # ← Multi-entity consolidation
app.include_router(compliance_router.router)       # ← Monitoring, Audit, Lineage
app.include_router(esg_router.router)              # ← ESG & Sustainability
app.include_router(subledger_router.router)        # ← Sub-Ledger: AR/AP aging
from app.routers import company360 as company360_router       # Company 360 view
from app.routers import marketing as marketing_router        # Marketing leads
# ...
app.include_router(company360_router.router)
app.include_router(marketing_router.router)
try:
    from app.routers import orchestration as orchestration_router
    app.include_router(orchestration_router.router)
except ImportError:
    pass

# ── Flywheel: Self-improvement cycle ──
try:
    from app.routers import flywheel as flywheel_router
    app.include_router(flywheel_router.router)
except ImportError:
    pass

# ── Workshop: Drag-and-drop dashboard builder ──
try:
    from app.routers import workshop as workshop_router
    app.include_router(workshop_router.router)
except ImportError:
    pass

# Static assets (fonts, images, etc.) — NOT legacy HTML frontends
static_dir = Path("./static")
static_dir.mkdir(exist_ok=True)
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# API ROOT Fallback (in case API doesn't catch)
@app.get("/api", include_in_schema=False)
async def api_root():
    from fastapi.responses import JSONResponse
    return JSONResponse({"status": "FinAI API Running"})

# Health check
@app.get("/health", tags=["system"])
async def health():
    from app.database import check_db_health
    db_health = await check_db_health()
    llm_ok = bool(settings.ANTHROPIC_API_KEY)
    return {
        "status":  "healthy" if db_health.get("status") == "healthy" else "degraded",
        "version": "2.0.0",
        "env":     settings.APP_ENV,
        "agent_mode": settings.AGENT_MODE,
        "model":   settings.ANTHROPIC_MODEL,
        "api_key": "configured" if llm_ok else "missing",
        "llm_available": llm_ok,
        "company_name": settings.COMPANY_NAME,
        "database": db_health,
        "capabilities": {
            "chat": llm_ok,
            "financial_apis": True,
            "analytics": True,
            "forecasting": True,
        },
    }

@app.get("/api/config/public", tags=["system"])
async def public_config():
    """Public configuration endpoint — returns non-sensitive settings for the frontend."""
    return {
        "company_name": settings.COMPANY_NAME,
        "default_currency": settings.DEFAULT_CURRENCY,
        "default_period": settings.DEFAULT_PERIOD,
        "app_name": settings.APP_NAME,
        "app_version": settings.APP_VERSION,
    }

@app.get("/api/system/backup", tags=["system"])
async def trigger_backup():
    """Trigger a database backup (admin operation)."""
    from app.services.db_backup import backup_database, get_backup_status
    backup_path = await backup_database()
    status = get_backup_status()
    return {
        "success": backup_path is not None,
        "backup_path": backup_path,
        **status,
    }

@app.get("/api/system/backup/status", tags=["system"])
async def backup_status():
    """Get backup status information."""
    from app.services.db_backup import get_backup_status
    return get_backup_status()

# ── WebSocket Real-Time Events ────────────────────────────────
@app.websocket("/api/ws")
async def websocket_realtime(ws: WebSocket):
    """Real-time event stream for frontend.

    Broadcasts: upload_complete, analysis_ready, alert_triggered,
    data_updated, action_proposed.
    """
    from app.services.realtime import realtime_manager
    await realtime_manager.connect(ws)
    try:
        while True:
            data = await ws.receive_json()
            await realtime_manager.handle_message(ws, data)
    except WebSocketDisconnect:
        realtime_manager.disconnect(ws)
    except Exception as e:
        logger.debug("WS realtime error: %s", e)
        realtime_manager.disconnect(ws)


# ── WebSocket Streaming Chat ──────────────────────────────────
@app.websocket("/ws/chat")
async def websocket_chat(ws: WebSocket):
    """Stream AI chat responses token-by-token via WebSocket.

    Routes through Supervisor (multi-agent) or legacy FinAIAgent
    based on AGENT_MODE config setting.
    """
    await ws.accept()

    # --- Auth check ---
    if settings.REQUIRE_AUTH:
        # Extract token from query param or Authorization header
        token = ws.query_params.get("token", "")
        if not token:
            # Check Authorization header (Sec-WebSocket-Protocol not standard for Bearer)
            token = ws.headers.get("authorization", "").replace("Bearer ", "")

        if not token:
            await ws.send_json({"type": "error", "content": "Authentication required. Pass token as query parameter: ws://host/ws/chat?token=YOUR_JWT"})
            await ws.close(code=4001, reason="Authentication required")
            return

        payload = decode_token(token)
        if payload is None:
            await ws.send_json({"type": "error", "content": "Invalid or expired token"})
            await ws.close(code=4001, reason="Invalid token")
            return

        logger.info("WebSocket authenticated: user_id=%s", payload.get("uid"))
    # --- End auth check ---

    logger.info("WebSocket client connected (agent_mode=%s)", settings.AGENT_MODE)
    try:
        async with AsyncSessionLocal() as db:
            while True:
                data = await ws.receive_json()
                message = data.get("message", "")
                history = data.get("history", [])

                if not message.strip():
                    await ws.send_json({"type": "error", "content": "Empty message"})
                    continue

                try:
                    # Send reasoning step: intent detection
                    intent_msg = "Analyzing your request..."
                    await ws.send_json({"type": "reasoning", "agent": "supervisor", "action": intent_msg})
                    if settings.AGENT_MODE == "multi":
                        # Multi-agent mode: Supervisor orchestrates specialized agents
                        from app.agents.supervisor import supervisor
                        await supervisor.stream_chat(message, history, db, ws)
                    else:
                        # Legacy mode: Direct to monolithic FinAIAgent
                        from app.services.ai_agent import agent
                        await agent.stream_chat(message, history, db, ws)
                except Exception as e:
                    logger.error(f"WS chat error: {e}", exc_info=True)
                    await ws.send_json({"type": "error", "content": str(e)})
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)


# ROOT: React Frontend configured cleanly
from fastapi.staticfiles import StaticFiles

STATIC_DIR = Path(os.getenv("FRONTEND_BUILD_PATH", "../frontend/dist")).resolve()

if STATIC_DIR.exists() and STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="frontend")
else:
    @app.get("/")
    async def fallback():
        return {"status": "API running"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.RELOAD,
        workers=1 if settings.RELOAD else settings.WORKERS,
        log_level=settings.LOG_LEVEL.lower(),
    )
