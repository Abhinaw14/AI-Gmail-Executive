"""
utils/classifier.py — LLM-based email classifier using Gemini.

Classification categories:
  urgent | informational | meeting_request | task_request | decision_required | spam
"""
import json
import re
import google.generativeai as genai
from config import get_settings

settings = get_settings()
genai.configure(api_key=settings.gemini_api_key)

CATEGORIES = [
    "urgent",
    "informational",
    "meeting_request",
    "task_request",
    "decision_required",
    "spam",
]

SYSTEM_PROMPT = """You are an expert email classifier for an AI executive assistant.
Classify the given email into exactly ONE of these categories:
- urgent: Requires immediate attention or response within hours
- informational: News, updates, newsletters — no action required
- meeting_request: Requesting to schedule or reschedule a meeting
- task_request: Asking to complete a task or deliver something
- decision_required: Needs a yes/no or strategic decision
- spam: Promotional, irrelevant or junk mail

Based on the email, you must also extract TWO extra things to save processing time:
1. "extracted_deadlines_text": A list of EXACT short string snippets from the text that mention a time or date (e.g., ["next Friday at 4 PM", "tomorrow morning", "by EOD 10/12/2023"]). Return an empty list if none exist.
2. "actionable_tasks": If the email has clear tasks for the receiver, extract them as a list of dicts. Example: [{"title": "Send the report", "priority": "high", "description": "Send the quarterly sales report to Dave"}]. Return an empty list if none exist.

Respond ONLY with valid JSON:
{
  "classification": "<category>",
  "confidence": <0.0 to 1.0>,
  "reasoning": "<one sentence explanation>",
  "urgency_indicators": ["<indicator1>", ...],
  "extracted_topics": ["<topic1>", ...],
  "extracted_deadlines_text": ["<exact snippet 1>", ...],
  "actionable_tasks": [
     {"title": "...", "priority": "high|medium|low", "description": "..."}
  ]
}
"""


def classify_email(subject: str, body: str, sender: str) -> dict:
    """
    Classify an email using Gemini.
    Returns classification dict.
    """
    model = genai.GenerativeModel(settings.gemini_model)
    prompt = f"""Sender: {sender}
Subject: {subject}

Body:
{body[:3000]}
"""
    try:
        response = model.generate_content(
            [{"role": "user", "parts": [SYSTEM_PROMPT + "\n\n" + prompt]}]
        )
        text = response.text.strip()
        # Extract JSON block
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            if result.get("classification") not in CATEGORIES:
                result["classification"] = "informational"
            return result
    except Exception as e:
        pass

    # Fallback
    return {
        "classification": "informational",
        "confidence": 0.5,
        "reasoning": "Classification failed; defaulting to informational.",
        "urgency_indicators": [],
        "extracted_topics": [],
        "extracted_projects": [],
        "extracted_decisions": [],
        "extracted_tasks": [],
    }
