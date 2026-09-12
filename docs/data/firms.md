# NASA FIRMS

**Adapter:** `infrastructure.firms.client.FirmsClient` (implements
`application.ingestion.ingest_thermal_events.ThermalEventProvider`)

## Source
`https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/{SOURCE}/{bbox}/{days}/{date}`
— CSV of thermal detections for a bounding box, one day at a time.

## Config
- `FIRMS_MAP_KEY` (.env, required) — free key from
  https://firms.modaps.eosdis.nasa.gov/api/map_key/
- `FIRMS_SOURCE` — one of `VIIRS_SNPP_NRT`, `VIIRS_NOAA20_NRT`, `MODIS_NRT`
- `AOI_BBOX` — `west,south,east,north`
- `HISTORY_DAYS` — how many days back to pull for the persistence signal
  (free tier caps at 10)

## Fields consumed
`latitude`, `longitude`, `bright_ti4`/`brightness`, `frp`, `confidence`,
`acq_date`, `acq_time` → mapped to `domain.entities.thermal_event.ThermalEvent`.
Malformed rows are skipped, not fatal to the whole pull.

## Idempotency
Detections are upserted on `(acquired_at, source, location)` — re-pulling
the same day is safe.

## Rate limits / reliability
Requests retry up to 3 times with exponential backoff
(`tenacity`) on transport errors. A missing/invalid `FIRMS_MAP_KEY` fails
fast with `ExternalServiceError` rather than a raw HTTP error.
