"""add message detail_level

Revision ID: 002
Revises: 001
Create Date: 2026-06-11

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column("detail_level", sa.String(16), nullable=False, server_default="normal"),
        schema="llm_translate",
    )


def downgrade() -> None:
    op.drop_column("messages", "detail_level", schema="llm_translate")
