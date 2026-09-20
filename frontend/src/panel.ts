import type { ClassificationSummary, ClassifiedEvent, EventDetail } from "./api";

function fmtPct(v: number | null): string {
  return v === null ? "—" : `${(v * 100).toFixed(0)}%`;
}

function fmtNum(v: number | null, digits = 2): string {
  return v === null ? "—" : v.toFixed(digits);
}

function riskTag(level: string): string {
  return `<span class="risk-tag risk-${level.toLowerCase()}">${level}</span>`;
}

export function renderHotspotTable(tbody: HTMLElement, events: ClassifiedEvent[], selectedId: string | null): void {
  tbody.innerHTML = events
    .map((e) => {
      const label = e.classifications[0]?.label ?? "unknown_needs_review";
      const when = new Date(e.acquired_at).toISOString().slice(0, 16).replace("T", " ");
      const selected = e.id === selectedId ? "selected" : "";
      return `
        <tr class="${selected}" data-id="${e.id}">
          <td>${riskTag(e.risk_level)}</td>
          <td>${label.replace(/_/g, " ")}</td>
          <td>${e.frp_mw.toFixed(1)}</td>
          <td>${e.nearest_facility ?? "—"}</td>
          <td>${when}</td>
        </tr>`;
    })
    .join("");
}

function modelCard(c: ClassificationSummary): string {
  return `
    <div class="model-card">
      <div class="model-card-header">
        <span>${c.model_source.toUpperCase()} (${c.model_version})</span>
        <span>${c.is_abnormal ? "ABNORMAL" : "NORMAL"}</span>
      </div>
      <div class="model-card-body">
        <div class="kv-row"><span class="k">label</span><span class="v">${c.label.replace(/_/g, " ")}</span></div>
        <div class="kv-row"><span class="k">confidence</span><span class="v">${fmtPct(c.confidence)}</span></div>
        <div class="kv-row"><span class="k">risk</span><span class="v">${c.risk_level ?? "—"} (${fmtNum(c.risk_score)})</span></div>
        <div class="reasoning-block">${c.reasoning}</div>
        <div class="metric-row">
          <span>precision <span>${fmtPct(c.model_precision)}</span></span>
          <span>recall <span>${fmtPct(c.model_recall)}</span></span>
          <span>accuracy <span>${fmtPct(c.model_accuracy)}</span></span>
          <span>f1 <span>${fmtPct(c.model_f1_macro)}</span></span>
        </div>
      </div>
    </div>`;
}

export function renderDetail(container: HTMLElement, detail: EventDetail): void {
  const satellite = detail.satellite_images.length
    ? detail.satellite_images
        .map(
          (img) =>
            `<div class="kv-row"><span class="k">${img.stac_item_id}</span><span class="v">${new Date(
              img.acquired_at
            )
              .toISOString()
              .slice(0, 10)} · cloud ${img.cloud_cover_pct?.toFixed(0) ?? "?"}% · ${
              img.has_embedding ? "embedded" : "no embedding"
            }</span></div>`
        )
        .join("")
    : `<div class="kv-row"><span class="k">no satellite passes retrieved yet</span></div>`;

  container.innerHTML = `
    <div class="detail-section">
      <div class="detail-section-title">FIRE REPRESENTATION</div>
      <div class="kv-row"><span class="k">brightness</span><span class="v">${detail.brightness_kelvin.toFixed(1)} K</span></div>
      <div class="kv-row"><span class="k">FRP</span><span class="v">${detail.frp_mw.toFixed(1)} MW</span></div>
      <div class="kv-row"><span class="k">FRP deviation</span><span class="v">${
        detail.frp_deviation_pct === null ? "—" : `${detail.frp_deviation_pct}%`
      }</span></div>
      <div class="kv-row"><span class="k">detection confidence</span><span class="v">${detail.confidence}</span></div>
      <div class="kv-row"><span class="k">acquired</span><span class="v">${detail.acquired_at}</span></div>
    </div>

    <div class="detail-section">
      <div class="detail-section-title">INDUSTRIAL CONTEXT</div>
      <div class="kv-row"><span class="k">nearest facility</span><span class="v">${detail.nearest_facility ?? "none in AOI"}</span></div>
      <div class="kv-row"><span class="k">facility type</span><span class="v">${detail.facility_type ?? "—"}</span></div>
      <div class="kv-row"><span class="k">distance</span><span class="v">${
        detail.distance_to_facility_km === null ? "—" : `${detail.distance_to_facility_km} km`
      }</span></div>
    </div>

    <div class="detail-section">
      <div class="detail-section-title">TEMPORAL HISTORY (${detail.persistence_window_days}d window)</div>
      <div class="kv-row"><span class="k">recurrences nearby</span><span class="v">${detail.persistence_count}</span></div>
    </div>

    <div class="detail-section">
      <div class="detail-section-title">SATELLITE EVIDENCE</div>
      ${satellite}
    </div>

    <div class="detail-section">
      <div class="detail-section-title">CLASSIFIERS</div>
      ${detail.classifications.length ? detail.classifications.map(modelCard).join("") : "<div>not yet classified</div>"}
    </div>`;
}
