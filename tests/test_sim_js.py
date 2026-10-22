"""The browser solver (web/bridges/solver.js) must give the same answers as the Python one."""

import json
import shutil
import subprocess

import numpy as np
import pytest

from bridgewatch.paths import ROOT
from bridgewatch.sim import models, suspension, truss

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node not installed")


def _js(script: str, payload: dict) -> dict:
    src = f"const S = require({json.dumps(str(ROOT / 'web' / 'bridges' / 'solver.js'))});\n" \
          f"const D = JSON.parse(require('fs').readFileSync(0, 'utf8'));\n{script}"
    out = subprocess.run([NODE, "-e", src], input=json.dumps(payload), capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def test_truss_matches_python():
    t, deck, xs = models.kelley_crossing()
    axles = [(30.0, 4.0), (44.0, 16.0)]
    py = truss.solve(t, truss.add(models.kelley_dead(t, deck, xs), truss.panel_loads(deck, xs, {"axles": axles})))
    tj = {"nodes": t.nodes, "members": [dict(m, tension_only=bool(m.get("tension_only"))) for m in t.members],
          "supports": t.supports, "yield_ksi": t.yield_ksi}
    js = _js("""
      const dead = S.addLoads(S.selfWeight(D.t), S.panelLoads(D.deck, D.xs, {uniform_klf: D.w}));
      const r = S.solveTruss(D.t, S.addLoads(dead, S.panelLoads(D.deck, D.xs, {axles: D.axles})));
      console.log(JSON.stringify(r));""", {"t": tj, "deck": deck, "xs": xs, "w": models.KELLEY_DECK_KLF, "axles": axles})
    for a, b in zip(py["members"], js["members"], strict=True):
        assert a["id"] == b["id"] and a["active"] == b["active"]
        assert abs(a["force_kip"] - b["force_kip"]) < 1e-6 * max(1.0, abs(a["force_kip"]))
    assert abs(py["disp_in"]["L3"][1] - js["disp_in"]["L3"][1]) < 1e-9


def test_suspension_matches_python():
    s = models.golden_gate(n=420)
    py = suspension.solve(s, suspension.patch(s, 1100, 3100, 2.0), 40)
    span = {k: getattr(s, k) for k in ("L", "f", "w_dead", "Ec_ksi", "Ac_in2", "EI_kft2", "Le", "Lt", "depth_ft", "alpha", "n",
                                       "side_l", "side_w")}
    js = _js("const r = S.solveSpan(D.s, S.patch(D.s, 1100, 3100, 2.0), 40); console.log(JSON.stringify(r));", {"s": span})
    assert np.allclose(py["defl_ft"], js["defl_ft"], rtol=1e-6, atol=1e-8)
    assert np.allclose(py["moment_kft"], js["moment_kft"], rtol=1e-5, atol=1e-3)
    assert abs(py["h_kip"] - js["h_kip"]) < 1e-6 * abs(py["h_kip"])
