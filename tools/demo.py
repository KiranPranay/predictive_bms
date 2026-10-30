#!/usr/bin/env python3
"""One command for a demonstration on a PC: builds the simulator if needed, then opens the
dashboard on a simulated pack.

    python3 tools/demo.py [--port 8080] [--rebuild] [--no-browser]

Needs CMake and a C++17 compiler for the first build; after that only Python. In the Windows
package the simulator is already built ("1 Demo - double-click.bat" runs this file).

If the port is taken by another program, the next free one up to 8099 is used.
"""

import argparse
import pathlib
import shutil
import socket
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import sim_server  # noqa: E402


def build():
    cmake = shutil.which("cmake")
    if not cmake:
        sys.exit("CMake is needed for the first build: https://cmake.org/download/")
    build_dir = ROOT / "build" / "host"
    print("Building the simulator (first time only)...")
    subprocess.run([cmake, "-S", str(ROOT / "host"), "-B", str(build_dir),
                    "-DCMAKE_BUILD_TYPE=Release"], check=True)
    subprocess.run([cmake, "--build", str(build_dir), "--config", "Release"], check=True)


def free_port(first, last=8099):
    """The first port from `first` that no other program is using."""
    for port in range(first, max(first, last) + 1):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    sys.exit(f"Ports {first} to {last} are all in use. Close other programs and try again.")


def main(argv=None):
    ap = argparse.ArgumentParser(description="dashboard on a simulated pack")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--rebuild", action="store_true", help="build the simulator again")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args(argv)
    if sim_server.in_package():
        if not sim_server.default_sim().exists():
            sys.exit("bms_sim.exe is missing from the program folder. Extract the whole zip again.")
    elif args.rebuild or not sim_server.default_sim().exists():
        build()
    argv = ["--port", str(free_port(args.port)), "--speed", "10"]
    if not args.no_browser:
        argv.append("--open")
    sim_server.main(argv)


if __name__ == "__main__":
    main()
