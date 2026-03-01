"""
utils/auth.py — API Key authentication middleware.
Simple header-based auth: X-API-Key must match the configured key.
For production use JWT or OAuth2 instead.
"""
import os
from fastapi import Request, HTTPException, Security
from fastapi.security import APIKeyHeader

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

# Key loaded from .env  (add API_AUTH_KEY=your-secret to .env)
_API_KEY = os.getenv("API_AUTH_KEY", "")


def get_api_key(api_key: str = Security(API_KEY_HEADER)) -> str:
    """
    Dependency for protected routes.
    If API_AUTH_KEY is not set in .env, auth is disabled (development mode).
    """
    if not _API_KEY:
        # Auth disabled — dev mode
        return "dev-mode"
    if api_key and api_key == _API_KEY:
        return api_key
    raise HTTPException(
        status_code=401,
        detail="Invalid or missing API key. Set X-API-Key header.",
    )
