# Circuit simulation in KiCad

The prototype's analog circuits, drawn in KiCad 10 and simulated with ngspice, the simulator
built into KiCad. These are schematics for simulation only: the prototype has no PCB. The part
values come from the architecture (revision 2.2) and `docs/wiring.md`; each sheet names its
sections in the title block.

| Project | Circuit | Analysis | What it shows |
| --- | --- | --- | --- |
| `sim/cell-taps/` | Board A: the four tap dividers (tap resistor, 330 kΩ, 56 kΩ) and the 10 kΩ / 100 nF filters into the ADS1115 | `.op`, plus a leakage sweep and a frequency response | the ADC voltages at full charge, the error that leakage at an ADC input causes, how fast the filter settles |
| `sim/ntc-divider/` | Board B: one of the five NTC dividers (10 kΩ pull-up, 10k B3950 NTC, 100 nF) | `.dc TEMP -20 100 1` | the ESP32 ADC voltage against temperature |
| `sim/current-sense/` | The 5 mΩ shunt and the INA226 inputs | `.dc I1 -5 5 0.1` | the shunt voltage from 5 A charge to 5 A discharge, and the error if the module's own R100 shunt is left in place |
| `sim/thermal-model/` | The two-node thermal model of one cell (section 9.1), as an electrical circuit | `.tran 1 3610` | the core and surface temperatures after 1 W of heat starts in the core |

The thermal model uses the electrical analogue of heat flow: 1 V stands for 1 °C, 1 A for 1 W,
1 F for 1 J/°C and 1 Ω for 1 °C/W. The values are the firmware's development values (core
40 J/°C, surface 5 J/°C, core to surface 2 °C/W, surface to air 30 °C/W); Gate 9 replaces them
with values fitted on the real cells.

## Simulate in KiCad

1. Install KiCad 10 from <https://www.kicad.org/download/>. On Linux without administrator
   rights: `flatpak install --user flathub org.kicad.KiCad`.
2. Open a project, for example `sim/thermal-model/thermal-model.kicad_pro`, and open its
   schematic.
3. Open the simulator: **Inspect → Simulator**. The analysis is the command written on the
   sheet (for example `.tran 1 3610`). Run it.
4. Add the signals to plot, for example `V(/T_CORE)` and `V(/T_SURF)`, or click a wire with the
   probe tool.

The cell-tap sheet has a current source, I1, at channel 4 with a value of 0. Change it (for
example to 50n) to see what leakage at that ADC input does.

## Run every simulation from the command line

```bash
python3 kicad/run_sims.py
```

It exports each schematic to a SPICE netlist with `kicad-cli`, runs ngspice in batch mode,
checks the results, and writes:

- `docs/build-guide/kicad-sim/results.json`: every number and every check;
- `docs/build-guide/figures/sim-*.svg`: the charts;
- `docs/build-guide/figures/kicad-*.svg`: the schematics as KiCad draws them, for the build guide;
- `build/kicad-sim/`: the netlists, the ngspice logs and the raw data.

`python3 kicad/run_sims.py --check` only simulates and checks. The exit code is 1 when a check
fails.

It needs `kicad-cli` (part of KiCad 10; the Flatpak's copy is found on its own) and ngspice. On
Linux without administrator rights, ngspice can go into the project's `.tools/` folder:

```bash
micromamba create -y -p .tools/sim -c conda-forge ngspice octave gnuplot
```

Elsewhere, set `KICAD_CLI` and `NGSPICE` to the two programs.

The sheets are written by `make_schematics.py` (with `sch.py`, a small writer for KiCad's
schematic format that copies the symbols from KiCad's own libraries). After a change to it,
run `python3 kicad/make_schematics.py`, then `run_sims.py`, and check the sheets in KiCad. KiCad's
electrical rules check (ERC) finds no violation on any of the four sheets.

## Results

These are simulation results, with the part values on the sheets. Gate 1 measures the real
channels.

**Cell taps.**
- At 4.2 V per cell the ADC inputs are 0.59, 1.19, 1.78 and 2.38 V with a 10 kΩ tap resistor,
  and 0.61, 1.22, 1.82 and 2.43 V with 1 kΩ. All are below the 3.0 V stop of Gate 1. The
  divider ratio is 7.071 with 10 kΩ and 6.911 with 1 kΩ; Gate 1 calibrates the exact value of
  each channel.
- Leakage at an ADC input causes 4.1 mV of error in the cell reading for every 10 nA. The
  Gate 1 limit, 20 mV, is reached at 49 nA. Calibration removes a steady leakage, but not one
  that changes with temperature or voltage. The clamp diode (TBD, BOM item 11) should therefore
  leak well below 49 nA over its whole working range; the Gate 1 leakage test confirms it.
- The filter's −3 dB point is 27.4 Hz (time constant 5.8 ms). After a step the input settles
  to 16-bit accuracy in 64 ms, less than one 200 ms sample.

**NTC divider.**
- 1.65 V at 25 °C, 1.00 V at 45 °C (the charge trip) and 0.76 V at 55 °C (the discharge
  trip). The slope is 36.7 mV/°C at 25 °C, 27.2 mV/°C at 45 °C and 21.4 mV/°C at 55 °C.
- The voltage stays inside the range where the ESP32 ADC is accurate (0.15 to 2.45 V at 12 dB
  attenuation) from 2.9 °C to above 100 °C. Below 2.9 °C it is above 2.45 V, where the ESP32
  ADC is less accurate. The firmware accepts readings from −20 to 100 °C (`kNtcMinC`,
  `kNtcMaxC`), so a cell temperature below 3 °C is read with less accuracy.
- Each NTC divider dissipates 0.27 mW in the NTC at 25 °C.

**Current sense.**
- 25.0 mV across the shunt at 5 A, well inside the INA226's ±81.92 mV range (2.5 µV per bit,
  16 bits). Discharge reads positive. The shunt dissipates 0.125 W at 5 A.
- If the module's R100 shunt is left in place, it carries part of the current and the reading
  is 4.76 % low, outside the 2 % of Gate 1 before calibration. Remove it (BOM item 12).

**Thermal model.**
- With 1 W in the core from time 0 and 25 °C air, the core reaches 26.34 °C after 1 minute,
  31.11 °C after 5 minutes, 43.25 °C after 20 minutes and 54.46 °C after one hour; it settles at
  57 °C. The two time constants are 8.4 s and 1422 s.
- ngspice and the Octave script (`matlab/thermal_step.m`) solve the same model in two different
  ways. They agree to within 0.0002 °C over the whole hour.
