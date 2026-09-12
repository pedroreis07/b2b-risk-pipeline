from pathlib import Path

from pydantic import (
    Field,
    RedisDsn,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).parent.parent


class Settings(BaseSettings):
    redis_dsn: RedisDsn = Field(alias="REDIS_DSN")
    rules_path: Path = Field(
        default=BASE_DIR / "config" / "rules.yaml", alias="RULES_PATH"
    )
    data_dir: Path = Field(default=BASE_DIR / "data", alias="DATA_DIR")
    output_dir: Path = Field(default=BASE_DIR / "output", alias="OUTPUT_DIR")

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", frozen=True, extra="ignore"
    )


settings = Settings()  # type: ignore[call-arg]
