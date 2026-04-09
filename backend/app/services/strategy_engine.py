"""
SHIM: Re-exports from app.services.v2.strategy_engine (Decimal-precise).
Original v1 code preserved in strategy_engine_v1.py.
"""
from app.services.v2.strategy_engine import (  # noqa: F401
    strategic_engine,
    StrategicEngine,
    StrategyBuilder,
    TimeSimulator,
    StrategyLearner,
    CompanyMemory,
    Strategy,
    StrategyPhase,
    MonthlyProjection,
)
