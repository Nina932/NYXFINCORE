"""add company column for multi-tenant isolation

Revision ID: f1a2b3c4d5e6
Revises: 3942c5d15eec
Create Date: 2026-04-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = '3942c5d15eec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Tables that need the company column added for tenant isolation.
# Dataset, Report, User already have it.
TABLES_NEEDING_COMPANY = [
    "custom_tools",
    "dataset_groups",
    "forecasts",
    "scenarios",
    "anomalies",
    "scheduled_reports",
    "financial_documents",
    "alerts",
    "decision_actions",
    "prediction_records",
    "monitoring_rules",
    "journal_entries",
]


def upgrade() -> None:
    for table in TABLES_NEEDING_COMPANY:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("company", sa.String(length=100), nullable=True)
            )
            batch_op.create_index(f"ix_{table}_company", ["company"])

    # Backfill existing rows with the default company name.
    # Uses raw SQL so it works on both SQLite and PostgreSQL.
    default_company = "NYXCoreThinker LLC"
    for table in TABLES_NEEDING_COMPANY:
        op.execute(
            sa.text(f"UPDATE {table} SET company = :company WHERE company IS NULL").bindparams(
                company=default_company
            )
        )


def downgrade() -> None:
    for table in reversed(TABLES_NEEDING_COMPANY):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_index(f"ix_{table}_company")
            batch_op.drop_column("company")
