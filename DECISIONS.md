# Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-10-19 | Scope = Q1 (becomes Poor), Q2 (repair / replace / close budget), Q3 (posted / restricted / closed), Q4 (inspection-interval screen); all US bridges | Questions FHWA InfoBridge does not answer; national coverage |
| 2026-10-19 | Structural simulation for documented bridges is on hold | Only ~140–500 bridges have public measured drawings; repair/condition platform first |
| 2026-10-19 | Use each year's `{year}del.zip` (comma-delimited, all states) for 1992–2025 | Same 119 leading columns in every year; one parser |
| 2026-10-19 | Python `csv` reader instead of a strict CSV parser | Free-text fields contain stray apostrophes; 164 malformed rows in 34 years are dropped and counted |
| 2026-10-19 | Link IDs across renumberings (padding, description, location ≤ 50 m), never to a structure built in the transition year | 225k of 432k ID disappearances were mass renumberings; replacements must not look like repairs |
| 2026-10-19 | Culverts included; condition = lowest of deck, superstructure, substructure, culvert | FHWA Good/Fair/Poor definition; culverts are 24% of bridges |
| 2026-10-19 | Censor, do not guess: a bridge that leaves the inventory before the horizon without the event has no label | Removal often follows replacement; treating it as "no event" would bias risk down |
| 2026-10-19 | Baselines: average rate, rating lookup ("stays the same"), time-in-condition, Markov (per component, material x age band) | The methods agencies and FHWA already use |
| 2026-10-19 | Hold out IA, TX, PA, CA, GA from all training | Transfer to an agency the model has not seen |
| 2026-10-19 | scikit-learn HistGradientBoosting with monotone constraints on ratings | No extra native dependency; prevents "worse rating, lower risk" artefacts |
| 2026-10-19 | Costs: FHWA 2025 replacement unit costs; rehab = 68% (FHWA's ratio); detour = federal BCA values via Caltrans comparison | Primary or near-primary public sources; USDOT PDF blocked scripted download (verify) |
| 2026-10-19 | Static website (MapLibre + deck.gl, data files only) | Same hosting model as the TradeRoute demo; no server |
| 2026-10-19 | Planner funds every bridge that still fits (skip, not stop); culverts with width 0 costed at length x 7.3 m (min 20 m²) | First version stopped at the first unaffordable bridge and costed zero-width culverts at $1k, inflating value per $ |
| 2026-10-19 | NBI detour >= 150 km (199/999 and the converted "99 miles" code) = no detour, costed as 100 km | ~35k bridges with no detour route were being treated as costless to close |
| 2026-10-19 | Q2 control strategy: value per $ with time-in-condition risk | Separates the model's contribution from the consequence weighting |
| 2026-10-19 | MapLibre pinned to 5.24.0 | 6.x ships ES modules only, no browser script build |
| 2026-10-19 | web/data/ is generated, not committed | ~240 MB on disk; rebuilt by `bridgewatch export` |
