"""
FinAI Agent Decisions Sub-Router
==================================
Phase I: Decision Intelligence, Prediction Tracking, and Monitoring.
Covers: decisions/generate, simulate, report, verdict, predictions,
        monitoring rules/alerts/dashboard, orchestrator endpoints,
        company history, company financials.
Extracted from agent_monitoring.py for maintainability.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.config import settings
import logging

logger = logging.getLogger(__name__)
router = APIRouter()  # NO prefix — parent adds /api/agent


@router.post("/agents/decisions/generate")
async def decisions_generate(body: dict):
    """Phase I: Generate ranked business actions from financial diagnosis."""
    try:
        from app.services.decision_engine import decision_engine
        from app.services.diagnosis_engine import diagnosis_engine
        current = dict(body.get("current") or body.get("financials") or body)
        if "ga_expenses" not in current and "operating_expenses" in current:
            current["ga_expenses"] = current["operating_expenses"]
        if "gross_profit" not in current and "revenue" in current and "cogs" in current:
            current["gross_profit"] = current["revenue"] - current["cogs"]
        report = diagnosis_engine.run_full_diagnosis(
            current_financials=current,
            previous_financials=body.get("previous", None),
            balance_sheet=body.get("balance_sheet", None),
            industry_id=body.get("industry", "fuel_distribution"),
        )
        decision_report = decision_engine.generate_decision_report(
            report=report, financials=current, top_n=body.get("top_n", 10),
        )
        result = decision_report.to_dict()
        try:
            actions = decision_report.ranked_actions if hasattr(decision_report, "ranked_actions") else []
            if actions:
                top = actions[0]
                cat = top.category.replace("_", " ").title() if hasattr(top, "category") else "Action"
                desc = top.description if hasattr(top, "description") else "recommended action"
                roi = f" (ROI {top.roi_estimate:.1f}x)" if hasattr(top, "roi_estimate") and top.roi_estimate else ""
                risk = f", {top.risk_level} risk" if hasattr(top, "risk_level") else ""
                summary = f"Top recommended action: {desc}{roi}{risk}."
            else:
                summary = "No actions generated — provide financial data for analysis."
        except Exception:
            summary = "Decision report generated successfully."
        result["summary"] = summary
        return result
    except Exception as e:
        return {"error": str(e)}


@router.post("/agents/decisions/simulate")
async def decisions_simulate(body: dict):
    """Phase I: Simulate financial impact of a specific business action."""
    try:
        from app.services.decision_engine import decision_engine, BusinessAction
        action = BusinessAction(
            action_id=f"sim_{body.get('category', 'custom')}",
            description=body.get("description", "Custom action"),
            category=body.get("category", "operational_efficiency"),
            expected_impact=0,
            implementation_cost=body.get("cost", 50_000),
            roi_estimate=0,
            risk_level=body.get("risk", "medium"),
            time_horizon=body.get("horizon", "short_term"),
            source_signal="manual_simulation",
        )
        result = decision_engine.simulator.simulate_action(action, body.get("financials", {}))
        return result
    except Exception as e:
        return {"error": str(e)}


@router.get("/agents/decisions/report")
async def decisions_report():
    """Phase I: Get the most recently generated decision report."""
    try:
        from app.services.decision_engine import decision_engine
        report = decision_engine.get_last_report()
        if report:
            return report.to_dict()
        return {"message": "No decision report generated yet. Use POST /agents/decisions/generate first."}
    except Exception as e:
        return {"error": str(e)}


@router.get("/agents/decisions/verdict")
async def decisions_verdict():
    """Phase I: Get the CFO verdict — the system's opinionated #1 recommendation."""
    try:
        from app.services.decision_engine import decision_engine
        verdict = decision_engine.get_last_verdict()
        if verdict:
            return verdict.to_dict()
        return {"message": "No verdict generated yet. Use POST /agents/decisions/generate first."}
    except Exception as e:
        return {"error": str(e)}


@router.post("/agents/predictions/record")
async def predictions_record(body: dict):
    """Phase I: Record a prediction for future accuracy tracking."""
    try:
        from app.services.prediction_tracker import prediction_tracker, PredictionEntry
        entry = PredictionEntry(
            prediction_type=body.get("prediction_type", "forecast"),
            metric=body.get("metric", ""),
            predicted_value=body.get("predicted_value", 0),
            confidence=body.get("confidence", 0.5),
            source_method=body.get("source_method", ""),
            prediction_period=body.get("prediction_period", ""),
            dataset_id=body.get("dataset_id"),
        )
        pid = prediction_tracker.record_prediction(entry)
        return {"prediction_id": pid, "status": "recorded"}
    except Exception as e:
        return {"error": str(e)}


@router.post("/agents/predictions/resolve")
async def predictions_resolve(body: dict):
    """Phase I: Match a prediction to its actual outcome."""
    try:
        from app.services.prediction_tracker import prediction_tracker
        pid = body.get("prediction_id")
        actual = body.get("actual_value")
        if pid is None or actual is None:
            return {"error": "prediction_id and actual_value are required"}
        outcome = prediction_tracker.resolve_prediction(int(pid), float(actual))
        if outcome:
            return outcome.to_dict()
        return {"error": f"Prediction {pid} not found"}
    except Exception as e:
        return {"error": str(e)}


@router.get("/agents/predictions/accuracy")
async def predictions_accuracy():
    """Phase I: Get prediction accuracy and calibration report."""
    try:
        from app.services.prediction_tracker import prediction_tracker
        report = prediction_tracker.generate_report()
        return report.to_dict()
    except Exception as e:
        return {"error": str(e)}


@router.get("/agents/monitoring/status")
async def monitoring_status(db: AsyncSession = Depends(get_db)):
    """Phase I: Get current monitoring state with active alerts."""
    try:
        from app.services.monitoring_engine import monitoring_engine
        dashboard = await monitoring_engine.get_dashboard(db)
        return dashboard.to_dict() if hasattr(dashboard, "to_dict") else dashboard
    except Exception as e:
        return {"error": str(e), "status": "degraded"}


@router.get("/agents/monitoring/alerts")
async def monitoring_alerts(db: AsyncSession = Depends(get_db)):
    """Phase I: Get all active monitoring alerts."""
    try:
        from app.services.monitoring_engine import monitoring_engine
        active = await monitoring_engine.get_active_alerts(db)
        alert_dicts = [a if isinstance(a, dict) else a.to_dict() for a in active]
        try:
            from app.services.realtime import realtime_manager
            critical = [a for a in alert_dicts if a.get("severity") in ("critical", "emergency")]
            if critical:
                await realtime_manager.emit("alert_triggered", {
                    "alerts": critical, "total_active": len(alert_dicts),
                })
        except Exception:
            pass
        return {"alerts": alert_dicts, "count": len(active)}
    except Exception as e:
        return {"error": str(e)}


@router.post("/agents/monitoring/rules")
async def monitoring_add_rule(body: dict):
    """Phase I: Add a new monitoring rule."""
    try:
        from app.services.monitoring_engine import monitoring_engine, MonitoringCheck
        rule = MonitoringCheck(
            rule_type=body.get("rule_type", "threshold"),
            metric=body.get("metric", ""),
            operator=body.get("operator", "lt"),
            threshold=float(body.get("threshold", 0)),
            severity=body.get("severity", "warning"),
            cooldown_minutes=int(body.get("cooldown_minutes", 60)),
            is_enabled=body.get("is_enabled", True),
            description=body.get("description", ""),
        )
        monitoring_engine.add_rule(rule)
        return {"status": "rule_added", "rules_count": len(monitoring_engine.get_rules())}
    except Exception as e:
        return {"error": str(e)}


@router.get("/agents/monitoring/dashboard")
async def monitoring_dashboard():
    """Phase I: Full monitoring dashboard with rules, alerts, and system health."""
    try:
        from app.services.monitoring_engine import monitoring_engine
        dashboard = monitoring_engine.get_dashboard()
        rules = monitoring_engine.get_rules()
        result = dashboard.to_dict()
        result["rules"] = [r.to_dict() for r in rules]
        return result
    except Exception as e:
        return {"error": str(e)}


# ── Orchestrator ──────────────────────────────────────────────────────────────

@router.post("/agents/orchestrator/run")
async def orchestrator_run(body: dict):
    """Phase K: Run full pipeline + persist result to DataStore."""
    import time as _time_orch
    _t0_orch = _time_orch.time()
    try:
        from app.services.orchestrator import orchestrator
        from app.services.data_store import data_store
        import os
        from datetime import datetime, timezone

        current = body.get("current") or body.get("financials") or {}
        if not current and body.get("revenue"):
            current = {k: v for k, v in body.items() if isinstance(v, (int, float)) or k in ("industry", "period")}
        if "ga_expenses" not in current and "operating_expenses" in current:
            current["ga_expenses"] = current["operating_expenses"]
        if "gross_profit" not in current and current.get("revenue") and current.get("cogs"):
            current["gross_profit"] = current["revenue"] - current["cogs"]
        prev = body.get("previous", None)
        bs = body.get("balance_sheet", None)
        company_id_orch = body.get("company_id")
        period_orch = body.get("period")

        if not current and company_id_orch:
            try:
                periods_orch = data_store.get_all_periods(company_id_orch)
                target_p = period_orch or (periods_orch[-1] if periods_orch else None)
                if target_p:
                    fin = data_store.get_financials(company_id_orch, target_p)
                    if fin:
                        if fin.get("revenue", 0) > 0 and fin.get("gross_profit", 0) > 0 and not fin.get("cogs"):
                            fin["cogs"] = fin["revenue"] - fin["gross_profit"]
                        current = {k: v for k, v in fin.items() if not k.startswith("bs_")}
                        bs = {k: v for k, v in fin.items() if k.startswith("bs_") or k in (
                            "cash", "receivables", "inventory", "total_assets",
                            "total_liabilities", "total_equity", "current_assets",
                            "current_liabilities", "fixed_assets_net",
                        )}
                    if len(periods_orch) >= 2:
                        idx = periods_orch.index(target_p) if target_p in periods_orch else -1
                        if idx > 0:
                            prev = data_store.get_financials(company_id_orch, periods_orch[idx - 1])
            except Exception:
                pass

        result = orchestrator.run(
            current_financials=current,
            previous_financials=prev,
            balance_sheet=bs,
            industry_id=body.get("industry", "fuel_distribution"),
            project_months=body.get("months", 12),
            monte_carlo_iterations=body.get("mc_iterations", 500),
        )
        rd = result.to_dict()

        company_id = body.get("company_id")
        pdf_path = None
        run_id = None

        if company_id:
            try:
                from app.services.professional_pdf import professional_pdf
                company_name = body.get("company", "Company")
                os.makedirs("exports", exist_ok=True)
                ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                pdf_path = f"exports/report_{ts}.pdf"
                pdf_bytes = professional_pdf.generate(rd, company_name)
                with open(pdf_path, "wb") as f:
                    f.write(pdf_bytes)
            except Exception:
                pdf_path = None
            run_id = data_store.save_orchestrator_result(company_id, rd, pdf_path=pdf_path)

        rd["orchestrator_run_id"] = run_id
        rd["pdf_path"] = pdf_path

        try:
            from app.services.realtime import realtime_manager
            await realtime_manager.emit("analysis_ready", {
                "run_id": run_id,
                "health_score": rd.get("executive_summary", {}).get("health_score"),
                "health_grade": rd.get("executive_summary", {}).get("health_grade"),
                "stages_completed": len([s for s in rd.get("stages", {}).values() if s]),
            })
        except Exception:
            pass

        try:
            from app.services.activity_feed import activity_feed
            _dur_o = int((_time_orch.time() - _t0_orch) * 1000)
            activity_feed.record(
                event_type="function_execution", resource_type="Orchestrator",
                resource_id=str(run_id or "unknown"), action="orchestrator_run",
                details={"company_id": company_id,
                         "stages": len([s for s in rd.get("stages", {}).values() if s]),
                         "health_score": rd.get("executive_summary", {}).get("health_score"),
                         "pdf_generated": pdf_path is not None},
                status="success", duration_ms=_dur_o,
            )
        except Exception:
            pass

        return rd
    except Exception as e:
        try:
            from app.services.activity_feed import activity_feed
            activity_feed.record(
                event_type="function_execution", resource_type="Orchestrator",
                resource_id="unknown", action="orchestrator_run",
                details={"error": str(e)[:200]}, status="failure",
                duration_ms=int((_time_orch.time() - _t0_orch) * 1000),
            )
        except Exception:
            pass
        return {"error": str(e)}


@router.post("/agents/orchestrator/pdf")
async def orchestrator_pdf(body: dict):
    """Phase M: Run full pipeline and generate downloadable PDF report."""
    try:
        from app.services.orchestrator import orchestrator
        from app.services.pdf_report import pdf_generator
        from fastapi.responses import Response

        result = orchestrator.run(
            current_financials=body.get("current", {}),
            previous_financials=body.get("previous", None),
            balance_sheet=body.get("balance_sheet", None),
            industry_id=body.get("industry", "fuel_distribution"),
            project_months=body.get("months", 12),
            monte_carlo_iterations=body.get("mc_iterations", 200),
        )
        company = body.get("company", settings.COMPANY_NAME)
        result_dict = result.to_dict()
        result_dict["financials"] = body.get("current", {})
        try:
            from app.services.pdf_report import generate_reportlab_pdf
            pdf_bytes = generate_reportlab_pdf(result_dict, company)
        except Exception:
            pdf_bytes = pdf_generator.generate_from_orchestrator(result_dict, company)
        if isinstance(pdf_bytes, bytearray):
            pdf_bytes = bytes(pdf_bytes)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=finai_report_{result.generated_at[:10]}.pdf"},
        )
    except Exception as e:
        logger.error("PDF generation error: %s", e, exc_info=True)
        from fastapi.responses import JSONResponse
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.post("/agents/orchestrator/brief")
async def orchestrator_brief(body: dict):
    """Phase P: Generate 1-page executive brief PDF."""
    try:
        from app.services.orchestrator import orchestrator
        from app.services.executive_brief import executive_brief as brief_generator
        from fastapi.responses import Response

        result = orchestrator.run(
            current_financials=body.get("current", {}),
            previous_financials=body.get("previous", None),
            balance_sheet=body.get("balance_sheet", None),
            industry_id=body.get("industry", "fuel_distribution"),
            project_months=body.get("months", 12),
            monte_carlo_iterations=body.get("mc_iterations", 100),
        )
        company = body.get("company", settings.COMPANY_NAME)
        try:
            from app.services.pdf_report import generate_reportlab_pdf
            result_dict = result.to_dict()
            result_dict["financials"] = body.get("current", {})
            pdf_bytes = generate_reportlab_pdf(result_dict, company)
        except Exception:
            pdf_bytes = brief_generator.generate(result.to_dict(), company_name=company)
        if isinstance(pdf_bytes, bytearray):
            pdf_bytes = bytes(pdf_bytes)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=finai_brief_{result.generated_at[:10]}.pdf"},
        )
    except Exception as e:
        return {"error": str(e)}


@router.get("/agents/orchestrator/last")
async def orchestrator_last():
    """Phase K: Get the most recent orchestrator result."""
    try:
        from app.services.orchestrator import orchestrator
        result = orchestrator.get_last_result()
        if result:
            return result.to_dict()
        return {"message": "No orchestrator run yet. Use POST /agents/orchestrator/run first."}
    except Exception as e:
        return {"error": str(e)}


# ── Company History ───────────────────────────────────────────────────────────

@router.get("/companies/{company_id}/history")
async def company_history(company_id: int):
    """Get full timeline for a company: uploads, periods, orchestrator runs."""
    try:
        from app.services.data_store import data_store
        company = data_store.get_company(company_id)
        if not company:
            return {"error": f"Company {company_id} not found"}
        return {
            "company": company,
            "periods": data_store.get_history(company_id),
            "orchestrator_runs": data_store.get_orchestrator_history(company_id),
            "uploads": data_store.get_upload_history(company_id),
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/companies/{company_id}/financials/{period}")
async def company_financials(company_id: int, period: str):
    """Get normalized financials for a specific period, with previous for comparison."""
    try:
        from app.services.data_store import data_store
        from app.services.data_validator import data_validator

        current = data_store.get_financials(company_id, period)
        if not current:
            return {"error": f"No data for company {company_id} period '{period}'"}

        all_periods = data_store.get_all_periods(company_id)
        prev_period = None
        previous = {}
        try:
            idx = all_periods.index(period)
            if idx > 0:
                prev_period = all_periods[idx - 1]
                previous = data_store.get_financials(company_id, prev_period)
        except ValueError:
            pass

        validation = data_validator.validate(current, previous or None)
        return {
            "company_id": company_id,
            "period": period,
            "financials": validation.corrected_data,
            "previous_period": prev_period,
            "previous_financials": previous,
            "validation": validation.to_dict(),
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/companies")
async def list_companies():
    """List all companies in DataStore."""
    try:
        from app.services.data_store import data_store
        return {"companies": data_store.list_companies()}
    except Exception as e:
        return {"error": str(e)}
