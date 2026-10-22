# Tier 2: structural simulation for documented bridges

Goal: 100 bridges with public, detailed structural data, each with a structural model a visitor can load (vehicles, wind,
snow, temperature) and watch respond. First milestone: 10.

## Source of structural data

- **HAER measured drawings** (Library of Congress, public domain). 2,829 bridges are listed in Wikipedia's "Bridges documented by
  the Historic American Engineering Record" tables. `scripts/haer_scan.py` reads each Library of Congress record: number of
  measured drawings, sheet titles, dates and significance.
- Later, possibly: NTSB investigation reports, published research models. Never security-restricted plans of in-service bridges.

## Selection rules

A bridge qualifies only when **its drawings give the geometry and the member sizes**, so the model is the real structure,
not an archetype. That is checked sheet by sheet, by eye, and recorded in `data/tier2/candidates.json` (`member_sizes`:
"table" = a member schedule or table of sections; "details" = sizes on detail drawings; "none").

Ranking among qualifying bridges:

1. **Data completeness**: member table > sizes on details; full elevation with panel dimensions; dimensioned deck and floor system.
2. **Solvable first**: pin- or rivet-connected trusses and two-hinge or fixed arches can be modelled as 2D/3D frames now.
   Suspension, cable-stayed and movable spans need cable or mechanism handling, so they come after the solver supports them.
3. **Still standing** (Extant, Bypassed, Relocated, Rehabilitated), and ideally still in the National Bridge Inventory, so the
   Tier 2 page links to the bridge's Tier 1 risk page.
4. **Variety** in the first 10: different truss and arch types, materials (wrought iron, early steel, timber, concrete) and
   regions, so each one teaches something different.
5. **Public interest**: a bridge people know or a type that matters in engineering history.

## What each Tier 2 bridge needs

| Item | Source | Stored as |
|---|---|---|
| Geometry: nodes, members, supports | Drawings, elevation and plan | `data/tier2/models/<haer>.json` |
| Member sections: area, I, S | Member table or details; built-up sections via `sectionproperties` | same file |
| Material | Drawing notes, date of construction; period allowable stresses (AASHTO Manual for Bridge Evaluation) [verify table] | same file |
| Provenance | Sheet number and drawing coordinates for every number read off a drawing | same file |
| Validation | Our solver vs PyNite, member by member, in CI | `tests/` |

## Status

- [x] v2 copy of v1 (`projects/bridgewatch-v2`, version 2.0.0.dev0)
- [ ] Scan all 2,829 Library of Congress records (running)
- [ ] Shortlist by drawings and sheet titles
- [ ] Check sheets by eye for member sizes; choose the first 10
- [ ] Model format, solver, validation, site page

## Scan result (2026-10-20)

- Standing bridges scanned: 1,585. With measured drawings: 295.
- With an explicit member-size table: 15. Those are the first pick, because member sizes plus panel geometry are all a 2D truss model needs.
- Top 10: `data/tier2/top10.json`. Each table sheet was checked by eye.
- Not yet checked: whether each one appears in the NBI (needed to link a model to the map).
- Next pool to reach 100: original construction drawings with sizes on detail sheets (Huey P. Long LA-17, IC Railroad trestle LA-49, Bay Bridge CA-32), and bridges with dimensioned connection details.

## Target set (2026-10-20): 20 bridges

- The 10 famous bridges are in `data/tier2/famous10.json`. Most are main-system models built from published engineering reports. Each entry is marked confirmed or partial.
- The 10 iron trusses are in `data/tier2/top10.json`. These are member-level models built from HAER member tables.

## Step 1 done (2026-10-21): first two models

- Solvers live in `src/bridgewatch/sim/`: `truss.py` (pin-jointed, with tension-only rods and eye-bars) and `suspension.py` (deflection theory).
- `bridgewatch sim` writes `reports/sim.md` and `data/tier2/models/*.json`.
- Kelley Crossing (TX-31): geometry from sheet 1, members from sheet 2. Plate thickness and the deck dead load are assumed.
- Golden Gate: inputs from the 1937 Chief Engineer's report. Validated against the report's own predicted deflections: 10.93 ft down vs 10.8 ft, 6.33 ft up vs 5.8 ft.
- Tests: `tests/test_sim.py`.

## On the web (2026-10-21)

- `web/bridges.html` ("Bridges under load"): Kelley Crossing and Golden Gate, solved live in the browser by `web/bridges/solver.js`,
  a port of the Python solvers. `tests/test_sim_js.py` checks the two agree (truss forces to 1e-6, suspension deflections to 1e-6).
- `bridgewatch sim` also writes the model inputs to `web/data/tier2/` for the page.
- Linked from the map page header and from the intro's last card.

## Models built (2026-10-21, later): 11 of 20

| Bridge | Kind | Source | Validation |
|---|---|---|---|
| Golden Gate | suspension | Strauss 1937; 1941 FWA report Table 4 | Table 4 within 5%; 1937 temperature cases 15% / 8% |
| George Washington (1931) | suspension, unstiffened | 1941 FWA report Table 4 | 5%, 11%, 25% (full-span case stiff: towers not modelled) |
| Tacoma Narrows (1940) | suspension, plate girders | 1941 FWA report (Caltech PDF) | Table 4 within 3% |
| Kelley Crossing | lenticular truss | HAER TX-31 | statics |
| Bridge L5245 | queen-post pony truss | HAER MN-133 sheet 7 (full member schedule) | statics |
| Walnut Street | Baltimore truss, Phoenix columns | HAER PA-412 sheets 2-4 | statics |
| Slate Run | quintangular lattice | HAER PA-460 sheets 2-3 | statics |
| Nicholson | lenticular, deck hung from lower chord | HAER PA-468 sheets 2, 4 | statics |
| Old Corinth Road | lenticular, half-through | HAER NY-292 sheets 1-3 (heights scaled) | statics; depth checked at section A-A |
| Whetstone Creek | bowstring | HAER OH-90 sheets 2-3 (heights scaled) | statics |
| Cooper's Tubular Arch | bowstring, Phoenix arch | HAER NY-291 sheets 1-2 (heights scaled) | statics |

- Suspension solver now includes suspended side spans: their cables straighten as the pull grows and let the tower tops lean in.
  Without it, full-span deflections were 35-40% low against Table 4; with it, within 5% for Golden Gate and Tacoma.
- Bay Bridge (Table 4 "Transbay") fails the antisymmetric check (model ~0 ft vs 7.5 ft up): back-to-back spans on a central
  anchorage need the HAER CA-32 drawings, not the summary table. Held back.
- Brooklyn: HAER NY-18 data gives cables and truss depths but no sag, dead load, stiffness or published deflections. Held back.
- Still to do: Bay Bridge (CA-32, 20 sheets), Huey P. Long (LA-17, 28 sheets: no stress sheet found yet), Arlington bascule
  (DC-7, 28 sheets), Eads (MO-12 data pages: 18" tubes, 520 ft centre arch; rib geometry needed), St. Johns (OR-40: 1,207 ft span,
  91 strands per cable; dead load and stiffness needed), Edmund Pettus (AL-209, 4 sheets), Old Army (WY-1: chord areas partial),
  Watkins Glen (NY-273: irregular panels, needs careful scaling), Brooklyn.
