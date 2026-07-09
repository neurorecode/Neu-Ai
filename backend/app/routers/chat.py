from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ChatMessage, Meeting
from ..schemas import ChatMessageOut, ChatRequest
from ..services.chat_service import chat_about_meeting

router = APIRouter(prefix="/api/meetings/{meeting_id}/chat", tags=["chat"])

MAX_HISTORY = 20


@router.get("", response_model=list[ChatMessageOut])
def get_history(meeting_id: str, db: Session = Depends(get_db)):
    meeting = db.get(Meeting, meeting_id)
    if meeting is None:
        raise HTTPException(404, "Meeting not found")
    return meeting.chat_messages


@router.post("", response_model=ChatMessageOut)
async def send_message(meeting_id: str, body: ChatRequest, db: Session = Depends(get_db)):
    meeting = db.get(Meeting, meeting_id)
    if meeting is None:
        raise HTTPException(404, "Meeting not found")
    if meeting.status != "completed":
        raise HTTPException(400, "Meeting is still processing — chat becomes available once done")

    message = body.message.strip()
    if not message:
        raise HTTPException(400, "Message is empty")

    history = [
        {"role": m.role, "content": m.content}
        for m in meeting.chat_messages[-MAX_HISTORY:]
    ]

    answer = await chat_about_meeting(meeting, history, message)

    db.add(ChatMessage(meeting_id=meeting.id, role="user", content=message))
    reply = ChatMessage(meeting_id=meeting.id, role="assistant", content=answer)
    db.add(reply)
    db.commit()
    return reply
