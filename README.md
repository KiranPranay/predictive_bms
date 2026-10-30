# Predictive BMS: the prototype

The working prototype of the major project **Predictive Thermal Battery Management System for
Li-ion Battery Packs**: a 4S1P NCR18650GA pack with an independent hardware BMS, supervised by an
ESP32. On every sample the ESP32 runs a thermal model of each cell, estimates heat that the
current cannot explain, forecasts each cell's temperature and checks every forecast, and opens
separate charge and load relays before a fixed limit is reached.

The design is fixed by architecture revision 2.2 of the bms-moosi repository, copied in
[docs/architecture/](docs/architecture/). This repository builds it: firmware, a simulated
pack to test it on, the dashboard, the bench tools, and the build documents. There is no PCB.
The prototype is wired from modules on perfboard ([docs/wiring.md](docs/wiring.md)).

## What is here

| Part | What it does | Where |
| --- | --- | --- |
| Supervisor core | every algorithm of architecture sections 5–10 in portable C++: filters, limits and latches, the two-state thermal model, the Kalman observer of core temperature and abnormal heat, predict and confirm, online resistance, the rest leak estimate and energy cross-check, the forecasts, the risk levels | `firmware/components/bms_core/` |
| ESP32 firmware | ESP-IDF v5.5: ADS1115, INA226 and NTC drivers, relays that start open, the 5 Hz safety task with a watchdog, flash storage of calibration and latches, serial console, Wi-Fi dashboard | `firmware/main/` |
| Simulated pack | four cells with their heat, a hardware BMS, sensors with noise, and every Gate 11 fault | `firmware/components/bms_sim/` |
| Tests and simulator | 26 unit tests and 30 scenarios that rehearse Gates 1, 2, 9, 10 and 11 | `host/` |
| Dashboard | one page, served by the ESP32 or by the simulator; on the simulator it adds nine guided demonstrations, a comparison with a fixed-limit BMS and the verification results | `dashboard/index.html` |
| Bench tools | Gate 1 calibration, Gate 9 thermal fit, Gate 10 OCV table, serial logger, simulator server | `tools/` |
| Build guide | one PDF with the single-line diagram, circuit diagrams, wiring, both perfboard layouts hole by hole, assembly steps and checks, and snapshots of the simulation | `docs/build-guide/Build-Guide.pdf` |
| Circuit simulation | the analog circuits (cell taps, NTC dividers, current shunt) and the cell's thermal model as KiCad 10 schematics, simulated with ngspice and checked | `kicad/` |
| Model check | the thermal model and the Kalman observer written a second time in GNU Octave (MATLAB-compatible) and compared with the firmware sample by sample | `matlab/` |
| Documents | wiring, firmware, gate-by-gate bring-up, simulator results, gate record sheets | `docs/` |

## Where the project stands

| Item | State |
| --- | --- |
| Supervisor core | written; 26 unit tests and 30 scenarios pass |
| ESP32 firmware | builds with ESP-IDF v5.5.6 without warnings (normal and bench builds); **not yet run on hardware** |
| Dashboard | runs on the simulator; the ESP32 serves the same page |
| Build guide | complete: circuits, single-line diagram, wiring, both perfboards hole by hole, assembly steps and checks, simulation snapshots, KiCad and Octave results |
| Circuit simulation (KiCad, ngspice) | four sheets; every check passes; KiCad's electrical rules check finds no violation |
| Model check (GNU Octave) | the Octave observer agrees with the firmware to 0.007 °C and 0.0013 W on four scenarios |
| Hardware | not built: next is Gate 0 in [docs/bring-up.md](docs/bring-up.md) |
| Thermal parameters, cell resistances, OCV table | estimates until Gates 4, 9 and 10 measure them; the thermal layer stays off until then (architecture 9.9) |

The simulator results are results about the method on an illustrative cell model, not about the
project's cells. [docs/simulator.md](docs/simulator.md) lists them, with what each gate must
still measure.

## On Windows, without building anything

The GitHub releases of this repository have `PredictiveBMS-Windows.zip`: the demo, the KiCad
projects, the Octave scripts, the Xcos models and the documents, ready to open. Extract it and
open `START HERE.pdf`. The demo needs nothing installed: double-click
`1 Demo - double-click.bat`. KiCad 10, GNU Octave and Scilab are free downloads.

The package is made by `tools/package_windows.py`. The workflow
`.github/workflows/windows.yml` builds it and tests it on Windows on every push: the demo
started from its .bat file, the Octave scripts in GNU Octave for Windows, the KiCad projects in
KiCad for Windows with its own ngspice, and Scilab with Xcos.

## Quick start

### 1. Build and test on the PC

Needs CMake 3.16 or later and a C++17 compiler (Linux, macOS or Windows).

```bash
cmake -S host -B build/host
cmake --build build/host
ctest --test-dir build/host --output-on-failure      # unit tests and scenarios
build/host/bms_sim run all                           # every scenario with its checks
```

### 2. See the whole system working on a simulated pack

```bash
python3 tools/demo.py        # builds the simulator the first time, then opens the dashboard
```

The dashboard (<http://127.0.0.1:8080/>) offers nine guided demonstrations, each on a fresh pack
with step-by-step narration: normal use, heat with no current, a cell that overheats under load, a
soft internal short (Gate 11), thermal runaway onset, a lifted sensor, a hot day at high current, a
cell reaching 4.15 V, and a controller crash. A second copy of the pack runs alongside with only
fixed limits, as a conventional BMS has, so every fault shows how much earlier the predictive
layer acts. The live system diagram, the charts (including each 5-minute forecast against the
reading it predicted) and the verification table of all 30 scenarios update as it runs. The
Simulator controls inject any fault by hand. `python3 tools/sim_server.py` starts the same page
without building.

### 3. Build and flash the firmware

ESP-IDF v5.5 is installed inside this folder (`.tools/`, not in git). On a new computer, install
it the same way, with nothing outside the project:

```bash
git clone -b v5.5.6 --depth 1 --recursive --shallow-submodules \
    https://github.com/espressif/esp-idf.git .tools/esp-idf
IDF_TOOLS_PATH=$PWD/.tools/espressif .tools/esp-idf/install.sh esp32
```

Then, in each new terminal:

```bash
export IDF_TOOLS_PATH=$PWD/.tools/espressif && . .tools/esp-idf/export.sh
cd firmware
idf.py menuconfig                      # Predictive BMS: Wi-Fi network, addresses, alarm
idf.py build
idf.py -p /dev/ttyUSB0 flash monitor   # Windows: -p COM3
```

### 4. Circuit simulation in KiCad and the model check in GNU Octave

Both tools are free. KiCad 10 includes the ngspice simulator; GNU Octave runs MATLAB `.m` files.
[kicad/README.md](kicad/README.md) and [matlab/README.md](matlab/README.md) explain how to install
and use them.

```bash
python3 kicad/run_sims.py                                 # every KiCad sheet: simulate and check
(cd matlab && octave --no-gui --eval "thermal_step")      # the thermal model, 1 W step
(cd matlab && octave --no-gui --eval "crosscheck")        # the Octave observer against the firmware
```

To simulate one circuit in KiCad itself, open its project in `kicad/sim/`, then **Inspect →
Simulator**, and run the analysis written on the sheet.

### 5. Bench tools

```bash
python3 -m venv .venv && .venv/bin/pip install -r tools/requirements.txt
.venv/bin/python -m unittest discover -s tools/tests
```

| Tool | Gate | Use |
| --- | --- | --- |
| `tools/calibrate.py` | 1 | tap, current and NTC calibration from bench readings, with the Gate 1 pass check |
| `tools/serial_log.py` | 8, 9 | records the firmware's CSV telemetry |
| `tools/fit_thermal.py` | 9 | fits the thermal model to a logged discharge |
| `tools/ocv_table.py` | 10 | builds the OCV slope table for the leak estimate |
| `tools/sim_server.py` | any | the dashboard on the simulated pack |

Each prints the console commands that store its result on the ESP32.

## Layout

```text
dashboard/index.html           the dashboard (no external files: works on the ESP32's own Wi-Fi)
docs/                          wiring, firmware, bring-up, simulator, gate records; architecture/
docs/build-guide/              the build guide PDF, its figures, and the scripts that make them
kicad/                         KiCad 10 simulation sheets (sim/) and the scripts that make and run them
matlab/                        the thermal model and observer in GNU Octave / MATLAB, and the cross-check
firmware/
  CMakeLists.txt, sdkconfig.*  the ESP-IDF project; sdkconfig.bench adds bench mode
  main/                        drivers, tasks, console, Wi-Fi and web server
  components/bms_core/         the supervisor (portable C++; config.h holds every limit)
  components/bms_sim/          the simulated pack
host/                          PC build: bms_sim, tests, scenarios
tools/                         bench tools and their tests
```

## Safety

The rules of [docs/architecture/safe-build-sequence.md](docs/architecture/safe-build-sequence.md)
apply to every step. In short: no lithium cell before Gate 3; never alone at the first power-up or
the first charge; never drive a live cell into thermal runaway, overcharge or over-discharge to
prove a limit. Limits are proven with simulated signals, the simulator, dummy heat sources, and
the supervised resistor of Gate 11. The hardware BMS stays connected as the final backstop, and
nothing in the firmware tries to override it.
