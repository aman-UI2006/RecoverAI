from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    """
    RecoverAI System Settings & Configuration Loader.
    Parses environment variables and provides structured defaults.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Core System Settings
    PROJECT_NAME: str = "RecoverAI"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"

    # Database Configuration
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/recoverai_db"
    SYNC_DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/recoverai_db"

    # Redis & Celery Configuration
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # Razorpay API Credentials (Test Mode)
    RAZORPAY_KEY_ID: str = Field(default="rzp_test_mock_key_id", description="Razorpay Test Key ID")
    RAZORPAY_KEY_SECRET: str = Field(default="mock_key_secret_12345", description="Razorpay Test Key Secret")
    RAZORPAY_WEBHOOK_SECRET: str = Field(default="mock_webhook_secret_67890", description="Razorpay Webhook Signing Secret")

    # LLM / AI Engine API Keys
    OPENAI_API_KEY: Optional[str] = Field(default=None, description="OpenAI API Key for LLM Recommender")

    # Merchant Default Policy Thresholds (Version 1.0)
    DEFAULT_MAX_RECOVERY_AMOUNT: float = 50000.00
    DEFAULT_MIN_ENRV_THRESHOLD: float = 0.15
    DEFAULT_MAX_RECOVERY_ATTEMPTS: int = 3
    DEFAULT_ATTRIBUTION_WINDOW_HOURS: int = 72
    DEFAULT_COOLDOWN_HOURS: int = 24


# Singleton settings instance
settings = Settings()
