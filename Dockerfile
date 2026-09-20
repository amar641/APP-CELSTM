FROM node:20-slim AS frontend-build

WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build


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
# Built by the frontend-build stage above — served by StaticFiles in
# api/main.py, same container, no separate frontend service.
COPY --from=frontend-build /frontend/dist ./frontend/dist

RUN pip install --no-cache-dir uv \
    && uv pip install --system --no-cache .

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["python", "-m", "industrial_fire.api.main"]
