# Multi-stage build: builder installs deps + warms tiktoken cache; runtime only copies /app/.venv
ARG BASE_IMAGE=docker.m.daocloud.io/library/python:3.12-slim

# ---------- builder：施工 ----------
FROM ${BASE_IMAGE} AS builder

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev --no-install-project

ENV TIKTOKEN_CACHE_DIR=/opt/tiktoken-cache
RUN mkdir -p ${TIKTOKEN_CACHE_DIR} \
    && /app/.venv/bin/python -c "import tiktoken; tiktoken.get_encoding('cl100k_base')"

# ---------- runtime：只搬成品 ----------
FROM ${BASE_IMAGE}

ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TIKTOKEN_CACHE_DIR=/opt/tiktoken-cache

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /opt/tiktoken-cache /opt/tiktoken-cache

RUN groupadd --system app \
    && useradd --system --gid app --no-create-home --shell /usr/sbin/nologin app

WORKDIR /app
RUN mkdir -p /app/data && chown -R app:app /app/data
COPY --chown=app:app gateway ./gateway

USER app

EXPOSE 8100
HEALTHCHECK --interval=30s --timeout=3s --start-period=8s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8100/health')"
CMD ["uvicorn", "gateway.main:app", "--host", "0.0.0.0", "--port", "8100", "--no-access-log"]
