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
  Firmware changes must build without warnings. After a change to `kicad/`, run
  `python3 kicad/make_schematics.py` and `python3 kicad/run_sims.py`, and keep KiCad's ERC at zero
  violations. After a change to the observer (`thermal.*`) or to `matlab/`, run `crosscheck` in
  Octave (`matlab/README.md`); the Octave copy must still agree with the firmware. After a change
  to `scilab/`, run `make_models.sce`, `check_models.sce`, `render_pictures.sce` and
  `make_charts.py` (`scilab/README.md`). The student documents (`docs/student/`) are rebuilt with
  `python3 docs/student/make_student_docs.py` after any change to the numbers they quote.
- **Git:** commit to `main`. Messages are short and plain (`firmware: ...`, `docs: ...`). Every
  commit ends with the trailer
  `Co-authored-by: muskan sultana <335379570+sultanamuskan@users.noreply.github.com>`. **No
  `Co-Authored-By: Claude` line or any other AI attribution** in commits or pull requests
  (organisation policy). The remote is `origin`, `git@github.com:KiranPranay/predictive_bms.git`
  (public); ask before pushing.
- **Keep out of git:** company documents (such as the purchase indent), other students' documents
  or names, and copyrighted papers (such as the base paper's PDF).
- **This computer:** no sudo, apt or system-wide installs. ESP-IDF lives in `.tools/`, ngspice and
  GNU Octave in `.tools/sim/` (micromamba; start Octave with `micromamba run -p .tools/sim octave`),
  and Python packages in `.venv/`, all git-ignored. KiCad 10 is the user's Flatpak
  (`flatpak run --command=kicad-cli org.kicad.KiCad`), and so is Scilab
  (`flatpak run --command=scilab-cli org.scilab.Scilab`). Anything else: write the command and the
  reason, and ask.
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
| `kicad/` | KiCad 10 simulation sheets in `sim/`, written by `make_schematics.py` (with `sch.py`); `run_sims.py` exports them with kicad-cli, runs ngspice and checks the results |
| `matlab/` | the thermal model and Kalman observer in GNU Octave / MATLAB; `crosscheck.m` compares them with the firmware on the simulator's per-sample logs (`bms_sim run NAME --csv FILE --csv-all`) |
| `scilab/` | the Xcos models (Scilab 2027.0.0 on Windows, the Flatpak's 2026.0.1 here), written by `make_models.sce` and checked by `check_models.sce` |
| `docs/student/` | the presentation guide and the viva notes for the student, in simple English, built by `make_student_docs.py` |
