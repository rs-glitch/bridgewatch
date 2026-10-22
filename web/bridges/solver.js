// Browser port of src/bridgewatch/sim/truss.py and suspension.py. Same units, same assumptions;
// tests/test_sim_js.py checks it against the Python results. Plain script: defines `BWSolver`.
"use strict";
(function (root) {
  // ------------------------------------------------------------------ dense solve (small trusses)
  function gauss(A, b) {
    const n = b.length;
    for (let c = 0; c < n; c++) {
      let p = c;
      for (let r = c + 1; r < n; r++) if (Math.abs(A[r][c]) > Math.abs(A[p][c])) p = r;
      [A[c], A[p]] = [A[p], A[c]]; [b[c], b[p]] = [b[p], b[c]];
      for (let r = c + 1; r < n; r++) {
        const f = A[r][c] / A[c][c];
        if (!f) continue;
        for (let k = c; k < n; k++) A[r][k] -= f * A[c][k];
        b[r] -= f * b[c];
      }
    }
    const x = new Array(n).fill(0);
    for (let r = n - 1; r >= 0; r--) {
      let s = b[r];
      for (let k = r + 1; k < n; k++) s -= A[r][k] * x[k];
      x[r] = s / A[r][r];
    }
    return x;
  }

  // ------------------------------------------------------------------ truss
  // t = {nodes: {name: [x, y] ft}, members: [{id, i, j, area, E, tension_only, group}], supports: {name: [fixx, fixy]}, yield_ksi}
  function solveTruss(t, loads, maxIter = 50) {
    const names = Object.keys(t.nodes), idx = Object.fromEntries(names.map((n, k) => [n, k]));
    const ndof = 2 * names.length, F = new Array(ndof).fill(0);
    for (const [n, [fx, fy]] of Object.entries(loads)) { F[2 * idx[n]] += fx; F[2 * idx[n] + 1] += fy; }
    const fixed = new Set();
    for (const [n, fx] of Object.entries(t.supports)) fx.forEach((on, d) => on && fixed.add(2 * idx[n] + d));
    const free = [...Array(ndof).keys()].filter((d) => !fixed.has(d));
    const geo = t.members.map((m) => {
      const a = idx[m.i], b = idx[m.j], [x1, y1] = t.nodes[m.i], [x2, y2] = t.nodes[m.j];
      const dx = (x2 - x1) * 12, dy = (y2 - y1) * 12, L = Math.hypot(dx, dy);
      return { a, b, L, c: dx / L, s: dy / L, k: m.E * m.area / L };
    });
    let active = t.members.map(() => true), u, elong, K, it = 0;
    for (it = 0; it < maxIter; it++) {
      K = Array.from({ length: ndof }, () => new Array(ndof).fill(0));
      geo.forEach((g, k) => {
        if (!active[k]) return;
        const v = [-g.c, -g.s, g.c, g.s], dofs = [2 * g.a, 2 * g.a + 1, 2 * g.b, 2 * g.b + 1];
        for (let p = 0; p < 4; p++) for (let q = 0; q < 4; q++) K[dofs[p]][dofs[q]] += g.k * v[p] * v[q];
      });
      let dmax = 1;
      for (let d = 0; d < ndof; d++) dmax = Math.max(dmax, K[d][d]);
      for (const d of free) K[d][d] += 1e-12 * dmax;
      const Kf = free.map((r) => free.map((c) => K[r][c]));
      const uf = gauss(Kf, free.map((d) => F[d]));
      u = new Array(ndof).fill(0);
      free.forEach((d, k) => { u[d] = uf[k]; });
      elong = geo.map((g) => (u[2 * g.b] - u[2 * g.a]) * g.c + (u[2 * g.b + 1] - u[2 * g.a + 1]) * g.s);
      const want = t.members.map((m, k) => !m.tension_only || elong[k] >= 0);
      if (want.every((w, k) => w === active[k])) break;
      active = want;
    }
    const members = t.members.map((m, k) => {
      const N = active[k] ? geo[k].k * elong[k] : 0, stress = N / m.area;
      return { id: m.id, group: m.group, force_kip: N, stress_ksi: stress, ratio: Math.abs(stress) / t.yield_ksi, active: active[k] };
    });
    const disp = Object.fromEntries(names.map((n, k) => [n, [u[2 * k], u[2 * k + 1]]]));
    const reactions = {};
    for (const n of Object.keys(t.supports)) {
      const r = [0, 1].map((d) => { const row = 2 * idx[n] + d; let s = -F[row]; for (let c = 0; c < ndof; c++) s += K[row][c] * u[c]; return fixed.has(row) ? s : 0; });
      reactions[n] = r;
    }
    return { members, disp_in: disp, reactions_kip: reactions, iterations: it + 1 };
  }

  function selfWeight(t, density = 480) {
    const out = Object.fromEntries(Object.keys(t.nodes).map((n) => [n, [0, 0]]));
    for (const m of t.members) {
      const [x1, y1] = t.nodes[m.i], [x2, y2] = t.nodes[m.j];
      const w = density * m.area / 144 * Math.hypot(x2 - x1, y2 - y1) / 1000;
      out[m.i][1] -= w / 2; out[m.j][1] -= w / 2;
    }
    return out;
  }
  function addLoads(...cases) {
    const out = {};
    for (const c of cases) for (const [n, [fx, fy]] of Object.entries(c)) { const o = out[n] ?? (out[n] = [0, 0]); o[0] += fx; o[1] += fy; }
    return out;
  }
  // deck loads to the floor-beam nodes through simple-span stringers
  function panelLoads(deck, xs, { uniform_klf = 0, axles = [] } = {}) {
    const out = Object.fromEntries(deck.map((n) => [n, [0, 0]]));
    for (let k = 0; k < xs.length - 1; k++) { const h = uniform_klf * (xs[k + 1] - xs[k]) / 2; out[deck[k]][1] -= h; out[deck[k + 1]][1] -= h; }
    for (const [x, P] of axles) {
      if (x < xs[0] || x > xs[xs.length - 1]) continue;
      let k = 0;
      while (k < xs.length - 2 && x >= xs[k + 1]) k++;
      const f = (x - xs[k]) / (xs[k + 1] - xs[k]);
      out[deck[k]][1] -= P * (1 - f); out[deck[k + 1]][1] -= P * f;
    }
    return out;
  }

  // ------------------------------------------------------------------ suspension (Melan deflection theory)
  // EI v'''' - (H + h) v'' = p - (8f/L^2) h;   h Le/(Ec Ac) + alpha dT Lt = (8f/L^2) ∫v dx
  // The interior system is pentadiagonal and positive definite, so a banded LDL-free elimination is enough.
  function bandSolve(diag, b) {
    // diag[k] = [a(i,i-2), a(i,i-1), a(i,i), a(i,i+1), a(i,i+2)]
    const m = b.length, A = diag.map((r) => r.slice()), x = b.slice();
    for (let i = 0; i < m; i++) {
      const p = A[i][2];
      for (let r = 1; r <= 2 && i + r < m; r++) {
        const f = A[i + r][2 - r] / p;
        if (!f) continue;
        for (let c = 0; c <= 2; c++) if (i + c < m) A[i + r][2 - r + c] -= f * A[i][2 + c];
        x[i + r] -= f * x[i];
      }
    }
    for (let i = m - 1; i >= 0; i--) {
      let s = x[i];
      for (let c = 1; c <= 2; c++) if (i + c < m) s -= A[i][2 + c] * x[i + c];
      x[i] = s / A[i][2];
    }
    return x;
  }
  // suspended side spans: each side cable straightens as the pull grows, letting its tower top lean in
  function sideSlack(s, h, H) {
    if (!s.side_l) return 0;
    const f1 = s.side_w * s.side_l ** 2 / (8 * H);
    return 2 * (8 / 3) * f1 ** 2 / s.side_l * (1 - (H / (H + h)) ** 2);
  }
  function solveSpan(s, p, dT = 0, tol = 1e-7, maxIter = 300) {
    const n = s.n, m = n - 1, dx = s.L / n, k8 = 8 * s.f / s.L ** 2, H = s.w_dead * s.L ** 2 / (8 * s.f), EA = s.Ec_ksi * s.Ac_in2;
    const d2 = 1 / dx ** 2, d4 = 1 / dx ** 4;
    let h = 0, v1, v2, it;
    const pin = p.slice(1, -1), q = new Array(m).fill(-k8);
    for (it = 0; it < maxIter; it++) {
      const T = H + h;
      const rows = [];
      for (let i = 0; i < m; i++) {
        const end = i === 0 || i === m - 1 ? 5 : 6;           // (D2 @ D2) loses one term at each end
        rows.push([s.EI_kft2 * d4, s.EI_kft2 * -4 * d4 - T * d2, s.EI_kft2 * end * d4 + 2 * T * d2, s.EI_kft2 * -4 * d4 - T * d2, s.EI_kft2 * d4]);
      }
      v1 = bandSolve(rows, pin); v2 = bandSolve(rows, q);
      const i1 = v1.reduce((a, b) => a + b, 0) * dx, i2 = v2.reduce((a, b) => a + b, 0) * dx;
      const hn = h + 0.7 * ((k8 * i1 - s.alpha * dT * s.Lt - sideSlack(s, h, H)) / (s.Le / EA - k8 * i2) - h);
      const done = Math.abs(hn - h) <= tol * Math.max(1, Math.abs(hn));
      h = hn;
      if (done) break;
    }
    const v = new Array(n + 1).fill(0);
    for (let i = 0; i < m; i++) v[i + 1] = v1[i] + h * v2[i];
    const M = v.map((_, i) => (i === 0 || i === n) ? 0 : -s.EI_kft2 * (v[i - 1] - 2 * v[i] + v[i + 1]) * d2);
    const slope = 4 * s.f / s.L;
    return { x_ft: v.map((_, i) => i * dx), defl_ft: v, moment_kft: M, h_kip: h, H_kip: H,
      cable_max_kip: (H + h) * Math.sqrt(1 + slope ** 2), iterations: it + 1 };
  }
  function patch(s, a, b, w) {
    const out = new Array(s.n + 1);
    for (let i = 0; i <= s.n; i++) { const x = i * s.L / s.n; out[i] = x >= a && x <= b ? w : 0; }
    return out;
  }

  const api = { solveTruss, selfWeight, addLoads, panelLoads, solveSpan, patch };
  if (typeof module !== "undefined") module.exports = api; else root.BWSolver = api;
})(typeof window !== "undefined" ? window : globalThis);
