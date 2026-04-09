"""
SHIM: Re-exports from app.services.v2.gl_pipeline (Decimal-precise).
Original v1 code preserved in gl_pipeline_v1.py.
"""
from app.services.v2.gl_pipeline import (  # noqa: F401
    gl_pipeline,
    GLPipeline,
    TrialBalance,
    TrialBalanceRow,
    TrialBalanceBuilder,
    TransactionAdapter,
)
