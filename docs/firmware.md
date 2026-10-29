# Firmware

ESP-IDF v5.5, C++17, FreeRTOS, on an ESP32-WROOM-32 DevKit. The firmware is built in two parts:

- **`firmware/components/bms_core/`**: every algorithm of the architecture, in portable C++ with
  no ESP-IDF code. The ESP32 runs it, and the PC builds the same files for the tests and the
  simulator (`host/`). What the tests check is what the ESP32 runs.
- **`firmware/main/`**: the ESP32 side: drivers, tasks, console, Wi-Fi and the web server.

## 1. Tasks

| Task | Core | Priority | Period | Job |
| --- | --- | --- | --- | --- |
| `safety` | 1 | highest application priority | 200 ms (5 Hz) | read every sensor, run the supervisor, drive the relays and alarm, save the latch, feed the task watchdog |
| console (REPL) | any | normal | on input | commands; talks to `safety` only through a queue |
| web server | 0 | low | on request | the dashboard and `/api/state`; reads a copy of the snapshot |
| Wi-Fi | 0 | ESP-IDF | | the network link only |

The safety task never waits for Wi-Fi, the console or the web server (section 8, rule 8). It
publishes a snapshot once a second under a mutex; the other tasks read the copy.

One sample takes about 45 ms: four ADS1115 conversions at 128 samples/s (about 36 ms), the
INA226 registers, and 16 ADC conversions for each of the five NTCs. The task watchdog restarts
the ESP32 if the safety task stops for 2 s; a restart leaves both relays open (section 10).

## 2. Where each part of the architecture lives

| Architecture | Code (`firmware/components/bms_core/`) |
| --- | --- |
| 5: cumulative taps, cell voltages, tap order, negative cell, 100 mV jump | `sensors.cpp`, `FrontEnd::process` |
| 6: NTC conversion, open and shorted sensors | `sensors.cpp`, `ntc_temperature_c` |
| 8, rules 1–3: 5 Hz, median of 5, 10 s low-pass, 30 s regression slope | `filters.h`, `sensors.cpp` |
| 8 table: limits, warnings, trips | `supervisor.cpp`, `Supervisor::check_limits` |
| 8, rules 4–6: persistence, hysteresis, latch, manual reset | `filters.h` (`Persist`), `Supervisor::trip`, `Supervisor::request_reset` |
| 9.1: two-state model, exact discretisation | `thermal.cpp`, `discretise` |
| 9.2: Kalman observer of T_c, T_s, Q_ab; cell comparison; sensor contact | `CellObserver`, `Supervisor::run_thermal` |
| 9.3: predict and confirm, prediction-accuracy record | `Predictor`, `RmsRecord` |
| 9.4: online resistance | `electrical.cpp`, `ResistanceTracker` |
| 9.5: rest leak estimate and energy cross-check | `LeakEstimator`, `Supervisor::run_thermal` |
| 9.6: settling temperature, time to limit, safe current | `thermal.cpp`, `forecast` |
| 9.7: self-acceleration | `risk.cpp`, `CellRisk::step` |
| 9.8: risk levels | `risk.cpp` |
| 9.9: fallback | `ModelMode` in `types.h`; `Supervisor::run_thermal`, `check_limits` |
| 10: failure behaviour | `Supervisor::check_limits` (sensors), `main.cpp` (restart after a crash), `outputs.cpp` (relays open at start) |

All fixed values are in `include/bms/config.h`, each with its section number.

## 3. Values the architecture does not set

These are development values. Each is listed with the gate that confirms or replaces it. Change
them only with that gate's measurements, never to make a test pass.

| Value | Setting | Where | Confirmed at |
| --- | --- | --- | --- |
| Persistence of the voltage, temperature, spread and current limits | 1.0 s | `kLimitHoldS` | Gates 2, 3 |
| Release bands (hysteresis): voltage, temperature, current | 20 mV, 1 °C, 0.2 A | `kHystV`, `kHystC`, `kHystA` | Gates 9, 10 |
| Release bands: rate and heat levels, cell comparison, time to limit | 0.1 °C/min, 0.05 °C/min, 60 s | `kHystRateCPerMin`, `kHystDiffCPerMin`, `kHystTimeS` | Gate 11 |
| Plausible NTC range | −20 to 100 °C | `kNtcMinC`, `kNtcMaxC` | Gate 1 |
| An NTC code that never changes is stuck after | 60 s | `kFlatLineS` | Gate 1 (check it never fires on a good channel) |
| No thermal verdict while the observer settles | 60 s | `kObserverWarmupS` | Gate 9 |
| Online resistance: largest accepted step result; steps before a drift verdict; settling bands | 0.5 Ω; 3; 10 % + 20 mA, 10 % + 5 mV | `config.h` | Gate 9 |
| Energy cross-check "agrees" when heat and leak power differ by no more than | 50 % or 0.05 W | `kCrossCheckTolerance`, `kCrossCheckFloorW` | Gate 11 |
| Kalman: NTC noise, core and surface model error, heat random walk (per sample) | 0.05 °C, 0.005 °C, 0.010 °C, 0.003 W | `KalmanTuning` in `types.h` | Gates 9, 11 |
| Thermal parameters before Gate 9 | c_core 40, c_surf 5 J/°C (sum = the 45 J/°C estimate), r_core 2.0 °C/W, r_air 30 °C/W | `ThermalParams` | Gate 9 replaces them |
| Cell resistance before Gate 4 | 35 mΩ (the estimate) | `ModelParams` | Gate 4 replaces it |
| Manual reset button | BOOT held for 3 s | `board.h` | Gate 2 |

The Kalman values were chosen in the simulator: they hold the Gate 11 resistor's surface heating
to an 11 % overshoot (see [simulator.md](simulator.md)) while a 1 W fault still trips in about
70 s. Re-check them at Gates 9 and 11 with the real NTC noise (the `raw` command shows it).

## 4. How the firmware reads the architecture

Where the text leaves a choice, the firmware takes the reading below. Each one is on the safe
side or is needed for the stated behaviour.

1. **The 100 mV jump check (section 5)** compares each cell with the previous reading after
   allowing for the change of current (R × ΔI). Without this, every load step above about 3 A
   would read as a sensor fault. A single spike costs two invalid samples, a sensor notice only.
2. **Charge temperature limits (section 8)** apply while charging (current at or below −20 mA,
   the rest band of section 9.5). The discharge temperature limits always apply. T_trip in 9.6 is
   45 °C while charging and 55 °C otherwise.
3. **Every trip latches** (section 3), including the voltage and current limits, and the latch is
   kept in flash: a restart never clears it. A restart after a crash, a watchdog or a brown-out
   latches its own trip, `controller_reset`, opening both branches (section 10). The Gate 2 stop
   rule "a fault automatically clears" can therefore not happen through a restart.
4. **Sensor faults open both branches**: a missing reading is ambiguous (section 8: "or both if
   ambiguous").
5. **The leak estimate (9.5) compares each cell with the mean of the other three**, not of all
   four. With all four, one leaking cell is compared partly with itself and shows only three
   quarters of its leak. The architecture's own example ("about 6 mV per hour relative to the
   others") matches the three-cell form.
6. **In the cell-to-cell comparison (9.2), negative abnormal heat counts as zero** in the mean of
   the other cells. A lifted NTC gives one cell a large negative value, which would otherwise make
   the three healthy cells look hot and trip the pack on the wrong cell. Negative heat is the
   sensor-contact sign and has its own check.
7. **The self-acceleration window (9.7) starts no earlier than the moment the cell reached
   Warning.** Read literally, the sudden start of any fault is a rise of more than 50 % within
   120 s, so a steady 0.4 W fault would trip, while table 9.8 holds it at Warning.
8. **Forecasts (9.6) use the abnormal heat only when positive**: noise must not make a forecast
   more hopeful.
9. **A cold 5-minute confirmation (9.3) counts as "under load"** when the mean current over those
   5 minutes is 1 A or more, the same 1 A as the sensor-contact check of 9.2.
10. **The observer reads the median-filtered temperature**, not the 10 s low-pass: the Kalman
    filter is itself the filter, and the low-pass lag would show as false abnormal heat during
    every load change. The limits and dT/dt use the 10 s low-pass as section 8 says.
11. **"Since the last reset" (9.3)** means since the ESP32 started or since `stats clear`.
12. **Manual reset (section 8, rule 6)** also requires 60 s since any trip condition was last
    present, and both relays stay open at start until every sensor has read plausibly for 2 s.
13. **Model modes (9.9).** `off`: the thermal parts are ignored and the raw rate limits are 0.5
    and 1.0 °C/min. `estimates`: the predictive layer runs on estimated values for development on
    dummy heat sources, as the project plan describes for semester 1, and the raw limits stay at
    0.5 and 1.0 °C/min. `fitted`: after Gate 9, with the raw limits at 1.0 and 2.0 °C/min.

## 5. Console

USB serial at 115200 baud (`idf.py monitor`, or any terminal). `help` lists everything.

| Command | Use |
| --- | --- |
| `status` | pack, cells, relays, risk, latch |
| `raw` | raw ADC volts, shunt microvolts, NTC millivolts and codes: the readings for Gate 1 |
| `events` | recent events and the trip records |
| `reset` | manual reset (same as holding BOOT for 3 s); accepted only under rule 6 |
| `log off\|1\|5` | CSV telemetry lines (prefix `CSV,`) at 1 or 5 per second |
| `stats clear` | clear the prediction-accuracy record |
| `cal show` | the stored calibration |
| `cal tap N GAIN OFFSET_V` | Gate 1, from `tools/calibrate.py` |
| `cal shunt OHM GAIN OFFSET_A` | Gate 1 |
| `cal ntc N OFFSET_C`, `cal vref MV` | Gate 1: NTC offset, measured 3.3 V rail |
| `model show` | the stored model |
| `model r0 R1 R2 R3 R4` | Gate 4 resistances, mΩ |
| `model thermal CC CS RC RU1 RU2 RU3 RU4` | Gate 9, from `tools/fit_thermal.py` |
| `model ocv V1 S1 [V2 S2 ...]`, `model ocv clear` | Gate 10, from `tools/ocv_table.py` |
| `model kalman MEAS CORE SURF HEAT` | observer tuning |
| `model mode off\|estimates\|fitted` | section 9.9 |
| `test hang`, `test crash` | Gate 2: watchdog and crash; both relays must open and stay open |
| `wifi on\|off` | Objective 5: show every protection works with Wi-Fi off |
| `sim on\|off`, `sim COMMAND` | bench mode, only in a bench build (below) |

Everything set with `cal` and `model` is saved in flash and applied at once.

## 6. Bench mode (Gates 2 and 3 only)

Before cells are connected every sensor reads as faulted, so the relays never close. The bench
build adds `sim on`: the supervisor then reads the simulated pack from
`firmware/components/bms_sim/`, while it drives the **real** relays and alarm. This allows the
Gate 2 relay tests on a benign 12 V lamp and the Gate 3 cutoff tests "with simulated voltage and
temperature signals". Plant commands such as `sim load 2`, `sim heat 2 0.5` or `sim ntc 3 open`
inject faults (full list in `firmware/components/bms_sim/include/sim/commands.h`).

- Build it separately: `idf.py -B build-bench -D SDKCONFIG=build-bench/sdkconfig -D SDKCONFIG_DEFAULTS="sdkconfig.defaults;sdkconfig.bench" build`.
- `sim on` refuses when the top tap reads more than 1 V, and bench mode stops by itself if a pack
  appears on the taps.
- A real I2C failure still counts in bench mode, so Gate 2 step 4 (interrupt I2C) works.
- The dashboard shows "BENCH MODE: SIMULATED SENSORS" and every CSV line ends in `SIM`.
- The latch carries across `sim on` and `sim off`; leaving bench mode never clears a trip.
- From Gate 4 on, flash the normal build. A release build never has bench mode.

## 7. Telemetry

**`GET /api/state`** returns the snapshot as JSON, once a second fresh. Main fields: `state`,
`mode`, `model`, `risk`, `relays`, `alarm`, `warnings`, `pack` (`v`, `i`, `t_amb`, `i_safe`,
`t_trip`), `latch`, `trip_log` (time, code, detail, voltages, current, temperatures, abnormal heat,
leak, relay states), `sensors`, `leak`, `events`, and `cells[4]` with `v`, `r_mohm`, `t_s`, `t_c`,
`q_w`, `q_rate`, `q_diff`, `f1`, `f5`, `e1`, `e5`, `verdict`, `rms5_hour`, `rms5_all`, `t_eq`,
`ttl_s`, `i_safe`, `leak_ma`, `cross`, `level`, `reasons`. Missing values are `null`. The writer is
`telemetry.cpp` in the core, shared by the ESP32 and the simulator.

**CSV** (`log 1`, and `bms_sim run NAME --csv FILE`), one header line, then one line a second:

```text
t_s,mode,load,charge,risk,current_a,v1,v2,v3,v4,ts1,ts2,ts3,ts4,t_amb,tc1,tc2,tc3,tc4,q1_w,q2_w,q3_w,q4_w,r1_mohm,r2_mohm,r3_mohm,r4_mohm
```

## 8. Building

```bash
export IDF_TOOLS_PATH=$PWD/.tools/espressif      # the project-local ESP-IDF
. .tools/esp-idf/export.sh
cd firmware
idf.py build
idf.py -p /dev/ttyUSB0 flash monitor            # Windows: -p COM3
idf.py menuconfig                               # Predictive BMS: Wi-Fi, I2C addresses, alarm
```

Any ESP-IDF v5.5 installation works the same way. The partition table is "single app, large";
the image uses about two thirds of it.
