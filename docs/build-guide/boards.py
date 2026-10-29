"""The two perfboards as data: every part, pin, hole and wire, and a check that the wiring
makes exactly the intended nets.

Boards are the 7 x 9 cm single-sided boards of BOM item 20: 30 columns (c = 0..29, along the
9 cm side) by 24 rows (r = 0..23), 2.54 mm pitch, seen from the component side with column 0
on the left. Every pin carries the net it belongs to. Wires are of two kinds:

- bare: tinned copper wire (or a resistor lead offcut) on the underside, soldered to every pad
  it runs over, along neighbouring holes only;
- jumper: insulated wire on the underside between two holes.

check() proves that the pins of each net are joined, and that no two nets touch.
"""

from collections import defaultdict

COLS, ROWS = 30, 24


class Board:
    def __init__(self, name, title):
        self.name, self.title = name, title
        self.parts = []    # dicts: ref, kind, value, pins [(label, (c, r), net)], extra
        self.bare = []     # (net, [(c, r), ...])
        self.jumpers = []  # (net, (c, r), (c, r))
        self.off = []      # (connector pin, goes to) for the harness tables

    def part(self, ref, kind, value, pins, **extra):
        self.parts.append({"ref": ref, "kind": kind, "value": value, "pins": pins, **extra})

    def wire(self, net, *holes):
        self.bare.append((net, list(holes)))

    def run(self, net, a, b):
        """Bare wire along a straight line of holes from a to b."""
        (c0, r0), (c1, r1) = a, b
        if c0 != c1 and r0 != r1:
            raise ValueError(f"{self.name}: bare wire {a}-{b} is not straight")
        n = max(abs(c1 - c0), abs(r1 - r0))
        dc, dr = (c1 > c0) - (c1 < c0), (r1 > r0) - (r1 < r0)
        self.wire(net, *[(c0 + k * dc, r0 + k * dr) for k in range(n + 1)])

    def jump(self, net, a, b):
        self.jumpers.append((net, a, b))

    def pins(self):
        for p in self.parts:
            for label, hole, net in p["pins"]:
                yield p, label, hole, net


def check(board):
    """Raises ValueError listing every problem; returns the nets and their pins."""
    errors = []
    pin_at = {}
    for p, label, hole, net in board.pins():
        c, r = hole
        if not (0 <= c < COLS and 0 <= r < ROWS):
            errors.append(f"{p['ref']}.{label} {hole} is off the board")
        if hole in pin_at:
            errors.append(f"{hole} holds two pins: {pin_at[hole][0]['ref']} and {p['ref']}")
        pin_at[hole] = (p, label, net)

    parent = {}

    def find(h):
        parent.setdefault(h, h)
        while parent[h] != h:
            parent[h] = parent[parent[h]]
            h = parent[h]
        return h

    def union(a, b):
        parent[find(a)] = find(b)

    declared = defaultdict(set)   # hole -> nets that wires say it carries
    for net, holes in board.bare:
        for a, b in zip(holes, holes[1:]):
            if abs(a[0] - b[0]) + abs(a[1] - b[1]) != 1:
                errors.append(f"bare wire {net}: {a} and {b} are not neighbours")
            union(a, b)
        for h in holes:
            declared[h].add(net)
    jumper_ends = {}
    for net, a, b in board.jumpers:
        for h in (a, b):
            if h in pin_at:
                errors.append(f"jumper {net} ends in {h}, which holds pin {pin_at[h][0]['ref']}")
            if h in jumper_ends:
                errors.append(f"{h} holds two jumper ends ({jumper_ends[h]} and {net})")
            jumper_ends[h] = net
            declared[h].add(net)
        union(a, b)

    for h, (p, label, net) in pin_at.items():
        find(h)
        declared[h].add(net)
    for p in board.parts:   # pins joined inside a module, such as the DevKit's two GND pins
        for a, b2 in p.get("ties", []):
            union(a, b2)

    groups = defaultdict(set)
    for h in list(parent):
        groups[find(h)].add(h)
    for g in groups.values():
        nets = set().union(*(declared[h] for h in g)) - {"NC"}
        if len(nets) > 1:
            errors.append(f"short between {sorted(nets)} at {sorted(g)[:6]}")
        if any("NC" in declared[h] for h in g) and len(g) > 1:
            errors.append(f"an unused pin is wired at {sorted(g)[:4]}")

    by_net = defaultdict(list)
    for h, (p, label, net) in pin_at.items():
        if net != "NC":
            by_net[net].append((p["ref"], label, h))
    for net, plist in by_net.items():
        roots = {find(h) for _, _, h in plist}
        if len(roots) > 1:
            errors.append(f"net {net} is not joined: {sorted(plist)}")
    if errors:
        raise ValueError(f"{board.name}:\n  " + "\n  ".join(errors))
    return by_net


# --------------------------------------------------------------------------------------------
# Board A: the four tap dividers (architecture section 5) and the ADS1115.

def board_a():
    b = Board("A", "Board A: cell-tap sensing")
    taps = ["B1", "B2", "B3", "B+"]
    b.part("J1", "jst", "JST-XH 5-pin", [
        ("B-", (1, 3), "NC"), ("B1", (1, 4), "B1"), ("B2", (1, 5), "B2"),
        ("B3", (1, 6), "B3"), ("B+", (1, 7), "B+")], dir="v", note="tap harness from the pack")
    for k in range(4):
        y = 3 + 5 * k
        tap, node, adc = taps[k], f"N{k + 1}", f"A{k}"
        b.part(f"R{k + 1}", "res", "330k", [("1", (4, y), tap), ("2", (8, y), node)])
        b.part(f"R{k + 5}", "res", "10k", [("1", (9, y), node), ("2", (13, y), adc)])
        b.part(f"R{k + 9}", "res", "56k", [("1", (9, y + 1), node), ("2", (13, y + 1), "GND")])
        b.part(f"C{k + 1}", "cap", "100n", [("1", (14, y), adc), ("2", (14, y + 1), "GND")])
        b.part(f"D{k + 1}", "diode", "clamp (TBD)", [("A", (14, y - 1), adc), ("K", (17, y - 1), "3V3")],
               note="fit after the Gate 1 leakage test")
        b.run(tap, (1, 4 + k), (2, 4 + k))
        b.jump(tap, (2, 4 + k), (3, y))
        b.run(tap, (3, y), (4, y))
        b.run(node, (8, y), (9, y))
        b.run(node, (9, y), (9, y + 1))
        b.wire(adc, (13, y - 1), (13, y), (14, y), (14, y - 1))
        b.run("GND", (13, y + 1), (15, y + 1))
        b.jump(adc, (13, y - 1), (19, 10 + k))
        b.run(adc, (19, 10 + k), (20, 10 + k))
    b.run("GND", (15, 1), (15, 21))
    b.run("3V3", (17, 1), (17, 21))
    b.part("J2", "module", "ADS1115 module", [
        ("VDD", (20, 4), "3V3"), ("GND", (20, 5), "GND"), ("SCL", (20, 6), "SCL"),
        ("SDA", (20, 7), "SDA"), ("ADDR", (20, 8), "GND"), ("ALRT", (20, 9), "NC"),
        ("A0", (20, 10), "A0"), ("A1", (20, 11), "A1"), ("A2", (20, 12), "A2"), ("A3", (20, 13), "A3")],
        dir="v", body=(20, 3, 27.4, 14), note="1 x 10 female header")
    b.part("J3", "header", "4-pin header", [
        ("3V3", (29, 4), "3V3"), ("GND", (29, 5), "GND"), ("SCL", (29, 6), "SCL"), ("SDA", (29, 7), "SDA")],
        dir="v", note="to board B, J7")
    b.run("3V3", (17, 4), (29, 4))
    b.run("GND", (15, 5), (16, 5))
    b.jump("GND", (16, 5), (19, 5))
    b.run("GND", (19, 5), (29, 5))
    b.run("SCL", (20, 6), (29, 6))
    b.run("SDA", (20, 7), (29, 7))
    b.run("GND", (20, 8), (21, 8))
    b.jump("GND", (21, 8), (22, 5))
    b.off = [
        ("J1 B-", "nothing (see the note on the sense ground)"),
        ("J1 B1, B2, B3, B+", "the pack's taps, each through a 1-10 kΩ resistor at the pack end"),
        ("J2", "ADS1115 module (plugs in)"),
        ("J3", "board B J7: 3V3, GND, SCL, SDA"),
    ]
    return b


# --------------------------------------------------------------------------------------------
# Board B: ESP32, NTC dividers (section 6), INA226 (section 4), relay inputs and alarm (section 7).

ESP_TOP = ["VIN", "GND", "D13", "D12", "D14", "D27", "D26", "D25", "D33", "D32", "D35", "D34", "VN", "VP", "EN"]
ESP_BOTTOM = ["3V3", "GND", "D15", "D2", "D4", "RX2", "TX2", "D5", "D18", "D19", "D21", "RX0", "TX0", "D22", "D23"]


def board_b():
    b = Board("B", "Board B: ESP32, temperatures, current, relays and alarm")
    top_nets = {"VIN": "5V", "GND": "GND", "D27": "ALARM", "D26": "CHARGE", "D25": "LOAD",
                "D33": "NTC2", "D32": "NTC1", "D35": "NTC4", "D34": "NTC3", "VP": "NTC5"}
    bot_nets = {"3V3": "3V3", "GND": "GND", "D21": "SDA", "D22": "SCL"}
    pins = [(n, (1 + i, 2), top_nets.get(n, "NC")) for i, n in enumerate(ESP_TOP)]
    pins += [(n, (1 + i, 12), bot_nets.get(n, "NC")) for i, n in enumerate(ESP_BOTTOM)]
    b.part("U1", "esp32", "ESP32 DevKit V1 (30-pin)", pins, body=(-1.6, 1.2, 17.6, 12.8),
           note="2 x 15 female headers, rows 10 holes apart", ties=[((2, 2), (2, 12))])

    # ESP32 pins out to pads above the top row and below the bottom row.
    for name, net in [("VIN", "5V"), ("D27", "ALARM"), ("D26", "CHARGE"), ("D25", "LOAD"),
                      ("D33", "NTC2"), ("D32", "NTC1"), ("D35", "NTC4"), ("D34", "NTC3"), ("VP", "NTC5")]:
        c = 1 + ESP_TOP.index(name)
        b.run(net, (c, 2), (c, 1))
    b.run("3V3", (1, 12), (1, 16))
    b.run("3V3", (1, 16), (21, 16))
    b.run("GND", (2, 12), (2, 13))
    b.jump("GND", (2, 13), (3, 19))
    b.run("SDA", (11, 12), (11, 13))
    b.run("SCL", (14, 12), (14, 13))

    # NTC dividers: 10k from 3V3, 100 nF to GND, a 2-pin connector per sensor.
    b.run("3V3", (21, 0), (21, 17))
    b.run("GND", (25, 0), (25, 19))
    esp_pad = {"NTC1": (10, 1), "NTC2": (9, 1), "NTC3": (12, 1), "NTC4": (11, 1), "NTC5": (14, 1)}
    for n in range(5):
        r = 1 + 3 * n
        net = f"NTC{n + 1}"
        b.part(f"R{n + 1}", "res", "10k", [("1", (22, r), "3V3"), ("2", (26, r), net)])
        b.part(f"C{n + 1}", "cap", "100n", [("1", (27, r), net), ("2", (27, r + 1), "GND")])
        b.part(f"J{n + 9}", "jst", "JST-XH 2-pin", [("T", (29, r), net), ("G", (29, r + 1), "GND")],
               dir="v", note=f"NTC{n + 1}" + (" (air)" if n == 4 else f" (cell {n + 1})"))
        b.run("3V3", (21, r), (22, r))
        b.run(net, (26, r), (29, r))
        b.run("GND", (25, r + 1), (29, r + 1))
        b.jump(net, esp_pad[net], (28, r))

    # INA226 module and the shunt's Kelvin pair.
    b.part("J8", "module", "INA226 module", [
        ("VBS", (20, 23), "IN-"), ("IN-", (21, 23), "IN-"), ("IN+", (22, 23), "IN+"), ("ALE", (23, 23), "NC"),
        ("SDA", (24, 23), "SDA"), ("SCL", (25, 23), "SCL"), ("GND", (26, 23), "GND"), ("VCC", (27, 23), "3V3")],
        dir="h", body=(19.4, 17.6, 27.6, 23.4), note="1 x 8 female header; module stands over the board")
    # The Kelvin pair enters at the board edge beside the module, so it can be plugged in with
    # the module fitted.
    b.part("J14", "header", "2-pin header", [("IN+", (17, 23), "IN+"), ("IN-", (18, 23), "IN-")],
           dir="h", note="shunt sense pair")
    b.run("IN-", (18, 23), (21, 23))
    b.run("IN+", (17, 23), (17, 22))
    b.jump("IN+", (17, 22), (22, 22))
    b.run("IN+", (22, 22), (22, 23))
    b.wire("GND", (26, 23), (26, 22), (26, 21), (26, 20), (26, 19), (25, 19))
    b.run("3V3", (27, 23), (27, 22))
    b.jump("3V3", (27, 22), (20, 17))
    b.run("3V3", (20, 17), (21, 17))
    b.run("SDA", (24, 21), (24, 23))
    b.run("SCL", (25, 21), (25, 23))
    b.jump("SDA", (11, 13), (24, 22))
    b.jump("SCL", (14, 13), (25, 22))

    # Link to board A.
    b.part("J7", "header", "4-pin header", [
        ("3V3", (29, 16), "3V3"), ("GND", (29, 17), "GND"), ("SCL", (29, 18), "SCL"), ("SDA", (29, 19), "SDA")],
        dir="v", note="to board A, J3")
    b.run("3V3", (21, 16), (22, 16))
    b.jump("3V3", (22, 16), (28, 16))
    b.run("3V3", (28, 16), (29, 16))
    b.run("GND", (25, 17), (29, 17))
    b.run("SCL", (28, 18), (29, 18))
    b.jump("SCL", (28, 18), (25, 21))
    b.run("SDA", (28, 19), (29, 19))
    b.jump("SDA", (28, 19), (24, 21))

    # 5 V in, relay inputs with pull-ups, buzzer and LED.
    b.part("J4", "terminal", "2-pin screw terminal", [("+5V", (0, 18), "5V"), ("GND", (0, 20), "GND")],
           dir="v", note="from the LM2596 (5.00 V)")
    b.run("5V", (0, 18), (2, 18))
    b.jump("5V", (1, 18), (1, 1))
    b.wire("GND", (0, 20), (0, 19), (1, 19), (2, 19), (3, 19))
    b.run("GND", (3, 19), (25, 19))
    b.part("J5", "header", "4-pin header", [
        ("GND", (4, 23), "GND"), ("IN1", (5, 23), "LOAD"), ("IN2", (6, 23), "CHARGE"), ("VCC", (7, 23), "5V")],
        dir="h", note="to the relay module")
    b.part("R6", "res", "10k", [("1", (5, 17), "3V3"), ("2", (5, 21), "LOAD")], dir="v")
    b.part("R7", "res", "10k", [("1", (6, 17), "3V3"), ("2", (6, 21), "CHARGE")], dir="v")
    b.run("3V3", (5, 16), (5, 17))
    b.run("3V3", (6, 16), (6, 17))
    b.run("LOAD", (5, 21), (5, 23))
    b.run("CHARGE", (6, 21), (6, 23))
    b.jump("LOAD", (8, 1), (5, 22))
    b.jump("CHARGE", (7, 1), (6, 22))
    b.run("GND", (4, 19), (4, 23))
    b.jump("5V", (2, 18), (7, 22))
    b.run("5V", (7, 22), (7, 23))
    b.part("J6", "header", "3-pin header", [("VCC", (10, 23), "5V"), ("I/O", (11, 23), "ALARM"), ("GND", (12, 23), "GND")],
           dir="h", note="to the buzzer module")
    b.run("5V", (7, 23), (10, 23))
    b.run("GND", (12, 23), (12, 19))
    b.run("ALARM", (11, 21), (11, 23))
    b.jump("ALARM", (6, 1), (11, 22))
    b.part("R8", "res", "330R", [("1", (11, 21), "ALARM"), ("2", (15, 21), "LEDA")], note="sized for the LED")
    b.part("LED1", "led", "red LED", [("A", (16, 21), "LEDA"), ("K", (17, 21), "GND")])
    b.run("LEDA", (15, 21), (16, 21))
    b.run("GND", (17, 21), (17, 19))
    b.off = [
        ("J4", "LM2596 output, set to 5.00 V before connecting"),
        ("J5 GND, IN1, IN2, VCC", "relay module GND, IN1 (K_LOAD), IN2 (K_CHARGE), VCC"),
        ("J6 VCC, I/O, GND", "active buzzer module"),
        ("J7", "board A J3: 3V3, GND, SCL, SDA"),
        ("J8", "INA226 module (plugs in)"),
        ("J9-J12", "NTC1-NTC4 on cells 1-4"),
        ("J13", "NTC5 in the air of the vent path"),
        ("J14 IN+, IN-", "the shunt's Kelvin sense pair: IN+ on the fuse side, IN- on the load side"),
    ]
    return b


BOARDS = [board_a, board_b]

if __name__ == "__main__":
    for make in BOARDS:
        bd = make()
        nets = check(bd)
        print(f"board {bd.name}: {len(bd.parts)} parts, {len(bd.bare)} bare wires, "
              f"{len(bd.jumpers)} jumpers, {len(nets)} nets: all joined, no shorts")
