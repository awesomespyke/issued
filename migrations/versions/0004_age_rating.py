"""Add age_rating to comic metadata

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | None = None
depends_on: str | None = None


def _column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    rows = conn.execute(sa.text(f"PRAGMA table_info({table})"))
    return any(row[1] == column for row in rows)


def upgrade() -> None:
    if not _column_exists("metadata", "age_rating"):
        op.add_column(
            "metadata",
            sa.Column("age_rating", sa.String(), nullable=True),
        )


def downgrade() -> None:
    if _column_exists("metadata", "age_rating"):
        op.drop_column("metadata", "age_rating")
