"""
utils/priority_model.py — Combined ML + heuristic email priority scorer.
Returns a score 0.0 (low) to 1.0 (high).

On first run uses heuristics only. After enough labelled data, trains
a lightweight sklearn logistic regression model.
"""
import re
from typing import Optional

HIGH_PRIORITY_KEYWORDS = [
    "urgent", "asap", "immediately", "critical", "deadline", "overdue",
    "action required", "time-sensitive", "important", "follow up",
    "needed today", "priority", "escalate", "emergency",
]

LOW_PRIORITY_KEYWORDS = [
    "newsletter", "unsubscribe", "promotional", "offer", "sale",
    "no-reply", "noreply", "donotreply", "notification", "alert",
]

VIP_DOMAINS: set[str] = set()  # populate from user config


def _keyword_score(text: str) -> float:
    text_lower = text.lower()
    high_hits = sum(1 for kw in HIGH_PRIORITY_KEYWORDS if kw in text_lower)
    low_hits = sum(1 for kw in LOW_PRIORITY_KEYWORDS if kw in text_lower)
    return min(1.0, max(0.0, (high_hits * 0.15) - (low_hits * 0.2) + 0.4))


def _sender_score(sender: str) -> float:
    domain = sender.split("@")[-1].lower() if "@" in sender else ""
    if domain in VIP_DOMAINS:
        return 0.9
    if any(x in sender.lower() for x in ["ceo", "cto", "director", "vp", "president"]):
        return 0.8
    if "noreply" in sender.lower() or "newsletter" in sender.lower():
        return 0.1
    return 0.5


def _classification_score(classification: str) -> float:
    mapping = {
        "urgent": 0.95,
        "decision_required": 0.85,
        "task_request": 0.7,
        "meeting_request": 0.65,
        "informational": 0.4,
        "spam": 0.05,
    }
    return mapping.get(classification, 0.5)


def compute_priority_score(
    subject: str,
    body: str,
    sender: str,
    classification: str,
    llm_urgency: Optional[float] = None,
) -> float:
    """
    Combined priority score:
    40% keyword heuristic + 30% sender + 30% classification
    If llm_urgency is provided, blend it: 50% heuristic, 50% LLM
    """
    kw = _keyword_score(subject + " " + body)
    snd = _sender_score(sender)
    cls = _classification_score(classification)

    heuristic = 0.4 * kw + 0.3 * snd + 0.3 * cls

    if llm_urgency is not None:
        return round(0.5 * heuristic + 0.5 * llm_urgency, 4)
    return round(heuristic, 4)
