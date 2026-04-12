# ADR-002: Python Decimal Over Float for Financial Math

**Status**: Accepted
**Date**: 2026-04-12
**Context**: Financial calculations require exact arithmetic. IEEE 754 floats cannot represent values like 0.1 exactly.

## Decision

All financial arithmetic uses Python's `decimal.Decimal` with `ROUND_HALF_UP`. Float is forbidden in any financial computation path.

## Rationale

- `float(0.1) + float(0.2) != 0.3` — this is unacceptable for financial statements.
- IFRS and Georgian tax regulations require specific rounding rules (ROUND_HALF_UP).
- A 0.01% rounding error on 51M GEL revenue is 5,116 GEL — material for audit.
- Excel values arrive as floats from openpyxl — we convert via `Decimal(str(v))` at the boundary to avoid binary representation errors.

## Rules

1. **Ingestion boundary** (`smart_excel_parser.py`): Convert to Decimal via `_safe_decimal()`.
2. **Calculation engine**: All arithmetic as Decimal. Use `.quantize(_TWO_PLACES, ROUND_HALF_UP)` for percentages.
3. **Storage**: SQLAlchemy `DecimalString` type stores as string, preserves precision.
4. **API output**: Decimal values serialize as strings in JSON. Frontend parses.
5. **LLM context**: Financial values passed to LLM as formatted strings, not floats.

## Consequences

- Slightly more verbose code than float arithmetic.
- Must use `Decimal(str(v))` not `Decimal(v)` when converting from float (to avoid binary representation).
- All tests for financial values must compare against `Decimal`, not `float`.
