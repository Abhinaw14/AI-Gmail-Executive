"""
api/main.py — FastAPI application entry point.
Two-phase loading: fast metadata fetch + background AI processing queue.
"""
import asyncio
import time
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from db.database import init_db, SessionLocal
from db.models import Email
from agents import email_reader_agent as gmail
from agents.coordinator_agent import process_email
from api.routers import emails, replies, calendar, reports, search, intelligence

log = logging.getLogger(__name__)
settings = get_settings()

# ─────────────────────────────────────────────────────────────
# Phase 1: Fast metadata poll — inserts emails without AI processing
# ─────────────────────────────────────────────────────────────

async def _poll_gmail_fast():
    """
    Phase 1: Fast metadata-only fetch from Gmail.
    Inserts lightweight emails into DB so inbox renders instantly.
    No LLM calls, no embeddings, no priority scoring.
    """
    await asyncio.sleep(3)  # wait for startup
    while True:
        try:
            t0 = time.time()
            log.info("[FastPoll] Checking Gmail for new emails (metadata only)...")
            metadata_list = gmail.fetch_metadata_only()
            db = SessionLocal()
            new_count = 0
            for meta in metadata_list:
                existing = db.query(Email).filter(
                    Email.gmail_id == meta["gmail_id"]
                ).first()
                if existing:
                    continue

                # Parse Gmail internalDate (ms epoch) → datetime
                internal_date_ms = meta.get("internal_date_ms")
                if internal_date_ms:
                    received_at = datetime.fromtimestamp(
                        int(internal_date_ms) / 1000, tz=timezone.utc
                    ).replace(tzinfo=None)
                else:
                    received_at = datetime.utcnow()

                # Insert lightweight row — no body, no AI fields
                email_obj = Email(
                    gmail_id=meta["gmail_id"],
                    thread_id=meta.get("thread_id", ""),
                    sender=meta.get("sender", ""),
                    sender_name=meta.get("sender_name", ""),
                    subject=meta.get("subject", ""),
                    body_text=meta.get("snippet", ""),  # snippet as placeholder
                    labels=meta.get("labels", []),
                    has_attachments=meta.get("has_attachments", False),
                    state="new",
                    created_at=received_at,
                    # processed_at stays NULL -> signals "needs processing"
                )
                db.add(email_obj)
                db.commit()
                new_count += 1

                # Mark as read in Gmail
                try:
                    gmail.mark_as_read(meta["gmail_id"])
                except Exception:
                    pass

            db.close()
            elapsed = (time.time() - t0) * 1000
            if new_count > 0:
                log.info(f"[FastPoll] ✅ {new_count} new emails inserted in {elapsed:.0f}ms")
            else:
                log.info(f"[FastPoll] No new emails ({elapsed:.0f}ms)")

        except Exception as e:
            log.error(f"[FastPoll] Error: {e}")

        await asyncio.sleep(settings.poll_interval_seconds)


# ─────────────────────────────────────────────────────────────
# Phase 2: Background AI processing queue
# ─────────────────────────────────────────────────────────────

async def _process_queue():
    """
    Phase 2: Background worker that processes unprocessed emails.
    Fetches full body, runs classification, priority, sentiment,
    embeddings, graph memory, deadline detection.
    Never blocks the inbox UI.

    Rate-limit aware: processes ONE email at a time with delays
    to respect Gemini free tier quotas.
    """
    await asyncio.sleep(8)  # let Phase 1 run first
    # Base delay between emails to respect Gemini 15 RPM free tier limit.
    # 1 email takes ~1-2 LLM requests now, so 15s delay ensures max 4-8 RPM strictly.
    backoff_seconds = 15

    while True:
        try:
            db = SessionLocal()
            # Pick up ONE unprocessed email at a time (newest first)
            email_obj = (
                db.query(Email)
                .filter(Email.processed_at.is_(None))
                .order_by(Email.created_at.desc())
                .first()
            )

            if not email_obj:
                db.close()
                await asyncio.sleep(10)  # nothing to process, check again in 10s
                continue

            t0 = time.time()
            try:
                # Step 1: Fetch full body if we only have snippet
                if not email_obj.body_text or len(email_obj.body_text) < 300:
                    log.info(f"[ProcessQueue] Fetching full body for: {email_obj.subject}")
                    full = gmail.fetch_full_message(email_obj.gmail_id)
                    if full:
                        email_obj.body_text = full.get("body_text", email_obj.body_text or "")
                        email_obj.body_html = full.get("body_html", "")
                        email_obj.recipients = full.get("recipients", [])
                        email_obj.cc = full.get("cc", [])
                        db.commit()

                # Step 2: Run full coordinator pipeline
                email_dict = {
                    "gmail_id": email_obj.gmail_id,
                    "thread_id": email_obj.thread_id or "",
                    "sender": email_obj.sender or "",
                    "sender_name": email_obj.sender_name or "",
                    "recipients": email_obj.recipients or [],
                    "cc": email_obj.cc or [],
                    "subject": email_obj.subject or "",
                    "body_text": email_obj.body_text or "",
                    "body_html": email_obj.body_html or "",
                    "labels": email_obj.labels or [],
                    "has_attachments": email_obj.has_attachments,
                    "snippet": (email_obj.body_text or "")[:200],
                    "internal_date_ms": str(int(email_obj.created_at.timestamp() * 1000)) if email_obj.created_at else None,
                }
                process_email(email_dict, db)

                elapsed = (time.time() - t0) * 1000
                log.info(f"[ProcessQueue] ✅ Processed '{email_obj.subject}' in {elapsed:.0f}ms")

                # Reset backoff on success
                backoff_seconds = 15

            except Exception as e:
                error_str = str(e).lower()
                if "429" in error_str or "quota" in error_str or "rate" in error_str:
                    # Gemini rate limit hit — back off significantly
                    backoff_seconds = min(backoff_seconds * 2, 120)  # max 2 min
                    log.warning(
                        f"[ProcessQueue] ⚠️ Gemini rate limit hit. "
                        f"Backing off for {backoff_seconds}s before next email."
                    )
                else:
                    log.error(f"[ProcessQueue] Error processing '{email_obj.subject}': {e}")
                    # Mark as processed so we don't retry endlessly
                    email_obj.processed_at = datetime.utcnow()
                    email_obj.state = "open"
                    db.commit()

            db.close()

        except Exception as e:
            log.error(f"[ProcessQueue] Queue error: {e}")

        # Wait between emails to respect rate limits
        await asyncio.sleep(backoff_seconds)


# ─────────────────────────────────────────────────────────────
# App lifecycle
# ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    log.info("✅ Database initialized")

    # Start both workers
    fast_poll = asyncio.create_task(_poll_gmail_fast())
    log.info(f"✅ Phase 1: Fast metadata polling started (interval: {settings.poll_interval_seconds}s)")

    process_queue = asyncio.create_task(_process_queue())
    log.info("✅ Phase 2: Background AI processing queue started")

    yield

    fast_poll.cancel()
    process_queue.cancel()


app = FastAPI(
    title="AI Gmail Executive Assistant",
    version="2.0.0",
    description="Context-aware AI assistant for Gmail — Two-phase loading architecture",
    lifespan=lifespan,
)

# CORS — allow React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(emails.router, prefix="/emails", tags=["Emails"])
app.include_router(replies.router, prefix="/replies", tags=["Replies"])
app.include_router(calendar.router, prefix="/calendar", tags=["Calendar"])
app.include_router(reports.router, prefix="/reports", tags=["Reports"])
app.include_router(search.router, prefix="/search", tags=["Search"])
app.include_router(intelligence.router, prefix="/intelligence", tags=["Intelligence"])


@app.get("/", tags=["Health"])
async def root():
    return {"status": "ok", "service": "AI Gmail Executive Assistant", "version": "2.0.0"}


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "healthy"}
