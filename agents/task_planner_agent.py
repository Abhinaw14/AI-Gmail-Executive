"""
agents/task_planner_agent.py — Extract tasks from emails and create them in DB.
Optional: push to Notion or Trello.
"""
import json
import re
import requests
from datetime import datetime

import google.generativeai as genai
from config import get_settings

settings = get_settings()
genai.configure(api_key=settings.gemini_api_key)


def extract_tasks_from_email(email: dict) -> list[dict]:
    """Use Gemini to extract action tasks from an email body."""
    model = genai.GenerativeModel(settings.gemini_model)
    prompt = f"""Extract all action items and tasks from this email.
Return ONLY valid JSON array:
[
  {{
    "title": "<task title>",
    "description": "<details>",
    "due_date": "<YYYY-MM-DD or null>",
    "assignee": "<email or name or null>",
    "priority": "<high|medium|low>"
  }}
]

Email Subject: {email.get('subject','')}
Email Body:
{email.get('body_text','')[:2000]}

If no tasks found, return empty array: []
"""
    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        m = re.search(r"\[.*\]", text, re.DOTALL)
        if m:
            return json.loads(m.group())
    except Exception:
        pass
    return []


def push_to_notion(task: dict) -> str | None:
    """Push a task to Notion. Returns task URL or None on failure."""
    if not settings.notion_token or not settings.notion_database_id:
        return None
    headers = {
        "Authorization": f"Bearer {settings.notion_token}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }
    body = {
        "parent": {"database_id": settings.notion_database_id},
        "properties": {
            "Name": {"title": [{"text": {"content": task.get("title", "Task")}}]},
            "Status": {"select": {"name": "To Do"}},
            "Priority": {"select": {"name": task.get("priority", "medium").capitalize()}},
        },
    }
    try:
        resp = requests.post("https://api.notion.com/v1/pages", json=body, headers=headers)
        if resp.ok:
            return resp.json().get("url")
    except Exception:
        pass
    return None


def push_to_trello(task: dict) -> str | None:
    """Push a task card to Trello. Returns card URL or None."""
    if not settings.trello_api_key or not settings.trello_token or not settings.trello_list_id:
        return None
    try:
        resp = requests.post(
            "https://api.trello.com/1/cards",
            params={
                "key": settings.trello_api_key,
                "token": settings.trello_token,
                "idList": settings.trello_list_id,
                "name": task.get("title", "Task"),
                "desc": task.get("description", ""),
            },
        )
        if resp.ok:
            return resp.json().get("url")
    except Exception:
        pass
    return None
