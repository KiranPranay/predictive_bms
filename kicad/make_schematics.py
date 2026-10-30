"""Writes the KiCad simulation schematics in kicad/sim/.

    python3 kicad/make_schematics.py

Each circuit is one KiCad project that opens in KiCad 10 and runs in its simulator (ngspice).
run_sims.py exports each schematic with kicad-cli, runs ngspice and checks the results. The part
values come from docs/wiring.md and from the firmware's configuration
(firmware/components/bms_core/include/bms/), with the architecture section named on the page.
"""

import datetime
import pathlib

import sch

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "sim"
VERSION = "20260306"   # KiCad 10.0
COMPANY = "Predictive BMS prototype"

R, C = "Device:R", "Device:C"
VDC, IDC = "Simulation_SPICE:VDC", "Simulation_SPICE:IDC"
GND, V3V3 = "power:GND", "power:+3V3"


def pin_offset(lib, lib_id, angle, num):
    """Where pin num sits relative to the symbol's anchor, on the page."""
    px, py = lib.pins(lib_id)[num]
    rx, ry = sch.rotate(px, py, angle)
    return rx, -ry


ANGLE = {"down": 0, "right": 90, "up": 180, "left": 270}   # pin 1 to pin 2, as drawn in the library


def two_pin(s, lib_id, ref, value, at, to="down", first="1", **kw):
    """Places a two-pin part with pin `first` at `at` and the other pin towards `to`. Returns the
    other pin's position."""
    angle = (ANGLE[to] + (0 if first == "1" else 180)) % 360
    ox, oy = pin_offset(s.lib, lib_id, angle, first)
    pins = s.part(lib_id, ref, value, at[0] - ox, at[1] - oy, angle, **kw)
    other = [p for n, p in pins.items() if n != first][0]
    return (round(other[0], 4), round(other[1], 4))


def ground(s, at):
    s.power(GND, at[0], at[1])


def flag(s, at, left=12.7):
    """A PWR_FLAG to the left of `at`: tells KiCad's ERC that this supply net is driven."""
    s.wire(at, (at[0] - left, at[1]))
    s.power("power:PWR_FLAG", at[0] - left, at[1])


def sim_fields(device, type_, params, pins="1=+ 2=-"):
    return {"Sim.Device": device, "Sim.Type": type_, "Sim.Pins": pins, "Sim.Params": params}


def run(s, start, *parts):
    """Draws a horizontal chain from `start`: each item is a gap (a number, in mm of wire) or a
    two-pin part (lib_id, ref, value, fields[, options]). Returns the end point and each part's
    pins."""
    x, y = start
    pins = []
    for item in parts:
        if isinstance(item, (int, float)):
            s.wire((x, y), (x + item, y))
            x += item
        else:
            lib_id, ref, value, fields, *options = item
            end = two_pin(s, lib_id, ref, value, (x, y), to="right", fields=fields, **(options[0] if options else {}))
            pins.append(((x, y), end))
            x = end[0]
    return (x, y), pins


# --- 1. Cell taps --------------------------------------------------------------------------

def cell_taps(lib, date):
    s = sch.Schematic(
        "cell-taps", "Cell tap dividers and filters (board A)", lib,
        ["Architecture rev 2.2 section 5; docs/wiring.md section 3.1",
         "Four channels built the same way; I1 stands for clamp leakage or ADC input current",
         "Simulation: .op gives the ADC voltages at 4.2 V per cell"])
    # The pack: four cells in series, B- at the bottom (the simulation's ground).
    x, y = 40.64, 154.94
    ground(s, (x, y))
    flag(s, (x, y))
    taps = ["B1", "B2", "B3", "B+"]
    bottom = (x, y)
    for k in range(4):
        top = two_pin(s, VDC, f"V{k + 1}", "4.2", bottom, to="up", first="2",
                      fields=sim_fields("V", "DC", "dc=4.2"))
        stub = (x + 12.7, top[1])
        s.wire(top, stub)
        s.label(taps[k], stub[0], stub[1], glob=True)
        if k < 3:
            nxt = (x, top[1] - 7.62)
            s.wire(top, nxt)
            s.junction(*top)
            bottom = nxt
    s.text("The pack: cells 1 to 4,\n4.2 V each (full charge).\nB- is the simulation ground.",
           x - 12.7, y + 10.16)

    for k in range(4):
        n, row = k + 1, 45.72 + k * 30.48
        start = (81.28, row)
        s.label(taps[k], start[0], start[1], angle=180, glob=True)
        (div, _) = run(s, start, 2.54,
                       (R, f"R{12 + n}", "10k", {"Note": "R_entry at the pack, 1-10 kΩ (section 11)"}),
                       5.08, (R, f"R{n}", "330k", None), 12.7)
        s.label(f"DIV{n}", div[0] - 10.16, div[1])
        lo = two_pin(s, R, f"R{8 + n}", "56k", (div[0], row + 5.08))
        s.wire(div, (div[0], row + 5.08))
        ground(s, lo)
        (node, _) = run(s, div, 5.08, (R, f"R{4 + n}", "10k", None), 12.7)
        s.junction(*div)
        cap = two_pin(s, C, f"C{n}", "100n", (node[0], row + 5.08))
        s.wire(node, (node[0], row + 5.08))
        ground(s, cap)
        out = (node[0] + 25.4, row)
        s.wire(node, (node[0] + 12.7, row), out)
        s.junction(*node)
        s.label(f"ADC{n}", out[0], out[1], glob=True)
        s.text(f"to ADS1115 A{k}", out[0] + 11.43, row - 0.635)
        if n == 4:
            leak = (node[0] + 12.7, row)
            lk = two_pin(s, IDC, "I1", "0", (leak[0], row + 5.08), fields=sim_fields("I", "DC", "dc=0"))
            s.wire(leak, (leak[0], row + 5.08))
            s.junction(*leak)
            ground(s, lk)
    s.text(".op", 25.4, 27.94, size=2.0, sim=True)
    s.text("R13-R16 are the series resistors at the tap end of each wire\n"
           "(1-10 kΩ, section 11); 10 kΩ is drawn. The clamp diode from each\n"
           "ADC input to 3V3 is TBD (BOM item 11) and is not drawn. I1 stands for\n"
           "its leakage and for the ADC input current; run_sims.py sweeps it.", 81.28, 162.56)
    return s


# --- 2. NTC divider ------------------------------------------------------------------------

def ntc(lib, date):
    s = sch.Schematic(
        "ntc-divider", "NTC temperature divider (board B), one of five", lib,
        ["Architecture rev 2.2 section 6; docs/wiring.md section 4.2",
         "NTC 10k B3950, modelled by its B-value equation at the simulation temperature",
         "Simulation: .dc TEMP -20 100 1 sweeps the NTC from -20 to 100 °C"])
    x0, top, bot = 50.8, 60.96, 101.6
    vs = two_pin(s, VDC, "V1", "3.3", (x0, bot), to="up", first="2", fields=sim_fields("V", "DC", "dc=3.3"))
    ground(s, (x0, bot))
    flag(s, (x0, bot))
    s.wire(vs, (x0, top))
    s.power(V3V3, x0, top)
    flag(s, (x0, top))
    s.text("ESP32 3V3", x0 + 5.08, top + 12.7)
    px = x0 + 30.48
    s.wire((x0, top), (px, top))
    pu = two_pin(s, R, "R1", "10k", (px, top + 2.54), fields={"Note": "1 % metal film (section 6)"})
    s.wire((px, top), (px, top + 2.54))
    node = (px, pu[1] + 7.62)
    s.wire(pu, node)
    s.junction(*node)
    th = two_pin(s, "Device:Thermistor_NTC", "TH1", "10k B3950", (px, node[1] + 2.54),
                 fields=sim_fields("I", "=", "i=V(NTC_ADC)/(10k*exp(3950*(1/(temper+273.15)-1/298.15)))"))
    s.wire(node, (px, node[1] + 2.54))
    ground(s, th)
    cx = px + 22.86
    s.wire(node, (cx, node[1]))
    cap = two_pin(s, C, "C1", "100n", (cx, node[1] + 2.54))
    s.wire((cx, node[1]), (cx, node[1] + 2.54))
    ground(s, cap)
    s.wire((cx, node[1]), (cx + 22.86, node[1]))
    s.junction(cx, node[1])
    s.label("NTC_ADC", cx + 22.86, node[1], glob=True)
    s.text("to ESP32 GPIO32-36 (ADC1)", cx + 38.1, node[1] - 0.635)
    s.text(".dc TEMP -20 100 1", 25.4, 27.94, size=2.0, sim=True)
    s.text("TH1 is a current source equal to V / R(T), where R(T) = 10 kΩ x exp(3950 x (1/T - 1/298.15)) and T is\n"
           "in kelvin: the B3950 equation the firmware uses (section 6). T is the simulation temperature ('temper'),\n"
           "which the DC sweep steps from -20 to 100 °C. No other part here depends on it.", 25.4, 127.0)
    return s


# --- 3. Current sense ----------------------------------------------------------------------

def current_sense(lib, date):
    s = sch.Schematic(
        "current-sense", "Pack current shunt and INA226 input", lib,
        ["Architecture rev 2.2 section 4; docs/wiring.md sections 2 and 4.3",
         "I1 sets the pack current: positive is discharge, negative is charge",
         "Simulation: .dc I1 -5 5 0.1"])
    x0, top, bot = 50.8, 60.96, 101.6
    vp = two_pin(s, VDC, "V1", "14.8", (x0, bot), to="up", first="2", fields=sim_fields("V", "DC", "dc=14.8"))
    ground(s, (x0, bot))
    flag(s, (x0, bot))
    s.wire(vp, (x0, top))
    s.text("Pack after the BMS\nand the 7.5 A fuse", x0 + 5.08, top + 15.24)
    (end, p) = run(s, (x0, top), 20.32, (R, "R1", "5m", {"Note": "5 mΩ external shunt (BOM item 13)"}), 25.4)
    s.label("SENSE_P", x0 + 7.62, top)
    s.label("SENSE_N", p[0][1][0] + 7.62, top)
    ld = two_pin(s, IDC, "I1", "1", end, fields=sim_fields("I", "DC", "dc=1"))
    ground(s, ld)
    s.text("Load (or charger)", end[0] + 5.08, top + 15.24)
    # The INA226 inputs, and the module's own shunt, which is removed.
    y2 = top + 55.88
    s.label("SENSE_P", x0 + 12.7, y2, angle=180)
    # R2 is excluded from the simulation, as it is removed from the module.
    (e2, _) = run(s, (x0 + 12.7, y2), 7.62,
                  (R, "R2", "0.1", {"Note": "INA226 module's R100: remove it (BOM item 12)"}, {"sim": False}), 7.62)
    s.label("SENSE_N", e2[0], e2[1])
    s.text("INA226 IN+ and IN- (Kelvin leads). R2 is the module's own R100 shunt. It is excluded from the\n"
           "simulation because it is removed from the module; run_sims.py puts it back once to show the error.",
           x0 - 12.7, y2 + 10.16)
    s.text(".dc I1 -5 5 0.1", 25.4, 27.94, size=2.0, sim=True)
    return s


# --- 4. Thermal model ----------------------------------------------------------------------

def thermal(lib, date):
    s = sch.Schematic(
        "thermal-model", "Two-node thermal model of one cell (electrical analogue)", lib,
        ["Architecture rev 2.2 sections 9.1-9.2; values: the firmware's ThermalParams (types.h)",
         "C_core 40, C_surf 5 J/°C (45 together, section 9.1); R_core 2, R_air 30 °C/W:",
         "development values, replaced by the Gate 9 fit"])
    x0, y0, bot = 50.8, 66.04, 93.98
    hs = two_pin(s, "Simulation_SPICE:IPULSE", "I1", "1 W step", (x0, bot), to="up",
                 fields=sim_fields("I", "PULSE", "y1=0 y2=1 td=10 tr=1m tf=1m tw=1e6 per=2e6"))
    ground(s, (x0, bot))
    flag(s, (x0, bot))
    s.wire(hs, (x0, y0))
    core = (x0 + 30.48, y0)
    s.wire((x0, y0), core)
    s.label("T_CORE", x0 + 12.7, y0)
    cc = two_pin(s, C, "C1", "40", (core[0], y0 + 5.08))
    s.wire(core, (core[0], y0 + 5.08))
    ground(s, cc)
    (surf, _) = run(s, core, 7.62, (R, "R1", "2", None), 22.86)
    s.junction(*core)
    s.label("T_SURF", surf[0] - 15.24, y0)
    cs = two_pin(s, C, "C2", "5", (surf[0], y0 + 5.08))
    s.wire(surf, (surf[0], y0 + 5.08))
    ground(s, cs)
    (amb, _) = run(s, surf, 7.62, (R, "R2", "30", None), 22.86)
    s.junction(*surf)
    s.label("T_AMB", amb[0] - 15.24, y0)
    va = two_pin(s, VDC, "V1", "25", (amb[0], y0 + 5.08), fields=sim_fields("V", "DC", "dc=25"))
    s.wire(amb, (amb[0], y0 + 5.08))
    ground(s, va)
    s.text("Heat made in the core\n(Joule heat or a fault)", x0 - 25.4, y0 + 6.35)
    s.text("Core:\nC_core", core[0] + 6.35, y0 + 15.24)
    s.text("Surface, where\nthe NTC sits:\nC_surf", surf[0] + 6.35, y0 + 15.24)
    s.text("Air:\nT_amb", amb[0] + 6.35, y0 + 15.24)
    s.text("R1 = R_core, core to surface; R2 = R_air, surface to air.", core[0] + 2.54, y0 - 10.16)
    s.text("Electrical analogue: 1 V = 1 °C, 1 A = 1 W, 1 F = 1 J/°C, 1 Ω = 1 °C/W.\n"
           "The firmware's Kalman observer (section 9.2) runs this same model on every sample.\n"
           "matlab/thermal_step.m solves it a second way, in Octave, and run_sims.py compares the two.",
           25.4, 129.54)
    s.text(".tran 1 3610", 25.4, 27.94, size=2.0, sim=True)
    return s


CIRCUITS = [cell_taps, ntc, current_sense, thermal]


def main():
    lib = sch.Library()
    date = datetime.date.today().isoformat()
    for make in CIRCUITS:
        s = make(lib, date)
        s.write(OUT / s.name, VERSION, date, "1", COMPANY)
        print("wrote", OUT / s.name / f"{s.name}.kicad_sch")


if __name__ == "__main__":
    main()
