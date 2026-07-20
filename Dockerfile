FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src

RUN pip install --no-cache-dir -e .

COPY alembic.ini ./
COPY alembic ./alembic

EXPOSE 8000

CMD ["uvicorn", "llm_gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
