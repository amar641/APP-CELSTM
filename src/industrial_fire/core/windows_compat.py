"""
Windows compatibility helpers.

psycopg's async driver requires a selector-based event loop; Windows
defaults asyncio to ProactorEventLoop, which it can't use. Call
`ensure_selector_event_loop()` once, before `asyncio.run(...)`, in any
script/entrypoint that opens an async DB session.
"""

from __future__ import annotations

import asyncio
import sys


def ensure_selector_event_loop() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
