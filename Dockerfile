FROM python:3.12-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gdal-bin \
    libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
COPY configs ./configs
COPY migrations ./migrations
COPY alembic.ini ./

RUN pip install --no-cache-dir uv \
    && uv pip install --system --no-cache .

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "industrial_fire.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
