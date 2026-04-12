# ADR-004: SQLAlchemy Event Listener for Multi-Tenancy

**Status**: Accepted
**Date**: 2026-04-12
**Context**: FinAI serves multiple companies. Each company's financial data must be isolated.

## Decision

Use a SQLAlchemy `do_orm_execute` event listener to automatically append `WHERE company = :tenant` to every SELECT query on tenant-scoped models. Tenant identity is extracted from the JWT token via middleware.

## Alternatives Considered

1. **Explicit filters in every query**: Error-prone — a single missed `.filter(company=...)` leaks data across tenants.
2. **Database-per-tenant**: Operationally complex. Alembic migrations must run N times. Connection pooling becomes difficult.
3. **Row-Level Security (PostgreSQL)**: Requires PostgreSQL. We support SQLite in development.
4. **Schema-per-tenant**: Same operational complexity as DB-per-tenant.

## Rationale

- The event listener approach is invisible to application code — developers cannot accidentally forget the filter.
- Works on both SQLite (dev) and PostgreSQL (production).
- The `TENANT_SCOPED_MODELS` set is explicit — easy to audit which models are filtered.
- Context variables are thread-safe (via `contextvars.ContextVar`).

## Implementation

- `app/middleware/tenant.py`: Extracts company from authenticated user, stores in ContextVar.
- `app/database.py`: `_inject_tenant_filter` event listener reads ContextVar, appends filter.
- Models in `TENANT_SCOPED_MODELS` must have a `company` column.
- Without tenant context (system/admin operations), all records are visible.

## Consequences

- Adding a new tenant-scoped model requires: (1) add `company` column, (2) add to `TENANT_SCOPED_MODELS` set, (3) create Alembic migration.
- Background tasks running without HTTP context must explicitly set tenant via `set_current_tenant()`.
- Admin operations that need cross-tenant visibility must run without tenant context.
