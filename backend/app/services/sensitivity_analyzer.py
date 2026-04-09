"""
SHIM: Re-exports from app.services.v2.sensitivity_analyzer (Decimal, deterministic MC).
Original v1 code preserved in sensitivity_analyzer_v1.py.
"""
from app.services.v2.sensitivity_analyzer import (  # noqa: F401
    sensitivity_analyzer,
    multi_var_simulator,
    scenario_monte_carlo,
    SensitivityAnalyzer,
    MultiVariableSimulator,
    ScenarioMonteCarlo,
    SensitivityReport,
    SensitivityBand,
    MultiVarResult,
    ScenarioMonteCarloResult,
)
