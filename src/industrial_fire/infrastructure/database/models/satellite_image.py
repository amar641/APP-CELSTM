from __future__ import annotations

import uuid
from datetime import datetime

from geoalchemy2 import Geography
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from industrial_fire.infrastructure.database.models.base import Base


class SatelliteImageModel(Base):
    __tablename__ = "satellite_images"
    __table_args__ = (Index("ix_satellite_images_footprint", "footprint", postgresql_using="gist"),)

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    thermal_event_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("thermal_events.id", ondelete="CASCADE"), nullable=False
    )
    stac_item_id: Mapped[str] = mapped_column(String(255), nullable=False)
    collection: Mapped[str] = mapped_column(String(128), nullable=False)
    footprint: Mapped[str] = mapped_column(Geography(geometry_type="POLYGON", srid=4326), nullable=False)
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cloud_cover_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    local_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    structured_features: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    has_embedding: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
