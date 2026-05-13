"""Add game session data blob

Revision ID: 2d8a1c3b0f4e
Revises: 899d1db911e6
Create Date: 2026-05-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "2d8a1c3b0f4e"
down_revision: Union[str, Sequence[str], None] = "899d1db911e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "game_sessions",
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.alter_column("game_sessions", "data", server_default=None)


def downgrade() -> None:
    op.drop_column("game_sessions", "data")
