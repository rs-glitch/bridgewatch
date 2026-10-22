from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RAW = DATA / "raw"
PANEL = DATA / "panel"  # one parquet per year, original NBI IDs
KEYED = DATA / "panel_keyed"  # same, with bridge_id replaced by the stable key from linking (original kept as nbi_id)
REPORTS = ROOT / "reports"
