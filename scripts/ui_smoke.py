"""Open the static site in headless Chromium and use it like a visitor. Fails on any local error.

    uv run python scripts/ui_smoke.py [--shots DIR]

Needs `bridgewatch export` first and Playwright's Chromium (`uv run playwright install chromium`).
The basemap comes from tiles.openfreemap.org; failures on that host are reported but do not fail the run.
"""

import argparse
import functools
import http.server
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

WEB = Path(__file__).resolve().parents[1] / "web"


def serve():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(WEB))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}/"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots")
    args = ap.parse_args()
    shots = Path(args.shots) if args.shots else None
    if shots:
        shots.mkdir(parents=True, exist_ok=True)
    httpd, url = serve()
    problems, external = [], []
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        local = lambda u: u.startswith(url)  # noqa: E731
        page.on("pageerror", lambda e: problems.append(f"page error: {e}"))
        page.on("console", lambda m: m.type == "error" and (external if "openfreemap" in m.text else problems).append(f"console: {m.text}"))
        page.on("response", lambda r: r.status >= 400 and (problems if local(r.url) else external).append(f"HTTP {r.status} {r.url}"))
        page.on("requestfailed", lambda r: (problems if local(r.url) else external).append(f"failed {r.url}"))

        def shot(name):
            if shots:
                page.screenshot(path=str(shots / f"{name}.png"), timeout=180000)  # software WebGL draws 600k points slowly

        page.goto(url + "map.html", wait_until="load")
        page.wait_for_function("document.querySelectorAll('#legend div').length >= 3", timeout=60000)
        page.wait_for_selector("#map canvas", timeout=60000)
        page.wait_for_timeout(4000)
        stats = page.text_content("#mapStats") or ""
        if "bridges" not in stats:
            problems.append(f"map stats missing: {stats!r}")
        shot("map")
        for mode in ("q1", "q3", "flag", "cond"):
            page.select_option("#colorBy", mode)
            page.wait_for_timeout(600)
        page.select_option("#colorBy", "q1")
        page.wait_for_timeout(1500)
        shot("map_q1")

        page.click('[data-tab="list"]')
        page.wait_for_selector("#listTable tbody tr", timeout=30000)
        if page.locator("#listTable tbody tr").count() < 10:
            problems.append("risk list has fewer than 10 rows for Iowa")
        shot("list")
        page.click("#listTable tbody tr >> nth=0")
        page.wait_for_selector("#detail:not([hidden]) svg", timeout=30000)
        page.wait_for_timeout(2500)
        detail = page.text_content("#detail") or ""
        for must in ("Becomes Poor within 4 yr", "Ratings 1992–2025", "not an engineering assessment"):
            if must not in detail:
                problems.append(f"detail panel missing {must!r}")
        shot("detail")

        page.click('[data-tab="plan"]')
        page.wait_for_selector("#planSummary .card", timeout=30000)
        page.eval_on_selector("#planBudget", "el => { el.value = 70; el.dispatchEvent(new Event('input')); }")
        page.wait_for_timeout(800)
        if "bridges treated" not in (page.text_content("#planSummary") or ""):
            problems.append("planner summary missing")
        if page.locator("#planBacktest table tbody tr").count() < 4:
            problems.append("planner backtest table missing")
        shot("plan")

        page.click('[data-tab="interval"]')
        page.wait_for_selector("#intSummary .card", timeout=30000)
        if page.locator("#intBacktest table tbody tr").count() < 4:
            problems.append("interval backtest table missing")
        shot("interval")

        page.click('[data-tab="right"]')
        page.wait_for_selector("#rightTables table", timeout=30000)
        if page.locator("#rightReliability circle").count() < 5:
            problems.append("calibration chart missing")
        shot("right")
        page.click('[data-tab="method"]')

        page.set_viewport_size({"width": 400, "height": 860})
        for tab in ("map", "list", "plan", "interval", "right", "method"):
            page.click(f'[data-tab="{tab}"]')
            page.wait_for_timeout(400)
            sw, w = page.evaluate("[document.documentElement.scrollWidth, innerWidth]")
            if sw > w:
                problems.append(f"{tab}: scrolls sideways at phone width ({sw}px > {w}px)")
        shot("phone")
        browser.close()
    httpd.shutdown()
    if external:
        print(f"note: {len(external)} external basemap request issue(s), e.g. {external[0]}")
    if problems:
        raise SystemExit("UI smoke: " + str(len(problems)) + " problem(s)\n  " + "\n  ".join(problems))
    print("UI smoke: map, risk list, detail panel, planner, interval screen and backtest pages work;"
          " no local errors; no sideways scroll at 400 px")


if __name__ == "__main__":
    main()
