from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except Exception:  # pragma: no cover
    from pydantic import BaseModel as BaseSettings  # type: ignore
    SettingsConfigDict = dict  # type: ignore


BYTES_PER_MEBIBYTE = 1024 * 1024
DEFAULT_MAX_UPLOAD_MIB = 25
DEFAULT_MAX_UPLOAD_BYTES = DEFAULT_MAX_UPLOAD_MIB * BYTES_PER_MEBIBYTE


class Settings(BaseSettings):
    """Application settings for the single-user production build.

    All configuration is read once through `get_settings()`. The runtime degrades gracefully to
    mock providers when API keys are missing, so the product still boots on first run, but the
    intended deployment supplies real keys via `.env`.
    """

    model_config = SettingsConfigDict(env_prefix="ATHENA_", env_file=".env", extra="ignore")

    # Core
    env: Literal["dev", "test", "docker", "prod"] = "dev"
    data_dir: Path = Field(default_factory=lambda: Path(".athena-data"))
    sqlite_path: Path | None = None
    export_dir: Path | None = None

    # Auth (single user — shared secret bearer token).  When unset in non-dev env the API rejects.
    api_key: str | None = None
    require_auth: bool = True

    # LLM
    llm_provider: Literal["mock", "openai", "anthropic", "deepseek", "openrouter", "gemma", "gemini"] = "mock"
    default_model: str = "mock-researcher"
    planner_model: str | None = None
    researcher_model: str | None = None
    writer_model: str | None = None
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    anthropic_api_key: str | None = None
    deepseek_api_key: str | None = None
    openrouter_api_key: str | None = None
    gemma_api_key: str | None = None  # alias for the Google AI Studio key when using Gemma
    google_api_key: str | None = None  # generic Google AI Studio key (works for Gemma + Gemini)
    gemma_base_url: str | None = None  # override for self-hosted vLLM / TGI / Ollama running Gemma
    llm_temperature: float = 0.2
    llm_timeout_sec: int = 60

    # Search
    search_provider: Literal["mock", "tavily", "duckduckgo"] = "mock"
    tavily_api_key: str | None = None
    search_max_results: int = 5
    search_cache_ttl_sec: int = 1800

    # Graph control
    use_langgraph: bool = False
    max_research_iterations: int = 2
    quality_threshold: float = 0.7
    max_parallel_researchers: int = 4
    hard_timeout_sec: int = 600
    max_budget_usd: float = 5.0

    # API
    allowed_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    rate_limit_per_minute: int = 30
    max_upload_bytes: int = DEFAULT_MAX_UPLOAD_BYTES

    # Legacy switches kept for backward compatibility
    use_real_llm: bool = False
    api_base_url: str = "http://localhost:8000"

    def ensure_dirs(self) -> Path:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if self.sqlite_path is None:
            self.sqlite_path = self.data_dir / "athena.sqlite3"
        if self.export_dir is None:
            self.export_dir = self.data_dir / "exports"
        self.export_dir.mkdir(parents=True, exist_ok=True)
        return self.data_dir

    def resolve_model(self, node: str) -> str:
        node_models = {
            "planner": self.planner_model,
            "researcher": self.researcher_model,
            "writer": self.writer_model,
        }
        return node_models.get(node) or self.default_model


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    # Backward-compat: if legacy use_real_llm flag is on but llm_provider still mock, default to openai.
    if settings.use_real_llm and settings.llm_provider == "mock":
        settings.llm_provider = "openai"
    # Auto-pick search provider when key present.
    if settings.tavily_api_key and settings.search_provider == "mock":
        settings.search_provider = "tavily"
    settings.ensure_dirs()
    return settings
