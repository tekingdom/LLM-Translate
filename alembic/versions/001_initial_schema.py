"""initial schema llm_translate

Revision ID: 001
Revises:
Create Date: 2026-06-10

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS llm_translate")

    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("default_source_lang", sa.String(2), nullable=False, server_default="zh"),
        sa.Column("default_target_lang", sa.String(2), nullable=False, server_default="en"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="llm_translate",
    )

    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("llm_translate.conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.Enum("user", "assistant", name="message_role", native_enum=False), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_lang", sa.String(2), nullable=False),
        sa.Column("target_lang", sa.String(2), nullable=False),
        sa.Column("tokens_in", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_per_sec_in", sa.Float(), nullable=False, server_default="0"),
        sa.Column("tokens_per_sec_out", sa.Float(), nullable=False, server_default="0"),
        sa.Column("from_cache", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="llm_translate",
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"], schema="llm_translate")

    op.create_table(
        "translation_cache",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("source_lang", sa.String(2), nullable=False),
        sa.Column("target_lang", sa.String(2), nullable=False),
        sa.Column("translated_text", sa.Text(), nullable=False),
        sa.Column("hit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("source_text", "source_lang", "target_lang", name="uq_translation_cache_lookup"),
        schema="llm_translate",
    )

    op.create_table(
        "prompts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("prompt_type", sa.Enum("system", "instruction", "persona", name="prompt_type", native_enum=False), nullable=False, unique=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="llm_translate",
    )

    op.create_table(
        "app_config",
        sa.Column("key", sa.String(128), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        schema="llm_translate",
    )


def downgrade() -> None:
    op.drop_table("app_config", schema="llm_translate")
    op.drop_table("prompts", schema="llm_translate")
    op.drop_table("translation_cache", schema="llm_translate")
    op.drop_index("ix_messages_conversation_id", table_name="messages", schema="llm_translate")
    op.drop_table("messages", schema="llm_translate")
    op.drop_table("conversations", schema="llm_translate")
    op.execute("DROP SCHEMA IF EXISTS llm_translate CASCADE")
