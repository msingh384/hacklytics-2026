from functools import lru_cache
from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    api_prefix: str = "/api"
    cors_origins: str = "http://localhost:5173"

    supabase_url: Optional[str] = None
    supabase_service_role_key: Optional[str] = None

    omdb_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None

    actian_address: str = "127.0.0.1:50051"
    actian_collection: str = "review_chunks"
    enable_actian: bool = False

    wikipedia_user_agent: str = "DirectorsCut/1.0 (contact@example.com)"
    request_timeout_seconds: int = 20

    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = 384

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @field_validator("cors_origins")
    @classmethod
    def _normalize_cors(cls, value: str) -> str:
        return ",".join([item.strip() for item in value.split(",") if item.strip()])

    @property
    def cors_origins_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def has_supabase(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_role_key)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
