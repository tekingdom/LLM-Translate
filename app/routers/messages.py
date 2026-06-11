import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.message import Message
from app.schemas.message import MessageCreate, MessageResponse, TranslateResponse
from app.services.translation import translate_message, translate_message_stream

router = APIRouter(tags=["messages"])


def _sse_event(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data, default=str)}\n\n"


@router.post(
    "/api/conversations/{conversation_id}/messages",
    response_model=TranslateResponse,
    status_code=201,
)
async def send_message(
    conversation_id: uuid.UUID,
    body: MessageCreate,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await translate_message(
            db,
            conversation_id,
            body.content,
            body.source_lang,
            body.target_lang,
            body.detail_level,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/api/conversations/{conversation_id}/messages/stream")
async def send_message_stream(
    conversation_id: uuid.UUID,
    body: MessageCreate,
):
    async def event_generator():
        yield _sse_event("started", {})
        try:
            async for event in translate_message_stream(
                conversation_id,
                body.content,
                body.source_lang,
                body.target_lang,
                body.detail_level,
            ):
                yield _sse_event(event["type"], event["data"])
        except ValueError as e:
            yield _sse_event("error", {"detail": str(e)})
        except Exception as e:
            yield _sse_event("error", {"detail": str(e)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

@router.get("/api/messages/{message_id}", response_model=MessageResponse)
async def get_message(message_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Message).where(Message.id == message_id))
    message = result.scalar_one_or_none()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    return message


@router.delete("/api/messages/{message_id}", status_code=204)
async def delete_message(message_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Message).where(Message.id == message_id))
    message = result.scalar_one_or_none()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    await db.delete(message)
