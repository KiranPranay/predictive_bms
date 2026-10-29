"""Tests of the Python tools.

    .venv/bin/python -m unittest discover -s tools/tests

The fit and server tests need the PC build (build/host/bms_sim); the fit test also needs numpy
and scipy. Each test is skipped, with the reason, when its need is missing.
"""

import contextlib
import io
import json
import pathlib
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

sys.path.insert(0, str(ROOT / "docs" / "build-guide"))

import boards  # noqa: E402
import calibrate  # noqa: E402
import ocv_table  # noqa: E402
import sim_server  # noqa: E402

SIM = sim_server.default_sim()


def quiet(fn, *args):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args)


class CalibrateTest(unittest.TestCase):
    def test_recovers_gain_and_offset_and_checks_gate1(self):
        gain, offset = 6.912, 0.004
        rows = [{"kind": "tap", "channel": "2", "reading": str((v - offset) / gain),
                 "reference": str(v)} for v in (0.0, 4.2, 8.4, 12.6, 16.8)]
        rows += [{"kind": "current", "channel": "1", "reading": str(a * 0.005e6 / 1.01),
                  "reference": str(a)} for a in (-1, -0.5, -0.25, 0.25, 0.5, 1)]
        rows += [{"kind": "ntc", "channel": "3", "reading": "24.6", "reference": "25.0"},
                 {"kind": "ntc", "channel": "3", "reading": "44.7", "reference": "45.0"}]
        commands, report, passed = calibrate.calibrate(rows)
        self.assertTrue(passed, report)
        self.assertIn("cal tap 2 6.912000 0.00400", commands)
        self.assertTrue(any(c.startswith("cal shunt 0.005000 1.01000") for c in commands))
        self.assertIn("cal ntc 3 0.35", commands)

    def test_fails_a_channel_outside_20_mv(self):
        rows = [{"kind": "tap", "channel": "1", "reading": str(v / 6.9),
                 "reference": str(v + (0.06 if v == 8.4 else 0.0))} for v in (0, 4.2, 8.4, 12.6, 16.8)]
        _, _, passed = calibrate.calibrate(rows)
        self.assertFalse(passed)


class BoardsTest(unittest.TestCase):
    def test_both_boards_join_every_net_without_shorts(self):
        for make in boards.BOARDS:
            nets = boards.check(make())
            self.assertIn("GND", nets)

    def test_a_short_is_caught(self):
        b = boards.board_a()
        b.run("GND", (17, 20), (16, 20))   # 3V3 bus to a free pad...
        b.run("GND", (16, 20), (15, 20))   # ...and on to the GND bus
        with self.assertRaisesRegex(ValueError, "short"):
            boards.check(b)

    def test_an_open_net_is_caught(self):
        b = boards.board_b()
        # Remove the bare run that joins the INA226's SDA pin to the two SDA links.
        b.bare = [w for w in b.bare if not (w[0] == "SDA" and w[1][0] == (24, 21))]
        with self.assertRaisesRegex(ValueError, "not joined"):
            boards.check(b)


class OcvTableTest(unittest.TestCase):
    def test_slope_from_pauses(self):
        # 0.2 V over a third of the charge: 0.6 V per unit, the 6 mV per % of mid-charge NMC.
        table = ocv_table.slopes([(3.6, 0), (3.8, 1100)], 3300)
        self.assertEqual(len(table), 1)
        self.assertAlmostEqual(table[0][0], 3.7)
        self.assertAlmostEqual(table[0][1], 0.6, places=6)


@unittest.skipUnless(SIM.exists(), "build/host/bms_sim is not built")
class FitThermalTest(unittest.TestCase):
    def test_fit_from_the_simulated_gate9_log_predicts_and_passes_the_scenarios(self):
        try:
            import fit_thermal
        except ImportError as e:
            self.skipTest(f"numpy or scipy missing: {e}")
        with tempfile.TemporaryDirectory() as d:
            log = pathlib.Path(d) / "gate9.csv"
            subprocess.run([str(SIM), "run", "fit_log", "--csv", str(log), "--quiet"],
                           check=True, stdout=subprocess.DEVNULL)
            res = quiet(fit_thermal.main, [str(log)])
        self.assertTrue(res["converged"])
        for rms in res["rms_c"]:
            self.assertLess(rms, 0.05)
        # The fitted model, loaded into the supervisor, must still meet the Gate 9 criteria and
        # catch the Gate 11 faults.
        values = [res["c_core"], res["c_surf"], res["r_core"]] + res["r_air"]
        for name in ("discharge_steps", "charge", "heat_no_current", "soft_short", "ntc_lift_off",
                     "small_fault"):
            out = subprocess.run([str(SIM), "run", name, "--thermal"] + [f"{v:.5g}" for v in values],
                                 capture_output=True, text=True)
            self.assertEqual(out.returncode, 0, out.stdout)


@unittest.skipUnless(SIM.exists(), "build/host/bms_sim is not built")
class SimServerTest(unittest.TestCase):
    def test_serves_dashboard_state_and_commands(self):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        proc = subprocess.Popen([sys.executable, str(ROOT / "tools" / "sim_server.py"),
                                 "--port", str(port), "--speed", "20"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            base = f"http://127.0.0.1:{port}"
            state = None
            for _ in range(50):
                try:
                    with urllib.request.urlopen(base + "/api/state", timeout=1) as r:
                        state = json.loads(r.read())
                    if state.get("state") == "run":
                        break
                except OSError:
                    pass
                time.sleep(0.2)
            self.assertIsNotNone(state)
            self.assertEqual(len(state["cells"]), 4)
            self.assertIn("sim", state)
            req = urllib.request.Request(base + "/sim", data=b"load 1.5", method="POST")
            with urllib.request.urlopen(req, timeout=2) as r:
                self.assertIn("load 1.5", r.read().decode())
            with urllib.request.urlopen(base + "/", timeout=2) as r:
                self.assertIn(b"Predictive BMS", r.read())
            self.assertIn("fixed", state["sim"])   # the fixed-limit twin
            self.assertIn("epoch", state["sim"])
            report = {}
            for _ in range(60):
                with urllib.request.urlopen(base + "/api/scenarios", timeout=2) as r:
                    report = json.loads(r.read())
                if report.get("status") == "done":
                    break
                time.sleep(0.5)
            self.assertEqual(report.get("status"), "done")
            self.assertEqual(len(report["results"]), 30)
            self.assertTrue(all(x["pass"] for x in report["results"]))
        finally:
            proc.terminate()
            proc.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
