"""
tests/test_agents.py — Unit tests for agents and utilities.
Run: pytest tests/ -v
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta


# ── Test Priority Model ──────────────────────────────────────

class TestPriorityModel:
    def test_urgent_keywords_boost_score(self):
        from utils.priority_model import compute_priority_score
        score = compute_priority_score(
            subject="URGENT: Action required immediately",
            body="Please respond ASAP, this is critical",
            sender="boss@company.com",
            classification="urgent",
            llm_urgency=0.9,
        )
        assert score > 0.7, f"Urgent email should score > 0.7, got {score}"

    def test_spam_gets_low_score(self):
        from utils.priority_model import compute_priority_score
        score = compute_priority_score(
            subject="🎉 50% OFF Sale! Unsubscribe here",
            body="promotional offer no-reply newsletter",
            sender="noreply@deals.com",
            classification="spam",
        )
        assert score < 0.3, f"Spam should score < 0.3, got {score}"

    def test_informational_mid_range(self):
        from utils.priority_model import compute_priority_score
        score = compute_priority_score(
            subject="Weekly team update",
            body="Here is a summary of this week's progress",
            sender="colleague@company.com",
            classification="informational",
        )
        assert 0.2 < score < 0.7, f"Informational should be mid-range, got {score}"


# ── Test State Tracker ────────────────────────────────────────

class TestStateTracker:
    def test_initial_state_is_open(self):
        from utils.state_tracker import determine_state
        state = determine_state(
            current_state="open",
            has_reply_draft=False,
            reply_sent=False,
        )
        assert state == "open"

    def test_state_after_reply_sent(self):
        from utils.state_tracker import determine_state
        state = determine_state(
            current_state="waiting_response",
            has_reply_draft=True,
            reply_sent=True,
        )
        assert state == "resolved"

    def test_state_after_draft_created(self):
        from utils.state_tracker import determine_state
        state = determine_state(
            current_state="open",
            has_reply_draft=True,
            reply_sent=False,
        )
        assert state == "waiting_response"


# ── Test Email Parser ─────────────────────────────────────────

class TestEmailParser:
    def test_parse_message_extracts_fields(self):
        from agents.email_reader_agent import parse_message
        mock_msg = {
            "id": "msg123",
            "threadId": "thread456",
            "internalDate": "1709000000000",
            "labelIds": ["INBOX", "UNREAD"],
            "snippet": "Hello world",
            "payload": {
                "mimeType": "text/plain",
                "headers": [
                    {"name": "From", "value": "Alice <alice@example.com>"},
                    {"name": "To", "value": "bob@example.com"},
                    {"name": "Subject", "value": "Test email"},
                    {"name": "Date", "value": "Mon, 1 Jan 2024 10:00:00 +0000"},
                ],
                "body": {"data": "SGVsbG8gd29ybGQ="},  # base64 "Hello world"
            },
        }
        result = parse_message(mock_msg)
        assert result["gmail_id"] == "msg123"
        assert result["thread_id"] == "thread456"
        assert result["sender"] == "alice@example.com"
        assert result["sender_name"] == "Alice"
        assert result["subject"] == "Test email"
        assert result["internal_date_ms"] == "1709000000000"
        assert "bob@example.com" in result["recipients"]

    def test_parse_message_handles_no_angle_brackets(self):
        from agents.email_reader_agent import parse_message
        mock_msg = {
            "id": "msg789",
            "threadId": "thread000",
            "payload": {
                "mimeType": "text/plain",
                "headers": [
                    {"name": "From", "value": "plain@sender.com"},
                    {"name": "Subject", "value": "Plain sender"},
                ],
                "body": {"data": ""},
            },
        }
        result = parse_message(mock_msg)
        assert result["sender"] == "plain@sender.com"


# ── Test Sentiment ────────────────────────────────────────────

class TestSentiment:
    @patch("utils.sentiment.genai")
    def test_sentiment_returns_default_on_failure(self, mock_genai):
        """If Gemini fails, return neutral default."""
        mock_genai.GenerativeModel.return_value.generate_content.side_effect = Exception("API down")
        from utils.sentiment import analyze_sentiment
        result = analyze_sentiment("Test", "Body", "sender@test.com")
        assert result["sentiment"] == "neutral"
        assert result["sentiment_score"] == 0.0


# ── Test Graph Memory ─────────────────────────────────────────

class TestGraphMemory:
    def test_add_and_query(self):
        from memory.graph_memory import GraphMemory
        gm = GraphMemory(path="/tmp/test_graph.pkl")
        gm.add_email_to_graph({
            "sender": "alice@test.com",
            "sender_name": "Alice",
            "recipients": ["bob@test.com"],
            "subject": "Meeting about project Alpha",
            "thread_id": "t1",
            "extracted_topics": ["project review"],
            "extracted_projects": ["Alpha"],
            "extracted_decisions": [],
            "extracted_tasks": ["prepare slides"],
        })

        neighbors = gm.get_neighbors("alice@test.com")
        assert len(neighbors) >= 2  # bob + topic or project

        top = gm.get_top_entities(limit=3)
        assert len(top) > 0

        summary = gm.get_person_summary("alice@test.com")
        assert "Alpha" in summary.get("projects", [])

    def test_search_nodes(self):
        from memory.graph_memory import GraphMemory
        gm = GraphMemory(path="/tmp/test_graph2.pkl")
        gm.add_node("topic:budget", "Topic", label="Q4 Budget Review")
        results = gm.search_nodes("budget")
        assert len(results) >= 1


# ── Test Profiler ─────────────────────────────────────────────

class TestProfiler:
    def test_timed_decorator(self):
        from utils.profiler import timed
        @timed("test_stage")
        def dummy():
            return 42
        assert dummy() == 42

    def test_pipeline_trace(self):
        import time
        from utils.profiler import PipelineTrace
        trace = PipelineTrace("test_pipeline")
        with trace.stage("fast"):
            time.sleep(0.01)
        with trace.stage("slow"):
            time.sleep(0.02)
        report = trace.report()
        assert "fast" in report
        assert "slow" in report
        assert report["slow"] > report["fast"]


# ── Integration Smoke Test ────────────────────────────────────

class TestIntegrationSmoke:
    """Test the coordinator pipeline with mocked Gmail API."""

    @patch("agents.email_reader_agent.get_gmail_service")
    @patch("utils.classifier.genai")
    @patch("agents.reply_generator_agent.genai")
    @patch("utils.sentiment.genai")
    def test_full_pipeline_mock(self, mock_sentiment_genai, mock_reply_genai, mock_classifier_genai, mock_gmail):
        """Ensures coordinator doesn't crash with fully mocked dependencies."""
        import json
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from db.models import Base, Email
        from agents.coordinator_agent import process_email

        # Use a fresh in-memory SQLite so we always have the latest schema
        test_engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=test_engine)
        TestSession = sessionmaker(bind=test_engine)
        db = TestSession()

        # Mock classifier
        mock_model = MagicMock()
        mock_model.generate_content.return_value.text = json.dumps({
            "classification": "informational",
            "confidence": 0.8,
            "extracted_topics": ["testing"],
            "extracted_projects": [],
            "extracted_decisions": [],
            "extracted_tasks": [],
        })
        mock_classifier_genai.GenerativeModel.return_value = mock_model

        # Mock sentiment
        sentiment_model = MagicMock()
        sentiment_model.generate_content.return_value.text = json.dumps({
            "sentiment": "neutral",
            "sentiment_score": 0.1,
            "tone": "formal",
        })
        mock_sentiment_genai.GenerativeModel.return_value = sentiment_model

        # Mock reply generator
        reply_model = MagicMock()
        reply_model.generate_content.return_value.text = json.dumps({
            "main_reply": "Thank you for the update.",
            "alternative_reply": "Got it, thanks!",
            "summary": "Weekly update received.",
            "action_items": [],
            "confidence_score": 0.85,
            "explanation": "Standard acknowledgment.",
        })
        mock_reply_genai.GenerativeModel.return_value = reply_model

        # Create test email in DB
        test_email = Email(
            gmail_id="integration_test_001",
            thread_id="thread_test_001",
            sender="tester@example.com",
            sender_name="Tester",
            subject="Integration Test Email",
            body_text="This is a smoke test for the pipeline.",
            state="open",
        )
        db.add(test_email)
        db.commit()

        # Run pipeline
        email_dict = {
            "gmail_id": "integration_test_001",
            "thread_id": "thread_test_001",
            "sender": "tester@example.com",
            "sender_name": "Tester",
            "subject": "Integration Test Email",
            "body_text": "This is a smoke test for the pipeline.",
            "body_html": "",
            "recipients": ["me@example.com"],
            "cc": [],
            "has_attachments": False,
            "attachments_meta": [],
        }

        result = process_email(email_dict, db)

        assert result["classification"] == "informational"
        assert result["reply_pending"] is True
        assert "priority_score" in result

        # Verify DB updated
        email_db = db.query(Email).filter(Email.gmail_id == "integration_test_001").first()
        assert email_db.classification == "informational"
        assert email_db.sentiment is not None

        db.close()
