#!/usr/bin/env python3
"""Builds the build guide: docs/build-guide/build-guide.html and Build-Guide.pdf.

    python3 docs/build-guide/build_guide.py            (figures, HTML and PDF)
    python3 docs/build-guide/build_guide.py --no-pdf   (figures and HTML only)

The board drawings, placement and wiring lists and continuity checks all come from boards.py,
which is checked for shorts and open nets first. The PDF is printed by Google Chrome or
Chromium (headless); set CHROME to its path if it is not found. Standard library only.
"""

import argparse
import csv
import datetime
import html
import json
import os
import pathlib
import shutil
import subprocess
import sys
from collections import Counter, defaultdict

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))

import boards as bd  # noqa: E402
import figures  # noqa: E402

E = html.escape


def table(head, rows, cls=""):
    out = [f'<table class="{cls}"><thead><tr>' + "".join(f"<th>{E(h)}</th>" for h in head) + "</tr></thead><tbody>"]
    for r in rows:
        out.append("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>")
    out.append("</tbody></table>")
    return "\n".join(out)


def fig(src, caption, cls=""):
    return f'<figure class="{cls}"><img src="{src}" alt="{E(caption)}"><figcaption>{caption}</figcaption></figure>'


def hole(h):
    return f"({h[0]}, {h[1]})"


# --------------------------------------------------------------------------------------------
# Generated tables.

def placement_rows(board):
    rows = []
    for p in board.parts:
        pins = p["pins"]
        if p["kind"] == "esp32":
            used = [f"{l} {hole(h)}" for l, h, n in pins if n != "NC"]
            where = "top row r = 2, bottom row r = 12, columns 1–15; used pins: " + ", ".join(used)
        else:
            where = " · ".join(f"{E(l)} {hole(h)}" for l, h, _ in pins)
        rows.append([f"<b>{E(p['ref'])}</b>", E(p["value"]), where, E(p.get("note", ""))])
    return rows


def wiring_rows(board):
    rows = []
    n = 0
    for net, holes in board.bare:
        n += 1
        a, b = holes[0], holes[-1]
        straight = len({h[0] for h in holes}) == 1 or len({h[1] for h in holes}) == 1
        via = "" if straight else " via " + ", ".join(hole(h) for h in holes[1:-1])
        rows.append([str(n), "bare", f'<span class="net" style="color:{figures.net_color(net)}">{E(net)}</span>',
                     f"{hole(a)} → {hole(b)}{via}", f"{len(holes) - 1}"])
    for net, a, b in board.jumpers:
        n += 1
        dist = ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5 * 2.54
        rows.append([str(n), "insulated", f'<span class="net" style="color:{figures.net_color(net)}">{E(net)}</span>',
                     f"{hole(a)} → {hole(b)}", f"cut {dist + 15:.0f} mm"])
    return rows


def continuity_rows(board):
    """For every net, the connector and module pins a meter must find joined."""
    by_net = defaultdict(list)
    for p, label, h, net in board.pins():
        if net == "NC" or p["kind"] in ("res", "cap", "diode", "led"):
            continue
        by_net[net].append(f"{p['ref']} {label}")
    rows = []
    for net in sorted(by_net):
        pins = by_net[net]
        if len(pins) > 1:
            rows.append([f'<span class="net" style="color:{figures.net_color(net)}">{E(net)}</span>',
                         E(", ".join(pins)), "0 Ω (beeps)"])
    return rows


def parts_count(make_boards):
    count = Counter()
    for b in make_boards:
        for p in b.parts:
            if p["kind"] in ("res", "cap", "led", "diode"):
                count[(p["kind"], p["value"])] += 1
    return count


def bom_rows():
    rows, total = [], 0.0
    with open(ROOT / "docs" / "architecture" / "bom.csv", newline="") as f:
        for r in csv.DictReader(f):
            if float(r["Design Qty"] or 0) <= 0:
                continue
            line = float(r["Line total (INR)"] or 0)
            total += line
            rows.append([r["Item"], E(r["Part"]), E(r["Specification"]), f'{E(r["Design Qty"])} {E(r["Unit"])}',
                         f"₹{line:,.2f}", E(r["Status"])])
    return rows, total


# --------------------------------------------------------------------------------------------
# Snapshots of the simulation (written by snapshots.py).

def snapshot_results():
    p = HERE / "snapshots" / "results.json"
    if p.exists():
        return json.loads(p.read_text())
    return None


def kicad_results():
    p = HERE / "kicad-sim" / "results.json"
    return json.loads(p.read_text()) if p.exists() else None


def octave_results():
    p = HERE / "matlab" / "crosscheck.json"
    return json.loads(p.read_text()) if p.exists() else None


def kicad_checks_table(k):
    if not k:
        return "<p>Run <code>python3 kicad/run_sims.py</code> to add the circuit simulation results.</p>"
    rows = [[E(c["circuit"]), E(c["check"]), E(f"{c['value']:g}" if isinstance(c["value"], (int, float)) else str(c["value"])),
             E(c["limit"]), "pass" if c["pass"] else "<b>FAIL</b>"] for c in k["checks"]]
    return table(["Circuit", "Check", "Result", "Limit or unit", ""], rows)


def octave_table(oc):
    if not oc:
        return "<p>Run <code>crosscheck</code> in Octave (matlab/README.md) to add the cross-check results.</p>"
    rows = [[f"<code>{E(r['scenario'])}</code>", f"{r['rows_compared']:,}", f"{r['max_dtc_c']:.4f} °C",
             f"{r['max_dq_w']:.4f} W", "agree" if r["pass"] else "<b>differ</b>"] for r in oc["results"]]
    return table(["Scenario", "Samples compared", "Largest core-temperature difference",
                  "Largest abnormal-heat difference", "Result"], rows)


def demo_table(res):
    if not res:
        return "<p>Run <code>snapshots.py</code> to add the demonstration results.</p>"
    names = {"normal": "Normal use", "heat": "Heat with no current", "defect": "A cell that overheats under load",
             "short": "Soft internal short (Gate 11)", "runaway": "Thermal runaway onset",
             "sensor": "A temperature sensor lifts off", "hot": "Hot day, high current",
             "overcharge": "One cell reaches 4.15 V", "crash": "Controller crash"}
    rows = []
    for k, title in names.items():
        r = res["results"].get(k)
        if not r:
            continue
        lines = [ln.strip() for ln in r["result"].splitlines() if ln.strip() and not ln.startswith("The simulation")]
        lines = [ln for ln in lines if ln != "Result"]
        rows.append([f"<b>{E(title)}</b>", "<br>".join(E(x) for x in lines)])
    return table(["Demonstration", "What the simulator showed"], rows, "demo")


# --------------------------------------------------------------------------------------------

CSS = """
@page { size: A4; margin: 15mm 14mm 17mm 14mm;
  @bottom-left { content: "Predictive BMS · build guide"; font: 8.5pt 'Liberation Sans', Arial, sans-serif; color: #888; }
  @bottom-right { content: "page " counter(page) " of " counter(pages); font: 8.5pt 'Liberation Sans', Arial, sans-serif; color: #888; } }
@page :first { @bottom-left { content: none; } @bottom-right { content: none; } }
* { box-sizing: border-box; }
body { font: 10pt/1.42 'Liberation Sans', Arial, Helvetica, sans-serif; color: #1d1d1b; margin: 0; }
h1 { font-size: 20pt; margin: 0 0 4mm; }
h2 { font-size: 15pt; margin: 0 0 3mm; padding-bottom: 1.5mm; border-bottom: 1.5px solid #2a78d6; break-after: avoid; }
h3 { font-size: 11.5pt; margin: 5mm 0 2mm; break-after: avoid; }
p { margin: 0 0 2.4mm; }
ul, ol { margin: 0 0 3mm; padding-left: 6mm; }
li { margin-bottom: 1mm; }
section { break-before: page; }
section.flow { break-before: auto; margin-top: 6mm; }
figure { margin: 3mm 0 4mm; break-inside: avoid; text-align: center; }
figure img { max-width: 100%; max-height: 235mm; border: 1px solid #ddd; }
figure.snap img { max-height: 120mm; }
figure.kicad img { max-width: 100%; }
figure.chart img { width: 86%; border: none; }
figcaption { font-size: 8.8pt; color: #4f4d48; margin-top: 1.5mm; text-align: left; }
table { border-collapse: collapse; width: 100%; font-size: 8.6pt; margin: 2mm 0 4mm; }
thead { display: table-header-group; }
tr { break-inside: avoid; }
th { background: #eef4fb; text-align: left; padding: 1.4mm 1.6mm; border-bottom: 1px solid #9db8dc; }
td { padding: 1.1mm 1.6mm; border-bottom: 1px solid #e3e0d6; vertical-align: top; }
table.demo td:first-child { width: 32%; }
.net { font-weight: bold; }
.note, .safety { break-inside: avoid; }
.note { background: #fff7e6; border-left: 3px solid #e07b00; padding: 2mm 3mm; margin: 2mm 0 4mm; font-size: 9.2pt; }
.safety { background: #fdeceb; border-left: 3px solid #d03b3b; padding: 2mm 3mm; margin: 2mm 0 4mm; font-size: 9.2pt; }
.cover { height: 260mm; display: flex; flex-direction: column; justify-content: space-between; }
.cover .top { margin-top: 30mm; }
.cover .title { font-size: 28pt; font-weight: bold; line-height: 1.15; margin-bottom: 6mm; }
.cover .sub { font-size: 15pt; color: #2a78d6; margin-bottom: 14mm; }
.cover .meta { font-size: 11pt; line-height: 1.7; }
.cover .foot { font-size: 9pt; color: #4f4d48; border-top: 1px solid #ccc; padding-top: 3mm; }
.toc { columns: 2; font-size: 10.5pt; }
.toc li { margin-bottom: 1.5mm; }
code { font-family: 'Liberation Mono', monospace; font-size: 9pt; background: #f3f2ee; padding: 0 1mm; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 4mm; }
"""


def build_html(snap):
    a, b = bd.board_a(), bd.board_b()
    for x in (a, b):
        bd.check(x)
    count = parts_count([a, b])
    bom, bom_total = bom_rows()
    res = snapshot_results()
    kres, oc = kicad_results(), octave_results()
    kr = kres["results"] if kres else None
    built = datetime.date.today().strftime("%d %B %Y").lstrip("0")
    snaps = HERE / "snapshots"

    def snapfig(name, caption):
        if (snaps / name).exists():
            return fig(f"snapshots/{name}", caption, "snap")
        return f"<p><i>Snapshot {E(name)} not yet taken: run snapshots.py.</i></p>"

    passives = []
    labels = {"res": "Resistor 1/4 W 1 % metal film", "cap": "Ceramic capacitor", "led": "LED", "diode": "Clamp diode"}
    for (kind, value), n in sorted(count.items()):
        note = {"330k": "kit (BOM item 10): check the value is in it", "56k": "kit (BOM item 10): check the value is in it",
                "10k": "kit (BOM item 10)", "330R": "kit; any value that gives a few mA in the LED",
                "100n": "BOM item 11", "red LED": "stock (BOM item 25)",
                "clamp (TBD)": "BOM item 11: chosen after the Gate 1 leakage test"}.get(value, "")
        passives.append([E(labels[kind]), E(value), str(n), E(note)])
    passives.append(["Resistor 1/4 W (tap entry, at the pack end)", "1–10 kΩ, e.g. 10k", "4", "kit (section 11)"])

    hardware = [
        ["Female header 1 × 15, 2.54 mm", "2", "ESP32 DevKit sockets (board B, U1)"],
        ["Female header 1 × 10, 2.54 mm", "1", "ADS1115 socket (board A, J2)"],
        ["Female header 1 × 8, 2.54 mm", "1", "INA226 socket (board B, J8)"],
        ["Male header strip, 2.54 mm", "1 strip (40 pins)", "J3, J7 (4 each), J5 (4), J6 (3), J14 (2), and spares"],
        ["JST-XH 2-pin plug and socket with lead", "5", "NTC1–NTC5 (board B, J9–J13)"],
        ["JST-XH 5-pin plug and socket with lead", "1", "tap harness (board A, J1); BOM item 18 has 4"],
        ["Screw terminal, 2-pin, 5.08 mm", "1", "5 V in (board B, J4)"],
        ["Female–female jumper leads, 20 cm", "1 set (about 15)", "board A ↔ B link, relay inputs, buzzer"],
        ["Tinned copper wire, 0.5–0.6 mm (or resistor offcuts)", "about 1 m", "bare runs and bridges on both boards"],
        ["Insulated hook-up wire, 24–30 AWG", "about 2 m", "the insulated links (35 on both boards)"],
        ["Heat-shrink, 2–3 mm", "1 m", "tap-entry resistors and NTC leads"],
        ["M3 nylon standoffs and screws", "8", "both boards (part of BOM item 24)"],
    ]

    connectors = [[f"<b>{E(x)}</b>", E(y)] for x, y in a.off] + [[f"<b>{E(x)}</b>", E(y)] for x, y in b.off]

    gates = [
        ["0", "Design frozen", "Build the firmware once; measure the charger plug", "every part has a purpose and rating"],
        ["1", "Sensing, no cells", "<code>raw</code>, <code>cal</code>, tools/calibrate.py", "taps ±20 mV; current ±2 % or ±20 mA; every NTC fault detected"],
        ["2", "Relays fail-safe", "bench build: <code>sim on</code>, <code>test hang</code>, <code>test crash</code>", "both contacts open on power-off, boot, reset, watchdog, I2C loss"],
        ["3", "BMS harness", "bench channels; <code>status</code>", "tap order and polarity; each cutoff opens only its branch"],
        ["4", "Cell matching", "<code>model r0 …</code>", "20 mV, 3 % capacity, 10 % resistance"],
        ["5–7", "Mechanics, weld, pack", "none", "no conductor can rub a cell; sound welds"],
        ["8", "First power-up", "<code>status</code>, tools/serial_log.py", "stable readings at rest for 30 min"],
        ["9", "Controlled discharge", "tools/fit_thermal.py, <code>model thermal …</code>", "abnormal heat < 0.25 °C/min; 5-min error ≤ 0.5 °C RMS"],
        ["10", "Controlled charge", "tools/ocv_table.py, <code>model ocv …</code>", "no unexpected 4.15 V; CC/CV taper"],
        ["11", "Predictive layer", "<code>bms_sim run all</code>; dummy heater; 47 Ω soft short", "warnings and trips as the architecture says"],
        ["12", "Enclosure and release", "normal build, model fitted", "every gate signed; guide accepts"],
    ]

    resist_a = [
        ["J1 B1 → J3 GND (and B2, B3, B+ on their channels)", "386 kΩ", "330 kΩ + 56 kΩ"],
        ["J1 B1 → J1 B2 (and each neighbouring pair)", "772 kΩ", "no tap is shorted to another"],
        ["J2 A0 → J3 GND (and A1, A2, A3)", "66 kΩ", "10 kΩ + 56 kΩ"],
        ["J1 B1 → J2 A0", "340 kΩ", "330 kΩ + 10 kΩ"],
        ["J3 3V3 → J3 GND", "open", "before the clamps are fitted"],
        ["J1 B− → anything", "open", "B− is not connected on the board"],
    ]
    resist_b = [
        ["J7 3V3 → J7 GND, J4 +5V → J4 GND, J4 +5V → J7 3V3", "open", "no short between supplies"],
        ["J9 T → J7 3V3 (and J10–J13 T)", "10 kΩ", "NTC pull-ups R1–R5"],
        ["J5 IN1 → J7 3V3, J5 IN2 → J7 3V3", "10 kΩ", "relay pull-ups R6, R7"],
        ["J6 I/O → J6 GND, meter on diode test (red on I/O)", "about 2 V (1.8–2.4 V)", "the LED's forward voltage plus R8 (the LED may glow)"],
        ["J14 IN+ → J14 IN−", "open", "the sense pair is not shorted"],
    ]

    body = f"""
<div class="cover">
  <div class="top">
    <div class="title">Predictive Thermal Battery Management System for Li-ion Battery Packs</div>
    <div class="sub">Build guide: circuits, single-line diagram, wiring, component placement, assembly, and the simulation in the project simulator, KiCad and GNU Octave</div>
    <div class="meta">
      Major project · Department of EEE<br>
      BVRIT HYDERABAD College of Engineering for Women<br>
      Muskan Sulathana · Roll No. 23WH1A0208<br>
      Guide: Dr. M. Rupesh, Associate Professor<br><br>
      Design basis: architecture revision 2.2 (24 October 2026)<br>
      Built {E(built)} from the predictive_bms repository
    </div>
  </div>
  <div class="foot">The prototype is built from off-the-shelf modules on two perfboards; no PCB is made.
  Every simulator result in this guide comes from an illustrative cell model, not from the project's cells:
  the real values are measured at the build gates named beside them.</div>
</div>

<section>
<h2>Contents</h2>
<ol class="toc">
<li>How to use this guide</li><li>The system at a glance</li><li>Single-line diagram</li>
<li>Circuit diagrams</li><li>ESP32 pin map</li><li>Components</li><li>Wiring between the units</li>
<li>Board A: cell-tap sensing</li><li>Board B: ESP32, temperatures, current, relays</li>
<li>Module pin orders</li><li>Enclosure layout</li><li>Assembly, step by step</li>
<li>Checks before power</li><li>Bring-up, gate by gate</li><li>The simulation</li>
<li>Circuit and model simulation in KiCad and GNU Octave</li><li>Safety rules</li>
</ol>
<h3>1. How to use this guide</h3>
<ul>
<li>Build in the order of section 12, and follow the gates of the safe build sequence (section 14). No lithium cell is
connected before Gate 3.</li>
<li>Holes are named by column and row, <b>(c, r)</b>, counted from 0 at the top-left corner of the component side.
Column 0 is on the left; on the underside drawings it is on the right, because the board is turned over.</li>
<li>Wire colours in the drawings mark nets, not the colour of wire to buy: red 3V3, orange 5 V, black GND, blue SDA,
amber SCL, purple taps, green ADC inputs, teal NTC lines.</li>
<li>The board layouts are generated from one description of each board, which is checked automatically: every net
is joined, and no two nets touch. The placement tables, wiring lists and continuity checks come from the same
description.</li>
<li>Generic modules differ. Before soldering a module's header, compare its printed pin names with section 10.</li>
</ul>
</section>

<section>
<h2>2. The system at a glance</h2>
<p>Two independent layers protect the pack. <b>Layer A</b> is a hardware BMS that always limits cell voltage and
current and balances the cells. <b>Layer B</b> is the ESP32 supervisor: five times a second it measures every cell
voltage, the pack current, four cell temperatures and the air temperature, runs a two-state thermal model of every
cell with a Kalman filter, and opens separate charge and load relays, latched, before a fixed limit is reached.</p>
{fig("../architecture/current-architecture.svg", "Figure 1. Architecture revision 2.2: power, protection and sensing.")}
{table(["Quantity", "Value"], [
    ["Pack", "4S1P NCR18650GA, 14.4 V nominal, 16.8 V max, 3.3 Ah (label)"],
    ["Continuous discharge", "5 A (software trip at 5.0 A); fuse 7.5 A at B+"],
    ["Charge", "isolated 16.8 V CC/CV, 1.5 A max (software trip at 1.6 A)"],
    ["Cell limits (software)", "warn 4.10 V / 3.20 V; trip 4.15 V (charge off) / 3.10 V (load off)"],
    ["Temperature limits", "charging 40 / 45 °C; discharging 50 / 55 °C; spread 7 / 10 °C"],
    ["Predictive levels", "abnormal heat 0.5 °C/min Warning, 1.0 °C/min Trip; cell difference 0.3 / 0.6 °C/min"],
    ["Hardware BMS", "OV 4.25 V, UV 2.7 V, short circuit, balance from 4.18 V at 30 mA"],
])}
</section>
<section>
<h3>How the supervisor decides</h3>
{fig("figures/firmware-flow.svg", "Figure 1a. One 5 Hz sample of the safety task, from the sensors to the relays.")}
{table(["Level", "Entered when any one of these holds", "Action"], [
    ["0 Normal", "none of the conditions below", "none"],
    ["1 Watch", "<i>thermal:</i> 5-minute forecast too low by 1.0 °C or more; abnormal heat 0.3 °C/min above the other cells for 30 s; under 10 min to the limit, or current above the safe current for 30 s. <i>Electrical:</i> leak at rest of 20 mA or more; resistance more than 30 % from its Gate 4 value", "dashboard notice and log"],
    ["2 Warning", "abnormal heat of 0.5 °C/min (about 0.4 W) for 30 s, or a thermal and an electrical Watch on the same cell", "alarm; both branches stay on"],
    ["3 Trip", "abnormal heat of 1.0 °C/min (about 0.75 W) for 10 s; 0.6 °C/min above the other cells for 10 s; self-accelerating heat while at Warning", "both relays open, latched, logged"],
])}
<p>Risk levels of architecture section 9.8. They are fixed rules, not a trained classifier, so every level can be traced
to the measurement that set it.</p>
</section>

<section>
<h2>3. Single-line diagram</h2>
{fig("figures/sld.svg", "Figure 2. Single-line diagram of the power path and the 5 V auxiliary supply.")}
<ul>
<li>The fuse sits at the pack's positive exit, then the shunt, then the branch wiring (section 11).</li>
<li>K_LOAD and K_CHARGE are normally-open contacts. Pull-ups hold both open whenever the ESP32 is reset, crashed or
unpowered.</li>
<li>The LM2596 is fed after the fuse and before the shunt. Its own current therefore does not count as pack current,
so the pack can read "at rest" (below 20 mA), which the self-discharge estimate needs.</li>
</ul>
</section>

<section>
<h2>4. Circuit diagrams</h2>
{fig("figures/circuit-taps.svg", "Figure 3. Cell-tap voltage sensing on board A.")}
</section>
<section>
{fig("figures/circuit-ntc-current.svg", "Figure 4. Temperature dividers and the current measurement on board B.")}
{fig("figures/circuit-control.svg", "Figure 5. ESP32 control: relay inputs with pull-ups, alarm buzzer and LED.")}
</section>

<section>
<h2>5. ESP32 pin map</h2>
{table(["Function", "ESP32 pin", "Board B", "Notes"], [
    ["I2C SDA", "GPIO21", "J7, J8", "ADS1115 (0x48) and INA226 (0x40)"],
    ["I2C SCL", "GPIO22", "J7, J8", "4.7 kΩ pull-ups only if the modules have none"],
    ["K_LOAD", "GPIO25", "J5 IN1", "active LOW, 10 kΩ pull-up to 3V3"],
    ["K_CHARGE", "GPIO26", "J5 IN2", "active LOW, 10 kΩ pull-up to 3V3"],
    ["Alarm buzzer and LED", "GPIO27", "J6 I/O, LED1", "steady = trip, 1 Hz = Warning"],
    ["NTC1 (cell 1)", "GPIO32 · ADC1_CH4", "J9", "ADC1 only"],
    ["NTC2 (cell 2)", "GPIO33 · ADC1_CH5", "J10", ""],
    ["NTC3 (cell 3)", "GPIO34 · ADC1_CH6", "J11", "input-only pin"],
    ["NTC4 (cell 4)", "GPIO35 · ADC1_CH7", "J12", "input-only pin"],
    ["NTC5 (air)", "GPIO36 (VP) · ADC1_CH0", "J13", "input-only pin"],
    ["Manual reset", "GPIO0 (BOOT)", "on the DevKit", "hold 3 s; or <code>reset</code> on the console"],
    ["Power", "VIN 5 V, 3V3 out", "J4, rails", "VIN from the LM2596 set to 5.00 V"],
])}
</section>

<section class="flow">
<h2>6. Components</h2>
<h3>6.1 Bill of materials (architecture BOM)</h3>
<p>Full replacement value of the active items: <b>₹{bom_total:,.2f}</b> (prices from <code>bom.csv</code>; shipping
excluded; items marked "existing stock" are owned already).</p>
{table(["#", "Part", "Specification", "Qty", "Line total", "Status"], bom)}
<h3>6.2 Passive parts on the two boards</h3>
{table(["Part", "Value", "Qty", "Source"], passives)}
<h3>6.3 Assembly hardware to add to the order</h3>
<p>These small parts are needed to build the boards as drawn and are not lines of the BOM yet.</p>
{table(["Part", "Qty", "Used for"], hardware)}
</section>

<section>
<h2>7. Wiring between the units</h2>
{fig("figures/wiring-overview.svg", "Figure 6. Every connection between the pack, the power parts, the two boards and the modules.")}
</section>
<section>
<h3>Connectors</h3>
{table(["Connector", "Goes to"], connectors)}
<div class="note">Tap harness: fit a 1–10 kΩ resistor at the pack end of each tap wire (B1, B2, B3, B+), sleeved in
heat-shrink, so a damaged wire cannot short a cell. Never hot-plug a harness that has not been measured: each
adjacent pair must read one cell voltage, rising in order. Connect B− first.</div>
</section>

<section>
<h2>8. Board A: cell-tap sensing</h2>
<p>Four identical divider channels feed the ADS1115. Parts are placed by channel, left to right in the direction of
the signal: tap in, 330 kΩ, the node, 10 kΩ and 56 kΩ, then the filter capacitor and the clamp. Two bare buses run
down the board: GND at column 15 and 3V3 at column 17.</p>
{fig("figures/board-a-top.svg", "Figure 7. Board A, component side.")}
</section>
<section>
{fig("figures/board-a-bottom.svg", "Figure 8. Board A, underside (turned over left to right).")}
<div class="note">J1 pin 1 (B−) is deliberately not connected. Joining B− to this board's ground would join B− and P−
through a thin wire and bypass the hardware BMS's switch.</div>
</section>
<section>
<h3>Board A: placement</h3>
{table(["Ref", "Part", "Pins and holes (c, r)", "Note"], placement_rows(a))}
<h3>Board A: wiring list</h3>
{table(["#", "Kind", "Net", "From → to", "Holes / length"], wiring_rows(a))}
</section>

<section>
<h2>9. Board B: ESP32, temperatures, current, relays and alarm</h2>
<p>The ESP32 sits in two 15-pin female headers with its USB end over the left edge, so the console cable fits with the
board in the case. The five NTC dividers run down the right side with their connectors on the edge; the INA226 module,
the relay and buzzer connectors and the 5 V input sit along the bottom edge.</p>
{fig("figures/board-b-top.svg", "Figure 9. Board B, component side.")}
</section>
<section>
{fig("figures/board-b-bottom.svg", "Figure 10. Board B, underside (turned over left to right).")}
</section>
<section>
<h3>Board B: placement</h3>
{table(["Ref", "Part", "Pins and holes (c, r)", "Note"], placement_rows(b))}
<h3>Board B: wiring list</h3>
{table(["#", "Kind", "Net", "From → to", "Holes / length"], wiring_rows(b))}
</section>

<section>
<h2>10. Module pin orders</h2>
{fig("figures/module-pinouts.svg", "Figure 11. The pin orders the board layouts assume.")}
<h2 style="margin-top:8mm">11. Enclosure layout</h2>
{fig("figures/enclosure.svg", "Figure 12. Vented PETG enclosure: pack bay, power side, sensing side, vent path.")}
</section>

<section>
<h2>12. Assembly, step by step</h2>
<h3>Board A</h3>
<ol>
<li>Mark the top-left corner of the component side with a pen, so the hole coordinates stay the right way round.</li>
<li>Fit and solder the low parts first: R1–R12, then C1–C4. Leave D1–D4 empty: the clamp part is chosen after the
Gate 1 leakage test.</li>
<li>Fit J1, the 1 × 10 female header J2 and the 4-pin header J3.</li>
<li>Underside: lay the two long buses (GND column 15, 3V3 column 17) as bare wire, then every bare bridge of the wiring
list, then the insulated links. Tick each line of the wiring list as you go.</li>
<li>Clean the flux off with isopropyl alcohol: residue leaks current across the 330 kΩ dividers.</li>
<li>Do the checks of section 13 before fitting the ADS1115.</li>
</ol>
<h3>Board B</h3>
<ol>
<li>Fit R1–R8, C1–C5 and LED1 (flat side, the cathode, towards column 17).</li>
<li>Fit the headers: two 1 × 15 female headers for the ESP32 (dry-fit the DevKit first: most have their rows
25.4 mm, 10 holes, apart), the 1 × 8 female header J8, J5, J6, J7, J14, the five 2-pin JST sockets and the screw
terminal J4.</li>
<li>Underside: the rails (3V3 along row 16 and column 21, GND along row 19 and column 25), then the bridges, then the
insulated links.</li>
<li>Clean the flux, then do the checks of section 13 before plugging in the ESP32 or the INA226.</li>
</ol>
<h3>Then, gate by gate</h3>
<ol>
<li>Gate 1: plug in the ESP32, the ADS1115 and the INA226, join J3 to J7, flash the firmware, calibrate (section 14).</li>
<li>Gate 2: set the LM2596 to 5.00 V with nothing connected and load-test it; then wire J4, the relay module (J5) and
the buzzer (J6).</li>
<li>Gates 3–8: the BMS harness, cell matching, welding and the first power-up, as the safe build sequence says.</li>
</ol>
</section>

<section>
<h2>13. Checks before power</h2>
<p>With a multimeter, with no modules plugged in and the clamps not fitted. A reading far from the value means a wrong
part or a missing or extra bridge: find it before going on.</p>
<h3>Board A: resistance</h3>
{table(["Between", "Expected", "Why"], resist_a)}
<h3>Board B: resistance</h3>
{table(["Between", "Expected", "Why"], resist_b)}
<h3>Continuity: every pin that must be joined</h3>
<p>Board A</p>
{table(["Net", "Pins", "Reading"], continuity_rows(a))}
<p>Board B</p>
{table(["Net", "Pins", "Reading"], continuity_rows(b))}
</section>

<section>
<h2>14. Bring-up, gate by gate</h2>
<p>The full procedure is in <code>docs/bring-up.md</code>; the pass and stop rules are in the safe build sequence.</p>
{table(["Gate", "What", "Firmware and tools", "Pass when"], gates)}
<h3>Firmware and tools</h3>
<ul>
<li>Build and flash: <code>idf.py build</code>, <code>idf.py -p PORT flash monitor</code> (ESP-IDF v5.5).</li>
<li>Serial console at 115200 baud: <code>status</code>, <code>raw</code>, <code>cal …</code>, <code>model …</code>,
<code>log 1</code>, <code>reset</code>, <code>test hang</code>, <code>test crash</code>, <code>wifi off</code>.</li>
<li>Dashboard over Wi-Fi: the ESP32's own access point "PredictiveBMS", http://192.168.4.1/. Every protection works
with Wi-Fi off.</li>
</ul>
</section>

<section>
<h2>15. The simulation</h2>
<p>Before any cell is connected, the supervisor is tested against a simulated 4S pack: the same code that runs on the
ESP32, with cells, heat, a hardware BMS, sensors with noise, and every fault Gate 11 asks for. A second copy of the
pack runs alongside with only fixed limits, as a conventional BMS has, to show what the predictive layer adds.
Start it with <code>python3 tools/demo.py</code>; it opens the dashboard in the browser.</p>
{snapfig("normal-charts.png", "Figure 13. Normal use: cell temperatures, abnormal heat near zero, and each 5-minute forecast drawn against the reading it predicted.")}
{snapfig("defect-story.png", "Figure 14. A guided demonstration: a cell defect under a 3 A load. The narration follows each step; the result is measured by the simulator.")}
</section>
<section>
{snapfig("defect-compare.png", "Figure 15. The same run against a fixed-limit BMS on the same pack: the predictive layer acts minutes earlier, with the cell far cooler.")}
{snapfig("defect-charts.png", "Figure 16. Charts of that run. The defective cell (cell 2) is cut off early and cools; the fixed-limit pack's hottest cell (dashed) climbs to 55 °C.")}
{snapfig("runaway-compare.png", "Figure 17. Thermal runaway onset (heat inside a cell that grows as it warms): the warning comes minutes before a 55 °C limit. Heat made inside a cell does not stop when the pack is disconnected; the gain is warning time.")}
</section>
<section>
{snapfig("heat-diagram.png", "Figure 18. Live system diagram after a trip: cell colours follow temperature; both relays open and latched; alarm on.")}
{snapfig("short-cells.png", "Figure 19. Cell cards at the end of the Gate 11 soft-short demonstration: the leak estimate, the energy cross-check and the confirmation on cell 2.")}
{snapfig("verification.png", "Figure 20. Verification: every scenario with its checks, run from the dashboard.")}
</section>
<section>
<h3>Results of the guided demonstrations</h3>
{demo_table(res)}
<p>The verification scenarios, all 30 of them, are listed in <code>docs/simulator.md</code>; each one rehearses a gate
test with the gate's own pass criteria.</p>
</section>

<section>
<h2>16. Circuit and model simulation in KiCad and GNU Octave</h2>
<p>Three tools check three different parts of the design, and each one is free and open source:</p>
{table(["Tool", "What it checks", "Where"], [
    ["<b>KiCad 10</b> with its simulator, <b>ngspice</b>", "The analog circuits: the cell-tap dividers and filters, the NTC dividers, the current shunt, and the cell's thermal model drawn as an electrical circuit", "<code>kicad/</code>"],
    ["<b>GNU Octave</b> (the same files run in MATLAB)", "The predictive model: the thermal model and the Kalman observer, written a second time from the firmware and compared with it sample by sample", "<code>matlab/</code>"],
    ["The project's simulator (section 15)", "The complete firmware: every limit, fault and gate scenario, on a simulated pack", "<code>host/</code>"],
])}
<p>The KiCad sheets open in KiCad 10: open the project, then <b>Inspect → Simulator</b> and run the analysis written on the
sheet. <code>python3 kicad/run_sims.py</code> runs all of them from the command line and checks the results;
the Octave scripts run with <code>octave --no-gui --eval "crosscheck"</code> in <code>matlab/</code>. KiCad's
electrical rules check finds no violation on any sheet. All results in this section are simulation results with the
part values on the sheets; the gates measure the real circuits.</p>
<h3>Simulation checks</h3>
{kicad_checks_table(kres)}
</section>

<section>
<h3>16.1 Cell taps (board A)</h3>
{fig("figures/kicad-cell-taps.svg", "Figure 21. KiCad sheet of the four cell-tap channels. V1–V4 are the cells at full charge; R13–R16 are the tap resistors at the pack. I1 stands for leakage at an ADC input.", "kicad")}
{fig("figures/sim-taps-leakage.svg", "Figure 22. Leakage at an ADC input (from the clamp diode or the ADC itself) against the error in the cell reading. Calibration removes a steady leakage, but not one that changes with temperature, so the clamp must leak well below the 49 nA that would use the whole Gate 1 limit.", "chart")}
{fig("figures/sim-taps-ac.svg", f"Figure 23. Frequency response from a tap to its ADC input. The filter passes the cell voltage and removes noise above about {kr['cell-taps']['f3db_hz']:.0f} Hz; after a step the input settles to 16-bit accuracy in {kr['cell-taps']['settle_ms_16bit']:.0f} ms, less than one 200 ms sample." if kr else "Figure 23.", "chart")}
<h3>16.2 NTC divider (board B)</h3>
{fig("figures/kicad-ntc-divider.svg", "Figure 24. KiCad sheet of one NTC divider. TH1 follows the B3950 equation at the simulation temperature, which the DC sweep steps from −20 to 100 °C.", "kicad")}
{fig("figures/sim-ntc.svg", "Figure 25. Voltage at the ESP32 ADC against the NTC's temperature. It stays in the ADC's accurate range from about 3 °C to above 100 °C; at the 45 °C and 55 °C trips it is 1.00 V and 0.76 V.", "chart")}
<h3>16.3 Current sense</h3>
{fig("figures/kicad-current-sense.svg", "Figure 26. KiCad sheet of the 5 mΩ shunt and the INA226 inputs. R2 is the module's own R100 shunt, which is removed; it is excluded from the simulation.", "kicad")}
{fig("figures/sim-current.svg", f"Figure 27. Shunt voltage from 5 A of charge to 5 A of discharge: {kr['current-sense']['sense_mv_5a']:.1f} mV at 5 A, inside the INA226's ±81.92 mV. With R100 left in place the reading is {abs(kr['current-sense']['r100_error_pct']):.2f} % low." if kr else "Figure 27.", "chart")}
<h3>16.4 The thermal model of a cell</h3>
{fig("figures/kicad-thermal-model.svg", "Figure 28. The two-node thermal model of section 9.1 as an electrical circuit: 1 V stands for 1 °C, 1 A for 1 W, 1 F for 1 J/°C and 1 Ω for 1 °C/W. I1 is 1 W of heat in the core from t = 10 s.", "kicad")}
{fig("figures/sim-thermal.svg", "Figure 29. Core and surface temperatures after 1 W starts in the core. The lines are ngspice; the dots are the Octave script, which solves the same model a second way. The two agree to 0.0002 °C. The cell needs more than an hour to settle, which is why the supervisor estimates the heat instead of waiting for a fixed limit.", "chart")}
<h3>16.5 The observer in GNU Octave</h3>
<p><code>matlab/thermal_observer.m</code> is a copy of the firmware's Kalman observer (section 9.2), written in the
<code>.m</code> language. <code>crosscheck</code> runs simulator scenarios with a log of every sample, gives the logged
current and temperatures to the Octave observer, and compares its core temperature and abnormal heat with the
firmware's. The limits are 0.01 °C and 0.002 W; the differences come from the rounding of the log.</p>
{octave_table(oc)}
{fig("matlab/crosscheck_load_defect.png", "Figure 30. The Octave observer (solid) against the firmware (dashed) on the cell-defect scenario. Top: core temperature and abnormal heat of each cell. Bottom: the differences, in thousandths of a degree and thousandths of a watt.", "chart")}
{fig("matlab/thermal_step.png", "Figure 31. The step response drawn by Octave, with the steady-state temperatures.", "chart")}
</section>

<section>
<h2>17. Safety rules</h2>
<div class="safety">
<ul>
<li>No lithium cell is connected before Gate 3. The first live power-up and the first charge are never done alone.</li>
<li>Never drive a live cell into thermal runaway, overcharge or over-discharge to prove a limit. Limits are proven with
simulated signals, the simulator, a heated dummy, and the supervised 47 Ω resistor of Gate 11.</li>
<li>Never solder to a cell terminal. Reject any cell that is swollen, dented, rusty, leaking, warm or smelling.</li>
<li>Work on a non-conductive bench with eye protection, rings and watches off, every exposed terminal covered except
the one being worked on, and a lithium-battery fire plan and sand bucket at hand.</li>
<li>The hardware BMS stays connected as the final backstop; nothing in the firmware overrides it.</li>
<li>The enclosure is vented and is not a fire enclosure: never seal it.</li>
</ul>
</div>
</section>
"""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Predictive BMS build guide</title>
<style>{CSS}</style></head><body>{body}</body></html>
"""


def find_chrome():
    for name in (os.environ.get("CHROME"), "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
                 "chrome", r"C:\Program Files\Google\Chrome\Application\chrome.exe"):
        if name and (shutil.which(name) or pathlib.Path(name).exists()):
            return shutil.which(name) or name
    return None


def main():
    ap = argparse.ArgumentParser(description="build the build guide")
    ap.add_argument("--no-pdf", action="store_true")
    args = ap.parse_args()
    figures.all_figures()
    out_html = HERE / "build-guide.html"
    out_html.write_text(build_html(None), encoding="utf-8")
    print("wrote", out_html.relative_to(ROOT))
    if args.no_pdf:
        return
    chrome = find_chrome()
    if not chrome:
        sys.exit("Chrome or Chromium is needed for the PDF; set CHROME to its path")
    pdf = HERE / "Build-Guide.pdf"
    subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-sandbox", "--no-pdf-header-footer",
                    f"--print-to-pdf={pdf}", out_html.as_uri()], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("wrote", pdf.relative_to(ROOT))


if __name__ == "__main__":
    main()
