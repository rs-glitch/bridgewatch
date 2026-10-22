"""Regenerate the results blocks in README.md and MODEL_CARD.md from reports/*.json (numbers are never typed by hand).

Blocks are delimited by <!-- results:NAME --> ... <!-- /results:NAME -->.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
PLAN_NAMES = {"worst_first": "Worst condition first", "traffic_first": "Highest traffic first", "risk_first": "Highest risk first",
              "value_per_dollar": "BridgeWatch (value per $)", "value_per_dollar_baseline_risk": "Value per $ with baseline risk"}
NAMES = {"gbm": "BridgeWatch model", "markov": "Markov chain", "time_in_cond": "Time in condition",
         "rating_lookup": "Rating stays the same", "climatology": "Average rate"}


def pct(x, d=1):
    return "–" if x is None else f"{100 * x:.{d}f}%"


def money(x):
    return f"${x / 1e9:.1f} B" if x >= 1e9 else f"${x / 1e6:.0f} M"


def backtest_rows(bt, target, h, year):
    out = {}
    for split in ("seen_states", "holdout_states"):
        rs = [r for r in bt if (r["target"], r["h"], r["test_year"], r["split"]) == (target, h, year, split)]
        g = next(r for r in rs if r["method"] == "gbm")
        base = [r for r in rs if r["method"] not in ("gbm", "climatology")]
        best = max(base, key=lambda r: r["precision_top1pct"])
        out[split] = (g, best)
    return out


def headline(bt, screen, plan) -> str:
    lines = ["| Question (time-split backtest) | Best existing method | BridgeWatch |", "|---|---|---|"]
    for target, label in (("poor", "Q1 · becomes Poor within 4 years: hit rate of the top-1% list"),
                          ("restricted", "Q3 · weight limit or closure within 4 years: hit rate of the top-1% list")):
        g, b = backtest_rows(bt, target, 4, 2021)["seen_states"]
        lines.append(f"| {label} | {pct(b['precision_top1pct'])} ({NAMES[b['method']].lower()}) | **{pct(g['precision_top1pct'])}** |")
    if screen:
        s = screen[-1]
        lines.append(f"| Q4 · 48-month interval misses, same number of bridges ({s['base_year']}) | {pct(s['method1']['miss_rate'], 2)} "
                     f"(Method 1 criteria) | **{pct(s['model_same_count']['miss_rate'], 2)}** |")
    if plan:
        b = sorted({r["budget"] for r in plan["results"]})[1]
        rs = [r for r in plan["results"] if r["budget"] == b]
        ours = next(r for r in rs if r["strategy"] == "value_per_dollar")
        alt = max((r for r in rs if r["strategy"] != "value_per_dollar"), key=lambda r: r["exposure_covered"])
        lines.append(f"| Q2 · detour exposure of real {plan['decision_year'] + 1}–{plan['decision_year'] + plan['h']} closures/postings "
                     f"inside a {money(b)} programme | {pct(alt['exposure_covered'] / plan['event_exposure'])} "
                     f"({PLAN_NAMES[alt['strategy']].lower()}) | **{pct(ours['exposure_covered'] / plan['event_exposure'])}** |")
    return "\n".join(lines)


def full_backtest(bt) -> str:
    lines = ["| Question | Horizon | Test year | States | Events | Best baseline, top 1% | Model, top 1% "
             "| Brier skill (best baseline → model) |",
             "|---|---|---|---|---|---|---|---|"]
    keys = sorted({(r["target"], r["h"], r["test_year"]) for r in bt})
    for target, h, year in keys:
        for split, (g, b) in backtest_rows(bt, target, h, year).items():
            bb = max((r for r in bt if (r["target"], r["h"], r["test_year"], r["split"]) == (target, h, year, split)
                      and r["method"] != "gbm"), key=lambda r: r["brier_skill"])
            lines.append(f"| {'Poor' if target == 'poor' else 'Limit/closure'} | {h} yr | {year} | {split.split('_')[0]} | "
                         f"{pct(g['rate'], 2)} | {pct(b['precision_top1pct'])} ({NAMES[b['method']]}) | {pct(g['precision_top1pct'])} | "
                         f"{bb['brier_skill']:+.3f} → {g['brier_skill']:+.3f} |")
    return "\n".join(lines)


def screen_table(screen) -> str:
    lines = ["| Base year | On 24 months | Miss rate, all | Method 1: bridges / miss | Model, same count: miss "
             "| Method 1 minus riskiest 10%: miss |",
             "|---|---|---|---|---|---|"]
    for s in screen:
        lines.append(f"| {s['base_year']} | {s['on_24mo']:,} | {pct(s['miss_rate_all_24mo'], 2)} | "
                     f"{s['method1']['bridges']:,} / {pct(s['method1']['miss_rate'], 2)} | "
                     f"{pct(s['model_same_count']['miss_rate'], 2)} | {pct(s['hybrid']['miss_rate'], 2)} |")
    return "\n".join(lines)


def plan_table(plan) -> str:
    names = {"worst_first": "Worst condition first", "traffic_first": "Highest traffic first",
             "risk_first": "Highest risk first", "value_per_dollar_baseline_risk": "Value per $, baseline risk (control)",
             "value_per_dollar": "BridgeWatch (value per $)"}
    lines = [f"Decision year {plan['decision_year']}, {plan['bridges']:,} open bridges; {plan['events']:,} were posted, restricted or "
             f"closed in {plan['decision_year'] + 1}–{plan['decision_year'] + plan['h']}.", "",
             "| Budget | Strategy | Bridges treated | Events inside treated set | Share of event detour exposure |",
             "|---|---|---|---|---|"]
    for r in plan["results"]:
        lines.append(f"| {money(r['budget'])} | {names[r['strategy']]} | {r['treated']:,} | {r['events_covered']:,} | "
                     f"{pct(r['exposure_covered'] / plan['event_exposure'])} |")
    return "\n".join(lines)


def inject(path: Path, blocks: dict):
    text = path.read_text()
    for name, body in blocks.items():
        text = re.sub(rf"(<!-- results:{name} -->).*?(<!-- /results:{name} -->)",
                      lambda m, b=body: f"{m.group(1)}\n{b}\n{m.group(2)}", text, flags=re.S)
    path.write_text(text)


def main():
    bt = json.loads((REPORTS / "backtest.json").read_text())
    screen = json.loads((REPORTS / "screen.json").read_text()) if (REPORTS / "screen.json").exists() else None
    plan = json.loads((REPORTS / "plan.json").read_text()) if (REPORTS / "plan.json").exists() else None
    blocks = {"headline": headline(bt, screen, plan), "backtest": full_backtest(bt)}
    if screen:
        blocks["screen"] = screen_table(screen)
    if plan:
        blocks["plan"] = plan_table(plan)
    for f in ("README.md", "MODEL_CARD.md"):
        if (ROOT / f).exists():
            inject(ROOT / f, blocks)


if __name__ == "__main__":
    main()
