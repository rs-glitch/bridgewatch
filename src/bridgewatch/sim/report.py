"""Run the Tier 2 models and write reports/sim.md plus data/tier2/models/*.json."""

import json

from ..paths import ROOT
from . import models, suspension, truss

OUT = ROOT / "data" / "tier2" / "models"
WEB = ROOT / "web" / "data" / "tier2"


def truss_bridge(b: models.TrussBridge) -> tuple[dict, list[str]]:
    t, deck, xs = b.t, b.deck, b.xs
    dead = b.dead()
    r_dead = truss.solve(t, dead)
    trucks = {name: truss.envelope(t, dead, deck, xs, ax) for name, ax in models.TRUCKS.items()} if b.trucks else {}
    crowd = truss.solve(t, truss.add(dead, truss.panel_loads(deck, xs, {"uniform_klf": b.crowd_klf})))
    mid = min(deck, key=lambda n: abs(t.nodes[n][0] - (xs[0] + xs[-1]) / 2))
    out = {"slug": b.slug, "kind": "truss", "name": t.meta["name"], "haer": t.meta["haer"], "sources": t.meta["sources"], **b.info,
           "nodes": t.nodes, "members": [{"id": m["id"], "i": m["i"], "j": m["j"], "area": m["area"], "E": m["E"], "group": m["group"],
                                         "tension_only": bool(m.get("tension_only"))} for m in t.members],
           "deck_klf": b.deck_klf, "density_lb_ft3": b.density_lb_ft3, "crowd_klf": b.crowd_klf, "roadway_ft": b.roadway_ft,
           "supports": t.supports, "deck_nodes": deck, "deck_x_ft": xs, "mid_node": mid, "yield_ksi": t.yield_ksi,
           "dead": r_dead, "crowd_100psf": crowd,
           "trucks": {n: {"axles_per_truss": models.TRUCKS[n], "worst": e["members"]} for n, e in trucks.items()}}
    lines = [f"## {t.meta['name']} ({t.meta['haer']}), one truss", "",
             "| Load | Worst member | Stress (ksi) | Share of yield | Max deflection (in) |", "|---|---|---|---|---|"]
    w = max(r_dead["members"], key=lambda m: m["ratio"])
    lines.append(f"| Dead load | {w['id']} ({w['group']}) | {w['stress_ksi']:.1f} | {w['ratio']:.0%} | {-r_dead['disp_in'][mid][1]:.2f} |")
    for n, e in trucks.items():
        w = max(e["members"].values(), key=lambda m: m["ratio"])
        d = -min(f["mid_defl_in"] for f in e["frames"])
        lines.append(f"| Dead + {n} | {w['id']} ({w['group']}) | {w['stress_ksi']:.1f} | {w['ratio']:.0%} | {d:.2f} |")
    w = max(crowd["members"], key=lambda m: m["ratio"])
    lines.append(f"| Dead + 100 psf crowd | {w['id']} ({w['group']}) | {w['stress_ksi']:.1f} | {w['ratio']:.0%} | "
                 f"{-crowd['disp_in'][mid][1]:.2f} |")
    return out, lines


def span_bridge(b: models.SpanBridge) -> tuple[dict, list[str]]:
    s, w = b.span, b.live_klf_per_cable
    full = suspension.solve(s, suspension.patch(s, 0, s.L, w))
    ext = suspension.extremes(s, w)
    checks = []
    for c in b.checks:
        val, loads = suspension.check(s, w, c["kind"], c.get("dT", 0.0))
        checks.append(dict(c, model_ft=val, loaded=loads))
    out = {"slug": b.slug, "kind": "span", "name": b.name, "haer": b.haer, **b.info, "sources": b.sources, "inputs": b.inputs,
           "live_klf_per_cable": w, "checks": checks, "stiffener": b.stiffener,
           "derived": {"cable_area_in2": s.Ac_in2, "EI_kft2": s.EI_kft2, "H_dead_kip_per_cable": s.H, "Le_ft": s.Le, "Lt_ft": s.Lt},
           "span": {k: getattr(s, k) for k in ("L", "f", "w_dead", "Ec_ksi", "Ac_in2", "EI_kft2", "Le", "Lt", "depth_ft", "alpha", "n",
                                                "side_l", "side_w")}}
    lines = [f"## {b.name}, main span, one cable and its stiffening {b.stiffener}", "",
             f"- Dead-load cable pull {s.H:,.0f} kip per cable; cable stress at the towers "
             f"{full['cable_max_kip'] / s.Ac_in2:.1f} ksi under full live load.",
             "", "| Check | Model | Published | Source |", "|---|---|---|---|"]
    lines += [f"| {c['label']} | {c['model_ft']:.2f} ft | {c['report_ft']} ft | {c['source']} |" for c in checks]
    lines += ["", f"- Live load only, worst anywhere: down {ext['down_ft'][0]:.1f} ft, up {ext['up_ft'][0]:.1f} ft; "
              f"peak {b.stiffener} moment {ext['moment_kft'][0]:,.0f} kip-ft."]
    return out, lines


def run() -> str:
    OUT.mkdir(parents=True, exist_ok=True)
    WEB.mkdir(parents=True, exist_ok=True)
    md = ["# Tier 2 simulations", "", "Every input is tagged stated, measured or assumed in `src/bridgewatch/sim/models.py`.", ""]
    jobs = [lambda f=f: span_bridge(f()) for f in models.SPANS] + [lambda f=f: truss_bridge(f()) for f in models.all_trusses()]
    index = []
    for fn in jobs:
        data, lines = fn()
        slug = data["slug"]
        (OUT / f"{slug}.json").write_text(json.dumps(data, indent=1, default=float))
        (WEB / f"{slug}.json").write_text(json.dumps(data, separators=(",", ":"), default=float))
        index.append({"slug": slug, "kind": data["kind"], "name": data["name"], "haer": data["haer"]})
        md += [*lines, ""]
    (WEB / "index.json").write_text(json.dumps(index, indent=1))
    (ROOT / "reports" / "sim.md").write_text("\n".join(md))
    return "\n".join(md)
