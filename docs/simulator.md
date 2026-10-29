# The simulated pack

The simulator runs the supervisor core, the same code as the ESP32, against a simulated 4S1P
pack. It does three jobs:

1. **Tests.** 29 scenarios rehearse the Gate 9, 10 and 11 tests and the sensor failures of
   section 10, each with checks taken from the gate's pass criteria. They run as part of `ctest`.
2. **Software validation first.** Gate 11 step 1 asks to "validate software first with recorded
   traces and synthetic ramps". The scenarios are that step, done before any cell is connected.
3. **A live demonstration.** `tools/sim_server.py` puts the dashboard on a running simulation, with
   buttons that inject faults.

```bash
cmake -S host -B build/host && cmake --build build/host
build/host/bms_sim list                    # the scenarios
build/host/bms_sim run all                 # every scenario with its checks
build/host/bms_sim run soft_short --csv soft_short.csv   # one scenario, with its 1 Hz log
python3 tools/sim_server.py --speed 10     # dashboard at http://127.0.0.1:8080/
```

## 1. The plant

The plant is `firmware/components/bms_sim/`. Its numbers are illustrative values for a 3.3 Ah
NMC 18650. They are **not** measurements of the project's cells, and nothing in the firmware
takes a value from them.

| Part | Model |
| --- | --- |
| Cells | state of charge; a smooth NMC open-circuit-voltage curve; DC resistance about 35 mΩ (±2 % between cells); one polarisation stage (8 mΩ, 30 s) |
| Heat | the same two-state structure as section 9.1 (c_core 40, c_surf 5 J/°C, r_core 2 °C/W; r_air 28 °C/W for the end cells and 31 °C/W for the middle cells), driven by the **true** heat: I²R, plus the polarisation loss that the supervisor's model does not have |
| Hardware BMS | cuts the pack at 4.25 V or 2.7 V per cell; bleeds 30 mA from a cell above 4.18 V |
| Relays and charger | the load draws its current only while K_LOAD is closed; the charger is CC/CV (16.8 V) and flows only while K_CHARGE is closed |
| Sensors | divider ratios drawn from 1 % resistors; ADS1115 125 µV steps and noise; INA226 2.5 µV steps and noise; NTC voltages with 1.5 mV noise |
| Faults | abnormal heat in a core, constant or growing with temperature; the Gate 11 resistor across a cell's taps (it drains the cell and heats its can); an internal soft short; a lifted, open, shorted or stuck NTC; an NTC offset (a simulated signal); ADS1115 or INA226 bus loss; single-sample spikes; a crash and restart |

## 2. Scenarios

The supervisor is set up as after Gates 1, 4, 9 and 10, except where the table says the model is
off.

| Scenario | Gate | What it shows |
| --- | --- | --- |
| `rest` | 9 | 30 minutes at rest: Normal, small abnormal heat, accurate forecasts |
| `discharge_steps` | 9 | 0.25–2 A steps: no flags, forecasts within 0.5 °C RMS, resistance within 15 % |
| `discharge_5a` | 9, 11 | 4.8 A for 20 minutes: the heating expected near 5 A is not flagged |
| `charge` | 10 | 1.5 A charge to 4.10 V per cell: no flags, small spread |
| `heat_no_current` | 11 | 1 W in a cell with no current: Warning, then Trip below 40 °C |
| `heat_warning` | 11 | 0.41 W in a cell: Warning and alarm, both branches stay on |
| `small_fault` | 11 | 0.2 W in a cell: the 5-minute confirmation (+1 °C) raises Watch |
| `cell_outlier` | 11 | 0.55 W in one cell under 2 A: trips on the cell-to-cell difference |
| `self_acceleration` | 11 | heat growing with temperature in every cell: self-acceleration trip |
| `soft_short` | 11 | 47 Ω across cell 2: leak, heat and confirmation agree; Warning |
| `internal_leak` | 11 | 25 mA internal leak: found electrically, Watch only |
| `forecast_hot_day` | 9 | 4.6 A at 35 °C: safe-current and time-to-limit Watch, then the load trip |
| `ntc_lift_off` | 11 | NTC3 lifts under 3 A: sensor-contact fault, both branches open |
| `ntc_open`, `ntc_short`, `ambient_open` | 1, 11 | a broken NTC: sensor fault after 2 s |
| `ntc_stuck` | 11 | a flat-line NTC: sensor fault after 60 s |
| `ads_loss`, `ina_loss` | 2 | I2C bus loss: both branches open after 2 s |
| `spikes` | 11 | single-sample spikes: rejected, no trip |
| `load_steps` | 9 | 0–3 A steps every 20 s: no false trips, resistance tracked |
| `cell_high_charge` | 10 | one cell reaches 4.15 V on charge: only the charge branch opens |
| `cell_low_discharge` | 9 | one cell reaches 3.10 V on discharge: only the load branch opens |
| `overcurrent` | 9, 10 | 5.3 A load and 1.8 A charge: each opens only its own branch |
| `charge_overtemp` | 10 | 45 °C while charging: only the charge branch opens |
| `temp_spread` | 11 | a 10 °C spread (simulated signal, model off): both branches open |
| `backstop_unfitted` | 11 | model off: the raw 1.0 °C/min backstop trips |
| `reset_rules` | 2 | latches hold through restarts; reset only when the rules allow |
| `fit_log` | 9 | 1 A and 2 A discharges with cooling curves, model off: the data for the Gate 9 fit |

All 29 pass. Some results from the run:

| Result | Value | Target |
| --- | --- | --- |
| 5-minute prediction error at rest, during the steps and during the charge | 0.02–0.11 °C RMS | ≤ 0.5 °C RMS (Gates 9, 10) |
| Largest abnormal heat in healthy use, 0.25–2 A and charging | 0.06 °C/min | < 0.25 °C/min (Gates 9, 10) |
| Online resistance against the true value | within 2 % | within 15 % (Gate 9) |
| 1 W fault with no current: time to Trip, cell temperature then | 70 s, 26.3 °C | before any fixed limit |
| 0.2 W fault: 5-minute confirmation | +1.19 °C, Watch | +1.0 °C raises Watch (9.3) |
| Gate 11 soft short (47 Ω): leak estimate against the current drawn | 72 mA against 79 mA | rises in that cell only |
| Gate 11 soft short: abnormal heat against the heat reaching the cell | 0.24 W against 0.24 W | cross-check agrees |
| 25 mA internal leak: estimate | 23 mA | ≥ 20 mA raises Watch |
| Sensor faults | latched at 2.0 s (stuck NTC: 62 s) | 2 s persistence |

## 3. What the simulator found

These are results about the method, not about the real cells. Each one names the gate where the
real pack answers it.

**Heat the model leaves out.** Real cells make more heat than I²R with the resistance a 0.2 s
current step measures, because of polarisation. In the simulator this extra heat shows as
abnormal heat: 0.06 °C/min at 2 A, but 0.26 °C/min at 4.8 A, half of the Warning level. Gate 9
measures how large it really is.

**What the Gate 9 fit can and cannot find.** A fit to the `fit_log` data matches the surface
temperature to 0.025 °C RMS, but gives a total heat capacity of 30.5 J/°C where the plant has
45 J/°C, and r_core 10.6 °C/W where the plant has 2 °C/W. Normal discharges set only each cell's
time constant and its temperature rise per watt; heat capacity, r_core, r_air and any missing
heat trade against each other. Fixing the heat capacity from the cells' mass does not help: the
fit is equally good at 40, 45 or 50 J/°C. This is what the architecture expects ("the fit absorbs
it"), and the fitted model still predicts accurately. With the fitted values loaded, 28 of the 29
scenarios pass. The exception is `heat_warning`. The fitted model reads abnormal heat about 20 %
high in °C/min, so a steady 0.41 W fault, inside the narrow band where the architecture holds it
at Warning (0.375–0.45 W), trips on the cell-to-cell rule instead. That is the safe direction.
The cost is that the watts on the dashboard carry the same scale error, so the energy
cross-check (9.5) agrees only within that error. To try a fit:

```bash
build/host/bms_sim run fit_log --csv gate9.csv
.venv/bin/python tools/fit_thermal.py gate9.csv
build/host/bms_sim run all --thermal <the seven values it prints>
```

**The Gate 11 resistor heats the can, not the core.** The observer's model puts abnormal heat in
the core. Heat at the surface makes the reading rise faster than any core heat could, and with
the first Kalman tuning the estimate jumped to 0.52 W for about 20 s, more than twice the true
0.24 W. That is enough to trip the pack on the cell-to-cell rule the moment the resistor is
fitted. The tuning now in the firmware lets the surface state absorb fast changes: the overshoot
is 11 % (0.26 W). At Gate 11, mount the resistor on the opposite side of the cell from its NTC,
watch the abnormal heat for the first minute, and re-check the tuning with the real NTC noise.

**The soft short needs 90 minutes.** The leak estimate waits 30 minutes after the last load or
charge, then fills a 60-minute window. In `soft_short` the resistor went on after 31 minutes at
rest and Warning came 59 minutes later, when the window was full. On the way, the cell-to-cell
heat difference raised Watch. Cell 2 was then 6.6 °C above the others and still warming, close
to the 7 °C spread warning; with the resistor left on longer the warning appears. Plan the
Gate 11 session for about two hours.

**The leak estimate is only as good as the Gate 10 table.** With three pauses (3.6, 3.8 and
4.0 V), a 25 mA leak read as 23 mA, because the slope between pauses differs from the slope at
the cell's own voltage. More pauses give a closer table; the firmware takes up to eight points.

**The time-to-limit forecast settles in about 5 minutes.** At 4.6 A and 35 °C, one minute after
the load started the forecast said 42 minutes while 30 minutes were left, because the model did
not yet know the missing heat. Once the observer had absorbed it (about 0.16 W), every forecast was within about
5 % of the time actually left.

**Self-acceleration is the fast path when cells heat together.** For one hot cell, the
cell-to-cell rule (0.6 °C/min) always trips before the heat can grow 50 % beyond the Warning
level. The self-acceleration test acts when the cells heat together, and when Warning came from
thermal and electrical evidence agreeing.
