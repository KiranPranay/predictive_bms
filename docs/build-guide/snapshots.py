#!/usr/bin/env python3
"""Runs every guided demonstration in a real browser and saves the pictures the build guide
uses, with the results, in docs/build-guide/snapshots/.

    python3 docs/build-guide/snapshots.py [--chrome /usr/bin/google-chrome]

Needs Playwright (pip install playwright) and an installed Chrome or Chromium; it does not
download a browser. Takes about 8 minutes: the demonstrations run in simulated time.
"""

import argparse
import json
import pathlib
import shutil
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = HERE / "snapshots"
DEMOS = ["normal", "heat", "defect", "short", "runaway", "sensor", "hot", "overcharge", "crash"]
# (demonstration, part of the page, file)
KEEP = [("normal", ".charts", "normal-charts.png"), ("heat", "#diagram", "heat-diagram.png"),
        ("defect", "#demo-card", "defect-story.png"), ("defect", "#compare-card", "defect-compare.png"),
        ("defect", ".charts", "defect-charts.png"), ("short", "#cells", "short-cells.png"),
        ("runaway", "#compare-card", "runaway-compare.png")]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--chrome", default=shutil.which("google-chrome") or shutil.which("chromium"))
    ap.add_argument("--port", type=int, default=8767)
    args = ap.parse_args()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("Playwright is needed: pip install playwright")
    OUT.mkdir(exist_ok=True)
    srv = subprocess.Popen([sys.executable, str(ROOT / "tools" / "sim_server.py"), "--port", str(args.port),
                            "--speed", "10"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    errors, results = [], {}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=args.chrome, args=["--no-sandbox"])
            page = browser.new_page(viewport={"width": 1280, "height": 900}, device_scale_factor=2)
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(f"http://127.0.0.1:{args.port}/?theme=light")
            page.wait_for_selector("#demo-card:not([hidden])", timeout=15000)
            page.wait_for_function("document.querySelector('#verify-status').textContent.includes('pass')",
                                   timeout=120000)
            results["verification"] = page.inner_text("#verify-status")
            page.click("#verify tr[data-k='4']")
            page.locator("#verify-card").screenshot(path=str(OUT / "verification.png"))
            for d in DEMOS:
                t0 = time.time()
                page.click(f".demo-btn[data-id='{d}']")
                page.wait_for_function("document.querySelector('#story-now').textContent.includes('Result')",
                                       timeout=300000)
                time.sleep(1.5)
                results[d] = {"seconds": round(time.time() - t0), "result": page.inner_text("#story-now"),
                              "compare": page.inner_text("#cmp-head")}
                for demo, sel, name in KEEP:
                    if demo == d:
                        page.locator(sel).screenshot(path=str(OUT / name))
                print(f"{d}: {results[d]['seconds']} s", flush=True)
            browser.close()
    finally:
        srv.terminate()
    (OUT / "results.json").write_text(json.dumps({"errors": errors, "results": results}, indent=2))
    print(f"browser errors: {len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
