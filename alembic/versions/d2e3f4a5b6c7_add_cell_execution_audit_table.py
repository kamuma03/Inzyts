"""add cell_execution_audit table

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-04-27 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2e3f4a5b6c7'
down_revision: Union[str, Sequence[str], None] = 'c1d2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'cell_execution_audit',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('job_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=True),
        sa.Column('code_hash', sa.String(length=64), nullable=False),
        sa.Column('code_length', sa.Integer(), nullable=False),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('error_name', sa.String(), nullable=True),
        sa.Column('killed_reason', sa.String(), nullable=True),
        sa.Column('policy_name', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id']),
    )
    op.create_index('ix_cell_execution_audit_timestamp', 'cell_execution_audit', ['timestamp'])
    op.create_index('ix_cell_execution_audit_job_id', 'cell_execution_audit', ['job_id'])
    op.create_index('ix_cell_execution_audit_user_id', 'cell_execution_audit', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_cell_execution_audit_user_id', table_name='cell_execution_audit')
    op.drop_index('ix_cell_execution_audit_job_id', table_name='cell_execution_audit')
    op.drop_index('ix_cell_execution_audit_timestamp', table_name='cell_execution_audit')
    op.drop_table('cell_execution_audit')
