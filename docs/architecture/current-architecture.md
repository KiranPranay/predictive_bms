# Predictive 4S BMS — Current Build Architecture

**Status:** build authority for the prototype
**Revision:** 2.2 — 24 October 2026 (adds the predictive thermal layer in section 9 and a fifth NTC for ambient temperature)
**Supersedes for construction:** the hardware diagrams in the first-review deck. The submitted review files remain historical records and must not be used as wiring instructions.

## 1. Objective and design envelope

Build a **4S1P, 14.4V nominal / 16.8V maximum, 3.3Ah nameplate (about 47.5Wh nominal) NMC lithium-ion prototype** using four existing red-rewrapped cells marked `PW 3300mAh NCR18650GA` that:

- measures each cell voltage, pack current, four cell-body temperatures and the ambient air temperature;
- calculates filtered temperature rate-of-rise (`dT/dt`) for every cell;
- runs a two-state thermal model and Kalman observer for every cell, estimating its core temperature and the abnormal heat, in watts, that its current cannot explain;
- predicts each cell's temperature 1 and 5 minutes ahead, then confirms each prediction against the real reading when that time arrives;
- cross-checks thermal evidence of an internal short against electrical evidence, the cell's self-discharge at rest, by an energy balance;
- forecasts each cell's settling temperature, time to its limit and the safe continuous current, and combines all evidence into one staged risk level;
- independently disconnects the charger and the load under software control;
- retains an independent hardware protection and balancing layer if the ESP32, firmware, Wi-Fi, or sensor code fails;
- exposes readings and latched faults on a Wi-Fi dashboard without making Wi-Fi part of the safety chain.

This is a **5A continuous prototype**, not a 20A system. Charging is limited to **1.5A**. Charge and discharge must not be intentionally operated at the same time during prototype tests.

### Existing-cell configuration and evidence

The four cells remain a normal costed BOM item even though this build can reuse stock recovered from earlier battery packs. The dashboard therefore records both facts: procurement state is **available from existing stock**, while quantity, replacement source, product code, purchase link and full replacement value remain visible for any future builder.

The supplied photographs show a representative red rewrapped cell marked `PW`, `3300mAh` and `NCR18650GA`, with signs of earlier pack attachment around the terminals. The user has confirmed the set is serviceable. Photographs and labels do not establish capacity, internal resistance, common history or authenticity, so the four-cell set must still pass Gate 4 matching before welding. Design calculations use the conservative 3.3Ah label capacity; genuine NCR18650GA references list 3.35Ah minimum and about 3.45Ah typical capacity.

## 2. Why the 4S spring holder is removed

The pack is being spot-welded with pure nickel and enclosed in a printed case. A spring holder would duplicate the pack structure and insert eight spring contacts into the current path. Those contacts add resistance, can loosen, and create extra heating that contaminates the thermal measurements.

The welded pack therefore uses:

- flame-retardant 18650 cell spacers above and below the cells;
- fish-paper rings on every positive terminal;
- pure nickel welds;
- fish/barley-paper barriers over exposed conductors;
- a heat-shrink sleeve around the completed insulated pack;
- a vented PETG enclosure with strain-relieved connectors.

The spacers are not electrical contacts; they only establish cell spacing and mechanical alignment.

## 3. Safety architecture

The design has two independent layers.

### Layer A — hardware protection, always active

The 4S hardware BMS is directly connected to `B-`, `B1`, `B2`, `B3`, and `B+`. It provides cell over-voltage, cell under-voltage, short-circuit/over-current protection, and passive balancing. Its common protected output is `P+ / P-`.

The selected board's published values are approximately:

| Function | Hardware threshold |
| --- | ---: |
| Over-charge detect | 4.25V ± 0.05V per cell |
| Balance start | 4.18V |
| Balance current | 30mA ± 5mA |
| Over-discharge detect | 2.7V ± 0.1V per cell |
| Rated continuous discharge | 20A board rating — **not the project limit** |

The **7.5A fuse at B+** protects the prototype wiring and relay path. The BMS's high current rating is only margin; it does not replace the fuse or the 5A firmware/bench limit.

### Layer B — predictive supervisory control

The ESP32 monitors the pack and drives two normally-open relay contacts:

- `K_LOAD`: connects protected `P-` to `LOAD-`;
- `K_CHARGE`: connects protected `P-` to `CHARGE-`.

`LOAD+` and `CHARGE+` are fed from fused, current-monitored `P+`. Separate negative switching lets firmware disable charging while leaving discharge available, or disable discharge while leaving controlled charging available. Both relay inputs have pull-ups so reset, disconnected GPIO, or unpowered control defaults both contacts **open**.

The relays are safety disconnects, not PWM devices. A trip is latched until a deliberate manual reset after the cause has cleared.

## 4. Power path and named nets

```text
4S1P cells → BMS B+/B-/B1/B2/B3 → P+
P+ → 7.5A fuse → 5mΩ shunt → FUSED+
FUSED+ → LOAD+ and CHARGE+
P- → relay K_LOAD NO contact → LOAD-
P- → relay K_CHARGE NO contact → CHARGE-
P+/P- → LM2596 (5.0V) → ESP32 VIN + relay VCC
ESP32 3.3V → ADS1115 + INA226 logic + divider/NTC references
```

Mount the fuse physically next to the pack positive exit. Put the INA226 shunt after the fuse and before the charge/load split. Positive current means discharge; negative current means charge. Because the monitor is common to both branches, do not charge and power the load simultaneously during the prototype phase.

The LM2596 is connected to protected `P+/P-` before the two branch relays. A software relay trip therefore leaves logging alive, while a hardware BMS under-voltage trip also removes controller power and prevents the controller from bypass-draining the pack.

## 5. Cell-voltage measurement

The ADS1115 runs from 3.3V and measures four cumulative tap voltages relative to `B-`:

| ADS1115 channel | Source | Nominal maximum | Computed cell |
| --- | --- | ---: | --- |
| A0 | `B1` | 4.2V | `Vcell1 = Vtap1` |
| A1 | `B2` | 8.4V | `Vcell2 = Vtap2 - Vtap1` |
| A2 | `B3` | 12.6V | `Vcell3 = Vtap3 - Vtap2` |
| A3 | `B+` | 16.8V | `Vcell4 = Vtap4 - Vtap3` |

Each tap uses a nominal **330kΩ high-side / 56kΩ low-side divider**, a 10kΩ series resistor, a 100nF filter capacitor, and low-leakage clamps. The divider ratio is about 0.145; 16.8V becomes about 2.44V. Measure the actual resistance of every divider and store its calibration coefficient. The firmware must reject impossible tap order, negative derived cell voltage, or a jump larger than 100mV between adjacent samples.

High-value dividers reduce permanent imbalance but make contamination and clamp leakage important. Clean flux residue and verify each channel against a calibrated multimeter over the full range before connecting cells.

## 6. Temperature measurement

Use four small 10k B3950 bead NTCs, one at the middle of each cell can, and a fifth in free air in the enclosure vent path, away from the cells, the LM2596 and the relay contacts, to measure ambient temperature for the thermal model in section 9. Bond the cell NTCs with electrically insulating, thermally conductive tape; do not place the bead on exposed nickel.

Each NTC forms a divider with a 10kΩ 1% pull-up to 3.3V and a 100nF filter. Connect only to ESP32 **ADC1** pins because ESP32 ADC2 is unavailable while Wi-Fi is active.

| Cell | ESP32 pin |
| --- | --- |
| NTC1 | GPIO32 / ADC1_CH4 |
| NTC2 | GPIO33 / ADC1_CH5 |
| NTC3 | GPIO34 / ADC1_CH6 |
| NTC4 | GPIO35 / ADC1_CH7 |
| Ambient NTC | GPIO36 / ADC1_CH0 (input-only, labelled VP on the DevKit) |

Calibrate every channel at ambient and at one controlled warm reference point. A disconnected or shorted NTC is a fault, not a valid extreme temperature.

## 7. Digital interfaces and outputs

| Function | ESP32 pin | Notes |
| --- | --- | --- |
| I2C SDA | GPIO21 | ADS1115 and INA226 at 3.3V |
| I2C SCL | GPIO22 | 4.7kΩ pull-ups only if not already fitted |
| Load relay | GPIO25 | Active LOW; 10kΩ pull-up; normally-open power contact |
| Charge relay | GPIO26 | Active LOW; 10kΩ pull-up; normally-open power contact |
| Fault buzzer/LED | GPIO27 | Latched alarm output through suitable driver/resistor |

Verify the exact relay board input state with a bench supply before connecting pack power. If either relay energises during ESP32 reset, add a transistor stage that guarantees de-energised startup.

## 8. Software limits for the prototype

These are conservative supervisory limits, not cell-manufacturer absolutes.

| Condition | Warning | Trip action |
| --- | --- | --- |
| Any cell high | 4.10V | At 4.15V disable charge |
| Any cell low | 3.20V | At 3.10V disable load |
| Charge temperature | 40°C | At 45°C disable charge |
| Discharge temperature | 50°C | At 55°C disable load |
| Temperature spread | 7°C | At 10°C disable both branches |
| Predictive thermal risk (section 9.8) | Level 2, Warning | Level 3, Trip: disable both branches |
| Rate of rise, raw backstop | 1.0°C/min for 30s | At 2.0°C/min for 10s disable both branches (0.5°C/min warning and 1.0°C/min trip until the model is fitted; section 9.9) |
| Pack current | 4.5A | At 5.0A disable load; 1.6A disables charge |
| Sensor plausibility | one invalid sample | persistent 2s fault disables affected branch or both if ambiguous |

Implementation rules:

1. Sample raw sensors at 5Hz and timestamp with a monotonic clock.
2. Apply a median-of-5 rejection stage, then a 10s low-pass estimate for temperature.
3. Calculate `dT/dt` by linear regression over the most recent 30s window; do not differentiate adjacent samples.
4. Require both persistence and hysteresis; do not chatter relays around a threshold.
5. Latch every trip with timestamp, measurements, reason, and relay state.
6. Permit manual reset only when every cell is 3.20–4.10V, every NTC is below 40°C, all sensors are plausible, and the initiating condition has cleared for 60s.
7. Hardware BMS protection remains the final backstop; software must never attempt to defeat it.
8. Run the predictive layer of section 9 in the safety task on the same filtered samples, never in the telemetry task.

The numerical limits must be revisited after sensor calibration and controlled benign tests. Never tune them by provoking thermal runaway in a live cell.

## 9. Predictive thermal layer

Sections 5–8 measure the pack and act on limits. This section is what makes the supervisor predictive. On every filtered sample it runs a physical model of each cell that predicts what the cell *should* be doing, estimates what no sensor can measure directly, forecasts where each cell is heading, and later checks each forecast against what really happened. It follows the predict–compare–flag structure of the base paper, Ojo et al. (IEEE TIE, 2021), but replaces its neural network with a physical model, so it needs no training data, every output has a physical unit, and it runs on the ESP32.

| Part | What it predicts or estimates | Section |
| --- | --- | --- |
| Two-state thermal model | How a healthy cell's core and surface temperature respond to its current | 9.1 |
| Kalman observer | Core temperature and abnormal heat, in watts | 9.2 |
| Predict and confirm | Each cell's temperature 1 and 5 minutes ahead, then checked against the real reading | 9.3 |
| Online resistance | Each cell's internal resistance | 9.4 |
| Rest leak estimate | Each cell's self-discharge current, and an energy cross-check against the abnormal heat | 9.5 |
| Operating forecasts | Settling temperature, time to limit and safe continuous current | 9.6 |
| Self-acceleration test | Whether the abnormal heat grows as the cell gets hotter | 9.7 |
| Risk level | One staged verdict from all the evidence | 9.8 |

### 9.1 Two-state thermal model

Each cell has a core and a surface, following Lin et al. (IEEE TCST, 2013):

```text
C_c · dT_c/dt = I² · R_i + Q_ab,i − (T_c − T_s) / R_c
C_s · dT_s/dt = (T_c − T_s) / R_c − (T_s − T_amb) / R_u,i
```

| Symbol | Meaning | Where it comes from |
| --- | --- | --- |
| `T_c`, `T_s` | core and surface temperature of the cell; only `T_s` is measured | NTC1–4 for `T_s` |
| `T_amb` | ambient air temperature | the ambient NTC |
| `I` | pack current, the same in all four series cells | INA226 |
| `R_i` | DC internal resistance of cell *i* | Gate 4, then tracked online (9.4) |
| `Q_ab,i` | abnormal heat: heat the current cannot explain; zero for a healthy cell | estimated (9.2) |
| `C_c`, `C_s` | heat capacity of the core and of the surface layer, J/°C; about 45 J/°C together for an 18650 | fitted at Gate 9 |
| `R_c` | thermal resistance from core to surface, °C/W | fitted at Gate 9 |
| `R_u,i` | thermal resistance from cell *i*'s surface to the air, °C/W; per cell, because end and middle cells cool differently | fitted at Gate 9 |

The `I²R` term is the irreversible part of the Bernardi heat equation used by Chen et al. (2024). Reversible (entropic) heat is not modelled; the fit absorbs it, and Gates 9 and 10 check that the result is good enough. The thermal parameters are fitted once at Gate 9 and then held fixed, so the model can never slowly learn a fault as normal.

### 9.2 Kalman observer: core temperature and abnormal heat

A discrete Kalman filter for each cell runs the model at 5Hz with the state `[T_c, T_s, Q_ab]`. `Q_ab` is modelled as a slowly varying state, so the filter estimates it from the gap between the measured and the predicted surface temperature. This gives two quantities no sensor provides:

- **Core temperature `T_c`.** Under load the core is hotter than the surface, which is all a sensor can touch. `T_c` is shown on the dashboard and used by the forecasts in 9.6.
- **Abnormal heat `Q_ab`, in watts.** This is the early sign the project looks for. A healthy cell under load has `Q_ab` near zero, because its current explains its heating, so normal load heating is never flagged. A cell heating with little or no current, which is how an internal short starts, shows a positive `Q_ab`.

For the limits, `Q_ab` is also expressed as the heating rate it causes, `Q_ab / (C_c + C_s)`: for an 18650, 0.5°C/min is about 0.4W and 1.0°C/min about 0.75W.

To stop a bad reading from explaining a fault away, `|I|` is clamped to 5.0A and `R_i` to the bounds in 9.4 when the expected heat is calculated.

Two further checks run on the observer output:

- **Cell-to-cell comparison.** The four cells carry the same current, so their abnormal heat should agree. Each cell's `Q_ab` is compared with the mean of the other three, so one cell drifting from its neighbours is flagged while every absolute value is still normal. This is the four-cell form of the cell comparison used for large packs by Sun et al. (IEEE TPEL, 2022).
- **Sensor contact.** A persistently negative `Q_ab` under load (below −0.4W for 60s with `|I|` at least 1A) means the cell reads cooler than its own current can explain, which is what happens when an NTC lifts off its cell. That is a sensor fault under section 10, not a temperature reading.

### 9.3 Predict and confirm

Every 10s the firmware predicts each cell's surface temperature 1 minute and 5 minutes ahead, and checks each prediction when its time comes.

1. **Predict.** From the present observer state, the model is run forward assuming the present current and ambient temperature continue. The dashboard shows the result, for example "Cell 2: 31.8°C now, 32.4°C in 1 min, 33.6°C in 5 min".
2. **Store.** The starting state and time are kept with each prediction.
3. **Confirm.** When the time arrives, the healthy model (`Q_ab` = 0) is re-run from the stored state using the current and ambient temperature actually measured in between, so a change of load is not counted as an error. The confirmation error is `e = measured T_s − predicted T_s`.

| Confirmation error at 5 min | Verdict |
| --- | --- |
| within ±0.5°C | **Confirmed normal**, shown as a tick on the dashboard |
| +1.0°C or more | **Hotter than predicted**, raises Watch (9.8) |
| −1.0°C or less under load | Treated as a possible sensor-contact fault, as in 9.2 |

A small, steady fault is easy to miss at any one moment but adds up over five minutes. For example, 0.2W of abnormal heat is only about 0.27°C/min, below the warning limit, but leaves the cell about 1.3°C hotter than predicted after five minutes, so it raises Watch.

The firmware also keeps a running record of the prediction error at both horizons (root-mean-square over the last hour and since the last reset). This is the evidence, in numbers, that the predictions are accurate; Gates 9 and 10 require a 5-minute error of no more than 0.5°C RMS in normal use.

### 9.4 Online internal resistance

Every step change in current of at least 0.5A gives each cell's resistance directly, `R_i = ΔV_i / ΔI`, from the cell voltages and current just before the step and on the first sample after it. This matches the Gate 4 DC-resistance method. Successive values are averaged over the last 20 steps. The model uses the average, bounded to ±30% of the Gate 4 value. A cell whose resistance drifts more than 30% from its Gate 4 value raises Watch. Rising resistance means ageing, a weak weld or connection, or a cell making more heat than it should for the same current.

### 9.5 Rest leak estimate and energy cross-check

An internal short drains its own cell, so it leaves an electrical trace as well as a thermal one. The firmware looks for it at rest: `|I|` below 20mA, no cell above 4.15V (so the BMS is not balancing), and at least 30 minutes after the last load or charge (so the voltages have settled). Each cell's voltage is compared with the mean of the four, which cancels temperature and measurement drift common to all of them. The slope of that difference over a 60-minute window gives the leak current:

```text
I_leak,i = − Q_cap · d(V_i − V_mean)/dt  /  (dOCV/dSOC)
```

Here `Q_cap` is 3.3Ah, and `dOCV/dSOC` is the slope of the cell's open-circuit-voltage curve at its present voltage. The slope comes from a table measured during the Gate 10 charge.

For example, a 20mA leak lowers a mid-charge cell by roughly 6mV per hour relative to the others (about 0.6% of its charge per hour, at roughly 10mV per 1%). The ADS1115 can measure that after averaging. Yet such a short makes only about 0.07W of heat, too little to see thermally, so the electrical check finds a soft short long before it is hot enough to measure.

**Energy cross-check.** A short with leak current `I_leak,i` turns about `V_i · I_leak,i` watts into heat inside the cell. When the observer's `Q_ab` and `V_i · I_leak,i` agree on the same cell, two independent measurements, one thermal and one electrical, point to the same internal fault. Both values are logged with the event.

### 9.6 Operating forecasts

At the present current, each cell's surface temperature settles at:

```text
T_s,eq,i = T_amb + (I² · R_i + Q_ab,i) · R_u,i
```

The model approaches it with a time constant `τ_i` taken from the fitted parameters. The forecasts are:

```text
if T_s,eq,i ≤ T_trip:   "settles at T_s,eq,i", the limit is never reached at this load
otherwise:              time to limit_i = τ_i · ln( (T_s,eq,i − T_s,i) / (T_s,eq,i − T_trip) )

safe continuous current  I_safe = min over i of  √( ( (T_trip − T_amb) / R_u,i − Q_ab,i ) / R_i )
```

`T_trip` is 45°C while charging and 55°C while discharging. Unlike a straight-line forecast, this one knows that a cell cools more as it warms. It can therefore say "this load is safe indefinitely" as well as "this load reaches the limit in 12 minutes". The safe current turns the prediction into an operating limit the user can see. With rough values for an 18650 in still air (about 30°C/W and 35mΩ), it comes out near the project's 5A limit at 25°C ambient, and lower on a hot day or if abnormal heat appears. A time to limit under 10 minutes, or a load current above `I_safe` for 30s, raises Watch.

### 9.7 Self-acceleration test

Thermal runaway begins as a chain of heat-producing reactions that speed up as the cell gets hotter (Feng et al., 2018). A cell heading towards runaway therefore shows abnormal heat that grows with its own temperature. While a cell is at Warning, the firmware checks the last 120s. If `Q_ab` has risen by at least 50% while `T_c` rose by at least 1°C, the heat is feeding itself, and the cell goes straight to Trip without waiting for the trip persistence timer.

### 9.8 Thermal risk level

All the evidence is combined into one level for each cell, and the highest level of the four is the pack's level. The level is shown on the dashboard and logged with the reason that set it.

| Level | Entered when any one of these holds | Action |
| --- | --- | --- |
| 0 Normal | none of the conditions below | — |
| 1 Watch | *thermal:* 5-minute confirmation +1.0°C or more (9.3); abnormal-heat difference from the other cells ≥ 0.3°C/min for 30s (9.2); time to limit under 10 min, or current above `I_safe` for 30s (9.6). *Electrical:* leak estimate ≥ 20mA (9.5); resistance drift over 30% (9.4) | Dashboard notice and log |
| 2 Warning | abnormal heat ≥ 0.5°C/min (about 0.4W) for 30s; **or** a thermal Watch and an electrical Watch on the same cell at the same time | Alarm on; both branches stay on |
| 3 Trip | abnormal heat ≥ 1.0°C/min (about 0.75W) for 10s; abnormal-heat difference ≥ 0.6°C/min for 10s; self-acceleration while at Warning (9.7) | Open both relays, latch and log |

A soft fault that is only a little out of line raises the alarm only when two independent kinds of evidence, thermal and electrical, agree on the same cell. A clear fault trips on its own. The rules are fixed tables, not a trained classifier, so every level can be traced back to the measurement that caused it.

### 9.9 Fallback

Until the thermal parameters are fitted at Gate 9, the thermal parts of this section are ignored. These are 9.2, 9.3, 9.6 and 9.7, and while they are off, the raw rate-of-rise limits return to 0.5°C/min warning and 1.0°C/min trip. The resistance tracking (9.4) runs from the first power-up. The leak estimate (9.5) runs once the Gate 10 voltage table exists. An invalid ambient NTC or current reading is a sensor fault and opens both relays under section 10. Fitted parameters are stored with the calibration record and are never widened just to pass a test.

### 9.10 Does it fit on the ESP32?

For each cell, the three-state Kalman filter takes a few hundred floating-point operations per sample. Four cells at 5Hz, plus the forecasts every 10s, come to well under 1% of a 240MHz ESP32 with its hardware floating-point unit. The 120s windows and the stored predictions use about 20kB of the 520kB of RAM, and the 60-minute leak window stores one-minute averages only. The whole layer runs in the safety task.

### 9.11 What is new

The base paper (Ojo et al.) predicts the cell's surface temperature with a trained neural network and flags the gap. Within the ten papers reviewed for this project, none does the following on a low-cost controller:

- estimate the abnormal heat itself, in watts, together with the core temperature, using a physical model and a Kalman filter that need no training data;
- predict each cell's temperature minutes ahead and then confirm every prediction against the real reading, keeping a running record of how accurate the predictions are;
- cross-check thermal evidence of an internal short against electrical evidence of the same short, by an energy balance;
- forecast a safe continuous current, not only a time to limit;
- combine all of this into one traceable risk level.

This is stated as a gap in the papers reviewed, not as a claim that no such work exists anywhere.

## 10. Failure behaviour

| Failure | Required result |
| --- | --- |
| ESP32 reset or crash | Both software relays open; hardware BMS remains active |
| Wi-Fi loss | Local monitoring and cutoffs continue; telemetry queues or drops safely |
| One NTC (cell or ambient) open/short | Latch sensor fault; disable both branches until diagnosis |
| NTC lifted off its cell | Detected as negative abnormal heat or a cold confirmation error under load (sections 9.2 and 9.3); latch sensor fault; disable both branches |
| ADS1115/INA226 communication loss | Open both relays and latch fault |
| Software relay welded closed | Hardware BMS and fuse remain capable of opening/clearing severe faults; remove pack from service |
| Hardware BMS opens | Controller loses power; pack remains disconnected until BMS recovery conditions are met |
| Reverse/misordered balance harness | Prevent connection during staged voltage check; never hot-plug an unverified harness |

## 11. Physical layout

- Put the fuse at the B+ exit, then shunt, then branch wiring.
- Keep BMS and electronics on insulated standoffs away from cell terminals.
- Route cell taps as a restrained low-current harness; add 1k–10k series resistance near each tap entry.
- Keep INA226 Kelvin pairs together and away from relay/contact current loops.
- Put relay contacts and power wiring on one side of the enclosure; analog sensing on the other.
- Provide vents around cells and electronics. Do not seal the enclosure or claim fire containment.
- Make the electronics cover removable without exposing cell terminals.

## 12. Sources used to validate the redesign

- [Orange/Robu 4S 20A BMS datasheet](https://robu.in/wp-content/uploads/2021/11/4S20A.pdf)
- [Robu 4S BMS wiring guide](https://robu.in/wp-content/uploads/2021/08/4S-20A.pdf)
- [TI INA226 product page](https://www.ti.com/product/INA226)
- [TI ADS1115 datasheet](https://www.ti.com/lit/ds/symlink/ads1115.pdf)
- [Feng et al., thermal runaway mechanism review, Energy Storage Materials 2018](https://doi.org/10.1016/j.ensm.2017.05.013)
- [Sun et al., cell-comparison thermal runaway warning, IEEE TPEL 2022](https://doi.org/10.1109/TPEL.2022.3173038)
- [Lin et al., lumped thermal model of a cylindrical cell, IEEE TCST 2013](https://doi.org/10.1109/TCST.2012.2217143)
- [Chen et al., Bernardi-based thermal runaway warning, Sensors 2024](https://doi.org/10.3390/s24154964)
- [Ojo et al., neural-network thermal fault detection, IEEE TIE 2021 (base paper)](https://doi.org/10.1109/TIE.2020.2984980)
- [Espressif ESP32 ADC documentation](https://docs.espressif.com/projects/esp-idf/en/v4.4/esp32/api-reference/peripherals/adc.html)
- [Panasonic NCR18650GA product specification](https://industrial.panasonic.com/ww/products/pt/lithium-ion/models/NCR18650GA)
- [NCR18650GA replacement listing used for project costing](https://batteryworks.in/products/panasonic-ncr18650ga-3-6v-3300mah-li-ion-battery)
- [SmartElex 5V 10A dual-relay manual](https://robu.in/wp-content/uploads/2025/01/USER-MANUAL-2.pdf)
- [16.8V/1.5A 4S NMC CC/CV charger listing](https://lionbattery.in/shop/shop/power-supply/ac-to-dc-power-supply/16-8v-1-5a-nmc-battery-charger-for-4s-li-ion-pack-cc-cv-charger/)
