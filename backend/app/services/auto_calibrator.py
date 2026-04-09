"""
AutoCalibrator — Bridges prediction calibration to forecast engine
==================================================================
Reads calibration factors from PredictionTracker and applies them
to forecasts automatically.
"""

from __future__ import annotations
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class AutoCalibrator:
    """Stores and applies calibration factors to forecasts."""

    _instance: Optional["AutoCalibrator"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._factors: Dict[str, float] = {}  # "method:metric" → factor
            cls._instance._last_update = None
        return cls._instance

    def update_factors(self, factors: Dict[str, float]) -> int:
        """Update calibration factors. Returns count of factors updated."""
        self._factors.update(factors)
        import time
        self._last_update = time.time()
        logger.info("AutoCalibrator: %d factors updated", len(factors))
        return len(factors)

    def get_factor(self, method: str, metric: str = "") -> float:
        """Get calibration factor for a method+metric combo. Default 1.0 (no adjustment)."""
        key = f"{method}:{metric}" if metric else method
        factor = self._factors.get(key, self._factors.get(method, 1.0))
        return factor

    def apply(self, value: float, method: str, metric: str = "") -> float:
        """Apply calibration factor to a predicted value."""
        factor = self.get_factor(method, metric)
        return value * factor

    def status(self) -> dict:
        """Get calibrator status."""
        return {
            "active_factors": len(self._factors),
            "factors": dict(self._factors),
            "last_update": self._last_update,
        }


auto_calibrator = AutoCalibrator()
