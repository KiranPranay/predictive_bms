#!/usr/bin/env python3
"""Dashboard on top of the simulated pack.

Runs ``bms_sim live`` (the same supervisor code as the ESP32, against a simulated 4S pack) and
serves the dashboard at http://127.0.0.1:8080/. The page adds, in simulation only: guided
demonstrations, a comparison with a fixed-limit BMS, fault buttons, and the results of every
verification scenario (``/api/scenarios``).

    python3 tools/sim_server.py [--port 8080] [--speed 10] [--sim build/host/bms_sim] [--open]

tools/demo.py builds the simulator first when needed, then starts this server.

Only the Python standard library is needed.
"""

import argparse
import http.server
import json
import pathlib
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser

# ROOT is the repository, or the "program" folder of the Windows package, which has the same
# tools/ and dashboard/ folders and bms_sim.exe at its top.
ROOT = pathlib.Path(__file__).resolve().parent.parent
DASHBOARD = ROOT / "dashboard" / "index.html"


def in_package():
    """True in the Windows package: there is no host/ source folder to build from."""
    return not (ROOT / "host").is_dir()


def default_sim():
    candidates = [ROOT / "bms_sim.exe", ROOT / "bms_sim"]
    for name in ("bms_sim", "bms_sim.exe"):
        for sub in ("", "Release", "Debug"):
            candidates.append(ROOT / "build" / "host" / sub / name)
    for p in candidates:
        if p.is_file():
            return p
    return ROOT / "build" / "host" / "bms_sim"


class Simulator:
    """Owns the bms_sim process: keeps its latest snapshot, forwards commands."""

    def __init__(self, exe, speed):
        self.proc = subprocess.Popen(
            [str(exe), "live", "--speed", str(speed)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", bufsize=1)
        self.lock = threading.Lock()
        self.latest = None
        self.replies = []
        threading.Thread(target=self._read_state, daemon=True).start()
        threading.Thread(target=self._read_replies, daemon=True).start()

    def _read_state(self):
        for line in self.proc.stdout:
            line = line.strip()
            if line.startswith("{"):
                with self.lock:
                    self.latest = line

    def _read_replies(self):
        for line in self.proc.stderr:
            with self.lock:
                self.replies.append(line.strip())
                del self.replies[:-20]

    def state(self):
        with self.lock:
            return self.latest

    def send(self, line):
        line = " ".join(line.split())[:80]
        if not line:
            return "empty command"
        with self.lock:
            before = len(self.replies)
        self.proc.stdin.write(line + "\n")
        self.proc.stdin.flush()
        for _ in range(50):   # the reply comes within a sample or two
            with self.lock:
                if len(self.replies) > before:
                    return self.replies[-1]
            threading.Event().wait(0.02)
        return "sent: " + line

    def stop(self):
        self.proc.terminate()


class Verification:
    """Runs every verification scenario once (bms_sim run all) and keeps the result."""

    def __init__(self, exe):
        self.exe = exe
        self.lock = threading.Lock()
        self.result = {"status": "idle"}

    def start(self):
        with self.lock:
            if self.result.get("status") == "running":
                return
            self.result = {"status": "running"}
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        t0 = time.time()
        with tempfile.TemporaryDirectory() as d:
            report = pathlib.Path(d) / "report.json"
            proc = subprocess.run([str(self.exe), "run", "all", "--quiet", "--report", str(report)],
                                  capture_output=True, text=True, encoding="utf-8", errors="replace")
            try:
                results = json.loads(report.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                results = []
        with self.lock:
            self.result = {"status": "done", "seconds": round(time.time() - t0, 1),
                           "exit_code": proc.returncode, "results": results}

    def get(self):
        with self.lock:
            if self.result.get("status") == "idle":
                self.result = {"status": "running"}
                threading.Thread(target=self._run, daemon=True).start()
            return dict(self.result)


def make_handler(sim, verification):
    class Handler(http.server.BaseHTTPRequestHandler):
        def _send(self, code, body, ctype):
            data = body.encode() if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            path = self.path.split("?")[0]
            if path in ("/", "/index.html"):
                self._send(200, DASHBOARD.read_bytes(), "text/html; charset=utf-8")
            elif path == "/api/scenarios":
                self._send(200, json.dumps(verification.get()), "application/json")
            elif path == "/api/state":
                state = sim.state()
                if state is None:
                    self._send(503, json.dumps({"error": "starting"}), "application/json")
                else:
                    self._send(200, state, "application/json")
            else:
                self._send(404, "not found", "text/plain")

        def do_POST(self):
            if self.path.split("?")[0] == "/api/scenarios":
                verification.start()
                self._send(200, json.dumps({"status": "running"}), "application/json")
                return
            if self.path.split("?")[0] != "/sim":
                self._send(404, "not found", "text/plain")
                return
            n = min(int(self.headers.get("Content-Length", 0)), 200)
            line = self.rfile.read(n).decode("utf-8", "replace")
            self._send(200, sim.send(line), "text/plain")

        def log_message(self, fmt, *args):
            pass

    return Handler


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--speed", type=float, default=10.0, help="simulated seconds per real second")
    ap.add_argument("--sim", type=pathlib.Path, default=None, help="path to the bms_sim program")
    ap.add_argument("--open", action="store_true", help="open the dashboard in the browser")
    args = ap.parse_args(argv)

    exe = args.sim or default_sim()
    if not exe.exists():
        if in_package():
            sys.exit("bms_sim.exe is missing from the program folder. Extract the whole zip again.")
        sys.exit(f"{exe} not found. Build it first:\n"
                 "  cmake -S host -B build/host && cmake --build build/host")
    if not DASHBOARD.exists():
        sys.exit(f"{DASHBOARD} is missing. Extract the whole zip again.")
    sim = Simulator(exe, args.speed)
    server = http.server.ThreadingHTTPServer((args.host, args.port),
                                             make_handler(sim, Verification(exe)))
    url = f"http://{args.host}:{server.server_port}/"
    print(f"Dashboard: {url}  (simulated pack, x{args.speed:g}). Ctrl-C stops it.", flush=True)
    if args.open:
        threading.Timer(1.0, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        sim.stop()


if __name__ == "__main__":
    main()
