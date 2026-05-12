"""Application configuration for PP_BOT."""
from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent


def _default_data_dir() -> Path:
    configured = (os.getenv("PP_BOT_DATA_DIR") or "").strip()
    if configured:
        return Path(configured)
    local_app_data = (os.getenv("LOCALAPPDATA") or "").strip()
    if local_app_data:
        return Path(local_app_data) / "PP_BOT"
    return BASE_DIR / "data"


DATA_DIR = _default_data_dir()
SOURCE_DIR = DATA_DIR / "sources"
OUTPUT_DIR = DATA_DIR / "outputs"
PRESENTATION_DIR = OUTPUT_DIR / "presentations"
DEFAULT_CA_BUNDLE = BASE_DIR / "rjcert.pem"


class Settings(BaseSettings):
    APP_NAME: str = "PP Bot"
    APP_VERSION: str = "0.1.0"

    # AI provider settings
    AI_PROVIDER: str = "githubcopilot"  # githubcopilot | openai
    AI_MODEL: str = ""
    AI_BASE_URL: str = ""
    AI_API_KEY: str = ""
    AI_HTTP_TIMEOUT_SECONDS: int = 30

    # GitHub Copilot / GitHub Models compatible settings
    GITHUBCOPILOT_BASE_URL: str = ""
    GITHUBCOPILOT_API_KEY: str = ""
    GITHUBCOPILOT_MODEL: str = ""
    GITHUBCOPILOT_EDITOR_VERSION: str = "vscode/1.98.0"
    GITHUBCOPILOT_EDITOR_PLUGIN_VERSION: str = "copilot-chat/0.26.7"
    GITHUBCOPILOT_INTEGRATION_ID: str = "vscode-chat"
    GITHUB_VERIFY_SSL: bool = True
    GITHUB_CA_BUNDLE: str = ""

    # OpenAI-compatible settings
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_BASE_URL: str = ""
    OPENAI_VERIFY_SSL: bool = True
    OPENAI_CA_BUNDLE: str = ""

    # Microsoft / SharePoint SSO settings
    MICROSOFT_TENANT_ID: str = "common"
    MICROSOFT_CLIENT_ID: str = ""
    MICROSOFT_AUTHORITY: str = ""
    MICROSOFT_SCOPES: str = "https://graph.microsoft.com/Sites.Read.All https://graph.microsoft.com/Files.Read.All"
    MICROSOFT_VERIFY_SSL: bool = True
    MICROSOFT_ALLOW_INSECURE_SSL: bool = True
    MICROSOFT_CA_BUNDLE: str = str(DEFAULT_CA_BUNDLE) if DEFAULT_CA_BUNDLE.exists() else ""

    # SharePoint access
    SHAREPOINT_BEARER_TOKEN: str = ""

    # Wiki / Confluence access
    WIKI_BEARER_TOKEN: str = ""

    # Source content defaults
    MAX_SEARCH_RESULTS: int = 10
    MAX_CONTEXT_CHARS: int = 24_000
    MAX_PRESENTATION_SLIDES: int = 12

    class Config:
        env_file = str(BASE_DIR / ".env")
        env_file_encoding = "utf-8"


settings = Settings()

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(SOURCE_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(PRESENTATION_DIR, exist_ok=True)
