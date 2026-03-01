"""
agents/scheduler_agent.py — Google Calendar integration.
Checks availability, finds open slots, creates events.
"""
from datetime import datetime, timedelta, timezone
from agents.email_reader_agent import _get_credentials
from googleapiclient.discovery import build
import pytz


def get_calendar_service():
    return build("calendar", "v3", credentials=_get_credentials())


def get_availability(date: datetime, duration_minutes: int = 30, timezone_str: str = "UTC") -> dict:
    """
    Check busy/free slots for a given day.
    Returns free slots as list of {start, end} dicts.
    """
    service = get_calendar_service()
    tz = pytz.timezone(timezone_str)

    day_start = tz.localize(datetime(date.year, date.month, date.day, 8, 0))
    day_end = tz.localize(datetime(date.year, date.month, date.day, 19, 0))

    body = {
        "timeMin": day_start.isoformat(),
        "timeMax": day_end.isoformat(),
        "items": [{"id": "primary"}],
    }
    try:
        result = service.freebusy().query(body=body).execute()
        busy_periods = result.get("calendars", {}).get("primary", {}).get("busy", [])
    except Exception:
        busy_periods = []

    # Generate all possible slots
    slots = []
    current = day_start
    duration = timedelta(minutes=duration_minutes)

    while current + duration <= day_end:
        slot_end = current + duration
        # Check if this slot overlaps with any busy period
        is_free = True
        for busy in busy_periods:
            busy_start = datetime.fromisoformat(busy["start"].replace("Z", "+00:00"))
            busy_end = datetime.fromisoformat(busy["end"].replace("Z", "+00:00"))
            if current < busy_end and slot_end > busy_start:
                is_free = False
                break
        if is_free:
            slots.append({
                "start": current.isoformat(),
                "end": slot_end.isoformat(),
                "display": f"{current.strftime('%I:%M %p')} – {slot_end.strftime('%I:%M %p')} ({timezone_str})",
            })
        current += timedelta(minutes=30)  # step by 30 min

    return {"date": date.strftime("%Y-%m-%d"), "free_slots": slots, "busy_count": len(busy_periods)}


def find_open_slots(
    days_ahead: int = 3,
    duration_minutes: int = 30,
    timezone_str: str = "UTC",
    max_slots: int = 5,
) -> list[dict]:
    """Find the next N open slots across upcoming days."""
    slots = []
    today = datetime.now()
    for i in range(days_ahead):
        day = today + timedelta(days=i + 1)
        avail = get_availability(day, duration_minutes, timezone_str)
        for s in avail["free_slots"]:
            slots.append(s)
            if len(slots) >= max_slots:
                return slots
    return slots


def create_event(
    title: str,
    start_iso: str,
    end_iso: str,
    attendees: list[str] = None,
    description: str = "",
    timezone_str: str = "UTC",
    add_meet: bool = True,
) -> dict:
    """Create a Google Calendar event and return the event dict."""
    service = get_calendar_service()
    body = {
        "summary": title,
        "description": description,
        "start": {"dateTime": start_iso, "timeZone": timezone_str},
        "end": {"dateTime": end_iso, "timeZone": timezone_str},
        "attendees": [{"email": e} for e in (attendees or [])],
    }
    if add_meet:
        body["conferenceData"] = {
            "createRequest": {"requestId": f"meet-{int(datetime.now().timestamp())}"}
        }
    try:
        event = service.events().insert(
            calendarId="primary",
            body=body,
            conferenceDataVersion=1 if add_meet else 0,
            sendUpdates="all",
        ).execute()
        return {
            "event_id": event.get("id"),
            "html_link": event.get("htmlLink"),
            "meet_link": event.get("conferenceData", {}).get("entryPoints", [{}])[0].get("uri", ""),
            "status": "created",
        }
    except Exception as e:
        return {"error": str(e), "status": "failed"}


def get_upcoming_events(days: int = 7) -> list[dict]:
    """Get upcoming events from primary calendar."""
    service = get_calendar_service()
    now = datetime.now(timezone.utc).isoformat()
    end = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
    try:
        result = service.events().list(
            calendarId="primary",
            timeMin=now,
            timeMax=end,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        events = []
        for e in result.get("items", []):
            events.append({
                "id": e.get("id"),
                "title": e.get("summary", "No Title"),
                "start": e.get("start", {}).get("dateTime", e.get("start", {}).get("date")),
                "end": e.get("end", {}).get("dateTime", e.get("end", {}).get("date")),
                "attendees": [a.get("email") for a in e.get("attendees", [])],
                "meet_link": e.get("hangoutLink", ""),
                "description": e.get("description", ""),
            })
        return events
    except Exception:
        return []
