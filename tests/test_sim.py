import math

import numpy as np

from bridgewatch.sim import models, suspension, truss


def _triangle():
    nodes = {"A": (0.0, 0.0), "B": (8.0, 0.0), "C": (4.0, 3.0)}
    members = [{"id": "AB", "i": "A", "j": "B", "area": 2.0, "E": 29000.0},
               {"id": "AC", "i": "A", "j": "C", "area": 2.0, "E": 29000.0},
               {"id": "BC", "i": "B", "j": "C", "area": 2.0, "E": 29000.0}]
    return truss.Truss(nodes=nodes, members=members, supports={"A": (True, True), "B": (False, True)})


def test_triangle_matches_statics():
    r = truss.solve(_triangle(), {"C": (0.0, -10.0)})
    f = {m["id"]: m["force_kip"] for m in r["members"]}
    # each rafter carries 5 kip vertical at slope 3/5: N = -5 / 0.6; the tie takes N * 0.8
    assert math.isclose(f["AC"], -5 / 0.6, rel_tol=1e-6)
    assert math.isclose(f["BC"], -5 / 0.6, rel_tol=1e-6)
    assert math.isclose(f["AB"], 5 / 0.6 * 0.8, rel_tol=1e-6)
    assert math.isclose(r["reactions_kip"]["A"][1], 5.0, rel_tol=1e-6)


def test_kelley_dead_load_balances_and_chords_behave():
    t, deck, xs = models.kelley_crossing()
    dead = models.kelley_dead(t, deck, xs)
    r = truss.solve(t, dead)
    total = -sum(fy for _, fy in dead.values())
    assert math.isclose(sum(fy for _, fy in r["reactions_kip"].values()), total, rel_tol=1e-6)
    for m in r["members"]:
        if m["group"] == "upper chord":
            assert m["force_kip"] < 0
        if m["group"] == "lower chord":
            assert m["force_kip"] > 0


def test_counters_never_carry_compression():
    t, deck, xs = models.kelley_crossing()
    dead = models.kelley_dead(t, deck, xs)
    e = truss.envelope(t, dead, deck, xs, models.TRUCKS["H20 (20-ton truck)"], step_ft=5.0)
    for m in e["members"].values():
        if m["group"] == "diagonal":
            assert m["force_kip"] >= -1e-9


def test_suspension_full_load_goes_to_cable_when_stiff():
    # an almost inextensible cable and a weak truss: full-span load should go to the cable, h = p L^2 / 8f
    s = suspension.Span(L=1000.0, f=100.0, w_dead=5.0, Ec_ksi=29000.0, Ac_in2=1e7, EI_kft2=1e3,
                        Le=1100.0, Lt=1050.0, depth_ft=10.0, n=200)
    r = suspension.solve(s, suspension.patch(s, 0, s.L, 1.0))
    assert math.isclose(r["h_kip"], 1.0 * s.L**2 / (8 * s.f), rel_tol=1e-3)
    assert np.abs(r["defl_ft"]).max() < 0.05


def test_suspension_spans_match_published_deflections():
    # 1941 Table 4 (normal temperature) within 6%; the 1937 Golden Gate figures, with temperature, within 16%
    for build in models.SPANS:
        b = build()
        for c in b.checks:
            val, _ = suspension.check(b.span, b.live_klf_per_cable, c["kind"], c.get("dT", 0.0))
            tol = c.get("tol", 0.06 if "1941" in c["source"] else 0.16)
            assert abs(val - c["report_ft"]) / c["report_ft"] < tol, (b.slug, c["kind"], val)


def test_every_truss_balances_and_rods_never_push():
    for build in models.all_trusses():
        b = build()
        dead = b.dead()
        r = truss.solve(b.t, dead)
        total = -sum(fy for _, fy in dead.values())
        assert math.isclose(sum(fy for _, fy in r["reactions_kip"].values()), total, rel_tol=1e-6), b.slug
        assert max(abs(u) for d in r["disp_in"].values() for u in d) < 3.0, b.slug       # no hidden mechanism
        live = truss.add(dead, truss.panel_loads(b.deck, b.xs, {"axles": [(b.xs[-1] / 3, 16.0), (b.xs[-1] / 3 + 14, 4.0)]}))
        for res, mem in zip(truss.solve(b.t, live)["members"], b.t.members, strict=True):
            if mem.get("tension_only"):
                assert res["force_kip"] >= -1e-9, (b.slug, mem["id"])
