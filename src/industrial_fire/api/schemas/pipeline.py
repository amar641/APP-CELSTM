from __future__ import annotations

from pydantic import BaseModel


class PipelineStatusResponse(BaseModel):
    running: bool
    last_poll_at: str | None
    events_seen_last_tick: int
    new_hotspots_last_tick: int
    total_hotspots_processed: int
    last_error: str | None
