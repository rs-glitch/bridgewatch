// Bridges under load. One bench at a time, built from data/tier2/<slug>.json and solved live with BWSolver.
"use strict";
(function () {
  const S = window.BWSolver;
  const $ = (s, r = document) => r.querySelector(s);
  const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  const fmt0 = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
  const fmt1 = new Intl.NumberFormat("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const NS = "http://www.w3.org/2000/svg";
  const el = (tag, attrs = {}, parent) => {
    const e = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
    if (parent) parent.appendChild(e);
    return e;
  };
  const json = (p) => fetch(p).then((r) => { if (!r.ok) throw new Error(`${p}: ${r.status}`); return r.json(); });

  // radio-style segmented controls
  function seg(root, key, onChange) {
    const buttons = [...root.querySelectorAll("button")];
    const set = (b) => { buttons.forEach((x) => x.setAttribute("aria-checked", String(x === b))); onChange(b.dataset[key]); };
    buttons.forEach((b) => b.addEventListener("click", () => set(b)));
    root.addEventListener("keydown", (e) => {
      if (!["ArrowLeft", "ArrowRight"].includes(e.key)) return;
      const k = buttons.findIndex((b) => b.getAttribute("aria-checked") === "true");
      const nb = buttons[(k + (e.key === "ArrowRight" ? 1 : buttons.length - 1)) % buttons.length];
      nb.focus(); set(nb); e.preventDefault();
    });
    return { set: (v) => set(buttons.find((b) => b.dataset[key] === v)) };
  }

  // utilisation colour: pale lavender -> apricot -> ember -> plum at yield
  const STOPS = [[0, [201, 195, 214]], [0.4, [236, 154, 110]], [0.7, [217, 87, 44]], [1, [122, 46, 63]]];
  function ramp(t) {
    t = Math.max(0, Math.min(1, t));
    for (let k = 1; k < STOPS.length; k++) {
      if (t <= STOPS[k][0]) {
        const [t0, a] = STOPS[k - 1], [t1, b] = STOPS[k], f = (t - t0) / (t1 - t0);
        return `rgb(${a.map((v, i) => Math.round(v + f * (b[i] - v))).join(",")})`;
      }
    }
    return `rgb(${STOPS.at(-1)[1].join(",")})`;
  }

  function sourcesHTML(sources) {
    return Object.entries(sources).map(([k, v]) => {
      const tags = ["stated", "measured", "assumed"].filter((t) => new RegExp(`\\b${t}\\b`, "i").test(v));
      return `<dt>${esc(k)}</dt><dd>${tags.map((t) => `<span class="tag tag--${t}">${t}</span>`).join("")}${esc(v)}</dd>`;
    }).join("");
  }
  const head = (d) => `<header class="bench__head"><p class="kicker">${esc(d.kicker)}</p>
    <h2 class="display-md" id="benchTitle">${esc(d.name.replace(/ Bridge$/, ""))}</h2><p class="bench__dek">${esc(d.dek)}</p></header>`;
  const foot = (d) => (d.drawing ? `<figure class="drawing"><img src="bridges/${esc(d.drawing)}" alt="Elevation drawing of ${esc(d.name)} from its HAER record" loading="lazy">
      <figcaption>The drawing the model comes from. ${esc(d.caption)}</figcaption></figure>` : "") +
    `<details class="sources"><summary>Where every number comes from</summary><dl>${sourcesHTML(d.sources)}</dl></details>`;

  function svgPoint(svg, evt) {
    const p = svg.createSVGPoint(); p.x = evt.clientX; p.y = evt.clientY;
    return p.matrixTransform(svg.getScreenCTM().inverse());
  }

  // ======================================================================= truss bench
  function trussBench(d, root) {
    const truckNames = Object.keys(d.trucks);
    root.innerHTML = head(d) + `<div class="bench__grid">
      <div class="stage"><svg class="stage__svg" data-r="svg" role="img" aria-label="${esc(d.name)} truss, members coloured by stress"></svg>
        <div class="stage__tip" data-r="tip" hidden></div><div class="scale" data-r="scale"></div></div>
      <div class="panel">
        <div class="seg" role="radiogroup" aria-label="Load" data-r="load">
          <button role="radio" data-load="none">Own weight</button>
          ${truckNames.map((n, k) => `<button role="radio" data-load="${esc(n)}">${esc(n.match(/\((\d+)-ton/)[1])} t${k ? "" : " truck"}</button>`).join("")}
          <button role="radio" data-load="crowd">Crowd</button>
        </div>
        <label class="slider" data-r="posWrap">Truck position <output data-r="posOut"></output>
          <input type="range" data-r="pos" min="-14" max="${d.deck_x_ft.at(-1)}" step="0.5" value="${Math.round(d.deck_x_ft.at(-1) / 3)}"></label>
        <label class="slider">Show deflection <output data-r="exOut"></output><input type="range" data-r="ex" min="1" max="100" step="1"></label>
        <div class="seg seg--sm" role="radiogroup" aria-label="Colour members by" data-r="colour">
          <button role="radio" data-colour="ratio" aria-checked="true">Share of yield</button><button role="radio" data-colour="sign">Pull or push</button></div>
        <div class="readout"><p class="readout__big"><span data-r="peak">–</span><small>of yield</small></p>
          <p class="readout__line" data-r="who"></p><dl class="kv" data-r="kv"></dl><p class="readout__env" data-r="env"></p></div>
      </div></div>` + foot(d);
    const R = (k) => $(`[data-r="${k}"]`, root);

    const t = { nodes: d.nodes, members: d.members, supports: d.supports, yield_ksi: d.yield_ksi };
    const deck = d.deck_nodes, xs = d.deck_x_ft, x0s = xs[0], span = xs.at(-1) - x0s;
    const dead = S.addLoads(S.selfWeight(t, d.density_lb_ft3), S.panelLoads(deck, xs, { uniform_klf: d.deck_klf }));
    const TRUCKS = Object.fromEntries(Object.entries(d.trucks).map(([k, v]) => [k, v.axles_per_truss]));
    const DECK_Y = d.deck_y_ft ?? 0, k = Math.max(1, span / 89);
    const ys = Object.values(d.nodes).map((p) => p[1]), yMax = Math.max(...ys, DECK_Y + 9), yMin = Math.min(...ys);
    const svg = R("svg"), tip = R("tip");
    const pad = 5 * k, top = yMax + 2 * k, bot = yMin - 4 * k;
    svg.setAttribute("viewBox", `${x0s - pad} ${-top} ${span + 2 * pad} ${top - bot}`);
    const state = { load: truckNames.at(-1) ?? "crowd", pos: +R("pos").value, ex: Math.round(25 * Math.sqrt(k)), colour: "ratio" };
    R("ex").value = state.ex;

    const axlesAt = (load, p) => { const [[, light], [, heavy]] = TRUCKS[load]; return [[p, heavy], [p + 14, light]]; };
    const liveAt = (load, p) => load === "none" ? {} : load === "crowd" ? S.panelLoads(deck, xs, { uniform_klf: d.crowd_klf })
      : S.panelLoads(deck, xs, { axles: axlesAt(load, p) });
    const solveAt = (load, p) => S.solveTruss(t, S.addLoads(dead, liveAt(load, p)));
    const envCache = {};
    function envelope(load) {
      if (envCache[load]) return envCache[load];
      let best = { ratio: 0 };
      for (let p = x0s - 14; p <= xs.at(-1); p += Math.max(1, span / 120)) {
        for (const mm of solveAt(load, p).members) if (mm.ratio > best.ratio) best = { ratio: mm.ratio, id: mm.id, group: mm.group, p };
      }
      return (envCache[load] = best);
    }

    // scenery: abutments under the end supports
    const g0 = el("g", {}, svg), fs = 1.15 * k, sup = Object.keys(d.supports);
    const sx = sup.map((n) => d.nodes[n][0]), sy = Math.min(...sup.map((n) => d.nodes[n][1]));
    for (const [a, b] of [[x0s - pad, Math.min(...sx) + 0.6 * k], [Math.max(...sx) - 0.6 * k, xs.at(-1) + pad]]) {
      el("rect", { x: a, y: -(sy - 0.3), width: b - a, height: 4 * k, rx: 0.4, fill: css("--panel-2"), stroke: css("--line"), "stroke-width": 0.08 * k }, g0);
    }
    el("text", { x: x0s + span / 2, y: -(bot + 0.8 * k), "text-anchor": "middle", "font-size": fs, "letter-spacing": 0.15 }, g0).textContent =
      `${fmt0.format(span)} ft between ${sup.length === 2 ? "bearings" : "supports"}`;
    const truckG = el("g", { class: "grab", tabindex: 0, role: "slider", "aria-label": "Truck, drag to move" }, svg);
    const deckLine = el("polyline", { fill: "none", stroke: css("--muted"), "stroke-width": 0.32 * k, "stroke-linecap": "round" }, svg);
    const crowdBand = el("polygon", { fill: css("--accent"), opacity: 0.18 }, svg);
    const memG = el("g", {}, svg), nodeG = el("g", {}, svg);
    const lines = d.members.map((mm) => el("line", { "stroke-linecap": "round", "stroke-width": ((0.16 + 0.052 * Math.min(mm.area, 18)) * Math.sqrt(k)).toFixed(3) }, memG));
    const hits = d.members.map((mm) => el("line", { stroke: "transparent", "stroke-width": 1.6 * k, "data-id": mm.id, style: "cursor:help" }, memG));
    const names = Object.keys(d.nodes);
    const dots = names.map(() => el("circle", { r: 0.3 * Math.sqrt(k), fill: css("--panel"), stroke: css("--ink"), "stroke-width": 0.12 * Math.sqrt(k) }, nodeG));
    const ink = css("--ink");
    el("rect", { x: -3.2, y: -8.2, width: 14.6, height: 6.4, rx: 0.5, fill: ink, opacity: 0.1, stroke: ink, "stroke-width": 0.12 }, truckG);
    el("path", { d: "M11.6 -1.8 V-6.2 h3.1 l2.1 2.6 v2.0 z", fill: ink, opacity: 0.16, stroke: ink, "stroke-width": 0.12 }, truckG);
    for (const x of [0, 14]) el("circle", { cx: x, cy: -1.25, r: 1.15, fill: css("--panel"), stroke: ink, "stroke-width": 0.22 }, truckG);
    const truckLabel = el("text", { x: 4.1, y: -4.4, "text-anchor": "middle", "font-size": 1.25, "font-weight": 600 }, truckG);

    const deckDisp = (r, x) => {
      let j = 0;
      while (j < xs.length - 2 && x >= xs[j + 1]) j++;
      const f = Math.max(0, Math.min(1, (x - xs[j]) / (xs[j + 1] - xs[j])));
      return r.disp_in[deck[j]][1] * (1 - f) + r.disp_in[deck[j + 1]][1] * f;
    };
    let last = null;
    function draw() {
      const r = solveAt(state.load, state.pos), sc = state.ex / 12;
      last = r;
      const P = (n) => { const [x, y] = d.nodes[n], [ux, uy] = r.disp_in[n]; return [x + ux * sc, -(y + uy * sc)]; };
      const tension = css("--s-deck"), comp = css("--accent");
      d.members.forEach((mm, j) => {
        const [x1, y1] = P(mm.i), [x2, y2] = P(mm.j), res = r.members[j];
        for (const ln of [lines[j], hits[j]]) { ln.setAttribute("x1", x1); ln.setAttribute("y1", y1); ln.setAttribute("x2", x2); ln.setAttribute("y2", y2); }
        const col = state.colour === "ratio" ? ramp(res.ratio) : res.force_kip >= 0 ? tension : comp;
        lines[j].setAttribute("stroke", res.active ? col : css("--muted"));
        lines[j].setAttribute("opacity", res.active ? (state.colour === "sign" ? (0.35 + 0.65 * Math.min(1, res.ratio / 0.6)).toFixed(2) : 1) : 0.35);
        lines[j].setAttribute("stroke-dasharray", res.active ? "none" : `${0.5 * k} ${0.5 * k}`);
      });
      names.forEach((n, j) => { const [x, y] = P(n); dots[j].setAttribute("cx", x); dots[j].setAttribute("cy", y); });
      const pts = [];
      for (let x = x0s; x <= xs.at(-1) + 1e-9; x += span / 90) pts.push([x, -(DECK_Y + deckDisp(r, x) * sc)]);
      deckLine.setAttribute("points", pts.map((p) => p.join(",")).join(" "));
      crowdBand.setAttribute("points", state.load === "crowd" ? [...pts.map(([x, y]) => `${x},${y - 0.25}`), ...pts.slice().reverse().map(([x, y]) => `${x},${y - 1.7}`)].join(" ") : "");
      const truck = state.load !== "none" && state.load !== "crowd";
      truckG.style.display = truck ? "" : "none";
      R("posWrap").hidden = !truck;
      if (truck) {
        const xm = Math.max(x0s, Math.min(xs.at(-1), state.pos + 7)), y = -(DECK_Y + deckDisp(r, xm) * sc) - 0.15;
        truckG.setAttribute("transform", `translate(${state.pos} ${y})`);
        truckLabel.textContent = state.load.split(" ")[0];
        truckG.setAttribute("aria-valuenow", state.pos);
      }
      readout(r);
    }
    const sign = (f) => f >= 0 ? "pulling (tension)" : "pushing (compression)";
    function readout(r) {
      const w = r.members.reduce((a, b) => b.ratio > a.ratio ? b : a);
      R("peak").textContent = `${Math.round(100 * w.ratio)}%`;
      R("who").innerHTML = `Busiest member: <b>${esc(w.id)}</b>, ${esc(w.group)}, ${fmt1.format(Math.abs(w.stress_ksi))} ksi ${sign(w.force_kip)}`;
      const slack = r.members.filter((mm) => !mm.active).length, only = d.members.filter((mm) => mm.tension_only).length;
      const rx = r.reactions_kip, [a, b] = [sup[0], sup.at(-1)];
      R("kv").innerHTML = `<dt>Sag at mid-span</dt><dd>${fmt1.format(Math.max(0, -r.disp_in[d.mid_node][1]))} in</dd>` +
        `<dt>Support reactions</dt><dd>${fmt1.format(rx[a][1])} kip left · ${fmt1.format(rx[b][1])} kip right</dd>` +
        `<dt>Slack members</dt><dd>${slack} of ${only} that can only pull</dd>`;
      const env = state.load === "none" || state.load === "crowd" ? null : envelope(state.load);
      R("env").textContent = state.load === "none" ? "Dead load only: the truss itself, the deck and the floor system."
        : !env ? `A 100 lb/ft² crowd over the whole ${fmt1.format(d.roadway_ft)} ft ${d.trucks && truckNames.length ? "roadway" : "walkway"}.`
          : `Worst moment of the crossing: ${Math.round(100 * env.ratio)}% of yield in ${env.id} (${env.group}), rear axle ${fmt0.format(env.p - x0s)} ft from the left bearing.`;
      R("posOut").textContent = `rear axle ${fmt0.format(state.pos - x0s)} ft`;
      R("exOut").textContent = `× ${state.ex}`;
    }

    const stage = svg.parentElement;
    const PROV = d.sources;
    let dragging = false, grabDx = 0;
    svg.addEventListener("pointermove", (e) => {
      const id = e.target.dataset?.id;
      if (!id || dragging) { tip.hidden = true; return; }
      const j = d.members.findIndex((mm) => mm.id === id), mm = d.members[j], res = last.members[j];
      const src = PROV[mm.group] ?? PROV[`${mm.group}s`] ?? "";
      tip.innerHTML = `<b>${esc(mm.id)} · ${esc(mm.group)}</b>${res.active ? `${fmt1.format(Math.abs(res.force_kip))} kip ${sign(res.force_kip)}<br>` +
        `${fmt1.format(Math.abs(res.stress_ksi))} ksi, ${Math.round(100 * res.ratio)}% of yield` : "Slack: it can only pull, so it carries nothing here"}` +
        `<br>Area ${mm.area} in²${src ? `<span class="src">${esc(src)}</span>` : ""}`;
      tip.hidden = false;
      const bb = stage.getBoundingClientRect(), x = e.clientX - bb.left, y = e.clientY - bb.top;
      tip.style.left = `${Math.max(8, Math.min(x + 14, bb.width - tip.offsetWidth - 8))}px`;
      tip.style.top = `${Math.max(8, y - tip.offsetHeight - 12)}px`;
    });
    svg.addEventListener("pointerleave", () => { tip.hidden = true; });
    const posInput = R("pos");
    const setPos = (p) => { state.pos = Math.max(x0s - 14, Math.min(xs.at(-1), Math.round(p * 2) / 2)); posInput.value = state.pos; draw(); };
    truckG.addEventListener("pointerdown", (e) => { dragging = true; grabDx = svgPoint(svg, e).x - state.pos; truckG.setPointerCapture(e.pointerId); tip.hidden = true; });
    truckG.addEventListener("pointermove", (e) => { if (dragging) setPos(svgPoint(svg, e).x - grabDx); });
    truckG.addEventListener("pointerup", () => { dragging = false; });
    truckG.addEventListener("keydown", (e) => {
      const step = { ArrowRight: 1, ArrowLeft: -1 }[e.key];
      if (step) { setPos(state.pos + step * (e.shiftKey ? 5 : 1)); e.preventDefault(); }
    });
    posInput.addEventListener("input", () => setPos(+posInput.value));
    R("ex").addEventListener("input", (e) => { state.ex = +e.target.value; draw(); });
    const loads = seg(R("load"), "load", (v) => { state.load = v; draw(); });
    seg(R("colour"), "colour", (v) => { state.colour = v; scaleKey(); draw(); });
    function scaleKey() {
      R("scale").innerHTML = state.colour === "ratio"
        ? `<span>0%</span><i style="background:linear-gradient(90deg,${[0, .2, .4, .55, .7, .85, 1].map(ramp).join(",")})"></i><span>100% of yield</span><span>· dashed = slack</span>`
        : `<span><i style="display:inline-block;width:18px;height:4px;background:${css("--s-deck")}"></i> pulling</span><span><i style="display:inline-block;width:18px;height:4px;background:${css("--accent")}"></i> pushing</span><span>· dashed = slack</span>`;
    }
    scaleKey();
    loads.set(state.load);
  }

  // ======================================================================= suspension bench
  function spanBench(d, root) {
    const [endA, endB] = d.ends, checks = d.checks ?? [], stiff = d.stiffener ?? "truss";
    root.innerHTML = head(d) + `<div class="bench__grid">
      <div class="stage"><svg class="stage__svg stage__svg--wide" data-r="svg" role="img" aria-label="${esc(d.name)} main span with loaded stretch and deflected deck"></svg>
        <svg class="stage__chart" data-r="chart" role="img" aria-label="Deck deflection along the main span"></svg></div>
      <div class="panel">
        <div class="seg" role="radiogroup" aria-label="Traffic pattern" data-r="mode">
          <button role="radio" data-mode="one" aria-checked="true">One stretch</button><button role="radio" data-mode="ends">Both ends</button>
          <button role="radio" data-mode="none">No traffic</button></div>
        <label class="slider" data-r="centreWrap">Centre of traffic <output data-r="centreOut"></output>
          <input type="range" data-r="centre" min="0" max="${d.span.L}" step="10"></label>
        <label class="slider">Length of traffic <output data-r="lenOut"></output><input type="range" data-r="len" min="100" max="${d.span.L}" step="10"></label>
        <label class="slider">Temperature change <output data-r="tOut"></output><input type="range" data-r="t" min="-40" max="40" step="1"></label>
        <div class="readout"><p class="readout__big"><span data-r="mid">–</span><small data-r="midDir">at mid-span</small></p><dl class="kv" data-r="kv"></dl></div>
      </div></div>
      <div class="checks"><h3>Checked against the engineers' own numbers</h3><div class="table-wrap"><table class="check" data-r="check"></table></div></div>` + foot(d);
    const R = (k) => $(`[data-r="${k}"]`, root);
    const s = d.span, L = s.L, mid = s.n / 2, W = d.live_klf_per_cable;
    const state = { mode: "one", centre: L / 2, len: L / 2, dT: 0 };
    const VS = 1.5, EX = 10;
    const patches = (st) => st.mode === "none" ? [] : st.mode === "ends" ? [[0, Math.min(st.len, L / 2)], [L - Math.min(st.len, L / 2), L]]
      : [[Math.max(0, st.centre - st.len / 2), Math.min(L, st.centre + st.len / 2)]];
    const loadOf = (st) => {
      const p = new Array(s.n + 1).fill(0);
      for (const [a, b] of patches(st)) S.patch(s, a, b, W).forEach((v, i) => { p[i] += v; });
      return p;
    };
    // a published check, recomputed here: [value, the state that shows it] (same cases as suspension.check in Python)
    function runCheck(c) {
      const dT = c.dT ?? 0, n = s.n;
      if (c.kind === "half_q_down" || c.kind === "half_3q_up") {
        const st = { mode: "one", centre: L / 4, len: L / 2, dT };
        const v = S.solveSpan(s, loadOf(st), dT).defl_ft;
        return [c.kind === "half_q_down" ? v[n / 4] : -v[3 * n / 4], st];
      }
      if (c.kind === "full_c_down") { const st = { mode: "one", centre: L / 2, len: L, dT }; return [S.solveSpan(s, loadOf(st), dT).defl_ft[mid], st]; }
      let best = [-Infinity, null];
      for (let j = 0; j <= 40; j++) {
        const a = (j + 1) / 42 * L / 2;
        const st = c.kind === "temp_c_down" ? { mode: "one", centre: L / 2, len: 2 * a, dT } : { mode: "ends", centre: L / 2, len: a, dT };
        const v = S.solveSpan(s, loadOf(st), dT).defl_ft[mid] * (c.kind === "temp_c_down" ? 1 : -1);
        if (v > best[0]) best = [v, st];
      }
      return best;
    }
    const results = checks.map(runCheck);
    if (checks.length) {
      R("check").innerHTML = `<thead><tr><th>Case</th><th class="num">Model</th><th class="num">Published</th><th>Source</th><th></th></tr></thead><tbody>` +
        checks.map((c, j) => `<tr><td>${esc(c.label)}</td><td class="num">${fmt1.format(results[j][0])} ft</td><td class="num">${fmt1.format(c.report_ft)} ft</td>
          <td class="fine">${esc(c.source)}</td><td><button class="show" data-check="${j}">Show</button></td></tr>`).join("") + "</tbody>";
    } else root.querySelector(".checks").hidden = true;

    const svg = R("svg"), side = 0.15 * L, x0 = -side, x1 = L + side, cab0 = 10 + s.f;
    const yTop = (cab0 + 0.04 * L + 40) * VS, yBot = (0.06 * L + 40) * VS;
    svg.setAttribute("viewBox", `${x0} ${-yTop} ${x1 - x0} ${yTop + yBot}`);
    const Y = (ft) => -ft * VS, sw = L / 4200;
    const cableAt = (x) => 10 + s.f * (2 * x / L - 1) ** 2;
    const g = el("g", {}, svg), water = -0.05 * L;
    el("rect", { x: x0, y: Y(water), width: x1 - x0, height: yBot, fill: css("--map-water"), opacity: 0.55 }, g);
    const slope = 4 * s.f / L;
    for (const [tx, dir] of [[0, -1], [L, 1]]) {
      el("line", { x1: tx, y1: Y(cab0), x2: tx + dir * side, y2: Y(cab0 - slope * side), stroke: css("--accent"), "stroke-width": 9 * sw }, g);
      el("line", { x1: tx, y1: Y(0), x2: tx + dir * side, y2: Y(0), stroke: css("--muted"), "stroke-width": 12 * sw }, g);
      el("rect", { x: tx - 22 * sw, y: Y(cab0 + 26 * sw), width: 44 * sw, height: (cab0 + 26 * sw - water) * VS, fill: css("--accent"), opacity: 0.85 }, g);
    }
    const lbl = (x, y, txt) => { el("text", { x, y, "text-anchor": "middle", "font-size": 70 * sw }, g).textContent = txt; };
    lbl(0, Y(cab0 + 60 * sw), `${endA} tower`); lbl(L, Y(cab0 + 60 * sw), `${endB} tower`);
    lbl(L / 2, Y(water) + yBot * 0.55, `${fmt0.format(L)} ft main span · deck movement drawn × ${EX}, heights × ${VS}`);
    const trafficG = el("g", {}, svg);
    const hangers = el("path", { stroke: css("--muted"), "stroke-width": 3 * sw, opacity: 0.55, fill: "none" }, svg);
    const cable = el("polyline", { fill: "none", stroke: css("--accent"), "stroke-width": 10 * sw, "stroke-linejoin": "round" }, svg);
    el("line", { x1: 0, x2: L, y1: Y(0), y2: Y(0), stroke: css("--muted"), "stroke-width": 3 * sw, "stroke-dasharray": `${18 * sw} ${18 * sw}`, opacity: 0.6 }, svg);
    const deckLine = el("polyline", { fill: "none", stroke: css("--ink"), "stroke-width": 14 * sw, "stroke-linejoin": "round" }, svg);
    const grab = el("rect", { x: 0, y: Y(cab0 * 0.25), width: L, height: cab0 * 0.5 * VS, fill: "transparent", class: "grab" }, svg);

    const ch = R("chart"), CW = 1000, CH = 230, cl = 52, cr = 16, ct = 14, cb = 30;
    const ext = Math.max(4, ...checks.map((c) => c.report_ft), ...results.map((r) => Math.abs(r[0]))) * 1.25;
    const vmin = -ext * 0.75, vmax = ext;
    ch.setAttribute("viewBox", `0 0 ${CW} ${CH}`);
    const cx = (x) => cl + x / L * (CW - cl - cr), cy = (v) => ct + (v - vmin) / (vmax - vmin) * (CH - ct - cb);
    const tickStep = ext > 20 ? 10 : ext > 8 ? 5 : ext > 3 ? 2 : 1;
    for (let v = -Math.floor(-vmin / tickStep) * tickStep; v <= vmax; v += tickStep) {
      el("line", { x1: cl, x2: CW - cr, y1: cy(v), y2: cy(v), stroke: css(v ? "--grid" : "--muted"), "stroke-width": 1 }, ch);
      el("text", { x: cl - 8, y: cy(v) + 4, "text-anchor": "end", "font-size": 11 }, ch).textContent = v === 0 ? "0 ft" : v > 0 ? `${v} ↓` : `${-v} ↑`;
    }
    for (const f of [0, 0.25, 0.5, 0.75, 1]) el("text", { x: cx(f * L), y: CH - 8, "text-anchor": "middle", "font-size": 11 }, ch).textContent = `${fmt0.format(f * L)} ft`;
    const markG = el("g", {}, ch);
    const band = el("g", {}, ch);
    const curve = el("polyline", { fill: "none", stroke: css("--accent"), "stroke-width": 2.5, "stroke-linejoin": "round" }, ch);
    const midDot = el("circle", { r: 4.5, fill: css("--accent"), stroke: css("--panel"), "stroke-width": 2 }, ch);
    let shown = -1;
    function marker() {   // the published value for the check being shown, at the point it refers to
      markG.innerHTML = "";
      if (shown < 0) return;
      const c = checks[shown], at = c.kind === "half_q_down" ? L / 4 : c.kind === "half_3q_up" ? 3 * L / 4 : L / 2;
      const v = c.kind.endsWith("up") ? -c.report_ft : c.report_ft;
      el("line", { x1: cx(at) - 26, x2: cx(at) + 26, y1: cy(v), y2: cy(v), stroke: css("--ink"), "stroke-width": 1.5, "stroke-dasharray": "3 3" }, markG);
      el("text", { x: cx(at) + 32, y: cy(v) + 4, "font-size": 11 }, markG).textContent = `published: ${fmt1.format(c.report_ft)} ft`;
    }

    function draw() {
      const r = S.solveSpan(s, loadOf(state), state.dT), v = r.defl_ft, n = s.n;
      const pts = [], cab = [];
      let hp = "";
      const hs = Math.max(1, Math.round(n / 42));
      for (let i = 0; i <= n; i += 2) {
        const x = r.x_ft[i], dy = -v[i] * EX;
        pts.push(`${x},${Y(dy)}`); cab.push(`${x},${Y(cableAt(x) + dy)}`);
      }
      for (let i = hs; i < n; i += hs) { const dy = -v[i] * EX; hp += `M${r.x_ft[i]} ${Y(dy)}V${Y(cableAt(r.x_ft[i]) + dy)}`; }
      deckLine.setAttribute("points", pts.join(" ")); cable.setAttribute("points", cab.join(" ")); hangers.setAttribute("d", hp);
      trafficG.innerHTML = ""; band.innerHTML = "";
      for (const [a, b] of patches(state)) {
        const ia = Math.round(a / L * n), ib = Math.round(b / L * n), tp = [], bt = [];
        for (let i = ia; i <= ib; i++) { const dy = -v[i] * EX; tp.push(`${r.x_ft[i]},${Y(dy + 16 * sw)}`); bt.unshift(`${r.x_ft[i]},${Y(dy + 4 * sw)}`); }
        el("polygon", { points: [...tp, ...bt].join(" "), fill: css("--ember"), opacity: 0.85 }, trafficG);
        el("rect", { x: cx(a), y: ct, width: cx(b) - cx(a), height: CH - ct - cb, fill: css("--accent"), opacity: 0.08 }, band);
      }
      const cps = [];
      for (let i = 0; i <= n; i += 2) cps.push(`${cx(r.x_ft[i]).toFixed(1)},${cy(v[i]).toFixed(1)}`);
      curve.setAttribute("points", cps.join(" "));
      midDot.setAttribute("cx", cx(L / 2)); midDot.setAttribute("cy", cy(v[mid]));
      const vm = v[mid];
      R("mid").textContent = `${fmt1.format(Math.abs(vm))} ft`;
      R("midDir").textContent = Math.abs(vm) < 0.05 ? "at mid-span" : vm > 0 ? "down at mid-span" : "up at mid-span";
      let iMax = 0, iMin = 0;
      v.forEach((y, i) => { if (y > v[iMax]) iMax = i; if (y < v[iMin]) iMin = i; });
      const Mmax = r.moment_kft.reduce((a, b) => Math.max(a, Math.abs(b)), 0);
      R("kv").innerHTML =
        `<dt>Deepest sag</dt><dd>${v[iMax] > 0.05 ? `${fmt1.format(v[iMax])} ft, ${fmt0.format(r.x_ft[iMax])} ft from ${esc(endA)}` : "none"}</dd>` +
        `<dt>Highest lift</dt><dd>${v[iMin] < -0.05 ? `${fmt1.format(-v[iMin])} ft, ${fmt0.format(r.x_ft[iMin])} ft from ${esc(endA)}` : "none"}</dd>` +
        `<dt>Cable pull at tower</dt><dd>${fmt0.format(r.cable_max_kip)} kip per cable (${fmt1.format(r.cable_max_kip / 1000)} million lb)</dd>` +
        `<dt>Cable stress</dt><dd>${fmt1.format(r.cable_max_kip / s.Ac_in2)} ksi</dd>` +
        `<dt>Extra pull from traffic</dt><dd>${r.h_kip >= 0 ? "+" : "−"}${fmt0.format(Math.abs(r.h_kip))} kip</dd>` +
        `<dt>Peak ${stiff} bending</dt><dd>${fmt0.format(Mmax)} kip·ft (flange force ${fmt0.format(Mmax / s.depth_ft)} kip)</dd>`;
      R("centreOut").textContent = `${fmt0.format(state.centre)} ft from ${endA}`;
      R("lenOut").textContent = `${fmt0.format(state.len)} ft${state.mode === "ends" ? " each end" : ""}`;
      R("tOut").textContent = `${state.dT > 0 ? "+" : ""}${state.dT}°F`;
      marker();
    }
    const cIn = R("centre"), lIn = R("len"), tIn = R("t");
    const sync = () => { lIn.max = state.mode === "ends" ? L / 2 : L; cIn.value = state.centre; lIn.value = state.len; tIn.value = state.dT;
      R("centreWrap").hidden = state.mode !== "one"; draw(); };
    const user = () => { shown = -1; root.querySelectorAll("button.show").forEach((b) => b.removeAttribute("aria-pressed")); };
    cIn.addEventListener("input", () => { user(); state.centre = +cIn.value; draw(); });
    lIn.addEventListener("input", () => { user(); state.len = +lIn.value; draw(); });
    tIn.addEventListener("input", () => { user(); state.dT = +tIn.value; draw(); });
    let quiet = false;
    const modes = seg(R("mode"), "mode", (mo) => { if (!quiet) user(); state.mode = mo; if (mo === "ends") state.len = Math.min(state.len, L / 2); sync(); });
    root.querySelectorAll("button.show").forEach((b) => b.addEventListener("click", (e) => {
      const j = +b.dataset.check;
      Object.assign(state, results[j][1]);
      quiet = true; modes.set(state.mode); quiet = false;
      shown = j; root.querySelectorAll("button.show").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
      marker();
      if (e.isTrusted) R("svg").scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "center" });
    }));
    let dragging = false;
    const toCentre = (e) => { user(); state.centre = Math.max(0, Math.min(L, Math.round(svgPoint(svg, e).x / 10) * 10)); if (state.mode !== "one") modes.set("one"); else sync(); };
    grab.addEventListener("pointerdown", (e) => { dragging = true; grab.setPointerCapture(e.pointerId); toCentre(e); });
    grab.addEventListener("pointermove", (e) => { if (dragging) toCentre(e); });
    grab.addEventListener("pointerup", () => { dragging = false; });
    if (checks.length) root.querySelector('button.show[data-check="0"]').click(); else sync();
  }

  // ======================================================================= picker
  // The 20-bridge target set, in page order. Slugs appear once a model exists (data/tier2/index.json).
  const TARGET = [["Golden Gate", "golden_gate"], ["Brooklyn"], ["Tacoma Narrows (1940)", "tacoma_narrows"], ["Bay Bridge, west span"], ["Huey P. Long"],
    ["Eads"], ["George Washington", "george_washington"], ["Arlington Memorial bascule"], ["St. Johns"], ["Edmund Pettus"], ["Kelley Crossing", "kelley_crossing"],
    ["Walnut Street", "walnut_street"], ["Slate Run", "slate_run"], ["Old Army Bridge, North Platte"], ["Old Corinth Road", "old_corinth"],
    ["Nicholson lenticular", "nicholson"], ["Bridge L5245", "bridge_l5245"], ["Whetstone Creek", "whetstone_creek"],
    ["Watkins Glen footbridge"], ["Cooper's tubular arch", "coopers_arch"]];
  const benchEl = $("#bench"), cache = {};
  json("data/tier2/index.json").then((index) => {
    const bySlug = Object.fromEntries(index.map((b) => [b.slug, b]));
    const slugOf = (sl) => sl && bySlug[sl] ? sl : null;
    const list = $("#progressList");
    list.innerHTML = TARGET.map(([n, slug]) => { const sl = slugOf(slug); return sl ? `<li class="done"><button data-slug="${sl}">${esc(n)}</button></li>` : `<li>${esc(n)}</li>`; }).join("");
    $("#doneCount").textContent = index.length;
    async function show(slug, scroll) {
      if (!bySlug[slug]) slug = index[0].slug;
      list.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.slug === slug)));
      const d = cache[slug] ?? (cache[slug] = await json(`data/tier2/${slug}.json`));
      benchEl.innerHTML = `<section class="bench" aria-labelledby="benchTitle"></section>`;
      (d.kind === "span" ? spanBench : trussBench)(d, benchEl.firstElementChild);
      try { history.replaceState(null, "", `#${slug}`); } catch { /* sandboxed */ }
      if (scroll) benchEl.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
    }
    list.addEventListener("click", (e) => { const b = e.target.closest("button[data-slug]"); if (b) show(b.dataset.slug, true); });
    show(location.hash.slice(1), false);
  }).catch((e) => { benchEl.innerHTML = `<p class="fine">Could not load the models (${esc(e.message)}). Run <code>bridgewatch sim</code>.</p>`; });
})();
