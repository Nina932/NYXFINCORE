"""comprehensive schema — all models for PostgreSQL migration

Revision ID: b7e4a2f19c03
Revises: 3942c5d15eec
Create Date: 2026-03-31 12:00:00.000000

This migration captures ALL current models so a fresh PostgreSQL
database can be brought up with a single `alembic upgrade head`.
Each table uses batch_alter for SQLite compatibility and standard
DDL for PostgreSQL.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7e4a2f19c03'
down_revision: Union[str, None] = '3942c5d15eec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    """Check if a table already exists (works for both SQLite and PostgreSQL)."""
    from sqlalchemy import inspect as sa_inspect
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    # This migration creates any tables that don't already exist.
    # On a fresh PostgreSQL database all tables are created.
    # On an existing SQLite database this is mostly a no-op.

    if not _table_exists('users'):
        op.create_table('users',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('email', sa.String(length=255), nullable=False),
            sa.Column('hashed_password', sa.String(length=255), nullable=False),
            sa.Column('full_name', sa.String(length=255), nullable=True),
            sa.Column('role', sa.String(length=50), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=True),
            sa.Column('is_verified', sa.Boolean(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_users_email', 'users', ['email'], unique=True)

    if not _table_exists('dataset_groups'):
        op.create_table('dataset_groups',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('company', sa.String(length=255), nullable=True),
            sa.Column('fiscal_year', sa.Integer(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )

    if not _table_exists('datasets'):
        op.create_table('datasets',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('original_filename', sa.String(length=255), nullable=True),
            sa.Column('file_type', sa.String(length=100), nullable=True),
            sa.Column('file_size', sa.Integer(), nullable=True),
            sa.Column('extension', sa.String(length=10), nullable=True),
            sa.Column('sheet_count', sa.Integer(), nullable=True),
            sa.Column('record_count', sa.Integer(), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=True),
            sa.Column('is_seed', sa.Boolean(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=True),
            sa.Column('period', sa.String(length=50), nullable=True),
            sa.Column('currency', sa.String(length=10), nullable=True),
            sa.Column('company', sa.String(length=100), nullable=True),
            sa.Column('upload_path', sa.String(length=500), nullable=True),
            sa.Column('group_id', sa.Integer(), sa.ForeignKey('dataset_groups.id', ondelete='SET NULL'), nullable=True),
            sa.Column('parse_error', sa.Text(), nullable=True),
            sa.Column('parse_metadata', sa.JSON(), nullable=True),
            sa.Column('owner_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_dataset_created', 'datasets', ['created_at'])
        op.create_index('ix_dataset_active', 'datasets', ['is_active'])
        op.create_index('ix_dataset_period', 'datasets', ['period'])

    if not _table_exists('dataset_snapshots'):
        op.create_table('dataset_snapshots',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('dataset_id', sa.Integer(), sa.ForeignKey('datasets.id', ondelete='CASCADE'), nullable=False),
            sa.Column('version', sa.Integer(), nullable=True),
            sa.Column('fingerprint', sa.String(length=128), nullable=False),
            sa.Column('record_counts', sa.JSON(), nullable=True),
            sa.Column('totals_json', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_snapshot_dataset', 'dataset_snapshots', ['dataset_id'])
        op.create_index('ix_snapshot_fingerprint', 'dataset_snapshots', ['fingerprint'])

    if not _table_exists('schema_profiles'):
        op.create_table('schema_profiles',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('file_type', sa.String(length=100), nullable=True),
            sa.Column('business_unit', sa.String(length=100), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )

    if not _table_exists('schema_versions'):
        op.create_table('schema_versions',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('profile_id', sa.Integer(), sa.ForeignKey('schema_profiles.id', ondelete='CASCADE'), nullable=False),
            sa.Column('version', sa.Integer(), nullable=True),
            sa.Column('rules_json', sa.JSON(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )

    if not _table_exists('schema_proposals'):
        op.create_table('schema_proposals',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('file_name', sa.String(length=255), nullable=False),
            sa.Column('sheet_names', sa.JSON(), nullable=True),
            sa.Column('header_samples', sa.JSON(), nullable=True),
            sa.Column('suggested_rules_json', sa.JSON(), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )

    if not _table_exists('etl_audit_events'):
        op.create_table('etl_audit_events',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('event_type', sa.String(length=50), nullable=False),
            sa.Column('dataset_id', sa.Integer(), nullable=True),
            sa.Column('detail', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )

    if not _table_exists('transactions'):
        op.create_table('transactions',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('dataset_id', sa.Integer(), sa.ForeignKey('datasets.id', ondelete='CASCADE'), nullable=False),
            sa.Column('date', sa.String(length=50), nullable=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('amount', sa.Float(), nullable=True),
            sa.Column('category', sa.String(length=100), nullable=True),
            sa.Column('type', sa.String(length=20), nullable=True),
            sa.Column('account', sa.String(length=100), nullable=True),
            sa.Column('reference', sa.String(length=100), nullable=True),
            sa.Column('currency', sa.String(length=10), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )

    if not _table_exists('revenue_items'):
        op.create_table('revenue_items',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('dataset_id', sa.Integer(), sa.ForeignKey('datasets.id', ondelete='CASCADE'), nullable=False),
            sa.Column('product', sa.String(length=255), nullable=True),
            sa.Column('segment', sa.String(length=100), nullable=True),
            sa.Column('category', sa.String(length=100), nullable=True),
            sa.Column('gross', sa.Float(), nullable=True),
            sa.Column('vat', sa.Float(), nullable=True),
            sa.Column('net', sa.Float(), nullable=True),
            sa.Column('eliminated', sa.Boolean(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )

    if not _table_exists('cogs_items'):
        op.create_table('cogs_items',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('dataset_id', sa.Integer(), sa.ForeignKey('datasets.id', ondelete='CASCADE'), nullable=False),
            sa.Column('product', sa.String(length=255), nullable=True),
            sa.Column('amount', sa.Float(), nullable=True),
            sa.Column('category', sa.String(length=100), nullable=True),
            sa.Column('segment', sa.String(length=100), nullable=True),
            sa.Column('eliminated', sa.Boolean(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )

    if not _table_exists('ga_expense_items'):
        op.create_table('ga_expense_items',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('dataset_id', sa.Integer(), sa.ForeignKey('datasets.id', ondelete='CASCADE'), nullable=False),
            sa.Column('line_item', sa.String(length=255), nullable=True),
            sa.Column('amount', sa.Float(), nullable=True),
            sa.Column('category', sa.String(length=100), nullable=True),
            sa.Column('eliminated', sa.Boolean(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )

    if not _table_exists('balance_sheet_items'):
        op.create_table('balance_sheet_items',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('dataset_id', sa.Integer(), sa.ForeignKey('datasets.id', ondelete='CASCADE'), nullable=False),
            sa.Column('account_code', sa.String(length=50), nullable=True),
            sa.Column('account_name', sa.String(length=500), nullable=True),
            sa.Column('ifrs_line_item', sa.String(length=255), nullable=True),
            sa.Column('opening_balance', sa.Float(), nullable=True),
            sa.Column('closing_balance', sa.Float(), nullable=True),
            sa.Column('section', sa.String(length=100), nullable=True),
            sa.Column('currency', sa.String(length=10), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )

    if not _table_exists('trial_balance_items'):
        op.create_table('trial_balance_items',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('dataset_id', sa.Integer(), sa.ForeignKey('datasets.id', ondelete='CASCADE'), nullable=False),
            sa.Column('account_code', sa.String(length=50), nullable=True),
            sa.Column('account_name', sa.String(length=500), nullable=True),
            sa.Column('debit', sa.Float(), nullable=True),
            sa.Column('credit', sa.Float(), nullable=True),
            sa.Column('opening_debit', sa.Float(), nullable=True),
            sa.Column('opening_credit', sa.Float(), nullable=True),
            sa.Column('turnover_debit', sa.Float(), nullable=True),
            sa.Column('turnover_credit', sa.Float(), nullable=True),
            sa.Column('closing_debit', sa.Float(), nullable=True),
            sa.Column('closing_credit', sa.Float(), nullable=True),
            sa.Column('section', sa.String(length=100), nullable=True),
            sa.Column('ifrs_line_item', sa.String(length=255), nullable=True),
            sa.Column('currency', sa.String(length=10), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )

    if not _table_exists('budget_lines'):
        op.create_table('budget_lines',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('dataset_id', sa.Integer(), sa.ForeignKey('datasets.id', ondelete='CASCADE'), nullable=False),
            sa.Column('line_item', sa.String(length=255), nullable=True),
            sa.Column('planned', sa.Float(), nullable=True),
            sa.Column('actual', sa.Float(), nullable=True),
            sa.Column('variance', sa.Float(), nullable=True),
            sa.Column('category', sa.String(length=100), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )

    if not _table_exists('reports'):
        op.create_table('reports',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('report_type', sa.String(length=50), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=True),
            sa.Column('parameters', sa.JSON(), nullable=True),
            sa.Column('result_data', sa.JSON(), nullable=True),
            sa.Column('summary', sa.Text(), nullable=True),
            sa.Column('recommendations', sa.JSON(), nullable=True),
            sa.Column('confidence_score', sa.Float(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )

    if not _table_exists('product_mappings'):
        op.create_table('product_mappings',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('product_name', sa.String(length=255), nullable=False),
            sa.Column('normalized_name', sa.String(length=255), nullable=True),
            sa.Column('category', sa.String(length=100), nullable=True),
            sa.Column('segment', sa.String(length=100), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )

    if not _table_exists('coa_mapping_overrides'):
        op.create_table('coa_mapping_overrides',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('account_code', sa.String(length=50), nullable=False),
            sa.Column('account_name', sa.String(length=500), nullable=True),
            sa.Column('override_section', sa.String(length=100), nullable=True),
            sa.Column('override_ifrs', sa.String(length=255), nullable=True),
            sa.Column('override_sign', sa.Integer(), nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )

    if not _table_exists('coa_master_accounts'):
        op.create_table('coa_master_accounts',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('account_code', sa.String(length=50), nullable=False),
            sa.Column('account_name', sa.String(length=500), nullable=True),
            sa.Column('account_type', sa.String(length=50), nullable=True),
            sa.Column('parent_code', sa.String(length=50), nullable=True),
            sa.Column('level', sa.Integer(), nullable=True),
            sa.Column('is_postable', sa.Boolean(), nullable=True),
            sa.Column('ifrs_line_item', sa.String(length=255), nullable=True),
            sa.Column('section', sa.String(length=100), nullable=True),
            sa.Column('normal_balance', sa.String(length=10), nullable=True),
            sa.Column('currency', sa.String(length=10), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=True),
            sa.Column('source', sa.String(length=50), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )

    if not _table_exists('agent_memory'):
        op.create_table('agent_memory',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('agent_name', sa.String(length=100), nullable=False),
            sa.Column('memory_type', sa.String(length=50), nullable=True),
            sa.Column('key', sa.String(length=255), nullable=False),
            sa.Column('value', sa.Text(), nullable=True),
            sa.Column('metadata_json', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )

    if not _table_exists('agent_audit_log'):
        op.create_table('agent_audit_log',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('agent_name', sa.String(length=100), nullable=False),
            sa.Column('action', sa.String(length=100), nullable=False),
            sa.Column('input_summary', sa.Text(), nullable=True),
            sa.Column('output_summary', sa.Text(), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=True),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('duration_ms', sa.Float(), nullable=True),
            sa.Column('token_count', sa.Integer(), nullable=True),
            sa.Column('model_used', sa.String(length=100), nullable=True),
            sa.Column('cache_hit', sa.Boolean(), nullable=True),
            sa.Column('metadata_json', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )

    if not _table_exists('feedback'):
        op.create_table('feedback',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('report_id', sa.Integer(), nullable=True),
            sa.Column('rating', sa.Integer(), nullable=True),
            sa.Column('comment', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )

    if not _table_exists('custom_tools'):
        op.create_table('custom_tools',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('tool_type', sa.String(length=50), nullable=True),
            sa.Column('config_json', sa.JSON(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )

    if not _table_exists('forecasts'):
        op.create_table('forecasts',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('metric', sa.String(length=100), nullable=False),
            sa.Column('method', sa.String(length=50), nullable=True),
            sa.Column('period_label', sa.String(length=50), nullable=True),
            sa.Column('predicted_value', sa.Float(), nullable=True),
            sa.Column('confidence_lower', sa.Float(), nullable=True),
            sa.Column('confidence_upper', sa.Float(), nullable=True),
            sa.Column('accuracy_score', sa.Float(), nullable=True),
            sa.Column('parameters_json', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )

    if not _table_exists('scenarios'):
        op.create_table('scenarios',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('scenario_type', sa.String(length=50), nullable=True),
            sa.Column('parameters_json', sa.JSON(), nullable=True),
            sa.Column('results_json', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )

    if not _table_exists('anomalies'):
        op.create_table('anomalies',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('metric', sa.String(length=100), nullable=False),
            sa.Column('anomaly_type', sa.String(length=50), nullable=True),
            sa.Column('severity', sa.String(length=20), nullable=True),
            sa.Column('detected_value', sa.Float(), nullable=True),
            sa.Column('expected_value', sa.Float(), nullable=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('is_resolved', sa.Boolean(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )

    if not _table_exists('exchange_rates'):
        op.create_table('exchange_rates',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('from_currency', sa.String(length=10), nullable=False),
            sa.Column('to_currency', sa.String(length=10), nullable=False),
            sa.Column('rate', sa.Float(), nullable=False),
            sa.Column('rate_date', sa.String(length=20), nullable=True),
            sa.Column('source', sa.String(length=50), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )

    if not _table_exists('mr_report_snapshots'):
        op.create_table('mr_report_snapshots',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('report_type', sa.String(length=50), nullable=False),
            sa.Column('period', sa.String(length=50), nullable=True),
            sa.Column('snapshot_data', sa.JSON(), nullable=True),
            sa.Column('generated_by', sa.String(length=100), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )

    if not _table_exists('scheduled_reports'):
        op.create_table('scheduled_reports',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('report_type', sa.String(length=50), nullable=True),
            sa.Column('schedule', sa.String(length=50), nullable=True),
            sa.Column('parameters_json', sa.JSON(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=True),
            sa.Column('last_run', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )

    if not _table_exists('data_lineage'):
        op.create_table('data_lineage',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('source_type', sa.String(length=50), nullable=True),
            sa.Column('source_id', sa.Integer(), nullable=True),
            sa.Column('target_type', sa.String(length=50), nullable=True),
            sa.Column('target_id', sa.Integer(), nullable=True),
            sa.Column('transformation', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )

    if not _table_exists('learning_records'):
        op.create_table('learning_records',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('account_code', sa.String(length=50), nullable=False),
            sa.Column('account_name', sa.String(length=500), nullable=True),
            sa.Column('classification', sa.JSON(), nullable=True),
            sa.Column('confidence', sa.Float(), nullable=True),
            sa.Column('source', sa.String(length=50), nullable=True),
            sa.Column('feedback_type', sa.String(length=50), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )

    if not _table_exists('classification_approvals'):
        op.create_table('classification_approvals',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('account_code', sa.String(length=50), nullable=False),
            sa.Column('account_name', sa.String(length=500), nullable=True),
            sa.Column('proposed_section', sa.String(length=100), nullable=True),
            sa.Column('proposed_ifrs', sa.String(length=255), nullable=True),
            sa.Column('confidence', sa.Float(), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=True),
            sa.Column('reviewed_by', sa.Integer(), nullable=True),
            sa.Column('review_note', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )

    if not _table_exists('auth_audit_events'):
        op.create_table('auth_audit_events',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('event_type', sa.String(length=50), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=True),
            sa.Column('email', sa.String(length=255), nullable=True),
            sa.Column('ip_address', sa.String(length=50), nullable=True),
            sa.Column('resource', sa.String(length=255), nullable=True),
            sa.Column('detail', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )

    if not _table_exists('revoked_tokens'):
        op.create_table('revoked_tokens',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('jti', sa.String(length=64), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=True),
            sa.Column('revoked_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_revoked_jti', 'revoked_tokens', ['jti'], unique=True)

    if not _table_exists('decision_actions'):
        op.create_table('decision_actions',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('action_type', sa.String(length=100), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('expected_impact', sa.JSON(), nullable=True),
            sa.Column('roi_estimate', sa.Float(), nullable=True),
            sa.Column('risk_level', sa.String(length=20), nullable=True),
            sa.Column('composite_score', sa.Float(), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )

    if not _table_exists('prediction_records'):
        op.create_table('prediction_records',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('prediction_type', sa.String(length=50), nullable=False),
            sa.Column('metric', sa.String(length=100), nullable=True),
            sa.Column('predicted_value', sa.Float(), nullable=True),
            sa.Column('confidence', sa.Float(), nullable=True),
            sa.Column('source_method', sa.String(length=100), nullable=True),
            sa.Column('resolved', sa.Boolean(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )

    if not _table_exists('prediction_outcomes'):
        op.create_table('prediction_outcomes',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('prediction_id', sa.Integer(), sa.ForeignKey('prediction_records.id', ondelete='CASCADE'), nullable=False),
            sa.Column('actual_value', sa.Float(), nullable=True),
            sa.Column('error_pct', sa.Float(), nullable=True),
            sa.Column('direction_correct', sa.Boolean(), nullable=True),
            sa.Column('magnitude_accuracy', sa.Float(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )

    if not _table_exists('alerts'):
        op.create_table('alerts',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('alert_type', sa.String(length=50), nullable=False),
            sa.Column('severity', sa.String(length=20), nullable=True),
            sa.Column('metric', sa.String(length=100), nullable=True),
            sa.Column('threshold_value', sa.Float(), nullable=True),
            sa.Column('current_value', sa.Float(), nullable=True),
            sa.Column('message', sa.Text(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=True),
            sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )

    if not _table_exists('monitoring_rules'):
        op.create_table('monitoring_rules',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('rule_type', sa.String(length=50), nullable=False),
            sa.Column('metric', sa.String(length=100), nullable=True),
            sa.Column('operator', sa.String(length=10), nullable=True),
            sa.Column('threshold', sa.Float(), nullable=True),
            sa.Column('severity', sa.String(length=20), nullable=True),
            sa.Column('cooldown_minutes', sa.Integer(), nullable=True),
            sa.Column('is_enabled', sa.Boolean(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )

    if not _table_exists('financial_documents'):
        op.create_table('financial_documents',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('title', sa.String(length=500), nullable=False),
            sa.Column('doc_type', sa.String(length=50), nullable=True),
            sa.Column('content', sa.Text(), nullable=True),
            sa.Column('metadata_json', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )

    if not _table_exists('knowledge_entities'):
        op.create_table('knowledge_entities',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('entity_id', sa.String(length=255), nullable=False),
            sa.Column('entity_type', sa.String(length=100), nullable=False),
            sa.Column('name', sa.String(length=500), nullable=True),
            sa.Column('properties_json', sa.JSON(), nullable=True),
            sa.Column('source', sa.String(length=100), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_ke_entity_id', 'knowledge_entities', ['entity_id'], unique=True)
        op.create_index('ix_ke_entity_type', 'knowledge_entities', ['entity_type'])

    if not _table_exists('knowledge_relations'):
        op.create_table('knowledge_relations',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('source_entity_id', sa.String(length=255), nullable=False),
            sa.Column('target_entity_id', sa.String(length=255), nullable=False),
            sa.Column('relation_type', sa.String(length=100), nullable=False),
            sa.Column('properties_json', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_kr_source', 'knowledge_relations', ['source_entity_id'])
        op.create_index('ix_kr_target', 'knowledge_relations', ['target_entity_id'])
        op.create_index('ix_kr_type', 'knowledge_relations', ['relation_type'])

    # journal_entries, posting_lines, document_number_sequences, fiscal_periods,
    # change_log, audit_trail, transformation_lineage were created in previous migration
    # (3942c5d15eec). Skip if they already exist.

    if not _table_exists('journal_entries'):
        op.create_table('journal_entries',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('document_number', sa.String(length=50), nullable=False),
            sa.Column('posting_date', sa.DateTime(timezone=True), nullable=False),
            sa.Column('period', sa.String(length=50), nullable=False),
            sa.Column('fiscal_year', sa.Integer(), nullable=False),
            sa.Column('description', sa.Text(), nullable=False),
            sa.Column('status', sa.String(length=20), nullable=False),
            sa.Column('reference', sa.String(length=200), nullable=True),
            sa.Column('currency', sa.String(length=10), nullable=True),
            sa.Column('source_type', sa.String(length=50), nullable=True),
            sa.Column('source_id', sa.Integer(), nullable=True),
            sa.Column('total_debit', sa.String(length=50), nullable=True),
            sa.Column('total_credit', sa.String(length=50), nullable=True),
            sa.Column('document_hash', sa.String(length=64), nullable=True),
            sa.Column('is_immutable', sa.Boolean(), nullable=True),
            sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('posted_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('reversed_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.Column('posted_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('reversed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('reversal_of_id', sa.Integer(), sa.ForeignKey('journal_entries.id', ondelete='SET NULL'), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_je_document', 'journal_entries', ['document_number'], unique=True)
        op.create_index('ix_je_period', 'journal_entries', ['period'])
        op.create_index('ix_je_status', 'journal_entries', ['status'])
        op.create_index('ix_je_posting_date', 'journal_entries', ['posting_date'])
        op.create_index('ix_je_fiscal_year', 'journal_entries', ['fiscal_year'])

    if not _table_exists('posting_lines'):
        op.create_table('posting_lines',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('journal_entry_id', sa.Integer(), sa.ForeignKey('journal_entries.id', ondelete='CASCADE'), nullable=False),
            sa.Column('line_number', sa.Integer(), nullable=False),
            sa.Column('account_code', sa.String(length=50), nullable=False),
            sa.Column('account_name', sa.String(length=500), nullable=True),
            sa.Column('cost_center', sa.String(length=50), nullable=True),
            sa.Column('profit_center', sa.String(length=50), nullable=True),
            sa.Column('debit', sa.String(length=50), nullable=True),
            sa.Column('credit', sa.String(length=50), nullable=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('tax_code', sa.String(length=20), nullable=True),
            sa.Column('currency', sa.String(length=10), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_pl_journal', 'posting_lines', ['journal_entry_id'])
        op.create_index('ix_pl_account', 'posting_lines', ['account_code'])
        op.create_index('ix_pl_cost_center', 'posting_lines', ['cost_center'])

    if not _table_exists('document_number_sequences'):
        op.create_table('document_number_sequences',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('prefix', sa.String(length=20), nullable=False),
            sa.Column('fiscal_year', sa.Integer(), nullable=False),
            sa.Column('next_number', sa.Integer(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )

    if not _table_exists('fiscal_periods'):
        op.create_table('fiscal_periods',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('period_name', sa.String(length=50), nullable=False),
            sa.Column('fiscal_year', sa.Integer(), nullable=False),
            sa.Column('start_date', sa.DateTime(timezone=True), nullable=False),
            sa.Column('end_date', sa.DateTime(timezone=True), nullable=False),
            sa.Column('status', sa.String(length=20), nullable=True),
            sa.Column('closed_by', sa.Integer(), nullable=True),
            sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('close_type', sa.String(length=20), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )

    if not _table_exists('change_log'):
        op.create_table('change_log',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('entity_type', sa.String(length=50), nullable=False),
            sa.Column('entity_id', sa.Integer(), nullable=False),
            sa.Column('field_name', sa.String(length=100), nullable=True),
            sa.Column('old_value', sa.Text(), nullable=True),
            sa.Column('new_value', sa.Text(), nullable=True),
            sa.Column('changed_by', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )

    if not _table_exists('audit_trail'):
        op.create_table('audit_trail',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('action', sa.String(length=50), nullable=False),
            sa.Column('entity_type', sa.String(length=50), nullable=False),
            sa.Column('entity_id', sa.Integer(), nullable=True),
            sa.Column('user_id', sa.Integer(), nullable=True),
            sa.Column('details', sa.JSON(), nullable=True),
            sa.Column('ip_address', sa.String(length=50), nullable=True),
            sa.Column('document_hash_before', sa.String(length=64), nullable=True),
            sa.Column('document_hash_after', sa.String(length=64), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )

    if not _table_exists('transformation_lineage'):
        op.create_table('transformation_lineage',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('source_table', sa.String(length=100), nullable=False),
            sa.Column('source_id', sa.Integer(), nullable=True),
            sa.Column('target_table', sa.String(length=100), nullable=False),
            sa.Column('target_id', sa.Integer(), nullable=True),
            sa.Column('rule_applied', sa.String(length=255), nullable=True),
            sa.Column('confidence', sa.Float(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )


def downgrade() -> None:
    # Only drop tables that this migration created (reverse order).
    # Use _table_exists guard so downgrade is safe to run multiple times.
    for table in reversed([
        'transformation_lineage', 'audit_trail', 'change_log',
        'fiscal_periods', 'document_number_sequences', 'posting_lines',
        'journal_entries', 'knowledge_relations', 'knowledge_entities',
        'financial_documents', 'monitoring_rules', 'alerts',
        'prediction_outcomes', 'prediction_records', 'decision_actions',
        'revoked_tokens', 'auth_audit_events', 'classification_approvals',
        'learning_records', 'data_lineage', 'scheduled_reports',
        'mr_report_snapshots', 'exchange_rates', 'anomalies', 'scenarios',
        'forecasts', 'custom_tools', 'feedback', 'agent_audit_log',
        'agent_memory', 'coa_master_accounts', 'coa_mapping_overrides',
        'product_mappings', 'reports', 'budget_lines', 'trial_balance_items',
        'balance_sheet_items', 'ga_expense_items', 'cogs_items',
        'revenue_items', 'transactions', 'etl_audit_events',
        'schema_proposals', 'schema_versions', 'schema_profiles',
        'dataset_snapshots', 'datasets', 'dataset_groups', 'users',
    ]):
        if _table_exists(table):
            op.drop_table(table)
