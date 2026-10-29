#!/usr/bin/env python3
"""Gate 9: fit the two-state thermal model (architecture 9.1) to a logged discharge.

Fits the shared core and surface heat capacities (c_core, c_surf, J/C), the core-to-surface
resistance (r_core, C/W) and each cell's surface-to-air resistance (r_air, C/W), using only the
heat the current explains (I^2 R) and the measured air temperature. Abnormal heat is taken as
zero, so log only normal operation: Gate 9 step 6 asks for a 1 A and a 2 A discharge, each
followed by its cooling curve. Start the log after at least 30 minutes at rest, so the core and
the surface start at the same temperature.

    python3 tools/fit_thermal.py LOG.csv [--r-mohm 35.1 34.8 35.4 35.0] [--json out.json]

LOG.csv is the CSV telemetry of the firmware ("log 1" on the console, captured with
tools/serial_log.py) or of the simulator ("bms_sim run fit_log --csv LOG.csv").

The result is printed as the console command that stores it ("model thermal ..."). If the
core/surface split cannot be told apart in the data, the report says so: then use the
single-mass fallback the plan allows, by keeping the total heat capacity and r_air and taking
the split from the estimate.
"""

import argparse
import csv
import json
import math
import sys

import numpy as np
from scipy.linalg import expm
from scipy.optimize import least_squares
from scipy.signal import fftconvolve

CLAMP_A = 5.0   # architecture 9.2: |I| is clamped to 5.0 A when the expected heat is computed
CELLS = 4


def read_log(path):
    """Reads the telemetry CSV; lines may carry the firmware's 'CSV,' prefix."""
    rows = []
    with open(path, newline="") as f:
        lines = (ln[4:] if ln.startswith("CSV,") else ln for ln in f)
        for row in csv.DictReader(lines):
            if row.get("t_s") in (None, "", "t_s"):
                continue
            rows.append(row)
    if len(rows) < 600:
        sys.exit(f"{path}: {len(rows)} rows; the fit needs at least 10 minutes at 1 Hz")

    def col(name):
        out = []
        for r in rows:
            v = r.get(name, "")
            out.append(float(v) if v not in ("", None) else math.nan)
        return np.array(out)

    data = {"t": col("t_s"), "i": col("current_a"), "t_amb": col("t_amb")}
    data["ts"] = np.stack([col(f"ts{k}") for k in range(1, CELLS + 1)])
    data["r"] = np.stack([col(f"r{k}_mohm") for k in range(1, CELLS + 1)]) / 1000.0
    return data


def resample(data, dt):
    """Puts every column on an even time grid (lost lines leave gaps in a serial log)."""
    t = data["t"]
    ok = np.isfinite(t)
    grid = np.arange(t[ok][0], t[ok][-1], dt)

    def interp(y):
        good = ok & np.isfinite(y)
        return np.interp(grid, t[good], y[good])

    out = {"t": grid, "i": interp(data["i"]), "t_amb": interp(data["t_amb"])}
    out["ts"] = np.stack([interp(y) for y in data["ts"]])
    out["r"] = np.stack([interp(y) for y in data["r"]])
    return out


def surface_response(c_core, c_surf, r_core, r_air, p_joule, t_amb, t0, dt):
    """Surface temperature of the healthy two-state model, by superposition.

    x(k+1) = phi x(k) + gam u(k) is solved in closed form: the response to each input is a
    convolution with the impulse response C phi^m gam, computed from the eigenvalues of phi.
    """
    a = np.array([[-1 / (r_core * c_core), 1 / (r_core * c_core)],
                  [1 / (r_core * c_surf), -(1 / r_core + 1 / r_air) / c_surf]])
    b = np.array([[1 / c_core, 0.0], [0.0, 1 / (r_air * c_surf)]])
    phi = expm(a * dt)
    gam = np.linalg.solve(a, phi - np.eye(2)) @ b
    w, v = np.linalg.eig(phi)
    w, v = w.real, v.real
    n = len(p_joule)
    powers = w[None, :] ** np.arange(n)[:, None]           # n x 2
    c_phi = (powers * v[1][None, :]) @ np.linalg.inv(v)     # row m: C phi^m
    y = c_phi @ np.array([t0, t0])                           # start at rest: core = surface
    h = c_phi @ gam                                          # impulse responses, n x 2
    y[1:] += fftconvolve(h[:, 0], p_joule)[: n - 1]
    y[1:] += fftconvolve(h[:, 1], t_amb)[: n - 1]
    return y


def fit(data, r_cell, dt):
    i_heat = np.minimum(np.abs(data["i"]), CLAMP_A)
    p = [i_heat ** 2 * r_cell[k] for k in range(CELLS)]
    ts = data["ts"]

    def residuals(x):
        c_core, c_surf, r_core = np.exp(x[:3])
        res = []
        for k in range(CELLS):
            y = surface_response(c_core, c_surf, r_core, math.exp(x[3 + k]), p[k],
                                 data["t_amb"], ts[k][0], dt)
            res.append(y - ts[k])
        return np.concatenate(res)

    x0 = np.log([40.0, 5.0, 2.0] + [30.0] * CELLS)   # the architecture's estimates as a start
    sol = least_squares(residuals, x0, method="trf", x_scale="jac")
    r = sol.fun
    dof = max(1, len(r) - len(sol.x))
    s2 = float(r @ r) / dof
    try:
        cov = np.linalg.inv(sol.jac.T @ sol.jac) * s2
        rel_se = np.sqrt(np.clip(np.diag(cov), 0, None))   # log parameters: relative error
    except np.linalg.LinAlgError:
        rel_se = np.full(len(sol.x), np.inf)
    per_cell = r.reshape(CELLS, -1)
    return {
        "c_core": float(math.exp(sol.x[0])),
        "c_surf": float(math.exp(sol.x[1])),
        "r_core": float(math.exp(sol.x[2])),
        "r_air": [float(math.exp(v)) for v in sol.x[3:]],
        "rel_se": [float(v) for v in rel_se],
        "rms_c": [float(np.sqrt(np.mean(c ** 2))) for c in per_cell],
        "max_abs_c": float(np.max(np.abs(r))),
        "samples": int(per_cell.shape[1]),
        "converged": bool(sol.success),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Gate 9 thermal fit (architecture 9.1)")
    ap.add_argument("log", help="telemetry CSV")
    ap.add_argument("--r-mohm", type=float, nargs=CELLS, metavar="R",
                    help="Gate 4 resistance of each cell; default: the logged online values")
    ap.add_argument("--dt", type=float, default=1.0, help="resampling step, s")
    ap.add_argument("--start", type=float, default=None, help="first time to use, s")
    ap.add_argument("--end", type=float, default=None, help="last time to use, s")
    ap.add_argument("--json", help="also write the result here")
    args = ap.parse_args(argv)

    data = read_log(args.log)
    keep = np.ones(len(data["t"]), bool)
    if args.start is not None:
        keep &= data["t"] >= args.start
    if args.end is not None:
        keep &= data["t"] <= args.end
    for key in ("t", "i", "t_amb"):
        data[key] = data[key][keep]
    data["ts"] = data["ts"][:, keep]
    data["r"] = data["r"][:, keep]
    data = resample(data, args.dt)

    if args.r_mohm:
        r_cell = [v / 1000.0 for v in args.r_mohm]
    else:
        r_cell = [float(np.nanmedian(data["r"][k])) for k in range(CELLS)]

    res = fit(data, r_cell, args.dt)
    res["r_cell_ohm"] = r_cell
    names = ["c_core", "c_surf", "r_core"] + [f"r_air{k + 1}" for k in range(CELLS)]
    values = [res["c_core"], res["c_surf"], res["r_core"]] + res["r_air"]

    print(f"Fitted on {res['samples']} samples per cell ({res['samples'] * args.dt / 60:.0f} min)")
    for n, v, se in zip(names, values, res["rel_se"]):
        print(f"  {n:8s} {v:9.3f}   +-{100 * se:5.1f} %")
    print(f"  total heat capacity {res['c_core'] + res['c_surf']:.1f} J/C")
    print("  fit error per cell (RMS): " + "  ".join(f"{v:.3f}" for v in res["rms_c"]) +
          f" C; largest {res['max_abs_c']:.3f} C")
    weak = [n for n, se in zip(names, res["rel_se"]) if se > 0.3]
    if not res["converged"]:
        print("WARNING: the fit did not converge; check the log covers a load and its cooling.")
    if weak:
        print("NOTE: these values are poorly set by this log (over 30 % uncertain): "
              + ", ".join(weak) + ".\n      If the core/surface split is among them, the model"
              " acts as a single thermal mass; keep the total heat capacity and r_air.")
    print("\nStore on the ESP32 (console), then switch the model on:")
    print("  model thermal " + " ".join(f"{v:.4g}" for v in values))
    print("  model mode fitted")
    if args.json:
        with open(args.json, "w") as f:
            json.dump(res, f, indent=2)
    return res


if __name__ == "__main__":
    main()
