from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CPV_",
        env_file=(".env", "../../.env"),
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "CPV Kanban AI"
    mock_mode: bool = True
    app_db_name: str = "cpv_app"
    cors_origins: str = "http://localhost:5173"
    cache_ttl_seconds: int = Field(default=300, ge=1)
    max_execution_retries: int = Field(default=2, ge=0, le=10)

    redis_url: str | None = None
    redis_cluster_nodes: str | None = None

    tidb_api_url: str | None = None
    tidb_api_token: str | None = None
    tidb_read_replica_dsn: str = "mock://read-replica"
    tidb_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("CPV_TIDB_URL", "TIDB_URL", "DATABASE_URL"),
    )
    tidb_require_ssl: bool = True

    oauth_issuer_url: str | None = None
    oauth_client_id: str | None = None
    oauth_dynamic_registration_url: str | None = None

    clickup_free_daily_quota: int = 50
    clickup_pro_daily_quota: int = 300
    service_account_rate_limit_exempt: bool = True

    default_git_commit_hash: str = "local-dev"
    groq_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GROQ_API_KEY", "CPV_GROQ_API_KEY"),
    )
    groq_model: str = Field(
        default="llama-3.3-70b-versatile",
        validation_alias=AliasChoices("GROQ_MODEL", "CPV_GROQ_MODEL"),
    )

    llm_provider: str = Field(
        default="groq",
        validation_alias=AliasChoices("LLM_PROVIDER", "CPV_LLM_PROVIDER"),
    )
    ollama_model: str = Field(
        default="llama3.1",
        validation_alias=AliasChoices("OLLAMA_MODEL", "CPV_OLLAMA_MODEL"),
    )
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        validation_alias=AliasChoices("OLLAMA_BASE_URL", "CPV_OLLAMA_BASE_URL"),
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
