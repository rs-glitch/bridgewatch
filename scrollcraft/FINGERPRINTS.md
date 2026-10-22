# Fingerprints

Every site you build with **scroll-craft** gets one row here, appended after it
ships. The registry exists so your next build can prove it is a different page
rather than a re-skin of one you already made.

This file is **yours**. It starts empty on purpose: the gate is about not
repeating *yourself*, so it has nothing to say until you have built something.

The rules and the gate live in the skill's
`references/uniqueness.md`. Short version:

**A new build must differ from EVERY row below on at least 4 of the 6
dimensions.** Four against each row individually, not four on average across the
table. If a planned build fails, change the plan. Never edit a row to make room
for it.

The six dimensions are: **grammar**, **nav treatment**, **hero device**,
**act-sequence shape**, **close pattern**, **signature move**.

Dimension 6 is free, because a signature move is unique by definition. So the
gate really asks for three more out of the remaining five, and a build that
changes only grammar and world will fail it.

---

## The registry

| Build | Grammar | Nav treatment | Hero device | Act-sequence shape | Close pattern | Signature move | World | Port |
|---|---|---|---|---|---|---|---|---|
| bridgewatch-intro (2026-10-20) | Continuous world (live WebGL map stage, not video legs) | Clickable waypoint route rail at the right, carrying the forecast year | Layered horizon: sky and sun, pitched data map, ink engineering drawing pinned to the bridge's real location, horizon haze, dust | 7 waypoints, 10.3vh: horizon > rise > regrade > hush > forecast (peak, 2.6vh) > proof > landing | Camera lands on one real place; CTA card sits beside the marked bridge and holds | Forecast horizon: scrolling turns 2025 to 2029 and at-risk bridges ignite as embers, riskiest band first | Haze pastel (apricot, rose, lilac), plum ink, one spice accent; Michroma + Geist | 8001 |

---

## What is taken

Add a bullet here whenever a build claims something a later build should avoid
reusing: a grammar, a nav treatment, a close pattern, a signature move, an
act-count-and-length band. The shared columns are what the next build inherits
as a constraint, so writing them down is the whole point.

- Continuous world over a live data map, with the camera driven by scroll and a padded high-pitch horizon hero.
- A waypoint route rail at the right edge that doubles as a readout (the year).
- Close as arrival at a real place with the CTA beside a marked point on the ground.
- Signature: time readout driving ignition of data points in risk order.
- 7 waypoints at 10.3vh.

---

## Appending a row

After shipping, add one line to the table and one bullet to **What is taken** if
the build claimed something new. Fill every column. Say what the build shares
with existing rows.

Rows are append-only. A build that has been superseded stays in the table,
because the space it occupies is still occupied.

---

## Worked example

The skill's author kept a registry of twelve builds across eight page grammars.
If you want to see what a filled-in table looks like, and which shapes tend to
collide, read `EXAMPLES.md` in the scroll-craft repository. Treat it as
illustration only: those rows are somebody else's builds and they do **not**
constrain yours.
