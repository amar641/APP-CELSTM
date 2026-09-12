# Frontend (placeholder)

Not yet built. Planned as a Leaflet/Mapbox GIS dashboard that consumes
`/api/v1/events` and `/api/v1/facilities` directly from the FastAPI
backend — see [docs/api/api-design.md](../docs/api/api-design.md).

No backend-for-frontend is planned; the dashboard is a pure client of the
existing API. A future Android client (Kotlin + Retrofit + Maps SDK, per
the original MVP's roadmap) would consume the same API unchanged.
