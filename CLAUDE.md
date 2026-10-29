# CLAUDE.md

The prototype of **Predictive Thermal Battery Management System for Li-ion Battery Packs** (4S1P
NCR18650GA, ESP32 supervisor, independent hardware BMS). Major project of Muskan Sulathana, EEE,
BVRIT Hyderabad; guide Dr. M. Rupesh. The academic documents (reviews, abstract, plan, tracker)
live in the separate bms-moosi repository; this repository builds the prototype. No PCB is
designed: the prototype is modules on perfboard.

## Rules

- **The architecture decides every engineering value.** It is bms-moosi
  `docs/current-architecture.md` (revision 2.2), copied read-only in `docs/architecture/`. Every
  value in `firmware/components/bms_core/include/bms/config.h` names its section, or is marked
  "development value" and listed in `docs/firmware.md` section 3 with the gate that confirms it.
  If the architecture changes, change it in bms-moosi first, copy it again, then update
  `config.h` and the docs.
- **Never weaken a limit, a persistence time or a scenario check so a test passes.** The
  scenario checks follow the gates' pass criteria. If a scenario fails, find out why; a real
  finding goes into `docs/simulator.md`.
- **Safety.** Never plan or describe a test that drives a live cell into thermal runaway,
  overcharge or over-discharge. Limits are proven with simulated signals, the simulator, dummy
  heat sources, or the supervised Gate 11 resistor. Nothing in a release build may fake a sensor
  reading or override the hardware BMS. Bench mode (`CONFIG_BMS_BENCH_SIM`) stays off by default
  and refuses to run with a pack on the taps.
- **The safety task never waits** for Wi-Fi, the console or the web server; they talk to it only
  through `firmware/main/shared.*`.
- **Tests before every commit:**
  `cmake -S host -B build/host && cmake --build build/host && ctest --test-dir build/host`,
  `.venv/bin/python -m unittest discover -s tools/tests`, and `idf.py build` in `firmware/`. After a
  change to the boards, the figures or the dashboard, rebuild the build guide
  (`python3 docs/build-guide/build_guide.py`) and look at the pages before committing
  (ESP-IDF environment: `export IDF_TOOLS_PATH=$PWD/.tools/espressif && . .tools/esp-idf/export.sh`).
  Firmware changes must build without warnings.
- **Git:** commit to `main`. Messages are short and plain (`firmware: ...`, `docs: ...`). **No
  `Co-Authored-By: Claude` line or any other AI attribution** in commits or pull requests
  (organisation policy). There is no remote yet; ask before creating one or pushing.
- **Keep out of git:** company documents (such as the purchase indent), other students' documents
  or names, and copyrighted papers (such as the base paper's PDF).
- **This computer:** no sudo, apt or system-wide installs. ESP-IDF lives in `.tools/` and Python
  packages in `.venv/`, both git-ignored. Anything else: write the command and the reason, and ask.
- **Writing:** every tracked file (documents, comments, commit messages, generated output) is
  written as the developer speaking to the users: never as an AI, never addressed to the
  developer, and without change history ("now", "at first"). Notes for the developer go in the
  chat or in `notes/` (git-ignored). Plain English, short sentences, no unexplained jargon,
  written for the person building and testing the prototype. Never claim a hardware result
  before the gate that measures it; simulator results are labelled as simulator results.
- **Code:** C++17, no exceptions, no heap use in the 5 Hz path, no external libraries in the core.
  Python tools need only the standard library, except `fit_thermal.py` (numpy, scipy) and
  `serial_log.py` (pyserial). Paths with `pathlib`; everything runs on Linux and Windows.

## Where things are

| Path | What it is |
| --- | --- |
| `firmware/components/bms_core/` | the supervisor: `config.h` (limits), `sensors`, `thermal`, `electrical`, `risk`, `supervisor`, `telemetry` |
| `firmware/main/` | ESP32 drivers, `safety_task`, `console`, `telemetry` (Wi-Fi and web), `storage` (NVS) |
| `firmware/components/bms_sim/` | the simulated pack (also the bench-mode sensor source) |
| `host/` | PC build: `bms_sim` (list, run, live), unit tests, scenarios (`sim/scenario.cpp`) |
| `dashboard/index.html` | the dashboard, embedded in the firmware and served by `tools/sim_server.py` |
| `tools/` | calibration, thermal fit, OCV table, serial logger, simulator server; tests in `tools/tests/` |
| `docs/` | `wiring.md`, `firmware.md`, `bring-up.md`, `simulator.md`, `gate-records.md`, `architecture/` |
| `docs/build-guide/` | `boards.py` (both perfboards as checked data), `figures.py`, `build_guide.py` (HTML and PDF), `snapshots.py` (browser pictures of the demonstrations) |
