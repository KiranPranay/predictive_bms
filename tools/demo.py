#!/usr/bin/env python3
"""One command for a demonstration on a PC: builds the simulator if needed, then opens the
dashboard on a simulated pack.

    python3 tools/demo.py [--port 8080] [--rebuild] [--no-browser]

Needs CMake and a C++17 compiler for the first build; after that only Python.
"""

import argparse
import pathlib
import shutil
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


def main():
    ap = argparse.ArgumentParser(description="dashboard on a simulated pack")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--rebuild", action="store_true", help="build the simulator again")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()
    if args.rebuild or not sim_server.default_sim().exists():
        build()
    argv = ["--port", str(args.port), "--speed", "10"]
    if not args.no_browser:
        argv.append("--open")
    sim_server.main(argv)


if __name__ == "__main__":
    main()
