import "maplibre-gl/dist/maplibre-gl.css";
import { api, type ClassifiedEvent } from "./api";
import { ConsoleMap } from "./map";
import { renderDetail, renderHotspotTable } from "./panel";

const POLL_INTERVAL_MS = 15_000; // status/table refresh; matches the pipeline's own cadence order of magnitude

const el = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;

const pipelineStatusEl = el<HTMLDivElement>("pipeline-status");
const statusLineEl = el<HTMLSpanElement>("status-line");
const hotspotCountEl = el<HTMLSpanElement>("hotspot-count");
const tableBodyEl = el<HTMLTableSectionElement>("hotspot-table-body");
const daysBackSelect = el<HTMLSelectElement>("days-back-select");
const railDefault = el<HTMLDivElement>("rail-default");
const railDetail = el<HTMLDivElement>("rail-detail");
const detailContent = el<HTMLDivElement>("detail-content");
const detailBackBtn = el<HTMLButtonElement>("detail-back");

let currentEvents: ClassifiedEvent[] = [];
let selectedId: string | null = null;

function setStatusLine(text: string): void {
  statusLineEl.innerHTML = `<span class="live-dot"></span>${text}`;
}

function showDetailPanel(): void {
  railDefault.hidden = true;
  railDetail.hidden = false;
}

function showDefaultPanel(): void {
  railDetail.hidden = true;
  railDefault.hidden = false;
  selectedId = null;
  renderHotspotTable(tableBodyEl, currentEvents, selectedId);
}

async function openEvent(map: ConsoleMap, id: string): Promise<void> {
  selectedId = id;
  renderHotspotTable(tableBodyEl, currentEvents, selectedId);
  showDetailPanel();
  detailContent.innerHTML = `<div class="kv-row"><span class="k">loading...</span></div>`;
  try {
    const detail = await api.event(id);
    renderDetail(detailContent, detail);
    map.flyTo([detail.longitude, detail.latitude]);
  } catch (err) {
    detailContent.innerHTML = `<div class="kv-row"><span class="k">failed to load event</span></div>`;
    console.error(err);
  }
}

async function refreshEvents(map: ConsoleMap): Promise<void> {
  const daysBack = Number(daysBackSelect.value);
  try {
    currentEvents = await api.events(daysBack);
    hotspotCountEl.textContent = `[${currentEvents.length}]`;
    map.setHotspots(currentEvents);
    if (railDefault.hidden === false) {
      renderHotspotTable(tableBodyEl, currentEvents, selectedId);
    }
    setStatusLine(`${currentEvents.length} hotspots in view (days_back=${daysBack})`);
  } catch (err) {
    setStatusLine("failed to load events — see console");
    console.error(err);
  }
}

async function refreshPipelineStatus(): Promise<void> {
  try {
    const status = await api.pipelineStatus();
    const lastPoll = status.last_poll_at ? new Date(status.last_poll_at).toISOString().slice(11, 19) : "never";
    pipelineStatusEl.textContent = status.running
      ? `> pipeline running · last poll ${lastPoll} · +${status.new_hotspots_last_tick} new · ${status.total_hotspots_processed} total processed`
      : `> pipeline stopped${status.last_error ? ` — ${status.last_error}` : ""}`;
  } catch (err) {
    pipelineStatusEl.textContent = "> pipeline status unavailable";
    console.error(err);
  }
}

async function main(): Promise<void> {
  const map = new ConsoleMap(el<HTMLDivElement>("map"), (id) => openEvent(map, id));
  await map.whenReady();

  try {
    const aoi = await api.aoi();
    map.setAoi(aoi);
    const bbox = aoi.properties.bbox as [number, number, number, number];
    map.fitToAoi(bbox);
  } catch (err) {
    console.error("failed to load AOI", err);
  }

  try {
    const facilities = await api.facilities();
    map.setFacilities(facilities);
  } catch (err) {
    console.error("failed to load facilities", err);
  }

  tableBodyEl.addEventListener("click", (e) => {
    const row = (e.target as HTMLElement).closest("tr[data-id]") as HTMLElement | null;
    if (row?.dataset.id) openEvent(map, row.dataset.id);
  });
  detailBackBtn.addEventListener("click", showDefaultPanel);
  daysBackSelect.addEventListener("change", () => refreshEvents(map));

  await refreshEvents(map);
  await refreshPipelineStatus();

  setInterval(() => refreshEvents(map), POLL_INTERVAL_MS);
  setInterval(refreshPipelineStatus, POLL_INTERVAL_MS);
}

main().catch((err) => {
  console.error(err);
  setStatusLine("fatal error — see console");
});
