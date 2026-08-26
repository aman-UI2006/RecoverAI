"""Initial schema migration: 13 core relational tables.

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-08-26 10:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. merchants
    op.create_table(
        'merchants',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('industry', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # 2. customers
    op.create_table(
        'customers',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('merchant_id', sa.String(length=36), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('historical_success_rate', sa.Float(), nullable=True),
        sa.Column('historical_transaction_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['merchant_id'], ['merchants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('merchant_id', 'email', name='uk_merchant_customer_email')
    )

    # 3. transactions
    op.create_table(
        'transactions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('merchant_id', sa.String(length=36), nullable=False),
        sa.Column('customer_id', sa.String(length=36), nullable=False),
        sa.Column('razorpay_payment_id', sa.String(length=100), nullable=True),
        sa.Column('razorpay_order_id', sa.String(length=100), nullable=True),
        sa.Column('razorpay_payment_link_id', sa.String(length=100), nullable=True),
        sa.Column('razorpay_subscription_id', sa.String(length=100), nullable=True),
        sa.Column('razorpay_invoice_id', sa.String(length=100), nullable=True),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=10), nullable=False, server_default='INR'),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('scenario_type', sa.String(length=50), nullable=False),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('recovery_cycle', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('mode', sa.String(length=20), nullable=False, server_default='SIMULATION'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id']),
        sa.ForeignKeyConstraint(['merchant_id'], ['merchants.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_transactions_status', 'transactions', ['status'], unique=False)
    op.create_index('idx_transactions_mode', 'transactions', ['mode'], unique=False)

    # 4. events
    op.create_table(
        'events',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('transaction_id', sa.String(length=36), nullable=True),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('event_source', sa.String(length=100), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('idempotency_key', sa.String(length=255), nullable=False),
        sa.Column('razorpay_event_id', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['transaction_id'], ['transactions.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('idempotency_key'),
        sa.UniqueConstraint('razorpay_event_id')
    )
    op.create_index('idx_events_idempotency', 'events', ['idempotency_key'], unique=False)

    # 5. decision_contexts
    op.create_table(
        'decision_contexts',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('transaction_id', sa.String(length=36), nullable=False),
        sa.Column('model_version', sa.String(length=50), nullable=False),
        sa.Column('feature_version', sa.String(length=50), nullable=False),
        sa.Column('policy_version', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['transaction_id'], ['transactions.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # 6. recovery_action_scores
    op.create_table(
        'recovery_action_scores',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('decision_context_id', sa.String(length=36), nullable=False),
        sa.Column('transaction_id', sa.String(length=36), nullable=False),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('recovery_probability', sa.Float(), nullable=False),
        sa.Column('expected_gross_recovery', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('intervention_cost', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('expected_net_recovery_value', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['decision_context_id'], ['decision_contexts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['transaction_id'], ['transactions.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('decision_context_id', 'action', name='uk_decision_action')
    )

    # 7. diagnoses
    op.create_table(
        'diagnoses',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('transaction_id', sa.String(length=36), nullable=False),
        sa.Column('failure_code', sa.String(length=100), nullable=False),
        sa.Column('failure_category', sa.String(length=100), nullable=False),
        sa.Column('root_cause_explanation', sa.Text(), nullable=False),
        sa.Column('confidence_score', sa.Float(), nullable=False),
        sa.Column('diagnosis_source', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['transaction_id'], ['transactions.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # 8. policies
    op.create_table(
        'policies',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('merchant_id', sa.String(length=36), nullable=True),
        sa.Column('policy_version', sa.String(length=50), nullable=False, server_default='v1.0'),
        sa.Column('max_recovery_attempts', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('max_auto_action_amount', sa.Numeric(precision=12, scale=2), nullable=False, server_default='50000.00'),
        sa.Column('min_recovery_probability', sa.Float(), nullable=False, server_default='0.15'),
        sa.Column('cooldown_hours', sa.Integer(), nullable=False, server_default='24'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['merchant_id'], ['merchants.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # 9. recovery_attempts
    op.create_table(
        'recovery_attempts',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('transaction_id', sa.String(length=36), nullable=False),
        sa.Column('decision_context_id', sa.String(length=36), nullable=True),
        sa.Column('logical_operation_key', sa.String(length=255), nullable=False),
        sa.Column('recommended_action', sa.String(length=100), nullable=False),
        sa.Column('action_payload', sa.JSON(), nullable=False),
        sa.Column('policy_status', sa.String(length=50), nullable=False),
        sa.Column('policy_reason', sa.Text(), nullable=True),
        sa.Column('policy_version', sa.String(length=50), nullable=False),
        sa.Column('execution_status', sa.String(length=50), nullable=False),
        sa.Column('external_resource_type', sa.String(length=50), nullable=False),
        sa.Column('external_resource_id', sa.String(length=100), nullable=True),
        sa.Column('razorpay_payment_link_id', sa.String(length=100), nullable=True),
        sa.Column('razorpay_reference_id', sa.String(length=100), nullable=True),
        sa.Column('executed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['decision_context_id'], ['decision_contexts.id']),
        sa.ForeignKeyConstraint(['transaction_id'], ['transactions.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('logical_operation_key')
    )

    # 10. recovery_attributions
    op.create_table(
        'recovery_attributions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('transaction_id', sa.String(length=36), nullable=False),
        sa.Column('recovery_attempt_id', sa.String(length=36), nullable=True),
        sa.Column('recovery_source', sa.String(length=50), nullable=False),
        sa.Column('attribution_status', sa.String(length=50), nullable=False),
        sa.Column('attribution_method', sa.String(length=50), nullable=False),
        sa.Column('attribution_window_minutes', sa.Integer(), nullable=False, server_default='1440'),
        sa.Column('recovered_amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('refunded_amount', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
        sa.Column('intervention_timestamp', sa.DateTime(timezone=True), nullable=True),
        sa.Column('recovery_timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['recovery_attempt_id'], ['recovery_attempts.id']),
        sa.ForeignKeyConstraint(['transaction_id'], ['transactions.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('transaction_id', 'recovery_attempt_id', name='uk_tx_attempt_attribution')
    )

    # 11. audit_events
    op.create_table(
        'audit_events',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('transaction_id', sa.String(length=36), nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('actor', sa.String(length=100), nullable=False),
        sa.Column('state_from', sa.String(length=50), nullable=True),
        sa.Column('state_to', sa.String(length=50), nullable=True),
        sa.Column('details', sa.JSON(), nullable=False),
        sa.Column('previous_hash', sa.String(length=64), nullable=False),
        sa.Column('event_hash', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['transaction_id'], ['transactions.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_audit_tx_hash', 'audit_events', ['transaction_id', 'event_hash'], unique=False)

    # 12. evaluation_runs
    op.create_table(
        'evaluation_runs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('run_name', sa.String(length=255), nullable=False),
        sa.Column('dataset_version', sa.String(length=50), nullable=False),
        sa.Column('dataset_size', sa.Integer(), nullable=False),
        sa.Column('random_seed', sa.Integer(), nullable=False, server_default='42'),
        sa.Column('model_version', sa.String(length=50), nullable=False),
        sa.Column('feature_version', sa.String(length=50), nullable=False),
        sa.Column('policy_version', sa.String(length=50), nullable=False),
        sa.Column('configuration_version', sa.String(length=50), nullable=False),
        sa.Column('code_commit_sha', sa.String(length=100), nullable=True),
        sa.Column('mode', sa.String(length=20), nullable=False, server_default='SIMULATION'),
        sa.Column('revenue_at_risk', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('baseline_recovered_amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('recoverai_gross_recovered_amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('incremental_recovered_amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('baseline_recovery_rate', sa.Float(), nullable=False),
        sa.Column('recoverai_recovery_rate', sa.Float(), nullable=False),
        sa.Column('summary_metrics', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # 13. human_reviews
    op.create_table(
        'human_reviews',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('transaction_id', sa.String(length=36), nullable=False),
        sa.Column('reviewer_id', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='PENDING'),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('decision', sa.String(length=100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['transaction_id'], ['transactions.id']),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('human_reviews')
    op.drop_table('evaluation_runs')
    op.drop_index('idx_audit_tx_hash', table_name='audit_events')
    op.drop_table('audit_events')
    op.drop_table('recovery_attributions')
    op.drop_table('recovery_attempts')
    op.drop_table('policies')
    op.drop_table('diagnoses')
    op.drop_table('recovery_action_scores')
    op.drop_table('decision_contexts')
    op.drop_index('idx_events_idempotency', table_name='events')
    op.drop_table('events')
    op.drop_index('idx_transactions_mode', table_name='transactions')
    op.drop_index('idx_transactions_status', table_name='transactions')
    op.drop_table('transactions')
    op.drop_table('customers')
    op.drop_table('merchants')
