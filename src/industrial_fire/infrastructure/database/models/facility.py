from __future__ import annotations

import uuid

from geoalchemy2 import Geography
from sqlalchemy import Index, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from industrial_fire.infrastructure.database.models.base import Base


class FacilityModel(Base):
    __tablename__ = "facilities"
    __table_args__ = (Index("ix_facilities_location", "location", postgresql_using="gist"),)

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    facility_type: Mapped[str] = mapped_column(String(32), nullable=False)
    location: Mapped[str] = mapped_column(Geography(geometry_type="POINT", srid=4326), nullable=False)
    osm_id: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
