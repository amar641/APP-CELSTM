import {
  GeoJSONSource,
  Map as MapLibreMap,
  NavigationControl,
  setWorkerUrl,
  type LngLatLike,
} from "maplibre-gl";
// Vite doesn't rewrite maplibre-gl's internal `import.meta.url`-relative worker
// lookup for a production build, which 404s and silently stalls style loading
// (no tile-independent style becomes "loaded" without the worker). Resolving
// it as a proper asset URL and pointing maplibre-gl at it explicitly fixes that.
import maplibreWorkerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
import type { AoiFeature, ClassifiedEvent, Facility } from "./api";

setWorkerUrl(maplibreWorkerUrl);

const RISK_COLOR: Record<string, string> = {
  CRITICAL: "#ff4d4d",
  HIGH: "#ff9c33",
  MEDIUM: "#e6c14d",
  LOW: "#4dae62",
};

// Classification -> icon glyph, matching the legend in index.html.
const CLASS_ICON: Record<string, string> = {
  wildfire: "triangle",
  potential_industrial_fire: "diamond",
  gas_flare_normal_industrial: "circle",
  unknown_needs_review: "square",
};

function drawGlyph(shape: string, color: string): ImageData {
  const size = 24;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d")!;
  ctx.fillStyle = color;
  ctx.strokeStyle = "#0a0d0a";
  ctx.lineWidth = 1.5;
  const c = size / 2;
  const r = size / 2 - 3;

  ctx.beginPath();
  if (shape === "triangle") {
    ctx.moveTo(c, c - r);
    ctx.lineTo(c + r, c + r * 0.8);
    ctx.lineTo(c - r, c + r * 0.8);
    ctx.closePath();
  } else if (shape === "diamond") {
    ctx.moveTo(c, c - r);
    ctx.lineTo(c + r, c);
    ctx.lineTo(c, c + r);
    ctx.lineTo(c - r, c);
    ctx.closePath();
  } else if (shape === "square") {
    ctx.rect(c - r * 0.8, c - r * 0.8, r * 1.6, r * 1.6);
  } else {
    ctx.arc(c, c, r, 0, Math.PI * 2);
  }
  ctx.fill();
  ctx.stroke();
  return ctx.getImageData(0, 0, size, size);
}

export interface HotspotClickHandler {
  (eventId: string): void;
}

export class ConsoleMap {
  private map: MapLibreMap;
  private onHotspotClick: HotspotClickHandler;

  constructor(container: HTMLElement, onHotspotClick: HotspotClickHandler) {
    this.onHotspotClick = onHotspotClick;
    this.map = new MapLibreMap({
      container,
      style: {
        version: 8,
        sources: {
          basemap: {
            // Standard OSM raster tiles — no API key, matches this project's
            // all-free-tier sources elsewhere (FIRMS, Overpass, Open-Meteo).
            // Darkened via raster paint properties below, not a CSS filter,
            // so the vector overlays (hotspots/facilities/AOI) drawn on the
            // same canvas keep their real colors.
            type: "raster",
            tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            tileSize: 256,
            attribution: "&copy; OpenStreetMap contributors",
          },
        },
        layers: [
          {
            id: "basemap",
            type: "raster",
            source: "basemap",
            paint: {
              "raster-saturation": -0.7,
              "raster-brightness-max": 0.45,
              "raster-contrast": 0.1,
            },
          },
        ],
      },
      center: [73, 24],
      zoom: 5,
    });
    this.map.addControl(new NavigationControl({ showCompass: false }), "top-right");
  }

  // Waits for the style spec to parse — NOT `isStyleLoaded()`/the `load`
  // event, both of which also wait for every source's tiles to finish
  // fetching, so they never resolve when the basemap's tile requests stall
  // (slow/blocked networks) even though addSource/addLayer only need the
  // style itself, not tiles. The `style.load` event fires as soon as the
  // style is ready but on the very next animation frame after construction,
  // which this method can race and miss if called a tick late — polling the
  // same internal flag that gates addSource ("Style is not done loading")
  // is a frame slower in the worst case but can't be missed.
  async whenReady(): Promise<void> {
    const style = this.map.style as unknown as { _loaded?: boolean } | undefined;
    while (!style?._loaded) {
      await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));
    }
  }

  fitToAoi(bbox: [number, number, number, number]): void {
    this.map.fitBounds(
      [
        [bbox[0], bbox[1]],
        [bbox[2], bbox[3]],
      ],
      { padding: 24, duration: 0 }
    );
  }

  setAoi(feature: AoiFeature): void {
    const data = { type: "FeatureCollection", features: [feature] } as GeoJSON.FeatureCollection;
    if (this.map.getSource("aoi")) {
      (this.map.getSource("aoi") as GeoJSONSource).setData(data);
      return;
    }
    this.map.addSource("aoi", { type: "geojson", data });
    this.map.addLayer({
      id: "aoi-line",
      type: "line",
      source: "aoi",
      paint: {
        "line-color": "#eaf2e2",
        "line-width": 1.5,
        "line-dasharray": [3, 2],
      },
    });
  }

  setFacilities(facilities: Facility[]): void {
    const data: GeoJSON.FeatureCollection = {
      type: "FeatureCollection",
      features: facilities.map((f) => ({
        type: "Feature",
        geometry: { type: "Point", coordinates: [f.longitude, f.latitude] },
        properties: { name: f.name, facility_type: f.facility_type },
      })),
    };
    if (this.map.getSource("facilities")) {
      (this.map.getSource("facilities") as GeoJSONSource).setData(data);
      return;
    }
    this.map.addSource("facilities", {
      type: "geojson",
      data,
      cluster: true,
      clusterRadius: 40,
      clusterMaxZoom: 9,
    });
    this.map.addLayer({
      id: "facility-clusters",
      type: "circle",
      source: "facilities",
      filter: ["has", "point_count"],
      paint: {
        "circle-color": "#d4b83c",
        "circle-radius": 10,
        "circle-stroke-width": 1,
        "circle-stroke-color": "#0a0d0a",
      },
    });
    this.map.addLayer({
      id: "facility-cluster-count",
      type: "symbol",
      source: "facilities",
      filter: ["has", "point_count"],
      layout: { "text-field": ["get", "point_count_abbreviated"], "text-size": 10 },
      paint: { "text-color": "#0a0d0a" },
    });
    this.map.addLayer({
      id: "facility-points",
      type: "circle",
      source: "facilities",
      filter: ["!", ["has", "point_count"]],
      paint: {
        "circle-color": "#d4b83c",
        "circle-radius": 4,
        "circle-stroke-width": 1,
        "circle-stroke-color": "#0a0d0a",
      },
    });
  }

  setHotspots(events: ClassifiedEvent[]): void {
    for (const shape of Object.values(CLASS_ICON)) {
      for (const risk of Object.keys(RISK_COLOR)) {
        const imageId = `hotspot-${shape}-${risk}`;
        if (!this.map.hasImage(imageId)) {
          this.map.addImage(imageId, drawGlyph(shape, RISK_COLOR[risk]));
        }
      }
    }

    const data: GeoJSON.FeatureCollection = {
      type: "FeatureCollection",
      features: events.map((e) => {
        const label = e.classifications[0]?.label ?? "unknown_needs_review";
        const shape = CLASS_ICON[label] ?? "square";
        return {
          type: "Feature",
          geometry: { type: "Point", coordinates: [e.longitude, e.latitude] },
          properties: {
            id: e.id,
            icon: `hotspot-${shape}-${e.risk_level}`,
            persistent: e.persistence_count >= 4,
            risk_level: e.risk_level,
          },
        };
      }),
    };

    if (this.map.getSource("hotspots")) {
      (this.map.getSource("hotspots") as GeoJSONSource).setData(data);
      return;
    }

    this.map.addSource("hotspots", { type: "geojson", data });

    // Persistence emphasis ring, drawn under the glyph.
    this.map.addLayer({
      id: "hotspot-persistence-ring",
      type: "circle",
      source: "hotspots",
      filter: ["==", ["get", "persistent"], true],
      paint: {
        "circle-radius": 12,
        "circle-color": "transparent",
        "circle-stroke-width": 2,
        "circle-stroke-color": "#ff9c33",
      },
    });

    this.map.addLayer({
      id: "hotspot-glyphs",
      type: "symbol",
      source: "hotspots",
      layout: { "icon-image": ["get", "icon"], "icon-size": 0.8, "icon-allow-overlap": true },
    });

    this.map.on("click", "hotspot-glyphs", (e) => {
      const id = e.features?.[0]?.properties?.id as string | undefined;
      if (id) this.onHotspotClick(id);
    });
    this.map.on("mouseenter", "hotspot-glyphs", () => {
      this.map.getCanvas().style.cursor = "pointer";
    });
    this.map.on("mouseleave", "hotspot-glyphs", () => {
      this.map.getCanvas().style.cursor = "";
    });
  }

  flyTo(center: LngLatLike): void {
    this.map.flyTo({ center, zoom: Math.max(this.map.getZoom(), 8), duration: 400 });
  }
}
