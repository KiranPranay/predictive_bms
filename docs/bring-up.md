# Bring-up, gate by gate

This follows [architecture/safe-build-sequence.md](architecture/safe-build-sequence.md). The gates
and their pass and stop rules are there; this page says what to do with the firmware and the
tools at each gate. Record every result in [gate-records.md](gate-records.md).

Commands in `code` are typed on the serial console (see [firmware.md](firmware.md), section 5).
Tools run from the repository root with the project's Python: `.venv/bin/python tools/...`.

## Before Gate 0: on the PC

1. Build and run every test: see the README. All tests must pass.
2. Watch the simulated pack: `python3 tools/sim_server.py`, open http://127.0.0.1:8080/, and try
   each fault button. This is what the real dashboard will show.

## Gate 0: freeze the design

No firmware step. Build the firmware once (`idf.py build`) to confirm the toolchain. Measure
the charger's plug and polarity: the charge connector (BOM item 22) depends on it.

## Gate 1: low-voltage electronics, no cells

Flash the normal build. The model stays `off`.

1. **Bus check.** `raw` must show `ADS1115 ok` and `INA226 ok` every time. A FAIL means wiring,
   address or pull-ups.
2. **3.3 V rail.** Measure the ESP32's 3V3 pin with the meter: `cal vref 3297` (your value, mV).
3. **Taps.** For each channel, apply 0, 4.2, 8.4, 12.6 and 16.8 V from a current-limited bench
   supply to the divider input. At each point write down the meter voltage and the ADS1115 volts
   from `raw`. Put them in a CSV (format at the top of `tools/calibrate.py`), run
   `tools/calibrate.py readings.csv`, and type the `cal tap` lines it prints. Pass: within ±20 mV.
   Stop if any ADC input goes above 3.0 V.
4. **NTCs.** Read each NTC at ambient and at one warm reference point against a reference
   thermometer; add them to the CSV; type the `cal ntc` lines. Unplug each NTC, then short it: the
   sensor fault must latch within about 2 s (`events`). `reset` after each test, once 60 s have
   passed. Leave the bench for 10 minutes and check that no NTC reports a flat line.
5. **NTC noise.** Repeat `raw` a few times and note how much each temperature moves. If it is
   clearly more or less than 0.05 °C after the median, set the first value of `model kalman`
   to match (Gate 9 checks the result).
6. **Current.** Fit the 5 mΩ shunt with Kelvin leads (remove the module's R100). Pass ±0.25, ±0.5
   and ±1 A from a protected supply or load; note the shunt microvolts from `raw` and the meter
   current; run `tools/calibrate.py`; type the `cal shunt` line. Pass: ±2 % or ±20 mA. A negative
   gain means the sense leads are reversed: swap them rather than keep the negative gain.

## Gate 2: relays and fail-safe, no cells

1. Set the LM2596 to 5.00 V with nothing connected, then load-test it at 500 mA for 15 minutes.
2. Power the relay module from 5 V with its inputs unconnected: both contacts open.
3. Fit the 10 kΩ pull-ups to 3V3 and connect GPIO25 and GPIO26. Measure the input voltage of each
   relay channel at rest; the relay must be fully off. If it chatters or holds on, add the
   transistor stage of architecture section 7.
4. Flash the **bench build** ([firmware.md](firmware.md), section 6). `sim on`: after 2 s both
   relays close (the simulated pack is healthy). Connect a benign 12 V lamp or resistor through the
   contacts.
5. **Independence.** `sim charge 1.8` trips only the charge relay (charge current above 1.6 A).
   `reset` after 60 s. `sim load 5.3` trips only the load relay.
6. **Fail-safe.** With both relays closed, check each of these opens both and keeps them open:
   - press EN (reset), and unplug USB: open during the restart and the boot;
   - `test hang`: the watchdog restarts the ESP32 within about 2 s, and `controller_reset` latches;
   - `test crash`: the same;
   - pull the SDA wire: `tap_sensor` and `current_sensor` latch after 2 s.
   Stop if a relay closes even briefly during boot, or if a fault clears without `reset`.
7. **Alarm.** `sim heat 2 0.41`: the alarm pulses (Warning). `sim heat 2 1.0`: it stays on
   (Trip). Set `CONFIG_BMS_ALARM_ACTIVE_LOW` if the buzzer works the wrong way round.
8. **Reset rules.** `reset` straight after a trip is refused ("not clear for 60 s"); after 60 s
   it is accepted. Holding BOOT for 3 s does the same.
9. **Wi-Fi.** Open the dashboard (see the console log for the address). `wifi off`, repeat one
   trip from step 5, then `wifi on`: the trip happened, and the event is in the log.
10. `sim off`.

## Gate 3: BMS harness with simulated cells

1. Do the harness checks of the build sequence with the bench channels (3.6, 7.2, 10.8,
   14.4 V). With the normal build flashed, `status` must show four cells near 3.6 V, in order.
2. **Voltage cutoffs with real signals.** Slowly raise cell 1's simulated voltage to 4.16 V
   (with four isolated channels in series, raise only the first channel; with taps referenced to
   B-, raise every tap by the same amount, or cell 2 drops). After 1 s `cell_high` latches and
   opens only the charge relay. Bring it back, `reset` after 60 s, then lower cell 1 to 3.08 V:
   `cell_low` opens only the load relay. Both values stay inside the hardware BMS limits.
3. **Temperature and predictive cutoffs.** With the tap harness unplugged, flash the bench build
   and use `sim` commands (for example `sim ambient 50` while `sim charge 1.5`, or
   `sim ntc 3 open`). `sim on` refuses while the taps carry voltage.
4. Flash the normal build again before Gate 4. From here on bench mode is not used.

## Gate 4: match the cells

Measure each cell's DC resistance with the same method the firmware uses online: a current step
of at least 0.5 A, R = ΔV / ΔI, voltage taken just before and just after the step. Store the
four values: `model r0 35.1 34.8 35.4 35.0` (mΩ). From then on a drift of more than 30 % raises
Watch.

## Gates 5 to 7: mechanics, weld, pack

No firmware step. Keep each NTC on its own cell: NTC1 on cell 1 (the B- end), up to NTC4 on
cell 4.

## Gate 8: first live power-up

Model `off`. Online resistance tracking starts here.

1. After the precharge and the fuse, `status`: four plausible cells, five plausible
   temperatures, near-zero current, state `run`.
2. Start a log for 30 minutes at rest: `tools/serial_log.py /dev/ttyUSB0 gate8.csv`.
3. The INA226 does not see the controller's own current (the LM2596 is fed before the shunt).
   Measure the quiescent current with a meter in series for the record.

## Gate 9: controlled discharge

1. Steps 0.25, 0.5, 1 and 2 A, then the 5 A step held at **4.8 A** (the software trip is at
   5.0 A). Compare the INA226 current (`status`) with the load's meter.
2. **Load trip (step 5).** Set the load to 5.0 A: after 1 s `discharge_current` latches, only
   K_LOAD opens, and the dashboard keeps updating. `reset` after 60 s.
3. **Check cell 1.** Under 2 A, compare cell 1's voltage with a meter across cell 1; the
   difference is the hardware BMS's switch drop ([wiring.md](wiring.md), section 3.1). Write it
   down.
4. **Fit (step 6).** After 30 minutes at rest, log a 1 A discharge for 20 minutes, 40 minutes of
   cooling, a 2 A discharge for 20 minutes and 40 minutes of cooling:
   `tools/serial_log.py /dev/ttyUSB0 gate9.csv`. Then `tools/fit_thermal.py gate9.csv`. Type the
   `model thermal` line it prints, then `model mode fitted`. Read the fit notes in
   [simulator.md](simulator.md), section 3: a good fit can have heat capacities far from 45 J/°C.
5. **Check (step 7).** Repeat the 1 A and 2 A steps. Pass: abnormal heat below 0.25 °C/min on
   every cell (dashboard), the 5-minute prediction error ("all") at most 0.5 °C RMS, and each
   cell's online resistance within 15 % of its Gate 4 value (`status`).
6. **NTC lift-off.** Under a 2–3 A load, lift one NTC off its cell: `ntc_contact` must latch and
   open both relays. This is safe for the cell, and it is the live form of Gate 11 step 5.

## Gate 10: controlled charge

1. Charge through the charge branch at no more than 1.5 A, watching all cells on the dashboard.
   End the first charge near 4.10 V per cell.
2. **OCV table (step 8).** Pause for 30 minutes at about 3.6, 3.8 and 4.0 V per cell. At each
   pause note the rested cell voltage (the mean of the four, from `status`) and the charge put in
   (from the charger or by integrating the logged current). Run `tools/ocv_table.py pauses.csv`
   and type the `model ocv` line. The rest leak estimate starts working with it.
3. Pass: abnormal heat below 0.25 °C/min and the 5-minute error at most 0.5 °C RMS during the
   charge.
4. **Step 5 (a simulated high-cell or high-temperature condition opens only K_CHARGE).** By
   design, the firmware cannot fake a reading while a pack is connected. This step is therefore
   shown in bench mode at Gate 3 and by the simulator scenarios `cell_high_charge` and
   `charge_overtemp`; attach both records to the Gate 10 sheet.

## Gate 11: predictive layer

1. **Software first (step 1).** `build/host/bms_sim run all` passes; keep the output with the
   record. Run it again with the Gate 9 values: `build/host/bms_sim run all --thermal ...`.
2. **Dummy heater (steps 2–4).** Plug the spare NTC on the heated aluminium dummy into a cell's
   NTC connector instead of that cell's own NTC, with the pack at rest. Heat the dummy at about
   0.4 W, then about 0.75 W: the dashboard must show abnormal heat on that "cell", Warning, then
   Trip; time each. The "heating expected at 5 A is not flagged" half was shown live at Gate 9 and
   by the `discharge_5a` scenario.
3. **Faulty sensors (step 5).** Unplug, short and lift an NTC: each latches a sensor fault. The
   flat-line case is the `ntc_stuck` scenario.
4. **Soft short (step 6).** Plan two hours. Pack at rest near 3.7 V per cell, every cell below
   30 °C, at least 30 minutes after the last load or charge. Bond the 47 Ω 1 W resistor to the
   middle of the chosen cell, **on the side away from its NTC**, and connect it across that cell's
   taps through a fused lead. Watch the dashboard: the confirmation error and the cell-to-cell
   heat difference raise Watch within about 10 minutes; the leak estimate appears after its
   60-minute window and should read about 80 mA on that cell only; the cross-check should read
   "agree"; the level reaches Warning. Remove the resistor at Warning, or at once if the cell
   reaches 40 °C. Then recharge to rebalance.
5. **Record (step 7).** Save `events`, the CSV log, and dashboard screenshots.

## Gate 12: enclosure and release

1. The release build is the normal build: bench mode off, model `fitted`, Wi-Fi as wanted.
2. Repeat the rest, 1 A discharge and low-current charge tests inside the enclosure.
3. Record the firmware version printed at boot (it comes from the git commit), and the output of
   `cal show` and `model show`.
