import asyncio
import json
import logging
import math
from datetime import datetime, time
from itertools import batched

import httpx
from dateutil.relativedelta import relativedelta
from pydantic import BaseModel
from tenacity import (
    before_sleep_log,
    retry,
    stop_after_attempt,
    wait_exponential_jitter,
)

from src.config import SAO_PAULO_TZ, settings
from src.infra import AsyncHttpManager, create_http_manager, create_redis_client


logger = logging.getLogger(__name__)


class CnpjApiResponse(BaseModel):
    descricao_situacao_cadastral: str
    data_inicio_atividade: str
    capital_social: float


class CnpjData(BaseModel):
    cnpj: str
    status: str
    activity_start_date: str
    capital_stock: float


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=1, max=10),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
async def fetch_cnpj(
    cnpj: str, client: httpx.AsyncClient, sem: asyncio.Semaphore
) -> dict:
    async with sem:
        response = await client.get(
            f"https://minhareceita.org/{cnpj}",
            timeout=settings.api_call_timeout,
        )
        response.raise_for_status()
        api_data = CnpjApiResponse.model_validate(response.json())

        return CnpjData(
            cnpj=cnpj,
            status=api_data.descricao_situacao_cadastral,
            activity_start_date=api_data.data_inicio_atividade,
            capital_stock=api_data.capital_social,
        ).model_dump()


async def fetch_all(cnpjs: list[str], http_manager: AsyncHttpManager) -> list[dict]:
    sem = asyncio.Semaphore(settings.api_semaphore_limit)
    client = http_manager.get_client()
    fetched = []
    total_chunks = math.ceil(len(cnpjs) / 2000)

    for idx, chunk in enumerate(batched(cnpjs, 2000, strict=False), 1):
        logger.info("Fetching chunk %d/%d (%d CNPJs)", idx, total_chunks, len(chunk))
        tasks = [fetch_cnpj(cnpj, client, sem) for cnpj in chunk]
        chunk_results = await asyncio.gather(*tasks)
        fetched.extend(chunk_results)

    return fetched


def cache_expiration() -> int:
    now = datetime.now(tz=SAO_PAULO_TZ)

    if now.day < 15:
        expiration_date = now.replace(day=15)
    else:
        expiration_date = now.replace(day=1) + relativedelta(day=15, months=1)

    expiration_date = datetime.combine(expiration_date, time.min, tzinfo=SAO_PAULO_TZ)
    ttl = int((expiration_date - now).total_seconds())

    ttl = max(ttl, 1)
    logger.debug("CNPJ cache TTL: %d seconds (expiry=%s)", ttl, expiration_date)
    return ttl


def fetch_cnpj_data_batch(cnpj_set: set[str]) -> dict[str, dict]:
    if not cnpj_set:
        return {}

    logger.info("Enriching %d unique CNPJs", len(cnpj_set))

    redis_client = create_redis_client()
    http_manager = create_http_manager()

    all_cnpjs = list(cnpj_set)
    cache_keys = [f"cnpjs:{cnpj}" for cnpj in all_cnpjs]
    cached_values = redis_client.mget(cache_keys)

    cnpj_data: dict[str, dict] = {}
    cnpjs_to_fetch: list[str] = []

    for cnpj, cached in zip(all_cnpjs, cached_values, strict=True):
        if cached:
            cnpj_data[cnpj] = json.loads(cached)
        else:
            cnpjs_to_fetch.append(cnpj)

    logger.info(
        "Redis cache: %d hits, %d misses (%.1f%% hit rate)",
        len(cnpj_data),
        len(cnpjs_to_fetch),
        len(cnpj_data) / len(all_cnpjs) * 100 if all_cnpjs else 0,
    )

    if not cnpjs_to_fetch:
        return cnpj_data

    fetched_results: list[dict] = http_manager.run(
        fetch_all(cnpjs_to_fetch, http_manager)
    )

    logger.info("Fetched %d CNPJs from API", len(fetched_results))

    exp = cache_expiration()
    pipeline = redis_client.pipeline()

    for result in fetched_results:
        cnpj = result["cnpj"]
        cnpj_data[cnpj] = result
        pipeline.set(f"cnpjs:{cnpj}", json.dumps(result), nx=True, ex=exp)

    pipeline.execute()

    return cnpj_data
