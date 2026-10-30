"""Builds the two documents for presenting the project:

- Presentation-Guide.pdf ("START HERE"): what to install on a Windows PC, and how to show every
  part of the project, step by step, with what to say;
- Viva-Notes.pdf: the whole project in simple words, likely viva questions with answers, and a
  glossary.

    python3 docs/student/make_student_docs.py [--no-pdf]

Standard library only. The PDFs need Chrome or Chromium (set CHROME to its path if it is not
found). The numbers come from the result files in docs/build-guide/.
"""

import argparse
import html
import json
import os
import pathlib
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
BG = ROOT / "docs" / "build-guide"
E = html.escape


def load(path):
    p = BG / path
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


KICAD = (load("kicad-sim/results.json") or {}).get("results", {})
OCTAVE = load("matlab/crosscheck.json") or {}


def kv(circuit, key, fmt, default="?"):
    """A number from the KiCad results, formatted; '?' if the results are missing."""
    try:
        return fmt.format(KICAD[circuit][key])
    except (KeyError, TypeError, ValueError):
        return default


def adc_list():
    """The four ADC voltages of the cell taps at full charge, from the KiCad results."""
    try:
        return ", ".join(f"{v:.2f}" for v in KICAD["cell-taps"]["adc_v_entry_10k"])
    except (KeyError, TypeError):
        return "?"


def table(head, rows, cls=""):
    h = "".join(f"<th>{x}</th>" for x in head)
    b = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<table class="{cls}"><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table>'


def fig(src, caption, cls=""):
    return f'<figure class="{cls}"><img src="{src}"><figcaption>{caption}</figcaption></figure>'


def say(text):
    return f'<div class="say"><b>Say:</b> {text}</div>'


def note(text):
    return f'<div class="note">{text}</div>'


def steps(*items):
    return "<ol class=\"steps\">" + "".join(f"<li>{x}</li>" for x in items) + "</ol>"


CSS = """
@page { size: A4; margin: 15mm 15mm 17mm 15mm;
  @bottom-left { content: "Predictive BMS · TITLE"; font: 8.5pt 'Liberation Sans', Arial, sans-serif; color: #888; }
  @bottom-right { content: "page " counter(page) " of " counter(pages); font: 8.5pt 'Liberation Sans', Arial, sans-serif; color: #888; } }
@page :first { @bottom-left { content: none; } @bottom-right { content: none; } }
* { box-sizing: border-box; }
body { font: 10.8pt/1.5 'Liberation Sans', Arial, Helvetica, sans-serif; color: #1d1d1b; margin: 0; }
h1 { font-size: 20pt; margin: 0 0 4mm; }
h2 { font-size: 15pt; margin: 0 0 3mm; padding-bottom: 1.5mm; border-bottom: 1.5px solid #2a78d6; break-after: avoid; }
h3 { font-size: 12pt; margin: 5mm 0 2mm; break-after: avoid; }
p { margin: 0 0 2.6mm; }
ul, ol { margin: 0 0 3mm; padding-left: 6mm; }
li { margin-bottom: 1.2mm; }
section { break-before: page; }
section.flow { break-before: auto; margin-top: 6mm; }
figure { margin: 3mm 0 4mm; break-inside: avoid; text-align: center; }
figure img { max-width: 100%; max-height: 120mm; border: 1px solid #ddd; }
figure.small img { max-height: 60mm; }
figure.mid img { max-height: 88mm; }
figure.tiny img { max-height: 46mm; }
figure.chart img { width: 70%; border: none; }
figcaption { font-size: 9pt; color: #4f4d48; margin-top: 1.5mm; text-align: left; }
table { border-collapse: collapse; width: 100%; font-size: 9.4pt; margin: 2mm 0 4mm; }
thead { display: table-header-group; }
tr { break-inside: avoid; }
th { background: #eef4fb; text-align: left; padding: 1.4mm 1.8mm; border-bottom: 1px solid #9db8dc; }
td { padding: 1.2mm 1.8mm; border-bottom: 1px solid #e3e0d6; vertical-align: top; }
table.plan td:first-child { width: 17%; white-space: nowrap; }
table.trouble td:first-child { width: 36%; }
.say { background: #eef7ee; border-left: 3px solid #1baf7a; padding: 2mm 3mm; margin: 2mm 0 3.5mm; break-inside: avoid; }
.note { background: #fff7e6; border-left: 3px solid #e07b00; padding: 2mm 3mm; margin: 2mm 0 4mm; font-size: 10pt; break-inside: avoid; }
.safety { background: #fdeceb; border-left: 3px solid #d03b3b; padding: 2mm 3mm; margin: 2mm 0 4mm; break-inside: avoid; }
ol.steps > li { margin-bottom: 1.8mm; }
.cover { height: 255mm; display: flex; flex-direction: column; justify-content: space-between; }
.cover .top { margin-top: 28mm; }
.cover .kicker { font-size: 13pt; color: #2a78d6; font-weight: bold; letter-spacing: 0.5px; margin-bottom: 4mm; }
.cover .title { font-size: 27pt; font-weight: bold; line-height: 1.15; margin-bottom: 6mm; }
.cover .sub { font-size: 14pt; color: #4f4d48; margin-bottom: 12mm; }
.cover .meta { font-size: 11pt; line-height: 1.7; }
.cover .foot { font-size: 9.5pt; color: #4f4d48; border-top: 1px solid #ccc; padding-top: 3mm; }
.toc { columns: 2; font-size: 11pt; }
code, .key { font-family: 'Liberation Mono', monospace; font-size: 9.6pt; background: #f3f2ee; padding: 0 1mm; }
.qa { break-inside: avoid; margin-bottom: 3mm; }
.qa .q { font-weight: bold; }
.qa .a { margin-left: 6mm; }
dl.gloss dt { font-weight: bold; margin-top: 2mm; break-after: avoid; }
dl.gloss dd { margin: 0 0 1mm 6mm; }
.fill { background: #fff3c4; padding: 0 1mm; }
"""


def page(title, short, body):
    css = CSS.replace("TITLE", short)
    return (f'<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><title>{E(title)}</title>'
            f"<style>{css}</style></head><body>{body}</body></html>\n")


# --------------------------------------------------------------------------------------------
# 1. The presentation guide

def presentation_guide():
    adc = adc_list()
    cpath = "<span class='key'>C:\\PredictiveBMS</span>"
    body = f"""
<div class="cover">
  <div class="top">
    <div class="kicker">START HERE</div>
    <div class="title">How to present the Predictive BMS on your Windows PC</div>
    <div class="sub">Install, open, click, and what to say: the demonstration, the KiCad circuits, the Octave model
    check and the Scilab Xcos models</div>
    <div class="meta">
      Predictive Thermal Battery Management System for Li-ion Battery Packs<br>
      Muskan Sulathana · Guide: Dr. M. Rupesh
    </div>
  </div>
  <div class="foot">You do not need to write or change any program. Every part opens with a double-click or a menu,
  and runs with one button. Read this guide once with the programs open, and practise the 15-minute plan in
  section 8 two times before the review.</div>
</div>

<section>
<h2>Contents</h2>
<ol class="toc">
<li>What to install</li><li>Get the project folder ready</li><li>Part 1: the demonstration dashboard</li>
<li>Part 2: the circuits in KiCad</li><li>Part 3: the model check in GNU Octave</li>
<li>Part 4: the block diagrams in Scilab Xcos</li><li>Part 5: the Build Guide</li><li>The 15-minute presentation</li>
<li>The day before: checklist</li><li>If something goes wrong</li>
</ol>

<h3>The project in two sentences</h3>
<p>This project protects a battery pack of four lithium-ion cells. An ESP32 controller measures every cell five times a
second, uses a heat model to find heat that should not be there, and disconnects the pack early, long before the cells
reach a fixed temperature limit.</p>
<p>The hardware is not built yet. Everything you show is a <b>simulation</b>: on the computer, with the real circuit
values and the real controller program. Always say "in the simulation" when you give a result.</p>
</section>

<section>
<h2>1. What to install</h2>
<p>All the programs are free. Install them the day before, when you have good internet. They are large downloads.
During each installation, keep the default choices and click <b>Next</b> until it finishes.</p>
{table(["Program", "Where to get it", "What it is for"], [
    ["<b>KiCad 10</b>", "<b>kicad.org</b> → Download → Windows. Take the newest 10.0 version.", "The circuit diagrams, and their simulation (KiCad has a circuit simulator inside, called ngspice)."],
    ["<b>GNU Octave 10.3.0</b>", "<b>octave.org</b> → Download → Windows. Take the installer for version 10.3.0 (its file name ends with <span class='key'>-w64-installer.exe</span>).", "The heat model and its estimator, written as MATLAB-style files. Octave is the free program that runs MATLAB files."],
    ["<b>Scilab 2026.0.1</b>", "<b>scilab.org</b> → Download → Windows 64-bit installer for 2026.0.1.", "Xcos, the block-diagram tool inside Scilab. It is the free tool like Simulink."],
    ["Nothing", "—", "The demonstration dashboard. It runs from the project folder and opens in your normal web browser (Edge or Chrome)."],
])}
{note("<b>First start of KiCad.</b> The first time KiCad opens, it may ask how to set up the symbol and footprint libraries. "
      "Choose the first, default option (<i>Copy default global ... library table</i>) and click OK. This happens only once.")}
</section>

<section>
<h2>2. Get the project folder ready</h2>
<p>You get the project as one zip file, <span class="key">PredictiveBMS-Windows.zip</span>. If you need a fresh copy,
it is on the project's GitHub page, <b>github.com/KiranPranay/predictive_bms</b>, under <b>Releases</b>.</p>
{steps(
    "Right-click the zip file → <b>Properties</b>. At the bottom, tick <b>Unblock</b> (if you see it) → <b>OK</b>. "
    "This stops Windows from blocking the demonstration later.",
    "Right-click the zip file → <b>Extract All…</b> Choose a short place, for example " + cpath + " "
    "or your Desktop. Do not run anything from inside the zip: extract it first.",
    "Open the extracted folder <b>PredictiveBMS</b>. You see:")}
{table(["In the folder", "What it is"], [
    ["<b>START HERE.pdf</b>", "This guide."],
    ["<b>1 Demo - double-click.bat</b>", "Starts the demonstration dashboard (Part 1)."],
    ["<b>2 KiCad circuits</b>", "Four KiCad projects: cell-taps, ntc-divider, current-sense, thermal-model (Part 2)."],
    ["<b>3 Octave model check</b>", "The Octave files, such as thermal_step.m and crosscheck.m, and the simulator program bms_sim.exe (Part 3)."],
    ["<b>4 Scilab Xcos models</b>", "cell_thermal_model.zcos and abnormal_heat_detection.zcos (Part 4)."],
    ["<b>Documents</b>", "Build-Guide.pdf, Viva-Notes.pdf and this guide."],
    ["<b>program</b>", "Files the demonstration needs. Do not move or change them."],
])}
{note("If Windows shows a blue box, <b>Windows protected your PC</b>, when you start something from this folder: click "
      "<b>More info</b>, then <b>Run anyway</b>. The files are the project's own programs. Unblocking the zip in step 1 "
      "avoids most of these boxes.")}
</section>

<section>
<h2>3. Part 1: the demonstration dashboard</h2>
<p>The dashboard shows the whole system working on a <b>simulated pack</b>: four cells, their heat, the hardware BMS,
the sensors, and the same controller program that will run on the ESP32. A second copy of the pack runs beside it,
protected only by fixed limits, like a normal BMS. So every fault shows how much earlier this project acts.</p>
<h3>Start it</h3>
{steps(
    "Double-click <b>1 Demo - double-click.bat</b>. A black window opens. It says that the demo is running. "
    "<b>Keep this black window open</b> for the whole presentation. Closing it stops the demo.",
    "Your browser opens the dashboard by itself. If it does not, open Edge or Chrome and type "
    "<span class='key'>http://127.0.0.1:8080/</span> in the address bar.",
    "Wait a few seconds until the numbers on the page start to change.")}
<h3>What is on the page</h3>
<ul>
<li><b>Guided demonstrations</b>: nine buttons. Each button starts one story on a fresh pack. A text box tells what
is happening, step by step. It has <b>Pause</b>, <b>Restart</b> and <b>Stop</b> buttons.</li>
<li><b>Predictive layer against a fixed-limit BMS</b>: the comparison of the two packs.</li>
<li><b>Cell cards</b>: for each cell, its voltage, temperature, estimated core temperature, abnormal heat (in watts)
and its risk level.</li>
<li><b>System</b>: a live drawing of the pack, the relays and the sensors.</li>
<li><b>Charts</b>: cell temperatures, abnormal heat, and each 5-minute forecast drawn against the real reading.</li>
<li><b>Verification</b>: all 30 test scenarios with their checks, at the bottom.</li>
</ul>
{fig("../build-guide/snapshots/defect-story.png", "The dashboard during a guided demonstration (here: a cell that overheats under load).", "small")}
</section>

<section>
<h3>Show the demonstrations in this order</h3>
<p>Click one button, let it run to the end, read the result box, then click the next. Times are approximate and
change by a few seconds between runs.</p>
{table(["Order", "Button", "What happens (about how long)", "What it proves"], [
    ["1", "<b>Normal use</b>", "A 2 A load, a rest, then charging at 1.5 A (about 2 minutes). The level stays <b>Normal</b>. The 5-minute forecasts land on the real readings.", "No false alarms. The model knows how a healthy cell heats."],
    ["2", "<b>Heat with no current</b>", "1 W of heat starts inside cell 2 while no current flows (under 1 minute). The supervisor trips about 1 minute later, with the cell near 26 °C. The fixed-limit BMS does nothing.", "It finds heat that the current cannot explain, which is how an internal fault starts."],
    ["3", "<b>A cell that overheats under load</b>", "Cell 2 gets a defect under a 3 A load (under 1 minute). This project trips about 2 minutes after the fault, near 28 °C, and the cell cools. The fixed-limit BMS trips about 7 minutes after the fault, at 55 °C.", "The main result: about 5 minutes earlier and about 27 °C cooler."],
    ["4", "<b>Soft internal short (Gate 11)</b>", "A 47 Ω resistor across cell 2 at rest, like a small internal short (about 1 minute). The leak estimate finds about 73 mA, close to the 79 mA really drawn. Heat and leak agree. Level: <b>Warning</b>.", "Two independent kinds of evidence, electrical and thermal, point to the same cell."],
    ["5", "<b>Thermal runaway onset</b>", "Heat inside cell 3 that grows as the cell warms (about 1 minute). This project trips about 8 minutes after it starts, near 29 °C. The fixed-limit BMS trips almost 4 minutes later, at 55 °C.", "An early warning. Disconnecting cannot stop heat made inside a cell, so the gain is warning time."],
])}
{say("Each demonstration runs on the same controller program that will run on the ESP32. The grey dashed line is the second pack, which has only fixed limits. Look how much earlier this project acts, and how much cooler the cell is.")}
<h3>What to point at</h3>
<ul>
<li><b>Abnormal heat chart</b>: the line of the faulty cell rises above the others. 0.5 °C/min is Warning and 1.0 °C/min
is Trip.</li>
<li><b>Comparison card</b>: the trip time and the temperature of both packs, side by side.</li>
<li><b>Forecast chart</b>: for a healthy cell, the forecast made 5 minutes earlier lands on the real reading.</li>
<li><b>Latched trip</b>: after a trip, both relays stay open until a manual reset is allowed.</li>
</ul>
<p>To finish, scroll to <b>Verification</b> and click <b>Run again</b>: <b>30 of 30 pass</b>.</p>
{say("These 30 scenarios are the tests of the build gates, done in simulation before any real cell is connected. All 30 pass.")}
{note("To stop the demo, close the black window. To start again, double-click the .bat file again.")}
</section>

<section>
<h2>4. Part 2: the circuits in KiCad</h2>
<p>KiCad is the circuit design program used in industry. Here it holds four small circuits, each with its own
simulation. The part values are the ones the prototype uses. Each circuit is one folder in <b>2 KiCad circuits</b>.</p>
<h3>How to open and run any of the four</h3>
{steps(
    "In the folder, open one circuit folder, for example <b>thermal-model</b>. Double-click the file ending in "
    "<span class='key'>.kicad_pro</span>. KiCad opens.",
    "In the KiCad window, double-click the file ending in <span class='key'>.kicad_sch</span> (or click "
    "<b>Schematic Editor</b>). The circuit appears.",
    "In the Schematic Editor menu, click <b>Inspect → Simulator</b>. The simulator window opens.",
    "Click <b>Run</b> (the green triangle ▶). If a window asks for the analysis, it is already filled in from the blue "
    "command written on the sheet (for example <span class='key'>.tran 1 3610</span>): click <b>OK</b>.",
    "Click <b>Add Signals</b>, tick the signals named below, and click <b>OK</b>. The graph appears.")}
{say("This is the real circuit with the real part values, drawn in KiCad. KiCad's built-in simulator, ngspice, calculates it. KiCad's electrical rules check finds no errors.")}

<h3>Circuit 1: cell-taps (board A)</h3>
{fig("../build-guide/figures/kicad-cell-taps.svg", "The four cell-tap channels as KiCad draws them.", "small")}
<ul>
<li><b>Run:</b> this sheet uses <span class="key">.op</span>, the "operating point": the steady voltages.</li>
<li><b>Read:</b> the voltages of <b>ADC1, ADC2, ADC3, ADC4</b> in the results list: about {E(adc)} V.</li>
<li><b>Point at:</b> all four are below 3.0 V, the safe limit for the ADS1115 input (the Gate 1 stop rule).</li>
</ul>
{say("Each cell tap goes through a 330 kΩ and 56 kΩ divider, so 16.8 V becomes about 2.4 V, which the ADC can read safely. The 10 kΩ and 100 nF filter removes noise.")}
</section>

<section>
<h3>Circuit 2: ntc-divider (board B)</h3>
{fig("../build-guide/figures/kicad-ntc-divider.svg", "One NTC temperature divider.", "tiny")}
<ul>
<li><b>Run:</b> this sheet sweeps the temperature of the NTC from −20 to 100 °C (<span class="key">.dc TEMP -20 100 1</span>).</li>
<li><b>Add signal:</b> <b>V(NTC_ADC)</b>. The graph shows the ADC voltage falling as the temperature rises.</li>
<li><b>Point at:</b> {kv("ntc-divider", "v_25c", "{:.2f}")} V at 25 °C, about 1.00 V at 45 °C (the charge limit) and
about 0.76 V at 55 °C (the discharge limit).</li>
</ul>
{say("An NTC's resistance falls as it gets hotter. With a 10 kΩ resistor above it, the voltage at the ESP32 tells the temperature. It stays in the ESP32's accurate range from about 3 °C to above 100 °C.")}

<h3>Circuit 3: current-sense</h3>
{fig("../build-guide/figures/kicad-current-sense.svg", "The 5 mΩ shunt and the INA226 inputs.", "tiny")}
<ul>
<li><b>Run:</b> this sheet sweeps the pack current from −5 A (charging) to +5 A (discharging) (<span class="key">.dc I1 -5 5 0.1</span>).</li>
<li><b>Add signal:</b> the voltage across the shunt, <b>V(/SENSE_P) − V(/SENSE_N)</b>. In the simulator, use
the <b>user-defined signal</b> box (in the signals menu) and type <span class="key">V(/SENSE_P)-V(/SENSE_N)</span>.
If you cannot find it, add <b>V(/SENSE_P)</b> and <b>V(/SENSE_N)</b> and explain the small gap between them.</li>
<li><b>Point at:</b> {kv("current-sense", "sense_mv_5a", "{:.1f}")} mV at 5 A. The INA226 can read up to about 81.9 mV,
so there is a large margin. Discharge reads positive.</li>
</ul>
{say("A 5 milliohm resistor in the pack's path makes a small voltage proportional to the current. The INA226 chip reads it in both directions, charge and discharge.")}
</section>

<section>
<h3>Circuit 4: thermal-model</h3>
{fig("../build-guide/figures/kicad-thermal-model.svg", "The heat model of one cell, drawn as an electrical circuit.", "small")}
<ul>
<li><b>Run:</b> this sheet simulates one hour after 1 W of heat starts in the cell's core (<span class="key">.tran 1 3610</span>).</li>
<li><b>Add signals:</b> <b>V(/T_CORE)</b> and <b>V(/T_SURF)</b>. Here 1 volt means 1 °C.</li>
<li><b>Point at:</b> both start at 25 °C. After one hour the core is at about 54.5 °C and still rising slowly. It
would settle at 57 °C.</li>
</ul>
{say("Heat flows like current. A heat capacity behaves like a capacitor, and a thermal resistance like a resistor. So the cell's heat model is a simple RC circuit. 1 volt stands for 1 °C and 1 ampere for 1 watt. The ESP32 runs this same model five times a second.")}
{note("<b>Tip.</b> On the projector, zoom the graph with the mouse wheel, or use the View menu to zoom.")}
</section>

<section>
<h2>5. Part 3: the model check in GNU Octave</h2>
<p>GNU Octave runs MATLAB-style programs (files ending in <span class="key">.m</span>). We use it to check the heat
model and the estimator a second, independent way. The same files also run in MATLAB.</p>
<h3>Open Octave in the right folder</h3>
{steps(
    "Start <b>GNU Octave (GUI)</b> from the Start menu.",
    "Find the <b>File Browser</b> panel (on the left). Use its folder box at the top, or the <b>Current Directory</b> "
    "box above the Command Window, to go to the folder <b>3 Octave model check</b>. The panel now lists "
    "<span class='key'>thermal_step.m</span>, <span class='key'>crosscheck.m</span> and the other files.")}
<h3>Run 1: thermal_step (a few seconds)</h3>
{steps(
    "Double-click <b>thermal_step.m</b>. It opens in the Editor.",
    "Press <b>F5</b> (or click the Run button ▶ in the Editor). Another way: click in the Command Window, type "
    "<span class='key'>thermal_step</span> and press Enter.",
    "A figure opens: the core (orange) and surface (blue) temperatures over one hour after 1 W of heat. The Command "
    "Window prints the temperatures at 1, 5, 20 and 60 minutes, and the two time constants, 8.4 s and 1422 s.")}
{say("This is the same heat model as in KiCad, solved by a different method. KiCad and Octave agree to within 0.0002 °C.")}
<h3>Run 2: crosscheck (one scenario in about a minute; all four take a few minutes)</h3>
{steps(
    "In the Command Window type <span class='key'>crosscheck({{'load_defect'}})</span> and press Enter: one scenario. "
    "(<span class='key'>crosscheck</span> alone runs all four; run that the day before.)",
    "Octave starts <span class='key'>bms_sim.exe</span>, the simulator, which runs the real controller program and writes a log. "
    "Then Octave's own copy of the estimator reads the same log and calculates the same numbers.",
    "A figure opens with four panels. Top: the core temperature and the abnormal heat of each cell; the solid "
    "(Octave) and dashed (controller) lines lie on top of each other. Bottom: the difference between them: only a "
    "few thousandths of a degree and of a watt. (The same figure is in the Build Guide, section 16.5.)")}
{say("The controller's estimator was written again in Octave and given the same sensor data. Both give the same core temperature and abnormal heat, to a few thousandths. This shows the controller program does what the model says.")}
</section>

<section>
<h2>6. Part 4: the block diagrams in Scilab Xcos</h2>
<p>Xcos is the block-diagram simulator inside Scilab, the free tool like Simulink. Each model is a drawing of
blocks joined by arrows. A scope block draws the result.</p>
<h3>How to run a model</h3>
{steps(
    "Open the folder <b>4 Scilab Xcos models</b> and double-click the model file (<span class='key'>.zcos</span>). "
    "Scilab starts and Xcos opens the diagram. (If it does not: start Scilab, click <b>Applications → Xcos</b>, then "
    "<b>File → Open</b> and choose the file.)",
    "Click <b>Start</b>, the black triangle ▶ in the Xcos toolbar.",
    "Wait until the simulation ends. The scope windows open with the graphs.")}
<h3>Model 1: cell_thermal_model.zcos</h3>
<p>The heat model of one cell as blocks: 1 W of heat starts in the core at 10 s, the air is at 25 °C, and the
simulation runs for one hour. The scope shows the core and the surface temperatures. It is the same model as the
KiCad thermal-model sheet and Octave's thermal_step.</p>
<p><b>Point at:</b> <span class="fill">[[XCOS-A]]</span></p>
{say("Here the same heat model is built from blocks, as engineers do in Simulink. The heat goes in on the left, the model is in the middle, and the scope shows the temperatures.")}
<h3>Model 2: abnormal_heat_detection.zcos</h3>
<p>One cell carries 3 A. Its normal Joule heat (I²R) is known. At 10 minutes, 1 W of extra, unknown heat starts:
the "abnormal" heat. An observer block, a fixed-gain version of the controller's Kalman filter, watches only the
surface temperature and estimates the abnormal heat. Two trips are compared:</p>
<ul>
<li><b>Predictive trip</b>: when the estimated abnormal heat reaches 0.75 W (about 1 °C per minute, the
architecture's trip level);</li>
<li><b>Fixed-limit trip</b>: when the surface temperature reaches 55 °C.</li>
</ul>
<p>The scopes show the temperatures, the estimated against the true abnormal heat, and the two trip signals.</p>
<p><b>Point at:</b> <span class="fill">[[XCOS-B]]</span></p>
{say("The observer sees only the surface temperature, like the real NTC sensor. It works out how much heat is not explained by the current. The predictive trip comes long before the fixed 55 °C limit.")}
</section>

<section>
<h2>7. Part 5: the Build Guide</h2>
<p>Open <b>Documents → Build-Guide.pdf</b>. It is the full construction document. Show these sections:</p>
{table(["Section", "What to show", "What to say"], [
    ["2. The system at a glance", "The architecture drawing and the table of the pack", "Two layers protect the pack: a hardware BMS, and the ESP32 supervisor with two relays."],
    ["3. Single-line diagram", "The power path from the cells to the load and the charger", "The fuse is at the pack's positive end, then the current shunt, then the two relays."],
    ["4. Circuit diagrams", "Cell taps, NTCs, current, control", "Every value comes from the architecture document."],
    ["6. Components", "The parts list and the total cost", "The full parts list costs about ₹9,260."],
    ["8 and 9. Board A and board B", "The perfboards hole by hole", "The board drawings are checked by a program: every connection is made and nothing is shorted."],
    ["12 and 13. Assembly and checks", "The step-by-step assembly and the meter checks", "Each board is checked with a meter before any power."],
    ["14. Bring-up", "The gate table", "The build goes through Gates 0 to 12. No lithium cell is connected before Gate 3."],
    ["15 and 16. The simulation", "The demonstration pictures, the KiCad and Octave results", "All results so far are simulation results; the gates measure the real circuits."],
])}
</section>

<section>
<h2>8. The 15-minute presentation</h2>
<p>Before you start: the demo is running (black window open), KiCad has the thermal-model sheet open with its
graph ready, Octave shows the thermal_step figure, Xcos has abnormal_heat_detection open, and the Build Guide is
open. Then you only switch windows (<b>Alt + Tab</b>).</p>
{table(["Time", "Show", "Say"], [
    ["0:00–1:00", "Build Guide cover", "The title, your name, your guide. \"This project predicts heating faults in a lithium-ion pack before a fixed limit is reached.\""],
    ["1:00–2:30", "Build Guide section 2 (architecture)", "The problem: lithium-ion cells can overheat, and a fixed temperature limit acts late. The two layers: the hardware BMS always protects; the ESP32 adds the predictive layer and two relays."],
    ["2:30–3:30", "Build Guide sections 3 and 4", "The power path and the sensors: four cell voltages (ADS1115), pack current (INA226 with a 5 mΩ shunt), five temperatures (NTCs)."],
    ["3:30–4:30", "Viva Notes, the heat model (or Build Guide 16.4)", "The heat model: core and surface. The Kalman filter estimates the core temperature and the abnormal heat in watts."],
    ["4:30–9:30", "The dashboard: Normal use, Heat with no current, A cell that overheats under load, Soft internal short", "One sentence per demonstration (section 3). Point at the comparison card: about 5 minutes earlier and about 27 °C cooler."],
    ["9:30–10:30", "The dashboard: Verification", "30 of 30 test scenarios pass."],
    ["10:30–12:00", "KiCad: thermal-model graph, then cell-taps values", "The circuit values are checked in KiCad's simulator. The heat model is an RC circuit."],
    ["12:00–13:00", "Octave: the crosscheck figure", "The estimator, written again in Octave, gives the same numbers as the controller program."],
    ["13:00–14:00", "Xcos: abnormal_heat_detection", "The block diagram: the predictive trip comes long before the fixed limit."],
    ["14:00–15:00", "Build Guide section 14 (bring-up)", "What is next: build the hardware gate by gate. Safety rules. \"Thank you. I am happy to take questions.\""],
], "plan")}
{note("If time is short, skip the soft-short demonstration and the Xcos part. If there is extra time, show "
      "the Thermal runaway onset demonstration.")}
</section>

<section>
<h2>9. The day before: checklist</h2>
<ul>
<li>☐ KiCad 10, GNU Octave 10.3.0 and Scilab 2026.0.1 are installed. Each one has been opened once (KiCad's library
question is answered).</li>
<li>☐ The zip is unblocked and extracted to a short folder, for example <span class="key">C:\\PredictiveBMS</span> (not
inside OneDrive).</li>
<li>☐ The demo starts, and all five demonstrations of section 3 run to the end.</li>
<li>☐ Each of the four KiCad circuits runs, and you know which signals to add.</li>
<li>☐ In Octave, <span class="key">thermal_step</span> and the full <span class="key">crosscheck</span> have run once.</li>
<li>☐ Both Xcos models run and show their scopes.</li>
<li>☐ You have read the Viva Notes, and practised the 15-minute plan two times with a timer.</li>
<li>☐ Laptop charged; charger and HDMI adapter in the bag; the display set to <b>Duplicate</b> (Windows key + P).</li>
<li>☐ Sleep turned off (Settings → System → Power) and notifications off (Focus assist / Do not disturb).</li>
<li>☐ A copy of the whole PredictiveBMS folder on a pen drive.</li>
</ul>
<p>Nothing in the project needs the internet during the presentation.</p>
</section>

<section>
<h2>10. If something goes wrong</h2>
{table(["Problem", "What to do"], [
    ["Blue box: <b>Windows protected your PC</b>", "Click <b>More info</b>, then <b>Run anyway</b>. Next time, unblock the zip before extracting (section 2)."],
    ["The black window opens and closes at once, or says a file is missing", "Extract the whole zip first; do not run it from inside the zip. Keep the folders as they are. Antivirus may have removed a file: extract again and allow the file."],
    ["The browser does not open", "Open Edge or Chrome yourself and type <span class='key'>http://127.0.0.1:8080/</span>."],
    ["The black window shows an error about port 8080, or the page does not load", "Another demo is already running. Close every black window, wait 5 seconds, and start again. If it still fails, restart the PC."],
    ["The page is open but nothing changes", "Check that the black window is still open. Press <b>F5</b> in the browser to reload."],
    ["A demonstration seems stuck", "Click <b>Stop</b>, then click the demonstration button again."],
    ["KiCad asks about the symbol or footprint library table", "Choose the first, default option (Copy default global ... table) and click OK."],
    ["The KiCad graph is empty after Run", "No signal is added yet: click <b>Add Signals</b> and tick the signals named in section 4."],
    ["KiCad asks for the simulation command", "Type the blue command written on the sheet (for example <span class='key'>.tran 1 3610</span>) and click OK."],
    ["Octave says <span class='key'>'thermal_step' undefined</span>", "Octave is in the wrong folder. Change the Current Directory to <b>3 Octave model check</b>."],
    ["Octave's crosscheck cannot find the simulator (bms_sim.exe)", "bms_sim.exe must be in the same folder as crosscheck.m. Extract the zip again; if antivirus removed it, allow it."],
    ["Octave's crosscheck is slow", "Run only <span class='key'>crosscheck({'load_defect'})</span>, or show its figure in the Build Guide, section 16.5."],
    ["The .zcos file opens in another program", "Start Scilab, click <b>Applications → Xcos</b>, then <b>File → Open</b>."],
    ["The Xcos scope window does not appear", "Wait until the simulation ends. Look for the scope behind the Xcos window (use the taskbar). Read the Scilab console for a message, then click Start again."],
    ["Text is too small on the projector", "In the browser press <b>Ctrl</b> and <b>+</b>. In KiCad and Xcos use the mouse wheel to zoom."],
], "trouble")}
<p>If one part fails and cannot be fixed quickly, show its picture in the Build Guide (section 15 or 16) and move on.
Say: "This is the result from the same simulation."</p>
</section>
"""
    return page("Presentation guide", "START HERE", body)


# --------------------------------------------------------------------------------------------
# 2. The viva notes

QA = [
    ("Basic ideas", [
        ("What is a battery management system (BMS)?",
         "A circuit that watches a battery pack and protects it. It measures cell voltages, current and temperature, and it disconnects the pack when something is unsafe. It can also balance the cells."),
        ("Why does a lithium-ion pack need a BMS?",
         "Lithium-ion cells are damaged or become unsafe if they are charged too high, discharged too low, carry too much current or get too hot. The BMS keeps every cell inside safe limits."),
        ("What is thermal runaway?",
         "A chain of heat-making reactions inside a cell that speed up as the cell gets hotter. The heat makes more heat. It can end in fire. It cannot be stopped by disconnecting the pack, so early warning matters."),
        ("What does 4S1P mean?",
         "Four cells in series (4S) and one cell in each place (1P). The pack has four cells in one row."),
        ("What are the voltages of your pack?",
         "14.4 V nominal (4 × 3.6 V) and 16.8 V when full (4 × 4.2 V)."),
        ("What is the capacity and energy of the pack?",
         "3.3 Ah, from the cell label. That is about 47.5 Wh at the nominal voltage."),
        ("Which cell do you use?",
         "The NCR18650GA, an 18650-size NMC lithium-ion cell. 18650 means 18 mm wide and 65 mm long."),
        ("What is cell balancing?",
         "Keeping all cells at the same charge. The hardware BMS does passive balancing: above 4.18 V it bleeds about 30 mA from a cell that is ahead of the others."),
        ("What is the current limit of your prototype?",
         "5 A continuous for discharge and 1.5 A for charge. The hardware BMS board is rated 20 A, but 20 A is not the project limit."),
        ("Why is a fixed temperature limit late?",
         "A cell is large and heats slowly. Its surface needs many minutes to reach 55 °C, even when a fault is already making heat inside. By then the fault has been there a long time."),
        ("Where does heat in a cell come from?",
         "Mainly from the current flowing through the cell's internal resistance: I²R, called Joule heat. A fault, like an internal short, adds heat that the current does not explain."),
        ("What is an internal short?",
         "A small, unwanted path for current inside a cell. It drains the cell even at rest, and it heats the cell. A soft short is a weak one that grows slowly."),
    ]),
    ("The design", [
        ("Why two protection layers?",
         "So that one failure cannot remove all protection. Layer A, the hardware BMS, always works, even if the ESP32 or its program fails. Layer B, the ESP32 supervisor, adds the predictive layer and separate charge and load relays."),
        ("What does the hardware BMS do?",
         "It stops charging above about 4.25 V per cell, stops discharging below about 2.7 V per cell, protects against short circuit and over-current, and balances the cells."),
        ("Why are the relays normally open?",
         "Normally open means the contact is open when the relay has no power. If the ESP32 resets, crashes or loses power, both relays open. The safe state is the default."),
        ("Why are there pull-up resistors on the relay inputs?",
         "The relay inputs are active LOW. The 10 kΩ pull-ups keep the inputs HIGH, so the relays stay off while the ESP32 is starting or if a wire comes loose."),
        ("Why two relays, one for charge and one for load?",
         "So the supervisor can stop charging but still allow discharge, or the other way round. For example, a high cell voltage opens only the charge relay."),
        ("Why is there a fuse, and why 7.5 A?",
         "The fuse protects the wiring and the relay path from a large fault current. 7.5 A is above the 5 A working current, so it does not blow in normal use."),
        ("Why use an ADS1115 for the cell voltages?",
         "It is a 16-bit ADC: much finer and more accurate than the ESP32's own ADC. The leak estimate needs to see changes of a few millivolts."),
        ("Why a 330 kΩ and 56 kΩ divider?",
         "The top tap is up to 16.8 V, but the ADC input must stay low. The divider makes 16.8 V into about 2.44 V. High values draw very little current from the cells."),
        ("Why the 10 kΩ resistor and 100 nF capacitor?",
         "Together with the divider they form a low-pass filter. It removes fast noise and passes the slow cell voltage. In the KiCad simulation the cut-off is about 27 Hz."),
        ("What are the clamps for, and why is the part TBD?",
         "Clamps protect the ADC input from a voltage spike. Their leakage current upsets the high-value divider, so the part is chosen at Gate 1 after a leakage test. The simulation shows that every 10 nA of leakage moves a cell reading by about 4.1 mV."),
        ("How do you get each cell's voltage?",
         "The ADC measures each tap against the pack's negative end. Cell 1 is the first tap. Each other cell is the difference between two neighbouring taps."),
        ("Why NTC thermistors?",
         "They are small, cheap and respond quickly. A 10 kΩ NTC at 25 °C changes its resistance a lot with temperature, so the reading is sensitive."),
        ("Why five NTCs?",
         "One on each of the four cells, and one in free air to measure the ambient temperature. The heat model needs the air temperature."),
        ("Why only ADC1 pins for the NTCs?",
         "On the ESP32, ADC2 does not work while Wi-Fi is on. So the five NTCs use ADC1 pins, GPIO32 to GPIO36."),
        ("Why the INA226 with a 5 mΩ shunt?",
         "The INA226 measures current in both directions, charge and discharge, with fine steps of 2.5 µV. The 5 mΩ shunt gives 25 mV at 5 A and wastes only 0.125 W. It replaced the ACS712 Hall sensor in the BOM for a calibrated, bidirectional reading."),
        ("Why must the INA226 module's R100 resistor be removed?",
         "The module has its own 0.1 Ω shunt. If it stays, it carries part of the current and the reading is about 4.8 % low (KiCad simulation). The 5 mΩ external shunt replaces it."),
        ("What is Kelvin wiring?",
         "Two separate thin wires that measure the voltage right at the shunt's own pads. The big current does not flow in them, so the wire resistance does not spoil the reading."),
        ("Why is the LM2596 connected before the shunt?",
         "The LM2596 powers the electronics. If its current went through the shunt, the pack would never look at rest, and the leak estimate could never run."),
        ("Why the ESP32?",
         "It is low-cost, fast (240 MHz with a floating-point unit), has Wi-Fi for the dashboard, and enough memory. The whole predictive layer uses well under 1 % of its processor."),
        ("Why is Wi-Fi not part of the safety chain?",
         "Wi-Fi can fail. All protection works with Wi-Fi off. Wi-Fi only carries the dashboard."),
        ("Why are trips latched?",
         "A latched trip stays on until a deliberate manual reset. A fault must not clear by itself and switch the pack back on. The reset is allowed only when every cell is between 3.20 and 4.10 V, every NTC is below 40 °C, all sensors are plausible, and the cause has been clear for 60 s."),
        ("How often does the supervisor measure?",
         "Five times a second (5 Hz). Each reading goes through a median-of-5 filter to reject single bad samples."),
    ]),
    ("The predictive layer", [
        ("What makes your BMS predictive?",
         "It runs a heat model of every cell. The model says what the cell should be doing. The difference from the real reading shows heat that should not be there, long before a fixed limit."),
        ("What is abnormal heat?",
         "Heat that the cell's current cannot explain, measured in watts. For a healthy cell it is near zero, even under load. A fault makes it positive."),
        ("What is the two-state thermal model?",
         "Each cell has a core and a surface. Heat is made in the core, flows to the surface through a thermal resistance, and from the surface to the air. Each part has a heat capacity."),
        ("Why estimate the core temperature?",
         "The sensor can only touch the surface. Under load the core is hotter than the surface. The model gives the core temperature, which no sensor can measure."),
        ("What is a Kalman filter, in simple words?",
         "A method that mixes a prediction from a model with a noisy measurement, trusting each according to how reliable it is. Every sample it predicts, compares with the reading, and corrects. It also estimates things that are not measured, like the core temperature and the abnormal heat."),
        ("Why not a neural network, like the base paper?",
         "A neural network needs a lot of training data, which does not exist for our cells. A physical model needs no training, every output has a unit, and it is small enough to run on the ESP32."),
        ("What are the risk levels?",
         "0 Normal, 1 Watch (a notice), 2 Warning (alarm on, the pack keeps working), 3 Trip (both relays open and latch)."),
        ("What abnormal heat causes a Warning or a Trip?",
         "Warning: 0.5 °C/min, about 0.4 W, for 30 s. Trip: 1.0 °C/min, about 0.75 W, for 10 s."),
        ("How do you convert watts to °C per minute?",
         "Divide the heat by the cell's total heat capacity, about 45 J/°C, and multiply by 60. For example, 0.75 W ÷ 45 J/°C × 60 = 1.0 °C/min."),
        ("What is the 5-minute check?",
         "Every 10 s the supervisor predicts each cell's temperature 1 and 5 minutes ahead. When the time comes, it compares the prediction with the reading. An error of +1.0 °C or more raises Watch."),
        ("Why compare a cell with the other three?",
         "All four cells carry the same current, so their abnormal heat should match. A cell out of step with the others is suspicious, even when every value is still small."),
        ("What is self-acceleration?",
         "When abnormal heat grows as the cell gets hotter, the heat is feeding itself, as at the start of thermal runaway. If, while at Warning, the abnormal heat rises by 50 % while the core rises by 1 °C within 120 s, the supervisor trips at once."),
        ("What is the leak estimate?",
         "At rest, a cell with an internal short slowly loses voltage compared with the others. The supervisor measures this drift over 60 minutes and turns it into a leak current. 20 mA or more raises Watch."),
        ("What is the energy cross-check?",
         "A leak current I at voltage V makes heat V × I inside the cell. If this matches the abnormal heat from the thermal model, two independent methods, electrical and thermal, point to the same fault."),
        ("What is the safe continuous current?",
         "The largest current at which every cell would settle below its temperature limit. The supervisor shows it on the dashboard."),
        ("How do you detect an NTC that has come off its cell?",
         "Under load, the cell reads cooler than its own current can explain, so the abnormal heat becomes negative. Below −0.4 W for 60 s with at least 1 A is a sensor fault, and both relays open."),
        ("What happens before the model is fitted?",
         "The thermal parts are switched off and simple rate-of-rise limits are used: 0.5 °C/min Warning and 1.0 °C/min Trip. The model is fitted at Gate 9."),
    ]),
    ("Tools and results", [
        ("Why KiCad?",
         "It is a free, open-source circuit design tool used in industry. It has a built-in circuit simulator, ngspice."),
        ("What is ngspice?",
         "A SPICE circuit simulator. SPICE programs calculate the voltages and currents in a circuit. KiCad uses ngspice inside."),
        ("What did the KiCad simulation show?",
         "The ADC inputs stay below 3.0 V; leakage of 10 nA at an ADC input moves a cell reading by about 4.1 mV; the NTC voltage is 1.65 V at 25 °C; the shunt gives 25 mV at 5 A; and the heat model's numbers match Octave's."),
        ("Why GNU Octave and not MATLAB?",
         "MATLAB needs a paid licence. GNU Octave is free and runs the same .m files, so the work also runs in MATLAB."),
        ("What did the Octave check show?",
         "Octave's copy of the estimator, given the same data, gives the same core temperature and abnormal heat as the controller program: within 0.007 °C and 0.0013 W on four simulated scenarios."),
        ("What is Xcos?",
         "The block-diagram simulator in Scilab, a free tool like Simulink. We built the heat model and the abnormal-heat detection as block diagrams."),
        ("What is the C++ simulator?",
         "A program that runs the real controller code on a PC against a simulated pack: four cells with their heat, the hardware BMS, noisy sensors, and every fault. It has 30 test scenarios and the dashboard demonstrations."),
        ("How do you know the controller program works?",
         "26 unit tests and 30 scenarios test it in simulation; the Octave copy gives the same numbers; and on the real board each build gate tests it with its own pass rules."),
        ("What is the main result?",
         "In simulation, with a cell defect under a 3 A load, this project trips about 5 minutes earlier than a fixed-limit BMS, with the cell about 27 °C cooler. A fixed-limit BMS does not react at all to 1 W of heat with no current."),
        ("Have you tested on real cells?",
         "Not yet. The hardware is the next step, gate by gate. All results now are simulation results. The real values, like the thermal parameters, are measured at the gates."),
        ("Why not test by heating a real cell until it fails?",
         "That is dangerous and is never done. Limits are proven with simulated signals, the simulator, a heated dummy cylinder, and a supervised 47 Ω resistor that copies a soft short safely."),
        ("What is new in your project?",
         "In the papers reviewed, none does all of this on a low-cost controller: estimating the abnormal heat in watts with a physical model and Kalman filter, predicting and then confirming each forecast, cross-checking thermal and electrical evidence, and forecasting a safe current."),
    ]),
    ("Limits and future work", [
        ("What happens if the ESP32 crashes?",
         "Both relays open, because they are normally open and their inputs are pulled up. The hardware BMS keeps protecting. The crash is latched."),
        ("What if a relay contact welds shut?",
         "The hardware BMS and the fuse can still open or clear severe faults. The pack is then removed from service."),
        ("What if a sensor breaks?",
         "An open, shorted or stuck NTC, or a lost ADS1115 or INA226, is a sensor fault. It latches and opens the relays within about 2 s (60 s for a stuck NTC)."),
        ("What are the limitations?",
         "The heat model's values are estimates until Gate 9 measures them. Heat made inside a cell cannot be stopped by disconnecting; the gain there is warning time. The prototype is limited to 5 A, and charge and load must not be used at the same time."),
        ("Why can a fixed-limit BMS not see an internal short at rest?",
         "With no current, the pack looks quiet. The heat of a soft short is small, and the temperature rises very slowly. Only an estimate of heat, or of the leak, can see it."),
        ("What is future work?",
         "Build and test the hardware through Gates 0 to 12, fit the heat model on the real cells, choose the clamp part, then move from perfboard to a PCB and test larger packs."),
        ("What does the project cost?",
         "About ₹9,260 for the full parts list at replacement prices, including the four cells."),
    ]),
]

GLOSSARY = [
    ("ADC (analog-to-digital converter)", "A circuit that turns a voltage into a number."),
    ("ADS1115", "A 16-bit, 4-channel ADC chip. It measures the four cell taps."),
    ("Ah (ampere-hour)", "The charge a battery holds. 3.3 Ah gives 3.3 A for one hour."),
    ("Ambient temperature", "The temperature of the air around the pack."),
    ("Balancing", "Keeping all cells at the same charge."),
    ("BMS (battery management system)", "The protection and monitoring circuit of a battery pack."),
    ("Buck converter (LM2596)", "A circuit that lowers a DC voltage efficiently. Here it makes 5.0 V from the pack."),
    ("CC/CV charging", "Constant current, then constant voltage: the normal way to charge lithium-ion cells."),
    ("Cell", "One battery unit. The pack has four."),
    ("Core temperature", "The temperature deep inside a cell. No sensor can reach it; the model estimates it."),
    ("Cross-check", "Checking one result with a second, independent method."),
    ("Divider (voltage divider)", "Two resistors in series that give a known fraction of a voltage."),
    ("ERC (electrical rules check)", "KiCad's automatic check of a circuit drawing for wiring mistakes."),
    ("ESP32", "A low-cost microcontroller with Wi-Fi. It runs the supervisor program."),
    ("ESP-IDF", "Espressif's official set of tools for writing ESP32 programs."),
    ("Firmware", "The program that runs inside a microcontroller."),
    ("Fixed-limit BMS", "A normal BMS that acts only when a reading crosses a fixed value, such as 55 °C."),
    ("Forecast", "A prediction of a future value, here a cell's temperature 1 or 5 minutes ahead."),
    ("Fuse", "A wire that melts and opens the circuit when the current is too high."),
    ("Gate", "One stage of the safe build sequence (Gates 0 to 12), each with pass and stop rules."),
    ("GNU Octave", "A free program that runs MATLAB-style .m files."),
    ("GPIO", "A general-purpose pin of the microcontroller."),
    ("Heat capacity (J/°C)", "How much heat raises a body by 1 °C. A cell has about 45 J/°C."),
    ("I²C", "A two-wire bus (SDA and SCL) that connects chips to the microcontroller."),
    ("INA226", "A chip that measures current, through the voltage across a shunt, in both directions."),
    ("Internal resistance", "The small resistance inside a cell. Current through it makes heat."),
    ("Internal short", "An unwanted current path inside a cell. It drains and heats the cell."),
    ("Joule heat (I²R)", "Heat made by a current I through a resistance R."),
    ("Kalman filter", "A method that combines a model's prediction and noisy readings to estimate values, including ones not measured."),
    ("Kelvin connection", "Separate sense wires that measure voltage right at a resistor's pads."),
    ("KiCad", "A free, open-source program for drawing and simulating circuits."),
    ("Latch", "A trip that stays until a deliberate reset."),
    ("Leak current", "The current an internal short draws from its own cell."),
    ("Li-ion (lithium-ion)", "The rechargeable cell type used here."),
    ("Low-pass filter", "A circuit that passes slow signals and removes fast noise."),
    ("MATLAB", "A paid program for engineering calculations. Octave runs its files."),
    ("Microcontroller", "A small computer on one chip that controls a device."),
    ("NMC", "Nickel manganese cobalt: the chemistry of the cells used."),
    ("Normally open (NO)", "A relay contact that is open when the relay has no power."),
    ("NTC thermistor", "A resistor whose resistance falls as its temperature rises."),
    ("ngspice", "The circuit simulator inside KiCad."),
    ("Observer", "A model that runs beside the real system and corrects itself with measurements, to estimate hidden values."),
    ("OCV (open-circuit voltage)", "A cell's voltage when no current flows and it has rested."),
    ("Perfboard", "A board with a grid of holes for building circuits by hand, without a PCB."),
    ("Pull-up resistor", "A resistor that holds a pin HIGH when nothing drives it."),
    ("Relay", "A switch moved by an electromagnet, controlled by a small signal."),
    ("Risk level", "The supervisor's verdict: Normal, Watch, Warning or Trip."),
    ("RMS error", "A kind of average size of errors. Large errors count more."),
    ("Scenario", "One complete simulated test with its own checks."),
    ("Scilab and Xcos", "A free engineering program; Xcos is its block-diagram simulator, like Simulink."),
    ("Self-discharge", "A cell slowly losing charge on its own."),
    ("Shunt", "A small, precise resistor in the current path. Its voltage shows the current."),
    ("Simulation", "Calculating how a system behaves, on a computer, instead of building it."),
    ("SOC (state of charge)", "How full a cell is, in percent."),
    ("SPICE", "The standard method and program family for simulating circuits."),
    ("Surface temperature", "The temperature of the cell's outside can, where the NTC sits."),
    ("Thermal resistance (°C/W)", "How many degrees of difference it takes to push 1 W of heat through a path."),
    ("Thermal runaway", "Heat-making reactions in a cell that speed up as it gets hotter."),
    ("Time constant", "How fast something settles. After one time constant it has gone about 63 % of the way."),
    ("Trip", "The supervisor opening the relays because of a fault."),
    ("Watchdog", "A timer that resets the controller if its program stops running."),
]


def viva_notes():
    qa_html = []
    n = 0
    for group, items in QA:
        qa_html.append(f"<h3>{E(group)}</h3>")
        for q, a in items:
            n += 1
            qa_html.append(f'<div class="qa"><div class="q">{n}. {E(q)}</div><div class="a">{E(a)}</div></div>')
    gloss = "".join(f"<dt>{E(t)}</dt><dd>{E(d)}</dd>" for t, d in GLOSSARY)
    oc_rows = [[f"<span class='key'>{E(r['scenario'])}</span>", f"{r['max_dtc_c']:.4f} °C", f"{r['max_dq_w']:.4f} W"]
               for r in OCTAVE.get("results", [])]

    body = f"""
<div class="cover">
  <div class="top">
    <div class="kicker">VIVA NOTES</div>
    <div class="title">Predictive Thermal Battery Management System for Li-ion Battery Packs</div>
    <div class="sub">The whole project in simple words, likely questions with answers, and a glossary</div>
    <div class="meta">Muskan Sulathana · Guide: Dr. M. Rupesh</div>
  </div>
  <div class="foot">How to use these notes: read sections 1 to 12 once, slowly. Then read the questions in section 13
  and answer each one aloud in your own words before you read the model answer. Every technical word is explained in
  the glossary at the end. All results are simulation results: the hardware is not built yet.</div>
</div>

<section>
<h2>Contents</h2>
<ol class="toc">
<li>The problem</li><li>The idea</li><li>The system: two layers</li><li>The components</li>
<li>How each measurement works</li><li>The heat model of a cell</li><li>The Kalman filter in plain words</li>
<li>Abnormal heat and the risk levels</li><li>Forecasts and the 5-minute check</li><li>The leak estimate</li>
<li>The tools</li><li>The results so far</li><li>Likely viva questions</li><li>Glossary</li>
</ol>

<h2 style="margin-top:8mm">1. The problem</h2>
<p>A lithium-ion cell stores a lot of energy in a small can. It is safe inside its limits. Outside them it can be
damaged, and it can become dangerous.</p>
<ul>
<li><b>Heat in a healthy cell.</b> Current flows through the cell's small internal resistance R. This makes heat,
I²R, called Joule heat. This heat is normal and expected.</li>
<li><b>Heat from a fault.</b> A defect or an internal short makes extra heat. The current does not explain this heat.</li>
<li><b>Thermal runaway.</b> If a cell gets hot enough, reactions inside it start to make heat. More heat makes the
reactions faster, which makes more heat. This chain can end in fire. Disconnecting the pack does not stop heat that
is made inside the cell.</li>
</ul>
<p><b>Why a fixed limit is late.</b> A normal BMS waits until the cell surface reaches a fixed temperature, for example
55 °C. But a cell is a large body. It warms slowly. With a fault inside, the surface may need many minutes, or may
never, reach 55 °C. By then the fault has been there for a long time.</p>
</section>

<section>
<h2>2. The idea: predict, compare, flag</h2>
<p>The project uses a <b>model</b> of how a healthy cell heats. Five times a second the supervisor:</p>
<ol>
<li><b>Predicts</b> the cell's temperature from its current, using the model;</li>
<li><b>Compares</b> the prediction with the real reading of the temperature sensor;</li>
<li><b>Flags</b> the difference. Heat that the current cannot explain is called <b>abnormal heat</b>, in watts.</li>
</ol>
<p>A healthy cell under load has abnormal heat near zero, because its current explains its heating. So normal use is
never flagged. A fault shows positive abnormal heat within about a minute, while the cell is still cool.</p>
<p>This follows the predict–compare–flag structure of the base paper, Ojo et al. (IEEE Transactions on Industrial
Electronics, 2021). The base paper uses a neural network. This project uses a physical heat model and a Kalman
filter instead. It needs no training data, every output has a unit (°C or W), and it runs on a low-cost ESP32.</p>
</section>

<section>
<h2>3. The system: two layers</h2>
{fig("../architecture/current-architecture.svg", "The architecture (revision 2.2): power, protection and sensing.", "mid")}
<p><b>The pack.</b> Four NCR18650GA cells in series (4S1P): 14.4 V nominal, 16.8 V full, 3.3 Ah, about 47.5 Wh. The
prototype is limited to 5 A discharge and 1.5 A charge.</p>
<p><b>Layer A, the hardware BMS.</b> A ready-made 4S protection board. It always works, even if the ESP32 fails. It
stops charging at about 4.25 V per cell, stops discharging at about 2.7 V per cell, protects against short circuits,
and balances the cells (30 mA from 4.18 V).</p>
<p><b>Layer B, the ESP32 supervisor.</b> It measures every cell voltage, the pack current, four cell temperatures and
the air temperature, five times a second. It runs the predictive layer and drives two relays:</p>
<ul>
<li><b>K_LOAD</b> connects the load, and <b>K_CHARGE</b> connects the charger. They are separate, so the supervisor can
stop charging but allow discharge, or the other way round.</li>
<li>Both are <b>normally open</b>, with pull-up resistors on their inputs. If the ESP32 resets, crashes or loses power,
both relays open by themselves.</li>
<li>A trip is <b>latched</b>: it stays until a deliberate manual reset, and the reset is allowed only when everything
is safe again.</li>
</ul>
<p><b>Why two layers?</b> So that no single failure removes all protection. The hardware BMS is the final backstop,
and nothing in the program tries to override it.</p>
</section>

<section>
<h2>4. The components and why each one is there</h2>
{table(["Part", "Why it is there"], [
    ["4 × NCR18650GA cells (4S1P)", "The battery: 3.3 Ah each, matched at Gate 4."],
    ["4S hardware BMS (20 A board)", "Layer A: voltage, short-circuit protection and balancing that always works."],
    ["ESP32 DevKit", "Layer B: the supervisor. Runs the predictive layer and the dashboard."],
    ["ADS1115 (16-bit ADC)", "Measures the four cell taps accurately."],
    ["330 kΩ / 56 kΩ dividers, 10 kΩ + 100 nF filters, clamps", "Bring the tap voltages down to the ADC's range, remove noise, protect the inputs."],
    ["5 × 10k B3950 NTC thermistors", "Four on the cells, one in the air."],
    ["INA226 module + 5 mΩ shunt", "Measures the pack current in both directions."],
    ["LM2596 buck converter (5.0 V)", "Powers the ESP32 and the relay module from the pack."],
    ["Dual 5 V relay module", "The two disconnects, K_LOAD and K_CHARGE."],
    ["7.5 A blade fuse and holder", "Protects the wiring against a large fault current."],
    ["Buzzer and red LED", "A local alarm that works without Wi-Fi."],
    ["XT60 and JST-XH connectors, wire", "Power, charger and balance connections."],
    ["Nickel strip, spacers, fish paper, sleeve", "Build the welded pack safely."],
    ["Two perfboards (no PCB)", "Board A: the cell taps and the ADS1115. Board B: the ESP32, NTC dividers, INA226, relay inputs and alarm."],
    ["PETG enclosure", "A vented case. It is not a fire enclosure."],
    ["16.8 V, 1.5 A CC/CV charger", "Charges the pack through the charge relay."],
])}
<p>The full parts list costs about ₹9,260 at replacement prices (Build Guide, section 6).</p>
{fig("../build-guide/figures/sld.svg", "Single-line diagram: cells, BMS, fuse, shunt, relays, load and charger.", "small")}
</section>

<section>
<h2>5. How each measurement works</h2>
<h3>Cell voltages: dividers and the ADS1115</h3>
<p>The ADS1115 measures four "taps" of the pack against its negative end: 4.2, 8.4, 12.6 and 16.8 V when full. Each tap
goes through a 330 kΩ and 56 kΩ divider, so 16.8 V becomes about 2.4 V. Then a 10 kΩ resistor and a 100 nF capacitor
filter out noise. Cell 1 is the first tap; every other cell is the difference of two neighbouring taps.</p>
<p><b>KiCad simulation:</b> at full charge the ADC inputs are {adc_list()} V,
all below the 3.0 V limit. Every 10 nA of leakage at an ADC input moves a cell reading by about
{kv("cell-taps", "err_mv_per_10na", "{:.1f}")} mV, so the clamp must leak far less than
{kv("cell-taps", "leak_for_20mv_na", "{:.0f}")} nA. The filter's cut-off is about {kv("cell-taps", "f3db_hz", "{:.0f}")} Hz.</p>
{fig("../build-guide/figures/circuit-taps.svg", "One cell-tap channel.", "small")}
<h3>Temperatures: NTC dividers</h3>
<p>An NTC thermistor's resistance falls as it gets hotter (10 kΩ at 25 °C). With a 10 kΩ resistor from 3.3 V above it,
the voltage in the middle tells the temperature. The ESP32's ADC1 reads it.</p>
<p><b>KiCad simulation:</b> {kv("ntc-divider", "v_25c", "{:.2f}")} V at 25 °C, about 1.00 V at 45 °C and 0.76 V at
55 °C. The reading stays in the ESP32's accurate range from about 3 °C to above 100 °C.</p>
<h3>Current: shunt and INA226</h3>
<p>A 5 mΩ resistor (the shunt) sits in the pack's current path. The current makes a small voltage across it:
V = I × R. The INA226 reads this voltage in both directions. Discharge is positive, charge is negative.</p>
<p><b>KiCad simulation:</b> {kv("current-sense", "sense_mv_5a", "{:.1f}")} mV at 5 A, well inside the INA226's
±81.9 mV range. If the module's own 0.1 Ω shunt (R100) is left in place, the reading is about 4.8 % low. So it is
removed.</p>
</section>

<section>
<h2>6. The heat model of a cell</h2>
<p>Each cell has two parts in the model (from Lin et al., IEEE TCST 2013):</p>
<ul>
<li>the <b>core</b>, where heat is made. Its heat capacity is C_core.</li>
<li>the <b>surface</b> (the can), where the NTC sits. Its heat capacity is C_surf.</li>
</ul>
<p>Heat flows from the core to the surface through a thermal resistance R_core, and from the surface to the air
through a thermal resistance R_air. A <b>heat capacity</b> (J/°C) says how much heat warms a body by 1 °C. A
<b>thermal resistance</b> (°C/W) says how many degrees it takes to push 1 W through a path.</p>
<p>The values used now are development values: C_core 40 J/°C and C_surf 5 J/°C (45 J/°C together, as the
architecture says for an 18650), R_core 2 °C/W and R_air 30 °C/W. Gate 9 replaces them with values fitted on the
real cells.</p>
<h3>The electrical analogue</h3>
<p>Heat flow behaves like electric current. So the model can be drawn as a circuit:</p>
{table(["Heat", "Electric circuit"], [
    ["Temperature, 1 °C", "Voltage, 1 V"], ["Heat flow, 1 W", "Current, 1 A"],
    ["Heat capacity, 1 J/°C", "Capacitor, 1 F"], ["Thermal resistance, 1 °C/W", "Resistor, 1 Ω"],
    ["Air temperature", "A fixed voltage source"], ["Heat made in the core", "A current source"],
])}
{fig("../build-guide/figures/kicad-thermal-model.svg", "The heat model drawn in KiCad.", "small")}
<p><b>Result (KiCad, Octave and Xcos give the same):</b> with 1 W in the core and 25 °C air, the core reaches about
26.3 °C after 1 minute, 31.1 °C after 5 minutes, 43.3 °C after 20 minutes and 54.5 °C after one hour. It would settle at
57 °C (25 + 1 W × 32 °C/W). There are two time constants: 8.4 s (core and surface share heat) and 1422 s, about
24 minutes (the whole cell warms up to the air). That slow time constant is why a fixed limit acts late.</p>
</section>

<section>
<h2>7. The Kalman filter in plain words</h2>
<p>The supervisor runs one Kalman filter per cell, five times a second. Its "state" is three numbers: the core
temperature, the surface temperature, and the abnormal heat.</p>
<ol>
<li><b>Predict.</b> From the last state and the measured current, the model predicts the new state. The expected
heat is I²R, from the cell's measured resistance.</li>
<li><b>Compare.</b> It compares the predicted surface temperature with the NTC reading.</li>
<li><b>Correct.</b> It moves the state towards the reading. How much depends on how much it trusts the model
and the sensor. If the reading stays above the prediction, the only way to explain it is more heat, so the
abnormal-heat estimate rises.</li>
</ol>
<p>So the filter gives two things no sensor measures: the <b>core temperature</b> and the <b>abnormal heat in
watts</b>. A simple everyday picture: you know how fast a kettle should warm on a given flame. If it warms faster,
something else is adding heat, and you can say how much.</p>
<p>Safety details: the current used in the calculation is limited to 5 A, and the resistance to its expected range, so a
bad reading cannot "explain away" a fault. The model's values are fitted once at Gate 9 and then fixed, so the model
can never slowly learn a fault as normal.</p>
</section>

<section>
<h2>8. Abnormal heat and the risk levels</h2>
<p>Abnormal heat is shown in watts and also as the heating rate it causes: watts ÷ 45 J/°C × 60 gives °C per
minute. So 0.4 W is about 0.5 °C/min, and 0.75 W is about 1.0 °C/min.</p>
{table(["Level", "When", "Action"], [
    ["0 Normal", "None of the conditions below", "—"],
    ["1 Watch", "5-minute check +1.0 °C or more; a cell differs from the others by 0.3 °C/min for 30 s; time to limit under 10 minutes, or current above the safe current for 30 s; leak estimate 20 mA or more; resistance drift over 30 %", "Notice on the dashboard and in the log"],
    ["2 Warning", "Abnormal heat 0.5 °C/min (about 0.4 W) for 30 s; or a thermal Watch and an electrical Watch on the same cell together", "Alarm on; both relays stay on"],
    ["3 Trip", "Abnormal heat 1.0 °C/min (about 0.75 W) for 10 s; a cell differs from the others by 0.6 °C/min for 10 s; self-acceleration while at Warning", "Both relays open, latched and logged"],
])}
<p>A small fault raises the alarm only when two independent kinds of evidence, thermal and electrical, agree. A clear
fault trips on its own. The rules are fixed tables, so every level can be traced back to the measurement that caused
it.</p>
<h3>Other fixed limits (section 8 of the architecture)</h3>
{table(["Condition", "Warning", "Trip"], [
    ["Any cell high", "4.10 V", "4.15 V: charge off"], ["Any cell low", "3.20 V", "3.10 V: load off"],
    ["Charge temperature", "40 °C", "45 °C: charge off"], ["Discharge temperature", "50 °C", "55 °C: load off"],
    ["Temperature spread", "7 °C", "10 °C: both off"], ["Pack current", "4.5 A", "5.0 A: load off; 1.6 A: charge off"],
])}
</section>

<section>
<h2>9. Forecasts and the 5-minute check</h2>
<ul>
<li><b>Predict and confirm.</b> Every 10 s the supervisor predicts each cell's surface temperature 1 and 5 minutes
ahead. When that time comes, it checks the prediction against the real reading. Within ±0.5 °C is "confirmed normal".
+1.0 °C or more raises Watch. Example: a small 0.2 W fault is only about 0.27 °C/min, below the warning level, but
after 5 minutes the cell is about 1.3 °C hotter than predicted, so it raises Watch.</li>
<li><b>Accuracy record.</b> It keeps the RMS error of its predictions. Gates 9 and 10 require 0.5 °C RMS or less at
5 minutes. In the simulation the error in normal use was 0.11 to 0.12 °C.</li>
<li><b>Settling temperature and time to limit.</b> From the current, the model says where each cell will settle, and
how many minutes until it reaches its limit (45 °C when charging, 55 °C when discharging).</li>
<li><b>Safe continuous current.</b> The largest current at which every cell settles below its limit. It is near 5 A at
25 °C and lower on a hot day.</li>
<li><b>Online resistance.</b> Each change in current of 0.5 A or more gives each cell's resistance, R = ΔV / ΔI. Rising
resistance means ageing or a weak connection. A drift over 30 % raises Watch.</li>
<li><b>Self-acceleration.</b> At Warning, if the abnormal heat has grown by 50 % while the core rose by 1 °C within
120 s, the heat is feeding itself, as at the start of thermal runaway. The supervisor trips at once.</li>
</ul>
</section>

<section>
<h2>10. The leak estimate and the energy cross-check</h2>
<p>An internal short drains its own cell, even at rest. So it leaves an electrical trace as well as a heat trace.</p>
<ol>
<li>The supervisor waits for rest: current below 20 mA, no cell above 4.15 V, and 30 minutes after the last load or
charge.</li>
<li>It compares each cell's voltage with the mean of the four. This cancels the drift that all cells share.</li>
<li>Over 60 minutes, the slope of that difference gives the leak current, using the cell's voltage-to-charge curve
measured at Gate 10.</li>
</ol>
<p>Example from the architecture: a 20 mA leak lowers a mid-charge cell by about 6 mV per hour compared with the others.
That leak makes only about 0.07 W of heat, too little to see as heat. So the electrical check finds a soft short long
before it is hot.</p>
<p><b>Energy cross-check.</b> A leak current I at cell voltage V makes V × I watts of heat inside the cell. When this
matches the abnormal heat from the Kalman filter, two independent methods point to the same fault.</p>
<p><b>Simulation result (Gate 11 soft short, 47 Ω across cell 2):</b> the leak estimate read about 73 mA against about
79 mA really drawn, and the abnormal heat and the leak heat agreed: level Warning.</p>
</section>

<section>
<h2>11. The tools, and why each one</h2>
{table(["Tool", "What it does in this project", "Why this tool"], [
    ["<b>KiCad 10 + ngspice</b>", "The four analog circuits (cell taps, NTC divider, current shunt) and the heat model drawn as a circuit, simulated and checked", "Free, open source, used in industry. ngspice is the circuit simulator inside KiCad."],
    ["<b>GNU Octave</b>", "The heat model and the Kalman filter written a second time and compared with the controller program", "Free. It runs MATLAB .m files, so the work also runs in MATLAB, which needs a paid licence."],
    ["<b>Scilab Xcos</b>", "The heat model and the abnormal-heat detection as block diagrams", "Free. It is the block-diagram tool like Simulink."],
    ["<b>The C++ simulator</b>", "Runs the real controller code on a PC against a simulated pack: 30 test scenarios and the dashboard demonstrations", "The same code that runs on the ESP32 is tested before any cell is connected (software-in-the-loop)."],
    ["<b>ESP32 + ESP-IDF</b>", "The real controller. The program is C++, on FreeRTOS, with the safety task at 5 Hz and a watchdog", "ESP-IDF is Espressif's official toolset. It builds the firmware without warnings."],
    ["<b>The dashboard</b>", "One web page: cell cards, charts, the system drawing, the demonstrations", "The ESP32 serves it over its own Wi-Fi; on a PC the simulator serves it."],
])}
<h3>How the checks fit together</h3>
<ul>
<li><b>KiCad</b> checks the electronics.</li>
<li><b>Octave</b> checks that the controller program computes the model correctly.</li>
<li><b>Xcos</b> shows the method as a block diagram.</li>
<li><b>The C++ simulator</b> tests the complete program against every fault the build gates ask for.</li>
</ul>
</section>

<section>
<h2>12. The results so far (all in simulation)</h2>
<h3>The guided demonstrations against a fixed-limit BMS</h3>
{table(["Demonstration", "This project", "Fixed-limit BMS"], [
    ["Heat with no current, 1 W in cell 2", "Trip about 1 minute after the heat began, cell near 26 °C", "No reaction"],
    ["A cell defect under 3 A", "Trip about 2 minutes after the fault, near 28 °C; the cell then cools", "Trip about 7 minutes after the fault, at 55 °C"],
    ["Thermal runaway onset (heat in cell 3 that grows as it warms)", "Trip about 8 minutes after it began, near 29 °C", "Trip about 4 minutes later, at 55 °C"],
    ["Soft internal short, 47 Ω (Gate 11)", "Warning: leak about 73 mA against 79 mA drawn; heat and leak agree", "No reaction"],
    ["NTC lifted off its cell under 3 A", "Sensor fault within about 10 s; both relays open", "No reaction"],
    ["Normal use (discharge, rest, charge)", "Normal throughout; 5-minute error 0.11 to 0.12 °C RMS", "—"],
])}
<p>Main result: for the cell defect, this project acts about 5 minutes earlier, with the cell about 27 °C cooler. For heat
made inside a cell, no BMS can stop the heat by disconnecting; what the predictive layer gives there is warning time.</p>
{fig("../build-guide/snapshots/defect-compare.png", "The dashboard's comparison after the cell-defect demonstration.", "small")}
<h3>Tests and cross-checks</h3>
<ul>
<li><b>26 unit tests and 30 scenarios</b> pass. The scenarios rehearse Gates 1, 2, 9, 10 and 11 with each gate's own
pass rules.</li>
<li><b>KiCad:</b> all 11 circuit checks pass; KiCad's electrical rules check finds no violation.</li>
<li><b>ngspice and Octave</b> solve the heat model two ways and agree within 0.0002 °C.</li>
<li><b>Octave against the controller program</b>, every sample replayed:</li>
</ul>
{table(["Scenario", "Largest core-temperature difference", "Largest abnormal-heat difference"], oc_rows) if oc_rows else ""}
<ul>
<li><b>Xcos:</b> <span class="fill">[[XCOS-A]]</span></li>
<li><b>Xcos:</b> <span class="fill">[[XCOS-B]]</span></li>
</ul>
<h3>What is not done yet</h3>
<ul>
<li>The hardware is not built. It is built gate by gate, Gates 0 to 12 (Build Guide, section 14). The firmware has not
yet run on an ESP32.</li>
<li>The heat model's values are estimates until Gate 9 measures them on the real cells.</li>
<li>The clamp part is chosen at Gate 1 after a leakage test.</li>
</ul>
<div class="safety"><b>Safety rules.</b> No lithium cell is connected before Gate 3. The first power-up and the first
charge are never done alone. A live cell is never driven into thermal runaway, overcharge or over-discharge to prove a
limit: limits are proven with simulated signals, the simulator, a heated dummy cylinder, and a supervised 47 Ω
resistor. The hardware BMS stays connected as the final backstop. The enclosure is vented and is not a fire
enclosure.</div>
</section>

<section>
<h2>13. Likely viva questions, with short answers</h2>
<p>Answer in your own words. Short, clear answers are best. If you do not know, say what you do know and where in the
project the answer would come from (for example, "Gate 9 measures that").</p>
{"".join(qa_html)}
</section>

<section>
<h2>14. Glossary</h2>
<dl class="gloss">{gloss}</dl>
</section>
"""
    return page("Viva notes", "viva notes", body), n


# --------------------------------------------------------------------------------------------

def find_chrome():
    for name in (os.environ.get("CHROME"), "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
                 "chrome", r"C:\Program Files\Google\Chrome\Application\chrome.exe"):
        if name and (shutil.which(name) or pathlib.Path(name).exists()):
            return shutil.which(name) or name
    return None


def to_pdf(chrome, src, pdf):
    subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-sandbox", "--no-pdf-header-footer",
                    f"--print-to-pdf={pdf}", src.as_uri()], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    ap = argparse.ArgumentParser(description="build the presentation guide and the viva notes")
    ap.add_argument("--no-pdf", action="store_true")
    args = ap.parse_args()
    viva, questions = viva_notes()
    docs = [("presentation-guide.html", "Presentation-Guide.pdf", presentation_guide()),
            ("viva-notes.html", "Viva-Notes.pdf", viva)]
    chrome = None if args.no_pdf else find_chrome()
    if not args.no_pdf and not chrome:
        sys.exit("Chrome or Chromium is needed for the PDFs; set CHROME to its path")
    for name, pdf, text in docs:
        out = HERE / name
        out.write_text(text, encoding="utf-8")
        print("wrote", out.relative_to(ROOT))
        if chrome:
            to_pdf(chrome, out, HERE / pdf)
            print("wrote", (HERE / pdf).relative_to(ROOT))
    print(f"{questions} viva questions")


if __name__ == "__main__":
    main()
