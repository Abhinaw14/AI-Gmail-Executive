"""
config.py — Central configuration loader.
Reads from .env file and exposes typed settings via Pydantic BaseSettings.
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
import os


class Settings(BaseSettings):
    # --- LLM ---
    gemini_api_key: str = Field(..., env="GEMINI_API_KEY")
    gemini_model: str = Field("gemini-2.5-flash", env="GEMINI_MODEL")

    # --- Google OAuth ---
    google_credentials_path: str = Field("credentials.json", env="GOOGLE_CREDENTIALS_PATH")
    google_token_path: str = Field("token.json", env="GOOGLE_TOKEN_PATH")
    google_scopes: str = Field(
        "https://www.googleapis.com/auth/gmail.modify,https://www.googleapis.com/auth/calendar",
        env="GOOGLE_SCOPES",
    )

    # --- Database ---
    database_url: str = Field("sqlite:///./assistant.db", env="DATABASE_URL")

    # --- ChromaDB ---
    chroma_db_path: str = Field("./chroma_db", env="CHROMA_DB_PATH")

    # --- Graph Memory ---
    graph_memory_path: str = Field("./graph_memory.pkl", env="GRAPH_MEMORY_PATH")

    # --- Polling ---
    poll_interval_seconds: int = Field(60, env="POLL_INTERVAL_SECONDS")

    # --- Optional integrations ---
    notion_token: str = Field("", env="NOTION_TOKEN")
    notion_database_id: str = Field("", env="NOTION_DATABASE_ID")
    slack_bot_token: str = Field("", env="SLACK_BOT_TOKEN")
    slack_channel_id: str = Field("", env="SLACK_CHANNEL_ID")
    trello_api_key: str = Field("", env="TRELLO_API_KEY")
    trello_token: str = Field("", env="TRELLO_TOKEN")
    trello_list_id: str = Field("", env="TRELLO_LIST_ID")

    # --- Frontend / CORS ---
    frontend_origin: str = Field("http://localhost:5173", env="FRONTEND_ORIGIN")

    @property
    def scopes_list(self) -> list[str]:
        return [s.strip() for s in self.google_scopes.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
