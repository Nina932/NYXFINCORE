"""
FinAI v2 Prediction Tracker — DB-persisted, restart-safe.
==========================================================
Replaces in-memory Dict storage with async SQLAlchemy CRUD against
existing PredictionRecord and PredictionOutcome models.

Key changes from v1:
- All predictions persist across server restarts
- IDs are database-generated (no collisions)
- All methods are async (require AsyncSession)
- Calibration computed from DB aggregations

Public API (drop-in for v1 after making callers async):
    from app.services.v2.prediction_tracker import prediction_tracker
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ── Dataclasses (unchanged from v1 for API compatibility) ──────────────

@dataclass
class PredictionEntry:
    prediction_type: str
    metric: str
    predicted_value: float
    confidence: float = 0.5
    source_method: str = ""
    prediction_period: str = ""
    dataset_id: Optional[int] = None
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prediction_type": self.prediction_type,
            "metric": self.metric,
            "predicted_value": round(self.predicted_value, 2),
            "confidence": round(self.confidence, 4),
            "source_method": self.source_method,
            "prediction_period": self.prediction_period,
            "dataset_id": self.dataset_id,
            "created_at": self.created_at,
        }


@dataclass
class OutcomeMatch:
    prediction_id: int
    predicted_value: float
    actual_value: float
    error_pct: float
    direction_correct: bool
    magnitude_accuracy: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prediction_id": self.prediction_id,
            "predicted_value": round(self.predicted_value, 2),
            "actual_value": round(self.actual_value, 2),
            "error_pct": round(self.error_pct, 2),
            "direction_correct": self.direction_correct,
            "magnitude_accuracy": round(self.magnitude_accuracy, 4),
        }


@dataclass
class CalibrationAdjustment:
    method: str
    metric: str
    correction_factor: float
    historical_bias: float
    sample_size: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "method": self.method,
            "metric": self.metric,
            "correction_factor": round(self.correction_factor, 4),
            "historical_bias": round(self.historical_bias, 4),
            "sample_size": self.sample_size,
        }


@dataclass
class LearningReport:
    total_predictions: int = 0
    total_resolved: int = 0
    overall_accuracy_pct: float = 0.0
    by_method: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    by_metric: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    calibration_adjustments: List[CalibrationAdjustment] = field(default_factory=list)
    confidence_trend: List[Dict[str, Any]] = field(default_factory=list)
    generated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_predictions": self.total_predictions,
            "total_resolved": self.total_resolved,
            "overall_accuracy_pct": round(self.overall_accuracy_pct, 2),
            "by_method": self.by_method,
            "by_metric": self.by_metric,
            "calibration_adjustments": [c.to_dict() for c in self.calibration_adjustments],
            "confidence_trend": self.confidence_trend,
            "generated_at": self.generated_at,
        }


# ── DB-backed Prediction Tracker ──────────────────────────────────────

class PredictionTracker:
    """
    DB-persisted prediction tracker.

    All data survives server restarts. IDs are database-generated.
    Calibration is computed from DB aggregations (not in-memory state).
    """

    async def record_prediction(self, entry: PredictionEntry, db: AsyncSession) -> int:
        """Record a prediction to DB. Returns database-generated ID."""
        from app.models.all_models import PredictionRecord

        record = PredictionRecord(
            prediction_type=entry.prediction_type,
            metric=entry.metric,
            predicted_value=entry.predicted_value,
            confidence=entry.confidence,
            source_method=entry.source_method,
            prediction_period=entry.prediction_period,
            dataset_id=entry.dataset_id,
        )
        db.add(record)
        await db.flush()  # Get the ID without committing

        logger.info(
            "Prediction %d recorded: %s %s = %.2f (method=%s)",
            record.id, entry.prediction_type, entry.metric,
            entry.predicted_value, entry.source_method,
        )
        return record.id

    async def resolve_prediction(
        self, prediction_id: int, actual_value: float, db: AsyncSession
    ) -> Optional[OutcomeMatch]:
        """Match prediction to actual outcome. Returns OutcomeMatch or None."""
        from app.models.all_models import PredictionRecord, PredictionOutcome

        # Load prediction
        result = await db.execute(
            select(PredictionRecord).where(PredictionRecord.id == prediction_id)
        )
        record = result.scalar_one_or_none()
        if not record:
            logger.warning("Prediction %d not found in DB", prediction_id)
            return None

        predicted = record.predicted_value

        # Error computation
        if abs(actual_value) > 0.001:
            error_pct = round((predicted - actual_value) / abs(actual_value) * 100, 2)
        else:
            error_pct = 0.0 if abs(predicted) < 0.001 else 100.0

        direction_correct = (predicted >= 0 and actual_value >= 0) or (predicted < 0 and actual_value < 0)
        magnitude_accuracy = round(1.0 - min(abs(error_pct) / 100.0, 1.0), 4)

        # Persist outcome
        outcome = PredictionOutcome(
            prediction_id=prediction_id,
            actual_value=actual_value,
            error_pct=error_pct,
            direction_correct=direction_correct,
            magnitude_accuracy=magnitude_accuracy,
        )
        db.add(outcome)

        # Mark prediction as resolved
        record.resolved = True
        await db.flush()

        logger.info(
            "Prediction %d resolved: error=%.2f%%, direction=%s, magnitude=%.4f",
            prediction_id, error_pct, direction_correct, magnitude_accuracy,
        )

        return OutcomeMatch(
            prediction_id=prediction_id,
            predicted_value=predicted,
            actual_value=actual_value,
            error_pct=error_pct,
            direction_correct=direction_correct,
            magnitude_accuracy=magnitude_accuracy,
        )

    async def calibrate(
        self, method: str, metric: str = "", db: AsyncSession = None
    ) -> Optional[CalibrationAdjustment]:
        """Compute calibration from DB outcomes."""
        if db is None:
            return None

        from app.models.all_models import PredictionRecord, PredictionOutcome

        # Build query for outcomes matching method (and optionally metric)
        q = (
            select(PredictionOutcome.error_pct)
            .join(PredictionRecord, PredictionOutcome.prediction_id == PredictionRecord.id)
            .where(PredictionRecord.source_method == method)
        )
        if metric:
            q = q.where(PredictionRecord.metric == metric)

        result = await db.execute(q)
        errors = [row[0] for row in result.all() if row[0] is not None]

        if len(errors) < 2:
            return None

        avg_bias = round(sum(errors) / len(errors), 4)
        correction = round(1.0 / (1.0 + avg_bias / 100.0), 4) if abs(avg_bias) > 0.01 else 1.0

        return CalibrationAdjustment(
            method=method,
            metric=metric or "all",
            correction_factor=correction,
            historical_bias=avg_bias,
            sample_size=len(errors),
        )

    async def generate_report(self, db: AsyncSession) -> LearningReport:
        """Generate accuracy report from DB aggregations."""
        from app.models.all_models import PredictionRecord, PredictionOutcome

        # Counts
        total = (await db.execute(
            select(func.count()).select_from(PredictionRecord)
        )).scalar() or 0

        resolved = (await db.execute(
            select(func.count()).select_from(PredictionOutcome)
        )).scalar() or 0

        # Overall accuracy
        avg_mag = (await db.execute(
            select(func.avg(PredictionOutcome.magnitude_accuracy))
        )).scalar()
        overall_acc = round((avg_mag or 0) * 100, 2)

        # By method
        method_stats = await db.execute(
            select(
                PredictionRecord.source_method,
                func.count(PredictionOutcome.id),
                func.avg(func.abs(PredictionOutcome.error_pct)),
                func.avg(PredictionOutcome.error_pct),
                func.max(func.abs(PredictionOutcome.error_pct)),
            )
            .join(PredictionRecord, PredictionOutcome.prediction_id == PredictionRecord.id)
            .group_by(PredictionRecord.source_method)
        )
        by_method = {}
        for row in method_stats.all():
            method_name = row[0] or "unknown"
            by_method[method_name] = {
                "count": row[1],
                "avg_error_pct": round(row[2] or 0, 2),
                "avg_bias": round(row[3] or 0, 2),
                "max_error_pct": round(row[4] or 0, 2),
            }

        # By metric
        metric_stats = await db.execute(
            select(
                PredictionRecord.metric,
                func.count(PredictionOutcome.id),
                func.avg(func.abs(PredictionOutcome.error_pct)),
                func.avg(PredictionOutcome.error_pct),
            )
            .join(PredictionRecord, PredictionOutcome.prediction_id == PredictionRecord.id)
            .group_by(PredictionRecord.metric)
        )
        by_metric = {}
        for row in metric_stats.all():
            by_metric[row[0] or "unknown"] = {
                "count": row[1],
                "avg_error_pct": round(row[2] or 0, 2),
                "avg_bias": round(row[3] or 0, 2),
            }

        return LearningReport(
            total_predictions=total,
            total_resolved=resolved,
            overall_accuracy_pct=overall_acc,
            by_method=by_method,
            by_metric=by_metric,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )


# Module-level singleton
prediction_tracker = PredictionTracker()
