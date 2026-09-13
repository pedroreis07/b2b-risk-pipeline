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
    pg_trx_work_mem_mb: float = Field(default=4.0, ge=4.0, alias="PG_TRX_WORK_MEM_MB")

    redis_dsn: RedisDsn = Field(alias="REDIS_DSN")
    redis_pool_max_size: int = Field(default=10, ge=1, alias="REDIS_POOL_MAX_SIZE")
    redis_pool_timeout: int = Field(default=20, ge=20, alias="REDIS_POOL_TIMEOUT")
    redis_health_check_interval: int = Field(
        default=30, ge=30, alias="REDIS_HEALTH_CHECK_INTERVAL"
    )
    redis_socket_timeout: float = Field(
        default=5.0, ge=5.0, alias="REDIS_SOCKET_TIMEOUT"
    )
    redis_socket_connect_timeout: float = Field(
        default=3.0, ge=3.0, alias="REDIS_SOCKET_CONNECT_TIMEOUT"
    )

    rules_path: Path = Field(
        default=BASE_DIR / "config" / "rules.yaml", alias="RULES_PATH"
    )
    data_dir: Path = Field(default=BASE_DIR / "data", alias="DATA_DIR")
    batch_size: int = Field(default=50_000, ge=1, alias="BATCH_SIZE")
    api_semaphore_limit: int = Field(default=30, alias="API_CALL_SEMAPHORE_LIMIT")
    api_call_timeout: int = Field(default=10, alias="API_CALL_TIMEOUT")
    api_keepalive_expiry: float = Field(
        default=30.0, ge=30.0, alias="API_KEEPALIVE_EXPIRY"
    )

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", frozen=True
    )


settings = Settings()  # type: ignore
