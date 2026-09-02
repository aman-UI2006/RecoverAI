"""Add ltv_score to customers and generated_message_text to recovery_attempts.

Revision ID: 002_add_ltv_generated_message
Revises: 001_initial_schema
Create Date: 2026-09-01 19:31:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '002_add_ltv_generated_message'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('customers', sa.Column('ltv_score', sa.Float(), nullable=True))
    op.add_column('recovery_attempts', sa.Column('generated_message_text', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('recovery_attempts', 'generated_message_text')
    op.drop_column('customers', 'ltv_score')
