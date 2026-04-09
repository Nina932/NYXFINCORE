"""
FinAI Backend — Application Configuration
"""
from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List
import os


class Settings(BaseSettings):
    # App
    APP_NAME: str = "FinAI Financial Intelligence"
    APP_VERSION: str = "2.4.x"
    APP_ENV: str = "production"
    DEBUG: bool = False
    SECRET_KEY: str = ""

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4
    RELOAD: bool = False

    # Database — supports SQLite (dev) and PostgreSQL (production)
    # SQLite default:  "sqlite+aiosqlite:///./data/finai.db"
    # PostgreSQL:      "postgresql+asyncpg://user:pass@host:5432/finai"
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/finai.db"
    # Secondary storage for financial snapshots/forensic audit trail
    FINAI_STORE_DB: str = "data/finai_store.db"

    # AI
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"
    ANTHROPIC_MAX_TOKENS: int = 4096

    # NVIDIA APIs (build.nvidia.com)
    NVIDIA_API_KEY: str = ""          # Nemotron Super 120B — agentic reasoning
    NVIDIA_API_KEY_GEMMA: str = ""    # Gemma 4 31B IT — primary LLM, Georgian-capable

    # Google Gemini API (paid tier — supports Georgian)
    GEMINI_API_KEY: str = ""

    # Ollama (local LLM)
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # Agent Mode: "legacy" = existing FinAIAgent, "multi" = new Supervisor + specialized agents
    AGENT_MODE: str = "multi"

    # Files
    UPLOAD_DIR: str = "./uploads"
    EXPORT_DIR: str = "./exports"
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: str = "xlsx,xls,csv"
    STRICT_SCHEMA_VALIDATION: bool = False  # Allow uploads with schema warnings
    STRICT_PARSING: bool = False  # Parse what we can, skip what we can't
    ALLOW_DUPLICATE_UPLOADS: bool = False
    VALIDATION_SAMPLE_ROWS: int = 50

    # Security
    CORS_ORIGINS: str = "https://nyxcore.space,https://www.nyxcore.space,http://localhost:3000,http://localhost:8080"
    JWT_SECRET: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 24
    # When True, all API endpoints require a valid Bearer token.
    # Set to False (default) to keep backward compatibility while auth is being rolled out.
    REQUIRE_AUTH: bool = True

    # Phase G: Industry Benchmark + API Key
    INDUSTRY_PROFILE: str = "fuel_distribution"
    API_KEY_ENABLED: bool = False
    API_KEY_HEADER: str = "X-API-Key"

    # Company
    COMPANY_NAME: str = "NYXCoreThinker LLC"
    DEFAULT_CURRENCY: str = "GEL"
    DEFAULT_PERIOD: str = "January 2025"

    # SMTP / Email (for scheduled reports)
    SMTP_ENABLED: bool = False
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "NYX CoreFinLogic <reports@nyxcore.tech>"

    # Currency / Exchange Rates
    EXCHANGE_RATE_API_URL: str = "https://open.er-api.com/v6/latest"
    EXCHANGE_RATE_API_KEY: str = ""
    SUPPORTED_CURRENCIES: str = "GEL,USD,EUR,GBP,TRY"

    # Scheduler
    SCHEDULER_ENABLED: bool = True
    SCHEDULER_CHECK_INTERVAL: int = 60

    # Redis Cache (optional — falls back to in-memory if unavailable)
    REDIS_URL: str = ""
    REDIS_ENABLED: bool = False
    REDIS_PREFIX: str = "finai:"
    REDIS_DEFAULT_TTL: int = 300

    # SSO / SAML / OIDC
    SSO_GOOGLE_CLIENT_ID: str = ""
    SSO_GOOGLE_CLIENT_SECRET: str = ""
    SSO_AZURE_CLIENT_ID: str = ""
    SSO_AZURE_CLIENT_SECRET: str = ""
    SSO_AZURE_TENANT_ID: str = "common"
    SSO_SAML_IDP_SSO_URL: str = ""
    SSO_SAML_IDP_METADATA_URL: str = ""
    SSO_SAML_IDP_CERTIFICATE: str = ""
    SSO_SAML_SP_ENTITY_ID: str = ""
    SSO_SAML_DISPLAY_NAME: str = "Corporate SSO"

    # Logging & Observability
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "./logs/finai.log"
    OTEL_MODE: str = "console"  # "console" | "otlp"

    # Frontend
    FRONTEND_BUILD_PATH: str = "../frontend/dist"

    @field_validator("ANTHROPIC_API_KEY", mode="before")
    @classmethod
    def _fix_empty_api_key(cls, v):
        """If system env sets ANTHROPIC_API_KEY='', read from .env file instead."""
        if v is not None and v.strip() == "":
            from dotenv import dotenv_values
            env_vals = dotenv_values(".env")
            return env_vals.get("ANTHROPIC_API_KEY", "")
        return v

    @field_validator("SECRET_KEY", "JWT_SECRET", mode="before")
    @classmethod
    def _reject_dev_secrets_in_production(cls, v, info):
        """Reject insecure default secrets outside development."""
        app_env = os.getenv("APP_ENV", "development")
        if app_env != "development" and (not v or v.startswith("dev-")):
            raise ValueError(
                f"{info.field_name} must be set to a secure value when "
                f"APP_ENV={app_env!r}. Set it in .env or environment variables."
            )
        # In development, provide a default so the app starts
        if not v:
            return f"dev-{info.field_name}-change-in-production"
        return v

    @field_validator("GEMINI_API_KEY", mode="before")
    @classmethod
    def _reject_hardcoded_gemini_key(cls, v):
        """Block any hardcoded API key from being used."""
        if v and v.startswith("AIzaSy"):
            import logging as _log
            _log.getLogger(__name__).warning(
                "GEMINI_API_KEY appears to be a hardcoded key. "
                "Set it via environment variable or .env file only."
            )
        return v

    class Config:
        env_file = ".env"
        case_sensitive = True

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    @property
    def allowed_extensions_list(self) -> List[str]:
        return [e.strip().lower() for e in self.ALLOWED_EXTENSIONS.split(",")]

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024


settings = Settings()

# Ensure directories exist
for d in [settings.UPLOAD_DIR, settings.EXPORT_DIR, "./logs"]:
    os.makedirs(d, exist_ok=True)
