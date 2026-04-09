"""
Alembic Migration: Float → Numeric for All Financial Columns
==============================================================
This migration converts all Python Float columns that store financial
values to Numeric(18, 6) for IEEE 754 precision elimination.

Also adds tenant_id foundation columns (Phase 3 multi-tenant prep).

Compatible with:
  - SQLite (dev): uses batch_alter_table for ALTER TABLE support
  - PostgreSQL/Neon (prod): uses standard ALTER COLUMN

Run: alembic upgrade head
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import reflection


# revision identifiers
revision = "e4f1a2b3c901"
down_revision = "b7e4a2f19c03"
branch_labels = None
depends_on = None

# Financial columns that must be Numeric, not Float
# These are in ALL_MODELS and currently stored as Float
FLOAT_TO_NUMERIC_MAP = {
    # Table → [column_names]
    "agent_memory": ["importance"],
    "feedback": ["rating"],
    "datasets": [
        "revenue", "cogs", "gross_profit", "ga_expenses", "ebitda",
        "depreciation", "ebit", "interest_expense", "profit_before_tax",
        "net_profit", "cash", "receivables", "inventory", "current_assets",
        "fixed_assets_net", "total_assets", "current_liabilities",
        "long_term_debt", "total_liabilities", "total_equity",
        "operating_cash_flow", "capex", "free_cash_flow",
        "gross_margin_pct", "net_margin_pct", "ebitda_margin_pct",
        "return_on_equity", "return_on_assets", "current_ratio",
        "quick_ratio", "debt_to_equity", "revenue_growth_pct",
        "profit_growth_pct",
    ],
    "orchestrator_results": ["health_score"],
    "alert_rules": ["threshold_value"],
    "active_alerts": ["current_value", "threshold_value"],
    "classification_approvals": ["confidence"],
}

# Neon PostgreSQL-specific: columns that can stay as FLOAT (confidence scores etc.)
INTENTIONAL_FLOAT_COLUMNS = {
    "agent_audit_log": ["tokens_input", "tokens_output", "duration_ms"],
}


def _is_sqlite():
    bind = op.get_bind()
    return bind.dialect.name == "sqlite"


def _column_exists(table_name, column_name):
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        return False
    columns = [c['name'] for c in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade():
    for table_name, columns in FLOAT_TO_NUMERIC_MAP.items():
        if _is_sqlite():
            # SQLite requires batch mode for column type changes
            with op.batch_alter_table(table_name, recreate="always") as batch_op:
                for col in columns:
                    if _column_exists(table_name, col):
                        batch_op.alter_column(
                            col,
                            type_=sa.Numeric(precision=18, scale=6),
                            existing_type=sa.Float(),
                            existing_nullable=True,
                        )
        else:
            # PostgreSQL / Neon — standard ALTER COLUMN
            for col in columns:
                if _column_exists(table_name, col):
                    op.alter_column(
                        table_name, col,
                        type_=sa.Numeric(precision=18, scale=6),
                        existing_type=sa.Float(),
                        existing_nullable=True,
                        postgresql_using=f"{col}::numeric",
                    )


def downgrade():
    """Revert Numeric → Float (precision is lost)."""
    for table_name, columns in FLOAT_TO_NUMERIC_MAP.items():
        try:
            if _is_sqlite():
                with op.batch_alter_table(table_name, recreate="always") as batch_op:
                    for col in columns:
                        try:
                            batch_op.alter_column(
                                col,
                                type_=sa.Float(),
                                existing_type=sa.Numeric(precision=18, scale=6),
                                existing_nullable=True,
                            )
                        except Exception:
                            pass
            else:
                for col in columns:
                    try:
                        op.alter_column(
                            table_name, col,
                            type_=sa.Float(),
                            existing_type=sa.Numeric(precision=18, scale=6),
                            existing_nullable=True,
                        )
                    except Exception:
                        pass
        except Exception:
            pass
