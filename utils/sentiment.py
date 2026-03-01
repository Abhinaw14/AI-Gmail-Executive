"""
utils/sentiment.py — Sentiment analysis using Gemini.
Tracks sentiment per email and provides trend data over time.
"""
import json
import logging
from datetime import datetime, timedelta

import google.generativeai as genai
from config import get_settings

log = logging.getLogger(__name__)
settings = get_settings()
genai.configure(api_key=settings.gemini_api_key)


def analyze_sentiment(subject: str, body: str, sender: str) -> dict:
    """
    Returns: { sentiment: positive|neutral|negative|mixed,
               sentiment_score: float -1..1,
               tone: str }
    Uses local lexicon heuristics instead of Gemini to save tokens & time.
    """
    text = f"{subject} {body}".lower()
    
    # Simple lexicon-based sentiment
    positive_words = {'great', 'good', 'excellent', 'amazing', 'thanks', 'thank you', 'appreciate', 'happy', 'glad', 'love', 'perfect', 'awesome', 'best'}
    negative_words = {'bad', 'terrible', 'worst', 'poor', 'disappointed', 'unhappy', 'angry', 'upset', 'hate', 'issue', 'problem', 'error', 'fail', 'urgent'}
    
    words = text.split()
    pos_matches = sum(1 for w in words if w in positive_words)
    neg_matches = sum(1 for w in words if w in negative_words)
    
    total = pos_matches + neg_matches
    if total == 0:
        score = 0.0
        sentiment = "neutral"
        tone = "informative"
    else:
        # Scale between -1 and 1
        score = (pos_matches - neg_matches) / total
        if score > 0.3:
            sentiment = "positive"
            tone = "friendly" if pos_matches > 2 else "positive"
        elif score < -0.3:
            sentiment = "negative"
            tone = "concerned" if "urgent" in text else "frustrated"
        elif pos_matches > 0 and neg_matches > 0:
            sentiment = "mixed"
            tone = "balanced"
        else:
            sentiment = "neutral"
            tone = "professional"
            
    return {
        "sentiment": sentiment,
        "sentiment_score": round(score, 2),
        "tone": tone
    }


def get_sentiment_trends(db_session, days: int = 7) -> dict:
    """
    Compute sentiment trends over a given window.
    Returns: { daily_avg: [{date, avg_score, count}...],
               by_sender: [{sender, avg_score, count}...],
               overall: {avg_score, positive_pct, negative_pct} }
    """
    from db.models import Email
    from sqlalchemy import func

    cutoff = datetime.utcnow() - timedelta(days=days)
    emails = (
        db_session.query(Email)
        .filter(Email.created_at >= cutoff, Email.sentiment_score.isnot(None))
        .all()
    )

    if not emails:
        return {"daily_avg": [], "by_sender": [], "overall": {"avg_score": 0, "positive_pct": 0, "negative_pct": 0}}

    # Daily averages
    daily = {}
    sender_data = {}
    total_score = 0
    pos_count = neg_count = 0

    for e in emails:
        day = e.created_at.strftime("%Y-%m-%d") if e.created_at else "unknown"
        score = e.sentiment_score or 0.0

        daily.setdefault(day, {"sum": 0, "count": 0})
        daily[day]["sum"] += score
        daily[day]["count"] += 1

        sender_data.setdefault(e.sender, {"sum": 0, "count": 0})
        sender_data[e.sender]["sum"] += score
        sender_data[e.sender]["count"] += 1

        total_score += score
        if score > 0.2:
            pos_count += 1
        elif score < -0.2:
            neg_count += 1

    n = len(emails)
    return {
        "daily_avg": sorted(
            [{"date": d, "avg_score": round(v["sum"] / v["count"], 3), "count": v["count"]} for d, v in daily.items()],
            key=lambda x: x["date"],
        ),
        "by_sender": sorted(
            [{"sender": s, "avg_score": round(v["sum"] / v["count"], 3), "count": v["count"]} for s, v in sender_data.items()],
            key=lambda x: x["avg_score"],
        ),
        "overall": {
            "avg_score": round(total_score / n, 3),
            "positive_pct": round(pos_count / n * 100, 1),
            "negative_pct": round(neg_count / n * 100, 1),
        },
    }