"""Configuration management for MindFlow backend.

Uses pydantic-settings to load configuration from environment variables
and an optional .env file. All settings can be overridden via env vars.
Supports both Anthropic (Claude) and OpenAI-compatible (Moonshot) providers.
"""

from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment and .env file.

    Attributes:
        llm_provider: LLM provider - "anthropic" or "openai".
        llm_api_key: API key for the LLM provider.
        llm_base_url: Base URL for OpenAI-compatible APIs (ignored for Anthropic).
        model_name: Model identifier (e.g. claude-sonnet-4-20250514 or kimi-k2.6).
        server_host: Host address the server binds to.
        server_port: Port number the server listens on.
        max_tokens: Maximum tokens for a single LLM generation call.
        context_history_size: Number of recent conversation turns to retain.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="MINDFLOW_",
        extra="ignore",
    )

    # Provider: "anthropic" or "openai"
    llm_provider: str = "anthropic"

    # API key - no prefix for convenience (works with LLM_API_KEY, ANTHROPIC_API_KEY, etc.)
    llm_api_key: Optional[str] = None

    # Base URL for OpenAI-compatible APIs
    llm_base_url: Optional[str] = None

    # Model configuration
    model_name: str = "claude-sonnet-4-20250514"
    max_tokens: int = 512

    # Server configuration
    server_host: str = "127.0.0.1"
    server_port: int = 8765

    # Context configuration
    context_history_size: int = 20

    @classmethod
    def load(cls) -> "Settings":
        """Load settings with fallback for legacy env vars."""
        import os

        settings = cls()

        # Fall back to legacy ANTHROPIC_API_KEY if no LLM_API_KEY is set
        if not settings.llm_api_key:
            settings.llm_api_key = os.environ.get("ANTHROPIC_API_KEY")

        # Fall back to MINDFLOW_LLM_MODEL env var for model_name
        env_model = os.environ.get("MINDFLOW_LLM_MODEL")
        if env_model:
            settings.model_name = env_model

        return settings


# Module-level singleton for convenience
settings = Settings.load()
