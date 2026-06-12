"""12-factor configuration for the production agent."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field


def _csv_env(name: str, default: str) -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    host: str = field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    environment: str = field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    debug: bool = field(default_factory=lambda: _bool_env("DEBUG", False))

    app_name: str = field(default_factory=lambda: os.getenv("APP_NAME", "Production AI Agent"))
    app_version: str = field(default_factory=lambda: os.getenv("APP_VERSION", "1.0.0"))
    instance_id: str = field(default_factory=lambda: os.getenv("INSTANCE_ID", os.getenv("HOSTNAME", "local")))

    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "mock-llm"))

    agent_api_key: str = field(default_factory=lambda: os.getenv("AGENT_API_KEY", "dev-key-change-me"))
    allowed_origins: list[str] = field(default_factory=lambda: _csv_env("ALLOWED_ORIGINS", "*"))

    redis_url: str = field(default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    require_redis: bool = field(default_factory=lambda: _bool_env("REQUIRE_REDIS", False))

    rate_limit_per_minute: int = field(
        default_factory=lambda: int(os.getenv("RATE_LIMIT_PER_MINUTE", "10"))
    )
    rate_limit_window_seconds: int = field(
        default_factory=lambda: int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
    )

    monthly_budget_usd: float = field(
        default_factory=lambda: float(os.getenv("MONTHLY_BUDGET_USD", "10.0"))
    )
    input_price_per_1k_tokens: float = field(
        default_factory=lambda: float(os.getenv("INPUT_PRICE_PER_1K_TOKENS", "0.00015"))
    )
    output_price_per_1k_tokens: float = field(
        default_factory=lambda: float(os.getenv("OUTPUT_PRICE_PER_1K_TOKENS", "0.0006"))
    )

    history_ttl_seconds: int = field(
        default_factory=lambda: int(os.getenv("HISTORY_TTL_SECONDS", "2592000"))
    )
    max_history_messages: int = field(
        default_factory=lambda: int(os.getenv("MAX_HISTORY_MESSAGES", "20"))
    )

    def validate(self) -> Settings:
        logger = logging.getLogger(__name__)
        if self.environment.lower() == "production" and self.agent_api_key == "dev-key-change-me":
            raise ValueError("AGENT_API_KEY must be set for production")
        if self.rate_limit_per_minute <= 0:
            raise ValueError("RATE_LIMIT_PER_MINUTE must be positive")
        if self.monthly_budget_usd <= 0:
            raise ValueError("MONTHLY_BUDGET_USD must be positive")
        if not self.openai_api_key:
            logger.warning("OPENAI_API_KEY is empty; using the bundled mock LLM")
        return self


settings = Settings().validate()
