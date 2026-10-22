#!/bin/sh
# Rebuild everything from the public FHWA files. About 2 GB of downloads; the model steps take roughly an hour on a laptop.
set -e
cd "$(dirname "$0")/.."
uv sync
uv run bridgewatch download      # 34 yearly NBI zips + manifest with SHA-256
uv run bridgewatch panel         # one parquet per year, typed
uv run bridgewatch link          # stable IDs across renumberings -> data/panel_keyed
uv run bridgewatch quality       # reports/data_quality.md
uv run bridgewatch labels        # future events per bridge-year
uv run bridgewatch features      # past-only features per bridge-year
uv run bridgewatch backtest      # Q1 + Q3: baselines vs model, time split + hold-out states
uv run bridgewatch screen        # Q4: inspection-interval screen backtest
uv run bridgewatch plan          # Q2: budget-planner backtest
uv run bridgewatch score         # 2025 risks for every bridge
uv run bridgewatch export        # static site data in web/data
echo "done: serve web/ with any static server, e.g. python -m http.server -d web"
