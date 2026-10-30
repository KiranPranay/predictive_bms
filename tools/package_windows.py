#!/usr/bin/env python3
"""Builds the Windows package: one folder (and one zip) that a user extracts and opens, with
nothing to install for the demo.

    python3 tools/package_windows.py --exe build/host/Release/bms_sim.exe \\
        --python python-3.12.10-embed-amd64.zip [--out dist]

--exe is the Windows build of the simulator; --python is the Python embeddable distribution for
Windows (python.org, "Windows embeddable package (64-bit)"). The result is dist/PredictiveBMS/
and dist/PredictiveBMS-Windows.zip:

    PredictiveBMS/
      START HERE.pdf                   the presentation guide (docs/student/), if it exists
      1 Demo - double-click.bat        starts the dashboard on a simulated pack
      2 KiCad circuits/                the KiCad projects of kicad/sim/
      3 Octave model check/            the Octave (MATLAB) scripts, with bms_sim.exe
      4 Scilab Xcos models/            the Xcos models of scilab/, if they exist
      Documents/                       the build guide and the student documents
      program/                         bms_sim.exe, Python, the demo server and the dashboard

The GitHub workflow .github/workflows/windows.yml builds and tests it on Windows. Only the Python
standard library is needed, and it runs on Linux and Windows.
"""

import argparse
import pathlib
import shutil
import sys
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
NAME = "PredictiveBMS"

# The demo launcher. Windows runs .bat files with CRLF line endings; they are added on writing.
LAUNCHER = r"""@echo off
setlocal
title Predictive BMS - demo
cd /d "%~dp0program" 2>nul || goto missing
if not exist "python\python.exe" goto missing
if not exist "bms_sim.exe" goto missing
if not exist "tools\demo.py" goto missing
if not exist "dashboard\index.html" goto missing
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
echo.
echo   Predictive BMS - demonstration on a simulated battery pack
echo   ------------------------------------------------------------
echo   The dashboard opens in your web browser in a few seconds.
echo   If it does not open, type the address shown below into the browser.
echo.
echo   The demo is running. Close this window to stop it.
echo.
"python\python.exe" "tools\demo.py"
echo.
echo   The demo has stopped. If there is a message above, it says why.
echo.
pause
exit /b 0

:missing
echo.
echo   A file of the demo is missing. The "program" folder must be beside this file,
echo   with python, bms_sim.exe, tools and dashboard inside it.
echo.
echo   Extract the whole zip first: right-click the zip file, choose "Extract All...",
echo   then open the extracted folder and double-click this file again.
echo.
pause
exit /b 1
"""


def copy(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def build(exe, python_zip, out):
    pkg = out / NAME
    if pkg.exists():
        shutil.rmtree(pkg)
    pkg.mkdir(parents=True)

    # The demo: the simulator, an embedded Python, the server and the dashboard. The program
    # folder repeats the repository's layout (tools/, dashboard/), so tools/demo.py and
    # tools/sim_server.py run unchanged.
    prog = pkg / "program"
    copy(exe, prog / "bms_sim.exe")
    with zipfile.ZipFile(python_zip) as z:
        z.extractall(prog / "python")
    if not (prog / "python" / "python.exe").exists():
        sys.exit(f"{python_zip} is not the Python embeddable distribution (no python.exe)")
    for name in ("demo.py", "sim_server.py"):
        copy(ROOT / "tools" / name, prog / "tools" / name)
    copy(ROOT / "dashboard" / "index.html", prog / "dashboard" / "index.html")
    (pkg / "1 Demo - double-click.bat").write_bytes(LAUNCHER.replace("\n", "\r\n").encode("ascii"))

    # KiCad: each project folder as it is, without per-user files.
    kicad = pkg / "2 KiCad circuits"
    for project in sorted((ROOT / "kicad" / "sim").iterdir()):
        if project.is_dir():
            for f in sorted(project.iterdir()):
                if f.suffix in (".kicad_pro", ".kicad_sch"):
                    copy(f, kicad / project.name / f.name)

    # Octave: the scripts and their README, with the simulator that crosscheck runs.
    octave = pkg / "3 Octave model check"
    for f in sorted((ROOT / "matlab").iterdir()):
        if f.suffix == ".m" or f.name == "README.md":
            copy(f, octave / f.name)
    copy(exe, octave / "bms_sim.exe")

    # Scilab Xcos models, when the repository has them.
    scilab = ROOT / "scilab"
    models = sorted(scilab.glob("*.zcos")) + sorted(scilab.glob("*.xcos")) if scilab.is_dir() else []
    if models:
        for f in models + [scilab / "README.md"]:
            if f.exists():
                copy(f, pkg / "4 Scilab Xcos models" / f.name)

    # Documents.
    docs = pkg / "Documents"
    copy(ROOT / "docs" / "build-guide" / "Build-Guide.pdf", docs / "Build-Guide.pdf")
    student = ROOT / "docs" / "student"
    for name in ("Presentation-Guide.pdf", "Viva-Notes.pdf"):
        if (student / name).exists():
            copy(student / name, docs / name)
    if (student / "Presentation-Guide.pdf").exists():
        copy(student / "Presentation-Guide.pdf", pkg / "START HERE.pdf")

    # The zip, with the PredictiveBMS folder at its top.
    archive = out / f"{NAME}-Windows.zip"
    if archive.exists():
        archive.unlink()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in sorted(pkg.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(out).as_posix())
    return pkg, archive


def summary(pkg, archive):
    print(f"{pkg}:")
    for f in sorted(pkg.iterdir()):
        if f.is_dir():
            n = sum(1 for x in f.rglob("*") if x.is_file())
            print(f"  {f.name}/  ({n} files)")
        else:
            print(f"  {f.name}")
    print(f"{archive}: {archive.stat().st_size / 1e6:.1f} MB")


def main(argv=None):
    ap = argparse.ArgumentParser(description="build the Windows package")
    ap.add_argument("--exe", type=pathlib.Path, required=True, help="the Windows bms_sim.exe")
    ap.add_argument("--python", type=pathlib.Path, required=True,
                    help="python-3.12.x-embed-amd64.zip from python.org")
    ap.add_argument("--out", type=pathlib.Path, default=ROOT / "dist")
    args = ap.parse_args(argv)
    for f in (args.exe, args.python):
        if not f.is_file():
            sys.exit(f"{f} not found")
    pkg, archive = build(args.exe, args.python, args.out)
    summary(pkg, archive)


if __name__ == "__main__":
    main()
