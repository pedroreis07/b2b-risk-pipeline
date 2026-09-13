import asyncio
import atexit
import logging
from collections.abc import Coroutine
from functools import lru_cache
from typing import Any

import httpx

from src.config import settings


logger = logging.getLogger(__name__)


class AsyncHttpManager:
    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._client: httpx.AsyncClient | None = None

    def get_loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

        return self._loop

    def get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            logger.info(
                "Creating HTTP client (max_connections=%d, keepalive_expiry=%.0fs)",
                settings.api_semaphore_limit,
                settings.api_keepalive_expiry,
            )
            limits = httpx.Limits(
                max_connections=settings.api_semaphore_limit,
                max_keepalive_connections=settings.api_semaphore_limit,
                keepalive_expiry=settings.api_keepalive_expiry,
            )
            self._client = httpx.AsyncClient(
                limits=limits, timeout=httpx.Timeout(settings.api_call_timeout)
            )

        return self._client

    def run(self, cr: Coroutine) -> Any:
        return self.get_loop().run_until_complete(cr)

    def close(self) -> None:
        logger.info("Closing HTTP manager")
        if self._client is not None and not self._client.is_closed:
            self.run(self._client.aclose())

        if self._loop is not None and not self._loop.is_closed():
            self._loop.close()


@lru_cache(maxsize=1)
def create_http_manager() -> AsyncHttpManager:
    logger.info("Creating HTTP manager")
    manager = AsyncHttpManager()
    atexit.register(manager.close)
    return manager
