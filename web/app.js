// BridgeWatch front end. Static: reads data/ written by `bridgewatch export`. No server, no tracking.
"use strict";

const STATES = { "01": "Alabama", "02": "Alaska", "04": "Arizona", "05": "Arkansas", "06": "California", "08": "Colorado",
  "09": "Connecticut", "10": "Delaware", "11": "District of Columbia", "12": "Florida", "13": "Georgia", "15": "Hawaii",
  "16": "Idaho", "17": "Illinois", "18": "Indiana", "19": "Iowa", "20": "Kansas", "21": "Kentucky", "22": "Louisiana",
  "23": "Maine", "24": "Maryland", "25": "Massachusetts", "26": "Michigan", "27": "Minnesota", "28": "Mississippi",
  "29": "Missouri", "30": "Montana", "31": "Nebraska", "32": "Nevada", "33": "New Hampshire", "34": "New Jersey",
  "35": "New Mexico", "36": "New York", "37": "North Carolina", "38": "North Dakota", "39": "Ohio", "40": "Oklahoma",
  "41": "Oregon", "42": "Pennsylvania", "44": "Rhode Island", "45": "South Carolina", "46": "South Dakota", "47": "Tennessee",
  "48": "Texas", "49": "Utah", "50": "Vermont", "51": "Virginia", "53": "Washington", "54": "West Virginia", "55": "Wisconsin",
  "56": "Wyoming", "72": "Puerto Rico" };
const OWNER = { "1": "State highway agency", "2": "County", "3": "Town or township", "4": "City", "11": "State park/forest",
  "21": "Other state agency", "25": "Other local agency", "26": "Private", "27": "Railroad", "31": "Toll authority",
  "32": "Local toll authority", "60": "Federal", "62": "Bureau of Indian Affairs", "64": "Forest Service", "66": "National Park Service" };
const MATERIAL = { "1": "Concrete", "2": "Concrete (continuous)", "3": "Steel", "4": "Steel (continuous)", "5": "Prestressed concrete",
  "6": "Prestressed concrete (continuous)", "7": "Timber", "8": "Masonry", "9": "Aluminium / iron", "0": "Other" };
const DESIGN = { "01": "Slab", "02": "Stringer / multi-beam or girder", "03": "Girder and floorbeam", "04": "Tee beam",
  "05": "Box beam (multiple)", "06": "Box beam (single/spread)", "07": "Frame", "08": "Orthotropic", "09": "Truss (deck)",
  "10": "Truss (thru)", "11": "Arch (deck)", "12": "Arch (thru)", "13": "Suspension", "14": "Stayed girder", "15": "Movable (lift)",
  "16": "Movable (bascule)", "17": "Movable (swing)", "18": "Tunnel", "19": "Culvert", "20": "Mixed types", "21": "Segmental box",
  "22": "Channel beam", "00": "Other" };
const POSTING = { A: "Open", B: "Open, work pending", D: "Open, temporary shoring", E: "Open, temporary structure",
  G: "New, not yet open", K: "Closed", P: "Posted for load", R: "Posted, other restriction" };
const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const hex = (h) => { const n = parseInt(h.replace("#", ""), 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; };
const $ = (s) => document.querySelector(s);
const fmt = new Intl.NumberFormat("en-US");
const money = (x) => x >= 1e9 ? `$${(x / 1e9).toFixed(2)} B` : x >= 1e6 ? `$${(x / 1e6).toFixed(1)} M` : x >= 1e3 ? `$${(x / 1e3).toFixed(0)} k` : `$${Math.round(x)}`;
const pct = (p, d = 1) => (p == null || Number.isNaN(p)) ? "–" : `${(100 * p).toFixed(d)}%`;
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

const cache = { states: new Map(), history: new Map() };
let summary, points, index, map, overlay;
// points.bin is sorted by state; index.states = [[fips, first record, count], ...]
function locate(i) {
  for (const [st, start, count] of index.states) if (i >= start && i < start + count) return [st, i - start];
  return [null, -1];
}

async function json(path) { const r = await fetch(path); if (!r.ok) throw new Error(`${path}: ${r.status}`); return r.json(); }
// State files are columnar with probabilities in 1/10,000 and value per dollar in 1/1,000; turn them into row objects once.
async function loadState(st) {
  const f = await json(`data/states/${st}.json`), d = f.data, n = d.bridge_id.length, P = f.scale.probabilities, V = f.scale.value_per_dollar;
  const rows = new Array(n);
  for (let k = 0; k < n; k++) {
    const r = {};
    for (const c of f.columns) r[c] = d[c][k];
    for (const c of ["p_poor_4y", "p_restricted_4y", "p_q4_miss_4y"]) r[c] = r[c] == null ? null : r[c] / P;
    r.value_per_dollar = r.value_per_dollar == null ? null : r.value_per_dollar / V;
    r.method1 = r.method1 === 1;
    r.k = k;
    rows[k] = r;
  }
  return rows;
}
const stateData = (st) => cache.states.get(st) ?? cache.states.set(st, loadState(st)).get(st);
const historyData = (st) => cache.history.get(st) ?? cache.history.set(st, json(`data/history/${st}.json`)).get(st);

// ---------------------------------------------------------------- tabs and selects
function initTabs() {
  const show = (name) => {
    document.querySelectorAll(".tabs button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === name)));
    document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.id === `tab-${name}`));
    if (name === "map" && map) map.resize();
    renderers[name]?.();
    try { history.replaceState(null, "", `#${name}`); } catch { /* sandboxed */ }
  };
  document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => show(b.dataset.tab)));
  const start = location.hash.slice(1);
  if (document.getElementById(`tab-${start}`)) show(start);
}

function initStateSelects() {
  const present = new Set(summary.by_state.map((s) => s.state_code));
  const opts = Object.entries(STATES).filter(([k]) => present.has(k)).sort((a, b) => a[1].localeCompare(b[1]));
  document.querySelectorAll(".state-select").forEach((sel) => {
    sel.innerHTML = (sel.id === "mapState" ? `<option value="">United States</option>` : "") +
      opts.map(([k, v]) => `<option value="${k}">${v}</option>`).join("");
    if (sel.id !== "mapState") sel.value = "19";
  });
}

// ---------------------------------------------------------------- map
const BAND_LABELS = ["< 1%", "1–3%", "3–10%", "10–25%", "> 25%"];
function colorOf(mode) {
  const g = hex(css("--good")), f = hex(css("--fair")), p = hex(css("--poor")), na = hex(css("--na"));
  const bands = ["--r1", "--r2", "--r3", "--r4", "--r5"].map((v) => hex(css(v)));
  return (i) => {
    const o = i * 12;
    if (mode === "cond") { const c = points.getUint8(o + 8); return c === 1 ? g : c === 2 ? f : c === 3 ? p : na; }
    if (mode === "flag") return (points.getUint8(o + 11) & 1) ? p : hex(css("--r1"));
    const b = points.getUint8(o + (mode === "q1" ? 9 : 10));
    return b ? bands[b - 1] : na;
  };
}
function bandCounts(mode) {
  const n = points.byteLength / 12, c = new Array(6).fill(0);
  for (let i = 0; i < n; i++) {
    const o = i * 12;
    if (mode === "cond") c[points.getUint8(o + 8)]++;
    else if (mode === "flag") c[points.getUint8(o + 11) & 1]++;
    else c[points.getUint8(o + (mode === "q1" ? 9 : 10))]++;
  }
  return c;
}
function legend(mode) {
  const cnt = bandCounts(mode), n = points.byteLength / 12;
  const share = (k) => ` <small>${fmt.format(cnt[k])} (${(100 * cnt[k] / n).toFixed(1)}%)</small>`;
  const row = (c, t, k) => `<div><span style="background:${c}"></span>${t}${k == null ? "" : share(k)}</div>`;
  if (mode === "cond") return row(css("--good"), "Good (all ratings ≥ 7)", 1) + row(css("--fair"), "Fair (lowest 5–6)", 2) + row(css("--poor"), "Poor (lowest ≤ 4)", 3);
  if (mode === "flag") return row(css("--poor"), "Posted for load, restricted or closed", 1) + row(css("--r1"), "Open", 0);
  return ["--r1", "--r2", "--r3", "--r4", "--r5"].map((v, i) => row(css(v), BAND_LABELS[i], i + 1)).join("") +
    row(css("--na"), mode === "q1" ? "Already Poor" : "Already posted or closed", 0) +
    `<p class="fine">Higher-risk bridges are drawn on top, so at national zoom the map looks redder than the counts. Zoom in to see each bridge.</p>`;
}
function drawPoints() {
  const mode = $("#colorBy").value, n = points.byteLength / 12, getColor = colorOf(mode);
  // draw riskier bridges last so they sit on top
  const order = Array.from({ length: n }, (_, i) => i);
  const rank = (i) => mode === "cond" ? points.getUint8(i * 12 + 8) : mode === "flag" ? (points.getUint8(i * 12 + 11) & 1) : points.getUint8(i * 12 + (mode === "q1" ? 9 : 10));
  order.sort((a, b) => rank(a) - rank(b));
  const layer = new deck.ScatterplotLayer({
    id: "bridges", data: { length: n }, pickable: true, radiusUnits: "meters", getRadius: 250, radiusMinPixels: 0.8,
    radiusMaxPixels: 7, opacity: 0.85, getPosition: (_, { index: k }) => { const i = order[k]; return [points.getFloat32(i * 12, true), points.getFloat32(i * 12 + 4, true)]; },
    getFillColor: (_, { index: k }) => getColor(order[k]), updateTriggers: { getFillColor: mode, getPosition: mode },
    onClick: ({ index: k }) => k >= 0 && openDetail(order[k]),
  });
  bridgeLayer = layer;
  overlay.setProps({ layers: [bridgeLayer, labelLayer].filter(Boolean) });
  $("#legend").innerHTML = legend(mode);
}
// Street basemap when openfreemap is reachable; otherwise (offline, or a host that blocks other sites) the built-in
// basemap from scripts/build_basemap.py. Open the page with #builtin-map to force the built-in one.
let places = null, labelLayer = null, bridgeLayer = null;
async function basemapStyle() {
  const STREETS = "https://tiles.openfreemap.org/styles/positron";
  if (location.hash !== "#builtin-map") {
    try {
      const r = await fetch(STREETS, { signal: AbortSignal.timeout(4000) });
      if (r.ok) return { style: STREETS, credit: "" };
    } catch { /* fall through */ }
  }
  const [states, counties, water, roads] = await Promise.all(["us_states", "counties", "water", "roads"].map((n) => json(`basemap/${n}.geojson`)));
  places = (await json("basemap/places.geojson")).features;
  const zoomed = (z0, v0, z1, v1) => ["interpolate", ["linear"], ["zoom"], z0, v0, z1, v1];
  return { credit: "Basemap: US Census (us-atlas), Natural Earth", style: { version: 8,
    sources: { states: { type: "geojson", data: states }, counties: { type: "geojson", data: counties },
      water: { type: "geojson", data: water }, roads: { type: "geojson", data: roads } },
    layers: [
      { id: "bg", type: "background", paint: { "background-color": css("--map-sea") } },
      { id: "land", type: "fill", source: "states", paint: { "fill-color": css("--map-land") } },
      { id: "lakes", type: "fill", source: "water", filter: ["==", ["get", "kind"], "lake"], paint: { "fill-color": css("--map-water") } },
      { id: "rivers", type: "line", source: "water", filter: ["all", ["==", ["get", "kind"], "river"], ["<=", ["get", "rank"], 7]],
        paint: { "line-color": css("--map-water"), "line-width": zoomed(3, 0.6, 10, 2.2) } },
      { id: "rivers-minor", type: "line", source: "water", minzoom: 6, filter: ["all", ["==", ["get", "kind"], "river"], [">", ["get", "rank"], 7]],
        paint: { "line-color": css("--map-water"), "line-width": zoomed(6, 0.4, 10, 1.4) } },
      { id: "counties", type: "line", source: "counties", minzoom: 5, paint: { "line-color": css("--map-border"), "line-opacity": zoomed(5, 0.15, 8, 0.45), "line-width": 0.6 } },
      { id: "roads-minor", type: "line", source: "roads", minzoom: 6, filter: ["==", ["get", "kind"], "minor"],
        paint: { "line-color": css("--map-road"), "line-width": zoomed(6, 0.5, 12, 2.5) } },
      { id: "roads-major", type: "line", source: "roads", minzoom: 4, filter: ["==", ["get", "kind"], "major"],
        paint: { "line-color": css("--map-road"), "line-width": zoomed(4, 0.6, 12, 3.5) } },
      { id: "roads-interstate", type: "line", source: "roads", filter: ["==", ["get", "kind"], "interstate"],
        paint: { "line-color": css("--map-interstate"), "line-width": zoomed(3, 0.6, 12, 4.5) } },
      { id: "states", type: "line", source: "states", paint: { "line-color": css("--map-border"), "line-width": zoomed(3, 0.8, 10, 1.8) } },
    ] } };
}
const rgb = (hex, a = 255) => { const n = parseInt(hex.replace("#", ""), 16); return [n >> 16 & 255, n >> 8 & 255, n & 255, a]; };
// City and county names (deck.gl text, because map-library labels need font files from a server)
function updateLabels() {
  if (!places) return;
  const z = map.getZoom(), ink = rgb(css("--ink")), halo = rgb(css("--map-land"), 230);
  const shown = places.filter((f) => f.properties.kind === "county" ? z >= 8 : f.properties.minzoom <= z + 1.2);
  labelLayer = new deck.TextLayer({ id: "labels", data: shown, getPosition: (f) => f.geometry.coordinates, getText: (f) => f.properties.name,
    getSize: (f) => f.properties.kind === "county" ? 11 : (f.properties.pop > 1e6 ? 14 : 12), getColor: (f) => f.properties.kind === "county" ? rgb(css("--muted")) : ink,
    fontFamily: "Geist, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif", fontWeight: 500, characterSet: "auto",
    fontSettings: { sdf: true }, outlineWidth: 3, outlineColor: halo, getTextAnchor: "middle", getAlignmentBaseline: "center",
    // hide labels that would overlap; bigger cities win, county names give way
    extensions: [new deck.CollisionFilterExtension()], collisionTestProps: { sizeScale: 1.3 },
    getCollisionPriority: (f) => f.properties.kind === "county" ? -1000 : Math.log10(f.properties.pop || 1) * 100 });
  overlay.setProps({ layers: [bridgeLayer, labelLayer].filter(Boolean) });
}
async function initMap() {
  const { style, credit } = await basemapStyle();
  map = new maplibregl.Map({ container: "map", style, center: [-96, 38.5], zoom: 3.4,
    attributionControl: { compact: true, customAttribution: ["Bridges: FHWA National Bridge Inventory", credit].filter(Boolean).join(" · ") } });
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-left");
  overlay = new deck.MapboxOverlay({ interleaved: false, layers: [], getTooltip: null });
  map.addControl(overlay);
  map.on("load", () => { drawPoints(); updateLabels(); });
  map.on("zoomend", updateLabels);
  $("#colorBy").addEventListener("change", drawPoints);
  $("#mapState").addEventListener("change", (e) => flyToState(e.target.value));
  const t = summary.by_state.reduce((a, s) => ({ b: a.b + s.bridges, p: a.p + s.poor, r: a.r + s.restricted, e: a.e + s.expected_new_poor_4y }), { b: 0, p: 0, r: 0, e: 0 });
  $("#mapStats").innerHTML = `${fmt.format(t.b)} bridges · ${fmt.format(t.p)} Poor · ${fmt.format(t.r)} posted or closed<br>` +
    `Expected to become Poor by ${summary.year + 4}: about ${fmt.format(Math.round(t.e))}`;
}
function flyToState(st) {
  if (!st) return map.flyTo({ center: [-96, 38.5], zoom: 3.4 });
  let x0 = 180, x1 = -180, y0 = 90, y1 = -90;
  const [, start, count] = index.states.find((s) => s[0] === st);
  for (let i = start; i < start + count; i++) {
    const x = points.getFloat32(i * 12, true), y = points.getFloat32(i * 12 + 4, true);
    if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y;
  }
  map.fitBounds([[x0, y0], [x1, y1]], { padding: 40, duration: 800 });
}

// ---------------------------------------------------------------- bridge detail
async function openDetail(i) {
  const [st, k] = locate(i);
  const panel = $("#detail");
  panel.hidden = false;
  panel.innerHTML = `<p class="fine">Loading…</p>`;
  const [rows, hist] = await Promise.all([stateData(st), historyData(st)]);
  if (!rows[k]) { panel.innerHTML = `<p>Not found.</p>`; return; }
  showDetail(rows[k], hist[k], st);
}
const nbiNo = (id) => String(id ?? "").replace(/^\d{2}-/, "").replace(/^0+(?=.)/, "");
const realText = (s) => s && /[A-Za-z1-9]/.test(s) ? s : "";
function showDetail(b, h, st) {
  const panel = $("#detail");
  panel.hidden = false;
  const name = [realText(b.carries), realText(b.crosses)].filter(Boolean).map(esc).join(" over ") || `Structure ${esc(nbiNo(b.nbi_id))}`;
  panel.innerHTML = `<button class="close" aria-label="Close">×</button>
    <h2>${name}</h2>
    <p class="fine">${esc(STATES[st] ?? st)} · NBI structure ${esc(nbiNo(b.nbi_id))}${realText(b.location_desc) ? " · " + esc(b.location_desc) : ""}</p>
    <p><span class="pill ${esc(b.condition)}">${esc(b.condition ?? "Not rated")}</span> &nbsp;${esc(POSTING[b.posting] ?? b.posting ?? "")}</p>
    <dl class="kv">
      <dt>Becomes Poor within 4 yr</dt><dd>${b.condition === "Poor" ? "Already Poor" : pct(b.p_poor_4y)}</dd>
      <dt>Weight limit or closure within 4 yr</dt><dd>${b.posting === "A" ? pct(b.p_restricted_4y) : "Already restricted"}</dd>
      <dt>Interval screen</dt><dd>${intervalText(b)}</dd>
      <dt>Built</dt><dd>${esc(b.year_built ?? "–")}</dd>
      <dt>Traffic</dt><dd>${b.adt != null ? fmt.format(b.adt) + " vehicles/day" : "–"}</dd>
      <dt>Type</dt><dd>${esc(MATERIAL[b.material] ?? "")} ${esc((DESIGN[b.design_type] ?? "").toLowerCase())}</dd>
      <dt>Owner</dt><dd>${esc(OWNER[b.owner] ?? b.owner ?? "–")}${b.nhs === "1" ? " · National Highway System" : ""}</dd>
      <dt>Ratings now</dt><dd>deck ${b.deck ?? "N"} · super ${b.superstructure ?? "N"} · sub ${b.substructure ?? "N"} · culvert ${b.culvert ?? "N"}</dd>
      <dt>Treatment cost</dt><dd>${money(b.treatment_cost)} (${b.condition === "Poor" ? "replacement" : "rehabilitation"}, FHWA unit cost)</dd>
      <dt>Detour cost if closed</dt><dd>${b.no_detour ? `No detour route recorded; costed as 100 km: ${money(b.detour_cost_day)} per day`
        : b.detour_cost_day <= 1 ? "Bypass at the site (no detour)" : `${money(b.detour_cost_day)} per day`}</dd>
    </dl>
    <h3>Ratings 1992–2025</h3>${h ? historyChart(h) : "<p class='fine'>No history.</p>"}
    <p class="fine">Screening estimate from public NBI data, not an engineering assessment. The owner agency's inspection and posting are authoritative.</p>`;
  panel.querySelector(".close").addEventListener("click", () => { panel.hidden = true; });
}
function intervalText(b) {
  if (b.interval !== 24) return `${b.interval ?? "–"}-month cycle`;
  if (!b.method1) return "24-month cycle; not Method 1-eligible";
  return `24-month cycle; Method 1-eligible · miss risk ${pct(b.p_q4_miss_4y)}`;
}
function historyChart(h) {
  // [first_year, deck, super, sub, culvert, posting]: one character per year; "." = no record, "N" = not applicable
  const [first, deckS, supS, subS, culvS, postS] = h;
  if (first == null) return "<p class='fine'>No history.</p>";
  const years = [...deckS].map((_, k) => first + k), W = 340, H = 152, L = 26, R = 18, B = 32, T = 6;
  const x = (y) => L + (y - 1992) / (2025 - 1992) * (W - L - R), yv = (r) => T + (9 - r) / 9 * (H - T - B);
  const series = [[deckS, "deck", "deck"], [supS, "super", "superstructure"], [subS, "sub", "substructure"], [culvS, "culv", "culvert"]];
  let svg = `<svg class="hist" viewBox="0 0 ${W} ${H}" role="img" aria-label="Condition ratings by year">`;
  svg += `<rect class="poor-band" x="${L}" y="${yv(4)}" width="${W - L - R}" height="${yv(0) - yv(4)}"/>`;
  svg += `<text class="band-label" x="${L + 4}" y="${yv(0) - 4}">Poor (≤ 4)</text>`;
  for (let r = 0; r <= 9; r++) svg += `<line class="${r === 0 ? "axis" : "grid"}" x1="${L}" x2="${W - R}" y1="${yv(r)}" y2="${yv(r)}"/>`;
  for (const r of [0, 2, 4, 6, 8]) svg += `<text class="tick" x="${L - 6}" y="${yv(r) + 4}" text-anchor="end">${r}</text>`;
  svg += `<line class="axis" x1="${L}" x2="${L}" y1="${yv(9)}" y2="${yv(0)}"/>`;
  for (const y of [1992, 2000, 2010, 2025]) svg += `<line class="axis" x1="${x(y)}" x2="${x(y)}" y1="${yv(0)}" y2="${yv(0) + 4}"/><text class="tick" x="${x(y)}" y="${H - 4}" text-anchor="middle">${y}</text>`;
  for (const [s, cls] of series) {
    const pts = [...s].map((c, k) => /\d/.test(c) ? [x(years[k]), yv(Number(c))] : null);
    let d = "", pen = false;
    for (const p of pts) { if (!p) { pen = false; continue; } d += `${pen ? "L" : "M"}${p[0].toFixed(1)},${p[1].toFixed(1)}`; pen = true; }
    if (d) svg += `<path class="line s-${cls}" d="${d}"/>`;
  }
  const step = (W - L - R) / 33;
  [...postS].forEach((c, k) => { if ("PRK".includes(c)) svg += `<rect class="posted" x="${(x(years[k]) - step / 2).toFixed(1)}" y="${yv(0) + 6}" width="${step.toFixed(1)}" height="4"/>`; });
  svg += "</svg>";
  const key = series.filter(([s]) => /\d/.test(s)).map(([, c, n]) => `<span><i class="sw s-${c}"></i>${n}</span>`).join("");
  return svg + `<div class="hist-key">${key}<span><i class="sw posted"></i>posted/closed</span></div>`;
}

// ---------------------------------------------------------------- risk list
async function renderList() {
  const st = $("#listState").value, metric = $("#listMetric").value, owner = $("#listOwner").value, minAdt = Number($("#listAdt").value) || 0;
  const rows = (await stateData(st)).filter((r) => (!owner || r.owner === owner) && (r.adt ?? 0) >= minAdt && r[metric] != null);
  rows.sort((a, b) => b[metric] - a[metric]);
  const top = rows.slice(0, 200);
  $("#listSummary").textContent = `${fmt.format(rows.length)} bridges match in ${STATES[st]}; showing the top ${top.length}.`;
  $("#listTable").innerHTML = `<thead><tr><th>Bridge</th><th>County</th><th>Owner</th><th class="num">Built</th><th class="num">Traffic/day</th>
    <th>Condition</th><th class="num">Lowest</th><th class="num">P(Poor 4y)</th><th class="num">P(limit/closure 4y)</th><th class="num">Treatment</th></tr></thead><tbody>` +
    top.map((r) => `<tr class="click" data-id="${esc(r.bridge_id)}"><td>${esc([realText(r.carries), realText(r.crosses)].filter(Boolean).join(" / ") || nbiNo(r.nbi_id))}</td>
      <td>${esc(r.county_code)}</td><td>${esc(OWNER[r.owner] ?? r.owner)}</td><td class="num">${r.year_built ?? ""}</td>
      <td class="num">${fmt.format(r.adt ?? 0)}</td><td>${esc(r.condition ?? "")}</td><td class="num">${r.lowest_rating ?? ""}</td>
      <td class="num">${pct(r.p_poor_4y)}</td><td class="num">${pct(r.p_restricted_4y)}</td><td class="num">${money(r.treatment_cost)}</td></tr>`).join("") + "</tbody>";
  $("#listTable").querySelectorAll("tr.click").forEach((tr) => tr.addEventListener("click", () => focusBridge(st, tr.dataset.id)));
}
async function focusBridge(st, id) {
  document.querySelector('.tabs button[data-tab="map"]').click();
  const [rows, hist] = await Promise.all([stateData(st), historyData(st)]);
  const b = rows.find((r) => r.bridge_id === id);
  if (b?.lon) map.flyTo({ center: [b.lon, b.lat], zoom: 12 });
  if (b) showDetail(b, hist[b.k], st);
}

// ---------------------------------------------------------------- planner (same logic as bridgewatch/planner.py)
const budgetOf = (v) => 1e6 * Math.pow(10, v / 100 * 3.5);  // $1 M .. ~$3.2 B
function planOrder(rows, strategy) {
  const key = { worst_first: (r) => [r.lowest_rating ?? 9, -(r.adt ?? 0)], traffic_first: (r) => [-(r.adt ?? 0)],
    risk_first: (r) => [-(r.p_restricted_4y ?? 0)], value_per_dollar: (r) => [-(r.value_per_dollar ?? 0)] }[strategy];
  return rows.map((r) => [key(r), r]).sort((a, b) => a[0][0] - b[0][0] || (a[0][1] ?? 0) - (b[0][1] ?? 0)).map((x) => x[1]);
}
async function renderPlan() {
  const st = $("#planState").value, budget = budgetOf(Number($("#planBudget").value)), strategy = $("#planStrategy").value;
  $("#planBudgetOut").textContent = money(budget);
  const rows = (await stateData(st)).filter((r) => r.posting === "A" && r.treatment_cost > 0);
  let spent = 0; const chosen = [];
  for (const r of planOrder(rows, strategy)) { if (spent + r.treatment_cost > budget) continue; spent += r.treatment_cost; chosen.push(r); }
  const expected = chosen.reduce((a, r) => a + (r.p_restricted_4y ?? 0), 0);
  const avoided = chosen.reduce((a, r) => a + (r.p_restricted_4y ?? 0) * r.detour_cost_day * 365 * 4, 0);
  const card = (v, t) => `<div class="card"><b>${v}</b><small>${t}</small></div>`;
  $("#planSummary").innerHTML = card(fmt.format(chosen.length), "bridges treated") + card(money(spent), "spent") +
    card(expected.toFixed(1), "expected weight limits/closures inside the treated set (4 yr)") + card(money(avoided), "expected detour cost covered (4 yr)");
  $("#planTable").innerHTML = `<thead><tr><th>Bridge</th><th class="num">Traffic/day</th><th>Condition</th><th class="num">P(limit/closure)</th><th class="num">Cost</th></tr></thead><tbody>` +
    chosen.slice(0, 100).map((r) => `<tr class="click" data-id="${esc(r.bridge_id)}"><td>${esc([realText(r.carries), realText(r.crosses)].filter(Boolean).join(" / ") || nbiNo(r.nbi_id))}</td>
      <td class="num">${fmt.format(r.adt ?? 0)}</td><td>${esc(r.condition)}</td><td class="num">${pct(r.p_restricted_4y)}</td><td class="num">${money(r.treatment_cost)}</td></tr>`).join("") + "</tbody>";
  $("#planTable").querySelectorAll("tr.click").forEach((tr) => tr.addEventListener("click", () => focusBridge(st, tr.dataset.id)));
  const close = rows.filter((r) => r.replacement_cost > r.detour_cost_day * 365 * 20).sort((a, b) => a.detour_cost_day - b.detour_cost_day).slice(0, 50);
  $("#closeTable").innerHTML = `<thead><tr><th>Bridge</th><th class="num">Traffic/day</th><th class="num">Detour $/day</th><th class="num">Replacement</th></tr></thead><tbody>` +
    close.map((r) => `<tr><td>${esc([realText(r.carries), realText(r.crosses)].filter(Boolean).join(" / ") || nbiNo(r.nbi_id))}</td><td class="num">${fmt.format(r.adt ?? 0)}</td>
      <td class="num">${money(r.detour_cost_day)}</td><td class="num">${money(r.replacement_cost)}</td></tr>`).join("") + "</tbody>";
  renderPlanBacktest();
}
function renderPlanBacktest() {
  const p = summary.plan;
  if (!p) { $("#planBacktest").innerHTML = "<p class='fine'>Run <code>bridgewatch plan</code> to add the backtest.</p>"; return; }
  const names = { worst_first: "Worst condition first", traffic_first: "Highest traffic first", risk_first: "Highest risk first",
    value_per_dollar: "BridgeWatch (value per $)", value_per_dollar_baseline_risk: "Value per $, baseline risk (control)" };
  const budgets = [...new Set(p.results.map((r) => r.budget))];
  let h = `<table><thead><tr><th>Budget</th><th>Strategy</th><th class="num">Treated</th><th class="num">Events covered</th><th class="num">Exposure covered</th></tr></thead><tbody>`;
  for (const b of budgets) {
    const rs = p.results.filter((r) => r.budget === b), best = Math.max(...rs.map((r) => r.exposure_covered));
    for (const r of rs) h += `<tr class="${r.exposure_covered === best ? "best" : ""}"><td>${money(b)}</td><td>${names[r.strategy]}</td><td class="num">${fmt.format(r.treated)}</td>
      <td class="num">${fmt.format(r.events_covered)} of ${fmt.format(p.events)}</td><td class="num">${pct(r.exposure_covered / p.event_exposure)}</td></tr>`;
  }
  $("#planBacktest").innerHTML = h + "</tbody></table><p class='fine' style='padding:6px 8px'>Nationwide, open bridges in 2017. Events = posted, restricted or closed in 2018–2021. Exposure = traffic × detour length of those events.</p>";
}

// ---------------------------------------------------------------- inspection intervals
async function renderInterval() {
  const st = $("#intState").value, rows = await stateData(st);
  const on24 = rows.filter((r) => r.interval === 24), elig = on24.filter((r) => r.method1);
  const sorted = [...elig].sort((a, b) => (b.p_q4_miss_4y ?? 0) - (a.p_q4_miss_4y ?? 0)), flagged = sorted.slice(0, Math.round(0.1 * elig.length));
  const card = (v, t) => `<div class="card"><b>${v}</b><small>${t}</small></div>`;
  $("#intSummary").innerHTML = card(fmt.format(on24.length), "bridges on a 24-month cycle") + card(fmt.format(elig.length), "meet our Method 1 encoding for 48 months") +
    card(fmt.format(flagged.length), "of those, the riskiest 10% by model");
  $("#intTable").innerHTML = `<thead><tr><th>Bridge</th><th class="num">Built</th><th class="num">Traffic/day</th><th class="num">Lowest</th><th class="num">Miss risk 4y</th></tr></thead><tbody>` +
    flagged.slice(0, 100).map((r) => `<tr class="click" data-id="${esc(r.bridge_id)}"><td>${esc([realText(r.carries), realText(r.crosses)].filter(Boolean).join(" / ") || nbiNo(r.nbi_id))}</td>
      <td class="num">${r.year_built ?? ""}</td><td class="num">${fmt.format(r.adt ?? 0)}</td><td class="num">${r.lowest_rating}</td><td class="num">${pct(r.p_q4_miss_4y)}</td></tr>`).join("") + "</tbody>";
  $("#intTable").querySelectorAll("tr.click").forEach((tr) => tr.addEventListener("click", () => focusBridge(st, tr.dataset.id)));
  const s = summary.screen;
  if (!s) { $("#intBacktest").innerHTML = "<p class='fine'>Run <code>bridgewatch screen</code> to add the backtest.</p>"; return; }
  $("#intBacktest").innerHTML = `<table><thead><tr><th>Base year</th><th>Rule</th><th class="num">Bridges</th><th class="num">Miss rate</th></tr></thead><tbody>` +
    s.map((y) => [["All bridges on 24 months", y.on_24mo, y.miss_rate_all_24mo], ["Method 1 criteria", y.method1.bridges, y.method1.miss_rate],
      ["Model, same number of bridges", y.model_same_count.bridges, y.model_same_count.miss_rate], ["Method 1 minus riskiest 10%", y.hybrid.bridges, y.hybrid.miss_rate],
      ["Already on 48 months (actual practice)", y.already_on_48mo.bridges, y.already_on_48mo.miss_rate]]
      .map(([n, c, m], k) => `<tr><td>${k ? "" : y.base_year}</td><td>${n}</td><td class="num">${fmt.format(c)}</td><td class="num">${pct(m, 2)}</td></tr>`).join("")).join("") + "</tbody></table>";
}

// ---------------------------------------------------------------- was it right?
const METHOD_NAMES = { gbm: "BridgeWatch model", markov: "Markov chain (agency-style)", time_in_cond: "Time in condition",
  rating_lookup: "Rating stays the same (worst-first)", climatology: "Average rate" };
function renderRight() {
  const bt = summary.backtest; if (!bt) return;
  const target = $("#rightTarget").value, h = Number($("#rightH").value), split = $("#rightSplit").value;
  const rows = bt.filter((r) => r.target === target && r.h === h && r.split === split);
  const years = [...new Set(rows.map((r) => r.test_year))].sort();
  if (!years.length) { $("#rightTables").innerHTML = "<p class='fine'>No fold for this combination.</p>"; $("#rightReliability").innerHTML = ""; return; }
  $("#rightTables").innerHTML = years.map((y) => {
    const rs = rows.filter((r) => r.test_year === y).sort((a, b) => b.avg_precision - a.avg_precision), r0 = rs[0];
    return `<h3>Test year ${y}: ${fmt.format(r0.n)} bridges, ${fmt.format(r0.events)} events (${pct(r0.rate, 2)})</h3><div class="table-wrap"><table>
      <thead><tr><th>Method</th><th class="num">Hit rate, top 1%</th><th class="num">Hit rate, top 5%</th><th class="num">Avg. precision</th><th class="num">AUC</th><th class="num">Brier skill</th></tr></thead><tbody>` +
      rs.map((r) => `<tr class="${r.method === "gbm" ? "best" : ""}"><td>${METHOD_NAMES[r.method] ?? r.method}</td><td class="num">${pct(r.precision_top1pct)}</td>
        <td class="num">${pct(r.precision_top5pct)}</td><td class="num">${r.avg_precision.toFixed(3)}</td><td class="num">${r.auc.toFixed(3)}</td>
        <td class="num">${r.brier_skill >= 0 ? "+" : ""}${r.brier_skill.toFixed(3)}</td></tr>`).join("") + "</tbody></table></div>";
  }).join("");
  const g = rows.find((r) => r.method === "gbm" && r.test_year === years.at(-1));
  $("#rightReliability").innerHTML = g ? `<h3>Calibration, test year ${g.test_year}: predicted vs observed (10 equal-size groups)</h3>` + reliabilityChart(g.reliability) : "";
}
function reliabilityChart(bins) {
  const max = Math.max(...bins.map((b) => Math.max(b[0], b[1]))) * 1.08 || 0.01, W = 420, H = 300, L = 46, B = 34, T = 10, R = 10;
  const x = (v) => L + v / max * (W - L - R), y = (v) => H - B - v / max * (H - B - T);
  let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Calibration chart"><line x1="${x(0)}" y1="${y(0)}" x2="${x(max)}" y2="${y(max)}" stroke="${css("--line")}" stroke-dasharray="4 4"/>`;
  for (let k = 0; k <= 4; k++) { const v = max * k / 4; s += `<text x="${x(v)}" y="${H - B + 16}" text-anchor="middle">${pct(v, 0)}</text><text x="${L - 6}" y="${y(v) + 4}" text-anchor="end">${pct(v, 0)}</text>`; }
  s += `<text x="${(L + W) / 2}" y="${H - 4}" text-anchor="middle">predicted risk</text><text x="12" y="${(H - B) / 2}" transform="rotate(-90 12 ${(H - B) / 2})" text-anchor="middle">observed rate</text>`;
  s += `<path d="${bins.map((b, k) => `${k ? "L" : "M"}${x(b[0]).toFixed(1)},${y(b[1]).toFixed(1)}`).join("")}" fill="none" stroke="${css("--accent")}" stroke-width="2"/>`;
  s += bins.map((b) => `<circle cx="${x(b[0])}" cy="${y(b[1])}" r="3.5" fill="${css("--accent")}"/>`).join("");
  return s + "</svg>";
}

const renderers = { list: renderList, plan: renderPlan, interval: renderInterval, right: renderRight };

// ---------------------------------------------------------------- boot
// Hosts that refuse binary files get the same bytes as base64 text (scripts/build_artifact.py writes it).
async function loadPoints() {
  const r = await fetch("data/points.bin");
  if (r.ok && !(r.headers.get("content-type") || "").includes("text/html")) return r.arrayBuffer();
  const t = await fetch("data/points.b64.txt");
  if (!t.ok) throw new Error(`data/points.bin: ${r.status}`);
  return Uint8Array.from(atob(await t.text()), (c) => c.charCodeAt(0)).buffer;
}
(async function boot() {
  try {
    [summary, index] = await Promise.all([json("data/summary.json"), json("data/points_index.json")]);
    points = new DataView(await loadPoints());
  } catch (e) {
    document.querySelector("main").innerHTML = `<p style="padding:16px">Could not load data (${esc(e.message)}). Run <code>bridgewatch export</code> first.</p>`;
    return;
  }
  initStateSelects();
  initTabs();
  await initMap();
  ["#listState", "#listMetric", "#listOwner", "#listAdt"].forEach((s) => $(s).addEventListener("change", renderList));
  ["#planState", "#planStrategy"].forEach((s) => $(s).addEventListener("change", renderPlan));
  $("#planBudget").addEventListener("input", renderPlan);
  $("#intState").addEventListener("change", renderInterval);
  ["#rightTarget", "#rightH", "#rightSplit"].forEach((s) => $(s).addEventListener("change", renderRight));
})();
