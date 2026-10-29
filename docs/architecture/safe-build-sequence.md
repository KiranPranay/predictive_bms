# Safe Build and Validation Sequence

This sequence is a gate checklist. Do not skip forward because a later step appears easier. Stop whenever an acceptance criterion is not met.

## Ground rules

- Work on a non-conductive, uncluttered bench with eye protection.
- Keep a Class D or lithium-battery-appropriate response plan, sand bucket, and a clear route to a safe outdoor isolation area. Water guidance varies by cell and incident; follow the cell supplier and local lab policy.
- Never work alone when first energising or charging the assembled pack.
- Remove rings, watches, loose metal, and conductive tools.
- Cover every exposed cell terminal except the one actively being worked on.
- Never solder directly to an 18650 terminal and never deliberately drive a live cell into thermal runaway.
- A swollen, dented, rusty, leaking, unusually warm, or odorous cell is rejected and quarantined.

## Gate 0 — freeze the design

1. Read `current-architecture.md` and mark the first-review diagrams as historical.
2. Reconcile the physical cart to `bom.csv`: add current-design items and remove excluded items.
3. Confirm the 7.5A fuse physically fits its holder.
4. Confirm the charger is isolated 16.8V CC/CV, 1.5A maximum, and centre-positive only if the chosen connector is centre-positive.
5. Print the net names `B-`, `B1`, `B2`, `B3`, `B+`, `P-`, `P+`, `LOAD-`, and `CHARGE-` as bench labels.

**Pass:** every part has an exact purpose, compatible rating, and connector.
**Stop:** any protection board is for LiFePO4 instead of 4S NMC/Li-ion, any charger is not 16.8V CC/CV, or the fuse/holder format is uncertain.

## Gate 1 — low-voltage electronics only

Do not use lithium cells yet.

1. Power the ESP32 from USB.
2. Power the ADS1115 and INA226 logic at 3.3V; scan the I2C bus and verify stable addresses.
3. Build one 330kΩ/56kΩ divider, RC filter, and clamp channel.
4. Sweep its input from 0 to 16.8V with a current-limited bench supply. Compare ADC-derived voltage to a calibrated multimeter at 0V, 4.2V, 8.4V, 12.6V, and 16.8V.
5. Repeat for all four channels and store coefficients.
6. Build the five 10k/NTC dividers on GPIO32–36 (four cells and one ambient). Verify open and short detection on every channel.
7. Modify/bypass the INA226 module's stock shunt and connect the 5mΩ external shunt with Kelvin leads. Calibrate at ±0.25A, ±0.5A, and ±1A using a protected supply/load.

**Pass:** cell-tap error is no more than ±20mV after calibration; current error is no more than ±2% or ±20mA, whichever is larger; every sensor fault is detected.
**Stop:** any ADC input exceeds 3.0V, tap order can become non-monotonic without a latched fault, or current polarity is ambiguous.

## Gate 2 — relay and fail-safe validation

Still do not use lithium cells.

1. Set the LM2596 to 5.00V with no ESP32 connected; then load-test it at 500mA for 15 minutes.
2. Power the relay board from 5V and confirm each contact is open with its input unconnected.
3. Add 10kΩ input pull-ups and connect GPIO25/26.
4. Reboot, reset, disconnect USB, crash the test firmware, and interrupt I2C. Both relays must return to open.
5. Switch only a benign 12V lamp or resistor load. Confirm charge and load outputs are independent.
6. Verify the alarm LED/buzzer and latched manual-reset logic.

**Pass:** both contacts are open for power-off, boot, reset, watchdog, and sensor-bus failure.
**Stop:** either relay briefly energises on boot or a fault automatically clears without the reset conditions.

## Gate 3 — BMS harness validation with a simulator

Use four isolated cell simulators or four current-limited bench channels if available. If the lab cannot provide an isolated multi-cell simulation, perform this gate with the guide/lab supervisor and follow the BMS manufacturer's staged harness procedure.

1. Connect BMS `B-` first.
2. Present sequential taps so the meter reads approximately 3.6V, 7.2V, 10.8V, and 14.4V from `B-`.
3. Before inserting the balance connector, measure every adjacent pin: each must be one-cell voltage and polarity must rise monotonically.
4. Verify `P+/P-` and the documented recovery behaviour.
5. Test supervisory cutoffs using simulated voltage and temperature signals; do not overcharge or over-discharge real cells to test logic.

**Pass:** tap order, software readings, relay actions, and BMS output all agree.
**Stop:** any adjacent balance lead exceeds one cell voltage, polarity reverses, or the BMS wiring does not match its datasheet.

## Gate 4 — inspect and match the cells

1. Record the visible marking, wrapper condition, prior weld/attachment evidence, mass, open-circuit voltage, capacity, and DC internal resistance for each of the four existing NCR18650GA-labelled cells.
2. Use only the four cells as one matched set; reject any cell with wrapper, insulating-ring, terminal or can damage. Replace damaged wraps/rings correctly before further work.
3. Bring all cells to the same resting state of charge, preferably near 3.6–3.7V.
4. Accept only cells within 20mV resting voltage, 3% measured capacity, and 10% DC resistance of the group mean.
5. Label cells C1–C4 and preserve the measurement sheet.

**Pass:** all four meet every matching rule after a rest period.
**Stop:** any cell warms at rest, self-discharges abnormally, or fails a matching limit.

## Gate 5 — dry mechanical assembly

1. Trial-fit the cells in top and bottom spacers with the intended series orientation.
2. Install positive terminal fish-paper rings.
3. Cut nickel links and insulating barriers before exposing more than one terminal.
4. Confirm NTC locations at each cell mid-body and route channels away from nickel edges.
5. Check the 3D enclosure provides wire strain relief, ventilation, no pinching, and no metal fastener path to a cell can.

**Pass:** the entire assembly closes without force and no conductor can rub a cell wrapper.
**Stop:** the case compresses cells, traps NTCs, or requires exposed terminals during normal service.

## Gate 6 — qualify the spot weld

1. Use spare nickel and a sacrificial steel coupon or rejected cell only; never learn settings on an accepted cell.
2. Make two weld pairs, then perform a peel test. Nickel should tear around sound weld nuggets rather than detach cleanly.
3. Check for burn-through, wrapper heat damage, or excessive electrode marking.
4. Record welder, pulse settings, electrode condition, and strip batch.

**Pass:** repeatable peel strength without burn-through.
**Stop:** sparks, perforation, hot cell can, damaged wrapper, or inconsistent nuggets.

## Gate 7 — weld the 4S1P pack

1. Recheck polarity against the printed series diagram.
2. Weld one link at a time with all other terminals covered.
3. After each link, measure total voltage and every adjacent cell voltage.
4. Attach the fused B+ lead immediately after the final positive connection; leave the fuse removed.
5. Add BMS balance leads in order and secure each lead before proceeding.
6. Install NTCs, barriers, and sleeve. Keep the BMS/electronics electrically insulated from nickel.

**Pass:** adjacent voltages are plausible and monotonic; pack total equals their sum within meter tolerance; no cell temperature rises.
**Stop:** wrong polarity, unexpected voltage step, warm cell, damaged wrapper, loose weld, or nicked sense lead.

## Gate 8 — first live power-up

1. Keep both relay outputs disconnected and the blade fuse removed.
2. Connect BMS `B-`, then balance taps from lowest to highest exactly as its guide specifies, then `B+`/power conductors.
3. Confirm pack tap voltages at the BMS connector before insertion.
4. Insert the 7.5A fuse through a current-limited precharge path appropriate to the controller input capacitance; investigate unexpected inrush.
5. Verify 5.0V, 3.3V, four cell voltages, four cell temperatures, the ambient temperature, and near-zero current. Online resistance tracking (architecture section 9.4) runs from here.
6. Let the system log at rest for 30 minutes with relays open.

**Pass:** no component heats, readings remain stable, and quiescent current is documented.
**Stop:** smoke, odour, noise, warming, unstable rail, wrong cell voltage, or unexplained current.

## Gate 9 — controlled discharge

1. Connect an electronic load through the load connector with the charge connector empty.
2. Test at 0.25A, 0.5A, 1A, 2A, then 5A maximum. Hold each step only long enough to inspect voltage drop and heating.
3. Compare INA226 current to the reference load meter.
4. Use simulated sensor inputs to verify warning and trip thresholds; do not discharge a cell to 2.7V to prove hardware protection.
5. Confirm a software load trip opens only `K_LOAD`, latches the cause, and keeps telemetry alive.
6. Fit the thermal model (architecture section 9.1): log a normal 1A and 2A discharge and the cooling curve after each, fit `C_c`, `C_s`, `R_c` and each cell's `R_u`, and store them with the calibration record.
7. With the fitted model running, repeat the 1A and 2A steps and record the abnormal heat (9.2), the 1- and 5-minute prediction errors (9.3), and the online resistance of each cell (9.4).

**Pass:** wiring, fuse holder, shunt, relays, nickel, and cells remain within the validated temperature limits; 5A operation is stable; with the fitted model, abnormal heat stays below the equivalent of 0.25°C/min at every test current, the 5-minute prediction error is no more than 0.5°C RMS, and each cell's online resistance agrees with its Gate 4 value within 15%.
**Stop:** any connection rises more than 10°C above ambient, cell spread exceeds 50mV under a modest load, or relay voltage drop is abnormal.

## Gate 10 — controlled charge

1. Disconnect the load completely.
2. Measure charger polarity and output voltage before mating connectors.
3. Begin through the charge branch while supervising all four cell voltages and temperatures continuously.
4. First test at a lower current if the charger allows; never exceed 1.5A.
5. Confirm a simulated high-cell or high-temperature condition opens only `K_CHARGE` and latches.
6. End the first charge early, around 4.10V/cell, then inspect balance and temperature behaviour before any later full charge.
7. Log abnormal heat and prediction errors (architecture sections 9.2 and 9.3) for every cell throughout the charge.
8. Pause the charge for 30 minutes at about 3.6V, 3.8V and 4.0V per cell and record the rested voltage and the charge put in, to build the open-circuit-voltage slope table for the leak estimate (9.5).

**Pass:** no cell approaches the 4.15V software limit unexpectedly; cell spread remains controlled; charger terminates correctly; abnormal heat stays below the equivalent of 0.25°C/min and the 5-minute prediction error is no more than 0.5°C RMS.
**Stop:** one cell rises faster, any cell exceeds 4.15V, temperature exceeds 40°C, or the charger does not enter CV/taper behaviour.

## Gate 11 — predictive thermal algorithm validation

Do **not** create an internal fault or thermal runaway in a live lithium cell.

1. Validate software first with recorded traces and synthetic ramps.
2. For a physical test, use a power resistor bonded to an aluminium dummy cylinder or a completely separate instrumented thermal mass.
3. Replay its temperature signal or thermally couple a spare NTC to prove the abnormal-heat warning (0.5°C/min, about 0.4W) and trip (1.0°C/min, about 0.75W), the cell-to-cell comparison (0.3 and 0.6°C/min), the 5-minute confirmation (+1.0°C), the time-to-limit and safe-current forecasts, the self-acceleration trip, and the raw 2.0°C/min backstop.
4. Heat the dummy with zero simulated pack current and confirm the heating is flagged as unexplained. Repeat with a simulated 5A current and the heating the model expects at 5A, and confirm it is not flagged.
5. Verify noisy data, step changes, disconnected sensors, and flat-line sensors cannot bypass the trip. Lift the NTC off the dummy under simulated load and confirm a sensor-contact fault.
6. **Emulated soft short on the live pack (supervised, normal operating range only).** With the pack at rest near 3.7V per cell and every cell below 30°C, bond a 47Ω 1W resistor to the middle of one cell and connect it across that cell's balance taps through a fused lead (about 80mA and 0.3W). This copies both signs of a soft internal short, a self-discharge and a heat source on one cell, without creating any fault inside the cell. Confirm that the leak estimate rises in that cell only, that its abnormal heat and 5-minute confirmation error rise, that the energy cross-check agrees, and that the risk level reaches Warning. Remove the resistor at Warning or at once if the cell reaches 40°C, then recharge to rebalance the pack.
7. Save the complete event record, including the prediction-accuracy record, for the report.

**Pass:** warning/trip timing matches the architecture and both branches fail open on an ambiguous thermal fault.
**Stop:** testing requires heating an energised cell outside its normal operating range.

## Gate 12 — enclosure and release

1. Print the enclosure in PETG and install standoffs, barriers, vents, strain relief, fuse access, and labels.
2. Ensure the electronics lid can be removed without touching cell terminals.
3. Repeat the rest, 1A discharge, and supervised low-current charge tests inside the enclosure while logging temperatures.
4. Photograph final routing and record fuse, firmware revision, cell serials, calibration date, and charger identity.
5. Define storage at roughly 30–50% state of charge with both external connectors disconnected.

**Release only if:** every gate has a signed measurement record, no temporary jumper remains, all faults latch correctly, and the guide/lab supervisor accepts the assembly.
