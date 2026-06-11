-- =============================================================================
-- LLM Translate — Database initialization script
-- PostgreSQL 16+
--
-- เหมาะสำหรับเริ่มต้นระบบใหม่ — PostgreSQL ว่าง ยังไม่มี schema llm_translate
-- สร้าง schema, ตาราง, และ stamp Alembic version (เทียบเท่า migration 001 + 002)
--
-- ไม่เหมาะสำหรับระบบที่มีข้อมูลอยู่แล้ว → ใช้ `alembic upgrade head` แทน
--
-- ค่า default ตรงกับ docker-compose.yml และ .env.example:
--   User:     llm_user
--   Password: llm_pass
--   Database: llm_translate_db
--   Schema:   llm_translate
--
-- เริ่มต้นระบบใหม่ (2 ขั้นตอน):
--
--   ขั้นที่ 1 — สร้าง user และ database (รันครั้งเดียว ในฐาน postgres):
--     psql -U postgres -c "CREATE USER llm_user WITH PASSWORD 'llm_pass';"
--     psql -U postgres -c "CREATE DATABASE llm_translate_db OWNER llm_user ENCODING 'UTF8';"
--
--   ขั้นที่ 2 — สร้าง schema และตาราง:
--     psql -U postgres -d llm_translate_db -f Docs/init.sql
--
-- หลังรันเสร็จ ตั้ง DATABASE_URL ใน .env แล้ว start app ได้เลย
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Database & User
--    (รันคำสั่งในขั้นที่ 1 ด้านบนแทน — ไม่รวมในไฟล์นี้เพราะต้อง connect คนละ database)
-- -----------------------------------------------------------------------------

-- -----------------------------------------------------------------------------
-- 2. Schema
-- -----------------------------------------------------------------------------

CREATE SCHEMA IF NOT EXISTS llm_translate;

-- -----------------------------------------------------------------------------
-- 3. Tables
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS llm_translate.conversations (
    id                  UUID PRIMARY KEY,
    title               VARCHAR(255),
    default_source_lang VARCHAR(2)  NOT NULL DEFAULT 'zh',
    default_target_lang VARCHAR(2)  NOT NULL DEFAULT 'en',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS llm_translate.messages (
    id                  UUID PRIMARY KEY,
    conversation_id     UUID        NOT NULL
        REFERENCES llm_translate.conversations (id) ON DELETE CASCADE,
    role                VARCHAR     NOT NULL,   -- user | assistant
    content             TEXT        NOT NULL,
    source_lang         VARCHAR(2)  NOT NULL,
    target_lang         VARCHAR(2)  NOT NULL,
    detail_level        VARCHAR(16) NOT NULL DEFAULT 'normal',  -- migration 002
    tokens_in           INTEGER     NOT NULL DEFAULT 0,
    tokens_out          INTEGER     NOT NULL DEFAULT 0,
    latency_ms          INTEGER     NOT NULL DEFAULT 0,
    tokens_per_sec_in   DOUBLE PRECISION NOT NULL DEFAULT 0,
    tokens_per_sec_out  DOUBLE PRECISION NOT NULL DEFAULT 0,
    from_cache          BOOLEAN     NOT NULL DEFAULT false,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_messages_conversation_id
    ON llm_translate.messages (conversation_id);

CREATE TABLE IF NOT EXISTS llm_translate.translation_cache (
    id              UUID PRIMARY KEY,
    source_text     TEXT        NOT NULL,
    source_lang     VARCHAR(2)  NOT NULL,
    target_lang     VARCHAR(2)  NOT NULL,
    translated_text TEXT        NOT NULL,
    hit_count       INTEGER     NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_used_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_translation_cache_lookup
        UNIQUE (source_text, source_lang, target_lang)
);

CREATE TABLE IF NOT EXISTS llm_translate.prompts (
    id          UUID PRIMARY KEY,
    prompt_type VARCHAR NOT NULL UNIQUE,   -- system | instruction | persona
    content     TEXT    NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS llm_translate.app_config (
    key   VARCHAR(128) PRIMARY KEY,
    value TEXT NOT NULL
);

-- -----------------------------------------------------------------------------
-- 4. Alembic version (ให้ app รู้ว่า migration ถึง head แล้ว)
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS llm_translate.alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

INSERT INTO llm_translate.alembic_version (version_num)
VALUES ('002')
ON CONFLICT (version_num) DO NOTHING;

-- -----------------------------------------------------------------------------
-- 5. Permissions (สำหรับ user llm_user — รัน init.sql ด้วย postgres แล้ว grant ให้ app user)
-- -----------------------------------------------------------------------------

GRANT USAGE ON SCHEMA llm_translate TO llm_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA llm_translate TO llm_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA llm_translate
    GRANT ALL ON TABLES TO llm_user;
