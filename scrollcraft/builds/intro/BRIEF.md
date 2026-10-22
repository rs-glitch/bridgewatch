# BRIEF: BridgeWatch intro

**Self-authored under explicit creative delegation.** The user answered topics 1 to 3 and wrote, for the rest,
"rest - use your judgement". Their words are quoted verbatim; everything marked *Authored* is my decision.

## The eight topics

1. **Vibe.** User: "fluid, cinematic, patel. refer to: Dune movies by villenue, etc." (read as *pastel*; Denis Villeneuve's
   Dune films). *Authored reading of the reference:* vast scale with a tiny human trace in it; haze that eats the horizon;
   slow, heavy camera moves; monumental geometry; long silences; a dusty apricot, rose and lilac palette rather than
   saturated orange.
2. **Scroll journey.** User: "the map". *Authored:* the map is the world. The page is one continuous flight over the real
   map of every US bridge, from a hazy horizon, up over the whole country, into the forecast, and down onto one bridge.
3. **Energy.** User: "it should feel calm and engaging". *Authored:* calm everywhere, with one quiet held beat before the
   peak so the peak lands without getting loud.
4. **Feeling and the one moment.** *Authored*, see the curve and the peak below.
5. **The thing no other site does.** *Authored:* you scroll forward through time over a real country, and the bridges
   the model expects to fail in the next four years light up in the order of their risk.
6. **Range.** *Authored:* premium-minimal leaning editorial: wide tracked display type, a lot of air, real figures in
   small type. Not cream-and-brass: the palette is haze pastel (apricot, rose, lilac) with plum ink.
7. **One world or scenes.** *Authored:* one unbroken world (the map never cuts).
8. **Assets.** *Authored:* real assets only, no generated imagery, no spend. The 1931 "as constructed" elevation of the
   Huey P. Long Bridge (HAER LA-17, sheet 12, Library of Congress, public domain); the FHWA National Bridge Inventory
   points (623,611 bridges, 2025) and BridgeWatch's own scores and backtest results; Census state outlines.

## Subject, belief, action

- **What it is, for whom:** BridgeWatch, a free public tool that forecasts which US bridges will become Poor or get a
  weight limit, for agencies, journalists and anyone curious about the bridges they cross.
- **The belief:** the country's bridges can be read as one landscape, and the forecast is honest because it was tested on
  what really happened.
- **The one action:** **Open the map** (same label everywhere).

## Journey (beats)

1. Arrival: a horizon in haze, a 1931 bridge drawing standing on it.
2. Scale: the ground resolves into 623,611 grains, each one a bridge.
3. State: the grains take colour; 41,651 are Poor today.
4. Question: the colour drains back to sand. "Which ones are next?"
5. Forecast (peak): time moves from 2025 to 2029 and the bridges at risk ignite.
6. Proof: the forecast was tested on years that already happened.
7. Landing: the camera comes down on the Huey P. Long Bridge; the map opens from there.

## Feeling curve

| # | Feeling | What on screen causes it |
|---|---|---|
| 1 | Stillness | Low sun in apricot haze; the ink truss drawing on the horizon; nothing moves but drifting dust |
| 2 | Vastness | The camera rises and tilts down; the horizon drops away and the whole continent appears as fine sand |
| 3 | Recognition | The sand takes colour: sage, ochre, plum. The plum is where the Poor bridges are, and you can see your region |
| 4 | Hush (authored silence) | Colour drains back to sand, the camera holds still, one short line asks the question |
| 5 | Wonder with a little foreboding | A year readout runs 2025 to 2029 under your hand; ember points rise off the sand, riskiest first |
| 6 | Trust | Small, calm type with real backtest numbers; the embers settle |
| 7 | Arrival | The camera sinks onto New Orleans; the drawing from the first screen is this bridge; "Open the map" sits beside it and holds |

**The peak (act 5):** "you scroll and the years tick forward, and the bridges that are about to fail start glowing like
embers across the whole country."

**Tell-someone sentence:** "It's the site where you scroll four years into the future over every bridge in America and
watch the ones at risk light up."

**Authored silence:** act 4 is deliberately still: the camera does not move and only one line of copy appears. The
verification pass should read it as intended quiet, not dead scroll.

## Grammar

**Continuous world (uniqueness.md §2.4).** The brief is literally a journey over a real geography ("the map"), and "one
unbroken world" was chosen. Why the others lost: filmic one-shot would cut the map into acts with seams; chaptered
editorial and typographic poster drop the map as the world; live surface would turn the intro into the tool itself
(the tool is one click away); gallery, split stage and cutlist do not fit one calm journey.

**Deviation, stated plainly:** worldflight mode expects pre-rendered video legs. This world is a live WebGL render of real
data, so it is one fixed canvas stage driven by page scroll, built in page code, with the same contract: one fixed stage,
nothing scrolling over it, copy in a fixed layer at waypoints, a clickable waypoint rail. Empty flow sections are used
only as scroll markers, and the stage publishes `data-sc-verify-state` so the harness can check it (verify.md).

## Layer contract (hero)

| Plane | Asset and depth | Movement | Rule |
|---|---|---|---|
| Far | Sky gradient and a low sun disc (CSS) | Slowest: sinks 4% as the camera rises | Never crosses the headline |
| Mid | The land and 623,611 bridge points (deck.gl, pitched 62°) | The camera itself | Horizon sits below the headline |
| Focal | Huey P. Long elevation, ink on transparent (HAER LA-17 sheet 12) | Sits on the horizon line, recedes and fades as the camera rises | Its piers stand on the horizon; it never floats |
| Atmosphere | Horizon haze band (CSS gradient), above the land, below the type | Thins as the camera rises | Separation, never a full-frame wash |
| Near | Dust motes (canvas 2D) | Fastest, slight drift with scroll and pointer | Off under reduced motion |
| Type | Semantic HTML | Fixed layer, translate within ±2vh | Headline and CTA readable on the first screen |

## Score (waypoints on the scroll track)

| Waypoint | Span (vh) | Device | Why |
|---|---|---|---|
| Horizon | 1.4 | Layered hero, greet copy | Establishing position inside the world |
| Grains | 1.4 | Camera rise and tilt (stage), count of real bridges | Scale needs the camera to move |
| Condition | 1.3 | Regrade of the points (stage), fixed copy | A state change, so the colour itself is the device |
| Hush | 0.8 | Held camera, one line | Silence before the peak |
| Forecast | 2.6 | Signature move: year readout and ignition | The peak gets the most room |
| Proof | 1.2 | Calm type, real figures | Information, compressed |
| Landing | 1.6 + hold | Camera descent to one place; CTA beside the bridge | The close is an arrival in the same world |

Total about 10.3 viewport-heights plus the final hold. Seven waypoints. Outside the 13.6 to 13.8vh band.

## Signature move

**The forecast horizon.** In act 5 the rail's year readout turns from 2025 to 2029 as you scroll, and every bridge the
model scores above 10% risk of becoming Poor rises off the sand as an ember, highest-risk band first, at the moment the
readout passes it. Real data only: the counts shown are the real numbers of bridges in each risk band, and the expected
total (about 17,000) is the sum of the model's probabilities.

## Real numbers used (source)

- 623,611 bridges; 41,651 Poor; 68,068 posted or closed; about 17,005 expected to become Poor by 2029
  (`web/data/summary.json`, from `bridgewatch score`).
- Top-1% hit rate, becoming Poor within 4 years, 2021 test year: 30.2% vs 24.3% for the best existing method
  (`reports/backtest.json`).
- Huey P. Long Bridge: NBI 22-022600060100001, US 90 over the Mississippi, built 1936, rated Fair.
