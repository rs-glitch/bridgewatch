import argparse


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="bridgewatch")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("download", help="fetch NBI yearly zips (1992-2025) into data/raw")
    d.add_argument("--years", help="e.g. 2015-2025 or 2019,2025 (default: all)")
    b = sub.add_parser("panel", help="parse data/raw zips into data/panel/nbi_{year}.parquet")
    b.add_argument("--years", help="e.g. 2015-2025 (default: every downloaded year)")
    sub.add_parser("link", help="link IDs across renumberings and write data/panel_keyed")
    sub.add_parser("backtest", help="run baselines (and models) over the time-split folds; writes reports/backtest.md")
    sub.add_parser("screen", help="Q4 inspection-interval backtest; writes reports/screen.json")
    sub.add_parser("plan", help="Q2 budget-planner backtest; writes reports/plan.json")
    sub.add_parser("score", help="score the latest year for the website; writes data/scores_2025.parquet")
    sub.add_parser("export", help="write the static website data into web/data")
    sub.add_parser("quality", help="write reports/data_quality.md from the panel")
    sub.add_parser("labels", help="write data/labels.parquet (future events per bridge-year)")
    sub.add_parser("features", help="write data/features.parquet (past-only features per bridge-year)")
    sub.add_parser("sim", help="run the Tier 2 bridge models; writes reports/sim.md and data/tier2/models")
    args = ap.parse_args(argv)
    if args.cmd == "download":
        from .download import YEARS, download

        download(_years(args.years) if args.years else YEARS)
    elif args.cmd == "panel":
        from .panel import build
        from .paths import RAW

        years = _years(args.years) if args.years else sorted(int(p.name[:4]) for p in RAW.glob("*del.zip"))
        build(years)
    elif args.cmd == "link":
        from .linking import apply_keys, build_links

        print(build_links())
        print(f"keyed panel: {apply_keys()} years")
    elif args.cmd == "backtest":
        from .evaluate import run

        run()
    elif args.cmd == "screen":
        from .screen import run_screen

        run_screen()
    elif args.cmd == "plan":
        from .planner import run_plan

        run_plan()
    elif args.cmd == "score":
        from .score import score

        print(f"scored {score().height:,} bridges")
    elif args.cmd == "export":
        from .export import export

        print(export())
    elif args.cmd == "sim":
        from .sim.report import run as run_sim

        print(run_sim())
    elif args.cmd == "quality":
        from .quality import build_report

        build_report()
        print("wrote reports/data_quality.md")
    elif args.cmd == "labels":
        from .labels import build_labels

        print(f"labels: {build_labels():,} bridge-years")
    elif args.cmd == "features":
        from .features import build_features

        print(f"features: {build_features():,} bridge-years")


def _years(spec: str):
    out = []
    for part in spec.split(","):
        a, _, b = part.partition("-")
        out += range(int(a), int(b or a) + 1)
    return out
