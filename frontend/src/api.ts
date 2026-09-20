// Thin typed client for /api/v1/* — mirrors src/industrial_fire/api/schemas/*.py exactly.
// No BFF: this dashboard is a pure client of the existing FastAPI app (see docs/api/api-design.md).

const API_BASE = "/api/v1";

export interface ClassificationSummary {
  model_source: string;
  model_version: string;
  label: string;
  confidence: number;
  is_abnormal: boolean;
  reasoning: string;
  model_precision: number | null;
  model_recall: number | null;
  model_accuracy: number | null;
  model_f1_macro: number | null;
  risk_level: string | null;
  risk_score: number | null;
  contributing_factors: string[];
}

export interface ClassifiedEvent {
  id: string;
  latitude: number;
  longitude: number;
  brightness_kelvin: number;
  frp_mw: number;
  confidence: string;
  acquired_at: string;
  nearest_facility: string | null;
  facility_type: string | null;
  distance_to_facility_km: number | null;
  persistence_count: number;
  frp_deviation_pct: number | null;
  classifications: ClassificationSummary[];
  risk_level: string;
  risk_score: number;
}

export interface SatelliteImageSummary {
  id: string;
  stac_item_id: string;
  collection: string;
  acquired_at: string;
  cloud_cover_pct: number | null;
  has_embedding: boolean;
}

export interface EventDetail extends ClassifiedEvent {
  persistence_window_days: number;
  satellite_images: SatelliteImageSummary[];
}

export interface Facility {
  id: string;
  name: string;
  facility_type: string;
  latitude: number;
  longitude: number;
}

export interface AoiFeature {
  type: "Feature";
  geometry: { type: "Polygon"; coordinates: number[][][] };
  properties: Record<string, unknown>;
}

export interface PipelineStatus {
  running: boolean;
  last_poll_at: string | null;
  events_seen_last_tick: number;
  new_hotspots_last_tick: number;
  total_hotspots_processed: number;
  last_error: string | null;
}

async function getJson<T>(path: string): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`);
  if (!resp.ok) {
    throw new Error(`${path} -> HTTP ${resp.status}`);
  }
  return resp.json() as Promise<T>;
}

export const api = {
  events: (daysBack: number) => getJson<ClassifiedEvent[]>(`/events?days_back=${daysBack}`),
  event: (id: string) => getJson<EventDetail>(`/events/${id}`),
  facilities: () => getJson<Facility[]>("/facilities"),
  aoi: () => getJson<AoiFeature>("/aoi"),
  pipelineStatus: () => getJson<PipelineStatus>("/pipeline/status"),
};
