#!/usr/bin/env python
"""
Delete thermal events (and cascading classification/risk/satellite-image
rows) older than a retention window. Run periodically to bound table/index
growth — FIRMS free-tier history is shallow anyway, so nothing is lost
that couldn't be re-ingested.

    uv run python scripts/maintenance/cleanup_old_events.py --retain-days 365
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta

from sqlalchemy import delete

from industrial_fire.core.logging import get_logger
from industrial_fire.core.windows_compat import ensure_selector_event_loop
from industrial_fire.infrastructure.database.models.thermal_event import ThermalEventModel
from industrial_fire.infrastructure.database.session import get_session_factory

logger = get_logger(__name__)


async def main(retain_days: int) -> None:
    cutoff = datetime.utcnow() - timedelta(days=retain_days)
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            delete(ThermalEventModel).where(ThermalEventModel.acquired_at < cutoff)
        )
        await session.commit()

    logger.info("deleted %d thermal events older than %s", result.rowcount, cutoff.isoformat())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--retain-days", type=int, default=365)
    args = parser.parse_args()
    ensure_selector_event_loop()
    asyncio.run(main(args.retain_days))
