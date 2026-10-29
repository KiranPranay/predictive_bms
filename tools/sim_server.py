#!/usr/bin/env python3
"""Dashboard on top of the simulated pack.

Runs ``bms_sim live`` (the same supervisor code as the ESP32, against a simulated 4S pack) and
serves the dashboard at http://127.0.0.1:8080/. The page shows a Simulator panel with which
faults can be injected: abnormal heat, the Gate 11 resistor across a cell, a lifted or broken
NTC, a lost I2C device, a crash and restart.

    python3 tools/sim_server.py [--port 8080] [--speed 10] [--sim build/host/bms_sim]

Only the Python standard library is needed.
"""

import argparse
import http.server
import json
import pathlib
import subprocess
import sys
import threading

ROOT = pathlib.Path(__file__).resolve().parent.parent
DASHBOARD = ROOT / "dashboard" / "index.html"


def default_sim():
    for name in ("bms_sim", "bms_sim.exe"):
        for sub in ("", "Release", "Debug"):
            p = ROOT / "build" / "host" / sub / name
            if p.exists():
                return p
    return ROOT / "build" / "host" / "bms_sim"


class Simulator:
    """Owns the bms_sim process: keeps its latest snapshot, forwards commands."""

    def __init__(self, exe, speed):
        self.proc = subprocess.Popen(
            [str(exe), "live", "--speed", str(speed)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1)
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


def make_handler(sim):
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
            elif path == "/api/state":
                state = sim.state()
                if state is None:
                    self._send(503, json.dumps({"error": "starting"}), "application/json")
                else:
                    self._send(200, state, "application/json")
            else:
                self._send(404, "not found", "text/plain")

        def do_POST(self):
            if self.path.split("?")[0] != "/sim":
                self._send(404, "not found", "text/plain")
                return
            n = min(int(self.headers.get("Content-Length", 0)), 200)
            line = self.rfile.read(n).decode("utf-8", "replace")
            self._send(200, sim.send(line), "text/plain")

        def log_message(self, fmt, *args):
            pass

    return Handler


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--speed", type=float, default=10.0, help="simulated seconds per real second")
    ap.add_argument("--sim", type=pathlib.Path, default=None, help="path to the bms_sim program")
    args = ap.parse_args()

    exe = args.sim or default_sim()
    if not exe.exists():
        sys.exit(f"{exe} not found. Build it first:\n"
                 "  cmake -S host -B build/host && cmake --build build/host")
    sim = Simulator(exe, args.speed)
    server = http.server.ThreadingHTTPServer((args.host, args.port), make_handler(sim))
    print(f"Dashboard: http://{args.host}:{server.server_port}/  (simulated pack, x{args.speed:g})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        sim.stop()


if __name__ == "__main__":
    main()
