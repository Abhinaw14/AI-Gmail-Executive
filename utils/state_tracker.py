"""
utils/state_tracker.py — Conversation lifecycle state machine.
Tracks email thread state: open → waiting_response → resolved / follow_up_pending
"""
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from db.models import Email


VALID_STATES = {"open", "waiting_response", "resolved", "follow_up_pending"}


def determine_state(
    current_state: str,
    has_reply_draft: bool = False,
    reply_sent: bool = False,
    follow_up_scheduled: bool = False,
) -> str:
    """
    Pure function: given current state and signals, return the next state.
    Used by coordinator and by the approval flow.
    """
    if reply_sent:
        return "resolved"
    if has_reply_draft and not reply_sent:
        return "waiting_response"
    if follow_up_scheduled:
        return "follow_up_pending"
    return current_state  # no change


def update_state(db: Session, email_id: int, new_state: str):
    if new_state not in VALID_STATES:
        raise ValueError(f"Invalid state: {new_state}")
    email = db.query(Email).filter(Email.id == email_id).first()
    if email:
        email.state = new_state
        db.commit()


def get_open_threads(db: Session) -> list[Email]:
    return db.query(Email).filter(Email.state == "open").all()


def get_follow_up_due(db: Session, hours: int = 24) -> list[Email]:
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    return (
        db.query(Email)
        .filter(Email.state == "follow_up_pending", Email.created_at <= cutoff)
        .all()
    )


def get_unanswered(db: Session, hours: int = 48) -> list[Email]:
    """Emails in open state older than `hours` hours — proactive reminder."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    return (
        db.query(Email)
        .filter(Email.state == "open", Email.created_at <= cutoff)
        .all()
    )
