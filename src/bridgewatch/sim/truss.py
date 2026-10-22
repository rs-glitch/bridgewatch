"""Plane pin-jointed truss solver (direct stiffness), with tension-only members.

Units: feet for geometry, square inches for areas, ksi for E and stress, kips for force.
"""

from dataclasses import dataclass, field

import numpy as np


@dataclass
class Truss:
    nodes: dict[str, tuple[float, float]]                 # name -> (x, y) ft
    members: list[dict]                                    # {id, i, j, area, E, tension_only, group}
    supports: dict[str, tuple[bool, bool]]                 # name -> (fix x, fix y)
    yield_ksi: float = 25.0
    meta: dict = field(default_factory=dict)

    @property
    def names(self) -> list[str]:
        return list(self.nodes)


def solve(t: Truss, loads: dict[str, tuple[float, float]], max_iter: int = 50) -> dict:
    """Static solve. `loads` maps node -> (Fx, Fy) in kips (Fy negative = down).

    Tension-only members (rods, counters) are switched off while they would be in
    compression, and the system is re-solved until the active set stops changing.
    """
    idx = {n: k for k, n in enumerate(t.names)}
    xy = np.array([t.nodes[n] for n in t.names], dtype=float) * 12.0          # inches
    ndof = 2 * len(idx)
    F = np.zeros(ndof)
    for n, (fx, fy) in loads.items():
        F[2 * idx[n]] += fx
        F[2 * idx[n] + 1] += fy
    fixed = [2 * idx[n] + d for n, fx in t.supports.items() for d, on in enumerate(fx) if on]
    free = np.setdiff1d(np.arange(ndof), fixed)

    geo = []
    for m in t.members:
        a, b = idx[m["i"]], idx[m["j"]]
        d = xy[b] - xy[a]
        L = float(np.hypot(*d))
        geo.append((a, b, L, d / L))

    active = np.ones(len(t.members), dtype=bool)
    it = 0
    for it in range(max_iter):  # noqa: B007 (reported below)
        K = np.zeros((ndof, ndof))
        for k, (m, (a, b, L, (c, s))) in enumerate(zip(t.members, geo, strict=True)):
            if not active[k]:
                continue
            ke = m["E"] * m["area"] / L * np.outer([-c, -s, c, s], [-c, -s, c, s])
            dofs = [2 * a, 2 * a + 1, 2 * b, 2 * b + 1]
            K[np.ix_(dofs, dofs)] += ke
        # a tiny spring keeps nodes left loose by an inactive counter from making K singular
        K[free, free] += 1e-12 * max(1.0, K.diagonal().max())
        u = np.zeros(ndof)
        u[free] = np.linalg.solve(K[np.ix_(free, free)], F[free])
        elong = np.array([(u[2 * b] - u[2 * a]) * c + (u[2 * b + 1] - u[2 * a + 1]) * s
                          for a, b, L, (c, s) in geo])
        N = np.array([m["E"] * m["area"] / g[2] for m, g in zip(t.members, geo, strict=True)]) * elong * active
        want = np.array([not m.get("tension_only") or e >= 0 for m, e in zip(t.members, elong, strict=True)])
        if (want == active).all():
            break
        active = want
    N[~active] = 0.0
    R = np.zeros(ndof)
    R[fixed] = (K @ u - F)[fixed]
    out = []
    for k, m in enumerate(t.members):
        stress = N[k] / m["area"]
        out.append({"id": m["id"], "group": m.get("group", ""), "force_kip": float(N[k]),
                    "stress_ksi": float(stress), "ratio": float(abs(stress) / t.yield_ksi),
                    "active": bool(active[k])})
    return {
        "members": out,
        "disp_in": {n: (float(u[2 * i]), float(u[2 * i + 1])) for n, i in idx.items()},
        "reactions_kip": {n: (float(R[2 * idx[n]]), float(R[2 * idx[n] + 1])) for n in t.supports},
        "iterations": it + 1,
    }


def self_weight(t: Truss, density_lb_ft3: float = 480.0) -> dict[str, tuple[float, float]]:
    """Member self-weight lumped half to each end node, kips."""
    loads: dict[str, list[float]] = {n: [0.0, 0.0] for n in t.nodes}
    for m in t.members:
        (x1, y1), (x2, y2) = t.nodes[m["i"]], t.nodes[m["j"]]
        w = density_lb_ft3 * m["area"] / 144.0 * float(np.hypot(x2 - x1, y2 - y1)) / 1000.0
        loads[m["i"]][1] -= w / 2
        loads[m["j"]][1] -= w / 2
    return {n: (fx, fy) for n, (fx, fy) in loads.items()}


def add(*cases: dict) -> dict[str, tuple[float, float]]:
    out: dict[str, list[float]] = {}
    for c in cases:
        for n, (fx, fy) in c.items():
            o = out.setdefault(n, [0.0, 0.0])
            o[0] += fx
            o[1] += fy
    return {n: (a, b) for n, (a, b) in out.items()}


def panel_loads(deck_nodes: list[str], xs: list[float], line_load: dict) -> dict[str, tuple[float, float]]:
    """Distribute deck loads to the floor-beam nodes by simple-span stringers.

    `line_load` holds {"uniform_klf": w} for a load over the whole deck and/or
    {"axles": [(x_ft, kips), ...]} for point loads.
    """
    out = {n: [0.0, 0.0] for n in deck_nodes}
    w = line_load.get("uniform_klf", 0.0)
    for k in range(len(xs) - 1):
        half = w * (xs[k + 1] - xs[k]) / 2
        out[deck_nodes[k]][1] -= half
        out[deck_nodes[k + 1]][1] -= half
    for x, P in line_load.get("axles", []):
        if x < xs[0] or x > xs[-1]:
            continue
        k = min(int(np.searchsorted(xs, x, side="right")) - 1, len(xs) - 2)
        f = (x - xs[k]) / (xs[k + 1] - xs[k])
        out[deck_nodes[k]][1] -= P * (1 - f)
        out[deck_nodes[k + 1]][1] -= P * f
    return {n: (a, b) for n, (a, b) in out.items()}


def envelope(t: Truss, base: dict, deck_nodes: list[str], xs: list[float], axles: list[tuple[float, float]],
             step_ft: float = 1.0) -> dict:
    """Roll an axle group across the deck; return the worst force per member and the governing position."""
    length = max(a for a, _ in axles) if axles else 0.0
    worst: dict[str, dict] = {}
    frames = []
    for x0 in np.arange(xs[0] - length, xs[-1] + step_ft, step_ft):
        live = panel_loads(deck_nodes, xs, {"axles": [(x0 + dx, P) for dx, P in axles]})
        r = solve(t, add(base, live))
        mid = min(t.nodes, key=lambda n: abs(t.nodes[n][0] - (xs[0] + xs[-1]) / 2) + (0 if n in deck_nodes else 1e6))
        frames.append({"x_ft": float(x0), "mid_defl_in": r["disp_in"][mid][1],
                       "max_ratio": max(m["ratio"] for m in r["members"])})
        for m in r["members"]:
            w = worst.get(m["id"])
            if w is None or m["ratio"] > w["ratio"]:
                worst[m["id"]] = dict(m, at_x_ft=float(x0))
    return {"members": worst, "frames": frames}
