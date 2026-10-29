#!/usr/bin/env python3
"""Gate 10: the dOCV/dSOC table for the rest leak estimate (architecture 9.5).

During the first controlled charge, pause for 30 minutes at about 3.6, 3.8 and 4.0 V per cell
(Gate 10 step 8). At each pause record the rested cell voltage and the charge put in so far:

    v_rest,charge_mah
    3.598,0
    3.801,1210
    4.002,2350

The slope between two pauses is dOCV/dSOC = dV / (dQ / capacity), stored at the middle voltage.
More pauses give a better table; the firmware holds up to 8 points.

    python3 tools/ocv_table.py pauses.csv [--capacity-mah 3300]

Prints the console command that stores the table. Only the Python standard library is needed.
"""

import argparse
import csv
import sys


def slopes(points, capacity_mah):
    pts = sorted(points)
    out = []
    for (v0, q0), (v1, q1) in zip(pts, pts[1:]):
        dq = q1 - q0
        if dq <= 0:
            raise ValueError(f"charge does not rise between {v0} V and {v1} V")
        out.append((0.5 * (v0 + v1), (v1 - v0) / (dq / capacity_mah)))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Gate 10 OCV slope table")
    ap.add_argument("csv", help="pauses: v_rest,charge_mah")
    ap.add_argument("--capacity-mah", type=float, default=3300.0,
                    help="cell capacity; the architecture uses the 3.3 Ah label")
    args = ap.parse_args(argv)
    with open(args.csv, newline="") as f:
        pts = [(float(r["v_rest"]), float(r["charge_mah"])) for r in csv.DictReader(f)]
    if len(pts) < 2:
        sys.exit("at least two pauses are needed")
    table = slopes(pts, args.capacity_mah)
    if len(table) > 8:
        sys.exit("the firmware holds 8 points; use fewer pauses")
    for v, s in table:
        print(f"  {v:.3f} V: {s:.3f} V per unit charge ({s * 10:.1f} mV per 1 %)")
    print("\nStore on the ESP32 (console):")
    print("  model ocv " + " ".join(f"{v:.3f} {s:.4f}" for v, s in table))
    return 0


if __name__ == "__main__":
    sys.exit(main())
