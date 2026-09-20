"""
Generates docs/architecture/er-diagram.jpg from the actual schema
(migrations/versions/0001_initial_schema.py + 0002_dual_classifier_metrics.py)
by hand — kept in sync manually, not introspected from the live DB, so
re-run this after any migration that adds/removes a table or column.

    uv run python scripts/maintenance/generate_er_diagram.py
    npx --yes playwright install chromium   # first run only
    npx --yes playwright screenshot --viewport-size=1780,1010 \\
        "file:///<absolute path to the .html this prints>" \\
        docs/architecture/er-diagram.png
    # then convert PNG -> JPG, e.g.:
    uv run --with pillow python -c "from PIL import Image; \\
        Image.open('docs/architecture/er-diagram.png').convert('RGB') \\
        .save('docs/architecture/er-diagram.jpg', quality=95)"

No SVG-to-raster library (cairosvg, ImageMagick, rsvg-convert) was
available in this environment, hence the headless-Chromium-screenshot
route rather than a single-command export.
"""

# ruff: noqa: E501 — SVG markup lines are long by nature; wrapping them hurts
# readability here more than it helps, unlike normal application code.
from __future__ import annotations

import os

ROW_H = 20
HEADER_H = 32
PAD_TOP = 10
PAD_BOTTOM = 10

PK_COLOR = "#b8860b"
FK_COLOR = "#1a5fb4"
NORMAL_COLOR = "#222"
HEADER_BG = "#1f3a5f"
HEADER_TEXT = "#ffffff"
BOX_BG = "#ffffff"
BOX_BORDER = "#1f3a5f"
ROW_ALT = "#f2f5f9"
FONT = "Consolas, 'Courier New', monospace"


class Table:
    def __init__(self, name, x, y, w, rows, note=None):
        self.name = name
        self.x = x
        self.y = y
        self.w = w
        self.rows = rows  # list of (marker, col, type_str)
        self.note = note  # optional extra line(s) shown under the attribute list
        note_lines = len(note) if note else 0
        self.h = (
            HEADER_H
            + PAD_TOP
            + ROW_H * len(rows)
            + (14 * note_lines + 6 if note_lines else 0)
            + PAD_BOTTOM
        )

    def attr_bottom_y(self):
        return self.y + HEADER_H + PAD_TOP + ROW_H * len(self.rows)

    def port(self, side):
        if side == "top":
            return (self.x + self.w / 2, self.y)
        if side == "bottom":
            return (self.x + self.w / 2, self.y + self.h)
        if side == "left":
            return (self.x, self.y + self.h / 2)
        if side == "right":
            return (self.x + self.w, self.y + self.h / 2)
        if side == "topleft":
            return (self.x + self.w * 0.25, self.y)
        if side == "topright":
            return (self.x + self.w * 0.75, self.y)
        if side == "bottomleft":
            return (self.x + self.w * 0.25, self.y + self.h)
        if side == "bottomright":
            return (self.x + self.w * 0.75, self.y + self.h)
        raise ValueError(side)

    def svg(self):
        out = []
        out.append(
            f'<rect x="{self.x}" y="{self.y}" width="{self.w}" height="{self.h}" '
            f'fill="{BOX_BG}" stroke="{BOX_BORDER}" stroke-width="1.5"/>'
        )
        out.append(
            f'<rect x="{self.x}" y="{self.y}" width="{self.w}" height="{HEADER_H}" '
            f'fill="{HEADER_BG}" stroke="{BOX_BORDER}" stroke-width="1.5"/>'
        )
        out.append(
            f'<text x="{self.x + self.w / 2}" y="{self.y + HEADER_H / 2 + 5}" '
            f'text-anchor="middle" font-family="{FONT}" font-size="15" font-weight="bold" '
            f'fill="{HEADER_TEXT}">{self.name}</text>'
        )
        ry = self.y + HEADER_H + PAD_TOP
        for i, (marker, col, typ) in enumerate(self.rows):
            if i % 2 == 1:
                out.append(
                    f'<rect x="{self.x}" y="{ry - 14}" width="{self.w}" height="{ROW_H}" fill="{ROW_ALT}"/>'
                )
            color = PK_COLOR if marker == "PK" else FK_COLOR if marker == "FK" else NORMAL_COLOR
            weight = "bold" if marker in ("PK", "FK") else "normal"
            mark_txt = marker if marker else ""
            out.append(
                f'<text x="{self.x + 8}" y="{ry}" font-family="{FONT}" font-size="11.5" '
                f'font-weight="{weight}" fill="{color}">{mark_txt}</text>'
            )
            out.append(
                f'<text x="{self.x + 40}" y="{ry}" font-family="{FONT}" font-size="11.5" '
                f'font-weight="{weight}" fill="{color}">{col}</text>'
            )
            out.append(
                f'<text x="{self.x + self.w - 8}" y="{ry}" text-anchor="end" font-family="{FONT}" '
                f'font-size="11" fill="#555">{typ}</text>'
            )
            ry += ROW_H
        if self.note:
            ry += 4
            for line in self.note:
                out.append(
                    f'<text x="{self.x + 8}" y="{ry}" font-family="{FONT}" font-size="10.5" '
                    f'font-style="italic" fill="#666">{line}</text>'
                )
                ry += 14
        return "\n".join(out)


def arrow_marker_defs():
    return """
    <defs>
      <marker id="crowN" markerWidth="14" markerHeight="14" refX="10" refY="5" orient="auto">
        <path d="M0,0 L10,5 L0,10" fill="none" stroke="#1a5fb4" stroke-width="1.6"/>
      </marker>
      <marker id="dot1" markerWidth="10" markerHeight="10" refX="4" refY="4" orient="auto">
        <circle cx="4" cy="4" r="3" fill="#1a5fb4"/>
      </marker>
    </defs>
    """


def elbow_line(p1, p2, mid_y, label, color="#1a5fb4", card_near="1", card_far="N"):
    """L-shaped connector routed below both endpoints — avoids cutting through box interiors."""
    x1, y1 = p1
    x2, y2 = p2
    path = f"M{x1},{y1} L{x1},{mid_y} L{x2},{mid_y} L{x2},{y2}"
    out = [f'<path d="{path}" fill="none" stroke="{color}" stroke-width="1.6" marker-end="url(#crowN)"/>']
    mx = (x1 + x2) / 2
    out.append(
        f'<rect x="{mx - len(label) * 3.1 - 4}" y="{mid_y - 10}" width="{len(label) * 6.2 + 8}" height="15" '
        f'fill="#ffffff" opacity="0.95"/>'
    )
    out.append(
        f'<text x="{mx}" y="{mid_y + 2}" text-anchor="middle" font-family="{FONT}" font-size="10.5" '
        f'fill="{color}">{label}</text>'
    )
    out.append(
        f'<text x="{x1}" y="{y1 + 14}" text-anchor="middle" font-family="{FONT}" font-size="11" '
        f'font-weight="bold" fill="{color}">{card_near}</text>'
    )
    out.append(
        f'<text x="{x2 - 12}" y="{y2 - 6}" text-anchor="middle" font-family="{FONT}" font-size="11" '
        f'font-weight="bold" fill="{color}">{card_far}</text>'
    )
    return "\n".join(out)


def fk_line(p1, p2, label, dashed=False, color="#1a5fb4", card_near="1", card_far="N"):
    x1, y1 = p1
    x2, y2 = p2
    dash = 'stroke-dasharray="6,4"' if dashed else ""
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    out = [
        f'<path d="M{x1},{y1} L{x2},{y2}" fill="none" stroke="{color}" stroke-width="1.6" {dash} '
        f'marker-end="url(#crowN)"/>'
    ]
    out.append(
        f'<rect x="{mx - len(label) * 3.1 - 4}" y="{my - 10}" width="{len(label) * 6.2 + 8}" height="15" '
        f'fill="#ffffff" opacity="0.9"/>'
    )
    out.append(
        f'<text x="{mx}" y="{my + 2}" text-anchor="middle" font-family="{FONT}" font-size="10.5" '
        f'fill="{color}">{label}</text>'
    )
    # cardinality tags near each end
    out.append(
        f'<text x="{x1 + (12 if x2>x1 else -12)}" y="{y1 - 6 if y2>y1 else y1+14}" '
        f'text-anchor="middle" font-family="{FONT}" font-size="11" font-weight="bold" fill="{color}">{card_near}</text>'
    )
    out.append(
        f'<text x="{x2 + (-14 if x2>x1 else 14)}" y="{y2 - 6 if y1>y2 else y2+14}" '
        f'text-anchor="middle" font-family="{FONT}" font-size="11" font-weight="bold" fill="{color}">{card_far}</text>'
    )
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Tables (columns/types match the migrations exactly)
# ---------------------------------------------------------------------------

thermal_events = Table(
    "thermal_events", 700, 150, 360,
    [
        ("PK", "id", "UUID"),
        ("", "location", "GEOGRAPHY(POINT,4326)"),
        ("", "brightness_kelvin", "FLOAT NOT NULL"),
        ("", "frp_mw", "FLOAT NOT NULL"),
        ("", "confidence", "VARCHAR(16) NOT NULL"),
        ("", "acquired_at", "TIMESTAMPTZ NOT NULL"),
        ("", "source", "VARCHAR(32) NOT NULL"),
        ("", "ingested_at", "TIMESTAMPTZ NOT NULL"),
    ],
    note=[
        "UNIQUE (acquired_at, source, location)",
        "GiST idx(location) · idx(acquired_at)",
    ],
)

facilities = Table(
    "facilities", 40, 40, 320,
    [
        ("PK", "id", "UUID"),
        ("", "name", "VARCHAR(255) NOT NULL"),
        ("", "facility_type", "VARCHAR(32) NOT NULL"),
        ("", "location", "GEOGRAPHY(POINT,4326)"),
        ("", "osm_id", "VARCHAR(64) UNIQUE NULL"),
    ],
    note=["GiST idx(location)"],
)

weather_observations = Table(
    "weather_observations", 1400, 40, 340,
    [
        ("PK", "id", "UUID"),
        ("", "location", "GEOGRAPHY(POINT,4326)"),
        ("", "observed_at", "TIMESTAMPTZ NOT NULL"),
        ("", "temperature_c", "FLOAT NULL"),
        ("", "wind_speed_ms", "FLOAT NULL"),
        ("", "wind_direction_deg", "FLOAT NULL"),
        ("", "relative_humidity_pct", "FLOAT NULL"),
        ("", "provider", "VARCHAR(64) NOT NULL"),
    ],
    note=["GiST idx(location) · idx(observed_at)"],
)

satellite_images = Table(
    "satellite_images", 40, 500, 320,
    [
        ("PK", "id", "UUID"),
        ("FK", "thermal_event_id", "UUID -> thermal_events"),
        ("", "stac_item_id", "VARCHAR(255) NOT NULL"),
        ("", "collection", "VARCHAR(128) NOT NULL"),
        ("", "footprint", "GEOGRAPHY(POLYGON,4326)"),
        ("", "acquired_at", "TIMESTAMPTZ NOT NULL"),
        ("", "cloud_cover_pct", "FLOAT NULL"),
        ("", "local_path", "VARCHAR(1024) NULL"),
        ("", "structured_features", "JSONB NOT NULL DEFAULT {}"),
        ("", "has_embedding", "BOOLEAN NOT NULL DEFAULT false"),
    ],
    note=["ON DELETE CASCADE · GiST idx(footprint)"],
)

classification_results = Table(
    "classification_results", 700, 500, 380,
    [
        ("PK", "id", "UUID"),
        ("FK", "thermal_event_id", "UUID -> thermal_events"),
        ("", "label", "VARCHAR(64) NOT NULL"),
        ("", "confidence", "FLOAT NOT NULL"),
        ("", "reasoning", "TEXT NOT NULL"),
        ("", "model_source", "VARCHAR(32) NOT NULL"),
        ("", "model_version", "VARCHAR(64) NOT NULL"),
        ("", "is_abnormal", "BOOLEAN NOT NULL DEFAULT true"),
        ("", "model_precision", "FLOAT NULL"),
        ("", "model_recall", "FLOAT NULL"),
        ("", "model_accuracy", "FLOAT NULL"),
        ("", "model_f1_macro", "FLOAT NULL"),
        ("", "classified_at", "TIMESTAMPTZ NOT NULL"),
    ],
    note=[
        "ON DELETE CASCADE · idx(thermal_event_id)",
        "model_source \u2208 {rule_based_v1, celstm_v1, xgboost_v1}",
    ],
)

risk_assessments = Table(
    "risk_assessments", 1320, 500, 420,
    [
        ("PK", "id", "UUID"),
        ("FK", "thermal_event_id", "UUID -> thermal_events"),
        ("FK", "classification_result_id", "UUID -> classif_results"),
        ("", "risk_level", "VARCHAR(16) NOT NULL"),
        ("", "risk_score", "FLOAT NOT NULL"),
        ("", "contributing_factors", "VARCHAR[] DEFAULT {}"),
        ("", "assessed_at", "TIMESTAMPTZ NOT NULL"),
    ],
    note=["ON DELETE CASCADE (both FKs)"],
)

qdrant = Table(
    "Qdrant :: satellite_image_embeddings", 40, 850, 320,
    [
        ("PK", "vector_id", "UUID == satellite_images.id"),
        ("", "vector", "FLOAT32[512]  (vision embedding)"),
    ],
    note=["External vector index (ADR-002) \u2014", "similarity search only, NOT the system of record"],
)

tables = [
    thermal_events, facilities, weather_observations,
    satellite_images, classification_results, risk_assessments, qdrant,
]

CANVAS_W = 1780
CANVAS_H = 1010

svg_parts = [arrow_marker_defs()]

# title
svg_parts.append(
    f'<text x="{CANVAS_W/2}" y="30" text-anchor="middle" font-family="{FONT}" '
    f'font-size="22" font-weight="bold" fill="#1f3a5f">Industrial Fire AI \u2014 Database ER Model (PostgreSQL/PostGIS + Qdrant)</text>'
)

# relationship lines first (so boxes draw on top of line ends cleanly)
svg_parts.append(
    fk_line(thermal_events.port("left"), facilities.port("right"),
            "nearest facility (ST_DWithin, computed \u2014 no stored FK)",
            dashed=True, color="#7a7a7a", card_near="N", card_far="1")
)
svg_parts.append(
    fk_line(thermal_events.port("right"), weather_observations.port("left"),
            "nearest in space+time (computed \u2014 no stored FK)",
            dashed=True, color="#7a7a7a", card_near="N", card_far="1")
)
svg_parts.append(
    fk_line(satellite_images.port("top"), thermal_events.port("bottomleft"),
            "satellite_images.thermal_event_id", card_near="N", card_far="1")
)
svg_parts.append(
    fk_line(classification_results.port("top"), thermal_events.port("bottom"),
            "classification_results.thermal_event_id", card_near="N", card_far="1")
)
svg_parts.append(
    fk_line(risk_assessments.port("top"), thermal_events.port("bottomright"),
            "risk_assessments.thermal_event_id", card_near="N", card_far="1")
)
svg_parts.append(
    elbow_line(risk_assessments.port("bottomleft"), classification_results.port("bottomright"),
               920, "risk_assessments.classification_result_id", card_near="N", card_far="1")
)
svg_parts.append(
    fk_line(satellite_images.port("bottom"), qdrant.port("top"),
            "has_embedding=true \u21d2 vector stored in Qdrant",
            dashed=True, color="#7a7a7a", card_near="1", card_far="1")
)

for t in tables:
    svg_parts.append(t.svg())

# legend
lx, ly = 1400, 270
svg_parts.append(f'<rect x="{lx}" y="{ly}" width="350" height="150" fill="#ffffff" stroke="#1f3a5f" stroke-width="1.5"/>')
svg_parts.append(f'<text x="{lx+10}" y="{ly+20}" font-family="{FONT}" font-size="13" font-weight="bold" fill="#1f3a5f">LEGEND</text>')
svg_parts.append(f'<text x="{lx+10}" y="{ly+40}" font-family="{FONT}" font-size="11.5" fill="{PK_COLOR}" font-weight="bold">PK</text>')
svg_parts.append(f'<text x="{lx+35}" y="{ly+40}" font-family="{FONT}" font-size="11.5" fill="#222">Primary key</text>')
svg_parts.append(f'<text x="{lx+10}" y="{ly+58}" font-family="{FONT}" font-size="11.5" fill="{FK_COLOR}" font-weight="bold">FK</text>')
svg_parts.append(f'<text x="{lx+35}" y="{ly+58}" font-family="{FONT}" font-size="11.5" fill="#222">Foreign key (solid arrow = enforced, N..1)</text>')
svg_parts.append(f'<line x1="{lx+10}" y1="{ly+72}" x2="{lx+40}" y2="{ly+72}" stroke="#7a7a7a" stroke-width="1.6" stroke-dasharray="6,4"/>')
svg_parts.append(f'<text x="{lx+48}" y="{ly+76}" font-family="{FONT}" font-size="11.5" fill="#222">Logical relationship (no stored FK)</text>')
svg_parts.append(f'<text x="{lx+10}" y="{ly+96}" font-family="{FONT}" font-size="11" fill="#555">All PKs: UUID (uuid4, server-generated).</text>')
svg_parts.append(f'<text x="{lx+10}" y="{ly+112}" font-family="{FONT}" font-size="11" fill="#555">Geometry: PostGIS GEOGRAPHY(SRID 4326),</text>')
svg_parts.append(f'<text x="{lx+10}" y="{ly+128}" font-family="{FONT}" font-size="11" fill="#555">GiST-indexed. Vectors live only in Qdrant.</text>')

svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{CANVAS_W}" height="{CANVAS_H}" viewBox="0 0 {CANVAS_W} {CANVAS_H}">' \
      f'<rect x="0" y="0" width="{CANVAS_W}" height="{CANVAS_H}" fill="#ffffff"/>' \
      + "\n".join(svg_parts) + "</svg>"

html = f"""<!doctype html><html><head><meta charset="utf-8">
<style>html,body{{margin:0;padding:0;background:#ffffff;}}</style>
</head><body>{svg}</body></html>"""

out_path = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "architecture", "er-diagram.html")
out_path = os.path.abspath(out_path)
with open(out_path, "w", encoding="utf-8") as f:
    f.write(html)
print("wrote", out_path, "canvas", CANVAS_W, CANVAS_H)
print("next: screenshot it (see this file's module docstring), then delete the .html — only the .jpg is committed")
