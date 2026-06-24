"""update persona/instruction prompts and clear th translation cache

Revision ID: 004
Revises: 003
Create Date: 2026-06-24

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_SYSTEM_SENTENCE = "Translate Chinese to English. "
NEW_SYSTEM_SENTENCE = "Translate the source text into the target language specified in each request. "

NEW_INSTRUCTION_PROMPT = (
    "Use standard aviation and UAV terminology consistently in the target language. "
    "Examples of domain terms in English sources include airframe, flight controller, "
    "ground control station, gimbal, payload, telemetry, waypoint, RTL, geofence, "
    "ESC, IMU, and GNSS/RTK — translate these into equivalent terms in the target "
    "language while keeping acronyms as appropriate. "
    "Keep acronyms, model numbers, part numbers, units, and numeric values "
    "exactly as in the source; do not convert units. "
    "Preserve document structure: headings, lists, table layout, and "
    "WARNING / CAUTION / NOTE labels in uppercase. "
    "Translate the same source term the same way throughout. "
    "If a term is ambiguous, prefer the meaning standard in aviation "
    "maintenance and operation manuals. "
    "Respond with the 2 translation options only; never add analysis, "
    "breakdowns, summaries, or transcriptions."
)

NEW_PERSONA_PROMPT = (
    "Write in the target language using a formal, precise, and concise "
    "technical-manual style. "
    "Use imperative mood for procedures and instructions. "
    "Avoid colloquial language and embellishment. "
    "Your entire reply must consist of only the 2 translation options."
)

OLD_INSTRUCTION_MARKER = "(e.g. airframe, flight controller"
OLD_PERSONA_MARKER = "Check the propeller"


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE llm_translate.prompts "
            "SET content = REPLACE(content, :old, :new), updated_at = NOW() "
            "WHERE prompt_type = 'system' AND content LIKE :pattern"
        ).bindparams(
            old=OLD_SYSTEM_SENTENCE,
            new=NEW_SYSTEM_SENTENCE,
            pattern=f"%{OLD_SYSTEM_SENTENCE}%",
        )
    )
    op.execute(
        sa.text(
            "UPDATE llm_translate.prompts "
            "SET content = :new_content, updated_at = NOW() "
            "WHERE prompt_type = 'instruction' AND content LIKE :pattern"
        ).bindparams(new_content=NEW_INSTRUCTION_PROMPT, pattern=f"%{OLD_INSTRUCTION_MARKER}%")
    )
    op.execute(
        sa.text(
            "UPDATE llm_translate.prompts "
            "SET content = :new_content, updated_at = NOW() "
            "WHERE prompt_type = 'persona' AND content LIKE :pattern"
        ).bindparams(new_content=NEW_PERSONA_PROMPT, pattern=f"%{OLD_PERSONA_MARKER}%")
    )
    op.execute(
        sa.text("DELETE FROM llm_translate.translation_cache WHERE target_lang = 'th'")
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE llm_translate.prompts "
            "SET content = REPLACE(content, :new, :old), updated_at = NOW() "
            "WHERE prompt_type = 'system' AND content LIKE :pattern"
        ).bindparams(
            old=OLD_SYSTEM_SENTENCE,
            new=NEW_SYSTEM_SENTENCE,
            pattern=f"%{NEW_SYSTEM_SENTENCE}%",
        )
    )
