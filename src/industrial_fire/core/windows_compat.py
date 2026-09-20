"""
Windows compatibility helpers.

psycopg's async driver requires a selector-based event loop; Windows
defaults asyncio to ProactorEventLoop, which it can't use.

`ensure_selector_event_loop()` — call once, before `asyncio.run(...)`, in
any plain script/entrypoint that opens an async DB session (every
`scripts/*.py` does this). It works there because bare `asyncio.run()`
honors `asyncio.get_event_loop_policy()`.

`api/main.py`'s `uvicorn.run(..., loop=...)` needs a different fix:
uvicorn >=0.36 ignores the event loop policy entirely and instead calls
`asyncio.run(..., loop_factory=...)` with its own factory that hardcodes
`ProactorEventLoop` on win32 (see `uvicorn.loops.asyncio.asyncio_loop_factory`).
Overriding it means pointing uvicorn's `loop=` at an import string for a
zero-arg callable that returns a loop instance — `asyncio.SelectorEventLoop`
itself already is one, so `api/main.py` passes `loop="asyncio:SelectorEventLoop"`
directly (uvicorn's own import-string convention for a custom loop) rather
than needing a wrapper function here.
"""

from __future__ import annotations

import asyncio
import sys


def ensure_selector_event_loop() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
