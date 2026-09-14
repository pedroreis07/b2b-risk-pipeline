from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import (
    Field,
    PostgresDsn,
    RedisDsn,
)
from pydantic_settings import BaseSettings


BASE_DIR = Path(__file__).parent.parent
SAO_PAULO_TZ = ZoneInfo("America/Sao_Paulo")


class Settings(BaseSettings):
    pg_dsn: PostgresDsn = Field(alias="PG_DSN")
    pg_pool_max_idle: int = Field(default=30, ge=30, alias="PG_POOL_MAX_IDLE")
    pg_trx_work_mem_mb: float = Field(default=4.0, ge=4.0, alias="PG_TRX_WORK_MEM_MB")

    redis_dsn: RedisDsn = Field(alias="REDIS_DSN")
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

    rules_path: Path = Field(alias="RULES_PATH")
    data_dir: Path = Field(alias="DATA_DIR")
    batch_size: int = Field(default=50_000, ge=1, alias="BATCH_SIZE")
    api_semaphore_limit: int = Field(default=30, alias="API_CALL_SEMAPHORE_LIMIT")
    api_call_timeout: int = Field(default=10, alias="API_CALL_TIMEOUT")
    api_keepalive_expiry: float = Field(
        default=30.0, ge=30.0, alias="API_KEEPALIVE_EXPIRY"
    )


settings = Settings()
