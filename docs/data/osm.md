# OpenStreetMap / Overpass

**Adapter:** `infrastructure.osm.overpass_client.OverpassFacilityProvider`
(implements `application.ingestion.ingest_facilities.FacilityProvider`)

## Source
Overpass API (`OVERPASS_API_URL`, default `https://overpass-api.de/api/interpreter`) —
queried for `node[tag]` within the AOI bbox for each tag in
`configs/data.yaml:osm.facility_tags`.

## Tag → FacilityType mapping
See `_TAG_TO_FACILITY_TYPE` in `overpass_client.py`. Extend both the YAML
tag list and this mapping together when adding a new facility category —
an unmapped tag falls back to `FacilityType.OTHER`.

## Replaces the MVP's hardcoded list
The original `app/facilities.py` had 3 hardcoded sample facilities. This
adapter queries live OSM data for the configured AOI instead — see
`POST /api/v1/facilities/refresh`.

## Idempotency
Facilities upsert on `osm_id` (`ON CONFLICT DO UPDATE`), so re-running
ingestion refreshes name/location without duplicating rows. Facilities
without a stable OSM id (manually seeded ones) use `osm_id = NULL` and are
only ever inserted, not updated.
