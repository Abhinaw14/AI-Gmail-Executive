"""
api/routers/emails.py — Email management endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from db.database import get_db
from db.models import Email
from agents.coordinator_agent import process_email
from agents import email_reader_agent as gmail

router = APIRouter()


@router.get("/")
def list_emails(
    state: str = None,
    classification: str = None,
    sort_by: str = Query("newest", description="newest | priority | priority_newest"),
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """
    sort_by options:
      newest          — strict chronological, newest first (default)
      priority        — highest priority_score first
      priority_newest — blended: boosts priority but keeps recent emails near top
    """
    q = db.query(Email)
    if state:
        q = q.filter(Email.state == state)
    if classification:
        q = q.filter(Email.classification == classification)

    total = q.count()

    if sort_by == "priority":
        items = (
            q.order_by(Email.priority_score.desc().nullslast(), Email.created_at.desc())
            .offset(offset).limit(limit).all()
        )
    elif sort_by == "priority_newest":
        candidates = q.order_by(Email.created_at.desc()).offset(offset).limit(limit * 3).all()
        n = len(candidates)
        ranked = []
        for i, e in enumerate(candidates):
            recency_rank = 1.0 - (i / max(n, 1))
            priority = e.priority_score or 0.5
            blended = 0.4 * priority + 0.6 * recency_rank
            ranked.append((blended, e))
        ranked.sort(key=lambda x: x[0], reverse=True)
        items = [e for _, e in ranked[:limit]]
    else:  # "newest" — default
        items = (
            q.order_by(Email.created_at.desc())
            .offset(offset).limit(limit).all()
        )

    return {
        "total": total,
        "sort_by": sort_by,
        "items": [_serialize(e) for e in items],
    }


@router.get("/{email_id}")
def get_email(email_id: int, fetch_thread: bool = False, db: Session = Depends(get_db)):
    email = db.query(Email).filter(Email.id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    data = _serialize_full(email)
    # Only fetch thread from Gmail if explicitly requested (avoids slow API call)
    if fetch_thread and email.thread_id:
        try:
            data["thread"] = gmail.fetch_thread(email.thread_id)
        except Exception:
            data["thread"] = []
    return data


@router.post("/{email_id}/process")
def trigger_process(email_id: int, db: Session = Depends(get_db)):
    """Manually trigger coordinator pipeline for an email (classify + index, no reply)."""
    email = db.query(Email).filter(Email.id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    email_dict = {
        "gmail_id": email.gmail_id,
        "thread_id": email.thread_id,
        "sender": email.sender,
        "sender_name": email.sender_name,
        "recipients": email.recipients or [],
        "cc": email.cc or [],
        "subject": email.subject,
        "body_text": email.body_text or "",
        "body_html": email.body_html or "",
        "has_attachments": email.has_attachments,
        "attachments_meta": [],
    }
    try:
        result = process_email(email_dict, db)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@router.get("/{email_id}/deadlines")
def detect_deadlines_for_email(email_id: int, db: Session = Depends(get_db)):
    """Detect deadlines in a specific email. Returns list of deadlines with dates."""
    from utils.deadline_extractor import extract_deadlines
    email = db.query(Email).filter(Email.id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    try:
        result = extract_deadlines(
            subject=email.subject or "",
            body=email.body_text or "",
            sender=email.sender or "",
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deadline detection failed: {str(e)}")


@router.post("/{email_id}/generate-reply")
def generate_reply_for_email(email_id: int, db: Session = Depends(get_db)):
    """
    On-demand: generate an AI reply draft and return it for user approval.
    Does NOT send anything — the user must approve first.
    """
    from agents.retrieval_agent import retrieve_context
    from agents.scheduler_agent import find_open_slots
    from agents.reply_generator_agent import generate_reply
    from utils.style_learner import get_style_description
    from memory.vector_store import get_vector_store
    from db.models import ReplyDraft

    email = db.query(Email).filter(Email.id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")

    try:
        vs = get_vector_store()
        # Retrieve context
        context = retrieve_context(
            query=(email.subject or "") + " " + (email.body_text or "")[:200],
            sender=email.sender or "",
        )
        # Calendar slots for meeting requests
        calendar_slots = []
        if email.classification == "meeting_request":
            calendar_slots = find_open_slots(days_ahead=3, duration_minutes=30, max_slots=5)
        # Style
        style = get_style_description(vs, (email.sender or "").split("@")[-1])
        # Generate reply
        email_dict = {
            "sender": email.sender, "sender_name": email.sender_name,
            "subject": email.subject, "body_text": email.body_text or "",
            "classification": email.classification or "informational",
            "priority_score": email.priority_score or 0.5,
        }
        reply_result = generate_reply(
            email=email_dict,
            rag_context=context["combined_context"],
            style_description=style,
            calendar_slots=calendar_slots,
            attachment_summary=email.attachment_summary,
        )

        # Detect fallback (confidence <= 0.2 means Gemini failed)
        is_fallback = reply_result.confidence_score <= 0.2

        # Save as pending draft
        draft = ReplyDraft(
            email_id=email.id,
            main_reply=reply_result.main_reply,
            alternative_reply=reply_result.alternative_reply,
            summary=reply_result.summary,
            action_items=reply_result.action_items,
            confidence_score=reply_result.confidence_score,
            explanation=reply_result.explanation,
            calendar_slots=calendar_slots,
            status="pending",
        )
        db.add(draft)
        db.commit()
        db.refresh(draft)

        response = {
            "draft_id": draft.id,
            "main_reply": draft.main_reply,
            "alternative_reply": draft.alternative_reply,
            "summary": draft.summary,
            "action_items": draft.action_items or [],
            "confidence_score": draft.confidence_score,
            "explanation": draft.explanation,
            "calendar_slots": draft.calendar_slots or [],
        }
        if is_fallback:
            response["warning"] = (
                "Gemini could not generate a proper reply. "
                "This could be due to API rate limits, quota exhaustion, or the email being too short. "
                "Check your backend terminal for the actual error. The fallback reply is editable."
            )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reply generation failed: {str(e)}")


@router.post("/{email_id}/send-reply")
def send_reply_for_email(
    email_id: int,
    body: dict = None,
    db: Session = Depends(get_db),
):
    """
    User approved: send the reply.
    Body can include: { "draft_id": int, "edited_text": str (optional) }
    """
    from db.models import ReplyDraft
    email = db.query(Email).filter(Email.id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")

    body = body or {}
    draft_id = body.get("draft_id")
    edited_text = body.get("edited_text")

    # Get the draft
    draft = None
    if draft_id:
        draft = db.query(ReplyDraft).filter(ReplyDraft.id == draft_id).first()

    reply_text = edited_text or (draft.main_reply if draft else None)
    if not reply_text:
        raise HTTPException(status_code=400, detail="No reply text provided")

    try:
        gmail.send_reply(
            thread_id=email.thread_id or "",
            to=email.sender or "",
            subject=email.subject or "",
            body=reply_text,
        )
        # Update draft status
        if draft:
            from datetime import datetime
            draft.status = "sent"
            draft.approved_at = datetime.utcnow()
            if edited_text:
                draft.edited_content = edited_text
        # Update email state
        email.state = "resolved"
        db.commit()
        return {"status": "sent", "to": email.sender}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send: {str(e)}")


@router.post("/{email_id}/reject-reply")
def reject_reply(email_id: int, body: dict = None, db: Session = Depends(get_db)):
    """User rejected the draft — mark it as rejected."""
    from db.models import ReplyDraft
    body = body or {}
    draft_id = body.get("draft_id")
    if draft_id:
        draft = db.query(ReplyDraft).filter(ReplyDraft.id == draft_id).first()
        if draft:
            draft.status = "rejected"
            db.commit()
    return {"status": "rejected"}



def _serialize(e: Email) -> dict:
    """Lightweight serialization for list views (snippet only)."""
    return {
        "id": e.id,
        "gmail_id": e.gmail_id,
        "thread_id": e.thread_id,
        "sender": e.sender,
        "sender_name": e.sender_name,
        "subject": e.subject,
        "classification": e.classification,
        "priority_score": e.priority_score,
        "state": e.state,
        "has_attachments": e.has_attachments,
        "attachment_summary": e.attachment_summary,
        "sentiment": e.sentiment,
        "sentiment_score": e.sentiment_score,
        "created_at": e.created_at.isoformat() + "Z" if e.created_at else None,
        "processed_at": e.processed_at.isoformat() + "Z" if e.processed_at else None,
        "snippet": (e.body_text or "")[:200],
        "processing_status": "processed" if e.processed_at else "processing",
    }


def _serialize_full(e: Email) -> dict:
    """Full serialization for detail view (complete body_text)."""
    return {
        **_serialize(e),
        "body_text": e.body_text or "",
        "body_html": e.body_html or "",
        "recipients": e.recipients or [],
        "cc": e.cc or [],
        "labels": e.labels or [],
        "sentiment_tone": e.sentiment_tone,
    }

