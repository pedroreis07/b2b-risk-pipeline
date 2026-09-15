# syntax=docker/dockerfile:1
FROM python:3.13-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev --no-editable

COPY main.py /app/
COPY src /app/src

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=README.md,target=README.md \
    uv sync --frozen --no-dev --no-editable

FROM python:3.13-slim-bookworm AS runner

RUN groupadd --system --gid 999 appgroup \
    && useradd --system --gid 999 --uid 999 --create-home --shell /bin/bash appuser

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app
COPY --chown=appuser:appgroup config /app/config
COPY --from=builder --chown=appuser:appgroup /app/.venv /app/.venv
RUN mkdir -p /app/data && chown -R appuser:appgroup /app/data
RUN mkdir -p /app/sorted && chown -R appuser:appgroup /app/sorted
USER appuser
CMD ["worker"]
