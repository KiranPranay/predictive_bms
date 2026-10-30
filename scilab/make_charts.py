"""Charts of the Xcos results for the build guide.

    python3 scilab/make_charts.py

Run check_models.sce in Scilab first: it writes build/scilab/results.json and the time series.
This script copies the results to docs/build-guide/scilab/results.json and draws
docs/build-guide/figures/xcos-temperatures.svg and xcos-abnormal-heat.svg.
"""

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "kicad"))

from run_sims import SERIES, chart  # noqa: E402  (the same chart style as the KiCad section)

BUILD = ROOT / "build" / "scilab"
DOCS = ROOT / "docs" / "build-guide"


def read_csv(path):
    rows = [list(map(float, line.split(","))) for line in path.read_text().splitlines() if line.strip()]
    return [list(col) for col in zip(*rows)]


def main():
    res = json.loads((BUILD / "results.json").read_text())
    (DOCS / "scilab").mkdir(parents=True, exist_ok=True)
    (DOCS / "scilab" / "results.json").write_text(json.dumps(res, indent=2) + "\n", encoding="utf-8")

    t, tc, ts, tc_est, q, q_est, _, _ = read_csv(BUILD / "model_b.csv")
    minutes = [x / 60 for x in t]
    tp, tf = res["predictive_trip_s"] / 60, res["fixed_trip_s"] / 60
    chart(DOCS / "figures" / "xcos-temperatures.svg",
          "Xcos: cell temperatures, 3 A load, 1 W of abnormal heat from minute 10",
          "time (min)", "temperature (°C)",
          [("core, true", minutes, tc, SERIES[1], False, False),
           ("surface (NTC)", minutes, ts, SERIES[0], False, False),
           ("core, estimated", minutes, tc_est, SERIES[2], True, False)],
          (0, 60), (20, 70), hlines=[(55, "fixed limit, 55 °C")],
          vlines=[(tp, f"predictive trip, {tp:.1f} min"), (tf, f"fixed-limit trip, {tf:.1f} min")])
    chart(DOCS / "figures" / "xcos-abnormal-heat.svg",
          "Xcos: abnormal heat, true and estimated by the observer",
          "time (min)", "abnormal heat (W)",
          [("true (the fault)", minutes, q, SERIES[1], False, False),
           ("estimated by the observer", minutes, q_est, SERIES[0], True, False)],
          (0, 60), (-0.1, 1.2), hlines=[(0.75, "trip level, 0.75 W")],
          vlines=[(tp, f"predictive trip, {tp:.1f} min")])
    print("wrote", DOCS / "scilab" / "results.json")


if __name__ == "__main__":
    main()
