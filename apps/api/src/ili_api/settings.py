from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ILI_", env_file=".env", extra="ignore")

    steam_timeout_seconds: float = 10.0
    steam_cache_ttl_seconds: int = 300
    steam_user_agent: str = "IndieLaunchIntelligence/0.1"
    cors_origins: str = "http://localhost:5173"
    catalog_path: Path = Path(__file__).resolve().parents[4] / "data/processed/steam-catalog.sqlite"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
