"""
FlywheelLoop — Background loop that closes the self-improvement cycle
=====================================================================
Every cycle: score unscored → sync corrections to KG → calibrate predictions.
Runs as a background asyncio task during app lifetime.
"""

from __future__ import annotations
import asyncio
import logging
import time
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

CYCLE_INTERVAL_SECONDS = 300  # 5 minutes
MAX_SCORE_PER_BATCH = 5  # Limit LLM scoring calls per cycle


class FlywheelLoop:
    """Orchestrates the complete data flywheel cycle."""

    _instance: Optional["FlywheelLoop"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._running = False
            cls._instance._cycle_count = 0
            cls._instance._last_cycle = None
            cls._instance._cycle_history: List[Dict] = []
            cls._instance._scoring_queue: List[str] = []
        return cls._instance

    async def run_cycle(self) -> Dict:
        """Execute one complete flywheel cycle."""
        t0 = time.time()
        stats = {
            "cycle": self._cycle_count + 1,
            "scored": 0,
            "synced_to_kg": 0,
            "calibrations_updated": 0,
            "errors": [],
        }

        # Step 1: Score unscored interactions
        try:
            from app.services.data_flywheel import data_flywheel
            from app.services.flywheel_scorer import flywheel_scorer

            unscored = [
                i for i in data_flywheel._interactions
                if i.quality_score is None
            ][:MAX_SCORE_PER_BATCH]

            for interaction in unscored:
                try:
                    result = await flywheel_scorer.score(
                        prompt=interaction.prompt,
                        response=interaction.response,
                        model=interaction.model,
                    )
                    interaction.quality_score = result["score"] / 5.0  # Normalize to 0-1
                    stats["scored"] += 1
                except Exception as e:
                    stats["errors"].append(f"scoring: {e}")
        except Exception as e:
            stats["errors"].append(f"flywheel import: {e}")

        # Step 2: Sync learned classifications to KG
        try:
            from app.services.learning_engine import learning_engine
            if hasattr(learning_engine, '_corrections_since_sync'):
                if learning_engine._corrections_since_sync >= 5:
                    learning_engine.sync_to_kg()
                    stats["synced_to_kg"] = learning_engine._corrections_since_sync
                    learning_engine._corrections_since_sync = 0
        except Exception as e:
            stats["errors"].append(f"kg_sync: {e}")

        # Step 3: Auto-calibrate predictions
        try:
            from app.services.prediction_tracker import prediction_tracker
            from app.services.auto_calibrator import auto_calibrator

            if hasattr(prediction_tracker, '_predictions') and len(prediction_tracker._predictions) >= 2:
                resolved = [p for p in prediction_tracker._predictions if hasattr(p, 'resolved') and p.resolved]
                if len(resolved) >= 2:
                    # Get calibration adjustments
                    report = prediction_tracker.generate_report()
                    factors = {}
                    for method_stat in report.by_method if hasattr(report, 'by_method') else []:
                        if hasattr(method_stat, 'avg_error_pct') and method_stat.avg_error_pct != 0:
                            # Correction factor: inverse of average bias
                            factor = 1.0 / (1.0 + method_stat.avg_error_pct / 100.0)
                            factors[method_stat.method] = round(factor, 4)

                    if factors:
                        auto_calibrator.update_factors(factors)
                        stats["calibrations_updated"] = len(factors)
        except Exception as e:
            stats["errors"].append(f"calibration: {e}")

        # Record cycle
        stats["duration_ms"] = round((time.time() - t0) * 1000)
        self._cycle_count += 1
        self._last_cycle = time.time()
        self._cycle_history.append(stats)
        if len(self._cycle_history) > 100:
            self._cycle_history = self._cycle_history[-50:]

        logger.info(
            "Flywheel cycle %d: scored=%d, synced=%d, calibrated=%d, errors=%d (%.0fms)",
            stats["cycle"], stats["scored"], stats["synced_to_kg"],
            stats["calibrations_updated"], len(stats["errors"]), stats["duration_ms"],
        )
        return stats

    async def start_background(self):
        """Run flywheel cycles in background loop."""
        self._running = True
        logger.info("Flywheel background loop started (interval=%ds)", CYCLE_INTERVAL_SECONDS)
        while self._running:
            try:
                await asyncio.sleep(CYCLE_INTERVAL_SECONDS)
                await self.run_cycle()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Flywheel cycle error: %s", e)
                await asyncio.sleep(60)

    def stop(self):
        """Stop the background loop."""
        self._running = False

    def queue_for_scoring(self, interaction_id: str):
        """Add an interaction to the scoring queue."""
        self._scoring_queue.append(interaction_id)

    def get_status(self) -> Dict:
        """Comprehensive flywheel status."""
        flywheel_stats = {}
        try:
            from app.services.data_flywheel import data_flywheel
            flywheel_stats = {
                "total_interactions": len(data_flywheel._interactions),
                "scored": sum(1 for i in data_flywheel._interactions if i.quality_score is not None),
                "unscored": sum(1 for i in data_flywheel._interactions if i.quality_score is None),
                "avg_quality": round(
                    sum(i.quality_score for i in data_flywheel._interactions if i.quality_score is not None)
                    / max(1, sum(1 for i in data_flywheel._interactions if i.quality_score is not None)),
                    2,
                ) if any(i.quality_score is not None for i in data_flywheel._interactions) else 0,
                "feedback_counts": dict(data_flywheel._feedback_counts) if hasattr(data_flywheel, '_feedback_counts') else {},
            }
        except Exception:
            pass

        learning_stats = {}
        try:
            from app.services.learning_engine import learning_engine
            learning_stats = {
                "total_classifications": len(learning_engine._classifications) if hasattr(learning_engine, '_classifications') else 0,
                "corrections_pending_sync": getattr(learning_engine, '_corrections_since_sync', 0),
            }
        except Exception:
            pass

        calibration_stats = {}
        try:
            from app.services.auto_calibrator import auto_calibrator
            calibration_stats = auto_calibrator.status()
        except Exception:
            pass

        return {
            "running": self._running,
            "cycle_count": self._cycle_count,
            "last_cycle": self._last_cycle,
            "cycle_interval_seconds": CYCLE_INTERVAL_SECONDS,
            "flywheel": flywheel_stats,
            "learning": learning_stats,
            "calibration": calibration_stats,
            "recent_cycles": self._cycle_history[-5:],
            "scoring_queue_size": len(self._scoring_queue),
        }


flywheel_loop = FlywheelLoop()
