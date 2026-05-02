"""Configuration management for MindFlow backend.

Uses pydantic-settings to load configuration from environment variables
and an optional .env file. All settings can be overridden via env vars
prefixed with MINDFLOW_ (except ANTHROPIC_API_KEY which is read directly).
"""

from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment and .env file.

    Attributes:
        anthropic_api_key: API key for Anthropic Claude. Required for LLM features.
        model_name: Claude model identifier to use for generation.
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

    # Anthropic API key - read without prefix for convenience
    anthropic_api_key: Optional[str] = None

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
        """Load settings, also checking ANTHROPIC_API_KEY directly.

        This allows users to set either MINDFLOW_ANTHROPIC_API_KEY or
        the standard ANTHROPIC_API_KEY environment variable.
        """
        import os

        settings = cls()
        # Fall back to the standard env var if the prefixed one is not set
        if not settings.anthropic_api_key:
            settings.anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")
        return settings


# Module-level singleton for convenience
settings = Settings.load()
