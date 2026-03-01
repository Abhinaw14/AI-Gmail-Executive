"""
agents/reply_generator_agent.py — Context-aware reply generation using Gemini.
Produces main reply, alternative, summary, action items, confidence, explanation.
"""
import json
import re
from dataclasses import dataclass, field
from typing import Optional

import google.generativeai as genai
from config import get_settings

settings = get_settings()
genai.configure(api_key=settings.gemini_api_key)


@dataclass
class ReplyDraftResult:
    main_reply: str
    alternative_reply: str
    summary: str
    action_items: list[str]
    confidence_score: float
    explanation: str
    calendar_slots: list[dict] = field(default_factory=list)


SYSTEM_PROMPT = """You are an AI executive assistant generating professional email replies.

Given the email details, past context, writing style, and calendar availability,
generate a structured JSON response with:
{
  "main_reply": "<complete email reply text>",
  "alternative_reply": "<shorter or more formal alternative reply>",
  "summary": "<2-sentence summary of what you understood from the email>",
  "action_items": ["<action item 1>", ...],
  "confidence_score": <0.0 to 1.0>,
  "explanation": "<why this reply was generated — reasoning in 2-3 sentences>"
}

Rules:
- Replies should be professional, clear and appropriately concise
- Match the provided writing style exactly
- If calendar slots are provided, offer them naturally in the reply
- action_items should be concrete next steps extracted from the email
- confidence_score reflects how confident you are this is the right reply
- Do NOT include placeholders like [Name] — use real information provided
"""


def generate_reply(
    email: dict,
    rag_context: str,
    style_description: str,
    calendar_slots: Optional[list[dict]] = None,
    attachment_summary: Optional[str] = None,
) -> ReplyDraftResult:
    """
    Generate a context-aware reply draft.
    """
    model = genai.GenerativeModel(settings.gemini_model)

    slots_text = ""
    if calendar_slots:
        slot_list = "\n".join(f"  - {s.get('display', s.get('start',''))}" for s in calendar_slots[:3])
        slots_text = f"\n\nAvailable meeting slots:\n{slot_list}"

    prompt = f"""{SYSTEM_PROMPT}

## Email Details
From: {email.get('sender_name','')} <{email.get('sender','')}>
Subject: {email.get('subject','')}
Classification: {email.get('classification','informational')}
Priority Score: {email.get('priority_score', 0.5)}

## Email Body
{email.get('body_text','')[:2000]}

## Past Conversation Context (RAG)
{rag_context[:2000]}

## Writing Style to Match
{style_description}

## Attachment Summary
{attachment_summary or 'No attachments.'}
{slots_text}

Respond ONLY with valid JSON.
"""

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # Clean up markdown formatting if present
        if text.startswith("```"):
            lines = text.split("\n")
            if len(lines) > 2:
                # Remove first line (```json) and last line (```)
                text = "\n".join(lines[1:-1])

        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                result = json.loads(m.group())
                return ReplyDraftResult(
                    main_reply=result.get("main_reply", ""),
                    alternative_reply=result.get("alternative_reply", ""),
                    summary=result.get("summary", ""),
                    action_items=result.get("action_items", []),
                    confidence_score=float(result.get("confidence_score", 0.7)),
                    explanation=result.get("explanation", ""),
                    calendar_slots=calendar_slots or [],
                )
            except json.JSONDecodeError as e:
                print(f"[ReplyGenerator] JSON Decode Error: {e} with raw text: {text}")
        else:
            # Gemini returned text but no valid JSON structure found
            print(f"[ReplyGenerator] Gemini returned non-JSON response: {text[:200]}")
            
        # Try to use the raw text as the reply if it's long enough
        if len(text) > 20:
            return ReplyDraftResult(
                main_reply=text,
                alternative_reply="",
                summary="AI generated a text reply but not in structured format.",
                action_items=[],
                confidence_score=0.5,
                explanation="Reply was generated but Gemini did not return structured JSON.",
                calendar_slots=calendar_slots or [],
            )
    except Exception as e:
        # LOG THE ACTUAL ERROR — this was silently swallowed before
        print(f"[ReplyGenerator] ERROR: {type(e).__name__}: {e}")

    return ReplyDraftResult(
        main_reply="Thank you for your email. I will get back to you shortly.",
        alternative_reply="Thanks for reaching out. I'll follow up soon.",
        summary="Unable to generate a full reply. Manual review required.",
        action_items=[],
        confidence_score=0.2,
        explanation=f"Reply generation failed. Please review and reply manually.",
        calendar_slots=calendar_slots or [],
    )

