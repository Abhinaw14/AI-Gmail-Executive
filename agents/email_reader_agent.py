"""
agents/email_reader_agent.py — Gmail API client.
Polls for new emails, parses threads, fetches attachments.
"""
import os
import base64
import re
from datetime import datetime, timezone
from typing import Optional

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config import get_settings

settings = get_settings()


def _get_credentials() -> Credentials:
    creds = None
    token_path = settings.google_token_path
    creds_path = settings.google_credentials_path
    scopes = settings.scopes_list

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, scopes)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, scopes)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as f:
            f.write(creds.to_json())
    return creds


def get_gmail_service():
    return build("gmail", "v1", credentials=_get_credentials())


# ─────────────────────────────────────────────────────────────
# Parsing helpers
# ─────────────────────────────────────────────────────────────

def _decode_body(data: str) -> str:
    try:
        return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _extract_parts(payload: dict) -> tuple[str, str, list[dict]]:
    """Recursively extract (plain_text, html, attachments)."""
    plain, html, attachments = "", "", []
    mime = payload.get("mimeType", "")

    if mime == "text/plain":
        data = payload.get("body", {}).get("data", "")
        plain = _decode_body(data)
    elif mime == "text/html":
        data = payload.get("body", {}).get("data", "")
        html = _decode_body(data)
    elif payload.get("filename"):
        attachments.append({
            "filename": payload["filename"],
            "mime_type": mime,
            "attachment_id": payload.get("body", {}).get("attachmentId", ""),
            "size": payload.get("body", {}).get("size", 0),
        })

    for part in payload.get("parts", []):
        p, h, a = _extract_parts(part)
        plain = plain or p
        html = html or h
        attachments.extend(a)

    return plain, html, attachments


def _header(headers: list[dict], name: str) -> str:
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def parse_message(msg: dict) -> dict:
    """Parse a raw Gmail message dict into a clean email dict."""
    payload = msg.get("payload", {})
    headers = payload.get("headers", [])
    plain, html, attachments = _extract_parts(payload)

    # 1. If no plain text exists but HTML does, strip the HTML tags
    if not plain and html:
        import html as html_lib
        # Remove style/script tags completely
        clean_html = re.sub(r'<style[^>]*>.*?</style>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
        clean_html = re.sub(r'<script[^>]*>.*?</script>', ' ', clean_html, flags=re.DOTALL | re.IGNORECASE)
        # Remove all other HTML tags
        clean_html = re.sub(r'<[^>]+>', ' ', clean_html)
        plain = html_lib.unescape(clean_html)
        plain = re.sub(r'\s+', ' ', plain).strip()

    # 2. TRUNCATE to a reasonable limit (e.g. 3000 chars ~ 750 tokens) to save LLM costs
    if plain and len(plain) > 3000:
        plain = plain[:3000] + "\n...[TRUNCATED FOR LENGTH]..."

    sender_raw = _header(headers, "From")
    # Extract email address from "Name <email>"
    match = re.search(r"<(.+?)>", sender_raw)
    sender_email = match.group(1) if match else sender_raw
    sender_name = sender_raw.replace(f"<{sender_email}>", "").strip().strip('"')

    recipients_raw = _header(headers, "To")
    recipients = [r.strip() for r in recipients_raw.split(",") if r.strip()]
    cc_raw = _header(headers, "Cc")
    cc = [r.strip() for r in cc_raw.split(",") if r.strip()]

    date_str = _header(headers, "Date")

    return {
        "gmail_id": msg["id"],
        "thread_id": msg.get("threadId", ""),
        "sender": sender_email,
        "sender_name": sender_name,
        "recipients": recipients,
        "cc": cc,
        "subject": _header(headers, "Subject"),
        "body_text": plain,
        "body_html": html,
        "labels": msg.get("labelIds", []),
        "has_attachments": len(attachments) > 0,
        "attachments_meta": attachments,
        "snippet": msg.get("snippet", ""),
        "date_str": date_str,
        # Gmail's authoritative receive timestamp (milliseconds since epoch)
        # Used for correct newest-first ordering — more reliable than Date header
        "internal_date_ms": msg.get("internalDate"),
    }


# ─────────────────────────────────────────────────────────────
# Main agent methods
# ─────────────────────────────────────────────────────────────

def fetch_new_emails(max_results: int = 20, label: str = "INBOX") -> list[dict]:
    """Fetch unread emails from Gmail, newest first (by internalDate)."""
    service = get_gmail_service()
    try:
        # 'q' forces Gmail's search which guarantees newest-first sorting.
        # Adding newer_than:1d to respect strict API quotas in the background queue.
        result = service.users().messages().list(
            userId="me",
            q=f"label:{label} is:unread newer_than:1d",
            maxResults=max_results,
        ).execute()
        messages = result.get("messages", [])
        parsed = []
        for m in messages:
            full_msg = service.users().messages().get(
                userId="me",
                id=m["id"],
                format="full",
                # Only fetch fields we need — reduces payload size and latency
                # (Gmail returns full raw HTML otherwise)
            ).execute()
            parsed.append(parse_message(full_msg))
        # Sort newest first by internalDate (Gmail's own timestamp)
        parsed.sort(
            key=lambda e: int(e.get("internal_date_ms") or 0),
            reverse=True,
        )
        return parsed
    except HttpError as e:
        print(f"[EmailReader] Gmail API error: {e}")
        return []


def fetch_thread(thread_id: str) -> list[dict]:
    """Fetch all messages in a thread."""
    service = get_gmail_service()
    try:
        thread = service.users().threads().get(userId="me", id=thread_id).execute()
        return [parse_message(m) for m in thread.get("messages", [])]
    except HttpError:
        return []


def fetch_attachment(msg_id: str, attachment_id: str) -> bytes:
    """Download an attachment by its attachment_id."""
    service = get_gmail_service()
    try:
        att = service.users().messages().attachments().get(
            userId="me", messageId=msg_id, id=attachment_id
        ).execute()
        return base64.urlsafe_b64decode(att["data"] + "==")
    except Exception:
        return b""


def mark_as_read(msg_id: str):
    service = get_gmail_service()
    service.users().messages().modify(
        userId="me", id=msg_id, body={"removeLabelIds": ["UNREAD"]}
    ).execute()


def add_label(msg_id: str, label_name: str):
    """Add a user label to a message (creates label if it doesn't exist)."""
    service = get_gmail_service()
    # Get or create label
    labels = service.users().labels().list(userId="me").execute().get("labels", [])
    label_id = next((l["id"] for l in labels if l["name"] == label_name), None)
    if not label_id:
        new_label = service.users().labels().create(
            userId="me", body={"name": label_name}
        ).execute()
        label_id = new_label["id"]
    service.users().messages().modify(
        userId="me", id=msg_id, body={"addLabelIds": [label_id]}
    ).execute()


def send_reply(thread_id: str, to: str, subject: str, body: str):
    """Send a reply email."""
    service = get_gmail_service()
    import email.mime.text as mime_text
    import email.mime.multipart as mime_mp

    msg = mime_mp.MIMEMultipart()
    msg["to"] = to
    msg["subject"] = f"Re: {subject}" if not subject.startswith("Re:") else subject
    msg.attach(mime_text.MIMEText(body, "plain"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(
        userId="me", body={"raw": raw, "threadId": thread_id}
    ).execute()


# ─────────────────────────────────────────────────────────────
# Batch fetch (reduce N serial calls)
# ─────────────────────────────────────────────────────────────

def fetch_messages_batch(msg_ids: list[str]) -> list[dict]:
    """
    Fetch multiple messages using Google Batch API.
    Significantly faster than serial messages.get() calls.
    """
    service = get_gmail_service()
    results = []
    batch = service.new_batch_http_request()

    def callback(id, response, exception):
        if exception:
            print(f"[EmailReader] Batch error for {id}: {exception}")
        elif response:
            results.append(parse_message(response))

    for mid in msg_ids:
        batch.add(
            service.users().messages().get(
                userId="me", id=mid, format="full"
            ),
            callback=callback,
        )

    batch.execute()
    results.sort(key=lambda e: int(e.get("internal_date_ms") or 0), reverse=True)
    return results


# ─────────────────────────────────────────────────────────────
# Phase 1: Fast metadata-only fetch (TWO-PHASE LOADING)
# ─────────────────────────────────────────────────────────────

def parse_metadata_only(msg: dict) -> dict:
    """
    Lightweight parse: extract only sender, subject, snippet, timestamp, labels.
    Does NOT parse body (skips _extract_parts entirely). ~10× faster.
    """
    payload = msg.get("payload", {})
    headers = payload.get("headers", [])

    sender_raw = _header(headers, "From")
    match = re.search(r"<(.+?)>", sender_raw)
    sender_email = match.group(1) if match else sender_raw
    sender_name = sender_raw.replace(f"<{sender_email}>", "").strip().strip('"')

    # Check for attachments without downloading them
    has_attachments = False
    parts = payload.get("parts", [])
    for p in parts:
        if p.get("filename"):
            has_attachments = True
            break

    return {
        "gmail_id": msg["id"],
        "thread_id": msg.get("threadId", ""),
        "sender": sender_email,
        "sender_name": sender_name,
        "subject": _header(headers, "Subject"),
        "snippet": msg.get("snippet", ""),
        "labels": msg.get("labelIds", []),
        "has_attachments": has_attachments,
        "internal_date_ms": msg.get("internalDate"),
    }


def fetch_metadata_only(max_results: int = 20, label: str = "INBOX") -> list[dict]:
    """
    Phase 1: Fast metadata-only fetch using batch API with format='metadata'.
    Returns lightweight email dicts (no body) for instant inbox rendering.
    Splits into small batches to avoid Gmail 429 rate limits.
    """
    import time
    t0 = time.time()

    service = get_gmail_service()
    try:
        # 'q' forces Gmail's search which guarantees newest-first sorting.
        # Adding newer_than:1d to respect strict API quotas in the background queue.
        result = service.users().messages().list(
            userId="me",
            q=f"label:{label} is:unread newer_than:1d",
            maxResults=max_results,
        ).execute()
        messages = result.get("messages", [])
        if not messages:
            return []

        results = []

        # Process in chunks of 10 to avoid Gmail rate limits
        CHUNK_SIZE = 10
        for chunk_start in range(0, len(messages), CHUNK_SIZE):
            chunk = messages[chunk_start:chunk_start + CHUNK_SIZE]
            batch = service.new_batch_http_request()

            def make_callback():
                def callback(id, response, exception):
                    if exception:
                        print(f"[EmailReader] Metadata batch error: {exception}")
                    elif response:
                        results.append(parse_metadata_only(response))
                return callback

            for m in chunk:
                batch.add(
                    service.users().messages().get(
                        userId="me", id=m["id"], format="metadata",
                        metadataHeaders=["From", "To", "Subject", "Date"],
                    ),
                    callback=make_callback(),
                )

            batch.execute()

            # Small delay between chunks to respect rate limits
            if chunk_start + CHUNK_SIZE < len(messages):
                time.sleep(0.3)

        results.sort(key=lambda e: int(e.get("internal_date_ms") or 0), reverse=True)

        elapsed = (time.time() - t0) * 1000
        print(f"[TIMING] fetch_metadata_only: {len(results)} emails in {elapsed:.0f}ms")
        return results

    except HttpError as e:
        print(f"[EmailReader] Metadata fetch error: {e}")
        return []


def fetch_full_message(msg_id: str) -> dict:
    """
    Phase 2: Fetch full message body on-demand (when user opens email or
    when background processor needs the full content for AI pipeline).
    """
    import time
    t0 = time.time()

    service = get_gmail_service()
    try:
        full_msg = service.users().messages().get(
            userId="me", id=msg_id, format="full",
        ).execute()
        parsed = parse_message(full_msg)

        elapsed = (time.time() - t0) * 1000
        print(f"[TIMING] fetch_full_message({msg_id}): {elapsed:.0f}ms")
        return parsed
    except HttpError as e:
        print(f"[EmailReader] Full message fetch error for {msg_id}: {e}")
        return {}


# ─────────────────────────────────────────────────────────────
# Gmail History API — incremental sync
# ─────────────────────────────────────────────────────────────

_last_history_id: str | None = None


def get_current_history_id() -> str | None:
    """Get current historyId from Gmail profile."""
    service = get_gmail_service()
    try:
        profile = service.users().getProfile(userId="me").execute()
        return profile.get("historyId")
    except Exception:
        return None


def fetch_new_since_history(history_id: str = None) -> list[dict]:
    """
    Use Gmail History API to fetch only new messages since last check.
    Much faster than listing all UNREAD messages.
    Falls back to fetch_new_emails() if no historyId available.
    """
    global _last_history_id

    start_id = history_id or _last_history_id
    if not start_id:
        # First run — get current historyId and fall back to normal fetch
        _last_history_id = get_current_history_id()
        return fetch_new_emails(max_results=10)

    service = get_gmail_service()
    try:
        results = service.users().history().list(
            userId="me",
            startHistoryId=start_id,
            historyTypes=["messageAdded"],
            labelId="INBOX",
        ).execute()

        _last_history_id = results.get("historyId", start_id)

        new_ids = set()
        for record in results.get("history", []):
            for msg_added in record.get("messagesAdded", []):
                msg = msg_added.get("message", {})
                labels = msg.get("labelIds", [])
                if "INBOX" in labels:
                    new_ids.add(msg["id"])

        if not new_ids:
            return []

        # Batch fetch all new messages at once
        return fetch_messages_batch(list(new_ids))

    except HttpError as e:
        if e.resp.status == 404:
            # historyId expired — reset and do full fetch
            _last_history_id = get_current_history_id()
            return fetch_new_emails(max_results=10)
        print(f"[EmailReader] History API error: {e}")
        return []
