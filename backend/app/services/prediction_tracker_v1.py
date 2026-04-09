"""
Phase I: Prediction Learning System
=====================================
Tracks predictions vs actual outcomes to self-calibrate forecast accuracy.

Pipeline:
    Record prediction -> Observe actual -> Compute error -> Calibrate -> Adjust weights

Rules:
    - ALL error computations are deterministic
    - Calibration adjustments are multiplicative correction factors
    - No LLM involved in any computation
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# DATACLASSES
# ═══════════════════════════════════════════════════════════════════

@dataclass
class PredictionEntry:
    """A recorded prediction to track against future actuals."""
    prediction_type: str    # forecast|scenario|anomaly_flag|threshold_breach
    metric: str
    predicted_value: float
    confidence: float = 0.5
    source_method: str = ""  # moving_avg|exp_smoothing|ensemble|scenario_engine
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
    """Result of matching a prediction to its actual outcome."""
    prediction_id: int
    predicted_value: float
    actual_value: float
    error_pct: float
    direction_correct: bool
    magnitude_accuracy: float  # 0-1 scale (1 = perfect)

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
    """Correction factor for a forecast method on a specific metric."""
    method: str
    metric: str
    correction_factor: float   # multiplicative: predicted * factor = calibrated
    historical_bias: float     # positive = overestimates, negative = underestimates
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
    """Aggregated prediction accuracy report."""
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


# ═══════════════════════════════════════════════════════════════════
# PREDICTION TRACKER
# ═══════════════════════════════════════════════════════════════════

class PredictionTracker:
    """
    Tracks predictions vs actuals, computes errors, and calibrates future forecasts.

    All computations are deterministic — no LLM calls.
    """

    def __init__(self):
        self._predictions: Dict[int, PredictionEntry] = {}
        self._outcomes: List[OutcomeMatch] = []
        self._method_errors: Dict[str, List[float]] = defaultdict(list)  # method -> [error_pcts]
        self._metric_errors: Dict[str, List[float]] = defaultdict(list)  # metric -> [error_pcts]
        self._next_id: int = 1
        self._calibrations: Dict[str, CalibrationAdjustment] = {}  # "method:metric" -> adjustment

    def record_prediction(self, entry: PredictionEntry) -> int:
        """
        Record a new prediction for future tracking.

        Returns:
            Prediction ID (local, in-memory).
        """
        pid = self._next_id
        self._next_id += 1
        entry.created_at = entry.created_at or datetime.now(timezone.utc).isoformat()
        self._predictions[pid] = entry
        logger.info("Prediction %d recorded: %s %s = %.2f (method=%s)",
                     pid, entry.prediction_type, entry.metric,
                     entry.predicted_value, entry.source_method)
        return pid

    def resolve_prediction(self, prediction_id: int, actual_value: float) -> Optional[OutcomeMatch]:
        """
        Match a prediction to its actual outcome and compute error metrics.

        Args:
            prediction_id: ID from record_prediction
            actual_value: The actual observed value

        Returns:
            OutcomeMatch with error_pct, direction_correct, magnitude_accuracy
        """
        entry = self._predictions.get(prediction_id)
        if entry is None:
            logger.warning("Prediction %d not found", prediction_id)
            return None

        predicted = entry.predicted_value
        # Error percentage: (predicted - actual) / actual * 100
        if abs(actual_value) > 0.001:
            error_pct = round((predicted - actual_value) / abs(actual_value) * 100, 2)
        else:
            error_pct = 0.0 if abs(predicted) < 0.001 else 100.0

        # Direction accuracy: did we predict the right direction of change?
        direction_correct = (predicted >= 0 and actual_value >= 0) or (predicted < 0 and actual_value < 0)

        # Magnitude accuracy: 1 - clamp(|error_pct|/100, 0, 1)
        magnitude_accuracy = round(1.0 - min(abs(error_pct) / 100.0, 1.0), 4)

        outcome = OutcomeMatch(
            prediction_id=prediction_id,
            predicted_value=predicted,
            actual_value=actual_value,
            error_pct=error_pct,
            direction_correct=direction_correct,
            magnitude_accuracy=magnitude_accuracy,
        )

        self._outcomes.append(outcome)
        self._method_errors[entry.source_method].append(error_pct)
        self._metric_errors[entry.metric].append(error_pct)

        logger.info("Prediction %d resolved: error=%.2f%%, direction=%s, magnitude=%.4f",
                     prediction_id, error_pct, direction_correct, magnitude_accuracy)
        return outcome

    def calibrate(self, method: str, metric: str = "") -> Optional[CalibrationAdjustment]:
        """
        Compute calibration adjustment for a method (optionally per metric).

        If a method consistently overestimates by X%, correction_factor = 1 / (1 + X/100)
        """
        errors = self._method_errors.get(method, [])
        if metric:
            # Filter to method+metric specific errors
            errors = [
                self._metric_errors[metric][i]
                for i, o in enumerate(self._outcomes)
                if self._predictions.get(o.prediction_id, PredictionEntry("", "", 0)).source_method == method
                and self._predictions.get(o.prediction_id, PredictionEntry("", "", 0)).metric == metric
            ]
            if not errors:
                errors = self._method_errors.get(method, [])

        if len(errors) < 2:
            return None

        avg_bias = round(sum(errors) / len(errors), 4)  # positive = overestimates
        # Correction: if avg_bias = +15 (overestimates 15%), factor = 1/(1+0.15) ≈ 0.87
        correction = round(1.0 / (1.0 + avg_bias / 100.0), 4) if abs(avg_bias) > 0.01 else 1.0

        adj = CalibrationAdjustment(
            method=method,
            metric=metric or "all",
            correction_factor=correction,
            historical_bias=avg_bias,
            sample_size=len(errors),
        )
        key = f"{method}:{metric or 'all'}"
        self._calibrations[key] = adj
        return adj

    def get_correction_factor(self, method: str, metric: str = "") -> float:
        """Return the correction factor for a method:metric pair, or 1.0 if not calibrated."""
        key = f"{method}:{metric or 'all'}"
        adj = self._calibrations.get(key)
        if adj:
            return adj.correction_factor
        # Try method-level fallback
        key_fallback = f"{method}:all"
        adj = self._calibrations.get(key_fallback)
        return adj.correction_factor if adj else 1.0

    def generate_report(self) -> LearningReport:
        """Generate aggregated prediction accuracy report."""
        total = len(self._predictions)
        resolved = len(self._outcomes)

        # Overall accuracy: average magnitude_accuracy across all outcomes
        overall_acc = 0.0
        if resolved:
            overall_acc = round(
                sum(o.magnitude_accuracy for o in self._outcomes) / resolved * 100, 2
            )

        # By method
        by_method: Dict[str, Dict[str, Any]] = {}
        for method, errors in self._method_errors.items():
            if not errors:
                continue
            abs_errors = [abs(e) for e in errors]
            by_method[method] = {
                "count": len(errors),
                "avg_error_pct": round(sum(abs_errors) / len(abs_errors), 2),
                "avg_bias": round(sum(errors) / len(errors), 2),
                "max_error_pct": round(max(abs_errors), 2),
                "direction_accuracy_pct": round(
                    sum(1 for o in self._outcomes
                        if self._predictions.get(o.prediction_id, PredictionEntry("", "", 0)).source_method == method
                        and o.direction_correct)
                    / max(len(errors), 1) * 100, 2
                ),
            }

        # By metric
        by_metric: Dict[str, Dict[str, Any]] = {}
        for metric, errors in self._metric_errors.items():
            if not errors:
                continue
            abs_errors = [abs(e) for e in errors]
            by_metric[metric] = {
                "count": len(errors),
                "avg_error_pct": round(sum(abs_errors) / len(abs_errors), 2),
                "avg_bias": round(sum(errors) / len(errors), 2),
            }

        # Calibration adjustments
        calibrations = list(self._calibrations.values())

        return LearningReport(
            total_predictions=total,
            total_resolved=resolved,
            overall_accuracy_pct=overall_acc,
            by_method=by_method,
            by_metric=by_metric,
            calibration_adjustments=calibrations,
            confidence_trend=[],
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    def to_kg_entities(self) -> List[Dict[str, Any]]:
        """Generate KG entities from prediction outcomes."""
        entities = []
        for adj in self._calibrations.values():
            entities.append({
                "entity_id": f"prediction_calibration_{adj.method}_{adj.metric}",
                "entity_type": "prediction_outcome",
                "label_en": f"Calibration: {adj.method} on {adj.metric}",
                "label_ka": "",
                "description": (
                    f"Correction factor: {adj.correction_factor:.4f}, "
                    f"Bias: {adj.historical_bias:+.2f}%, "
                    f"Sample size: {adj.sample_size}"
                ),
                "properties": {
                    "method": adj.method,
                    "metric": adj.metric,
                    "correction_factor": adj.correction_factor,
                    "historical_bias": adj.historical_bias,
                    "sample_size": adj.sample_size,
                },
            })
        return entities

    def reset(self):
        """Clear all tracked data (for testing)."""
        self._predictions.clear()
        self._outcomes.clear()
        self._method_errors.clear()
        self._metric_errors.clear()
        self._calibrations.clear()
        self._next_id = 1


# Module-level singleton
prediction_tracker = PredictionTracker()
