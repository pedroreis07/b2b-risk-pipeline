import asyncio
import json
import logging
from datetime import datetime, time
from zoneinfo import ZoneInfo

import httpx
import redis
from dateutil.relativedelta import relativedelta

from src.models import CnpjApiResponse, CnpjData
from src.utils import calc_company_age


logger = logging.getLogger(__name__)


async def _fetch_cnpj(cnpj: str, client: httpx.AsyncClient) -> dict:
    response = await client.get(f"https://minhareceita.org/{cnpj}")
    response.raise_for_status()
    api_data = CnpjApiResponse.model_validate(response.json())

    return CnpjData(
        cnpj=cnpj,
        status=api_data.descricao_situacao_cadastral,
        company_age=calc_company_age(api_data.data_inicio_atividade),
        capital_stock=api_data.capital_social,
    ).model_dump()


async def _fetch_all(cnpjs: list[str]) -> list[dict]:
    async with httpx.AsyncClient() as client:
        tasks = [_fetch_cnpj(cnpj, client) for cnpj in cnpjs]
        return await asyncio.gather(*tasks)


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

    if cnpjs_to_fetch:
        fetched_results = asyncio.run(_fetch_all(cnpjs_to_fetch))
        pipeline = redis_client.pipeline()

        for result in fetched_results:
            cnpj = result["cnpj"]
            cnpj_data[cnpj] = result
            pipeline.set(f"cnpjs:{cnpj}", json.dumps(result), nx=True, ex=exp)

        pipeline.execute()

    return cnpj_data
