"""lowercase userrole enum values (idempotent)

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-05-11 09:50:00.000000

Older releases of this project shipped a migration that created the
``userrole`` Postgres enum with uppercase labels (``ADMIN``, ``ANALYST``,
``VIEWER``). The current code expects lowercase labels (matching
``UserRole.*.value``) — fresh installs already get lowercase, but anyone
with a pre-existing volume from the older migration ends up with the
SQLAlchemy read-path failing with::

    LookupError: 'ADMIN' is not among the defined enum values.
    Possible values: admin, analyst, viewer

``ALTER TYPE ... RENAME VALUE`` (PostgreSQL 10+) rewrites the enum
labels in place — existing rows are updated transparently, no row-by-row
UPDATE required. The migration checks each label first so it's safe to
run against a DB that already has the lowercase form.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'e3f4a5b6c7d8'
down_revision: Union[str, Sequence[str], None] = 'd2e3f4a5b6c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_RENAMES = (
    ("ADMIN", "admin"),
    ("ANALYST", "analyst"),
    ("VIEWER", "viewer"),
)


def upgrade() -> None:
    bind = op.get_bind()
    for old, new in _RENAMES:
        exists = bind.execute(
            _exists_sql(), {"label": old}
        ).scalar()
        if exists:
            op.execute(
                f"ALTER TYPE userrole RENAME VALUE '{old}' TO '{new}'"
            )


def downgrade() -> None:
    bind = op.get_bind()
    for old, new in _RENAMES:
        exists = bind.execute(
            _exists_sql(), {"label": new}
        ).scalar()
        if exists:
            op.execute(
                f"ALTER TYPE userrole RENAME VALUE '{new}' TO '{old}'"
            )


def _exists_sql():
    from sqlalchemy import text
    return text(
        "SELECT EXISTS ("
        "  SELECT 1 FROM pg_enum e "
        "  JOIN pg_type t ON e.enumtypid = t.oid "
        "  WHERE t.typname = 'userrole' AND e.enumlabel = :label"
        ")"
    )
