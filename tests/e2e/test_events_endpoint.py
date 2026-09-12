"""
End-to-end test against the running API. Requires Postgres + Qdrant
(`docker compose up -d postgres qdrant`) and a valid `FIRMS_MAP_KEY` in
the test environment — skipped by default so `pytest` works without
external services.

    RUN_E2E=1 uv run pytest tests/e2e -v
"""

import os

import pytest
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_E2E") != "1", reason="set RUN_E2E=1 with Postgres/Qdrant running to enable"
)


@pytest.mark.asyncio
async def test_health_endpoint():
    from industrial_fire.api.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_events_endpoint_returns_sorted_by_risk():
    from industrial_fire.api.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/events")
    assert resp.status_code == 200
    body = resp.json()
    risk_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    ranks = [risk_order[e["risk_level"]] for e in body]
    assert ranks == sorted(ranks)
