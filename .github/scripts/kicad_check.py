"""Checks the package's KiCad projects with KiCad for Windows: ERC, the SPICE netlist, and a
simulation with KiCad's own ngspice library (the one its simulator window uses).

    python .github/scripts/kicad_check.py "C:/Program Files/KiCad/10.0" "dist/PredictiveBMS/2 KiCad circuits"

The results must match docs/build-guide/kicad-sim/results.json, which kicad/run_sims.py writes
on Linux with ngspice. Windows only (ctypes loads ngspice.dll).
"""

import ctypes as C
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
EXPECTED = json.loads((ROOT / "docs" / "build-guide" / "kicad-sim" / "results.json").read_text())["results"]
ANALYSIS = re.compile(r"^\s*\.(op|dc|ac|tran|end)\b", re.I)


class VectorInfo(C.Structure):
    _fields_ = [("v_name", C.c_char_p), ("v_type", C.c_int), ("v_flags", C.c_short),
                ("v_realdata", C.POINTER(C.c_double)), ("v_compdata", C.c_void_p),
                ("v_length", C.c_int)]


SendChar = C.CFUNCTYPE(C.c_int, C.c_char_p, C.c_int, C.c_void_p)
SendStat = C.CFUNCTYPE(C.c_int, C.c_char_p, C.c_int, C.c_void_p)
ControlledExit = C.CFUNCTYPE(C.c_int, C.c_int, C.c_bool, C.c_bool, C.c_int, C.c_void_p)
SendData = C.CFUNCTYPE(C.c_int, C.c_void_p, C.c_int, C.c_int, C.c_void_p)
SendInitData = C.CFUNCTYPE(C.c_int, C.c_void_p, C.c_int, C.c_void_p)
BGThreadRunning = C.CFUNCTYPE(C.c_int, C.c_bool, C.c_int, C.c_void_p)


class Ngspice:
    """ngspice as a shared library, driven as KiCad's simulator drives it."""

    def __init__(self, dll):
        os.add_dll_directory(str(dll.parent))
        self.lib = C.CDLL(str(dll))
        self.out = []
        self._cb = (SendChar(self._char), SendStat(lambda *a: 0),
                    ControlledExit(lambda *a: 0), SendData(lambda *a: 0),
                    SendInitData(lambda *a: 0), BGThreadRunning(lambda *a: 0))
        self.lib.ngSpice_Init.argtypes = [SendChar, SendStat, ControlledExit, SendData,
                                          SendInitData, BGThreadRunning, C.c_void_p]
        self.lib.ngSpice_Circ.argtypes = [C.POINTER(C.c_char_p)]
        self.lib.ngSpice_Command.argtypes = [C.c_char_p]
        self.lib.ngGet_Vec_Info.argtypes = [C.c_char_p]
        self.lib.ngGet_Vec_Info.restype = C.POINTER(VectorInfo)
        self.lib.ngSpice_Init(*self._cb, None)

    def _char(self, text, ident, user):
        self.out.append(text.decode("utf-8", "replace"))
        return 0

    def load(self, lines):
        arr = (C.c_char_p * (len(lines) + 1))(*[l.encode() for l in lines], None)
        if self.lib.ngSpice_Circ(arr) != 0:
            raise SystemExit("ngspice did not accept the netlist:\n" + "\n".join(self.out[-20:]))

    def cmd(self, text):
        self.lib.ngSpice_Command(text.encode())

    def vec(self, name):
        p = self.lib.ngGet_Vec_Info(name.encode())
        if not p or not p.contents.v_realdata:
            raise SystemExit(f"no vector {name}:\n" + "\n".join(self.out[-20:]))
        v = p.contents
        return [v.v_realdata[i] for i in range(v.v_length)]


def close(name, value, expected, tol):
    ok = abs(value - expected) <= tol
    print(f"  {'PASS' if ok else 'FAIL'} {name}: {value:.6g} (Linux ngspice {expected:.6g}, tolerance {tol:g})")
    return ok


def main():
    kicad, projects = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
    cli = kicad / "bin" / "kicad-cli.exe"
    dlls = sorted((kicad / "bin").glob("*ngspice*.dll"))
    print("kicad-cli:", subprocess.run([str(cli), "version"], capture_output=True, text=True).stdout.strip())
    print("ngspice library:", [d.name for d in dlls])
    # KiCad's first start copies the default symbol library table; do the same here.
    table = pathlib.Path(os.environ["APPDATA"]) / "kicad" / "10.0" / "sym-lib-table"
    if not table.exists():
        templates = sorted(kicad.rglob("template/sym-lib-table"))
        print("default symbol library table:", templates[0] if templates else "not found")
        if templates:
            table.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(templates[0], table)
    spice = Ngspice(dlls[0])
    tmp = pathlib.Path(os.environ.get("RUNNER_TEMP", "."))
    ok = True
    for sch in sorted(projects.glob("*/*.kicad_sch")):
        name = sch.stem
        print(f"{name}:")
        rpt = tmp / f"{name}-erc.rpt"
        r = subprocess.run([str(cli), "sch", "erc", "--severity-all", "--exit-code-violations",
                            "-o", str(rpt), str(sch)], capture_output=True, text=True)
        print("  ERC:", (r.stdout + r.stderr).strip().splitlines()[0] if (r.stdout + r.stderr).strip() else "")
        if r.returncode != 0:
            print(rpt.read_text(errors="replace"))
            ok = False
        cir = tmp / f"{name}.cir"
        subprocess.run([str(cli), "sch", "export", "netlist", "--format", "spice", "-o", str(cir), str(sch)],
                       check=True, capture_output=True)
        lines = [l for l in cir.read_text(errors="replace").splitlines() if not ANALYSIS.match(l)] + [".end"]
        spice.load(lines)
        exp = EXPECTED[name]
        if name == "cell-taps":
            spice.cmd("op")
            for n in range(1, 5):
                ok &= close(f"V(ADC{n})", spice.vec(f"adc{n}")[0], exp["adc_v_entry_10k"][n - 1], 0.001)
        elif name == "ntc-divider":
            spice.cmd("dc temp 25 25 1")
            ok &= close("V(NTC_ADC) at 25 degC", spice.vec("ntc_adc")[0], exp["v_25c"], 0.001)
        elif name == "current-sense":
            spice.cmd("dc i1 5 5 1")
            spice.cmd("let vs = v(/sense_p) - v(/sense_n)")
            ok &= close("shunt voltage at 5 A (mV)", spice.vec("vs")[0] * 1000, exp["sense_mv_5a"], 0.01)
        elif name == "thermal-model":
            spice.cmd("tran 1 3610 0 1")
            spice.cmd("let tc = v(/t_core)")
            time, tc = spice.vec("time"), spice.vec("tc")
            ok &= close("core temperature 1 h after the step (degC)", tc[-1] if abs(time[-1] - 3610) < 1 else float("nan"),
                        exp["at"]["3600"][0], 0.01)
        spice.cmd("remcirc")
    if not ok:
        print("\n".join(spice.out[-40:]))
        raise SystemExit("KiCad check failed")
    print("KiCad check passed")


if __name__ == "__main__":
    main()
