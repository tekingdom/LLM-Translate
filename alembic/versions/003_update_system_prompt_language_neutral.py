"""update system prompt to be language neutral

Revision ID: 003
Revises: 002
Create Date: 2026-06-11

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_SENTENCE = "Translate Chinese to English. "
NEW_SENTENCE = "Translate the source text into the target language specified in each request. "


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE llm_translate.prompts "
            "SET content = REPLACE(content, :old, :new), updated_at = NOW() "
            "WHERE prompt_type = 'system' AND content LIKE :pattern"
        ).bindparams(old=OLD_SENTENCE, new=NEW_SENTENCE, pattern=f"%{OLD_SENTENCE}%")
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE llm_translate.prompts "
            "SET content = REPLACE(content, :new, :old), updated_at = NOW() "
            "WHERE prompt_type = 'system' AND content LIKE :pattern"
        ).bindparams(old=OLD_SENTENCE, new=NEW_SENTENCE, pattern=f"%{NEW_SENTENCE}%")
    )
