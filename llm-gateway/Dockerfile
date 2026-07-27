FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app

RUN pip install --no-cache-dir -e .

COPY alembic.ini ./
COPY alembic ./alembic

EXPOSE 8000

# Railway (and most PaaS) inject $PORT and expect the app to bind to it;
# docker-compose doesn't set it, so we default to 8000 for local use.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
