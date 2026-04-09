"""
FinAI Advanced Features Router — Forecasting, Scenarios, Anomalies,
Currency, Scheduled Reports, Data Lineage, Trends, and Health Status.

All 22 endpoints follow the existing router pattern: async handlers,
SQLAlchemy async sessions via Depends(get_db), structured error handling,
and JSON-serialisable responses.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
from datetime import date, datetime
import os
import logging

from app.database import get_db
from app.models.all_models import (
    Forecast, Scenario, Anomaly, ExchangeRate,
    ScheduledReport, DataLineage, Dataset,
)
from app.services.forecasting import ForecastEngine, TrendAnalyzer
from app.services.anomaly_detector import AnomalyDetector
from app.services.currency_service import CurrencyService
from app.services.scenario_engine import ScenarioEngine
from app.services.scheduler import ReportScheduler, report_scheduler
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/advanced", tags=["advanced"])

# ── Module-level service instances ────────────────────────────────────────────

forecast_engine = ForecastEngine()
trend_analyzer = TrendAnalyzer()
anomaly_detector = AnomalyDetector()
currency_service = CurrencyService()
scenario_engine = ScenarioEngine()


# ── Helper ────────────────────────────────────────────────────────────────────

async def _get_active_dataset_id(db: AsyncSession) -> int:
    """Resolve the currently active dataset, raising 404 if none exists."""
    result = await db.execute(select(Dataset).where(Dataset.is_active == True))
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(404, "No active dataset. Upload a file first.")
    return ds.id


# ═══════════════════════════════════════════════════════════════════════════════
# 1. FORECASTING (4 endpoints)
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/forecast")
async def generate_forecast(payload: dict, db: AsyncSession = Depends(get_db)):
    """Generate a financial forecast using the specified method and parameters."""
    try:
        forecast_type = payload.get("forecast_type", "revenue")
        product = payload.get("product")
        segment = payload.get("segment")
        method = payload.get("method", "auto")
        periods = int(payload.get("periods", 6))

        result = await forecast_engine.generate_forecast(
            db,
            forecast_type=forecast_type,
            product=product,
            segment=segment,
            method=method,
            periods=periods,
        )
        return result
    except Exception as e:
        logger.error("Forecast generation failed: %s", e, exc_info=True)
        raise HTTPException(500, detail=str(e))


@router.get("/forecasts")
async def list_forecasts(db: AsyncSession = Depends(get_db)):
    """List all saved forecasts, newest first."""
    try:
        result = await db.execute(
            select(Forecast).order_by(Forecast.created_at.desc())
        )
        return [f.to_dict() for f in result.scalars().all()]
    except Exception as e:
        logger.error("Failed to list forecasts: %s", e, exc_info=True)
        raise HTTPException(500, detail=str(e))


@router.get("/forecasts/{forecast_id}")
async def get_forecast(forecast_id: int, db: AsyncSession = Depends(get_db)):
    """Retrieve a single forecast by ID."""
    try:
        result = await db.execute(
            select(Forecast).where(Forecast.id == forecast_id)
        )
        forecast = result.scalar_one_or_none()
        if not forecast:
            raise HTTPException(404, "Forecast not found")
        return forecast.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get forecast %d: %s", forecast_id, e, exc_info=True)
        raise HTTPException(500, detail=str(e))


@router.delete("/forecasts/{forecast_id}")
async def delete_forecast(forecast_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a saved forecast."""
    try:
        result = await db.execute(
            select(Forecast).where(Forecast.id == forecast_id)
        )
        forecast = result.scalar_one_or_none()
        if not forecast:
            raise HTTPException(404, "Forecast not found")
        await db.delete(forecast)
        await db.commit()
        return {"message": "Forecast deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete forecast %d: %s", forecast_id, e, exc_info=True)
        raise HTTPException(500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# 2. SCENARIOS (4 endpoints)
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/scenarios")
async def create_scenario(payload: dict, db: AsyncSession = Depends(get_db)):
    """Create a what-if scenario by applying changes to a base dataset."""
    try:
        name = payload.get("name", "Untitled Scenario")
        description = payload.get("description", "")
        base_dataset_id = payload.get("base_dataset_id")
        changes = payload.get("changes", [])

        if not base_dataset_id:
            base_dataset_id = await _get_active_dataset_id(db)

        result = await scenario_engine.create_scenario(
            db,
            name=name,
            description=description,
            base_dataset_id=base_dataset_id,
            changes=changes,
        )
        return result
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, detail=str(e))
    except Exception as e:
        logger.error("Scenario creation failed: %s", e, exc_info=True)
        raise HTTPException(500, detail=str(e))


@router.get("/scenarios")
async def list_scenarios(db: AsyncSession = Depends(get_db)):
    """List all saved scenarios, newest first."""
    try:
        result = await db.execute(
            select(Scenario).order_by(Scenario.created_at.desc())
        )
        return [s.to_dict() for s in result.scalars().all()]
    except Exception as e:
        logger.error("Failed to list scenarios: %s", e, exc_info=True)
        raise HTTPException(500, detail=str(e))


@router.get("/scenarios/{scenario_id}")
async def get_scenario(scenario_id: int, db: AsyncSession = Depends(get_db)):
    """Retrieve a single scenario with full results."""
    try:
        result = await db.execute(
            select(Scenario).where(Scenario.id == scenario_id)
        )
        scenario = result.scalar_one_or_none()
        if not scenario:
            raise HTTPException(404, "Scenario not found")
        return scenario.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get scenario %d: %s", scenario_id, e, exc_info=True)
        raise HTTPException(500, detail=str(e))


@router.post("/scenarios/compare")
async def compare_scenarios(payload: dict, db: AsyncSession = Depends(get_db)):
    """Compare multiple scenarios side-by-side."""
    try:
        scenario_ids = payload.get("scenario_ids", [])
        if not scenario_ids or len(scenario_ids) < 2:
            raise HTTPException(400, "Provide at least 2 scenario_ids to compare")

        result = await scenario_engine.compare_scenarios(db, scenario_ids)
        return result
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(404, detail=str(e))
    except Exception as e:
        logger.error("Scenario comparison failed: %s", e, exc_info=True)
        raise HTTPException(500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# 3. ANOMALIES (3 endpoints)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/anomalies")
async def list_anomalies(
    dataset_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """List anomalies for a dataset, ordered by severity and score."""
    try:
        did = dataset_id if dataset_id else await _get_active_dataset_id(db)

        result = await db.execute(
            select(Anomaly)
            .where(Anomaly.dataset_id == did)
            .order_by(Anomaly.severity.desc(), Anomaly.score.desc())
        )
        return [a.to_dict() for a in result.scalars().all()]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to list anomalies: %s", e, exc_info=True)
        raise HTTPException(500, detail=str(e))


@router.post("/anomalies/detect")
async def detect_anomalies(payload: dict, db: AsyncSession = Depends(get_db)):
    """Run full anomaly detection (Z-score, IQR, Benford) on a dataset."""
    try:
        dataset_id = payload.get("dataset_id")
        zscore_threshold = float(payload.get("zscore_threshold", 2.0))
        iqr_multiplier = float(payload.get("iqr_multiplier", 1.5))

        if not dataset_id:
            dataset_id = await _get_active_dataset_id(db)

        result = await anomaly_detector.run_full_detection(
            db,
            dataset_id=dataset_id,
            zscore_threshold=zscore_threshold,
            iqr_multiplier=iqr_multiplier,
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Anomaly detection failed: %s", e, exc_info=True)
        raise HTTPException(500, detail=str(e))


@router.put("/anomalies/{anomaly_id}/ack")
async def acknowledge_anomaly(anomaly_id: int, db: AsyncSession = Depends(get_db)):
    """Mark an anomaly as acknowledged."""
    try:
        result = await db.execute(
            select(Anomaly).where(Anomaly.id == anomaly_id)
        )
        anomaly = result.scalar_one_or_none()
        if not anomaly:
            raise HTTPException(404, "Anomaly not found")

        anomaly.is_acknowledged = True
        await db.commit()
        return {"message": "Anomaly acknowledged"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to acknowledge anomaly %d: %s", anomaly_id, e, exc_info=True)
        raise HTTPException(500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# 4. CURRENCY (3 endpoints)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/currency/rates")
async def get_currency_rates(
    base: str = Query(default="GEL", description="Base currency code"),
    db: AsyncSession = Depends(get_db),
):
    """Get current exchange rates for a base currency."""
    try:
        # Try fetching live rates first
        rates = await currency_service.fetch_rates(base=base)

        if rates:
            # Store fetched rates in DB for caching
            await currency_service.store_rates(db, rates, base=base, source="api")
            # Filter to supported currencies only
            supported = CurrencyService.SUPPORTED_CURRENCIES
            filtered = {k: v for k, v in rates.items() if k.upper() in supported}
            return {
                "base": base.upper(),
                "rates": filtered,
                "source": "api",
                "timestamp": datetime.utcnow().isoformat(),
            }

        # Fallback: return rates from DB
        stmt = (
            select(ExchangeRate)
            .where(ExchangeRate.from_currency == base.upper())
            .order_by(ExchangeRate.rate_date.desc())
        )
        result = await db.execute(stmt)
        records = result.scalars().all()

        # Deduplicate by to_currency (keep latest)
        seen = {}
        for r in records:
            if r.to_currency not in seen:
                seen[r.to_currency] = r.rate

        if seen:
            return {
                "base": base.upper(),
                "rates": seen,
                "source": "database_cache",
                "timestamp": datetime.utcnow().isoformat(),
            }

        # Last fallback: hardcoded rates
        fallback_rates = {}
        for (from_c, to_c), rate in CurrencyService.FALLBACK_RATES.items():
            if from_c == base.upper():
                fallback_rates[to_c] = rate

        return {
            "base": base.upper(),
            "rates": fallback_rates,
            "source": "fallback",
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error("Failed to get currency rates: %s", e, exc_info=True)
        raise HTTPException(500, detail=str(e))


@router.get("/currency/convert")
async def convert_currency(
    amount: float = Query(..., description="Amount to convert"),
    from_currency: str = Query(..., description="Source currency code"),
    to_currency: str = Query(..., description="Target currency code"),
    date: Optional[str] = Query(default=None, description="Rate date (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
):
    """Convert an amount from one currency to another."""
    try:
        rate_date = None
        if date:
            try:
                parts = date.split("-")
                from datetime import date as date_cls
                rate_date = date_cls(int(parts[0]), int(parts[1]), int(parts[2]))
            except (ValueError, IndexError):
                raise HTTPException(400, "Invalid date format. Use YYYY-MM-DD.")

        result = await currency_service.convert(
            db,
            amount=amount,
            from_currency=from_currency,
            to_currency=to_currency,
            rate_date=rate_date,
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Currency conversion failed: %s", e, exc_info=True)
        raise HTTPException(500, detail=str(e))


@router.get("/currency/history")
async def get_rate_history(
    from_currency: str = Query(..., description="Source currency code"),
    to_currency: str = Query(..., description="Target currency code"),
    days: int = Query(default=30, description="Number of days of history"),
    db: AsyncSession = Depends(get_db),
):
    """Get historical exchange rate data for a currency pair."""
    try:
        history = await currency_service.get_rate_history(
            db,
            from_currency=from_currency,
            to_currency=to_currency,
            days=days,
        )
        return {
            "from_currency": from_currency.upper(),
            "to_currency": to_currency.upper(),
            "days": days,
            "history": history,
        }
    except Exception as e:
        logger.error("Failed to get rate history: %s", e, exc_info=True)
        raise HTTPException(500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# 5. SCHEDULED REPORTS (5 endpoints)
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/schedules")
async def create_schedule(payload: dict, db: AsyncSession = Depends(get_db)):
    """Create a new scheduled report delivery."""
    try:
        name = payload.get("name")
        report_type = payload.get("report_type", "pl_summary")
        frequency = payload.get("frequency", "weekly")
        recipients = payload.get("recipients", [])
        is_active = payload.get("is_active", True)
        parameters = payload.get("parameters")

        if not name:
            raise HTTPException(400, "Schedule name is required")
        if not recipients:
            raise HTTPException(400, "At least one recipient email is required")

        result = await report_scheduler.create_schedule(
            db,
            name=name,
            report_type=report_type,
            frequency=frequency,
            recipients=recipients,
            is_active=is_active,
            parameters=parameters,
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create schedule: %s", e, exc_info=True)
        raise HTTPException(500, detail=str(e))


@router.get("/schedules")
async def list_schedules(db: AsyncSession = Depends(get_db)):
    """List all scheduled reports."""
    try:
        result = await db.execute(
            select(ScheduledReport).order_by(ScheduledReport.created_at.desc())
        )
        return [s.to_dict() for s in result.scalars().all()]
    except Exception as e:
        logger.error("Failed to list schedules: %s", e, exc_info=True)
        raise HTTPException(500, detail=str(e))


@router.put("/schedules/{schedule_id}")
async def update_schedule(
    schedule_id: int,
    payload: dict,
    db: AsyncSession = Depends(get_db),
):
    """Update an existing scheduled report."""
    try:
        result = await report_scheduler.update_schedule(db, schedule_id, payload)
        if "error" in result:
            raise HTTPException(404, result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update schedule %d: %s", schedule_id, e, exc_info=True)
        raise HTTPException(500, detail=str(e))


@router.delete("/schedules/{schedule_id}")
async def delete_schedule(schedule_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a scheduled report."""
    try:
        result = await db.execute(
            select(ScheduledReport).where(ScheduledReport.id == schedule_id)
        )
        schedule = result.scalar_one_or_none()
        if not schedule:
            raise HTTPException(404, "Schedule not found")

        await db.delete(schedule)
        await db.commit()
        return {"message": "Schedule deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete schedule %d: %s", schedule_id, e, exc_info=True)
        raise HTTPException(500, detail=str(e))


@router.post("/schedules/{schedule_id}/test")
async def test_schedule_email(
    schedule_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Send a test email for a scheduled report to verify delivery.

    Returns detailed diagnostics so the frontend can show exactly
    what is misconfigured (SMTP disabled, missing credentials, etc.).
    """
    try:
        # First check SMTP readiness — return diagnostics, not a hard 400
        smtp_diag = _smtp_diagnostics()
        if not smtp_diag["ready"]:
            return {
                "success": False,
                "message": "SMTP not configured - see diagnostics",
                "smtp": smtp_diag,
            }
        result = await report_scheduler.send_test_email(db, schedule_id)
        result["smtp"] = smtp_diag
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Test email failed for schedule %d: %s", schedule_id, e, exc_info=True)
        raise HTTPException(500, detail=str(e))


@router.get("/smtp-status")
async def smtp_status():
    """Return SMTP configuration diagnostics.

    Never exposes passwords — only reports whether each setting is present
    and whether the overall configuration is ready for email delivery.
    """
    return _smtp_diagnostics()


@router.get("/schedules/{schedule_id}/preview")
async def preview_schedule_email(
    schedule_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Generate the email HTML for a scheduled report and return it.

    This lets users see exactly what the email would look like without
    needing SMTP configured.  The frontend opens it in a new tab.
    """
    from fastapi.responses import HTMLResponse

    try:
        result = await db.execute(
            select(ScheduledReport).where(ScheduledReport.id == schedule_id)
        )
        schedule = result.scalar_one_or_none()
        if schedule is None:
            raise HTTPException(404, detail=f"Schedule id={schedule_id} not found")

        dataset = await report_scheduler._resolve_dataset(schedule, db)
        data = await report_scheduler._gather_report_data(
            schedule.report_type, dataset, db
        )
        data["schedule_name"] = f"[PREVIEW] {schedule.name}"
        data["generated_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        data["period"] = dataset.period if dataset else "N/A"
        data["currency"] = dataset.currency if dataset else "GEL"
        data["company"] = dataset.company if dataset else getattr(
            settings, "COMPANY_NAME", "NYX Core Thinker LLC"
        )

        html = report_scheduler._build_report_html(schedule.report_type, data)
        return HTMLResponse(content=html, media_type="text/html")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Preview failed for schedule %d: %s", schedule_id, e, exc_info=True
        )
        raise HTTPException(500, detail=str(e))


def _smtp_diagnostics() -> dict:
    """Build a diagnostic dict describing the current SMTP configuration.

    Never leaks passwords — only boolean flags + masked hints.
    """
    enabled = getattr(settings, "SMTP_ENABLED", False)
    host = getattr(settings, "SMTP_HOST", "") or ""
    port = getattr(settings, "SMTP_PORT", 0) or 0
    user = getattr(settings, "SMTP_USER", "") or ""
    password = getattr(settings, "SMTP_PASSWORD", "") or ""
    from_addr = getattr(settings, "SMTP_FROM", "") or ""

    issues: list[str] = []
    if not enabled:
        issues.append("SMTP_ENABLED is false - set to true in .env")
    if not host:
        issues.append("SMTP_HOST is empty")
    if not user:
        issues.append("SMTP_USER is empty - set your email address")
    if not password:
        issues.append("SMTP_PASSWORD is empty - set your app password")

    return {
        "ready": enabled and bool(host) and bool(user) and bool(password),
        "enabled": enabled,
        "host": host,
        "port": port,
        "user_set": bool(user),
        "password_set": bool(password),
        "from": from_addr,
        "issues": issues,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 6. DATA LINEAGE (1 endpoint)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/lineage/{entity_type}/{entity_id}")
async def get_lineage(
    entity_type: str,
    entity_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get data lineage (provenance) for a specific financial entity."""
    try:
        result = await db.execute(
            select(DataLineage).where(
                DataLineage.entity_type == entity_type,
                DataLineage.entity_id == entity_id,
            )
        )
        lineage = result.scalar_one_or_none()
        if not lineage:
            return {"message": "No lineage found"}
        return lineage.to_dict()
    except Exception as e:
        logger.error(
            "Failed to get lineage for %s/%d: %s", entity_type, entity_id, e,
            exc_info=True,
        )
        raise HTTPException(500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# 7. TRENDS (1 endpoint)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/trends")
async def get_trends(
    metric: str = Query(default="revenue", description="Metric to analyse"),
    segment: Optional[str] = Query(default=None, description="Segment filter"),
    product: Optional[str] = Query(default=None, description="Product filter"),
    db: AsyncSession = Depends(get_db),
):
    """Analyse historical trends across multiple dataset periods."""
    try:
        result = await trend_analyzer.analyze_trends(
            db,
            metric=metric,
            segment=segment,
            product=product,
        )
        return result
    except Exception as e:
        logger.error("Trend analysis failed: %s", e, exc_info=True)
        raise HTTPException(500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# 8. HEALTH / STATUS (1 endpoint)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/status")
async def advanced_status(db: AsyncSession = Depends(get_db)):
    """Check availability and configuration of all advanced features."""
    try:
        # SMTP status
        smtp_enabled = (
            getattr(settings, "SMTP_ENABLED", False)
            or os.getenv("SMTP_ENABLED", "false").lower() == "true"
        )
        smtp_host = getattr(settings, "SMTP_HOST", None) or os.getenv("SMTP_HOST")

        # Exchange rate API
        exchange_api_url = getattr(settings, "EXCHANGE_RATE_API_URL", None)
        exchange_api_available = exchange_api_url is not None or True  # open.er-api.com fallback

        # ChromaDB / vector store
        chromadb_available = False
        try:
            import chromadb  # noqa: F401
            chromadb_available = True
        except ImportError:
            pass

        # Active dataset check
        active_ds_result = await db.execute(
            select(Dataset).where(Dataset.is_active == True)
        )
        active_dataset = active_ds_result.scalar_one_or_none()

        # Count saved items
        forecast_count = (await db.execute(
            select(Forecast.id)
        )).scalars().all()
        scenario_count = (await db.execute(
            select(Scenario.id)
        )).scalars().all()
        anomaly_count = (await db.execute(
            select(Anomaly.id)
        )).scalars().all()
        schedule_count = (await db.execute(
            select(ScheduledReport.id)
        )).scalars().all()

        return {
            "status": "operational",
            "features": {
                "forecasting": {
                    "available": True,
                    "methods": [
                        "moving_average", "exponential_smoothing",
                        "linear_regression", "growth_rate",
                        "seasonal_decomposition", "auto",
                    ],
                    "saved_forecasts": len(forecast_count),
                },
                "scenarios": {
                    "available": True,
                    "saved_scenarios": len(scenario_count),
                },
                "anomaly_detection": {
                    "available": True,
                    "methods": ["zscore", "iqr", "benford", "seasonal"],
                    "detected_anomalies": len(anomaly_count),
                },
                "currency_conversion": {
                    "available": True,
                    "exchange_api": exchange_api_available,
                    "supported_currencies": CurrencyService.SUPPORTED_CURRENCIES,
                },
                "scheduled_reports": {
                    "available": True,
                    "smtp_enabled": smtp_enabled,
                    "smtp_host": smtp_host,
                    "active_schedules": len(schedule_count),
                    "scheduler_running": report_scheduler.is_running,
                },
                "data_lineage": {
                    "available": True,
                },
                "trend_analysis": {
                    "available": True,
                    "metrics": ["revenue", "cogs", "margin", "ga_expenses"],
                },
                "vector_search": {
                    "available": chromadb_available,
                },
            },
            "active_dataset": {
                "id": active_dataset.id if active_dataset else None,
                "name": active_dataset.name if active_dataset else None,
                "period": active_dataset.period if active_dataset else None,
            },
        }
    except Exception as e:
        logger.error("Status check failed: %s", e, exc_info=True)
        raise HTTPException(500, detail=str(e))
