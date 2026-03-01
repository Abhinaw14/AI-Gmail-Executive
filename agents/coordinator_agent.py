"""
agents/coordinator_agent.py — Orchestration brain.
Decides what to do for each incoming email and calls appropriate agents.
"""
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from db.models import Email, ReplyDraft, Task
from utils.classifier import classify_email
from utils.priority_model import compute_priority_score
from utils.attachment_parser import parse_attachment
from utils.style_learner import get_style_description
from utils.sentiment import analyze_sentiment
from utils.deadline_extractor import (
    extract_deadlines, should_add_to_calendar, build_calendar_event_from_deadline
)
from agents.retrieval_agent import retrieve_context
from agents.scheduler_agent import find_open_slots, create_event
from agents.reply_generator_agent import generate_reply
from agents.task_planner_agent import extract_tasks_from_email, push_to_notion, push_to_trello
from memory.vector_store import get_vector_store
from memory.graph_memory import get_graph_memory
from agents import email_reader_agent as gmail

log = logging.getLogger(__name__)


def process_email(email_dict: dict, db: Session) -> dict:
    """
    Full pipeline for a single email:
    1. Classify
    2. Compute priority
    3. Parse attachments
    4. Retrieve context (RAG + Graph)
    5. Calendar reasoning (if meeting request)
    6. Generate reply
    7. Extract tasks
    8. Persist to DB + memory
    9. Return summary dict
    """
    log.info(f"[Coordinator] Processing: {email_dict.get('subject','')}")

    # ── 1. Classify ──
    classification_result = classify_email(
        subject=email_dict.get("subject", ""),
        body=email_dict.get("body_text", ""),
        sender=email_dict.get("sender", ""),
    )
    email_dict.update(classification_result)  # merges extracted_topics, etc.

    # ── 2. Priority score ──
    priority = compute_priority_score(
        subject=email_dict.get("subject", ""),
        body=email_dict.get("body_text", ""),
        sender=email_dict.get("sender", ""),
        classification=classification_result["classification"],
        llm_urgency=classification_result.get("confidence"),
    )

    # ── 2b. Sentiment ──
    sentiment_result = analyze_sentiment(
        subject=email_dict.get("subject", ""),
        body=email_dict.get("body_text", ""),
        sender=email_dict.get("sender", ""),
    )

    # ── 3. Parse attachments ──
    attachment_summary = ""
    vs = get_vector_store()
    if email_dict.get("has_attachments"):
        summaries = []
        for att_meta in email_dict.get("attachments_meta", []):
            if att_meta.get("attachment_id"):
                data = gmail.fetch_attachment(email_dict["gmail_id"], att_meta["attachment_id"])
                result = parse_attachment(att_meta["filename"], data)
                if result.entities.get("summary"):
                    summaries.append(f"{att_meta['filename']}: {result.entities['summary']}")
                # Store document in vector memory
                vs.upsert(
                    "documents",
                    doc_id=f"doc-{email_dict['gmail_id']}-{att_meta['filename']}",
                    text=result.raw_text[:3000],
                    metadata={"filename": att_meta["filename"], "sender": email_dict["sender"]},
                )
        attachment_summary = "\n".join(summaries)

    # ── 4. Retrieve context ──
    context = retrieve_context(
        query=email_dict.get("subject", "") + " " + email_dict.get("body_text", "")[:200],
        sender=email_dict.get("sender", ""),
    )

    # ── 5. Calendar check for meeting requests ──
    calendar_slots = []
    if classification_result["classification"] == "meeting_request":
        calendar_slots = find_open_slots(days_ahead=3, duration_minutes=30, max_slots=5)

    # ── 6. Style learning (Skipped to save API quota on Free Tier) ──
    # style = get_style_description(vs, email_dict.get("sender", "").split("@")[-1])
    style = "Use a professional and concise tone."

    # NOTE: Reply generation removed from auto-pipeline.
    # Replies are now generated on-demand via the /emails/{id}/generate-reply endpoint.
    reply_draft = None

    # ── 7. Extract & persist tasks ──
    tasks_extracted = []
    if classification_result["classification"] in ("task_request", "urgent", "decision_required"):
        # We now extract tasks directly in phase 1!
        tasks_raw = classification_result.get("actionable_tasks", [])
        for t in tasks_raw:
            due = None
            if t.get("due_date"):
                try:
                    due = datetime.strptime(t["due_date"], "%Y-%m-%d")
                except Exception:
                    pass
            email_db = db.query(Email).filter(Email.gmail_id == email_dict["gmail_id"]).first()
            task = Task(
                title=t.get("title", "Untitled Task"),
                description=t.get("description", ""),
                due_date=due,
                priority=t.get("priority", "medium"),
                assignee=t.get("assignee", ""),
                source_email_id=email_db.id if email_db else None,
            )
            task.notion_task_id = push_to_notion(t) or ""
            task.trello_card_id = push_to_trello(t) or ""
            db.add(task)
            tasks_extracted.append(t.get("title", ""))
        db.commit()

    # ── 8. Deadline detection + Auto-calendar ──
    deadlines_found = []
    calendar_events_created = []
    if classification_result["classification"] != "spam":
        deadline_result = extract_deadlines(
            subject=email_dict.get("subject", ""),
            sender=email_dict.get("sender", ""),
            snippets=classification_result.get("extracted_deadlines_text", []),
            reference_date=email_dict.get("date_str") or str(datetime.now().date())
        )
        if deadline_result.get("has_deadlines"):
            for dl in deadline_result["deadlines"]:
                deadlines_found.append(dl)
                # Only add to calendar if it meets priority/urgency thresholds
                if should_add_to_calendar(dl, priority, classification_result["classification"]):
                    event_body = build_calendar_event_from_deadline(
                        deadline=dl,
                        email_subject=email_dict.get("subject", ""),
                        email_sender=email_dict.get("sender", ""),
                        email_id=email_db.id if email_db else None,
                    )
                    try:
                        result = create_event(**event_body)
                        if result.get("status") == "created":
                            calendar_events_created.append({
                                "title": event_body["title"],
                                "date": dl.get("date"),
                                "event_id": result.get("event_id"),
                                "link": result.get("html_link"),
                            })
                            log.info(f"[Coordinator] Calendar event created: {event_body['title']}")
                    except Exception as e:
                        log.warning(f"[Coordinator] Calendar event failed: {e}")

    # ── 9. Update vector + graph memory ──
    vs.upsert(
        "emails",
        doc_id=email_dict["gmail_id"],
        text=email_dict.get("subject", "") + "\n" + email_dict.get("body_text", "")[:1500],
        metadata={
            "sender": email_dict.get("sender", ""),
            "subject": email_dict.get("subject", ""),
            "classification": classification_result["classification"],
            "thread_id": email_dict.get("thread_id", ""),
        },
    )
    get_graph_memory().add_email_to_graph({**email_dict, **classification_result})

    # ── Update email state ──
    email_db = db.query(Email).filter(Email.gmail_id == email_dict["gmail_id"]).first()
    if email_db:
        email_db.classification = classification_result["classification"]
        email_db.priority_score = priority
        email_db.processed_at = datetime.utcnow()
        email_db.attachment_summary = attachment_summary
        email_db.sentiment = sentiment_result.get("sentiment", "neutral")
        email_db.sentiment_score = sentiment_result.get("sentiment_score", 0.0)
        email_db.sentiment_tone = sentiment_result.get("tone", "unknown")
        if classification_result["classification"] == "spam":
            email_db.state = "resolved"
        else:
            email_db.state = "waiting_response"
        db.commit()

    log.info(f"[Coordinator] Done: {classification_result['classification']} | priority={priority:.2f} | deadlines={len(deadlines_found)} | calendar_events={len(calendar_events_created)}")

    return {
        "gmail_id": email_dict["gmail_id"],
        "classification": classification_result["classification"],
        "priority_score": priority,
        "tasks_created": tasks_extracted,
        "reply_pending": reply_draft is not None,
        "calendar_slots_offered": len(calendar_slots),
        "deadlines_found": deadlines_found,
        "calendar_events_created": calendar_events_created,
    }
