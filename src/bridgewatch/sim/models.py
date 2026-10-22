"""The Tier 2 bridge models. Every number carries its source:
"stated" (printed on the record), "measured" (scaled off a drawing), or "assumed".
"""

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from itertools import pairwise

from . import suspension, truss


@dataclass
class TrussBridge:
    """One plane truss of a two-truss bridge, with its deck and the page copy that goes with it."""
    slug: str
    t: truss.Truss
    deck: list[str]                       # floor-beam nodes, in order
    xs: list[float]                       # their x, ft
    deck_klf: float                       # deck dead load per truss, kip/ft
    roadway_ft: float                     # clear width carrying the crowd load
    info: dict = field(default_factory=dict)   # kicker, dek, drawing, caption, deck_y_ft
    trucks: bool = True                   # False for footbridges
    density_lb_ft3: float = 480.0         # iron and steel

    @property
    def crowd_klf(self) -> float:         # 100 psf over the roadway, half to each truss
        return 0.100 * self.roadway_ft / 2

    def dead(self) -> dict:
        return truss.add(truss.self_weight(self.t, self.density_lb_ft3),
                         truss.panel_loads(self.deck, self.xs, {"uniform_klf": self.deck_klf}))


def m(i: str, j: str, area: float, group: str, E: float, tension_only: bool = False) -> dict:
    return {"id": f"{i}-{j}", "i": i, "j": j, "area": area, "E": E, "group": group, "tension_only": tension_only}


def chain(names: list[str], area: float, group: str, E: float, tension_only: bool = False) -> list[dict]:
    return [m(a, b, area, group, E, tension_only) for a, b in pairwise(names)]

# ---------------------------------------------------------------- Kelley Crossing
# HAER TX-31, Kelley Crossing Bridge, Caldwell County TX, Berlin Iron Bridge Co., c. 1895.
# Sheet 1: pin-to-pin panel lengths and 89 ft span (stated); node heights scaled off the
# 1/4" = 1'-0" elevation (measured, about +/- 0.3 ft). Sheet 2: table of sections.

KELLEY_X = [0.0, 14.5, 29.5, 44.5, 59.5, 74.5, 89.0]          # stated, sheet 1
KELLEY_UP = [0.0, 3.75, 5.6, 6.6, 5.6, 3.75, 0.0]             # measured, sheet 1
KELLEY_LO = [0.0, -3.3, -5.2, -6.1, -5.2, -3.3, 0.0]          # measured, sheet 1

KELLEY_SOURCES = {
    "record": "HAER TX-31 (loc.gov/item/tx0757), sheets 1-3, Christopher B. Brown and Christianna I. Raber, 1996",
    "panel lengths": "stated: 14'-6\", 4 x 15'-0\", 14'-6\"; span 89'-0\" (sheet 1)",
    "node heights": "measured off the sheet 1 elevation; centre depth 12.7 ft (sheet 2 section shows 12'-2 1/2\" overall)",
    "upper chord": ("stated outline: 14\" cover plate, 7\" webs, 2x2x3/8 angles (sheet 2). "
                    "Plate and web thickness assumed 1/4\": area 9.7 in2"),
    "lower chord": "stated: two 2\" x 3/4\" eye-bars per panel (sheets 2-3): 3.0 in2",
    "verticals": "stated: lattice of 2x2x3/8 angles (sheet 2); four angles assumed: 5.44 in2",
    "diagonals": "stated: 1\" round rods (sheets 2-3), crossed in each interior panel, tension only: 0.785 in2",
    "material": "wrought iron (Berlin Iron Bridge Co. practice); E = 26,000 ksi, yield 25 ksi assumed",
    "deck dead load": "assumed 0.31 kip/ft for 13'-3\" timber deck on steel stringers and floor beams; half to each truss",
}


def kelley_crossing() -> tuple[truss.Truss, list[str], list[float]]:
    nodes = {"E0": (0.0, 0.0), "E6": (KELLEY_X[6], 0.0)}
    for k in range(1, 6):
        nodes[f"U{k}"] = (KELLEY_X[k], KELLEY_UP[k])
        nodes[f"L{k}"] = (KELLEY_X[k], KELLEY_LO[k])
    up = ["E0"] + [f"U{k}" for k in range(1, 6)] + ["E6"]
    lo = ["E0"] + [f"L{k}" for k in range(1, 6)] + ["E6"]
    E = 26000.0
    members = []
    for k in range(6):
        members.append({"id": f"{up[k]}-{up[k + 1]}", "i": up[k], "j": up[k + 1], "area": 9.7, "E": E, "group": "upper chord"})
        members.append({"id": f"{lo[k]}-{lo[k + 1]}", "i": lo[k], "j": lo[k + 1], "area": 3.0, "E": E, "group": "lower chord",
                        "tension_only": True})
    for k in range(1, 6):
        members.append({"id": f"U{k}-L{k}", "i": f"U{k}", "j": f"L{k}", "area": 5.44, "E": E, "group": "vertical"})
    for k in range(1, 5):
        members.append({"id": f"U{k}-L{k + 1}", "i": f"U{k}", "j": f"L{k + 1}", "area": 0.785, "E": E, "group": "diagonal",
                        "tension_only": True})
        members.append({"id": f"L{k}-U{k + 1}", "i": f"L{k}", "j": f"U{k + 1}", "area": 0.785, "E": E, "group": "diagonal",
                        "tension_only": True})
    t = truss.Truss(nodes=nodes, members=members, supports={"E0": (True, True), "E6": (False, True)},
                    yield_ksi=25.0, meta={"name": "Kelley Crossing Bridge", "haer": "TX-31", "sources": KELLEY_SOURCES})
    deck = lo                                                     # floor beams hang at the lower panel points
    return t, deck, KELLEY_X


KELLEY_DECK_KLF = 0.31 / 2                                        # per truss, assumed

# Live loads per truss (half of each axle). AASHTO H-trucks: 14 ft axle spacing, 20/80 split.
TRUCKS = {
    "H10 (10-ton truck)": [(0.0, 2.0), (14.0, 8.0)],
    "H15 (15-ton truck)": [(0.0, 3.0), (14.0, 12.0)],
    "H20 (20-ton truck)": [(0.0, 4.0), (14.0, 16.0)],
}
CROWD_KLF = 0.100 * 13.25 / 2                                     # 100 psf over the 13'-3" roadway, per truss


def kelley_dead(t: truss.Truss, deck: list[str], xs: list[float]) -> dict:
    return truss.add(truss.self_weight(t), truss.panel_loads(deck, xs, {"uniform_klf": KELLEY_DECK_KLF}))


def kelley_bridge() -> TrussBridge:
    t, deck, xs = kelley_crossing()
    return TrussBridge("kelley_crossing", t, deck, xs, KELLEY_DECK_KLF, 13.25, info={
        "kicker": "HAER TX-31 · Caldwell County, Texas · Berlin Iron Bridge Co., c. 1895",
        "dek": ("An 89 ft lenticular iron truss: an arched top chord and a hanging bottom chord of eye-bars, with crossed "
                "1-inch rods that can only pull. Drag the truck across. Rods that would have to push go slack and the model drops them."),
        "drawing": "kelley-elevation.png",
        "caption": ("HAER TX-31, sheet 1 (Brown and Raber, 1996), Library of Congress. Panel lengths are printed on it; "
                    "panel-point heights were scaled off it to about ±0.3 ft."),
        "deck_y_ft": -0.6})


# ------------------------------------------------------------------ Bridge L5245
# HAER MN-133, Bridge L5245 over Okabena Creek, Jackson County MN. Sheet 7 (Tony Hanson, 2016) carries the
# elevation with dimensions and a full member schedule; thicknesses the schedule leaves out are assumed.

L5245_SOURCES = {
    "record": "HAER MN-133 (loc.gov/item/mn0635), sheet 7: east elevation and member schedule, Tony Hanson, 2016",
    "geometry": "stated: three 15 ft panels, 45 ft span, 7'-6\" from lower chord to upper chord (sheet 7)",
    "upper chord": ("stated: two channels 5 3/8\" x 1 3/4\" with lacing (L0-U1, U1-U2, U2-L3). "
                    "Web and flange thickness assumed 1/4\": 4.2 in2"),
    "lower chord": "stated: two bars 2\" x 1/2\" (L0-L3): 2.0 in2, tension only",
    "vertical": "stated: four angles 1 3/4\" x 1 3/4\" with bar lacing (L1-U1, L2-U2); thickness assumed 1/4\": 3.25 in2",
    "diagonal": "stated: looped bars 7/8\" diameter with turnbuckles, crossed in the middle panel: 0.60 in2, tension only",
    "material": "stated steel; E 29,000 ksi and yield 30 ksi assumed for early mild steel",
    "deck dead load": ("stated: 4\" concrete deck 15'-2\" wide on six 3x6 I-beam stringers, two 6\" outer channels, 5x12 floor "
                       "beams. Unit weights assumed (concrete 150 lb/ft3): 0.89 kip/ft, half to each truss"),
}


def l5245() -> TrussBridge:
    E = 29000.0
    nodes = {"L0": (0.0, 0.0), "L1": (15.0, 0.0), "L2": (30.0, 0.0), "L3": (45.0, 0.0), "U1": (15.0, 7.5), "U2": (30.0, 7.5)}
    members = (chain(["L0", "U1", "U2", "L3"], 4.2, "upper chord", E)
               + chain(["L0", "L1", "L2", "L3"], 2.0, "lower chord", E, tension_only=True)
               + [m("L1", "U1", 3.25, "vertical", E), m("L2", "U2", 3.25, "vertical", E),
                  m("U1", "L2", 0.601, "diagonal", E, True), m("L1", "U2", 0.601, "diagonal", E, True)])
    t = truss.Truss(nodes=nodes, members=members, supports={"L0": (True, True), "L3": (False, True)}, yield_ksi=30.0,
                    meta={"name": "Bridge L5245", "haer": "MN-133", "sources": L5245_SOURCES})
    return TrussBridge("bridge_l5245", t, ["L0", "L1", "L2", "L3"], [0.0, 15.0, 30.0, 45.0], 0.89 / 2, 15.17, info={
        "kicker": "HAER MN-133 · Okabena Creek, Jackson County, Minnesota",
        "dek": ("A 45 ft steel pony truss: two inclined end posts, one top strut and crossed rods in the middle panel. "
                "The smallest bridge here, and the only one whose drawing lists every member."),
        "drawing": "l5245-elevation.png",
        "caption": "HAER MN-133, sheet 7 (Tony Hanson, 2016), Library of Congress. Every dimension in the model is printed on this sheet.",
        "deck_y_ft": 0.0})


TRUSSES: list[Callable[[], TrussBridge]] = [kelley_bridge, l5245]


def all_trusses() -> list[Callable[[], TrussBridge]]:
    from . import trusses  # imported late: trusses.py builds on the helpers above

    return TRUSSES + trusses.ALL

# ------------------------------------------------------------------ Golden Gate
# J. B. Strauss, The Golden Gate Bridge: Report of the Chief Engineer, Sept 1937
# (Golden Gate Bridge and Highway District, 1938). archive.org/details/goldengatebridge1970gold

GG = {
    "L": 4200.0,                     # stated, main span
    "side": 1125.0,                  # stated, each side span
    "f": 470.0,                      # stated, cable sag
    "w_bridge": 21.300,              # stated, dead load of main span, kip/ft (both cables)
    "live_bridge": 4.000,            # stated, design live load, kip/ft
    "wires": 27572,                  # stated, per cable
    "wire_d": 0.196,                 # stated, inches
    "E_wire": 28750.0,               # stated, from wire tests, ksi
    "depth": 25.0,                   # stated, stiffening truss depth
    "top_chord": 145.51,             # stated, max gross area, centre span, in2
    "bot_chord": 132.0,              # stated, max gross area, centre span, in2
    "E_steel": 29000.0,              # assumed
}

GG_SOURCES = {
    "record": "Strauss, Report of the Chief Engineer, 1937, pp. 73-82 (principal dimensions; basis of design; stiffening trusses)",
    "geometry": "stated: 4,200 ft main span, 1,125 ft side spans, 470 ft sag, trusses 25 ft deep, 90 ft apart",
    "dead load": ("stated: 21,300 lb per lineal foot of main span (cables 6,670; trusses 3,330; floor 3,830; "
                  "bracing 600; paving 6,470; misc 400)"),
    "live load": "stated: 4,000 lb per lineal foot of bridge, of the length and position that gives the maximum effect",
    "cable": "stated: 27,572 wires of 0.196 in per cable (832 in2 of steel); wire E 28,750,000 psi from tests",
    "truss stiffness": ("from stated maximum chord areas (top 145.51, bottom 132 in2) at 25 ft depth; "
                        "chords are lighter away from the quarter points, so this is an upper bound"),
    "cable lengths": "Le and Lt from a parabolic main cable with backstays at the main cable's tower slope (assumed)",
    "side spans": "stated: suspended, 1,125 ft each; their dead load per foot assumed equal to the main span's",
    "not modelled": "tower bending stiffness (tower tops move freely with the cable), side-span live load, suspender stretch",
    "check": "the report gives a maximum downward deflection of 10.8 ft and upward of 5.8 ft at the centre span",
}


@dataclass
class SpanBridge:
    """A suspension main span as one cable and its stiffening truss or girder, with published deflection checks."""
    slug: str
    name: str
    haer: str
    span: suspension.Span
    live_klf_per_cable: float
    inputs: dict
    sources: dict
    checks: list[dict]
    info: dict = field(default_factory=dict)
    stiffener: str = "truss"


TABLE4 = "Ammann, von Kármán and Woodruff, 1941, Table 4 (normal temperature)"


def golden_gate(n: int = 420) -> suspension.Span:
    g = GG
    Ac = g["wires"] * math.pi / 4 * g["wire_d"] ** 2
    a, b = g["top_chord"], g["bot_chord"]
    I_in4 = a * b / (a + b) * (g["depth"] * 12) ** 2
    slope = 4 * g["f"] / g["L"]
    sec = math.sqrt(1 + slope**2)
    # parabola: integral of sec^3 ~ L(1 + 8 (f/L)^2), sec^2 ~ L(1 + 16/3 (f/L)^2)
    r = g["f"] / g["L"]
    Le = g["L"] * (1 + 8 * r**2) + 2 * g["side"] * sec**3
    Lt = g["L"] * (1 + 16 / 3 * r**2) + 2 * g["side"] * sec**2
    return suspension.Span(L=g["L"], f=g["f"], w_dead=g["w_bridge"] / 2, Ec_ksi=g["E_wire"], Ac_in2=Ac,
                           EI_kft2=g["E_steel"] * I_in4 / 144.0, Le=Le, Lt=Lt, depth_ft=g["depth"], n=n,
                           side_l=g["side"], side_w=g["w_bridge"] / 2)


def golden_gate_bridge() -> SpanBridge:
    return SpanBridge("golden_gate", "Golden Gate Bridge", "CA-31", golden_gate(), GG["live_bridge"] / 2, GG, GG_SOURCES, [
        {"kind": "half_q_down", "label": "Down at the quarter point, traffic tower to centre", "report_ft": 12.41, "source": TABLE4},
        {"kind": "half_3q_up", "label": "Up at the other quarter point, same traffic", "report_ft": 6.72, "source": TABLE4},
        {"kind": "full_c_down", "label": "Down at the centre, whole main span loaded", "report_ft": 7.34, "source": TABLE4},
        {"kind": "temp_c_down", "dT": 40, "label": "Deepest centre sag, traffic in the middle, 40°F warmer", "report_ft": 10.8,
         "source": "Strauss, 1937 report"},
        {"kind": "temp_c_up", "dT": -40, "label": "Highest centre lift, traffic at both ends, 40°F colder", "report_ft": 5.8,
         "source": "Strauss, 1937 report"}],
        info={"kicker": "HAER CA-31 · San Francisco to Marin · opened 1937", "ends": ["San Francisco", "Marin"],
              "dek": ("The 4,200 ft main span as its designers analysed it: one cable of 27,572 wires and the 25 ft stiffening truss it "
                      "carries, by deflection theory. Put traffic on any stretch and change the temperature. Drag along the deck to "
                      "move the traffic.")})


# ------------------------------------------------------------------ Tacoma Narrows (1940)
# O. H. Ammann, T. von Kármán, G. B. Woodruff, The Failure of the Tacoma Narrows Bridge, report to the Federal Works
# Agency, March 1941. authors.library.caltech.edu/records/q1ehq-5e206

TN = {
    "L": 2800.0, "side": 1100.0, "f": 232.0,                       # stated, pp. 11-12, 51 and Table 4
    "w_bridge": 5.700,                                             # stated, as built, kip/ft of centre span (p. 40)
    "w_side": 5.740,                                               # stated, side spans
    "live_bridge": 1.500,                                          # stated, the review's live load (p. 41)
    "Ac": 190.32,                                                  # stated, net wire area per cable (p. 52)
    "I_girder_in2ft2": 1283.0,                                     # stated, each stiffening girder (p. 47)
    "depth": 8.04,                                                 # stated, 8 ft 1/2 in plate girders
    "E_wire": 28000.0,                                             # assumed
    "E_steel": 29000.0,                                            # assumed
}
TN_SOURCES = {
    "record": "Ammann, von Kármán and Woodruff, The Failure of the Tacoma Narrows Bridge, Federal Works Agency, 1941 (Caltech library)",
    "geometry": "stated: 2,800 ft centre span, 1,100 ft suspended side spans, 232 ft sag (1/12), girders 39 ft apart",
    "dead load": ("stated: 5,700 lb per foot of centre span as built (slab 2,650; floor steel 720; girders 900; cables 1,430), "
                  "5,740 in the side spans"),
    "live load": "stated: the 1941 review used 1,500 lb per foot of bridge; the bridge was designed for 1,000",
    "cable": "stated: 6,308 No. 6 wires per cable in 19 strands, 190.32 in2 net; wire E 28,000 ksi assumed",
    "girder stiffness": "stated: each plate girder 96 x 1/2 web, four 8x6x1/2 angles, two 20x1/2 cover plates, I = 1,283 in2 ft2",
    "not modelled": "the wind: this is the static bridge. The flutter that destroyed it on 7 November 1940 is a dynamic instability",
}


def tacoma_narrows(n: int = 420) -> SpanBridge:
    t = TN
    r, slope = t["f"] / t["L"], 4 * t["f"] / t["L"]
    sec = math.sqrt(1 + slope**2)
    s = suspension.Span(L=t["L"], f=t["f"], w_dead=t["w_bridge"] / 2, Ec_ksi=t["E_wire"], Ac_in2=t["Ac"],
                        EI_kft2=t["E_steel"] * t["I_girder_in2ft2"], Le=t["L"] * (1 + 8 * r**2) + 2 * t["side"] * sec**3,
                        Lt=t["L"] * (1 + 16 / 3 * r**2) + 2 * t["side"] * sec**2, depth_ft=t["depth"], n=n,
                        side_l=t["side"], side_w=t["w_side"] / 2)
    return SpanBridge("tacoma_narrows", "Tacoma Narrows Bridge (1940)", "WA-99", s, t["live_bridge"] / 2, t, TN_SOURCES, [
        {"kind": "half_q_down", "label": "Down at the quarter point, traffic tower to centre", "report_ft": 10.95, "source": TABLE4},
        {"kind": "half_3q_up", "label": "Up at the other quarter point, same traffic", "report_ft": 2.74, "source": TABLE4},
        {"kind": "full_c_down", "label": "Down at the centre, whole main span loaded", "report_ft": 10.50, "source": TABLE4}],
        stiffener="girder",
        info={"kicker": "HAER WA-99 · Puget Sound, Washington · opened July 1940, fell November 1940", "ends": ["Tacoma", "Gig Harbor"],
              "dek": ("Two 8 ft plate girders stiffening a 2,800 ft span: 1/350 of the span, against Golden Gate's 1/168. Load it and "
                      "watch how far it moves. The static bridge was adequate; what it lacked was stiffness against the wind.")})


# ------------------------------------------------------------------ George Washington (1931)
# The 1941 report's Table 4 lists its properties as opened: one deck, no stiffening trusses (the lower deck and its trusses
# came in 1962). Every input below is from that table unless marked.

GWB = {"L": 3500.0, "side": 650.0, "f": 319.2, "w_bridge": 31.590, "live_bridge": 4.000, "Ac_all": 3195.0, "cables": 4,
       "I_all_in2ft2": 168.0, "E_wire": 28000.0, "E_steel": 29000.0, "depth": 8.0}
GWB_SOURCES = {
    "record": "Ammann, von Kármán and Woodruff, The Failure of the Tacoma Narrows Bridge, 1941, Table 4 (George Washington column)",
    "geometry": "stated: 3,500 ft centre span, 650 ft side spans (not suspended: straight backstays), 319.2 ft sag, 106 ft between cables",
    "dead load": "stated: 31,590 lb per foot of centre span, single-deck condition (39,500 with the 1962 lower deck)",
    "live load": "stated: 4,000 lb per foot of bridge",
    "cable": "stated: four cables, 3,195 in2 of wire in all; wire E 28,000 ksi assumed",
    "stiffness": "stated: 168 in2 ft2 for the whole floor: in effect an unstiffened bridge, held in shape by its own weight",
    "not modelled": "tower flexibility and the anchorages; the full-span check comes out 25% stiff, likely for that reason",
}


def george_washington(n: int = 420) -> SpanBridge:
    g, nc = GWB, GWB["cables"]
    r, slope = g["f"] / g["L"], 4 * g["f"] / g["L"]
    sec = math.sqrt(1 + slope**2)
    s = suspension.Span(L=g["L"], f=g["f"], w_dead=g["w_bridge"] / nc, Ec_ksi=g["E_wire"], Ac_in2=g["Ac_all"] / nc,
                        EI_kft2=g["E_steel"] * g["I_all_in2ft2"] / nc, Le=g["L"] * (1 + 8 * r**2) + 2 * g["side"] * sec**3,
                        Lt=g["L"] * (1 + 16 / 3 * r**2) + 2 * g["side"] * sec**2, depth_ft=g["depth"], n=n)
    return SpanBridge("george_washington", "George Washington Bridge (1931)", "NY-129", s, g["live_bridge"] / nc, g, GWB_SOURCES,
                      [
        {"kind": "half_q_down", "label": "Down at the quarter point, traffic tower to centre", "report_ft": 5.88, "source": TABLE4},
        {"kind": "half_3q_up", "label": "Up at the other quarter point, same traffic", "report_ft": 3.54, "source": TABLE4, "tol": 0.15},
        {"kind": "full_c_down", "label": "Down at the centre, whole main span loaded", "report_ft": 2.92, "source": TABLE4, "tol": 0.3}],
        stiffener="floor",
        info={"kicker": "HAER NY-129 · Hudson River, Fort Lee to Manhattan · opened 1931", "ends": ["Fort Lee", "Manhattan"],
              "dek": ("At 3,500 ft, twice the longest span before it, and built with no stiffening truss at all: Ammann let "
                      "31,590 lb of bridge per foot hold the cables in shape. Compare how little it moves with Tacoma Narrows, "
                      "a ninth of its weight.")})


SPANS: list[Callable[[], SpanBridge]] = [golden_gate_bridge, george_washington, tacoma_narrows]
