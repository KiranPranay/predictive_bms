"""Simulates the KiCad schematics in kicad/sim/ with ngspice and checks the results.

    python3 kicad/run_sims.py

For each circuit it exports the SPICE netlist with kicad-cli (KiCad 10), runs ngspice in batch
mode, checks the results against the architecture's numbers, and writes:

- build/kicad-sim/: the netlists, the ngspice logs and the raw data;
- docs/build-guide/kicad-sim/results.json: every number and every check;
- docs/build-guide/figures/sim-*.svg: the charts, and kicad-*.svg: the schematics as KiCad draws them.

With --check it only simulates and checks, and writes nothing under docs/ (the tests use this).

kicad-cli is found on the PATH, through the KiCad Flatpak, or in KICAD_CLI. ngspice is found in
.tools/sim/bin, on the PATH, or in NGSPICE. The exit code is 1 when a check fails.
"""

import json
import math
import os
import pathlib
import re
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sch  # noqa: E402  (the schematic reader in this folder)

ROOT = HERE.parent
SIM = HERE / "sim"
BUILD = ROOT / "build" / "kicad-sim"
DOCS = ROOT / "docs" / "build-guide"
FIGS = DOCS / "figures"
RESULTS = DOCS / "kicad-sim" / "results.json"
OCTAVE_STEP = ROOT / "build" / "matlab" / "thermal_step.csv"

# Numbers the checks use, with their source.
ADC_STOP_V = 3.0          # Gate 1 stop: no ADC input above 3.0 V
TAP_TOL_V = 0.020         # Gate 1 pass: tap error within 20 mV after calibration
ESP_ADC_MIN, ESP_ADC_MAX = 0.15, 2.45   # ESP32 ADC1 at 12 dB attenuation (ESP-IDF), ntc_adc.cpp
INA226_FS_V = 32767 * 2.5e-6            # INA226: 16-bit shunt register, 2.5 uV per bit
CURRENT_TOL = 0.02        # Gate 1 pass: current within 2 % (or 20 mA)
TEMP_LIMITS = {"charge trip": 45.0, "discharge trip": 55.0}   # architecture section 8 table


# --- Tools ---------------------------------------------------------------------------------

def kicad_cli():
    if os.environ.get("KICAD_CLI"):
        return [os.environ["KICAD_CLI"]]
    if shutil.which("kicad-cli"):
        return ["kicad-cli"]
    if shutil.which("flatpak"):
        r = subprocess.run(["flatpak", "info", "org.kicad.KiCad"], capture_output=True)
        if r.returncode == 0:
            return ["flatpak", "run", "--command=kicad-cli", "org.kicad.KiCad"]
    return None


def ngspice():
    if os.environ.get("NGSPICE"):
        return os.environ["NGSPICE"]
    for p in (ROOT / ".tools" / "sim" / "bin" / "ngspice", ROOT / ".tools" / "sim" / "Library" / "bin" / "ngspice.exe"):
        if p.exists():
            return str(p)
    return shutil.which("ngspice")


def export_netlist(cli, name):
    sch = SIM / name / f"{name}.kicad_sch"
    out = BUILD / f"{name}.cir"
    r = subprocess.run(cli + ["sch", "export", "netlist", "--format", "spice", "-o", str(out), str(sch)],
                       capture_output=True, text=True)
    if r.returncode != 0 or not out.exists():
        raise SystemExit(f"kicad-cli could not export {sch}:\n{r.stdout}{r.stderr}")
    return out.read_text(encoding="utf-8")


def drawing_bounds(path):
    """The area the circuit covers on the KiCad page, in mm, with room for the text."""
    xs, ys = [], []

    def walk(node):
        if not isinstance(node, list) or not node:
            return
        if node[0] == "lib_symbols":
            return
        if node[0] in ("at", "xy") and len(node) >= 3:
            xs.append(float(node[1]))
            ys.append(float(node[2]))
        if node[0] in ("text", "label", "global_label"):
            at = sch.find(node, "at")[0]
            lines = sch.unq(node[1]).split("\\n")
            xs.append(float(at[1]) + max(len(t) for t in lines) * 1.1 + 4)
            ys.append(float(at[2]) + 2.2 * len(lines))
        for x in node[1:]:
            walk(x)
    walk(sch.parse(path.read_text(encoding="utf-8")))
    return min(xs) - 6, min(ys) - 6, max(xs) + 4, max(ys) + 6


def export_svg(cli, name):
    """Writes the schematic as KiCad draws it, cropped to the circuit, for the build guide."""
    path = SIM / name / f"{name}.kicad_sch"
    tmp = BUILD / "svg"
    tmp.mkdir(parents=True, exist_ok=True)
    subprocess.run(cli + ["sch", "export", "svg", "--exclude-drawing-sheet", "-o", str(tmp), str(path)],
                   capture_output=True, check=True)
    x0, y0, x1, y1 = drawing_bounds(path)
    svg = (tmp / f"{name}.svg").read_text(encoding="utf-8")
    svg = re.sub(r'width="[^"]*mm" height="[^"]*mm" viewBox="[^"]*"',
                 f'width="{x1 - x0:.2f}mm" height="{y1 - y0:.2f}mm" viewBox="{x0:.2f} {y0:.2f} {x1 - x0:.2f} {y1 - y0:.2f}"',
                 svg, count=1)
    (FIGS / f"kicad-{name}.svg").write_text(svg, encoding="utf-8")


ANALYSIS = re.compile(r"^\s*\.(op|dc|ac|tran|end)\b", re.I)


def run_spice(spice, netlist, control, tag, extra=""):
    """Runs the netlist without its own analysis lines, with `control` as the .control block.
    Returns ngspice's printed output."""
    body = "\n".join(l for l in netlist.splitlines() if not ANALYSIS.match(l))
    deck = BUILD / f"{tag}.cir"
    deck.write_text(f"{body}\n{extra}\n.control\nset wr_singlescale\nset wr_vecnames\n"
                    f"{control}\nquit\n.endc\n.end\n", encoding="utf-8")
    r = subprocess.run([spice, "-b", deck.name], capture_output=True, text=True, cwd=BUILD)
    (BUILD / f"{tag}.log").write_text(r.stdout + r.stderr, encoding="utf-8")
    if r.returncode != 0 or "error" in (r.stdout + r.stderr).lower().replace("errors: 0", ""):
        raise SystemExit(f"ngspice failed on {deck}; see {BUILD / (tag + '.log')}")
    return r.stdout


def read_data(path):
    """Reads a wrdata file written with wr_singlescale and wr_vecnames. Returns its columns in
    order: the sweep (time, frequency or the swept value) first, then each vector."""
    lines = (BUILD / path).read_text().split("\n")
    n = len(lines[0].split())
    cols = [[] for _ in range(n)]
    for line in lines[1:]:
        vals = line.split()
        if len(vals) == n:
            for c, v in zip(cols, vals):
                c.append(float(v))
    return cols


def printed(out, name):
    m = re.search(rf"^\s*{re.escape(name)}\s*=\s*([-+0-9.eE]+)", out, re.M | re.I)
    return float(m.group(1)) if m else float("nan")


def interp(xs, ys, x):
    for (x0, y0), (x1, y1) in zip(zip(xs, ys), zip(xs[1:], ys[1:])):
        if min(x0, x1) <= x <= max(x0, x1) and x1 != x0:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return float("nan")


def crossing(xs, ys, level):
    for (x0, y0), (x1, y1) in zip(zip(xs, ys), zip(xs[1:], ys[1:])):
        if (y0 - level) * (y1 - level) <= 0 and y1 != y0:
            return x0 + (x1 - x0) * (level - y0) / (y1 - y0)
    return float("nan")


class Checks:
    def __init__(self):
        self.items = []

    def add(self, circuit, what, value, limit, ok):
        self.items.append({"circuit": circuit, "check": what, "value": value, "limit": limit, "pass": bool(ok)})


# --- The circuits --------------------------------------------------------------------------

def cell_taps(spice, net, checks):
    res = {}
    for r_entry in ("10k", "1k"):
        alter = "\n".join(f"alter r{12 + n} {r_entry}" for n in range(1, 5))
        out = run_spice(spice, net, f"{alter}\nop\nprint v(adc1) v(adc2) v(adc3) v(adc4)", f"taps-op-{r_entry}")
        adc = [printed(out, f"v(adc{n})") for n in range(1, 5)]
        res[f"adc_v_entry_{r_entry}"] = adc
        res[f"gain_entry_{r_entry}"] = [4.2 * n / v for n, v in enumerate(adc, 1)]
    top = max(res["adc_v_entry_10k"] + res["adc_v_entry_1k"])
    checks.add("cell taps", "highest ADC input at 4 x 4.2 V", round(top, 4), f"< {ADC_STOP_V} V (Gate 1 stop)",
               top < ADC_STOP_V)

    run_spice(spice, net, "dc I1 0 100n 1n\nwrdata taps-leak.dat v(adc4)", "taps-leak")
    sweep, adc4 = read_data("taps-leak.dat")
    gain = res["gain_entry_10k"][3]
    err_mv = [(adc4[0] - v) * gain * 1000 for v in adc4]
    leak_na = [i * 1e9 for i in sweep]
    per10 = interp(leak_na, err_mv, 10.0)
    limit_na = crossing(leak_na, err_mv, TAP_TOL_V * 1000)
    res.update(leak_na=leak_na, leak_err_mv=err_mv, err_mv_per_10na=per10, leak_for_20mv_na=limit_na)
    checks.add("cell taps", "tap error per 10 nA of leakage", round(per10, 2), "mV (for the TBD clamp)", True)

    run_spice(spice, net, "alter @v4[acmag] = 1\nac dec 50 0.1 10k\nwrdata taps-ac.dat vdb(adc4)", "taps-ac")
    freq, db = read_data("taps-ac.dat")
    lf = db[0]
    f3 = crossing(freq, db, lf - 3.0103)
    tau = 1 / (2 * math.pi * f3)
    res.update(f3db_hz=f3, tau_ms=tau * 1e3, settle_ms_16bit=tau * math.log(2 ** 16) * 1e3,
               ac_f=freq, ac_db=[v - lf for v in db])
    checks.add("cell taps", "settling to 16 bits after a step", round(tau * math.log(2 ** 16) * 1e3, 1),
               "< 200 ms (one 5 Hz sample)", tau * math.log(2 ** 16) < 0.2)
    return res


def ntc(spice, net, checks):
    run_spice(spice, net, "dc temp -20 100 0.5\nwrdata ntc.dat v(ntc_adc)", "ntc")
    t, v = read_data("ntc.dat")
    res = {"temp_c": t, "adc_v": v, "v_25c": interp(t, v, 25.0)}
    res["usable_from_c"] = crossing(t, v, ESP_ADC_MAX)
    res["usable_to_c"] = crossing(t, v, ESP_ADC_MIN)
    res["mv_per_c"] = {str(k): (interp(t, v, k - 0.5) - interp(t, v, k + 0.5)) * 1000 for k in (25, 45, 55)}
    res["ntc_mw_25c"] = res["v_25c"] ** 2 / 10e3 * 1000
    checks.add("NTC", "divider at 25 °C", round(res["v_25c"], 4), "1.65 V (half of 3.3 V)",
               abs(res["v_25c"] - 1.65) < 0.005)
    for name, lim in TEMP_LIMITS.items():
        vv = interp(t, v, lim)
        checks.add("NTC", f"ADC voltage at the {name} ({lim:g} °C)", round(vv, 4),
                   f"{ESP_ADC_MIN}-{ESP_ADC_MAX} V (ESP32 ADC1, 12 dB)", ESP_ADC_MIN < vv < ESP_ADC_MAX)
    return res


def current_sense(spice, net, checks):
    sense = "v(/sense_p)-v(/sense_n)"
    run_spice(spice, net, f"dc I1 -5 5 0.1\nwrdata cur.dat {sense}", "cur")
    i, vs = read_data("cur.dat")
    run_spice(spice, net, f"dc I1 -5 5 0.1\nwrdata cur100.dat {sense}", "cur-r100",
              extra="RR100 /SENSE_P /SENSE_N 0.1")   # the module's R100, left in place
    _, vs100 = read_data("cur100.dat")
    v5 = interp(i, vs, 5.0)
    err100 = (interp(i, vs100, 5.0) / 0.005 - 5.0) / 5.0
    res = {"current_a": i, "sense_mv": [x * 1000 for x in vs], "sense_mv_r100": [x * 1000 for x in vs100],
           "sense_mv_5a": v5 * 1000, "shunt_w_5a": 5.0 ** 2 * 0.005, "r100_error_pct": err100 * 100,
           "fs_mv": INA226_FS_V * 1000}
    checks.add("current", "shunt voltage at 5 A", round(v5 * 1000, 3), f"within +/-{INA226_FS_V * 1000:.2f} mV (INA226)",
               abs(v5) < INA226_FS_V)
    checks.add("current", "sign: discharge reads positive", round(v5 * 1000, 3), "> 0", v5 > 0)
    checks.add("current", "error if the module's R100 is left in place", round(err100 * 100, 2),
               "% (must be removed; Gate 1 allows 2 %)", True)
    return res


def thermal(spice, net, checks):
    run_spice(spice, net, "tran 1 3610 0 1\nwrdata thermal.dat v(/t_core) v(/t_surf)", "thermal")
    time, tc, ts = read_data("thermal.dat")
    t = [x - 10.0 for x in time]   # the step starts at 10 s
    marks = (60, 300, 1200, 3600)
    res = {"t_s": t, "t_core": tc, "t_surf": ts,
           "at": {str(m): [interp(t, tc, m), interp(t, ts, m)] for m in marks}}
    # The model's two time constants, from its matrix (the same values as the schematic).
    cc, cs, rc, ra = 40.0, 5.0, 2.0, 30.0
    a, b, c, dd = -1 / (rc * cc), 1 / (rc * cc), 1 / (rc * cs), -(1 / rc + 1 / ra) / cs
    tr, det = a + dd, a * dd - b * c
    l1 = (tr + math.sqrt(tr * tr - 4 * det)) / 2
    l2 = (tr - math.sqrt(tr * tr - 4 * det)) / 2
    res["tau_s"] = [-1 / l1, -1 / l2]
    res["steady_core_c"] = 25.0 + 1.0 * (rc + ra)
    checks.add("thermal", "core rise after 1 h of 1 W", round(interp(t, tc, 3600) - 25, 3),
               f"approaches {rc + ra:g} °C (R_core + R_air)", interp(t, tc, 3600) - 25 < rc + ra)
    if OCTAVE_STEP.exists():
        rows = [list(map(float, l.split(","))) for l in OCTAVE_STEP.read_text().split("\n")[1:] if l.strip()]
        worst = max(max(abs(interp(t, tc, r[0]) - r[1]), abs(interp(t, ts, r[0]) - r[2]))
                    for r in rows if 0 <= r[0] <= 3600)
        res["octave"] = {"t_s": [r[0] for r in rows], "t_core": [r[1] for r in rows], "t_surf": [r[2] for r in rows]}
        res["octave_max_diff_c"] = worst
        checks.add("thermal", "ngspice against Octave, largest difference", round(worst, 4), "< 0.01 °C",
                   worst < 0.01)
    return res


CIRCUITS = {"cell-taps": cell_taps, "ntc-divider": ntc, "current-sense": current_sense,
            "thermal-model": thermal}


# --- Charts --------------------------------------------------------------------------------

INK, MUTED, GRID = "#1f2328", "#5b6470", "#e3e6ea"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
FONT = "Liberation Sans, Arial, Helvetica, sans-serif"


def nice_ticks(lo, hi, n=6):
    step = 10 ** math.floor(math.log10((hi - lo) / n))
    for m in (1, 2, 2.5, 5, 10):
        if (hi - lo) / (step * m) <= n:
            step *= m
            break
    t = math.ceil(lo / step) * step
    out = []
    while t <= hi + 1e-9:
        out.append(round(t, 10))
        t += step
    return out


def chart(path, title, xlabel, ylabel, series, xr, yr, bands=(), hlines=(), vlines=(), logx=False,
          w=760, h=380):
    """A line chart as SVG. series: [(name, xs, ys, colour, dashed, markers)]."""
    legend = len(series) > 1   # one series: the title names it
    l, r, t, b = 64, 170 if legend else 24, 34, 46
    pw, ph = w - l - r, h - t - b

    def X(x):
        if logx:
            return l + (math.log10(x) - math.log10(xr[0])) / (math.log10(xr[1]) - math.log10(xr[0])) * pw
        return l + (x - xr[0]) / (xr[1] - xr[0]) * pw

    def Y(y):
        return t + ph - (y - yr[0]) / (yr[1] - yr[0]) * ph

    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
         f'font-family="{FONT}" font-size="12">',
         f'<rect width="{w}" height="{h}" fill="#fff"/>',
         f'<text x="{l}" y="20" font-size="14" font-weight="bold" fill="{INK}">{title}</text>']
    for (y0, y1, label) in bands:
        o.append(f'<rect x="{l}" y="{Y(y1):.1f}" width="{pw}" height="{Y(y0) - Y(y1):.1f}" fill="#eef6ee"/>')
        o.append(f'<text x="{l + pw - 6}" y="{Y(y1) + 15:.1f}" text-anchor="end" fill="{MUTED}">{label}</text>')
    xt = [10 ** k for k in range(math.ceil(math.log10(xr[0])), math.floor(math.log10(xr[1])) + 1)] if logx \
        else nice_ticks(*xr)
    for x in xt:
        o.append(f'<line x1="{X(x):.1f}" y1="{t}" x2="{X(x):.1f}" y2="{t + ph}" stroke="{GRID}"/>')
        o.append(f'<text x="{X(x):.1f}" y="{t + ph + 16}" text-anchor="middle" fill="{MUTED}">{x:g}</text>')
    for y in nice_ticks(*yr):
        o.append(f'<line x1="{l}" y1="{Y(y):.1f}" x2="{l + pw}" y2="{Y(y):.1f}" stroke="{GRID}"/>')
        o.append(f'<text x="{l - 6}" y="{Y(y) + 4:.1f}" text-anchor="end" fill="{MUTED}">{y:g}</text>')
    o.append(f'<line x1="{l}" y1="{t + ph}" x2="{l + pw}" y2="{t + ph}" stroke="{MUTED}"/>')
    o.append(f'<text x="{l + pw / 2}" y="{h - 8}" text-anchor="middle" fill="{INK}">{xlabel}</text>')
    o.append(f'<text transform="translate(16 {t + ph / 2}) rotate(-90)" text-anchor="middle" fill="{INK}">{ylabel}</text>')
    for (y, label) in hlines:
        o.append(f'<line x1="{l}" y1="{Y(y):.1f}" x2="{l + pw}" y2="{Y(y):.1f}" stroke="#b42318" stroke-dasharray="5 4"/>')
        o.append(f'<text x="{l + pw - 4}" y="{Y(y) - 5:.1f}" text-anchor="end" fill="#b42318">{label}</text>')
    for k, (x, label) in enumerate(vlines):
        o.append(f'<line x1="{X(x):.1f}" y1="{t}" x2="{X(x):.1f}" y2="{t + ph}" stroke="{MUTED}" stroke-dasharray="3 3"/>')
        o.append(f'<text x="{X(x) + 4:.1f}" y="{t + 12 + 15 * k}" fill="{MUTED}">{label}</text>')
    ly = t + 6
    for (name, xs, ys, colour, dashed, markers) in series:
        pts = [(X(x), Y(y)) for x, y in zip(xs, ys) if xr[0] <= x <= xr[1] and yr[0] <= y <= yr[1]]
        if markers:
            for (px, py) in pts:
                o.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="4" fill="{colour}" stroke="#fff" stroke-width="1.5"/>')
        else:
            d = " ".join(f"{px:.1f},{py:.1f}" for px, py in pts)
            dash = ' stroke-dasharray="7 5"' if dashed else ""
            o.append(f'<polyline points="{d}" fill="none" stroke="{colour}" stroke-width="2"{dash}/>')
        if not legend:
            continue
        ly += 18
        sx = l + pw + 12
        if markers:
            o.append(f'<circle cx="{sx + 10}" cy="{ly - 4}" r="4" fill="{colour}"/>')
        else:
            dash = ' stroke-dasharray="7 5"' if dashed else ""
            o.append(f'<line x1="{sx}" y1="{ly - 4}" x2="{sx + 20}" y2="{ly - 4}" stroke="{colour}" stroke-width="2"{dash}/>')
        o.append(f'<text x="{sx + 26}" y="{ly}" fill="{INK}">{name}</text>')
    o.append("</svg>")
    path.write_text("\n".join(o) + "\n", encoding="utf-8")


def charts(res):
    t = res["cell-taps"]
    chart(FIGS / "sim-taps-leakage.svg", "Cell tap: reading error from leakage at the ADC input",
          "leakage current at the ADC input (nA)", "error in the cell reading (mV)",
          [("channel 4, ngspice", t["leak_na"], t["leak_err_mv"], SERIES[0], False, False)],
          (0, 100), (0, 50), hlines=[(20, "Gate 1 limit, 20 mV")])
    chart(FIGS / "sim-taps-ac.svg", "Cell tap: frequency response of the divider and filter",
          "frequency (Hz)", "gain relative to DC (dB)",
          [("tap to ADC input", t["ac_f"], t["ac_db"], SERIES[0], False, False)],
          (0.1, 10000), (-50, 5), hlines=[(-3, f"-3 dB at {t['f3db_hz']:.1f} Hz")], logx=True)
    n = res["ntc-divider"]
    chart(FIGS / "sim-ntc.svg", "NTC divider: voltage at the ESP32 ADC against temperature",
          "NTC temperature (°C)", "ADC input (V)",
          [("NTC divider", n["temp_c"], n["adc_v"], SERIES[0], False, False)],
          (-20, 100), (0, 3.3), bands=[(ESP_ADC_MIN, ESP_ADC_MAX, "ESP32 ADC1 usable range")],
          vlines=[(45, "45 °C, charge trip"), (55, "55 °C, discharge trip")])
    c = res["current-sense"]
    chart(FIGS / "sim-current.svg", "Current sense: voltage across the shunt at the INA226 input",
          "pack current (A), discharge positive", "shunt voltage (mV)",
          [("5 mΩ shunt", c["current_a"], c["sense_mv"], SERIES[0], False, False),
           ("R100 left in place", c["current_a"], c["sense_mv_r100"], SERIES[1], True, False)],
          (-5, 5), (-30, 30))
    th = res["thermal-model"]
    series = [("core, ngspice", th["t_s"], th["t_core"], SERIES[1], False, False),
              ("surface, ngspice", th["t_s"], th["t_surf"], SERIES[0], False, False)]
    if "octave" in th:
        o = th["octave"]
        pick = [k for k, x in enumerate(o["t_s"]) if x % 300 == 0]
        series += [("core, Octave", [o["t_s"][k] for k in pick], [o["t_core"][k] for k in pick], SERIES[1], False, True),
                   ("surface, Octave", [o["t_s"][k] for k in pick], [o["t_surf"][k] for k in pick], SERIES[0], False, True)]
    chart(FIGS / "sim-thermal.svg", "Thermal model: 1 W of heat in the core from t = 0, ambient 25 °C",
          "time (s)", "temperature (°C)", series, (0, 3600), (20, 60),
          hlines=[(th["steady_core_c"], f"core settles at {th['steady_core_c']:g} °C")])


def compact(res):
    """The results without the long data arrays, for results.json. A value the sweep never
    reached (NaN) is written as null."""
    def clean(v):
        if isinstance(v, float) and math.isnan(v):
            return None
        if isinstance(v, dict):
            return {k: clean(x) for k, x in v.items()}
        if isinstance(v, list):
            return [clean(x) for x in v]
        return v
    return {name: {k: clean(v) for k, v in r.items() if not (isinstance(v, list) and len(v) > 8) and k != "octave"}
            for name, r in res.items()}


def main(argv=None):
    """With --check, only simulates and checks: nothing under docs/ is written."""
    write = "--check" not in (sys.argv[1:] if argv is None else argv)
    cli, spice = kicad_cli(), ngspice()
    if not cli or not spice:
        print("needs kicad-cli (KiCad 10) and ngspice; see kicad/README.md")
        return 2
    BUILD.mkdir(parents=True, exist_ok=True)
    FIGS.mkdir(parents=True, exist_ok=True)
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    checks, res = Checks(), {}
    for name, fn in CIRCUITS.items():
        net = export_netlist(cli, name)
        res[name] = fn(spice, net, checks)
        if write:
            export_svg(cli, name)
    if write:
        charts(res)
        RESULTS.write_text(json.dumps({"results": compact(res), "checks": checks.items}, indent=2) + "\n",
                           encoding="utf-8")
    for c in checks.items:
        print(f"{'PASS' if c['pass'] else 'FAIL'}  {c['circuit']}: {c['check']} = {c['value']} ({c['limit']})")
    return 0 if all(c["pass"] for c in checks.items) else 1


if __name__ == "__main__":
    sys.exit(main())
