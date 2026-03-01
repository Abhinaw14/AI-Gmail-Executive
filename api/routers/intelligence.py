"""
api/routers/intelligence.py — Proactive intelligence + sentiment endpoints.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db.database import get_db
from agents.intelligence_agent import generate_proactive_insights
from utils.sentiment import get_sentiment_trends

router = APIRouter()


@router.get("/insights")
def get_insights(db: Session = Depends(get_db)):
    """Get proactive intelligence suggestions (follow-ups, overdue tasks, etc.)."""
    insights = generate_proactive_insights(db)
    return {"total": len(insights), "insights": insights}


@router.get("/sentiment")
def sentiment_trends(days: int = 7, db: Session = Depends(get_db)):
    """Get sentiment trend data over N days."""
    trends = get_sentiment_trends(db, days=days)
    return trends
