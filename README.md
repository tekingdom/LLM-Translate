# LLM Translate

เว็บบริการแปลภาษาแบบสนทนา (English, 中文, ไทย) ใช้ Local LLM ผ่าน OpenAI-compatible API

## คุณสมบัติ

- แปลภาษา en / zh / th ทุกทิศทาง
- OpenAI-compatible API (Ollama, vLLM, LM Studio)
- PostgreSQL schema `llm_translate`
- Cache แปลจีนแบบ exact match
- นับ token in/out และความเร็ว
- System / Instruction / Persona prompts (CRUD)
- ประวัติสนทนา public ไม่ต้อง login
- Streaming response (SSE) สำหรับแปลแบบ real-time
- UI แชทง่ายๆ (vanilla JS + SSE) + REST API
- Docker สำหรับ web service (ฐานข้อมูลแยก)

## ความต้องการ

- Python 3.11+
- PostgreSQL 16
- Local LLM ที่รองรับ OpenAI API

## ติดตั้ง

```bash
# สร้าง virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS

pip install -e .

# คัดลอก config
copy .env.example .env        # Windows
# cp .env.example .env        # Linux/macOS

# รัน migration (ต่อ PostgreSQL ที่มีอยู่แล้ว)
alembic upgrade head

# เริ่มเซิร์ฟเวอร์
uvicorn app.main:app --reload
```

เปิดเบราว์เซอร์: http://localhost:8000/chat

## รันด้วย Docker (เฉพาะ Web)

ฐานข้อมูล PostgreSQL ต้องพร้อมใช้งานแล้ว — ตั้ง `DATABASE_URL` ใน `.env` ให้ชี้ไปที่ DB จริง

```bash
cp .env.example .env
# แก้ DATABASE_URL, LLM_BASE_URL ใน .env

# รัน web container
docker compose -f docker-compose.web.yml up -d --build

# ดู logs
docker compose -f docker-compose.web.yml logs -f llm_translate_web
```

**หมายเหตุ Docker:**
- Container จะรัน `alembic upgrade head` อัตโนมัติก่อน start
- `localhost` ใน `DATABASE_URL` จะถูกแปลงเป็น `host.docker.internal` อัตโนมัติเมื่อรันใน container
- บน Linux อาจต้องแก้ `DATABASE_URL` เป็น IP ของ host โดยตรง

**แก้ปัญหา Docker ที่พบบ่อย:**
| Error | สาเหตุ | วิธีแก้ |
|-------|--------|---------|
| `exec /entrypoint.sh: no such file or directory` | ไฟล์ shell มี line ending แบบ Windows (CRLF) | แก้แล้วใน Dockerfile (`sed` + `sh /entrypoint.sh`) |
| `relation "llm_translate.prompts" does not exist` | migration ยังไม่รันสำเร็จ หรือเชื่อม DB ผิด host | ตรวจ `DATABASE_URL` ใน `.env` ใช้ `localhost` ได้ — app จะ remap ให้ |
| Container restart loop | เชื่อม PostgreSQL ไม่ได้จากใน container | ใช้ `host.docker.internal` แทน `localhost` |

## ตัวแปร Environment

| ตัวแปร | คำอธิบาย |
|--------|----------|
| `DATABASE_URL` | PostgreSQL async URL |
| `DB_SCHEMA` | Schema name (default: `llm_translate`) |
| `LLM_BASE_URL` | OpenAI-compatible endpoint |
| `LLM_API_KEY` | API key |
| `LLM_MODEL` | ชื่อ model |
| `LLM_TEMPERATURE` | อุณหภูมิ (แนะนำ 0.1–0.3) |
| `LLM_MAX_TOKENS` | Max output tokens |
| `LLM_TIMEOUT_SEC` | Timeout วินาที |
| `DEFAULT_SYSTEM_PROMPT` | System prompt fallback |
| `DEFAULT_INSTRUCTION_PROMPT` | Instruction prompt fallback |
| `DEFAULT_PERSONA_PROMPT` | Persona prompt fallback |

ดูรายละเอียดเพิ่มเติมใน `.env.example` และ [Docs/project.md](Docs/project.md)

## เอกสาร

| เอกสาร | เนื้อหา |
|--------|---------|
| [Docs/project.md](Docs/project.md) | สถาปัตยกรรม, data flow, database, services |
| [Docs/api.md](Docs/api.md) | REST API และ SSE streaming ครบทุก endpoint |
| [Docs/init.sql](Docs/init.sql) | สคริปต SQL เริ่มต้นระบบใหม่ (PostgreSQL ว่าง) |
| `/docs` | Swagger UI (interactive) |

## API (ตัวอย่าง)

Endpoint ที่ใช้บ่อย — ดูครบทุก endpoint ที่ [Docs/api.md](Docs/api.md)

| Method | Path | หน้าที่ |
|--------|------|---------|
| POST | `/api/conversations` | สร้างสนทนา |
| POST | `/api/conversations/{id}/messages` | ส่งข้อความแปล |
| POST | `/api/conversations/{id}/messages/stream` | แปลแบบ SSE streaming |
| GET | `/api/stats` | สรุป token และ cache hit rate |
| GET | `/health/ready` | ตรวจ DB และ LLM |

## หน้าเว็บ

| Path | หน้า |
|------|------|
| `/chat` | เริ่มแชทใหม่ |
| `/chat/{id}` | หน้าแชท |
| `/conversations` | ประวัติสนทนา public |

## ข้อแนะนำ

- ตั้งค่า `.env` จาก `.env.example` ก่อนรันครั้งแรก
- ตรวจว่า Local LLM พร้อมใช้งานที่ `LLM_BASE_URL` (เช่น Ollama, vLLM, LM Studio)
- ใช้ `GET /health/ready` ตรวจ DB และ LLM ก่อน deploy
- อ่าน [Docs/project.md](Docs/project.md) ถ้าต้องการเข้าใจการทำงานภายใน
- อ่าน [Docs/api.md](Docs/api.md) ถ้าจะ integrate ผ่าน REST/SSE

**สงสัยอะไร ถามได้เลย** — เปิด issue หรือถามในทีม
