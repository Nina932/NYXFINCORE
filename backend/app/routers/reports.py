"""
FinAI Reports Router — CRUD + Excel export
Row format matches frontend: {c, l, ac, pl, lvl, bold, sep, s}
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, List, Any
from app.database import get_db, AsyncSessionLocal
from app.models.all_models import Report
from app.utils.excel_export import excel_exporter
from app.services.job_manager import job_manager, compute_checksum
from app.config import settings
import logging, os, asyncio, uuid

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/reports", tags=["reports"])


class ReportCreate(BaseModel):
    title:            str
    report_type:      str = "pl"     # pl | bs | mr | cashflow | custom
    period:           str = "January 2025"
    currency:         str = "GEL"
    company:          Optional[str] = None
    rows:             Optional[List[Any]] = None  # [{c,l,ac,pl,lvl,bold,sep,s}]
    summary:          Optional[str] = None
    kpis:             Optional[Any] = None
    source_dataset_id: Optional[int] = None
    metadata_json:    Optional[Any] = None  # dict or JSON string with {language: "en"|"ka"}


@router.get("")
async def list_reports(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Report).order_by(Report.created_at.desc()))
    return [r.to_dict() for r in result.scalars().all()]


@router.post("")
async def create_report(payload: ReportCreate, db: AsyncSession = Depends(get_db)):
    r = Report(
        title=payload.title, report_type=payload.report_type,
        period=payload.period, currency=payload.currency,
        company=payload.company or settings.COMPANY_NAME, rows=payload.rows,
        summary=payload.summary, kpis=payload.kpis,
        source_dataset_id=payload.source_dataset_id,
        metadata_json=payload.metadata_json,
        generated_by="user",
    )
    db.add(r)
    await db.commit()
    return r.to_dict()


@router.get("/{report_id}")
async def get_report(report_id: int, db: AsyncSession = Depends(get_db)):
    r = (await db.execute(select(Report).where(Report.id == report_id))).scalar_one_or_none()
    if not r:
        raise HTTPException(404, "Report not found")
    return r.to_dict()


@router.delete("/{report_id}")
async def delete_report(report_id: int, db: AsyncSession = Depends(get_db)):
    r = (await db.execute(select(Report).where(Report.id == report_id))).scalar_one_or_none()
    if not r:
        raise HTTPException(404, "Report not found")
    if r.export_path and os.path.exists(r.export_path):
        try:
            os.unlink(r.export_path)
        except Exception:
            pass
    await db.delete(r)
    await db.commit()
    return {"message": "Report deleted", "id": report_id}


@router.get("/{report_id}/export")
async def export_report(report_id: int, db: AsyncSession = Depends(get_db)):
    """Export report to Excel. Row format {c,l,ac,pl,lvl,bold,sep,s} handled by exporter."""
    r = (await db.execute(select(Report).where(Report.id == report_id))).scalar_one_or_none()
    if not r:
        raise HTTPException(404, "Report not found")
    try:
        if r.report_type and r.report_type.lower() == 'bs':
            path = excel_exporter.export_balance_sheet(r)
        else:
            path = excel_exporter.export_report(r)
        r.export_path = path
        await db.commit()
        filename = os.path.basename(path)
        return FileResponse(path, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename=filename)
    except Exception as e:
        logger.error(f"Export error: {e}", exc_info=True)
        raise HTTPException(500, f"Export failed: {str(e)}")


@router.get("/{report_id}/export-enhanced")
async def export_report_enhanced(report_id: int, db: AsyncSession = Depends(get_db)):
    """Enhanced export with Executive Summary sheet, charts, and AI narrative.

    Uses ReportAgent to build a multi-sheet Excel with:
    - Sheet 1: Executive Summary with KPIs and AI Commentary
    - Sheet 2: Charts (Revenue vs COGS, Margin by Segment, Revenue Mix)
    - Sheet 3: Financial Data (original report rows)
    """
    r = (await db.execute(select(Report).where(Report.id == report_id))).scalar_one_or_none()
    if not r:
        raise HTTPException(404, "Report not found")
    try:
        # Create a background job and return job id immediately.
        job_id = f"report-export-{report_id}-{uuid.uuid4().hex[:8]}"
        await job_manager.create_job(job_id)

        async def _worker(job_id: str, report_id: int):
            await job_manager.set_running(job_id)
            try:
                # Use a fresh DB session inside the background task
                async with AsyncSessionLocal() as session:
                    from app.agents.registry import registry
                    from app.agents.base import AgentTask, AgentContext
                    report_agent = registry.get("report")
                    if report_agent:
                        task = AgentTask(
                            task_type="export",
                            instruction="Enhanced Excel export",
                            parameters={"report_id": report_id},
                            source_agent="api",
                        )
                        context = AgentContext(db=session, dataset_ids=[], period=r.period or "", user_message="", conversation_history=[])
                        result = await report_agent.execute(task, context)
                        tool_result = result.data.get("tool_result", "")
                    else:
                        # Fallback
                        # reload report within this session
                        rep = (await session.execute(select(Report).where(Report.id == report_id))).scalar_one_or_none()
                        path = excel_exporter.export_report(rep)

                    # Determine exported file path from agent result.
                    candidate_path = None
                    # Prefer structured result from agent: dict with 'export_path'
                    if 'tool_result' in locals() or 'tool_result' in globals():
                        pass
                    # tool_result is set above when agent executed; fallback to 'path' if not
                    if 'tool_result' in locals():
                        tr = tool_result
                    else:
                        tr = None

                    # If agent returned structured dict, look for keys
                    if isinstance(tr, dict):
                        path_candidate = tr.get('export_path') or tr.get('path') or tr.get('file_path')
                        if path_candidate:
                            p = path_candidate if os.path.isabs(path_candidate) else os.path.join(os.getcwd(), path_candidate)
                            p = os.path.normpath(p)
                            if os.path.exists(p):
                                candidate_path = p
                    # If agent returned a string, try to resolve it as a path
                    if candidate_path is None and isinstance(tr, str) and tr:
                        p = tr if os.path.isabs(tr) else os.path.join(os.getcwd(), tr)
                        p = os.path.normpath(p)
                        if os.path.exists(p):
                            candidate_path = p

                    # If still no candidate and we had a fallback exporter result in 'path', use that
                    if candidate_path is None and 'path' in locals() and path and os.path.exists(path):
                        candidate_path = path

                    if not candidate_path:
                        raise RuntimeError(f"Export did not produce a file (agent result). Received: {tr if 'tr' in locals() else path}")
                    path = candidate_path

                    checksum = compute_checksum(path)
                    # Reload report to compute row_count and dataset refs
                    rep = (await session.execute(select(Report).where(Report.id == report_id))).scalar_one_or_none()
                    row_count = 0
                    dataset_refs = []
                    try:
                        if rep and rep.rows:
                            row_count = len(rep.rows)
                        if rep and getattr(rep, "source_dataset_id", None):
                            dataset_refs = [rep.source_dataset_id]
                        # persist export_path
                        if rep:
                            rep.export_path = path
                            session.add(rep)
                            await session.commit()
                    except Exception:
                        await session.rollback()

                    manifest = {
                        "file_path": path,
                        "checksum": checksum,
                        "row_count": row_count,
                        "dataset_refs": dataset_refs,
                    }

                    await job_manager.set_success(job_id, manifest)
            except Exception as e:
                logger.error(f"Background export job {job_id} failed: {e}", exc_info=True)
                await job_manager.set_failed(job_id, str(e))

        # schedule background worker
        asyncio.create_task(_worker(job_id, report_id))
        return JSONResponse(status_code=202, content={"job_id": job_id, "status_url": f"/api/reports/export-jobs/{job_id}"})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Enhanced export scheduling error: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to schedule enhanced export: {str(e)}")


@router.get("/export-jobs/{job_id}")
async def get_export_job(job_id: str):
    j = await job_manager.get(job_id)
    if not j:
        raise HTTPException(404, "Job not found")
    return {
        "job_id": j.job_id,
        "status": j.status,
        "created_at": j.created_at,
        "updated_at": j.updated_at,
        "manifest": j.manifest,
        "error": j.error,
    }
