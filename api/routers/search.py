"""
api/routers/search.py — Hybrid search endpoint.
Supports: sender filter, subject filter, semantic vector search, keyword + vector fusion.
"""
import re
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from db.database import get_db
from db.models import Email
from memory.vector_store import get_vector_store
from utils.profiler import PipelineTrace

router = APIRouter()


@router.get("/")
def search(
    q: str = Query("", description="Free-text semantic query"),
    sender: str = Query("", description="Filter by sender email (partial match)"),
    subject: str = Query("", description="Filter by subject (partial match)"),
    classification: str = Query("", description="Filter by email type"),
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
):
    """
    Hybrid search:
    1. Keyword SQL filter  (sender, subject, classification)
    2. Semantic vector search (ChromaDB) on email body
    3. Merge + deduplicate results, ranked by combined score
    """
    trace = PipelineTrace("search")

    # ── Step 1: SQL keyword filter ──────────────────────────────
    with trace.stage("sql_keyword_filter"):
        sql_q = db.query(Email)

        if sender:
            sql_q = sql_q.filter(
                or_(
                    Email.sender.ilike(f"%{sender}%"),
                    Email.sender_name.ilike(f"%{sender}%"),
                )
            )
        if subject:
            sql_q = sql_q.filter(Email.subject.ilike(f"%{subject}%"))
        if classification:
            sql_q = sql_q.filter(Email.classification == classification)
        if q and not sender and not subject:
            # Full-text keyword fallback in body/subject
            sql_q = sql_q.filter(
                or_(
                    Email.subject.ilike(f"%{q}%"),
                    Email.body_text.ilike(f"%{q}%"),
                    Email.sender.ilike(f"%{q}%"),
                )
            )

        sql_results = (
            sql_q.order_by(Email.created_at.desc())
            .limit(limit * 2)
            .all()
        )
        sql_ids = {e.gmail_id: e for e in sql_results}

    # ── Step 2: Semantic vector search ──────────────────────────
    vector_ids: dict[str, float] = {}
    if q:
        with trace.stage("vector_semantic_search"):
            vs = get_vector_store()
            where_filter = None
            if sender:
                where_filter = {"sender": sender}
            elif classification:
                where_filter = {"classification": classification}

            vec_results = vs.query(
                collection="emails",
                query_text=q,
                n_results=min(limit, 50),
                where=where_filter,
            )
            # distance → similarity score (lower distance = higher score)
            for r in vec_results:
                dist = r.get("distance") or 0.5
                similarity = max(0.0, 1.0 - dist)
                vector_ids[r["id"]] = similarity

    # ── Step 3: Fetch DB records for vector hits ─────────────────
    with trace.stage("db_fetch_vector_hits"):
        vec_emails: dict[str, Email] = {}
        if vector_ids:
            db_hits = (
                db.query(Email)
                .filter(Email.gmail_id.in_(list(vector_ids.keys())))
                .all()
            )
            vec_emails = {e.gmail_id: e for e in db_hits}

    # ── Step 4: Merge + rank ─────────────────────────────────────
    with trace.stage("merge_rank"):
        all_ids = set(sql_ids.keys()) | set(vec_emails.keys())
        ranked = []
        for gid in all_ids:
            email_obj = sql_ids.get(gid) or vec_emails.get(gid)
            if not email_obj:
                continue
            keyword_hit = 1.0 if gid in sql_ids else 0.0
            semantic_score = vector_ids.get(gid, 0.0)
            # Combined: keyword presence boosted, semantic as secondary signal
            combined = 0.4 * keyword_hit + 0.4 * semantic_score + 0.2 * (email_obj.priority_score or 0)
            ranked.append((combined, email_obj))

        # Sort: combined score DESC, then by date DESC
        ranked.sort(key=lambda x: (x[0], x[1].created_at or ""), reverse=True)
        final = [e for _, e in ranked[:limit]]

    trace.report()

    return {
        "total": len(final),
        "query": q,
        "items": [_serialize(e, vector_ids.get(e.gmail_id)) for e in final],
    }


def _serialize(e: Email, semantic_score: float = None) -> dict:
    return {
        "id": e.id,
        "gmail_id": e.gmail_id,
        "sender": e.sender,
        "sender_name": e.sender_name,
        "subject": e.subject,
        "classification": e.classification,
        "priority_score": e.priority_score,
        "state": e.state,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "snippet": (e.body_text or "")[:200],
        "semantic_score": round(semantic_score, 4) if semantic_score else None,
    }
