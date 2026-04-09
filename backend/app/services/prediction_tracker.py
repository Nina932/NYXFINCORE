"""
SHIM: Re-exports from app.services.v2.prediction_tracker (DB-persisted).
Original v1 code preserved in prediction_tracker_v1.py.

v2 methods require AsyncSession — callers that don't have db access
can still use the v1 in-memory API via prediction_tracker_v1.
For new code, import from app.services.v2.prediction_tracker directly.
"""
# Re-export v2 classes for new code
from app.services.v2.prediction_tracker import (  # noqa: F401
    PredictionTracker,
    PredictionEntry,
    OutcomeMatch,
    CalibrationAdjustment,
    LearningReport,
)

# For backward compatibility: use v2 singleton
# Callers using the old sync API (no db param) will get AttributeError
# on the new async methods — they need to be updated to pass db.
from app.services.v2.prediction_tracker import prediction_tracker  # noqa: F401
