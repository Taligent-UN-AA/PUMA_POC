"""
Configuration settings for TALI Minimal Pipeline
Loads settings from .env file
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from .env"""
    
    # OpenAI settings
    openai_api_key: str
    openai_model: str = "gpt-4o"
    openai_temperature: float = 0.1
    openai_max_tokens: int = 4000
    
    # Langfuse settings (opcional - para observabilidad)
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"  # o tu instancia self-hosted
    langfuse_enabled: bool = False  # Activar/desactivar Langfuse
    
    # Application settings
    log_level: str = "INFO"
    output_dir: str = "minimal/output"
    csv_separator: str = ";"
    csv_encoding: str = "utf-8"
    date_format: str = "%d/%m/%Y"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from .env


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
