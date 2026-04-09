"""
Flywheel Router — Self-improvement cycle status and control
============================================================
"""

from fastapi import APIRouter
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/flywheel", tags=["flywheel"])


@router.get("/status")
async def flywheel_status():
    """Comprehensive flywheel status: interactions, scoring, learning, calibration."""
    from app.services.flywheel_loop import flywheel_loop
    return flywheel_loop.get_status()


@router.post("/trigger-cycle")
async def trigger_cycle():
    """Manually trigger one flywheel cycle (score + sync + calibrate)."""
    from app.services.flywheel_loop import flywheel_loop
    result = await flywheel_loop.run_cycle()
    return result


@router.get("/scoring-queue")
async def scoring_queue():
    """Show pending scoring queue and recent scores."""
    from app.services.flywheel_loop import flywheel_loop
    from app.services.data_flywheel import data_flywheel

    recent_scored = [
        {
            "id": i.interaction_id,
            "model": i.model,
            "prompt_preview": i.prompt[:80],
            "quality_score": i.quality_score,
            "workload_type": i.workload_type,
        }
        for i in data_flywheel._interactions
        if i.quality_score is not None
    ][-10:]

    return {
        "queue_size": len(flywheel_loop._scoring_queue),
        "total_interactions": len(data_flywheel._interactions),
        "scored": sum(1 for i in data_flywheel._interactions if i.quality_score is not None),
        "unscored": sum(1 for i in data_flywheel._interactions if i.quality_score is None),
        "recent_scored": recent_scored,
    }


@router.get("/calibrations")
async def get_calibrations():
    """Get active prediction calibration factors."""
    from app.services.auto_calibrator import auto_calibrator
    return auto_calibrator.status()


# ── Fine-Tune Pipeline (closes the flywheel loop) ──

@router.get("/finetune/status")
async def finetune_status():
    """Get fine-tune pipeline status."""
    from app.services.finetune_pipeline import finetune_pipeline
    return finetune_pipeline.status()


@router.post("/finetune/export")
async def finetune_export():
    """Export high-quality scored interactions as training data (JSONL)."""
    from app.services.finetune_pipeline import finetune_pipeline
    return finetune_pipeline.export_training_data()


@router.post("/finetune/train")
async def finetune_train(body: dict = {}):
    """Full pipeline: export → create modelfile → deploy via Ollama."""
    from app.services.finetune_pipeline import finetune_pipeline
    base_model = body.get("base_model", "llama3.2:1b")
    return await finetune_pipeline.train_and_deploy(base_model)
