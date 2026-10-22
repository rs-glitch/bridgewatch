"""Find HAER-documented bridges with measured drawings (candidates for structural simulation).

    uv run python scripts/haer_scan.py list    # Wikipedia "Bridges documented by HAER in <state>" tables -> data/tier2/haer_list.json
    uv run python scripts/haer_scan.py scan [--standing] [--parallel]
        # Library of Congress record per bridge -> data/tier2/haer_scan.jsonl (resumable)
        # --standing skips replaced/demolished/destroyed/ruined bridges; --parallel uses 3 workers

The scan is polite (each worker waits GAP s between requests; a 429 pauses all workers for 65 minutes)
and can be stopped and restarted at any time.
"""

import gzip
import json
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "tier2"
LIST, SCAN = OUT / "haer_list.json", OUT / "haer_scan.jsonl"
UA = {"User-Agent": "bridgewatch-research/2.0 (HAER drawings survey)", "Accept-Encoding": "gzip"}
GONE = {"Replaced", "Demolished", "Destroyed"}
GAP = 3  # seconds each worker waits between requests


def get(url):
    # gzip: loc.gov responses often arrive truncated when sent uncompressed
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90) as r:
        body = r.read()
        return (gzip.decompress(body) if r.headers.get("Content-Encoding") == "gzip" else body).decode()


def clean(s):
    s = re.sub(r"<ref.*?(</ref>|/>)", "", s)
    return re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", s).strip()


def build_list():
    q = json.loads(get("https://en.wikipedia.org/w/api.php?action=query&list=search&srlimit=100&format=json&srsearch="
                       + urllib.parse.quote('intitle:"bridges documented by the Historic American Engineering Record"')))
    rows = []
    for t in [x["title"] for x in q["query"]["search"]]:
        raw = get("https://en.wikipedia.org/w/index.php?action=raw&title=" + urllib.parse.quote(t.replace(" ", "_")))
        for block in raw.split("\n|-")[1:]:
            cells = [c.strip() for c in re.split(r"\n\|(?!\})", "\n" + block.split("\n|}")[0]) if c.strip()]
            m = re.search(r"\{\{HAER\|([^|}]+)\|([^|}]+)", block)
            if m and len(cells) >= 4:
                rows.append({"page": t.split(" in ")[-1], "haer": m.group(1), "loc": m.group(2), "name": clean(cells[1]),
                             "status": clean(cells[2]), "type": clean(cells[3])})
        time.sleep(0.3)
    uniq = list({r["loc"]: r for r in rows}.values())
    OUT.mkdir(parents=True, exist_ok=True)
    LIST.write_text(json.dumps(uniq, indent=0))
    print(f"{len(uniq)} bridges -> {LIST}")


def count(medium, label):
    for m in medium or []:
        if m.lower().startswith(label):
            n = re.search(r"\d+", m)
            return int(n.group()) if n else 0
    return 0


def record(row):
    d = json.loads(get(f"https://www.loc.gov/item/{row['loc']}/?fo=json"))
    it = d.get("item", {})
    sheets = []
    for res in d.get("resources", []):
        if "drawing" not in (res.get("caption") or "").lower():
            continue
        for f in res.get("files", []):
            for x in f if isinstance(f, list) else [f]:
                if isinstance(x, dict) and x.get("use") == "caption" and x.get("title"):
                    sheets.append(x["title"].split(" - ")[0].strip())
    notes = it.get("notes") or []
    return {**row, "title": it.get("title"), "drawings": count(it.get("medium"), "measured drawing"),
            "photos": count(it.get("medium"), "photo("), "data_pages": count(it.get("medium"), "data page"),
            "dates": next((n.split(":", 1)[1].strip() for n in notes if n.startswith("Building/structure dates")), None),
            "significance": next((n.split(":", 1)[1].strip()[:400] for n in notes if n.startswith("Significance")), None),
            "sheets": sheets}


def fetch_one(row, pause):
    """One record with retries. `pause` is shared: a 429 makes every worker wait."""
    rec = {**row, "error": "not tried"}
    for _ in range(6):
        wait = pause["until"] - time.time()
        if wait > 0:
            time.sleep(wait)
        try:
            return record(row)
        except urllib.error.HTTPError as e:
            rec = {**row, "error": e.code}
            if e.code == 404:
                return rec
            print(f"{row['loc']}: HTTP {e.code}, retrying", flush=True)
            if e.code == 429:  # loc.gov blocks for an hour after its limit is hit; retrying sooner extends the block
                pause["until"] = time.time() + 65 * 60
            time.sleep(10)
        except Exception as e:  # truncated or timed-out response: retry
            rec = {**row, "error": str(e)[:100]}
            time.sleep(10)
    return rec


def scan(standing_only=False, workers=1):
    rows = json.loads(LIST.read_text())
    done = set()
    if SCAN.exists():
        recs = [json.loads(line) for line in SCAN.read_text().splitlines() if line.strip()]
        done = {r["loc"] for r in recs if r.get("error") in (None, 404)}  # failed fetches are retried on the next run
    todo = [r for r in rows if r["loc"] not in done and not (standing_only and r["status"] in GONE | {"Ruin"})]
    todo.sort(key=lambda r: (r["status"] in GONE, r["status"] != "Extant"))
    print(f"{len(done)} done, {len(todo)} to go with {workers} worker(s)", flush=True)
    pause, lock, n = {"until": 0.0}, threading.Lock(), [0]

    def work(row):
        rec = fetch_one(row, pause)
        with lock:
            out.write(json.dumps(rec) + "\n")
            out.flush()
            n[0] += 1
            if n[0] % 100 == 0:
                print(f"{len(done) + n[0]} scanned", flush=True)
        time.sleep(GAP)

    with SCAN.open("a") as out, ThreadPoolExecutor(workers) as pool:
        list(pool.map(work, todo))
    print("scan complete", flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "list":
        build_list()
    else:
        scan(standing_only="--standing" in sys.argv, workers=3 if "--parallel" in sys.argv else 1)
