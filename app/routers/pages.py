import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.static_assets import static_version
from app.models.conversation import Conversation
from app.schemas.message import validate_message_fields
from app.services.conversations import load_conversation_with_recent_messages
from app.services.message_format import format_translation_content
from app.services.translation import translate_message

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="app/templates")
templates.env.filters["format_translation"] = format_translation_content
templates.env.globals["static_version"] = static_version

VALID_LANGS = frozenset({"en", "zh", "th"})
VALID_DETAIL_LEVELS = frozenset({"normal", "short", "detailed"})
VALID_NUM_OPTIONS = frozenset({1, 2, 3})


def _validate_form_fields(
    content: str,
    source_lang: str,
    target_lang: str,
    detail_level: str,
    num_options: int = 1,
) -> None:
    if source_lang not in VALID_LANGS or target_lang not in VALID_LANGS:
        raise HTTPException(status_code=422, detail="Invalid language")
    if detail_level not in VALID_DETAIL_LEVELS:
        raise HTTPException(status_code=422, detail="Invalid detail level")
    if num_options not in VALID_NUM_OPTIONS:
        raise HTTPException(status_code=422, detail="Invalid num_options")
    try:
        validate_message_fields(content, source_lang, target_lang, detail_level, num_options)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc


@router.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/chat", status_code=302)


@router.get("/chat", response_class=HTMLResponse, include_in_schema=False)
async def new_chat_page(request: Request):
    return templates.TemplateResponse(
        request,
        "new_chat.html",
        {"source_langs": ["en", "zh", "th"], "target_langs": ["en", "zh", "th"]},
    )


@router.post("/chat", include_in_schema=False)
async def create_chat_and_redirect(
    source_lang: str = Form(...),
    target_lang: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    if source_lang not in VALID_LANGS or target_lang not in VALID_LANGS:
        raise HTTPException(status_code=422, detail="Invalid language")
    conversation = Conversation(
        default_source_lang=source_lang,
        default_target_lang=target_lang,
    )
    db.add(conversation)
    await db.flush()
    await db.refresh(conversation)
    return RedirectResponse(url=f"/chat/{conversation.id}", status_code=303)


@router.get("/chat/{conversation_id}", response_class=HTMLResponse, include_in_schema=False)
async def chat_page(
    request: Request,
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    conversation = await load_conversation_with_recent_messages(db, conversation_id)
    if not conversation:
        return RedirectResponse(url="/chat", status_code=302)
    return templates.TemplateResponse(
        request,
        "chat.html",
        {
            "conversation": conversation,
            "source_langs": ["en", "zh", "th"],
            "target_langs": ["en", "zh", "th"],
        },
    )


@router.post("/chat/{conversation_id}/send", include_in_schema=False)
async def send_chat_message(
    request: Request,
    conversation_id: uuid.UUID,
    content: str = Form(...),
    source_lang: str = Form(...),
    target_lang: str = Form(...),
    detail_level: str = Form(default="normal"),
    num_options: int = Form(default=1),
    db: AsyncSession = Depends(get_db),
):
    _validate_form_fields(content, source_lang, target_lang, detail_level, num_options)
    try:
        await translate_message(
            db, conversation_id, content, source_lang, target_lang, detail_level, num_options
        )
    except ValueError:
        return RedirectResponse(url="/chat", status_code=303)

    conversation = await load_conversation_with_recent_messages(db, conversation_id)
    return templates.TemplateResponse(
        request,
        "partials/messages.html",
        {"conversation": conversation},
    )


@router.get("/conversations", response_class=HTMLResponse, include_in_schema=False)
async def conversations_page(request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Conversation).order_by(Conversation.updated_at.desc()).limit(100)
    )
    conversations = result.scalars().all()
    return templates.TemplateResponse(
        request,
        "conversations.html",
        {"conversations": conversations},
    )
