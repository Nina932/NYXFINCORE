"""
SHIM: Re-exports from app.services.v2.decision_engine (Decimal-precise, deterministic MC).
Original v1 code preserved in decision_engine_v1.py.
"""
from app.services.v2.decision_engine import (  # noqa: F401
    decision_engine,
    DecisionEngine,
    DecisionReport,
    BusinessAction,
    CFOVerdict,
    SensitivityResult,
    RiskMatrix,
    ActionGenerator,
    ActionRanker,
    MonteCarloSimulator,
)
