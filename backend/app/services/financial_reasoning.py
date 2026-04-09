"""
SHIM: Re-exports from app.services.v2.financial_reasoning (Decimal-precise).
Original v1 code preserved in financial_reasoning_v1.py.
"""
from app.services.v2.financial_reasoning import (  # noqa: F401
    reasoning_engine,
    FinancialReasoningEngine,
    CausalChain,
    CausalFactor,
    VarianceDecomposition,
    ScenarioResult,
)
