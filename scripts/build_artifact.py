"""Build the hosted version of the site: one page with its stylesheets inlined, plus the publish file list.

    uv run python scripts/build_artifact.py

The host wraps the page in its own <html>/<head>/<body> and only allows stylesheets inline, so this writes
dist/artifact/index.html (title, inline CSS, body) and dist/artifact/files.json (published path -> source file, in batches
under 60 MB, since one publish takes at most 64 MB).
"""

import base64
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB, OUT = ROOT / "web", ROOT / "dist" / "artifact"
BATCH = 60 * 2**20


def main():
    html = (WEB / "index.html").read_text()
    title = re.search(r"<title>.*?</title>", html, re.S).group(0)
    body = re.search(r"<body>(.*)</body>", html, re.S).group(1)
    css = "\n".join((WEB / p).read_text() for p in ("basemap/maplibre-gl.css", "styles.css"))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "index.html").write_text(f"{title}\n<style>\n{css}\n</style>\n{body.strip()}\n")
    # the host serves no binary types, so the point file goes as base64 text (app.js falls back to it)
    b64 = OUT / "data" / "points.b64.txt"
    b64.parent.mkdir(exist_ok=True)
    b64.write_text(base64.b64encode((WEB / "data" / "points.bin").read_bytes()).decode())
    files = [p for p in sorted(WEB.rglob("*")) if p.is_file() and p.name not in ("index.html", ".DS_Store")
             and p.suffix not in (".css", ".bin")] + [b64]
    batches, cur, size = [], {}, 0
    for p in sorted(files, key=lambda p: p.stat().st_size):
        if size + p.stat().st_size > BATCH and cur:
            batches.append(cur)
            cur, size = {}, 0
        cur[p.relative_to(OUT if OUT in p.parents else WEB).as_posix()] = str(p.relative_to(ROOT))
        size += p.stat().st_size
    batches.append(cur)
    (OUT / "files.json").write_text(json.dumps(batches, indent=1))
    total = sum(p.stat().st_size for p in files)
    print(f"{OUT / 'index.html'}: {len(files)} files, {total / 2**20:.0f} MB in {len(batches)} batches")


if __name__ == "__main__":
    main()
