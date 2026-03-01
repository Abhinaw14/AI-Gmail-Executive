"""
db/models.py — SQLAlchemy ORM models.
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Float, DateTime,
    Boolean, ForeignKey, JSON
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Email(Base):
    __tablename__ = "emails"

    id = Column(Integer, primary_key=True, index=True)
    gmail_id = Column(String, unique=True, index=True, nullable=False)
    thread_id = Column(String, index=True)
    sender = Column(String, index=True)
    sender_name = Column(String)
    recipients = Column(JSON)           # list of email addresses
    cc = Column(JSON)
    subject = Column(String)
    body_text = Column(Text)
    body_html = Column(Text)
    labels = Column(JSON)               # Gmail label ids
    classification = Column(String)     # urgent | informational | meeting_request | task_request | decision_required | spam
    priority_score = Column(Float, default=0.5)
    state = Column(String, default="open")  # open | waiting_response | resolved | follow_up_pending
    has_attachments = Column(Boolean, default=False)
    attachment_summary = Column(Text)
    sentiment = Column(String)              # positive | neutral | negative | mixed
    sentiment_score = Column(Float)         # -1.0 to 1.0
    sentiment_tone = Column(String)         # friendly, demanding, etc.
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime)
    is_read = Column(Boolean, default=False)
    is_sent = Column(Boolean, default=False)

    replies = relationship("ReplyDraft", back_populates="email")
    tasks = relationship("Task", back_populates="source_email")


class ReplyDraft(Base):
    __tablename__ = "reply_drafts"

    id = Column(Integer, primary_key=True, index=True)
    email_id = Column(Integer, ForeignKey("emails.id"))
    main_reply = Column(Text)
    alternative_reply = Column(Text)
    summary = Column(Text)
    action_items = Column(JSON)         # list of strings
    confidence_score = Column(Float)
    explanation = Column(Text)
    calendar_slots = Column(JSON)       # suggested time slots if meeting request
    status = Column(String, default="pending")  # pending | approved | rejected | sent
    created_at = Column(DateTime, default=datetime.utcnow)
    approved_at = Column(DateTime)
    edited_content = Column(Text)       # if user edited before approving

    email = relationship("Email", back_populates="replies")


class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id = Column(Integer, primary_key=True, index=True)
    g_event_id = Column(String, unique=True)
    title = Column(String)
    description = Column(Text)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    attendees = Column(JSON)
    location = Column(String)
    meet_link = Column(String)
    agenda = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    source_email_id = Column(Integer, ForeignKey("emails.id"), nullable=True)


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text)
    due_date = Column(DateTime)
    status = Column(String, default="pending")  # pending | in_progress | done | overdue
    assignee = Column(String)
    priority = Column(String, default="medium")  # high | medium | low
    source_email_id = Column(Integer, ForeignKey("emails.id"), nullable=True)
    notion_task_id = Column(String)
    trello_card_id = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)

    source_email = relationship("Email", back_populates="tasks")


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    report_type = Column(String)        # daily | weekly
    generated_at = Column(DateTime, default=datetime.utcnow)
    period_start = Column(DateTime)
    period_end = Column(DateTime)
    content_markdown = Column(Text)
    metrics = Column(JSON)              # structured metrics dict
