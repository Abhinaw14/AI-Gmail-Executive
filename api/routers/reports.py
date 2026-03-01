"""
api/routers/reports.py — Intelligence report endpoints.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from db.database import get_db
from db.models import Report
from agents.reporting_agent import generate_report

router = APIRouter()


@router.get("/daily")
def get_daily(db: Session = Depends(get_db)):
    report = (
        db.query(Report)
        .filter(Report.report_type == "daily")
        .order_by(Report.generated_at.desc())
        .first()
    )
    if not report:
        return {"message": "No daily report yet. POST /reports/daily to generate one."}
    return _serialize(report)


@router.get("/weekly")
def get_weekly(db: Session = Depends(get_db)):
    report = (
        db.query(Report)
        .filter(Report.report_type == "weekly")
        .order_by(Report.generated_at.desc())
        .first()
    )
    if not report:
        return {"message": "No weekly report yet. POST /reports/weekly to generate one."}
    return _serialize(report)


@router.post("/daily")
def generate_daily(db: Session = Depends(get_db)):
    report = generate_report(db, "daily")
    return _serialize(report)


@router.post("/weekly")
def generate_weekly(db: Session = Depends(get_db)):
    report = generate_report(db, "weekly")
    return _serialize(report)


def _serialize(r: Report) -> dict:
    return {
        "id": r.id,
        "report_type": r.report_type,
        "generated_at": r.generated_at.isoformat() if r.generated_at else None,
        "period_start": r.period_start.isoformat() if r.period_start else None,
        "period_end": r.period_end.isoformat() if r.period_end else None,
        "content_markdown": r.content_markdown,
        "metrics": r.metrics or {},
    }
