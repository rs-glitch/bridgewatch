"""Download the National Bridge Inventory: one comma-delimited, all-states zip per year from FHWA.

Every year 1992-2025 is published as `{year}del.zip` (FHWA re-exported the old years in the current column layout in 2016).
2025 is the last year in the 1995 Coding Guide format; from 2026 states report in the new SNBI format.
Files are fetched once, then verified against data/raw/manifest.json (size + SHA-256).
"""

import hashlib
import json
import time
import urllib.request
from datetime import UTC, datetime

from .paths import RAW

BASE = "https://www.fhwa.dot.gov/bridge/nbi/{year}del.zip"
YEARS = range(1992, 2026)
UA = {"User-Agent": "bridgewatch/0.1 (research; NBI bulk download)"}


def sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _fetch(url: str, dest, tries: int = 3) -> None:
    tmp = dest.with_suffix(".part")
    for attempt in range(1, tries + 1):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r, open(tmp, "wb") as f:
                while chunk := r.read(1 << 20):
                    f.write(chunk)
            tmp.replace(dest)
            return
        except OSError:
            if attempt == tries:
                raise
            time.sleep(5 * attempt)


def download(years=YEARS, verbose: bool = True) -> dict:
    RAW.mkdir(parents=True, exist_ok=True)
    mpath = RAW / "manifest.json"
    manifest = json.loads(mpath.read_text()) if mpath.exists() else {}
    for year in years:
        key, dest, url = str(year), RAW / f"{year}del.zip", BASE.format(year=year)
        known = manifest.get(key)
        if dest.exists() and known and dest.stat().st_size == known["bytes"] and sha256(dest) == known["sha256"]:
            if verbose:
                print(f"{year}: ok (cached)")
            continue
        if verbose:
            print(f"{year}: downloading {url}", flush=True)
        _fetch(url, dest)
        manifest[key] = {
            "url": url,
            "bytes": dest.stat().st_size,
            "sha256": sha256(dest),
            "retrieved_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        mpath.write_text(json.dumps(manifest, indent=1, sort_keys=True))
        time.sleep(1)  # be polite to the FHWA server
    return manifest
