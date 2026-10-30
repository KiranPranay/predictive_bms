"""Starts the Windows package's demo as a user does (the .bat file) and checks it works.

    python .github/scripts/demo_check.py dist/PredictiveBMS

Two runs: one with port 8080 free, and one with port 8080 taken by another program, where the
demo must move to 8081. Each run checks the dashboard page, the live state of the simulated pack,
a command, and the verification of every scenario. Windows only.
"""

import json
import pathlib
import socket
import subprocess
import sys
import time
import urllib.request


def get(url, timeout=3):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read()


def wait_for_state(base, seconds=60):
    end = time.time() + seconds
    while time.time() < end:
        try:
            state = json.loads(get(base + "/api/state"))
            if len(state.get("cells", [])) == 4:
                return state
        except (OSError, ValueError):
            pass
        time.sleep(0.5)
    raise SystemExit(f"no state from {base} within {seconds} s")


def run(pkg, port, check_scenarios):
    bat = pkg / "1 Demo - double-click.bat"
    log = pkg.parent / f"demo-{port}.log"
    with open(log, "w", encoding="utf-8", errors="replace") as out:
        proc = subprocess.Popen(["cmd", "/c", str(bat)], stdout=out, stderr=subprocess.STDOUT,
                                stdin=subprocess.PIPE, cwd=str(pkg.parent))
    base = f"http://127.0.0.1:{port}"
    try:
        state = wait_for_state(base)
        page = get(base + "/").decode("utf-8")
        assert "Predictive BMS" in page, "the dashboard page did not load"
        assert "sim" in state and "fixed" in state["sim"], "no simulator data in the state"
        req = urllib.request.Request(base + "/sim", data=b"load 1.5", method="POST")
        with urllib.request.urlopen(req, timeout=5) as r:
            reply = r.read().decode()
        assert "load" in reply, f"unexpected reply to a command: {reply}"
        print(f"port {port}: dashboard, state ({len(state['cells'])} cells) and commands work")
        if check_scenarios:
            end = time.time() + 600
            report = {}
            while time.time() < end:
                report = json.loads(get(base + "/api/scenarios", timeout=10))
                if report.get("status") == "done":
                    break
                time.sleep(2)
            results = report.get("results", [])
            failed = [r for r in results if not r.get("pass")]
            assert report.get("status") == "done", "the scenarios did not finish"
            assert len(results) == 30 and not failed, f"{len(results)} scenarios, failed: {failed}"
            print(f"port {port}: all {len(results)} scenarios pass ({report.get('seconds')} s)")
    finally:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
        time.sleep(1)
        print(f"--- launcher output (port {port}) ---")
        print(log.read_text(encoding="utf-8", errors="replace"))


def main():
    pkg = pathlib.Path(sys.argv[1]).resolve()
    run(pkg, 8080, check_scenarios=True)
    # Another program holds port 8080: the demo must start on the next port.
    blocker = socket.socket()
    try:
        blocker.bind(("127.0.0.1", 8080))
        blocker.listen()
    except OSError:
        pass   # the port is still held from the first run, which blocks it just as well
    try:
        run(pkg, 8081, check_scenarios=False)
    finally:
        blocker.close()
    print("demo check passed")


if __name__ == "__main__":
    main()
