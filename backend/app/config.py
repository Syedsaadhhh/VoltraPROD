"""Application configuration and environment settings management.

Detects missing credentials safely without logging or exposing secrets.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator

# Authoritative path to repository root .env
REPO_ROOT = Path(__file__).resolve().parents[2]
ROOT_ENV_PATH = REPO_ROOT / ".env"

if ROOT_ENV_PATH.is_file():
    load_dotenv(dotenv_path=ROOT_ENV_PATH, override=False)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT_ENV_PATH) if ROOT_ENV_PATH.is_file() else ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Gemini / Google ADK
    GOOGLE_API_KEY: Optional[str] = Field(default=None, description="AI Studio API key")
    GEMINI_MODEL: str = Field(default="gemini-3.6-flash", description="Pinned Gemini model identifier")

    # ClickHouse Cloud
    CLICKHOUSE_HOST: Optional[str] = Field(default=None, description="ClickHouse Cloud hostname (pure hostname, no scheme or path)")
    CLICKHOUSE_PORT: int = Field(default=8443, description="ClickHouse HTTPS port (8443 for ClickHouse Cloud)")
    CLICKHOUSE_USER: str = Field(default="default", description="ClickHouse read user")
    CLICKHOUSE_PASSWORD: Optional[str] = Field(default=None, description="ClickHouse read user password")
    CLICKHOUSE_DATABASE: str = Field(default="default", description="Database name")
    CLICKHOUSE_SECURE: bool = Field(default=True, description="Use TLS/SSL")
    CLICKHOUSE_VERIFY: bool = Field(default=True, description="Verify SSL certificates")
    CLICKHOUSE_ALLOW_WRITE_ACCESS: bool = Field(default=False, description="MCP write access permission")
    CLICKHOUSE_CONNECT_TIMEOUT: int = Field(default=30, description="Connection timeout in seconds")

    @field_validator("CLICKHOUSE_HOST", mode="before")
    @classmethod
    def clean_clickhouse_host(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return v
        cleaned = v.strip()
        if "://" in cleaned:
            cleaned = cleaned.split("://", 1)[1]
        cleaned = cleaned.lstrip("/")
        cleaned = cleaned.split("/", 1)[0]
        if ":" in cleaned:
            cleaned = cleaned.split(":", 1)[0]
        return cleaned.strip()

    # ClickHouse Admin / Seeding (separate credential)
    CLICKHOUSE_ADMIN_USER: Optional[str] = Field(default=None, description="Admin user for DDL/seeding")
    CLICKHOUSE_ADMIN_PASSWORD: Optional[str] = Field(default=None, description="Admin password for DDL/seeding")

    @property
    def formatted_firebase_private_key(self) -> Optional[str]:
        if not self.FIREBASE_PRIVATE_KEY:
            return None
        cleaned = self.FIREBASE_PRIVATE_KEY.strip().strip("'\"").replace("\\n", "\n")
        if "BEGIN PRIVATE KEY" not in cleaned:
            if cleaned.startswith("n") and "MII" in cleaned:
                cleaned = cleaned[1:]
            cleaned = f"-----BEGIN PRIVATE KEY-----\n{cleaned.strip()}\n-----END PRIVATE KEY-----\n"
        return cleaned

    # Firebase / Firestore
    FIREBASE_PROJECT_ID: Optional[str] = Field(default=None, description="Firebase Project ID")
    FIREBASE_CLIENT_EMAIL: Optional[str] = Field(default=None, description="Service account client email")
    FIREBASE_PRIVATE_KEY: Optional[str] = Field(default=None, description="Service account private key")
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = Field(default=None, description="Path to service account file")

    # Hosting & Runtime
    PORT: int = Field(default=8000, description="Web server listening port")
    ENVIRONMENT: str = Field(default="development", description="Runtime environment")
    CORS_ORIGINS: str = Field(
        default="http://localhost:5173,http://localhost:8000,http://127.0.0.1:8000",
        description="Comma-separated allowed origins"
    )

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def is_gemini_configured(self) -> bool:
        return bool(self.GOOGLE_API_KEY and self.GOOGLE_API_KEY.strip())

    @property
    def is_clickhouse_configured(self) -> bool:
        return bool(
            self.CLICKHOUSE_HOST
            and self.CLICKHOUSE_HOST.strip()
            and self.CLICKHOUSE_PASSWORD
            and self.CLICKHOUSE_PASSWORD.strip()
        )

    @property
    def is_firestore_configured(self) -> bool:
        has_sa_file = bool(self.GOOGLE_APPLICATION_CREDENTIALS and self.GOOGLE_APPLICATION_CREDENTIALS.strip())
        has_sa_env = bool(
            self.FIREBASE_PROJECT_ID
            and self.FIREBASE_CLIENT_EMAIL
            and self.FIREBASE_PRIVATE_KEY
        )
        return has_sa_file or has_sa_env

    def get_credential_status(self) -> Dict[str, Any]:
        """Safe status report returning booleans and missing variable names without exposing secrets."""
        missing_gemini = []
        if not self.is_gemini_configured:
            missing_gemini.append("GOOGLE_API_KEY")

        missing_clickhouse = []
        if not self.CLICKHOUSE_HOST:
            missing_clickhouse.append("CLICKHOUSE_HOST")
        if not self.CLICKHOUSE_PASSWORD:
            missing_clickhouse.append("CLICKHOUSE_PASSWORD")

        missing_firestore = []
        if not self.is_firestore_configured:
            if not self.GOOGLE_APPLICATION_CREDENTIALS:
                if not self.FIREBASE_PROJECT_ID:
                    missing_firestore.append("FIREBASE_PROJECT_ID")
                if not self.FIREBASE_CLIENT_EMAIL:
                    missing_firestore.append("FIREBASE_CLIENT_EMAIL")
                if not self.FIREBASE_PRIVATE_KEY:
                    missing_firestore.append("FIREBASE_PRIVATE_KEY")

        return {
            "gemini": {
                "configured": self.is_gemini_configured,
                "model": self.GEMINI_MODEL,
                "missing": missing_gemini,
            },
            "clickhouse": {
                "configured": self.is_clickhouse_configured,
                "host": self.CLICKHOUSE_HOST if self.CLICKHOUSE_HOST else None,
                "port": self.CLICKHOUSE_PORT,
                "database": self.CLICKHOUSE_DATABASE,
                "secure": self.CLICKHOUSE_SECURE,
                "missing": missing_clickhouse,
            },
            "firestore": {
                "configured": self.is_firestore_configured,
                "project_id": self.FIREBASE_PROJECT_ID if self.FIREBASE_PROJECT_ID else None,
                "missing": missing_firestore,
            },
        }


settings = Settings()
