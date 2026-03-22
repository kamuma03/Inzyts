"""add user_id to jobs

Revision ID: a1b2c3d4e5f6
Revises: 4e69b3cf3724
Create Date: 2026-03-21 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '4e69b3cf3724'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('jobs', sa.Column('user_id', sa.String(), nullable=True))
    op.create_index(op.f('ix_jobs_user_id'), 'jobs', ['user_id'], unique=False)
    op.create_foreign_key('fk_jobs_user_id_users', 'jobs', 'users', ['user_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint('fk_jobs_user_id_users', 'jobs', type_='foreignkey')
    op.drop_index(op.f('ix_jobs_user_id'), table_name='jobs')
    op.drop_column('jobs', 'user_id')
