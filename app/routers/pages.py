import uuid

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.conversation import Conversation
from app.services.translation import translate_message

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="app/templates")


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
    result = await db.execute(
        select(Conversation)
        .where(Conversation.id == conversation_id)
        .options(selectinload(Conversation.messages))
    )
    conversation = result.scalar_one_or_none()
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
    db: AsyncSession = Depends(get_db),
):
    try:
        await translate_message(
            db, conversation_id, content, source_lang, target_lang, detail_level
        )
    except ValueError:
        return RedirectResponse(url="/chat", status_code=303)

    result = await db.execute(
        select(Conversation)
        .where(Conversation.id == conversation_id)
        .options(selectinload(Conversation.messages))
    )
    conversation = result.scalar_one_or_none()
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
