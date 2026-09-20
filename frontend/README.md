# GIS Dashboard

MapLibre GL JS + Vite + TypeScript, no framework. Built and served
directly by the FastAPI app (`api/main.py` mounts `frontend/dist` as
static files) — this is **not** a standalone service; there's no
backend-for-frontend, and in production it's just static assets shipped
alongside the API in the same container (see the repo root `Dockerfile`).

Aesthetic is deliberately an old-school monitoring console — dense
monospace tables, flat 1px-bordered panels, no gradients/shadows/rounded
corners — not a modern SaaS dashboard. See `src/style.css` for the theme
tokens.

## Develop

```bash
npm install
npm run dev
```

Starts Vite's dev server on `:5173`, proxying `/api/*` to a locally
running backend (`uv run python -m industrial_fire.api.main`, from the
repo root — see the root [README](../README.md)). `api/main.py`'s CORS
middleware allows `localhost:5173` for exactly this.

## Build

```bash
npm run build
```

Outputs to `frontend/dist/`, which `api/main.py` serves at `/` once it
exists (skipped if missing, so a dev checkout without a build still runs
the API fine — you just won't get the dashboard at `/`).

## What it shows

- Map (~65-70% of the screen): AOI boundary, industrial facilities
  (clustered), thermal hotspots colored by risk level and shaped by
  classification, with an emphasis ring on persistent hotspots.
- Side rail: pipeline status, legend, a dense hotspot table.
- Click a hotspot (map or table) to open the detail panel: fire
  representation, industrial context, satellite evidence, temporal
  history, and one card per classifier (CELSTM, XGBoost) with its label,
  confidence, risk, reasoning, and offline precision/recall/accuracy/f1.

All of it comes from `/api/v1/events`, `/api/v1/events/{id}`,
`/api/v1/facilities`, `/api/v1/aoi`, and `/api/v1/pipeline/status` — see
[docs/api/api-design.md](../docs/api/api-design.md).
