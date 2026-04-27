"""add csv_hash and cost_breakdown to jobs

Revision ID: c1d2e3f4a5b6
Revises: b2c3d4e5f6a7
Create Date: 2026-04-27 13:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('jobs', sa.Column('csv_hash', sa.String(length=64), nullable=True))
    op.create_index('ix_jobs_csv_hash', 'jobs', ['csv_hash'])
    op.add_column('jobs', sa.Column('cost_breakdown', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('jobs', 'cost_breakdown')
    op.drop_index('ix_jobs_csv_hash', table_name='jobs')
    op.drop_column('jobs', 'csv_hash')
