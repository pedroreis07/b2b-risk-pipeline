from pathlib import Path

from pydantic import (
    Field,
    PostgresDsn,
    RedisDsn,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).parent.parent


class Settings(BaseSettings):
    pg_dsn: PostgresDsn = Field(alias="PG_DSN")
    pg_pool_max_size: int = Field(default=1, ge=1, alias="PG_POOL_MAX_SIZE")
    pg_pool_min_size: int = Field(default=0, ge=0, alias="PG_POOL_MIN_SIZE")
    pg_pool_max_idle: int = Field(default=30, ge=30, alias="PG_POOL_MAX_IDLE")

    redis_dsn: RedisDsn = Field(alias="REDIS_DSN")

    rules_path: Path = Field(
        default=BASE_DIR / "config" / "rules.yaml", alias="RULES_PATH"
    )
    data_dir: Path = Field(default=BASE_DIR / "data", alias="DATA_DIR")

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", frozen=True, extra="ignore"
    )


settings = Settings()  # type: ignore[call-arg]
