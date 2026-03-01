"""
agents/intelligence_agent.py — Proactive Intelligence Engine.
Scans email history and generates actionable suggestions:
  - Follow-up reminders for unanswered threads
  - Overdue task alerts
  - Sender relationship insights
  - Calendar conflict warnings
  - Priority anomaly detection
"""
import json
import logging
from datetime import datetime, timedelta

import google.generativeai as genai
from sqlalchemy.orm import Session
from sqlalchemy import func

from config import get_settings
from db.models import Email, Task, ReplyDraft
from memory.graph_memory import get_graph_memory
from utils.sentiment import get_sentiment_trends

log = logging.getLogger(__name__)
settings = get_settings()
genai.configure(api_key=settings.gemini_api_key)


def generate_proactive_insights(db: Session) -> list[dict]:
    """
    Analyze recent email activity and produce a list of proactive suggestions.
    Each suggestion: { type, priority, title, detail, action_label }
    """
    insights = []

    # ── 1. Stale threads (waiting_response > 48h) ──
    stale_cutoff = datetime.utcnow() - timedelta(hours=48)
    stale = (
        db.query(Email)
        .filter(Email.state == "waiting_response", Email.processed_at < stale_cutoff)
        .order_by(Email.priority_score.desc())
        .limit(10)
        .all()
    )
    for e in stale:
        hours = int((datetime.utcnow() - e.processed_at).total_seconds() / 3600) if e.processed_at else 99
        insights.append({
            "type": "follow_up",
            "priority": "high" if e.priority_score and e.priority_score > 0.7 else "medium",
            "title": f"No reply sent: {e.subject}",
            "detail": f"Waiting {hours}h — from {e.sender_name or e.sender}.",
            "action_label": "View email",
            "email_id": e.id,
        })

    # ── 2. Overdue tasks ──
    overdue = (
        db.query(Task)
        .filter(Task.status.in_(["pending", "in_progress"]), Task.due_date < datetime.utcnow())
        .order_by(Task.due_date.asc())
        .limit(5)
        .all()
    )
    for t in overdue:
        days_late = (datetime.utcnow() - t.due_date).days if t.due_date else 0
        insights.append({
            "type": "overdue_task",
            "priority": "high",
            "title": f"Overdue: {t.title}",
            "detail": f"{days_late} day(s) past due. Assigned to: {t.assignee or 'unassigned'}.",
            "action_label": "Update task",
            "task_id": t.id,
        })

    # ── 3. High-volume senders (>5 emails in 7 days) ──
    week_ago = datetime.utcnow() - timedelta(days=7)
    top_senders = (
        db.query(Email.sender, func.count(Email.id).label("cnt"))
        .filter(Email.created_at >= week_ago)
        .group_by(Email.sender)
        .having(func.count(Email.id) >= 5)
        .order_by(func.count(Email.id).desc())
        .limit(5)
        .all()
    )
    for sender, cnt in top_senders:
        insights.append({
            "type": "sender_volume",
            "priority": "low",
            "title": f"High activity from {sender}",
            "detail": f"{cnt} emails in the past 7 days. Consider creating a filter or label.",
            "action_label": "View sender",
        })

    # ── 4. Unapproved drafts aging > 24h ──
    old_drafts = (
        db.query(ReplyDraft)
        .filter(ReplyDraft.status == "pending", ReplyDraft.created_at < datetime.utcnow() - timedelta(hours=24))
        .limit(5)
        .all()
    )
    for d in old_drafts:
        insights.append({
            "type": "draft_stale",
            "priority": "medium",
            "title": f"Unapproved draft ({d.id})",
            "detail": f"Draft pending for >24h. Confidence: {int((d.confidence_score or 0) * 100)}%.",
            "action_label": "Review draft",
            "draft_id": d.id,
        })

    # ── 5. Sentiment alert (negative trend from key sender) ──
    try:
        trends = get_sentiment_trends(db, days=7)
        for sender_info in trends.get("by_sender", []):
            if sender_info["avg_score"] < -0.3 and sender_info["count"] >= 2:
                insights.append({
                    "type": "sentiment_alert",
                    "priority": "medium",
                    "title": f"Negative sentiment from {sender_info['sender']}",
                    "detail": f"Avg score: {sender_info['avg_score']} across {sender_info['count']} emails. May need a personal follow-up.",
                    "action_label": "View history",
                })
    except Exception:
        pass

    # ── 6. Graph memory: relationship insights (top connected entities) ──
    try:
        gm = get_graph_memory()
        top_entities = gm.get_top_entities(limit=3)
        if top_entities:
            names = ", ".join([f"{e[0]} ({e[1]} connections)" for e in top_entities])
            insights.append({
                "type": "relationship",
                "priority": "low",
                "title": "Key contacts this week",
                "detail": f"Most connected: {names}.",
                "action_label": "View graph",
            })
    except Exception:
        pass

    # Sort: high > medium > low
    priority_order = {"high": 0, "medium": 1, "low": 2}
    insights.sort(key=lambda x: priority_order.get(x.get("priority", "low"), 3))

    return insights
