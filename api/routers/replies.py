"""
api/routers/replies.py — Reply approval endpoints.
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from db.database import get_db
from db.models import ReplyDraft, Email
from agents import email_reader_agent as gmail

router = APIRouter()


class EditReplyBody(BaseModel):
    content: str


@router.get("/pending")
def list_pending(db: Session = Depends(get_db)):
    drafts = db.query(ReplyDraft).filter(ReplyDraft.status == "pending").all()
    return [_serialize(d, db) for d in drafts]


@router.get("/{draft_id}")
def get_draft(draft_id: int, db: Session = Depends(get_db)):
    draft = db.query(ReplyDraft).filter(ReplyDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    return _serialize(draft, db)


@router.post("/{draft_id}/approve")
def approve_draft(draft_id: int, db: Session = Depends(get_db)):
    """Approve and send the reply via Gmail."""
    draft = db.query(ReplyDraft).filter(ReplyDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    email = db.query(Email).filter(Email.id == draft.email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Source email not found")

    reply_body = draft.edited_content or draft.main_reply
    gmail.send_reply(
        thread_id=email.thread_id,
        to=email.sender,
        subject=email.subject or "",
        body=reply_body,
    )
    draft.status = "sent"
    draft.approved_at = datetime.utcnow()
    email.state = "resolved"
    db.commit()
    return {"status": "sent", "draft_id": draft_id}


@router.post("/{draft_id}/edit")
def edit_draft(draft_id: int, body: EditReplyBody, db: Session = Depends(get_db)):
    draft = db.query(ReplyDraft).filter(ReplyDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    draft.edited_content = body.content
    db.commit()
    return {"status": "updated", "draft_id": draft_id}


@router.delete("/{draft_id}")
def reject_draft(draft_id: int, db: Session = Depends(get_db)):
    draft = db.query(ReplyDraft).filter(ReplyDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    draft.status = "rejected"
    db.commit()
    return {"status": "rejected"}


def _serialize(d: ReplyDraft, db: Session) -> dict:
    email = db.query(Email).filter(Email.id == d.email_id).first()
    return {
        "id": d.id,
        "email_id": d.email_id,
        "email_subject": email.subject if email else "",
        "email_sender": email.sender if email else "",
        "main_reply": d.main_reply,
        "alternative_reply": d.alternative_reply,
        "summary": d.summary,
        "action_items": d.action_items or [],
        "confidence_score": d.confidence_score,
        "explanation": d.explanation,
        "calendar_slots": d.calendar_slots or [],
        "status": d.status,
        "edited_content": d.edited_content,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }
