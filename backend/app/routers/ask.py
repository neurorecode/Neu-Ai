"""Cross-meeting Ask: one question answered across all the user's meetings."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, WorkspaceMember
from ..schemas import AskRequest, AskResponse
from ..services.ask_service import ask_across_meetings
from ..services.auth import get_current_user

router = APIRouter(prefix="/api/ask", tags=["ask"])


@router.post("", response_model=AskResponse)
async def ask(
    body: AskRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    question = body.question.strip()
    if not question:
        raise HTTPException(400, "Question is empty")

    workspace_ids = [
        m.workspace_id
        for m in db.query(WorkspaceMember).filter(WorkspaceMember.user_id == user.id).all()
    ]
    if body.workspace_id:
        if body.workspace_id not in workspace_ids:
            raise HTTPException(403, "Not a member of that workspace")
        workspace_ids = [body.workspace_id]
    if not workspace_ids:
        return AskResponse(answer="You don't have any meetings yet.", sources=[])

    answer, sources = await ask_across_meetings(db, workspace_ids, question)
    return AskResponse(answer=answer, sources=sources)
