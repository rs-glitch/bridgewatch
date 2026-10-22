"""Tier 2 truss models beyond Kelley Crossing: one plane truss each, built from HAER drawings.
Every number carries its source, as in models.py: stated (printed on the sheet), measured (scaled off it), or assumed.
Wrought iron: E 26,000 ksi, yield 25 ksi. Early mild steel: E 29,000 ksi, yield 30 ksi. Both assumed.
"""

import math

from . import truss
from .models import TrussBridge, chain, m

IRON, STEEL = 26000.0, 29000.0


def ft(feet: float, inches: float = 0.0) -> float:
    return feet + inches / 12


def angle(a: float, b: float, t: float) -> float:
    """Area of one angle a x b x t, in2."""
    return (a + b - t) * t


def rod(d: float) -> float:
    return math.pi / 4 * d * d


def cumsum(steps: list[float], start: float = 0.0) -> list[float]:
    out = [start]
    for s in steps:
        out.append(out[-1] + s)
    return out


# ------------------------------------------------------------------ Walnut Street (PA-412)
WALNUT_SOURCES = {
    "record": "HAER PA-412 (loc.gov/item/pa3490), sheets 2-4, Lou A. McCrory and John R. Bowie, 1996; sizes from Brookhart & Tyo's "
              "1950 report, field checked 1996 (sheet 4 note)",
    "geometry": "stated: ten panels of 17'-3 1/4\", 35'-0\" pin to pin, sub-panel points M at mid-height (sheet 2)",
    "upper chord": "stated: Phoenix columns, 16.0 in2 (end posts, U4-U6) and 14.1 in2 (U2-U4, U6-U8) (sheet 3)",
    "vertical": ("stated: Phoenix columns 6.4 in2 (U4-L4, U6-L6) and 3.8 in2 (upper verticals); flats and rods for the hangers: "
                 "L1-M1 two flats 6\" x 11/16\" (north truss, modelled), L2-U2 two flats 3\" x 11/16\", L3-M3 two 1 1/4\" rods and "
                 "one flat 3 3/8\" x 11/16\" (sheets 3-4)"),
    "lower chord": "stated: two flats 4 1/8\" x 1\" (8.25 in2), 4 1/8\" x 1 1/4\" in the middle panels (10.3 in2), tension only (sheet 4)",
    "diagonal": ("stated: struts of four angles 3x2 1/2x5/16 and two plates 7 1/2x5/16 (11.2 in2); main diagonals of plates "
                 "3x1 and 3x13/16; middle-panel rods 1 1/4\" and 1 1/2\", tension only (sheet 4)"),
    "material": "wrought iron (Phoenix columns, 1890) assumed: E 26,000 ksi, yield 25 ksi",
    "deck dead load": "assumed: open steel grid floor, stringers and floor beams on a 21 ft roadway, 0.84 kip/ft, half to each truss",
    "not modelled": "the mid-height longitudinal strut, buckling of the Phoenix columns, the 1996 flood loss of spans",
}


def walnut_street() -> TrussBridge:
    p, h = ft(17, 3.25), 35.0
    n = {f"L{i}": (i * p, 0.0) for i in range(11)}
    n |= {f"U{i}": (i * p, h) for i in range(2, 9)}
    n |= {f"M{i}": (i * p, h / 2) for i in (1, 3, 5, 7, 9)}
    E = IRON
    strut = 4 * angle(3, 2.5, 5 / 16) + 2 * 7.5 * 5 / 16
    hanger3 = 2 * rod(1.25) + 3.375 * 11 / 16
    mem = chain(["L0", "M1", "U2"], 16.0, "upper chord", E) + chain(["U8", "M9", "L10"], 16.0, "upper chord", E)
    mem += chain(["U2", "U3", "U4"], 14.1, "upper chord", E) + chain(["U4", "U5", "U6"], 16.0, "upper chord", E)
    mem += chain(["U6", "U7", "U8"], 14.1, "upper chord", E)
    for i in range(10):
        a = 10.3125 if i in (4, 5) else 8.25
        mem.append(m(f"L{i}", f"L{i + 1}", a, "lower chord", E, True))
    mem += [m("L2", "U2", 2 * 3 * 11 / 16, "vertical", E, True), m("L8", "U8", 2 * 3 * 11 / 16, "vertical", E, True),
            m("L4", "U4", 6.4, "vertical", E), m("L6", "U6", 6.4, "vertical", E)]
    mem += [m(f"M{i}", f"U{i}", 3.8, "vertical", E) for i in (3, 5, 7)]
    mem += [m(f"L{i}", f"M{i}", 2 * 6 * 11 / 16, "vertical", E, True) for i in (1, 9)]
    mem += [m(f"L{i}", f"M{i}", hanger3, "vertical", E, True) for i in (3, 5, 7)]
    mem += [m("L2", "M1", strut, "diagonal", E), m("L2", "M3", strut, "diagonal", E),
            m("L8", "M7", strut, "diagonal", E), m("L8", "M9", strut, "diagonal", E),
            m("U2", "M3", 6.0, "diagonal", E, True), m("U8", "M7", 6.0, "diagonal", E, True),
            m("M3", "L4", 2 * 3 * 13 / 16, "diagonal", E, True), m("M7", "L6", 2 * 3 * 13 / 16, "diagonal", E, True),
            m("L4", "M5", 2 * rod(1.25), "diagonal", E, True), m("L6", "M5", 2 * rod(1.25), "diagonal", E, True),
            m("M5", "U4", 2 * rod(1.5), "diagonal", E, True), m("M5", "U6", 2 * rod(1.5), "diagonal", E, True)]
    t = truss.Truss(nodes=n, members=mem, supports={"L0": (True, True), "L10": (False, True)}, yield_ksi=25.0,
                    meta={"name": "Walnut Street Bridge", "haer": "PA-412", "sources": WALNUT_SOURCES})
    deck = [f"L{i}" for i in range(11)]
    return TrussBridge("walnut_street", t, deck, [n[d][0] for d in deck], 0.84 / 2, 19.0, info={
        "kicker": "HAER PA-412 · Susquehanna River, Harrisburg, Pennsylvania · 1890",
        "dek": ("One 173 ft span of a Baltimore truss: each panel split at mid-height so the long Phoenix-column verticals "
                "never buckle. The bridge carried trolleys, then cars, and is now a footbridge."),
        "drawing": "walnut-elevation.png",
        "caption": "HAER PA-412, sheet 2 (McCrory and Bowie, 1996), Library of Congress. Half elevation; the truss is symmetric.",
        "deck_y_ft": 0.0})


# ------------------------------------------------------------------ Slate Run (PA-460)
SLATE_SOURCES = {
    "record": "HAER PA-460 (loc.gov/item/pa3579), sheets 2-3, Elizabeth Milnarik, Slavica Bubic, 1997",
    "geometry": ("stated: lower panel points L0-L19 and upper U1-U19 at their printed spacings, 202'-8\" overall; 22'-4\" between "
                 "chords plus 1'-4\" chord depths, so 23'-8\" centroid to centroid (sheet 3)"),
    "upper chord": ("stated: two angles 3x3x1/2 and two plates 16x1/2 throughout (21.5 in2); two more angles over the middle 154'-2\" "
                    "and a 22x1/2 plate over the middle 128' (sheet 3)"),
    "lower chord": "stated: two angles 3x3x1/2 and two plates 16x1/2 (21.5 in2); a 22x1/8 plate over the middle 117'-4\" (sheet 3)",
    "diagonal": ("stated: two angles 3x3x1/2 (5.5 in2) for every web member, four angles at L0 and L19; 'tension' and "
                 "'compression' families as listed (sheet 3). The riveted crossings are not modelled as joints"),
    "end post": "stated: two angles 3x3x1/2, two plates 16x1/2, one plate 22x1/2 (32.5 in2) (sheet 3)",
    "material": "1890 iron or steel; wrought iron assumed: E 26,000 ksi, yield 25 ksi",
    "deck dead load": ("stated: 12\" I stringers and 5\" open grid floor, not original; unit weights assumed: 0.68 kip/ft, half to each "
                       "truss"),
}
SLATE_TOP = [ft(11), ft(10, 6), ft(9, 10), ft(10, 9), ft(10, 6), ft(10, 5), ft(9, 10), ft(10, 10), ft(10, 6), ft(10, 3),
             ft(10, 4), ft(10, 6), ft(10), ft(10, 6), ft(10, 6), ft(10, 2), ft(10, 6), ft(10, 4)]
SLATE_BOT = [ft(8, 9), ft(11), ft(10, 3), ft(10, 4), ft(10, 8), ft(10, 9), ft(10, 5), ft(10, 5), ft(10, 11), ft(10, 9), ft(10, 4),
             ft(10, 8), ft(10, 9), ft(10, 6), ft(10, 8), ft(10, 6), ft(10, 8), ft(10, 7), ft(12, 2)]


def slate_run() -> TrussBridge:
    E, h = IRON, ft(23, 8)
    ux, lx = cumsum(SLATE_TOP, ft(3, 7)), cumsum(SLATE_BOT)
    span = lx[-1]
    n = {f"L{i}": (x, 0.0) for i, x in enumerate(lx)} | {f"U{i + 1}": (x, h) for i, x in enumerate(ux)}
    mid = span / 2

    def top_area(x: float) -> float:
        return 21.5 + (5.5 if abs(x - mid) <= ft(154, 2) / 2 else 0) + (11.0 if abs(x - mid) <= 64 else 0)

    def bot_area(x: float) -> float:
        return 21.5 + (2.75 if abs(x - mid) <= ft(117, 4) / 2 else 0)

    mem = [m(f"U{i}", f"U{i + 1}", top_area((n[f"U{i}"][0] + n[f"U{i + 1}"][0]) / 2), "upper chord", E) for i in range(1, 19)]
    mem += [m(f"L{i}", f"L{i + 1}", bot_area((lx[i] + lx[i + 1]) / 2), "lower chord", E) for i in range(19)]
    mem += [m("L0", "U1", 32.5, "end post", E), m("L19", "U19", 32.5, "end post", E)]
    comp = [(4, 1), (5, 2), (6, 3), (7, 4), (8, 5), (9, 6), (10, 7), (11, 8), (12, 9),
            (16, 18), (15, 17), (14, 16), (13, 15), (12, 14), (11, 13), (10, 12), (9, 11)]
    tens = [(1, 1), (1, 2), (1, 3), (2, 4), (3, 5), (4, 6), (5, 7), (6, 8), (7, 9), (8, 10),
            (19, 18), (19, 17), (19, 16), (18, 15), (17, 14), (16, 13), (15, 12), (14, 11), (13, 10)]
    mem += [m(f"U{u}", f"L{lo}", 5.5, "diagonal", E) for u, lo in comp + tens]
    mem += [m(f"U{u}", f"L{lo}", 11.0, "diagonal", E) for u, lo in ((2, 0), (3, 0), (17, 19), (18, 19))]
    t = truss.Truss(nodes=n, members=mem, supports={"L0": (True, True), "L19": (False, True)}, yield_ksi=25.0,
                    meta={"name": "Upper Bridge at Slate Run", "haer": "PA-460", "sources": SLATE_SOURCES})
    deck = [f"L{i}" for i in range(20)]
    return TrussBridge("slate_run", t, deck, lx, 0.68 / 2, 16.75, info={
        "kicker": "HAER PA-460 · Pine Creek, Lycoming County, Pennsylvania · 1890",
        "dek": ("A 203 ft 'quintangular' lattice: five Warren trusses overlapped, so every load has many paths to the bearings. "
                "Watch how evenly the diagonals share a truck compared with the older trusses here."),
        "drawing": "slate-elevation.png",
        "caption": ("HAER PA-460, sheet 3 (Milnarik and Bubic, 1997), Library of Congress. Every panel length in the model is printed on "
                    "it."),
        "deck_y_ft": 0.0})


# ------------------------------------------------------------------ Nicholson (PA-468)
NICH_SOURCES = {
    "record": "HAER PA-468 (loc.gov/item/pa3588), sheets 2 and 4, Jonathan Cherry, 1997",
    "geometry": ("stated: eight panels of 14'-2 3/4\"; upper-to-lower chord depths 8'-10 3/8\", 14'-3\", 15'-8 11/16\", 16'-0 7/16\"; "
                 "bottom-chord eyebar lengths 15'-4\", 14'-5\", 14'-3\", 14'-2 3/4\" fix the lower chord's shape (sheet 2). "
                 "Hanger length to the deck 0.8 ft measured"),
    "upper chord": "stated: two channels 8x2x5/16 and a plate 16x5/16; channel thickness taken through: 12.1 in2 (sheet 4)",
    "lower chord": "stated: two eyebars 3\" x 1 1/8\" per panel (6.75 in2), tension only (sheets 2, 4)",
    "end post": "stated: four angles 2x2x1/4, two plates 9 1/4x5/16, one plate 21x1/4 (14.8 in2) (sheet 4)",
    "vertical": ("stated: four angles 1 3/4x1 3/4x1/4 with lacing, U1-M1 to U7-M7 (3.4 in2); U-bolt hangers of 1\" square bar, two legs "
                 "(sheet 4)"),
    "diagonal": "stated: one or two 7/8\" rods, two 1\" rods in the middle panels, crossed, tension only (sheet 4)",
    "edge stiffener": "stated: four angles 1 3/4x1 3/4x1/4 with lacing, L0 to L8 along the deck (sheet 4)",
    "material": "wrought iron (Berlin Iron Bridge Co., 1881) assumed: E 26,000 ksi, yield 25 ksi",
    "deck dead load": ("stated: 2x4 decking, 6\" I stringers, 7\" I deck beams (not original); unit weights assumed: 0.27 kip/ft, half to "
                       "each truss"),
}


def nicholson() -> TrussBridge:
    E, p = IRON, ft(14, 2.75)
    eye = [ft(15, 4), ft(14, 5), ft(14, 3), ft(14, 2.75)]
    rise = [math.sqrt(max(e * e - p * p, 0.0)) for e in eye]       # drop of each eyebar from the end inwards
    depth = [ft(8, 10.375), ft(14, 3), ft(15, 8.6875), ft(16, 0.4375)]
    m4 = 0.0
    my = [m4 + rise[1] + rise[2] + rise[3], m4 + rise[2] + rise[3], m4 + rise[3], m4]
    u0 = my[0] + rise[0]
    hang = 0.8
    n = {"L0": (0.0, -hang), "L8": (8 * p, -hang), "U0": (0.0, u0), "U8": (8 * p, u0)}
    for i in range(1, 8):
        k = min(i, 8 - i) - 1
        n[f"M{i}"] = (i * p, my[k])
        n[f"U{i}"] = (i * p, my[k] + depth[k])
        n[f"L{i}"] = (i * p, -hang)
    top = 2 * (8 * 5 / 16 + 2 * (2 - 5 / 16) * 5 / 16) + 16 * 5 / 16
    endpost = 4 * angle(2, 2, 0.25) + 2 * 9.25 * 5 / 16 + 21 * 0.25
    four = 4 * angle(1.75, 1.75, 0.25)
    mem = chain([f"U{i}" for i in range(9)], top, "upper chord", E)
    mem += chain(["U0"] + [f"M{i}" for i in range(1, 8)] + ["U8"], 2 * 3 * 1.125, "lower chord", E, True)
    mem += [m("L0", "U0", endpost, "end post", E), m("L8", "U8", endpost, "end post", E)]
    mem += [m(f"M{i}", f"U{i}", four, "vertical", E) for i in range(1, 8)]
    mem += [m(f"L{i}", f"M{i}", 2.0, "hanger", E, True) for i in range(1, 8)]
    mem += chain([f"L{i}" for i in range(9)], four, "edge stiffener", E)
    one, two78, two1 = rod(0.875), 2 * rod(0.875), 2 * rod(1.0)
    for u, mm_, a in [(2, 1, one), (3, 2, one), (4, 3, one), (4, 5, one), (5, 6, one), (6, 7, one),
                      (1, 2, two78), (7, 6, two78), (2, 3, two1), (3, 4, two1), (5, 4, two1), (6, 5, two1)]:
        mem.append(m(f"U{u}", f"M{mm_}", a, "diagonal", E, True))
    t = truss.Truss(nodes=n, members=mem, supports={"L0": (True, True), "L8": (False, True)}, yield_ksi=25.0,
                    meta={"name": "Nicholson Township Lenticular Bridge", "haer": "PA-468", "sources": NICH_SOURCES})
    deck = [f"L{i}" for i in range(9)]
    return TrussBridge("nicholson", t, deck, [i * p for i in range(9)], 0.27 / 2, 14.2, info={
        "kicker": "HAER PA-468 · Tunkhannock Creek, Wyoming County, Pennsylvania · 1881",
        "dek": ("A 114 ft Berlin lenticular truss whose lower chord rides above the deck: the roadway hangs from it on U-bolts. "
                "The arch pushes, the eyebar lens pulls, and the two cancel at the ends."),
        "drawing": "nicholson-elevation.png",
        "caption": ("HAER PA-468, sheet 2 (Jonathan Cherry, 1997), Library of Congress. Panel lengths, depths and eyebar lengths are "
                    "printed on it."),
        "deck_y_ft": -hang})


# ------------------------------------------------------------------ Old Corinth Road (NY-292)
CORINTH_SOURCES = {
    "record": ("HAER NY-292 (loc.gov/item/ny1775), sheets 1-3, Caroline Schweyer, Luis G. Rosario-Lluveras, Wang Bing, Karl Bodensiek, "
               "1994-95"),
    "geometry": ("stated: nine panels at their printed lengths, 136'-0\" (sheet 1 plan). Panel-point heights measured off the 1/8\" "
                 "elevation (about +/- 0.3 ft), checked against the stated 17'-11 1/2\" depth at section A-A (sheet 3)"),
    "upper chord": "stated outline: box of 7\" webs and 2x2 angles, 1'-2\" wide (sheet 2); thicknesses as drawn, 1/4\": 7.25 in2 assumed",
    "lower chord": "stated: two bars 3 1/4\" x 1 1/2\" (9.75 in2), tension only (sheet 2)",
    "vertical": "stated outline: laced posts of 2x2x3/16 angles, 1'-2\" wide (sheet 2); four angles: 2.9 in2 assumed",
    "diagonal": "stated: 1 1/4\" rods (diagonals) and 1\" rods (counters), crossed in panels 1-8, tension only (sheet 2)",
    "material": "wrought iron (Berlin Iron Bridge Co., 1885) assumed: E 26,000 ksi, yield 25 ksi",
    "deck dead load": ("stated: 7 stringers on 2'-7\" floor beams at mid-height of the posts; timber plank and unit weights assumed: 0.40 "
                       "kip/ft, half to each truss"),
}


def old_corinth() -> TrussBridge:
    E = IRON
    xs = cumsum([ft(15, 6.25), ft(14, 11.75), ft(15, 0.25), ft(14, 11.75), ft(15, 0.5),
                 ft(14, 11.75), ft(14, 11.75), ft(15, 0.25), ft(15, 5.75)])
    up = [0, 5.5, 9.27, 11.58, 12.36, 12.36, 11.58, 9.27, 5.5, 0]       # measured, symmetrised
    lo = [0, -4.98, -8.8, -10.6, -11.66, -11.66, -10.6, -8.8, -4.98, 0]
    dy = -0.5                                                           # floor beams at mid-height, measured
    n = {"L0": (0.0, 0.0), "L9": (xs[9], 0.0)}
    for i in range(1, 9):
        n[f"U{i}"], n[f"L{i}"], n[f"D{i}"] = (xs[i], up[i]), (xs[i], lo[i]), (xs[i], dy)
    upper, post = 7.25, 2.9
    mem = chain(["L0"] + [f"U{i}" for i in range(1, 9)] + ["L9"], upper, "upper chord", E)
    mem += chain(["L0"] + [f"L{i}" for i in range(1, 9)] + ["L9"], 9.75, "lower chord", E, True)
    for i in range(1, 9):
        mem += [m(f"U{i}", f"D{i}", post, "vertical", E), m(f"D{i}", f"L{i}", post, "vertical", E)]
    for i in range(1, 8):
        main_dir = i < 4.5                                              # mains slope down toward mid-span
        a_main, a_ctr = rod(1.25), rod(1.0)
        mem.append(m(f"U{i}", f"L{i + 1}", a_main if main_dir else a_ctr, "diagonal", E, True))
        mem.append(m(f"L{i}", f"U{i + 1}", a_ctr if main_dir else a_main, "diagonal", E, True))
    t = truss.Truss(nodes=n, members=mem, supports={"L0": (True, True), "L9": (False, True)}, yield_ksi=25.0,
                    meta={"name": "Old Corinth Road Bridge", "haer": "NY-292", "sources": CORINTH_SOURCES})
    deck = ["L0"] + [f"D{i}" for i in range(1, 9)] + ["L9"]
    return TrussBridge("old_corinth", t, deck, xs, 0.40 / 2, 17.5, info={
        "kicker": "HAER NY-292 · Sacandaga River, Hadley, New York · 1885",
        "dek": ("A 136 ft Douglas-patent lenticular truss with the road threaded through its middle, half above and half below. "
                "The floor beams hang on the posts, so each post works both ways at once."),
        "drawing": "corinth-elevation.png",
        "caption": ("HAER NY-292, sheet 1 (Schweyer and Rosario-Lluveras, 1995), Library of Congress. Panel-point heights were scaled off "
                    "this elevation."),
        "deck_y_ft": dy})


# ------------------------------------------------------------------ Whetstone Creek (OH-90)
WHET_SOURCES = {
    "record": "HAER OH-90 (loc.gov/item/oh1718), sheets 2-3, Daron Fender, Elaine Pierce, Troy Zimmermann, 1993",
    "geometry": ("stated: half elevation with pin spacings and a 13'-1\" overall depth at mid-span (sheet 2); the bridge is symmetric "
                 "about L5. Upper panel-point heights measured off the 1/2\" elevation (about +/- 0.2 ft)"),
    "upper chord": "stated: 8\" riveted octagonal tube (sheet 3); plate thickness not given, 8.0 in2 assumed",
    "vertical": ("stated: 2\" cruciform (U1-L1, U9-L9), laced 1 3/4\" angles (U2-L2, U4-L4, U6-L6, U8-L8), cruciform of 1 1/2\" angles "
                 "(U3-L3, U5-L5, U7-L7) (sheet 3); thicknesses assumed 3/16\""),
    "diagonal": "stated: 1\" rods, crossed in every interior panel, tension only (sheet 3)",
    "lower chord": "stated: two wrought-iron bars 1/2\" x 6\" (6.0 in2), tension only (sheets 2-3)",
    "material": "wrought iron (c. 1879) assumed: E 26,000 ksi, yield 25 ksi",
    "deck dead load": ("stated: 3 1/2\" decking, 8 1/2\" stringers, 8\" floor beams, 14'-9\" between trusses; unit weights assumed: 0.33 "
                       "kip/ft, half to each truss"),
}


def whetstone() -> TrussBridge:
    E = IRON
    half = [0.0, 10.27, 19.79, 29.60, 39.89, 50.88]                     # stated pin spacings (clear widths plus half posts)
    xs = half + [2 * half[-1] - x for x in reversed(half[:-1])]
    hh = [0.0, 4.52, 7.62, 9.76, 11.57, 12.42]                          # measured
    hs = hh + list(reversed(hh[:-1]))
    n = {f"L{i}": (x, 0.0) for i, x in enumerate(xs)} | {f"U{i}": (xs[i], hs[i]) for i in range(1, 10)}
    mem = chain(["L0"] + [f"U{i}" for i in range(1, 10)] + ["L10"], 8.0, "upper chord", E)
    mem += chain([f"L{i}" for i in range(11)], 6.0, "lower chord", E, True)
    cruci2, laced, cruci15 = 2 * 2 * 0.375, 4 * angle(1.75, 1.75, 3 / 16), 4 * angle(1.5, 1.5, 3 / 16)
    for i in range(1, 10):
        a = cruci2 if i in (1, 9) else laced if i % 2 == 0 else cruci15
        mem.append(m(f"U{i}", f"L{i}", a, "vertical", E))
    for i in range(1, 9):
        mem += [m(f"U{i}", f"L{i + 1}", rod(1.0), "diagonal", E, True), m(f"L{i}", f"U{i + 1}", rod(1.0), "diagonal", E, True)]
    t = truss.Truss(nodes=n, members=mem, supports={"L0": (True, True), "L10": (False, True)}, yield_ksi=25.0,
                    meta={"name": "Whetstone Creek Bridge", "haer": "OH-90", "sources": WHET_SOURCES})
    deck = [f"L{i}" for i in range(11)]
    return TrussBridge("whetstone_creek", t, deck, xs, 0.33 / 2, 14.0, info={
        "kicker": "HAER OH-90 · Whetstone Creek, Morrow County, Ohio · c. 1879",
        "dek": ("A 102 ft wrought-iron bowstring: an octagonal tube arch tied by a pair of flat bars. Crossed 1-inch rods in "
                "every panel take the uneven loads the arch alone can't."),
        "drawing": "whetstone-elevation.png",
        "caption": ("HAER OH-90, sheet 2 (Fender, Pierce and Zimmermann, 1993), Library of Congress. Half elevation; the bridge is "
                    "symmetric."),
        "deck_y_ft": 0.0})


# ------------------------------------------------------------------ Cooper's Tubular Arch (NY-291)
COOPER_SOURCES = {
    "record": "HAER NY-291 (loc.gov/item/ny1774), sheets 1-2, Caroline Schweyer, Luis G. Rosario-Lluveras, Wang Bing, 1994-95",
    "geometry": ("stated: six panels 10'-0\", 10'-2\", 10'-8 1/2\", 10'-8 1/2\", 10'-2\", 10'-0\"; 61'-9\" span (sheets 1-2). "
                 "Upper panel-point heights measured off the 3/8\" elevation, checked against the 9'-2\" section (sheet 2)"),
    "upper chord": "stated: Phoenix column 6 3/4\" diameter, 9 1/2\" over the flanges, 1/4\" wall (sheet 2): 7.85 in2",
    "vertical": "stated: laced post of two flats 1 3/4\" x 5/8\" (sheet 2): 2.19 in2",
    "diagonal": "stated: 1 1/8\" rods for diagonals and counters, tension only (sheet 2)",
    "lower chord": "stated: two bars 4\" x 5/8\" (5.0 in2), tension only (sheet 2)",
    "material": "cast and wrought iron (1875) assumed: E 26,000 ksi, yield 25 ksi",
    "deck dead load": ("stated: 9\" I transverse beams, 4\" I stringers, 13'-3\" between trusses; plank deck and unit weights assumed: "
                       "0.22 kip/ft, half to each truss"),
}


def coopers() -> TrussBridge:
    E = IRON
    xs = cumsum([ft(10), ft(10, 2), ft(10, 8.5), ft(10, 8.5), ft(10, 2), ft(10)])
    hs = [0, 4.57, 7.42, 8.44, 7.42, 4.57, 0]                          # measured
    n = {f"L{i}": (x, 0.0) for i, x in enumerate(xs)} | {f"U{i}": (xs[i], hs[i]) for i in range(1, 6)}
    phoenix = math.pi * (6.75 - 0.25) * 0.25 + 4 * 2 * 1.375 * 0.25
    mem = chain(["L0"] + [f"U{i}" for i in range(1, 6)] + ["L6"], phoenix, "upper chord", E)
    mem += chain([f"L{i}" for i in range(7)], 2 * 4 * 0.625, "lower chord", E, True)
    mem += [m(f"U{i}", f"L{i}", 2 * 1.75 * 0.625, "vertical", E) for i in range(1, 6)]
    for i in range(1, 5):
        mem += [m(f"U{i}", f"L{i + 1}", rod(1.125), "diagonal", E, True), m(f"L{i}", f"U{i + 1}", rod(1.125), "diagonal", E, True)]
    t = truss.Truss(nodes=n, members=mem, supports={"L0": (True, True), "L6": (False, True)}, yield_ksi=25.0,
                    meta={"name": "Cooper's Tubular Arch Bridge", "haer": "NY-291", "sources": COOPER_SOURCES})
    deck = [f"L{i}" for i in range(7)]
    return TrussBridge("coopers_arch", t, deck, xs, 0.22 / 2, 13.25, info={
        "kicker": "HAER NY-291 · Old Erie Canal, DeWitt, New York · 1875",
        "dek": ("The only surviving bridge on William Cooper's 1873 patent: a Phoenix-column arch tied by flat bars, 62 ft "
                "between bearings. It now carries a bike path across the re-watered canal."),
        "drawing": "coopers-elevation.png",
        "caption": ("HAER NY-291, sheet 1 (Schweyer and Rosario-Lluveras, 1995), Library of Congress. Heights were scaled off this "
                    "elevation."),
        "deck_y_ft": 0.0})


ALL = [walnut_street, slate_run, nicholson, old_corinth, whetstone, coopers]
