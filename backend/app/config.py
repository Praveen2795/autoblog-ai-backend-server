"""
Application Configuration
Loads settings from environment variables with secure defaults.
"""
from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # API Configuration
    APP_NAME: str = "AutoBlog AI API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # Security - REQUIRED in production
    GEMINI_API_KEY: str = ""
    JWT_SECRET_KEY: str = "change-me-in-production-use-openssl-rand-hex-32"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 60 * 24  # 24 hours
    
    # CORS Settings
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]
    
    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    
    # Gemini Model Configuration
    GEMINI_FLASH_MODEL: str = "gemini-2.5-flash"
    GEMINI_PRO_MODEL: str = "gemini-2.5-pro"
    GEMINI_IMAGE_MODEL: str = "gemini-2.0-flash-exp"
    
    # Research Configuration
    MAX_RESEARCH_RETRIES: int = 5
    MAX_REFINEMENT_ITERATIONS: int = 5
    QUALITY_THRESHOLD: int = 90
    
    # Email Pipeline Configuration
    EMAIL_ADDRESS: str = ""  # Email address for sending/receiving
    EMAIL_PASSWORD: str = ""  # App-specific password (for Gmail, use App Password)
    EMAIL_IMAP_SERVER: str = "imap.gmail.com"  # IMAP server for receiving
    EMAIL_IMAP_PORT: int = 993
    EMAIL_SMTP_SERVER: str = "smtp.gmail.com"  # SMTP server for sending
    EMAIL_SMTP_PORT: int = 465
    EMAIL_CHECK_INTERVAL: int = 60  # Seconds between inbox checks
    EMAIL_AUTO_START: bool = False  # Auto-start email pipeline on server start
    EMAIL_ALLOWED_SENDERS: str = ""  # Comma-separated whitelist (empty = process all)
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    Uses lru_cache for performance - settings are loaded once.
    """
    return Settings()


# Export settings instance for convenience
settings = get_settings()
