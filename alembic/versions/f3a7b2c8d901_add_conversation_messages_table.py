"""Add conversation_messages table

Revision ID: f3a7b2c8d901
Revises: 01a999b9017e
Create Date: 2026-02-26 10:34:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3a7b2c8d901'
down_revision: Union[str, Sequence[str], None] = '01a999b9017e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create conversation_messages table for persistent follow-up history."""
    op.create_table('conversation_messages',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('job_id', sa.String(), nullable=False),
    sa.Column('role', sa.String(), nullable=False),
    sa.Column('content', sa.String(), nullable=False),
    sa.Column('cells', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_conversation_messages_job_id'), 'conversation_messages', ['job_id'], unique=False)


def downgrade() -> None:
    """Drop conversation_messages table."""
    op.drop_index(op.f('ix_conversation_messages_job_id'), table_name='conversation_messages')
    op.drop_table('conversation_messages')
