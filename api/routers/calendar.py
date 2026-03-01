"""
api/routers/calendar.py — Google Calendar endpoints.
"""
from datetime import datetime
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from agents.scheduler_agent import get_availability, find_open_slots, create_event, get_upcoming_events

router = APIRouter()


class CreateEventBody(BaseModel):
    title: str
    start_iso: str
    end_iso: str
    attendees: list[str] = []
    description: str = ""
    timezone_str: str = "UTC"


@router.get("/availability")
def availability(
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    duration: int = Query(30, description="Meeting duration in minutes"),
    timezone: str = Query("UTC"),
):
    try:
        dt = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
    return get_availability(dt, duration_minutes=duration, timezone_str=timezone)


@router.get("/slots")
def open_slots(
    days_ahead: int = Query(3, description="How many days ahead to search"),
    duration: int = Query(30, description="Meeting duration in minutes"),
    timezone: str = Query("UTC"),
    max_slots: int = Query(5),
):
    return {"slots": find_open_slots(days_ahead, duration, timezone, max_slots)}


@router.get("/events")
def upcoming(days: int = Query(7, description="Upcoming days to fetch")):
    return {"events": get_upcoming_events(days)}


@router.post("/events")
def create(body: CreateEventBody):
    result = create_event(
        title=body.title,
        start_iso=body.start_iso,
        end_iso=body.end_iso,
        attendees=body.attendees,
        description=body.description,
        timezone_str=body.timezone_str,
    )
    if result.get("status") == "failed":
        raise HTTPException(status_code=500, detail=result.get("error"))
    return result


@router.get("/deadlines")
def scan_deadlines(days: int = Query(7, description="Scan emails from last N days")):
    """Scan recent emails for deadlines and return them."""
    from sqlalchemy.orm import Session
    from db.database import get_db, SessionLocal
    from db.models import Email
    from utils.deadline_extractor import extract_deadlines, should_add_to_calendar

    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - __import__("datetime").timedelta(days=days)
        emails = (
            db.query(Email)
            .filter(Email.created_at >= cutoff, Email.classification != "spam")
            .order_by(Email.created_at.desc())
            .limit(50)
            .all()
        )

        all_deadlines = []
        for email in emails:
            result = extract_deadlines(
                subject=email.subject or "",
                body=email.body_text or "",
                sender=email.sender or "",
            )
            if result.get("has_deadlines"):
                for dl in result["deadlines"]:
                    dl["email_id"] = email.id
                    dl["email_subject"] = email.subject
                    dl["email_sender"] = email.sender
                    dl["priority_score"] = email.priority_score
                    dl["would_add_to_calendar"] = should_add_to_calendar(
                        dl, email.priority_score or 0, email.classification or ""
                    )
                    all_deadlines.append(dl)

        # Sort by date
        all_deadlines.sort(key=lambda d: d.get("date", "9999"))
        return {"total": len(all_deadlines), "deadlines": all_deadlines}
    finally:
        db.close()


@router.post("/add-from-email")
def add_deadline_from_email(body: dict):
    """
    Manually add a deadline from an email to the calendar.
    Body: { email_id, title, date, time?, description? }
    """
    from utils.deadline_extractor import build_calendar_event_from_deadline

    deadline = {
        "title": body.get("title", "Deadline"),
        "date": body.get("date"),
        "time": body.get("time"),
        "urgency": body.get("urgency", "high"),
        "type": body.get("type", "submission"),
        "description": body.get("description", ""),
    }
    if not deadline["date"]:
        raise HTTPException(status_code=400, detail="Date is required")

    event_body = build_calendar_event_from_deadline(
        deadline=deadline,
        email_subject=body.get("email_subject", ""),
        email_sender=body.get("email_sender", ""),
        email_id=body.get("email_id"),
    )
    result = create_event(**event_body)
    if result.get("status") == "failed":
        raise HTTPException(status_code=500, detail=result.get("error"))
    return result

