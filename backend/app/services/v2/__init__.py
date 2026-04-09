"""
FinAI v2 Services — Audit-safe, Decimal-precise financial engine.

All v2 modules use:
- Decimal (ROUND_HALF_UP) for financial math — never float
- DB-backed persistence — never in-memory singletons
- Explicit error handling — never silent exception swallowing
- Deterministic computation — seeded RNG where applicable
"""
