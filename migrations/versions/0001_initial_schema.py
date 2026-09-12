"""initial schema — PostGIS extension + core tables

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-09-04

"""

from __future__ import annotations

from typing import Sequence, Union

import geoalchemy2
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "thermal_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "location", geoalchemy2.Geography(geometry_type="POINT", srid=4326), nullable=False
        ),
        sa.Column("brightness_kelvin", sa.Float(), nullable=False),
        sa.Column("frp_mw", sa.Float(), nullable=False),
        sa.Column("confidence", sa.String(length=16), nullable=False),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_thermal_events_location", "thermal_events", ["location"], postgresql_using="gist"
    )
    op.create_index("ix_thermal_events_acquired_at", "thermal_events", ["acquired_at"])
    op.create_index(
        "uq_thermal_events_natural_key",
        "thermal_events",
        ["acquired_at", "source", "location"],
        unique=True,
    )

    op.create_table(
        "facilities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("facility_type", sa.String(length=32), nullable=False),
        sa.Column(
            "location", geoalchemy2.Geography(geometry_type="POINT", srid=4326), nullable=False
        ),
        sa.Column("osm_id", sa.String(length=64), nullable=True, unique=True),
    )
    op.create_index("ix_facilities_location", "facilities", ["location"], postgresql_using="gist")

    op.create_table(
        "weather_observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "location", geoalchemy2.Geography(geometry_type="POINT", srid=4326), nullable=False
        ),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("temperature_c", sa.Float(), nullable=True),
        sa.Column("wind_speed_ms", sa.Float(), nullable=True),
        sa.Column("wind_direction_deg", sa.Float(), nullable=True),
        sa.Column("relative_humidity_pct", sa.Float(), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
    )
    op.create_index(
        "ix_weather_observations_location", "weather_observations", ["location"], postgresql_using="gist"
    )
    op.create_index("ix_weather_observations_observed_at", "weather_observations", ["observed_at"])

    op.create_table(
        "satellite_images",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "thermal_event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("thermal_events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stac_item_id", sa.String(length=255), nullable=False),
        sa.Column("collection", sa.String(length=128), nullable=False),
        sa.Column(
            "footprint", geoalchemy2.Geography(geometry_type="POLYGON", srid=4326), nullable=False
        ),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cloud_cover_pct", sa.Float(), nullable=True),
        sa.Column("local_path", sa.String(length=1024), nullable=True),
        sa.Column("structured_features", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("has_embedding", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index(
        "ix_satellite_images_footprint", "satellite_images", ["footprint"], postgresql_using="gist"
    )

    op.create_table(
        "classification_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "thermal_event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("thermal_events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("label", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("reasoning", sa.String(), nullable=False),
        sa.Column("model_source", sa.String(length=32), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("classified_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "risk_assessments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "thermal_event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("thermal_events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "classification_result_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("classification_results.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("risk_level", sa.String(length=16), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=False),
        sa.Column(
            "contributing_factors", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"
        ),
        sa.Column("assessed_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("risk_assessments")
    op.drop_table("classification_results")
    op.drop_index("ix_satellite_images_footprint", table_name="satellite_images")
    op.drop_table("satellite_images")
    op.drop_index("ix_weather_observations_observed_at", table_name="weather_observations")
    op.drop_index("ix_weather_observations_location", table_name="weather_observations")
    op.drop_table("weather_observations")
    op.drop_index("ix_facilities_location", table_name="facilities")
    op.drop_table("facilities")
    op.drop_index("uq_thermal_events_natural_key", table_name="thermal_events")
    op.drop_index("ix_thermal_events_acquired_at", table_name="thermal_events")
    op.drop_index("ix_thermal_events_location", table_name="thermal_events")
    op.drop_table("thermal_events")
