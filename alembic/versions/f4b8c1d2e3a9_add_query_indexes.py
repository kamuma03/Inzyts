"""Add indexes for hot query paths (job mode, previous-job lookup, conversation history)

Revision ID: f4b8c1d2e3a9
Revises: e3f4a5b6c7d8
Create Date: 2026-06-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f4b8c1d2e3a9"
down_revision: Union[str, Sequence[str], None] = "e3f4a5b6c7d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Job.mode is filtered in the previous-job lookup and mode dashboards.
    op.create_index(op.f("ix_jobs_mode"), "jobs", ["mode"], unique=False)
    # Composite covering execution_task's previous-comparable-job query.
    op.create_index(
        "ix_jobs_prev_lookup",
        "jobs",
        ["user_id", "csv_hash", "mode", "status"],
        unique=False,
    )
    # Conversation history is loaded WHERE job_id = ? ORDER BY created_at.
    op.create_index(
        op.f("ix_conversation_messages_created_at"),
        "conversation_messages",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_conversation_messages_job_created",
        "conversation_messages",
        ["job_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_conversation_messages_job_created", table_name="conversation_messages")
    op.drop_index(op.f("ix_conversation_messages_created_at"), table_name="conversation_messages")
    op.drop_index("ix_jobs_prev_lookup", table_name="jobs")
    op.drop_index(op.f("ix_jobs_mode"), table_name="jobs")
