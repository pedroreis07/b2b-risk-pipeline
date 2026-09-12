import asyncio
import json
import logging
from datetime import datetime, time
from itertools import batched
from zoneinfo import ZoneInfo

import httpx
import redis
from dateutil.relativedelta import relativedelta
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential_jitter,
)

from src.config import settings
from src.models import CnpjApiResponse, CnpjData
from src.services.http import AsyncHttpManager
from src.utils import calc_company_age


logger = logging.getLogger(__name__)


@retry(stop=stop_after_attempt(3), wait=wait_exponential_jitter(initial=1, max=10))
async def _fetch_cnpj(
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
            company_age=calc_company_age(api_data.data_inicio_atividade),
            capital_stock=api_data.capital_social,
        ).model_dump()


async def _fetch_all(cnpjs: list[str], http_manager: AsyncHttpManager) -> list[dict]:
    sem = asyncio.Semaphore(settings.api_semaphore_limit)
    client = http_manager.get_client()
    fetched = []

    for chunk in batched(cnpjs, 2000, strict=False):
        tasks = [_fetch_cnpj(cnpj, client, sem) for cnpj in chunk]
        chunk_results = await asyncio.gather(*tasks)
        fetched.extend(chunk_results)

    return fetched


def _cache_expiration() -> int:
    tz = ZoneInfo("America/Sao_Paulo")
    now = datetime.now(tz)

    if now.day < 15:
        expiration_date = now.replace(day=15)
    else:
        expiration_date = now.replace(day=1) + relativedelta(day=15, months=1)

    expiration_date = datetime.combine(expiration_date, time.min, tzinfo=tz)
    ttl = int((expiration_date - now).total_seconds())

    return max(ttl, 1)


def enrich_cnpjs(
    cnpj_set: set[str],
    redis_client: redis.Redis,
    http_manager: AsyncHttpManager,
) -> dict[str, dict]:
    exp = _cache_expiration()

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

    fetched_results: list[dict] = http_manager.run(
        _fetch_all(cnpjs_to_fetch, http_manager)
    )

    pipeline = redis_client.pipeline()

    for result in fetched_results:
        cnpj = result["cnpj"]
        cnpj_data[cnpj] = result
        pipeline.set(f"cnpjs:{cnpj}", json.dumps(result), nx=True, ex=exp)

    pipeline.execute()

    return cnpj_data
