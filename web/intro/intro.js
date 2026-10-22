/* BridgeWatch intro: one fixed world (the real bridge map), flown by page scroll.
   Scroll position t is measured in viewport-heights. The camera, the colour of the grains, the forecast year and the
   embers are all functions of t, eased, then lerped every frame so the motion stays fluid under an uneven wheel. */
(function () {
  "use strict";
  const $ = (s) => document.querySelector(s);
  const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  const rgb = (hex, a = 255) => { const n = parseInt(hex.replace("#", ""), 16); return [n >> 16 & 255, n >> 8 & 255, n & 255, a]; };
  const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
  const smooth = (x) => { x = clamp(x); return x * x * (3 - 2 * x); };
  const lerp = (a, b, k) => a + (b - a) * k;
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const fine = matchMedia("(hover: hover) and (pointer: fine)").matches;
  const phone = () => innerWidth <= 760;

  const HPL = [-90.1656, 29.94133];  // Huey P. Long Bridge, NBI 22-022600060100001

  // ---------------------------------------------------------------- track
  const wps = [...document.querySelectorAll(".wp")];
  wps.forEach((el) => el.style.setProperty("--span", el.dataset.wpSpan));
  const starts = []; let acc = 0;
  wps.forEach((el) => { starts.push(acc); acc += Number(el.dataset.wpSpan); });
  const T_END = acc - 1;  // the furthest the page can scroll, in viewport-heights

  // Camera keyframes along the track. Phones get a flatter, more central framing.
  const KEYS = () => {
    const p = phone();
    return [
      // horizon: aim beyond the bridge, pad the top so the horizon sits just under the headline and the bridge stands in front of it
      { t: 0,           lon: HPL[0] - (p ? 0.12 : 1.0), lat: HPL[1] + (p ? 0.55 : 0.8), zoom: p ? 6.7 : 7.2, pitch: 85, bearing: 0, pad: p ? 0.42 : 0.333 },
      { t: starts[1],   lon: p ? -97 : -103.5, lat: p ? 36.5 : 38.6, zoom: p ? 2.45 : 3.3, pitch: 34, bearing: -10 },  // the whole country
      { t: starts[2],   lon: -93.0, lat: 37.6, zoom: p ? 2.75 : 3.7, pitch: 42, bearing: -14 },   // condition
      { t: starts[3],   lon: -91.8, lat: 37.4, zoom: p ? 2.8 : 3.78, pitch: 44, bearing: -15 },   // hush: settles
      { t: starts[4],   lon: -91.6, lat: 37.4, zoom: p ? 2.82 : 3.8, pitch: 44, bearing: -15 },   // hush held
      { t: starts[5],   lon: -87.8, lat: 36.4, zoom: p ? 3.25 : 4.25, pitch: 54, bearing: 8 },    // forecast drift east
      { t: starts[6],   lon: -90.0, lat: 31.6, zoom: p ? 5.6 : 6.4, pitch: 58, bearing: 16 },     // south toward Louisiana
      { t: T_END,       lon: HPL[0] + (p ? 0.0 : 0.05), lat: HPL[1] + (p ? -0.02 : -0.01), zoom: p ? 10.6 : 11.3, pitch: 56, bearing: 18 },  // landing
    ];
  };
  let keys = KEYS();
  function cameraAt(t) {
    if (reduced) {  // reduced motion: hold one pose per waypoint, change only between them
      const i = wpIndex(t); const k = keys[Math.min(i + (i >= 4 ? 1 : 0), keys.length - 1)];
      return { pad: 0, ...k };
    }
    let i = 0; while (i < keys.length - 2 && t > keys[i + 1].t) i++;
    const a = keys[i], b = keys[i + 1], u = smooth((t - a.t) / Math.max(1e-6, b.t - a.t));
    return { lon: lerp(a.lon, b.lon, u), lat: lerp(a.lat, b.lat, u), zoom: lerp(a.zoom, b.zoom, u), pitch: lerp(a.pitch, b.pitch, u),
      bearing: lerp(a.bearing, b.bearing, u), pad: lerp(a.pad || 0, b.pad || 0, u) };
  }
  function wpIndex(t) { let i = 0; while (i < starts.length - 1 && t >= starts[i + 1] - 0.35) i++; return i; }
  // forecast year fraction, 0 at 2025 and 1 at 2029
  const yearFrac = (t) => reduced ? Math.floor(clamp((t - starts[4] - 0.2) / 1.9) * 4.999) / 4 : smooth(clamp((t - starts[4] - 0.25) / 1.55));
  // colour mode of the grains: sand, condition, or dim (behind the embers)
  const colourMode = (t) => (t >= starts[2] - 0.45 && t < starts[3] + 0.15) ? "cond" : (t >= starts[4] - 0.1 && t < starts[5] + 0.4) ? "dim" : (t >= starts[6] - 0.3 ? "cond" : "sand");

  // ---------------------------------------------------------------- data
  async function loadPoints() {
    const r = await fetch("data/points.bin");
    if (r.ok && !(r.headers.get("content-type") || "").includes("text/html")) return r.arrayBuffer();
    const t = await fetch("data/points.b64.txt");  // hosts that refuse binary files
    return Uint8Array.from(atob(await t.text()), (c) => c.charCodeAt(0)).buffer;
  }
  const json = (p) => fetch(p).then((r) => { if (!r.ok) throw new Error(p); return r.json(); });

  // ---------------------------------------------------------------- deck
  let deckgl, n, pos, cond, embers, layersBase, ready = false;
  const C = {};
  function colours() {
    Object.assign(C, { sand: rgb("#B89C88", 125), dim: rgb("#C2AA98", 80), good: rgb(css("--good"), 200), fair: rgb(css("--fair"), 200),
      poor: rgb(css("--poor"), 235), land: rgb("#EDD8C4"), ground: rgb(css("--ground")), line: rgb("#C7AA98", 150),
      water: rgb("#BCC3D9", 230), ember: rgb(css("--ember"), 235), emberSoft: rgb(css("--ember-soft"), 200), accent: rgb(css("--sc-accent")) });
  }

  async function initDeck() {
    colours();
    const [buf, states, water] = await Promise.all([loadPoints(), json("basemap/us_states.geojson"), json("intro/water-major.geojson")]);
    const dv = new DataView(buf); n = buf.byteLength / 12;
    pos = new Float32Array(n * 2); cond = new Uint8Array(n);
    const eIdx = [];
    for (let i = 0; i < n; i++) {
      pos[i * 2] = dv.getFloat32(i * 12, true); pos[i * 2 + 1] = dv.getFloat32(i * 12 + 4, true);
      cond[i] = dv.getUint8(i * 12 + 8);
      const q1 = dv.getUint8(i * 12 + 9);
      if (q1 >= 4) eIdx.push(i, q1);
    }
    // embers: bridges scored above 10% risk of becoming Poor within 4 years; the riskiest band ignites first
    const m = eIdx.length / 2; embers = { pos: new Float32Array(m * 2), ign: new Float32Array(m), band: new Uint8Array(m) };
    let seed = 7; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
    for (let j = 0; j < m; j++) {
      const i = eIdx[j * 2], b = eIdx[j * 2 + 1];
      embers.pos[j * 2] = pos[i * 2]; embers.pos[j * 2 + 1] = pos[i * 2 + 1]; embers.band[j] = b;
      embers.ign[j] = b === 5 ? 0.02 + rnd() * 0.45 : 0.4 + rnd() * 0.58;
    }
    const ground = { type: "Feature", geometry: { type: "Polygon", coordinates: [[[-179.9, -70], [60, -70], [60, 84], [-179.9, 84], [-179.9, -70]]] } };
    layersBase = [
      new deck.GeoJsonLayer({ id: "ground", data: ground, filled: true, stroked: false, getFillColor: C.ground }),
      new deck.GeoJsonLayer({ id: "land", data: states, filled: true, stroked: true, getFillColor: C.land, getLineColor: C.line,
        lineWidthUnits: "pixels", getLineWidth: 0.8 }),
      new deck.GeoJsonLayer({ id: "water", data: water, filled: true, stroked: true, getFillColor: C.water, getLineColor: C.water,
        lineWidthUnits: "pixels", lineWidthMinPixels: 1, getLineWidth: (f) => f.properties.kind === "river" ? 1.4 : 0 }),
    ];
    deckgl = new deck.Deck({
      parent: $("#ground"), controller: false, useDevicePixels: Math.min(devicePixelRatio || 1, 1.5),
      views: new deck.MapView({ repeat: false, farZMultiplier: 4 }),
      viewState: toView(cameraAt(0)), layers: [],
      parameters: { depthTest: false },
    });
    ready = true;
    window.__intro = { deck: deckgl, C };  // for the verification scripts
  }
  const toView = (c) => ({ longitude: c.lon, latitude: c.lat, zoom: c.zoom, pitch: c.pitch, bearing: c.bearing, maxPitch: 85,
    padding: { top: Math.round(c.pad * innerHeight), bottom: 0, left: 0, right: 0 } });

  // Two grain layers crossfaded by scroll: sand, and the same grains coloured by condition. Uniform opacity only, so the
  // regrade costs nothing per frame and plays the same forwards and backwards.
  let grainsSand, grainsCond;
  function grainLayers() {
    const common = { data: { length: n, attributes: { getPosition: { value: pos, size: 2 } } }, radiusUnits: "meters", getRadius: 240,
      radiusMinPixels: phone() ? 0.55 : 0.7, radiusMaxPixels: 5, stroked: false };
    grainsSand = { ...common, id: "grains-sand", getFillColor: C.sand };
    grainsCond = { ...common, id: "grains-cond", getFillColor: (_, { index }) => cond[index] === 3 ? C.poor : cond[index] === 2 ? C.fair : C.good };
  }
  function layers(state) {
    if (!grainsSand) grainLayers();
    const sandL = new deck.ScatterplotLayer({ ...grainsSand, opacity: state.sandOpacity, visible: state.sandOpacity > 0.01 });
    const condL = new deck.ScatterplotLayer({ ...grainsCond, opacity: state.condOpacity, visible: state.condOpacity > 0.01 });
    const f = state.year;
    const emberHalo = new deck.ScatterplotLayer({
      id: "ember-halo", data: { length: embers.ign.length, attributes: { getPosition: { value: embers.pos, size: 2 } } },
      radiusUnits: "pixels", getRadius: (_, { index }) => embers.band[index] === 5 ? 3.6 : 2.2, getFillColor: (_, { index }) => embers.band[index] === 5 ? [...C.ember.slice(0, 3), 30] : [...C.emberSoft.slice(0, 3), 18],
      getFilterValue: (_, { index }) => embers.ign[index], filterRange: [-1, f], filterSoftRange: [-1, Math.max(-1, f - 0.06)],
      extensions: [new deck.DataFilterExtension({ filterSize: 1 })], opacity: state.emberOpacity, visible: state.emberOpacity > 0.01,
    });
    const emberCore = new deck.ScatterplotLayer({
      id: "ember-core", data: { length: embers.ign.length, attributes: { getPosition: { value: embers.pos, size: 2 } } },
      radiusUnits: "pixels", getRadius: (_, { index }) => embers.band[index] === 5 ? 1.25 : 0.8, getFillColor: (_, { index }) => embers.band[index] === 5 ? C.ember : [...C.emberSoft.slice(0, 3), 150],
      getFilterValue: (_, { index }) => embers.ign[index], filterRange: [-1, f], filterSoftRange: [-1, Math.max(-1, f - 0.06)],
      extensions: [new deck.DataFilterExtension({ filterSize: 1 })], opacity: state.emberOpacity, visible: state.emberOpacity > 0.01,
    });
    const mark = new deck.ScatterplotLayer({
      id: "hpl", data: [HPL], getPosition: (d) => d, radiusUnits: "pixels", getRadius: 9, stroked: true, filled: true,
      getFillColor: [...C.accent.slice(0, 3), 60], getLineColor: C.accent, lineWidthUnits: "pixels", getLineWidth: 1.6,
      opacity: state.markOpacity, visible: state.markOpacity > 0.01,
    });
    return [...layersBase, sandL, condL, emberHalo, emberCore, mark];
  }

  // ---------------------------------------------------------------- dust (near plane)
  const dust = $("#dust"), dctx = dust.getContext("2d");
  let motes = [];
  function sizeDust() {
    const r = Math.min(devicePixelRatio || 1, 1.5);
    dust.width = innerWidth * r; dust.height = innerHeight * r; dctx.setTransform(r, 0, 0, r, 0, 0);
    const count = reduced ? 0 : phone() ? 45 : 110;
    let s = 11; const rnd = () => (s = (s * 16807) % 2147483647) / 2147483647;
    motes = Array.from({ length: count }, () => ({ x: rnd() * innerWidth, y: rnd() * innerHeight, d: 0.25 + rnd() * 0.75, v: 0.08 + rnd() * 0.22, ph: rnd() * 6.28 }));
  }
  function drawDust(dt, scrollV, px, py, alpha) {
    dctx.clearRect(0, 0, innerWidth, innerHeight);
    if (!motes.length || alpha < 0.01) return;
    for (const m of motes) {
      const dd = Math.min(dt, 64); m.x += (m.v * m.d) * dd * 0.06; m.y -= (0.02 * m.d) * dd * 0.06 + scrollV * m.d * 0.25;
      m.y += 0; if (m.x > innerWidth + 10) m.x = -10; if (m.y < -10) m.y = innerHeight + 10; if (m.y > innerHeight + 10) m.y = -10;
      m.ph += dt * 0.0012;
      const a = alpha * (0.16 + 0.24 * m.d) * (0.75 + 0.25 * Math.sin(m.ph));
      dctx.fillStyle = `rgba(255, 244, 232, ${a.toFixed(3)})`;
      dctx.beginPath(); dctx.arc(m.x + px * m.d * 14, m.y + py * m.d * 10, 0.6 + m.d * 1.6, 0, 6.283); dctx.fill();
    }
  }

  // ---------------------------------------------------------------- frame loop
  const world = $("#world"), truss = $("#truss"), haze = $("#haze"), sun = $(".sun"), yearEl = $("#year"), routeYear = $("#routeYear"), land = $("#landCard");
  const routeLinks = [...document.querySelectorAll(".route a")];
  const plates = [...document.querySelectorAll("[data-plate-for]")].map((el) => ({ el, copy: document.getElementById(el.dataset.plateFor) }));
  function sizePlates() {
    for (const pl of plates) {
      const prev = pl.copy.style.transform; pl.copy.style.transform = "none";
      const r = pl.copy.getBoundingClientRect(); pl.copy.style.transform = prev;
      const padX = 90, padY = 70;
      Object.assign(pl.el.style, { left: `${r.left - padX}px`, top: `${r.top - padY}px`, width: `${r.width + 2 * padX}px`, height: `${r.height + 2 * padY}px` });
    }
  }
  let cam = cameraAt(0), lastY = scrollY, lastTime = performance.now(), ptr = { x: 0, y: 0, tx: 0, ty: 0 }, lastState = "", curWp = -1;
  if (fine && !reduced) addEventListener("pointermove", (e) => { ptr.tx = e.clientX / innerWidth - 0.5; ptr.ty = e.clientY / innerHeight - 0.5; }, { passive: true });

  let loopErrors = 0;
  function frame(now) {
    try { step(now); } catch (e) { if (loopErrors++ < 3) console.warn("[intro] frame skipped:", e.message); }
    requestAnimationFrame(frame);
  }
  function step(now) {
    const dt = Math.min(400, now - lastTime); lastTime = now;  // a slow renderer still converges in real time
    const vh = innerHeight, t = clamp(scrollY / vh, 0, T_END);
    const target = cameraAt(t), k = reduced ? 1 : 1 - Math.pow(1 - 0.085, dt / 16.7);
    for (const key of ["lon", "lat", "zoom", "pitch", "bearing", "pad"]) cam[key] = lerp(cam[key], target[key], k);
    ptr.x = lerp(ptr.x, ptr.tx, 0.06); ptr.y = lerp(ptr.y, ptr.ty, 0.06);
    const scrollV = (scrollY - lastY) / Math.max(1, dt) * 16.7; lastY = scrollY;

    const yf = yearFrac(t), year = 2025 + yf * 4;
    const condW = Math.max(smooth((t - starts[2] + 0.5) / 0.55) * (1 - smooth((t - starts[3] + 0.15) / 0.4)), smooth((t - starts[6] + 0.25) / 0.5));
    const foreW = smooth((t - starts[4] + 0.1) / 0.4) * (1 - smooth((t - starts[6] + 0.3) / 0.5));
    const st = { mode: colourMode(t), year: yf, condOpacity: condW, sandOpacity: (1 - condW) * (1 - 0.5 * foreW),
      emberOpacity: smooth((t - starts[4] - 0.05) / 0.4) * (1 - 0.45 * smooth((t - starts[5] + 0.1) / 0.4)) * (1 - smooth((t - starts[6] + 0.3) / 0.5)),
      markOpacity: smooth((t - starts[6] - 0.05) / 0.35) };
    if (ready) {
      deckgl.setProps({ viewState: toView(cam), layers: layers(st) });
      // deck.gl 9 creates its GPU device asynchronously; asking for viewports before that asserts
      const vp = deckgl.isInitialized ? deckgl.getViewports()[0] : null;
      if (vp) placeWorld(vp, t, vh);
    }
    yearEl.textContent = routeYear.textContent = String(Math.floor(year + 1e-6) > 2029 ? 2029 : Math.floor(year + 1e-6));
    sun.style.setProperty("--sun-x", `${(ptr.x * -10).toFixed(1)}px`);
    sun.style.setProperty("--sun-y", `${(smooth(t / 1.4) * 12 * vh / 100 + ptr.y * -6).toFixed(1)}px`);
    drawDust(dt, scrollV, ptr.x, ptr.y, 1 - 0.65 * smooth((t - 0.8) / 1.2));

    const wi = wpIndex(t);
    if (wi !== curWp) { curWp = wi; routeLinks.forEach((a) => a.setAttribute("aria-current", String(Number(a.dataset.wp) === wi))); }
    const sig = `${wi}|${cam.zoom.toFixed(2)}|${cam.pitch.toFixed(1)}|${cam.lon.toFixed(2)}|${yf.toFixed(2)}|${condW.toFixed(2)}|${truss.style.opacity}`;
    if (sig !== lastState) { world.setAttribute("data-sc-verify-state", sig); lastState = sig; }
    // plates follow their copy block's box and the engine's opacity for it
    for (const pl of plates) {
      const o = pl.copy.style.opacity || "0";
      if (pl.el.style.opacity !== o) pl.el.style.opacity = o;
    }
    const hush = t > starts[3] + 0.05 && t < starts[4] - 0.05;
    world.toggleAttribute("data-sc-verify-hold", false);
    // the hush is authored stillness; under reduced motion every waypoint is a deliberately held view
    if (hush || reduced) world.setAttribute("data-sc-verify-hold", "true");
  }

  // The drawing stands where the bridge is: its foot is pinned to the bridge's projected position on the ground.
  function placeWorld(vp, t, vh) {
    const [x, y] = vp.project(HPL);
    const w = (phone() ? 1.5 : 0.56) * innerWidth * (1 - 0.5 * smooth(t / 1.1));
    const o = (1 - smooth((t - 0.25) / 0.75)) * (ready ? 1 : 0);
    truss.style.width = `${w.toFixed(0)}px`;
    truss.style.opacity = o.toFixed(3);
    truss.style.transform = `translate3d(${(x - w / 2 + ptr.x * -8).toFixed(1)}px, ${(y - w * 485 / 3600 * 0.93).toFixed(1)}px, 0)`;
    // horizon haze: sits where far ground meets the sky, fades as the camera tips down
    const far = vp.project([cam.lon, cam.lat + 28]);
    const hy = clamp(far[1], -vh, vh * 2);
    haze.style.transform = `translate3d(0, ${(hy - vh * 0.2).toFixed(1)}px, 0)`;
    haze.style.opacity = (smooth((cam.pitch - 52) / 20)).toFixed(3);
    // the landing card sits beside the bridge, never on it
    if (land && !phone()) {
      const lx = clamp(x + 40, 16, innerWidth - land.offsetWidth - 230), ly = clamp(y - land.offsetHeight * 0.5, 80, vh - land.offsetHeight - 110);
      land.style.left = `${lx.toFixed(0)}px`; land.style.top = `${ly.toFixed(0)}px`;
    }
  }

  // ---------------------------------------------------------------- route rail: jump between waypoints
  routeLinks.forEach((a) => a.addEventListener("click", (e) => {
    e.preventDefault();
    scrollTo({ top: settleY(Number(a.dataset.wp)), behavior: reduced ? "auto" : "smooth" });
  }));

  // Keyboard: copy is fixed, so scrolling a control into view cannot open its cue. Park the track at the control's waypoint.
  const settleY = (i) => Math.min((starts[i] + (i === wps.length - 1 ? 0.6 : 0.35)) * innerHeight, document.documentElement.scrollHeight - innerHeight);
  document.addEventListener("focusin", (e) => {
    const wp = e.target.closest && e.target.closest(".wp");
    if (!wp) return;
    const i = wps.indexOf(wp), y = settleY(i);
    if (Math.abs(scrollY - y) > innerHeight * 0.3) scrollTo({ top: y, behavior: "instant" });
  });

  // ---------------------------------------------------------------- boot
  function relayout() { keys = KEYS(); sizeDust(); sizePlates(); }
  addEventListener("resize", relayout);
  sizeDust(); sizePlates();
  addEventListener("load", sizePlates); if (document.fonts) document.fonts.ready.then(sizePlates);
  if (window.ScrollCraft) ScrollCraft.mount(document.body);
  initDeck().catch((e) => { console.error(e); document.documentElement.classList.add("no-world"); });
  requestAnimationFrame(frame);
})();
