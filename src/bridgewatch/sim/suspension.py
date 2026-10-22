"""Suspension span by deflection theory (Melan), one cable plus its stiffening truss.

    EI v'''' - (H + h) v'' = p(x) - (8 f / L^2) h
    h Le / (Ec Ac) + alpha dT Lt = (8 f / L^2) * integral(v dx)

v is downward deflection, H the dead-load cable pull, h the live-load increment.
With suspended side spans (side_l, side_w), each side cable straightens as the pull grows, letting its tower top lean in
by (8/3)(f1^2/l1)(1 - (H/(H+h))^2); that slack is added to the right-hand side of the compatibility equation.
The truss is simply supported at the towers (Golden Gate's main-span trusses hang
from rocker links there). Units: kips and feet; areas in in^2 and E in ksi on input.
"""

from dataclasses import dataclass

import numpy as np


@dataclass
class Span:
    L: float              # main span, ft
    f: float              # cable sag, ft
    w_dead: float         # dead load carried by this cable, kip/ft
    Ec_ksi: float
    Ac_in2: float
    EI_kft2: float        # stiffening truss
    Le: float             # integral of sec^3 over all cable spans, ft
    Lt: float             # integral of sec^2 over all cable spans, ft
    depth_ft: float       # stiffening truss depth
    alpha: float = 6.5e-6  # per deg F
    n: int = 420
    side_l: float = 0.0    # suspended side span length, ft (0: straight backstays)
    side_w: float = 0.0    # its dead load per cable, kip/ft

    @property
    def H(self) -> float:
        return self.w_dead * self.L**2 / (8 * self.f)

    @property
    def EA(self) -> float:
        return self.Ec_ksi * self.Ac_in2


def _operators(n: int, dx: float):
    """Interior-node second and fourth differences with v = v'' = 0 at both ends."""
    m = n - 1
    D2 = (np.diag(-2.0 * np.ones(m)) + np.diag(np.ones(m - 1), 1) + np.diag(np.ones(m - 1), -1)) / dx**2
    return D2, D2 @ D2


def side_slack(s: Span, h: float) -> float:
    """Inward lean of both tower tops, ft, as the side-span cables straighten under the extra pull h."""
    if not s.side_l:
        return 0.0
    f1 = s.side_w * s.side_l**2 / (8 * s.H)
    return 2 * (8 / 3) * f1**2 / s.side_l * (1 - (s.H / (s.H + h)) ** 2)


def solve(s: Span, p: np.ndarray, dT: float = 0.0, tol: float = 1e-7, max_iter: int = 300) -> dict:
    """`p` is the live load on this cable's truss, kip/ft, at the n+1 grid points."""
    dx = s.L / s.n
    x = np.linspace(0.0, s.L, s.n + 1)
    D2, D4 = _operators(s.n, dx)
    k = 8 * s.f / s.L**2
    ones = np.ones(s.n - 1)
    h = 0.0
    it = 0
    for it in range(max_iter):  # noqa: B007 (reported below)
        A = s.EI_kft2 * D4 - (s.H + h) * D2
        v1 = np.linalg.solve(A, p[1:-1])
        v2 = np.linalg.solve(A, -k * ones)
        i1, i2 = v1.sum() * dx, v2.sum() * dx
        h_new = (k * i1 - s.alpha * dT * s.Lt - side_slack(s, h)) / (s.Le / s.EA - k * i2)
        h_new = h + 0.7 * (h_new - h)                 # damped: the side-span term makes this a fixed point in h
        if abs(h_new - h) <= tol * max(1.0, abs(h_new)):
            h = h_new
            break
        h = h_new
    v = np.zeros(s.n + 1)
    v[1:-1] = v1 + h * v2
    curv = np.zeros(s.n + 1)
    curv[1:-1] = D2 @ v[1:-1]
    M = -s.EI_kft2 * curv
    slope_tower = 4 * s.f / s.L
    return {
        "x_ft": x,
        "defl_ft": v,
        "moment_kft": M,
        "chord_kip": M / s.depth_ft,
        "h_kip": float(h),
        "H_kip": float(s.H),
        "cable_max_kip": float((s.H + h) * np.sqrt(1 + slope_tower**2)),
        "hanger_klf": (s.H + h) * (k - curv),
        "iterations": it + 1,
    }


def patch(s: Span, a: float, b: float, w: float) -> np.ndarray:
    x = np.linspace(0.0, s.L, s.n + 1)
    return np.where((x >= a) & (x <= b), w, 0.0)


def extremes(s: Span, w_live: float, dT: float = 0.0, steps: int = 40) -> dict:
    """Search partial-length uniform loads (one end, and centred) for the worst deflections and moments."""
    best = {"down_ft": (0.0, None), "up_ft": (0.0, None), "moment_kft": (0.0, None)}
    L = s.L
    cases = [(0.0, L * k / steps) for k in range(1, steps + 1)]
    cases += [(L / 2 - L * k / (2 * steps), L / 2 + L * k / (2 * steps)) for k in range(1, steps + 1)]
    for a, b in cases:
        r = solve(s, patch(s, a, b, w_live), dT)
        down, up, mom = r["defl_ft"].max(), -r["defl_ft"].min(), np.abs(r["moment_kft"]).max()
        if down > best["down_ft"][0]:
            best["down_ft"] = (float(down), (a, b))
        if up > best["up_ft"][0]:
            best["up_ft"] = (float(up), (a, b))
        if mom > best["moment_kft"][0]:
            best["moment_kft"] = (float(mom), (a, b))
    return best


def check(s: Span, w: float, kind: str, dT: float = 0.0) -> tuple[float, list]:
    """Deflection (ft, positive in the named direction) for a published check, and the loaded stretches that give it.

    half_q_down / half_3q_up: live load from one tower to mid-span, deflection at the loaded / unloaded quarter point.
    full_c_down: whole main span loaded, centre. temp_c_down / temp_c_up: the worst centred / both-ends load with dT.
    """
    L, n = s.L, s.n
    if kind in ("half_q_down", "half_3q_up"):
        v = solve(s, patch(s, 0, L / 2, w), dT)["defl_ft"]
        return (float(v[n // 4]) if kind == "half_q_down" else float(-v[3 * n // 4])), [[0, L / 2]]
    if kind == "full_c_down":
        return float(solve(s, patch(s, 0, L, w), dT)["defl_ft"][n // 2]), [[0, L]]
    best = (-np.inf, None)
    for j in range(41):
        a = (j + 1) / 42 * L / 2
        if kind == "temp_c_down":
            loads = [[L / 2 - a, L / 2 + a]]
            val = solve(s, patch(s, *loads[0], w), dT)["defl_ft"][n // 2]
        else:
            loads = [[0, a], [L - a, L]]
            val = -solve(s, patch(s, 0, a, w) + patch(s, L - a, L, w), dT)["defl_ft"][n // 2]
        if val > best[0]:
            best = (float(val), loads)
    return best
