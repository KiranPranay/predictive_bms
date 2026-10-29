# Gate records

One sheet per gate. Fill it in at the bench, sign it, and keep a scan or photo with the project.
The release rule (Gate 12) needs a signed record for every gate. Pass and stop rules are in
[architecture/safe-build-sequence.md](architecture/safe-build-sequence.md).

Every sheet starts with:

| Date | Firmware version (boot log) | Build (normal / bench) | Done by | Witness (needed at Gates 8 and 10) |
| --- | --- | --- | --- | --- |
| | | | | |

## Gate 0: design frozen

| Check | Result |
| --- | --- |
| Cart matches `bom.csv` (items added and removed) | |
| 7.5 A fuse fits its holder | |
| Charger: isolated, 16.8 V CC/CV, at most 1.5 A; plug size; polarity | |
| Net labels printed (B-, B1, B2, B3, B+, P-, P+, LOAD-, CHARGE-) | |

Pass / stop: ______  Signed: ______

## Gate 1: sensing, no cells

| Channel | 0 V | 4.2 V | 8.4 V | 12.6 V | 16.8 V | Gain | Offset | Worst error (≤ 20 mV) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Tap 1 | | | | | | | | |
| Tap 2 | | | | | | | | |
| Tap 3 | | | | | | | | |
| Tap 4 | | | | | | | | |

| Current | −1 A | −0.5 A | −0.25 A | +0.25 A | +0.5 A | +1 A | Worst error (≤ 2 % or 20 mA) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Meter | | | | | | | |
| INA226 | | | | | | | |

| NTC | Ambient ref / read | Warm ref / read | Offset | Open detected | Short detected |
| --- | --- | --- | --- | --- | --- |
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |
| 4 | | | | | |
| 5 (air) | | | | | |

3.3 V rail (`cal vref`): ______ mV.  I2C addresses: ADS1115 ______ INA226 ______.
No flat-line fault in 10 minutes: ______.  Clamp part chosen and its leakage: ______.

Pass / stop: ______  Signed: ______

## Gate 2: relays and fail-safe

| Check | Load relay | Charge relay |
| --- | --- | --- |
| LM2596 output, then after 15 min at 500 mA | | |
| Open with inputs unconnected | | |
| Input voltage at rest with pull-up | | |
| Opens and stays open: power-off | | |
| … EN reset | | |
| … `test hang` (watchdog), `controller_reset` latched | | |
| … `test crash`, `controller_reset` latched | | |
| … SDA pulled (I2C loss), sensor fault latched | | |
| Independent trip: `sim charge 1.8` opens charge only | | |
| Independent trip: `sim load 5.3` opens load only | | |
| Alarm: pulses at Warning, steady at Trip | | |
| Reset refused before 60 s, accepted after | | |
| A trip with Wi-Fi off | | |

Pass / stop: ______  Signed: ______

## Gate 3: BMS harness

| Check | Result |
| --- | --- |
| Tap voltages at the connector (3.6 / 7.2 / 10.8 / 14.4 V) | |
| Adjacent pins: one cell each, rising in order | |
| `status` cell voltages | |
| P+/P- and BMS recovery as documented | |
| Cell 1 at 4.16 V: `cell_high`, charge only | |
| Cell 1 at 3.08 V: `cell_low`, load only | |
| Bench mode temperature and predictive cutoffs (list) | |

Pass / stop: ______  Signed: ______

## Gate 4: cell matching

| Cell | Marking / wrapper | Mass (g) | Rest voltage | Capacity (mAh) | DC resistance (mΩ) | Within 20 mV / 3 % / 10 % |
| --- | --- | --- | --- | --- | --- | --- |
| C1 | | | | | | |
| C2 | | | | | | |
| C3 | | | | | | |
| C4 | | | | | | |

`model r0` typed: ______.  Pass / stop: ______  Signed: ______

## Gates 5 to 7: assembly

| Gate | Check | Result |
| --- | --- | --- |
| 5 | dry fit closes without force; NTC positions; vents; strain relief | |
| 6 | weld settings (welder, pulse, electrode, strip batch); peel test | |
| 7 | voltage after each link; total equals the sum; no warm cell | |

Pass / stop: ______  Signed: ______

## Gate 8: first live power-up

| Check | Result |
| --- | --- |
| Tap voltages at the BMS connector before insertion | |
| Precharge and fuse inserted; inrush | |
| 5.0 V, 3.3 V, four cells, five temperatures, current near zero | |
| Quiescent current (meter in series) | |
| 30 minutes at rest: stable, nothing warm (log file name) | |

Pass / stop: ______  Signed: ______  Witness: ______

## Gate 9: controlled discharge

| Step | INA226 (A) | Load meter (A) | Hottest connection rise (°C) | Cell spread (mV) |
| --- | --- | --- | --- | --- |
| 0.25 A | | | | |
| 0.5 A | | | | |
| 1 A | | | | |
| 2 A | | | | |
| 4.8 A | | | | |

5.0 A load trip opened K_LOAD only and telemetry continued: ______.
Cell 1 under 2 A, firmware against meter: ______ (BMS switch drop).
Fit log file: ______.  `model thermal` values: ______________________________.

| After the fit, 1 A and 2 A | Cell 1 | Cell 2 | Cell 3 | Cell 4 |
| --- | --- | --- | --- | --- |
| Largest abnormal heat (< 0.25 °C/min) | | | | |
| 5-minute error, °C RMS (≤ 0.5) | | | | |
| Online resistance against Gate 4 (within 15 %) | | | | |

NTC lifted under load: `ntc_contact` latched: ______.

Pass / stop: ______  Signed: ______

## Gate 10: controlled charge

| Pause | Rested voltage (mean) | Charge put in (mAh) |
| --- | --- | --- |
| about 3.6 V | | |
| about 3.8 V | | |
| about 4.0 V | | |

`model ocv` typed: ______.  Charger CC/CV behaviour: ______.  End voltage and spread: ______.
Largest abnormal heat during the charge: ______.  5-minute error, °C RMS: ______.
Step 5 covered by (bench mode record, scenario output): ______.

Pass / stop: ______  Signed: ______  Witness: ______

## Gate 11: predictive layer

| Test | Expected | Result and time |
| --- | --- | --- |
| `bms_sim run all` (and with the Gate 9 values) | all pass | |
| Dummy at about 0.4 W, no current | Warning | |
| Dummy at about 0.75 W, no current | Trip, both open | |
| NTC unplugged / shorted / lifted | sensor fault, both open | |
| Soft short, 47 Ω on cell __ : leak estimate | about 80 mA, that cell only | |
| … abnormal heat and 5-minute confirmation | rise on that cell | |
| … energy cross-check | agree | |
| … level | Warning, no trip | |
| … cell temperature (below 40 °C) | | |

Event record and log files: ______.  Pass / stop: ______  Signed: ______

## Gate 12: release

| Check | Result |
| --- | --- |
| Enclosure: standoffs, barriers, vents, strain relief, fuse access, labels | |
| Lid removable without touching a cell terminal | |
| Rest, 1 A discharge and low-current charge inside the enclosure | |
| Firmware version; `cal show` and `model show` attached | |
| Fuse, cell serials, calibration date, charger identity | |
| No temporary jumper; every fault latches | |
| Storage at 30–50 % charge, connectors off | |

Accepted by the guide / lab supervisor: ______  Date: ______
