"""Closed time interval used for history windows (persistence checks, weather joins, STAC search)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True, slots=True)
class TimeRange:
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.start > self.end:
            raise ValueError(f"start ({self.start}) must be <= end ({self.end})")

    @classmethod
    def last_n_days(cls, n: int, *, now: datetime | None = None) -> TimeRange:
        end = now or datetime.utcnow()
        return cls(start=end - timedelta(days=n), end=end)

    def contains(self, moment: datetime) -> bool:
        return self.start <= moment <= self.end

    @property
    def duration_days(self) -> float:
        return (self.end - self.start).total_seconds() / 86400.0
