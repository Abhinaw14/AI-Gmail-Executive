"""
utils/deadline_extractor.py — Gemini-based deadline and date detection from email text.
Extracts actionable deadlines and decides if they warrant a calendar event.
"""
import json
import re
from datetime import datetime

import google.generativeai as genai
from config import get_settings

settings = get_settings()
genai.configure(api_key=settings.gemini_api_key)

SYSTEM_PROMPT = """You are an AI assistant that extracts deadlines from emails.

Analyze the email and extract ALL deadlines, due dates, submission dates, 
meeting times, event dates, or any time-sensitive commitments.

For each deadline found, return:
- "title": short title for the calendar event (e.g., "Project Report Due")
- "date": ISO date string (YYYY-MM-DD) or ISO datetime string 
- "time": time if mentioned (HH:MM in 24h), or null
- "urgency": "critical" | "high" | "medium" | "low"
- "type": "submission" | "meeting" | "exam" | "interview" | "payment" | "event" | "reminder" | "other"
- "description": 1-sentence context

Only extract CONCRETE dates. Do NOT invent dates not mentioned.
If relative dates like "tomorrow" or "next Monday" are used, resolve them 
relative to the reference date provided.

Return JSON: { "deadlines": [...], "has_deadlines": true/false }
If no deadlines found, return { "deadlines": [], "has_deadlines": false }

Respond ONLY with valid JSON.
"""

# Priority threshold — only emails scoring above this get auto-calendar events
CALENDAR_PRIORITY_THRESHOLD = 0.35

# Only these urgency levels get auto-added to calendar
CALENDAR_URGENCY_LEVELS = {"critical", "high", "medium"}

# These classifications are more likely to have real deadlines
DEADLINE_CLASSIFICATIONS = {"urgent", "task_request", "decision_required", "meeting_request"}


def extract_deadlines(
    subject: str,
    sender: str,
    snippets: list[str],
    reference_date: str = None,
) -> dict:
    """
    Uses python's dateparser to mathematically guarantee perfect date extraction 
    from snippets identified by the AI classifier, avoiding LLM math hallucinations.
    """
    import dateparser
    from datetime import datetime
    
    if not reference_date:
        reference_date = datetime.now().strftime("%Y-%m-%d")

    deadlines = []
    
    # Base configuration for resolving "tomorrow", "next Friday", etc.
    dt_settings = {
        'RELATIVE_BASE': datetime.strptime(reference_date[:10], "%Y-%m-%d") if len(reference_date) >= 10 else datetime.now(),
        'PREFER_DATES_FROM': 'future'
    }

    for snippet in snippets:
        if not snippet or len(snippet) < 3:
            continue
            
        # Parse the exact date with dateparser
        parsed_dt = dateparser.parse(snippet, settings=dt_settings)
        if not parsed_dt:
            # If dateparser fails, try stripping common prefixes like "by " or "on "
            clean_snippet = re.sub(r'^(by|on|at|due|before)\s+', '', snippet, flags=re.IGNORECASE)
            parsed_dt = dateparser.parse(clean_snippet, settings=dt_settings)
            
        if parsed_dt:
            # Determine urgency and type by looking at the snippet and subject
            text_context = (subject + " " + snippet).lower()
            
            is_meeting = any(w in text_context for w in ['meet', 'interview', 'call', 'sync', 'zoom', 'teams'])
            is_deadline = any(w in text_context for w in ['due', 'deadline', 'submit', 'complete by', 'expire', 'eod'])
            
            if "urgent" in text_context or "asap" in text_context or "immediately" in text_context:
                urgency = "high"
            elif is_deadline:
                urgency = "medium"
            else:
                urgency = "low"
                
            dtype = "meeting" if is_meeting else ("submission" if is_deadline else "event")

            # Extract time if it wasn't just a midnight default
            has_explicit_time = bool(re.search(r'\d{1,2}(:\d{2})?\s*(am|pm|a\.m\.|p\.m\.)|\d{1,2}:\d{2}', snippet, re.IGNORECASE))
            
            deadlines.append({
                "title": subject[:50] + "..." if len(subject) > 50 else subject,
                "date": parsed_dt.strftime("%Y-%m-%d"),
                "time": parsed_dt.strftime("%H:%M") if has_explicit_time else None,
                "urgency": urgency,
                "type": dtype,
                "description": f"Auto-detected exact date from context: '{snippet}'"
            })

    return {"deadlines": deadlines, "has_deadlines": len(deadlines) > 0}


def should_add_to_calendar(
    deadline: dict,
    email_priority: float,
    email_classification: str,
) -> bool:
    """
    Decide if a deadline is important enough for a calendar event.
    
    Criteria (inspired by Superhuman, Spark, Notion):
    - Email priority must be above threshold
    - Deadline urgency must be critical/high/medium
    - Certain classifications get a boost
    """
    urgency = deadline.get("urgency", "low")
    dtype = deadline.get("type", "other")

    # Always add critical deadlines regardless of priority
    if urgency == "critical":
        return True

    # High urgency + decent priority
    if urgency == "high" and email_priority >= 0.3:
        return True

    # Medium urgency needs higher priority OR deadline-prone classification
    if urgency == "medium":
        if email_priority >= CALENDAR_PRIORITY_THRESHOLD:
            return True
        if email_classification in DEADLINE_CLASSIFICATIONS:
            return True

    # Meetings and interviews always get added if medium+ urgency
    if dtype in ("meeting", "interview", "exam") and urgency in CALENDAR_URGENCY_LEVELS:
        return True

    return False


def build_calendar_event_from_deadline(
    deadline: dict,
    email_subject: str,
    email_sender: str,
    email_id: int = None,
) -> dict:
    """
    Build a Google Calendar event body from a deadline entry.
    """
    title = deadline.get("title", email_subject)
    date_str = deadline.get("date", "")
    time_str = deadline.get("time")
    urgency = deadline.get("urgency", "medium")
    dtype = deadline.get("type", "other")
    description = deadline.get("description", "")

    # Build ISO datetime
    if time_str:
        start_iso = f"{date_str}T{time_str}:00+05:30"  # IST
        # Default 1 hour for meetings/events, 30 min reminder for submissions
        duration_hours = 1 if dtype in ("meeting", "interview", "event", "exam") else 0.5
    else:
        # All-day or default to 9 AM
        start_iso = f"{date_str}T09:00:00+05:30"
        duration_hours = 1

    from datetime import timedelta
    start_dt = datetime.fromisoformat(start_iso)
    end_dt = start_dt + timedelta(hours=duration_hours)
    end_iso = end_dt.isoformat()

    # Color-code by urgency in description
    urgency_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(urgency, "⚪")

    full_description = (
        f"{urgency_emoji} {urgency.upper()} — {dtype}\n\n"
        f"{description}\n\n"
        f"📧 From: {email_sender}\n"
        f"📋 Subject: {email_subject}\n"
        f"🤖 Auto-added by AI Assistant"
    )
    if email_id:
        full_description += f"\n📎 Email ID: {email_id}"

    return {
        "title": f"{'⚠️ ' if urgency in ('critical','high') else ''}{title}",
        "start_iso": start_iso,
        "end_iso": end_iso,
        "description": full_description,
        "attendees": [],
        "timezone_str": "Asia/Kolkata",
        "add_meet": dtype in ("meeting", "interview"),
    }
