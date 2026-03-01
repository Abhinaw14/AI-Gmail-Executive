"""
agents/reporting_agent.py — Generates daily and weekly intelligence reports.
"""
import json
from datetime import datetime, timedelta

import google.generativeai as genai
from sqlalchemy.orm import Session

from db.models import Email, Task, CalendarEvent, Report
from config import get_settings

settings = get_settings()
genai.configure(api_key=settings.gemini_api_key)


def _compute_metrics(db: Session, start: datetime, end: datetime) -> dict:
    emails = db.query(Email).filter(Email.created_at >= start, Email.created_at <= end).all()
    tasks = db.query(Task).filter(Task.created_at >= start).all()
    overdue_tasks = [t for t in tasks if t.due_date and t.due_date < datetime.utcnow() and t.status != "done"]

    classification_counts: dict = {}
    for e in emails:
        c = e.classification or "unknown"
        classification_counts[c] = classification_counts.get(c, 0) + 1

    resolved = len([e for e in emails if e.state == "resolved"])
    open_count = len([e for e in emails if e.state == "open"])
    urgent = classification_counts.get("urgent", 0)

    return {
        "total_emails": len(emails),
        "resolved": resolved,
        "open": open_count,
        "urgent": urgent,
        "by_classification": classification_counts,
        "total_tasks": len(tasks),
        "overdue_tasks": len(overdue_tasks),
        "overdue_task_list": [t.title for t in overdue_tasks],
    }


def _generate_narrative(report_type: str, metrics: dict, period: str) -> str:
    model = genai.GenerativeModel(settings.gemini_model)
    prompt = f"""You are an AI executive assistant writing a {report_type} intelligence report.

Period: {period}
Metrics:
{json.dumps(metrics, indent=2)}

Write a concise, insightful {report_type} report in Markdown format with sections:
## Executive Summary
## Email Activity
## Tasks & Deadlines
## Action Required
## Recommendations

Keep it professional and actionable. Use bullet points.
"""
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception:
        return f"# {report_type.capitalize()} Report\n\nCould not generate narrative."


def generate_report(db: Session, report_type: str = "daily") -> Report:
    now = datetime.utcnow()
    if report_type == "daily":
        start = now - timedelta(days=1)
        period = f"{start.strftime('%Y-%m-%d')} to {now.strftime('%Y-%m-%d')}"
    else:
        start = now - timedelta(weeks=1)
        period = f"{start.strftime('%Y-%m-%d')} to {now.strftime('%Y-%m-%d')}"

    metrics = _compute_metrics(db, start, now)
    narrative = _generate_narrative(report_type, metrics, period)

    report = Report(
        report_type=report_type,
        generated_at=now,
        period_start=start,
        period_end=now,
        content_markdown=narrative,
        metrics=metrics,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report
