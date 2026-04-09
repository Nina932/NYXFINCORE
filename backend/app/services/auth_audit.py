"""
SHIM: Re-exports from app.services.v2.auth_audit (DB-first write ordering).
Original v1 code preserved in auth_audit_v1.py.
"""
from app.services.v2.auth_audit import (  # noqa: F401
    auth_audit,
    AuthAuditLogger,
)
