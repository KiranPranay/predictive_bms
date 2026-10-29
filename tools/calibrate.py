#!/usr/bin/env python3
"""Gate 1: calibration coefficients from bench readings, and the Gate 1 pass check.

Fill a CSV with one row per reading, taken with the console command "raw" and a calibrated
multimeter (or a reference thermometer):

    kind,channel,reading,reference
    tap,1,0.6090,4.200       reading: ADS1115 input volts (raw)    reference: meter volts at the tap
    current,1,1250.0,0.250   reading: INA226 shunt microvolts (raw) reference: meter amps
    ntc,2,24.61,25.00        reading: NTC temperature (raw)         reference: thermometer degC

Gate 1 asks for taps at 0, 4.2, 8.4, 12.6 and 16.8 V on every channel, current at +-0.25,
+-0.5 and +-1 A, and each NTC at ambient and at one warm reference point.

    python3 tools/calibrate.py readings.csv [--shunt-ohm 0.005]

Prints the console commands that store the result, and PASS or FAIL against the Gate 1
limits: taps within +-20 mV, current within +-2 % or +-20 mA (whichever is larger).
Only the Python standard library is needed.
"""

import argparse
import csv
import sys
from collections import defaultdict

TAP_LIMIT_V = 0.020
CURRENT_LIMIT_FRAC = 0.02
CURRENT_LIMIT_A = 0.020


def line_fit(xs, ys):
    """Least-squares y = gain * x + offset."""
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        raise ValueError("all readings are the same; take readings across the range")
    gain = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    return gain, my - gain * mx


def calibrate(rows, shunt_ohm=0.005):
    """Returns (commands, report lines, passed)."""
    groups = defaultdict(list)
    for r in rows:
        groups[(r["kind"].strip().lower(), int(r["channel"]))].append(
            (float(r["reading"]), float(r["reference"])))
    commands, report, passed = [], [], True

    for ch in range(1, 5):
        pts = groups.get(("tap", ch))
        if not pts:
            continue
        gain, offset = line_fit([p[0] for p in pts], [p[1] for p in pts])
        worst = max(abs(gain * x + offset - y) for x, y in pts)
        ok = worst <= TAP_LIMIT_V
        passed &= ok
        commands.append(f"cal tap {ch} {gain:.6f} {offset:.5f}")
        report.append(f"tap {ch}: gain {gain:.5f}, offset {offset * 1000:+.1f} mV, worst error "
                      f"{worst * 1000:.1f} mV over {len(pts)} points -> {'PASS' if ok else 'FAIL'}")

    pts = groups.get(("current", 1))
    if pts:
        amps_raw = [p[0] * 1e-6 / shunt_ohm for p in pts]
        gain, offset = line_fit(amps_raw, [p[1] for p in pts])
        worst_ok = True
        worst = 0.0
        for x, (_, ref) in zip(amps_raw, pts):
            err = abs(gain * x + offset - ref)
            worst = max(worst, err)
            worst_ok &= err <= max(CURRENT_LIMIT_FRAC * abs(ref), CURRENT_LIMIT_A)
        passed &= worst_ok
        commands.append(f"cal shunt {shunt_ohm:.6f} {gain:.5f} {offset:.4f}")
        sign = "" if gain > 0 else " (negative gain: the shunt sense leads are reversed)"
        report.append(f"current: gain {gain:.4f}, offset {offset * 1000:+.1f} mA, worst error "
                      f"{worst * 1000:.1f} mA -> {'PASS' if worst_ok else 'FAIL'}{sign}")

    for ch in range(1, 6):
        pts = groups.get(("ntc", ch))
        if not pts:
            continue
        diffs = [ref - x for x, ref in pts]
        offset = sum(diffs) / len(diffs)
        spread = max(diffs) - min(diffs)
        commands.append(f"cal ntc {ch} {offset:.2f}")
        note = "" if spread <= 0.3 else \
            " - the error changes with temperature: check the 3.3 V rail (cal vref) and the bead type"
        report.append(f"NTC{ch}: offset {offset:+.2f} C, spread between points {spread:.2f} C{note}")
    return commands, report, passed


def main(argv=None):
    ap = argparse.ArgumentParser(description="Gate 1 calibration")
    ap.add_argument("csv", help="readings: kind,channel,reading,reference")
    ap.add_argument("--shunt-ohm", type=float, default=0.005)
    args = ap.parse_args(argv)
    with open(args.csv, newline="") as f:
        rows = list(csv.DictReader(f))
    commands, report, passed = calibrate(rows, args.shunt_ohm)
    if not commands:
        sys.exit("no tap, current or ntc rows found")
    print("\n".join(report))
    print("\nStore on the ESP32 (console):")
    print("\n".join("  " + c for c in commands))
    print("\nGate 1 limits:", "PASS" if passed else "FAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
