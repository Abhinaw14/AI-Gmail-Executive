"""
utils/style_learner.py — Learn writing style from past sent emails.
Injects a style description into the reply generator prompt.
"""
import json
import re
import google.generativeai as genai
from config import get_settings

settings = get_settings()
genai.configure(api_key=settings.gemini_api_key)


def learn_style(sent_emails: list[dict]) -> str:
    """
    Analyze a list of sent emails to extract writing style.
    Returns a style description string to inject into prompts.
    """
    if not sent_emails:
        return "Use a professional and concise tone."

    samples = "\n\n---\n\n".join(
        f"Subject: {e.get('subject','')}\n{e.get('body_text','')[:500]}"
        for e in sent_emails[:10]
    )

    model = genai.GenerativeModel(settings.gemini_model)
    prompt = f"""Analyze the following email samples written by the same person.
Describe their writing style in 3-5 bullet points covering:
- Greeting style (formal/casual)
- Sign-off phrases they use
- Average sentence length (short/medium/long)
- Tone (formal/friendly/direct)
- Any distinctive phrases or patterns

Respond in plain numbered list, no JSON.

Email samples:
{samples}
"""
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception:
        return "Use a professional and concise tone."


def get_style_description(vector_store, sender_domain: str) -> str:
    """Retrieve style samples from vector store and generate style description."""
    try:
        results = vector_store.query(
            collection="style_samples",
            query_text="email reply style",
            n_results=10,
            where={"sender_domain": sender_domain} if sender_domain else None,
        )
        samples = [{"subject": r["metadata"].get("subject", ""), "body_text": r["text"]} for r in results]
        return learn_style(samples)
    except Exception:
        return "Use a professional and concise tone."
