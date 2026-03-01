"""
utils/attachment_parser.py — Parse PDF and DOCX attachments, extract entities.
"""
import re
import json
import base64
import google.generativeai as genai
from dataclasses import dataclass, field
from typing import Optional
from config import get_settings

settings = get_settings()
genai.configure(api_key=settings.gemini_api_key)


@dataclass
class AttachmentResult:
    filename: str
    file_type: str
    raw_text: str
    entities: dict = field(default_factory=dict)
    # entities: {dates, amounts, names, tasks, decisions}


def _extract_pdf_text(data: bytes) -> str:
    try:
        from pypdf import PdfReader
        import io
        reader = PdfReader(io.BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:
        return ""


def _extract_docx_text(data: bytes) -> str:
    try:
        import io
        from docx import Document
        doc = Document(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception:
        return ""


def _extract_entities_with_llm(text: str) -> dict:
    model = genai.GenerativeModel(settings.gemini_model)
    prompt = f"""Extract structured information from the following document text.
Respond ONLY with valid JSON:
{{
  "dates": ["<date1>", ...],
  "amounts": ["<amount1>", ...],
  "names": ["<person/company name>", ...],
  "tasks": ["<task description>", ...],
  "decisions": ["<decision made>", ...],
  "summary": "<2-sentence summary>"
}}

Document:
{text[:4000]}
"""
    try:
        response = model.generate_content(prompt)
        text_resp = response.text.strip()
        m = re.search(r"\{.*\}", text_resp, re.DOTALL)
        if m:
            return json.loads(m.group())
    except Exception:
        pass
    return {"dates": [], "amounts": [], "names": [], "tasks": [], "decisions": [], "summary": ""}


def parse_attachment(filename: str, data: bytes) -> AttachmentResult:
    """Parse an attachment and extract entities."""
    ext = filename.lower().split(".")[-1]

    if ext == "pdf":
        text = _extract_pdf_text(data)
        file_type = "pdf"
    elif ext in ("docx", "doc"):
        text = _extract_docx_text(data)
        file_type = "docx"
    elif ext in ("txt", "md", "csv"):
        text = data.decode("utf-8", errors="ignore")
        file_type = "text"
    else:
        text = ""
        file_type = ext

    entities = _extract_entities_with_llm(text) if text.strip() else {}
    return AttachmentResult(filename=filename, file_type=file_type, raw_text=text, entities=entities)
