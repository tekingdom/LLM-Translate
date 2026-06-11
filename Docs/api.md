# LLM Translate — API Reference

คู่มือ REST API และ SSE streaming สำหรับ LLM Translate

**Base URL:** `http://localhost:8000` (หรือตาม `APP_PORT` ใน `.env`)

**Interactive docs:** `GET /docs` (Swagger UI)

---

## ทั่วไป

| รายการ | ค่า |
|--------|-----|
| Content-Type (JSON) | `application/json` |
| Validation error | **422** Unprocessable Entity (FastAPI standard) |
| Path params (UUID) | รูปแบบ UUID v4 |
| Authentication | ไม่มี — public API |

---

## Schemas

### MessageCreate

```json
{
  "content": "string (1–32000 chars)",
  "source_lang": "en | zh | th",
  "target_lang": "en | zh | th",
  "detail_level": "normal | short | detailed"
}
```

`detail_level` default: `"normal"`

### MessageResponse

```json
{
  "id": "uuid",
  "conversation_id": "uuid",
  "role": "user | assistant",
  "content": "string",
  "source_lang": "en | zh | th",
  "target_lang": "en | zh | th",
  "detail_level": "normal | short | detailed",
  "tokens_in": 0,
  "tokens_out": 0,
  "latency_ms": 0,
  "tokens_per_sec_in": 0.0,
  "tokens_per_sec_out": 0.0,
  "from_cache": false,
  "created_at": "2026-06-11T00:00:00Z"
}
```

### TranslateResponse

```json
{
  "user_message": { "...MessageResponse" },
  "assistant_message": { "...MessageResponse" }
}
```

### ConversationCreate

```json
{
  "title": "string | null",
  "default_source_lang": "zh",
  "default_target_lang": "en"
}
```

### ConversationUpdate

```json
{
  "title": "string | null",
  "default_source_lang": "en | zh | th | null",
  "default_target_lang": "en | zh | th | null"
}
```

ทุก field เป็น optional — ส่งเฉพาะ field ที่ต้องการเปลี่ยน

### ConversationResponse

```json
{
  "id": "uuid",
  "title": "string | null",
  "default_source_lang": "zh",
  "default_target_lang": "en",
  "created_at": "2026-06-11T00:00:00Z",
  "updated_at": "2026-06-11T00:00:00Z"
}
```

### ConversationWithMessages

`ConversationResponse` + `"messages": [MessageResponse, ...]`

### PromptResponse

```json
{
  "prompt_type": "system | instruction | persona",
  "content": "string",
  "updated_at": "2026-06-11T00:00:00Z"
}
```

### PromptUpdate

```json
{
  "content": "string (min 1 char)"
}
```

### CacheEntryResponse

```json
{
  "id": "uuid",
  "source_text": "string",
  "source_lang": "en | zh | th",
  "target_lang": "en | zh | th",
  "translated_text": "string",
  "hit_count": 0,
  "created_at": "2026-06-11T00:00:00Z",
  "last_used_at": "2026-06-11T00:00:00Z"
}
```

### StatsResponse

```json
{
  "total_messages": 0,
  "total_tokens_in": 0,
  "total_tokens_out": 0,
  "cache_hits": 0,
  "cache_total": 0,
  "cache_hit_rate": 0.0
}
```

`cache_hit_rate` เป็นเปอร์เซ็นต์ (0–100) นับจาก assistant messages เท่านั้น

### AppConfigResponse / AppConfigUpdate

```json
{ "key": "string", "value": "string" }
```

Update body: `{ "value": "string" }` (min length 0)

---

## Health

### GET /health/live

Liveness probe

**Response 200:**
```json
{ "status": "ok" }
```

---

### GET /health/ready

Readiness probe — ตรวจ database และ LLM

**Response 200:**
```json
{
  "status": "ready",
  "checks": {
    "database": "ok",
    "llm": "ok"
  }
}
```

**Response 503:**
```json
{
  "status": "not_ready",
  "checks": {
    "database": "ok | error",
    "llm": "ok | error"
  }
}
```

---

## Conversations

Prefix: `/api/conversations`

### GET /api/conversations

รายการสนทนา (เรียง `updated_at` desc)

**Query params:**

| Param | Type | Default | Constraints |
|-------|------|---------|-------------|
| `skip` | int | 0 | ≥ 0 |
| `limit` | int | 50 | 1–100 |

**Response 200:** `list[ConversationResponse]`

---

### POST /api/conversations

สร้างสนทนาใหม่

**Body:** `ConversationCreate`

**Response 201:** `ConversationResponse`

---

### GET /api/conversations/{conversation_id}

ดูสนทนาพร้อม messages

**Query params:**

| Param | Type | Default | Constraints |
|-------|------|---------|-------------|
| `message_limit` | int | 50 | 1–500 |

**Response 200:** `ConversationWithMessages`

**Response 404:** `{ "detail": "Conversation not found" }`

---

### PUT /api/conversations/{conversation_id}

อัปเดต title หรือ default languages

**Body:** `ConversationUpdate`

**Response 200:** `ConversationResponse`

**Response 404:** `{ "detail": "Conversation not found" }`

---

### DELETE /api/conversations/{conversation_id}

ลบสนทนา (CASCADE ลบ messages ด้วย)

**Response 204:** no body

**Response 404:** `{ "detail": "Conversation not found" }`

---

## Translation / Messages

### POST /api/conversations/{conversation_id}/messages

ส่งข้อความแปล (non-streaming)

**Body:** `MessageCreate`

**Response 201:** `TranslateResponse`

**Response 404:** `{ "detail": "Conversation not found" }`

---

### POST /api/conversations/{conversation_id}/messages/stream

ส่งข้อความแปล (SSE streaming)

**Body:** `MessageCreate`

**Response:** `text/event-stream`

**Headers:**
- `Cache-Control: no-cache`
- `Connection: keep-alive`
- `X-Accel-Buffering: no`

#### SSE Events

Format: comment padding + `event: <type>` + `data: <JSON>`

| Event | Data | คำอธิบาย |
|-------|------|----------|
| `started` | `{}` | เริ่มต้น stream |
| `user_message` | `MessageResponse` dict | ข้อความ user ที่บันทึกแล้ว |
| `token` | `{"delta": "...", "from_cache": bool}` | chunk ของคำแปล |
| `done` | `{"user_message": {...}, "assistant_message": {...}}` | เสร็จสิ้น |
| `error` | `{"detail": "..."}` | เกิดข้อผิดพลาด |

**หมายเหตุ:** Error ส่งผ่าน SSE event (HTTP 200) ไม่ใช่ HTTP error code

ข้อความ error ที่เป็นไปได้:
- `"Conversation not found"`
- `"หมดเวลารอ Local LLM (timeout)"`
- `"Translation failed"`

#### ตัวอย่าง SSE stream

```
: (padding...)
event: started
data: {}

event: user_message
data: {"id": "...", "role": "user", "content": "你好", ...}

event: token
data: {"delta": "Hello", "from_cache": false}

event: token
data: {"delta": " world", "from_cache": false}

event: done
data: {"user_message": {...}, "assistant_message": {...}}
```

---

### GET /api/messages/{message_id}

ดึง message เดี่ยว

**Response 200:** `MessageResponse`

**Response 404:** `{ "detail": "Message not found" }`

---

### DELETE /api/messages/{message_id}

ลบ message

**Response 204:** no body

**Response 404:** `{ "detail": "Message not found" }`

---

## Prompts

Prefix: `/api/prompts`

### GET /api/prompts

ดู prompts ทั้ง 3 ประเภท (system, instruction, persona)

**Response 200:** `list[PromptResponse]` — คืน 3 entries เสมอ (จาก DB หรือ defaults)

---

### PUT /api/prompts/{prompt_type}

อัปเดต prompt

**Path:** `prompt_type` = `system` | `instruction` | `persona`

**Body:** `PromptUpdate`

**Response 200:** `PromptResponse`

---

## Cache

Prefix: `/api/cache`

### GET /api/cache

ดู translation cache entries (เรียง `last_used_at` desc)

**Query params:**

| Param | Type | Default | Constraints |
|-------|------|---------|-------------|
| `skip` | int | 0 | ≥ 0 |
| `limit` | int | 50 | 1–100 |

**Response 200:** `list[CacheEntryResponse]`

---

### DELETE /api/cache/{cache_id}

ลบ cache entry

**Response 204:** no body

**Response 404:** `{ "detail": "Cache entry not found" }`

---

## Stats

Prefix: `/api/stats`

### GET /api/stats

สรุป token usage และ cache hit rate

**Response 200:** `StatsResponse`

---

## Config

Prefix: `/api/config`

Generic key-value store (ยังไม่ wired เข้า core services)

### GET /api/config

**Response 200:** `list[AppConfigResponse]`

---

### GET /api/config/{key}

**Response 200:** `AppConfigResponse`

**Response 404:** `{ "detail": "Config key not found" }`

---

### PUT /api/config/{key}

Upsert config entry

**Body:** `AppConfigUpdate`

**Response 200:** `AppConfigResponse`

---

### DELETE /api/config/{key}

**Response 204:** no body

**Response 404:** `{ "detail": "Config key not found" }`

---

## Web UI Routes

Routes เหล่านี้ไม่อยู่ใน OpenAPI (`include_in_schema=False`) — สำหรับ browser เท่านั้น

| Method | Path | คำอธิบาย |
|--------|------|----------|
| GET | `/` | Redirect → `/chat` |
| GET | `/chat` | หน้าเริ่มแชทใหม่ |
| POST | `/chat` | Form: `source_lang`, `target_lang` → redirect `/chat/{id}` |
| GET | `/chat/{conversation_id}` | หน้าแชท |
| POST | `/chat/{conversation_id}/send` | Form fallback (non-streaming SSR) |
| GET | `/conversations` | ประวัติสนทนา public (100 รายการล่าสุด) |

---

## ตัวอย่าง curl

### 1. สร้าง conversation

```bash
curl -X POST http://localhost:8000/api/conversations \
  -H "Content-Type: application/json" \
  -d '{"default_source_lang": "zh", "default_target_lang": "en"}'
```

### 2. แปลข้อความ (non-streaming)

```bash
curl -X POST http://localhost:8000/api/conversations/{conversation_id}/messages \
  -H "Content-Type: application/json" \
  -d '{
    "content": "你好世界",
    "source_lang": "zh",
    "target_lang": "en",
    "detail_level": "normal"
  }'
```

### 3. แปลแบบ streaming (SSE)

```bash
curl -N -X POST http://localhost:8000/api/conversations/{conversation_id}/messages/stream \
  -H "Content-Type: application/json" \
  -d '{
    "content": "สวัสดีครับ",
    "source_lang": "th",
    "target_lang": "en"
  }'
```

### 4. ดู stats

```bash
curl http://localhost:8000/api/stats
```

### 5. ตรวจ readiness

```bash
curl http://localhost:8000/health/ready
```

---

## สรุป Endpoints

| Method | Path | Tag |
|--------|------|-----|
| GET | `/health/live` | health |
| GET | `/health/ready` | health |
| GET | `/api/conversations` | conversations |
| POST | `/api/conversations` | conversations |
| GET | `/api/conversations/{id}` | conversations |
| PUT | `/api/conversations/{id}` | conversations |
| DELETE | `/api/conversations/{id}` | conversations |
| POST | `/api/conversations/{id}/messages` | messages |
| POST | `/api/conversations/{id}/messages/stream` | messages |
| GET | `/api/messages/{id}` | messages |
| DELETE | `/api/messages/{id}` | messages |
| GET | `/api/prompts` | prompts |
| PUT | `/api/prompts/{type}` | prompts |
| GET | `/api/cache` | cache |
| DELETE | `/api/cache/{id}` | cache |
| GET | `/api/stats` | stats |
| GET | `/api/config` | config |
| GET | `/api/config/{key}` | config |
| PUT | `/api/config/{key}` | config |
| DELETE | `/api/config/{key}` | config |

---

## เอกสารที่เกี่ยวข้อง

- [project.md](project.md) — สถาปัตยกรรมและ data flow
- [README.md](../README.md) — ติดตั้งและเริ่มต้นใช้งาน
