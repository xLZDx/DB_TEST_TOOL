"""IntelliTest application configuration."""
import json
from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR.parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    APP_NAME: str = "IntelliTest"
    APP_VERSION: str = "1.0.0"
    APP_PORT: int = 8560

    # AI Provider
    AI_PROVIDER: str = "githubcopilot"
    GITHUBCOPILOT_TOKEN: str = ""
    GITHUBCOPILOT_MODEL: str = "gpt-4o"
    GITHUBCOPILOT_ENDPOINT: str = "https://api.githubcopilot.com"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    AI_MODEL: str = ""
    AZURE_OPENAI_BASE_URL: str = ""
    AZURE_OPENAI_API_KEY: str = ""
    AZURE_OPENAI_API_VERSION: str = "2024-02-01"
    OPENAI_VERIFY_SSL: bool = True
    GITHUB_VERIFY_SSL: bool = True
    OPENAI_CA_BUNDLE: str = ""
    GITHUB_CA_BUNDLE: str = ""
    GITHUB_OAUTH_CLIENT_ID: str = ""
    GITHUB_OAUTH_SCOPE: str = "read:user copilot"
    COPILOT_AUTH_MODE: str = "manual"
    AI_HTTP_TIMEOUT_SECONDS: int = 30

    # Jira
    JIRA_BASE_URL: str = ""
    JIRA_EMAIL: str = ""
    JIRA_API_TOKEN: str = ""
    JIRA_DEFAULT_PROJECT: str = ""

    # TFS / Azure DevOps
    TFS_BASE_URL: str = ""
    TFS_PAT: str = ""
    TFS_COLLECTION: str = "DefaultCollection"
    TFS_PROJECTS: str = ""  # comma-separated

    # TestRail
    TESTRAIL_URL: str = ""
    TESTRAIL_EMAIL: str = ""
    TESTRAIL_API_KEY: str = ""
    TESTRAIL_DEFAULT_PROJECT_ID: str = ""

    # Databases
    DATASOURCES_JSON: str = "[]"

    # Storage
    DATA_DIR: str = ""

    # Security
    SECRET_KEY: str = "change-me-to-a-random-secret-key"

    def get_data_dir(self) -> Path:
        if self.DATA_DIR:
            return Path(self.DATA_DIR)
        return BASE_DIR.parent / "data"

    def get_tfs_projects(self) -> List[str]:
        raw = self.TFS_PROJECTS.strip()
        if not raw:
            return []
        return [p.strip() for p in raw.split(",") if p.strip()]

    def get_datasources(self) -> List[dict]:
        try:
            return json.loads(self.DATASOURCES_JSON) or []
        except Exception:
            return []


settings = Settings()
