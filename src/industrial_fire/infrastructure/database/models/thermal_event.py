from __future__ import annotations

import uuid
from datetime import datetime

from geoalchemy2 import Geography
from sqlalchemy import DateTime, Float, Index, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from industrial_fire.infrastructure.database.models.base import Base


class ThermalEventModel(Base):
    __tablename__ = "thermal_events"
    __table_args__ = (
        Index("ix_thermal_events_location", "location", postgresql_using="gist"),
        Index("ix_thermal_events_acquired_at", "acquired_at"),
        Index(
            "uq_thermal_events_natural_key",
            "acquired_at",
            "source",
            "location",
            unique=True,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    location: Mapped[str] = mapped_column(Geography(geometry_type="POINT", srid=4326), nullable=False)
    brightness_kelvin: Mapped[float] = mapped_column(Float, nullable=False)
    frp_mw: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[str] = mapped_column(String(16), nullable=False)
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
