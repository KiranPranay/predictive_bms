# Wiring the prototype (modules and perfboard, no PCB)

The prototype is built from the modules in the bill of materials, wired on two 7 × 9 cm
perfboards. Every value here comes from the architecture document (revision 2.2, sections 3
to 7 and 11). Where a part is still open in the bill of materials, it is marked **TBD** with the
gate that settles it.

Work through the build gates in order ([bring-up.md](bring-up.md)). No lithium cell is
connected before Gate 3, and the pack is not welded before Gate 7.

## 1. What goes where

| Unit | Contents | Where |
| --- | --- | --- |
| Pack | 4 × NCR18650GA in a 4S1P row, spot-welded nickel, spacers, fish paper, sleeve, 4 cell NTCs bonded mid-body | lower part of the enclosure |
| Power side | hardware BMS, 7.5 A blade fuse in its inline holder, 5 mΩ shunt, relay module, LM2596, XT60 load and charge connectors | one side of the enclosure |
| Board A, sense | 4 tap dividers with filters and clamps, 5 NTC dividers, ADS1115, INA226 | the other side, away from the relay contacts |
| Board B, control | ESP32 DevKit, relay input pull-ups, alarm buzzer and LED | next to board A |
| Air sensor | NTC5 in free air in the vent path, away from the cells, the LM2596 and the relays | vent |

Section 11 rules: fuse at the B+ exit, then the shunt, then the branch wiring; BMS and boards on
insulated standoffs; relay contacts and power wiring on one side, analog sensing on the other;
the electronics lid removable without exposing a cell terminal.

## 2. Power path

```text
cells ── BMS (B-, B1, B2, B3, B+) ── P+ ── 7.5 A fuse ──┬── 5 mΩ shunt ── FUSED+ ──┬── LOAD+   (XT60 load)
                                                        │   IN+      IN-           └── CHARGE+ (charge connector)
                                                        └── LM2596 IN+
P- ──┬── relay K_LOAD   COM ─ NO ── LOAD-
     ├── relay K_CHARGE COM ─ NO ── CHARGE-
     └── LM2596 IN-  = electronics ground (GND)
LM2596 OUT 5.00 V ── ESP32 VIN, relay module VCC, buzzer module VCC
ESP32 3V3 ── ADS1115 VDD, INA226 VCC, divider and NTC pull-ups, relay input pull-ups
```

| From | To | Wire | Notes |
| --- | --- | --- | --- |
| Pack + (B+) | fuse holder | 16 AWG red, short | fuse mounted at the pack's positive exit; fuse removed until Gate 8 |
| fuse holder | shunt IN+ side | 16 AWG red | |
| shunt IN- side (FUSED+) | XT60 load +, charge connector + | 16 AWG red | positive current = discharge flows IN+ to IN- |
| BMS P- | relay K_LOAD COM and K_CHARGE COM | 16 AWG black | |
| K_LOAD NO | XT60 load - (LOAD-) | 16 AWG black | normally-open contact only |
| K_CHARGE NO | charge connector - (CHARGE-) | 16 AWG black | normally-open contact only |
| fuse/shunt junction | LM2596 IN+ | 22 AWG red | see the note below |
| BMS P- | LM2596 IN- | 22 AWG black | |

**Take the LM2596 supply between the fuse and the shunt.** The architecture puts the LM2596 on
protected P+/P- before the branch relays (section 4). Taking it after the fuse keeps that wire
fused. Taking it before the shunt matters for the leak estimate: the controller draws tens of
milliamps, and if that current passed the shunt the pack would never read as at rest (|I| below
20 mA, section 9.5), so the self-discharge estimate would never run. Because the LM2596 takes
P-, a hardware BMS cut-off still removes controller power (section 4).

Charge connector: a barrel adapter matched to the measured charger plug (BOM item 22, **TBD**
until the charger's plug and polarity are measured at Gate 0).

## 3. Board A: sense

### 3.1 Cell taps (section 5)

Run a separate low-current sense harness from the pack taps to board A, restrained, with a 1–10 kΩ
series resistor at the tap end of each wire (section 11). The BMS keeps its own 5-pin JST-XH
balance lead.

Each of the four channels, built the same way:

```text
tap (B1, B2, B3 or B+) ── R_entry 1-10 kΩ (at the pack) ── 330 kΩ ──┬── 10 kΩ ──┬── ADS1115 An
                                                                     │           ├── 100 nF ── GND
                                                                    56 kΩ        └── clamp to 3V3 (TBD)
                                                                     │
                                                                    GND
```

| Channel | Tap | ADS1115 input | Nominal maximum | At the ADC |
| --- | --- | --- | ---: | ---: |
| 1 | B1 | A0 | 4.2 V | 0.61 V |
| 2 | B2 | A1 | 8.4 V | 1.22 V |
| 3 | B3 | A2 | 12.6 V | 1.83 V |
| 4 | B+ | A3 | 16.8 V | 2.44 V |

- Resistors: 1 % metal film (BOM item 10). Measure each 330 kΩ and 56 kΩ before fitting; Gate 1
  calibrates every channel anyway.
- Clamp: low-leakage, from the ADC input to 3V3. The part is **TBD**: choose it at Gate 1 after a
  breadboard leakage test, because leakage directly upsets a 330 kΩ divider (BOM item 11).
- Clean all flux from this area. Contamination leaks current across high-value resistors.
- The ADS1115 runs at 3.3 V and reads ±4.096 V full scale; no input may exceed 3.0 V
  (Gate 1 stop rule).

**Ground reference.** The divider low sides and the ADS1115 ground are the electronics ground,
P-. The hardware BMS switches the negative side, so P- sits above B- by the BMS MOSFET drop while
current flows. That drop adds to the reading of cell 1 only (cells 2 to 4 are differences of
taps), and the online resistance of cell 1 includes it. Check it at Gate 9: under a 2 A load,
compare the firmware's cell 1 voltage with a meter across cell 1.

### 3.2 NTCs (section 6)

Five identical dividers. Bond NTC1–4 at the middle of each cell can with electrically insulating,
thermally conductive tape, never on bare nickel. NTC5 hangs in free air in the vent path.

```text
3V3 ── 10 kΩ 1 % ──┬── ESP32 GPIO (ADC1)
                   ├── 100 nF ── GND
                   └── NTC 10k B3950 ── GND
```

| Sensor | ESP32 pin | ADC channel |
| --- | --- | --- |
| NTC1, cell 1 | GPIO32 | ADC1_CH4 |
| NTC2, cell 2 | GPIO33 | ADC1_CH5 |
| NTC3, cell 3 | GPIO34 | ADC1_CH6 |
| NTC4, cell 4 | GPIO35 | ADC1_CH7 |
| NTC5, air | GPIO36 (VP) | ADC1_CH0 |

Only ADC1 pins: ADC2 does not work while Wi-Fi is on. GPIO34–36 are input-only, which is all an
NTC needs. Use a two-pin connector per NTC so a sensor can be replaced without soldering at the
pack.

### 3.3 Current (section 4)

| INA226 module pin | Connect to |
| --- | --- |
| VCC | 3V3 |
| GND | GND |
| SCL / SDA | GPIO22 / GPIO21 (shared I2C bus) |
| IN+ | shunt, fuse side (Kelvin sense lead) |
| IN- | shunt, FUSED+ side (Kelvin sense lead) |
| VBUS | FUSED+ (if the module brings it out separately) |

- Remove or bypass the module's own R100 shunt (BOM item 12); the 5 mΩ external shunt (item 13)
  replaces it. At 5 A it drops 25 mV and dissipates 0.125 W.
- Kelvin wiring: the two sense leads leave the shunt's own pads, twisted together, kept away from
  the relay contacts and the power current loop (section 11).
- Address: A0 and A1 to GND gives 0x40, the firmware default.

### 3.4 I2C bus

| ADS1115 pin | Connect to |
| --- | --- |
| VDD / GND | 3V3 / GND |
| SCL / SDA | GPIO22 / GPIO21 |
| ADDR | GND (address 0x48, the firmware default) |
| ALRT | not connected |

Add 4.7 kΩ pull-ups from SDA and SCL to 3V3 only if neither module has them fitted (section 7).
Check with `raw` on the console at Gate 1. If the addresses differ, change them in
`idf.py menuconfig` → Predictive BMS.

## 4. Board B: control

| Function | ESP32 pin | Wiring |
| --- | --- | --- |
| Load relay K_LOAD | GPIO25 | relay module IN1; 10 kΩ pull-up from IN1 to 3V3 |
| Charge relay K_CHARGE | GPIO26 | relay module IN2; 10 kΩ pull-up from IN2 to 3V3 |
| Alarm | GPIO27 | buzzer module input, and the red LED through its resistor to GND |
| Manual reset | GPIO0 (BOOT button) | the DevKit's own button: hold 3 s |
| Power | VIN | LM2596 5.00 V output; set and load-test it before connecting (Gate 2) |

- Relays are **active LOW**: the firmware drives a pin LOW to close a contact. A floating or HIGH
  input leaves the contact open, so reset, a crash, or an unpowered ESP32 all leave both branches
  open (section 3).
- The relay module runs at 5 V while the ESP32 drives 3.3 V logic. With a 3.3 V pull-up, check at
  Gate 2 that the module's input really releases at 3.3 V. If a relay energises during reset or
  stays partly on, add a transistor stage that guarantees a de-energised start (section 7).
- Never switch the relays with PWM. They are disconnects.
- Red LED resistor: (3.3 V - LED forward voltage) / the LED current you want; from stock (BOM
  item 25). Set `CONFIG_BMS_ALARM_ACTIVE_LOW` in menuconfig if the buzzer module sounds on LOW.

## 5. Hardware BMS (layer A)

Connect exactly as its guide specifies, at Gate 3 with simulated cells first and at Gate 8 on the
pack: B- first, then the balance taps from the lowest to the highest, then B+. Measure every
adjacent pair at the connector before inserting it; each must be one cell voltage, rising in
order. Never hot-plug an unverified harness (section 10).

## 6. Perfboard layout

```text
Board A (sense)                                   Board B (control)
+--------------------------------------------+    +------------------------------------+
| tap harness in   [R 330k/56k/10k x4]        |    | [ESP32 DevKit on female headers]   |
| (JST, restrained) [100nF + clamp x4]        |    |  USB to the edge for the console   |
|                   [ADS1115 module]  I2C ----+----+--> GPIO21/22                       |
| NTC1-5 in        [10k + 100nF x5] ADC lines-+----+--> GPIO32-36                       |
| shunt Kelvin pair [INA226 module]            |    | [10k pull-ups] IN1/IN2 to relays  |
| 3V3 / GND from board B                       |    | [alarm LED + buzzer]  5 V in      |
+--------------------------------------------+    +------------------------------------+
   analog side of the enclosure                      next to the analog side; relay
                                                     module and power wiring opposite
```

- Keep the tap traces (up to 16.8 V) apart from the 3.3 V logic and from each other; leave a gap
  of a few holes and cut unused strips.
- Strain-relieve every wire that leaves a board.
- Keep the NTC and tap lines away from the relay contacts and the LM2596.
- The prototype has no PCB: the permanent board of Gate 12 is a carefully soldered perfboard
  with this layout.
