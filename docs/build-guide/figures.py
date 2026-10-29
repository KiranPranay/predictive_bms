"""Draws every figure of the build guide as SVG, from the board data in boards.py and the values
of the architecture document. Standard library only.

    python3 docs/build-guide/figures.py      (writes docs/build-guide/figures/*.svg)
"""

import math
import pathlib

import boards as bd

OUT = pathlib.Path(__file__).resolve().parent / "figures"

FONT = "Liberation Sans, Arial, Helvetica, sans-serif"
INK, INK2, MUTED, LINE = "#1d1d1b", "#4f4d48", "#8a8780", "#d6d2c6"
BOARD_TOP, BOARD_BOTTOM, PAD = "#efdcae", "#e8d4a2", "#c89a4c"
NET_COLORS = {
    "GND": "#2b2b2b", "3V3": "#d03b3b", "5V": "#e07b00", "SDA": "#2a78d6", "SCL": "#b07d00",
    "LOAD": "#c2185b", "CHARGE": "#8e24aa", "ALARM": "#6d4c41", "LEDA": "#a1887f",
    "IN+": "#00897b", "IN-": "#00695c",
}


def net_color(net):
    if net in NET_COLORS:
        return NET_COLORS[net]
    if net in ("B1", "B2", "B3", "B+"):
        return "#6a3fd0"
    if net.startswith("N"):
        return "#9c7fe0" if not net.startswith("NTC") else "#0f8a8a"
    if net.startswith("A"):
        return "#1b9e77"
    return INK2


class Svg:
    def __init__(self, w, h):
        self.w, self.h, self.items = w, h, []

    def add(self, s):
        self.items.append(s)

    @staticmethod
    def _dash(dash):
        return f' stroke-dasharray="{dash}"' if dash else ""

    def rect(self, x, y, w, h, fill="none", stroke=INK, sw=1.2, rx=0, dash=None, opacity=None):
        op = f' fill-opacity="{opacity}"' if opacity is not None else ""
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" fill="{fill}"{op} '
                 f'stroke="{stroke}" stroke-width="{sw}"{self._dash(dash)}/>')

    def line(self, x1, y1, x2, y2, stroke=INK, sw=1.4, dash=None, cap="round"):
        self.add(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke}" '
                 f'stroke-width="{sw}" stroke-linecap="{cap}"{self._dash(dash)}/>')

    def poly(self, pts, stroke=INK, sw=1.4, fill="none", dash=None, close=False):
        d = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        tag = "polygon" if close else "polyline"
        self.add(f'<{tag} points="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" '
                 f'stroke-linejoin="round" stroke-linecap="round"{self._dash(dash)}/>')

    def path(self, d, stroke=INK, sw=1.4, fill="none", dash=None, opacity=None):
        op = f' stroke-opacity="{opacity}"' if opacity is not None else ""
        self.add(f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round" '
                 f'stroke-linejoin="round"{op}{self._dash(dash)}/>')

    def circle(self, cx, cy, r, fill="none", stroke=INK, sw=1.2):
        self.add(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')

    def text(self, x, y, s, size=12, anchor="start", weight="normal", fill=INK, rotate=None, italic=False):
        s = str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        rot = f' transform="rotate({rotate} {x:.1f} {y:.1f})"' if rotate else ""
        it = ' font-style="italic"' if italic else ""
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="{anchor}" '
                 f'font-weight="{weight}" fill="{fill}"{it}{rot}>{s}</text>')

    def save(self, name):
        OUT.mkdir(exist_ok=True)
        body = "\n".join(self.items)
        (OUT / name).write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" width="{self.w}" '
            f'height="{self.h}" font-family="{FONT}">\n<rect width="100%" height="100%" fill="#ffffff"/>\n'
            f'{body}\n</svg>\n')


# ============================================================================================
# Schematic symbols (IEC style), drawn at a point, horizontal unless noted.

def resistor(s, x1, y1, x2, y2, label="", value="", side=1):
    """Resistor between two points on a horizontal or vertical line."""
    L = math.hypot(x2 - x1, y2 - y1)
    ux, uy = (x2 - x1) / L, (y2 - y1) / L
    bl, bw = 30, 11
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    s.line(x1, y1, mx - ux * bl / 2, my - uy * bl / 2)
    s.line(mx + ux * bl / 2, my + uy * bl / 2, x2, y2)
    if abs(uy) < 0.5:
        s.rect(mx - bl / 2, my - bw / 2, bl, bw, fill="#fff")
        if label:
            s.text(mx, my - 10 * side - (3 if side < 0 else 0) + (14 if side < 0 else 0), label, 11, "middle", "bold")
        if value:
            s.text(mx, my + (20 if side > 0 else -12), value, 11, "middle", fill=INK2)
    else:
        s.rect(mx - bw / 2, my - bl / 2, bw, bl, fill="#fff")
        if label:
            s.text(mx + 10 * side, my - 2, label, 11, "start" if side > 0 else "end", "bold")
        if value:
            s.text(mx + 10 * side, my + 12, value, 11, "start" if side > 0 else "end", fill=INK2)


def capacitor(s, x, y1, y2, label="", value=""):
    """Vertical capacitor from (x, y1) down to (x, y2)."""
    my = (y1 + y2) / 2
    s.line(x, y1, x, my - 4)
    s.line(x, my + 4, x, y2)
    s.line(x - 10, my - 4, x + 10, my - 4, sw=2)
    s.line(x - 10, my + 4, x + 10, my + 4, sw=2)
    if label:
        s.text(x + 13, my - 2, label, 11, weight="bold")
    if value:
        s.text(x + 13, my + 11, value, 11, fill=INK2)


def ground(s, x, y):
    s.line(x, y, x, y + 6)
    for k, w in enumerate((12, 8, 4)):
        s.line(x - w, y + 6 + 4 * k, x + w, y + 6 + 4 * k, sw=1.4)


def rail(s, x, y, name, up=True):
    """Supply symbol: a short bar with the rail name."""
    s.line(x, y, x, y - 8 if up else y + 8)
    yy = y - 8 if up else y + 8
    s.line(x - 9, yy, x + 9, yy, sw=2)
    s.text(x, yy - 5 if up else yy + 14, name, 11, "middle", "bold")


def dot(s, x, y):
    s.circle(x, y, 2.8, fill=INK, stroke=INK)


def diode(s, x1, y, x2, label="", value="", dashed=False):
    """Horizontal diode, anode at x1, cathode at x2."""
    mx = (x1 + x2) / 2
    d = "4 3" if dashed else None
    s.line(x1, y, mx - 8, y, dash=d)
    s.line(mx + 8, y, x2, y, dash=d)
    s.poly([(mx - 8, y - 7), (mx - 8, y + 7), (mx + 6, y)], fill="#fff", close=True, dash=d)
    s.line(mx + 7, y - 7, mx + 7, y + 7, sw=2)
    if label:
        s.text(mx, y - 11, label, 11, "middle", "bold")
    if value:
        s.text(mx, y + 20, value, 10, "middle", fill=INK2)


def contact_no(s, x1, y, x2, label=""):
    """Normally-open contact, horizontal."""
    s.line(x1, y, x1 + 12, y)
    s.line(x2 - 12, y, x2, y)
    s.line(x1 + 12, y, x2 - 14, y - 12, sw=1.8)
    s.circle(x1 + 12, y, 2, fill=INK)
    s.circle(x2 - 12, y, 2, fill=INK)
    if label:
        s.text((x1 + x2) / 2, y + 18, label, 11, "middle", "bold")


def fuse(s, x1, y, x2, label="", value=""):
    mx = (x1 + x2) / 2
    s.line(x1, y, mx - 16, y)
    s.line(mx + 16, y, x2, y)
    s.rect(mx - 16, y - 7, 32, 14, fill="#fff")
    s.line(mx - 16, y, mx + 16, y, sw=1)
    if label:
        s.text(mx, y - 12, label, 11, "middle", "bold")
    if value:
        s.text(mx, y + 22, value, 10, "middle", fill=INK2)


def battery(s, x, y, label="", cells=4):
    """Battery of cells on a horizontal line starting at x, centred on y; returns end x."""
    for k in range(cells):
        cx = x + 14 + k * 22
        s.line(cx, y - 14, cx, y + 14, sw=2)
        s.line(cx + 8, y - 7, cx + 8, y + 7, sw=4)
        if k:
            s.line(cx - 14, y, cx, y, sw=1)
    s.line(x, y, x + 14, y)
    end = x + 14 + (cells - 1) * 22 + 8
    s.line(end, y, end + 12, y)
    s.text(x + 6, y - 20, "+", 13, weight="bold")
    if label:
        s.text((x + end) / 2 + 6, y + 32, label, 11, "middle", fill=INK2)
    return end + 12


def box(s, x, y, w, h, title, lines=(), fill="#f6f4ee", stroke=INK, title_size=12, dash=None):
    s.rect(x, y, w, h, fill=fill, stroke=stroke, rx=6, dash=dash)
    s.text(x + w / 2, y + 18, title, title_size, "middle", "bold")
    for k, t in enumerate(lines):
        s.text(x + w / 2, y + 34 + 14 * k, t, 10.5, "middle", fill=INK2)


def ntc_symbol(s, x, y1, y2, label=""):
    """Vertical thermistor: resistor body with a diagonal line."""
    my = (y1 + y2) / 2
    s.line(x, y1, x, my - 15)
    s.line(x, my + 15, x, y2)
    s.rect(x - 5.5, my - 15, 11, 30, fill="#fff")
    s.line(x - 12, my + 13, x + 12, my - 13, sw=1.2)
    s.line(x - 12, my + 13, x - 18, my + 13, sw=1.2)
    s.text(x + 14, my + 18, "t°", 10, fill=INK2)
    if label:
        s.text(x + 14, my - 2, label, 11, weight="bold")


# ============================================================================================
# Perfboard drawings.

P = 22   # pixels per hole


class BoardView:
    def __init__(self, board, bottom=False):
        self.b, self.bottom = board, bottom
        self.ml, self.mt = 44, 70
        self.ox = self.ml + 3.2 * P
        self.oy = self.mt + 2.3 * P
        self.W = int(self.ox + 29 * P + 3.2 * P + 24)
        self.H = int(self.oy + 23 * P + 2.3 * P + (96 if bottom else 18))

    def X(self, c):
        return self.ox + ((bd.COLS - 1 - c) if self.bottom else c) * P

    def Y(self, r):
        return self.oy + r * P


def draw_board(board, bottom):
    v = BoardView(board, bottom)
    s = Svg(v.W, v.H)
    X, Y = v.X, v.Y
    bx0, by0 = v.ox - 3.2 * P, v.oy - 2.3 * P
    bw, bh = 29 * P + 6.4 * P, 23 * P + 4.6 * P
    side = "underside, seen with the board turned over left to right" if bottom else "component side"
    s.text(bx0, 30, f"{board.title}", 18, weight="bold")
    s.text(bx0, 50, f"7 × 9 cm perfboard, 30 × 24 holes at 2.54 mm · {side}", 12, fill=INK2)
    s.rect(bx0, by0, bw, bh, fill=BOARD_BOTTOM if bottom else BOARD_TOP, stroke="#a88c55", sw=1.5, rx=6)
    for cx in (bx0 + 0.45 * 2.54 * P / 2.54 * 1.5, bx0 + bw - 0.45 * 2.54 * P / 2.54 * 1.5):
        for cy in (by0 + 15, by0 + bh - 15):
            s.circle(cx, cy, 7, fill="#fff", stroke="#a88c55")
    for c in range(bd.COLS):
        if c % 5 == 0 or c == bd.COLS - 1:
            s.text(X(c), by0 - 8, c, 10, "middle", fill=MUTED)
    for r in range(bd.ROWS):
        if r % 5 == 0 or r == bd.ROWS - 1:
            s.text(bx0 - 8, Y(r) + 3.5, r, 10, "end", fill=MUTED)
    s.text(bx0 - 8, by0 - 8, "r\\c", 10, "end", fill=MUTED)
    for c in range(bd.COLS):
        for r in range(bd.ROWS):
            if bottom:
                s.circle(X(c), Y(r), 5.2, fill="#e6c27a", stroke=PAD, sw=0.8)
            s.circle(X(c), Y(r), 2.2, fill="#fff", stroke="#b49c6c", sw=0.6)

    if bottom:
        draw_underside(s, v, board)
    else:
        draw_parts(s, v, board)
    return s


def draw_parts(s, v, board):
    X, Y = v.X, v.Y
    # Modules first, as dashed outlines over the area they cover.
    for p in board.parts:
        if "body" in p:
            c0, r0, c1, r1 = p["body"]
            s.rect(X(c0), Y(r0), (c1 - c0) * P, (r1 - r0) * P, fill="#cfe3f7", stroke="#2a78d6", sw=1.4,
                   rx=6, dash="6 4", opacity=0.35)
            if p["kind"] == "esp32":
                cx, cy = X((c0 + c1) / 2), Y((r0 + r1) / 2)
                s.text(cx, cy - 4, p["value"], 13, "middle", "bold", fill="#1f5fae")
                s.text(cx, cy + 12, "plugs into its two headers", 10.5, "middle", fill="#1f5fae")
            else:   # title in the corner away from the header and its pin labels
                s.text(X(c1) - 8, Y(r1) - 22, p["value"], 12.5, "end", "bold", fill="#1f5fae")
                s.text(X(c1) - 8, Y(r1) - 8, "plugs into its header", 10, "end", fill="#1f5fae")
            if p["kind"] == "esp32":
                s.text(X(c0) + 6, cy + 30, "← USB end (overhangs the edge)", 10.5, fill="#1f5fae")
                s.text(X(c1) - 6, cy + 30, "antenna end", 10.5, "end", fill="#1f5fae")
    for p in board.parts:
        k = p["kind"]
        pins = p["pins"]
        if k in ("res", "cap", "diode", "led"):
            (l1, (c1, r1), _), (l2, (c2, r2), _) = pins
            x1, y1, x2, y2 = X(c1), Y(r1), X(c2), Y(r2)
            s.line(x1, y1, x2, y2, stroke="#9a9a9a", sw=1.6)
            s.circle(x1, y1, 3, fill="#bdbdbd", stroke="#7a7a7a", sw=0.8)
            s.circle(x2, y2, 3, fill="#bdbdbd", stroke="#7a7a7a", sw=0.8)
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            horiz = r1 == r2
            if k == "res":
                L, Wd = (2.75 * P, 0.66 * P)
                label = f"{p['ref']} {p['value']}"
                if horiz:
                    s.rect(mx - L / 2, my - Wd / 2, L, Wd, fill="#e3c18f", stroke="#8a6d3b", rx=5)
                    s.text(mx, my + 3.5, label, 9.5, "middle", "bold", fill="#4a3410")
                else:
                    s.rect(mx - Wd / 2, my - L / 2, Wd, L, fill="#e3c18f", stroke="#8a6d3b", rx=5)
                    s.text(mx + 3.5, my, label, 9.5, "middle", "bold", fill="#4a3410", rotate=-90)
            elif k == "cap":
                s.rect(mx - 7, my - 7, 14, 14, fill="#f2c14e", stroke="#a77d11", rx=7)
                s.text(mx + 10, my + 3, p["ref"], 9.5, fill=INK2)
            elif k == "diode":
                L = abs(x2 - x1) * 0.45
                s.rect(mx - L / 2, my - 6, L, 12, fill="#3a3a3a", stroke="#111", rx=3, dash="3 2")
                s.rect(mx + L / 2 - 6, my - 6, 4, 12, fill="#cfcfcf", stroke="none")
                s.text(mx, my - 9, f"{p['ref']} clamp (TBD)", 9.5, "middle", fill=INK2)
            elif k == "led":
                s.circle(mx, my, 9, fill="#e53935", stroke="#8e1b18")
                s.line(mx + 6, my - 7, mx + 6, my + 7, stroke="#8e1b18", sw=1.6)
                s.text(mx, my - 13, f"{p['ref']} (flat side = K)", 9.5, "middle", fill=INK2)
        elif k in ("header", "jst", "terminal", "module", "esp32"):
            xs = [X(c) for _, (c, r), _ in pins]
            ys = [Y(r) for _, (c, r), _ in pins]
            if k == "esp32":
                for row in (2, 12):
                    rowpins = [(l, h) for l, h, _ in pins if h[1] == row]
                    xa = min(X(h[0]) for _, h in rowpins)
                    xb = max(X(h[0]) for _, h in rowpins)
                    s.rect(min(xa, xb) - 0.45 * P, Y(row) - 0.45 * P, abs(xb - xa) + 0.9 * P, 0.9 * P,
                           fill="#262626", stroke="#000", rx=2)
                    for l, (c, r) in rowpins:
                        s.rect(X(c) - 3, Y(r) - 3, 6, 6, fill="#555", stroke="none")
                        dy = -0.62 * P if row == 2 else 0.62 * P + 8
                        net = next(n for ll, hh, n in pins if hh == (c, r))
                        col = INK if net != "NC" else MUTED
                        s.text(X(c), Y(r) + dy, l, 8.5, "middle", "bold" if net != "NC" else "normal",
                               fill=col, rotate=-60 if row == 2 else 60)
                s.text(X(-1.2), Y(7) + 4, "U1", 12, "end", "bold")
                continue
            pad = 0.45 * P
            x0, x1 = min(xs) - pad, max(xs) + pad
            y0, y1 = min(ys) - pad, max(ys) + pad
            fill = {"header": "#262626", "module": "#262626", "jst": "#f7f7f2", "terminal": "#2e7d32"}[k]
            stroke = {"jst": "#555"}.get(k, "#000")
            s.rect(x0, y0, x1 - x0, y1 - y0, fill=fill, stroke=stroke, rx=2)
            for l, (c, r), net in pins:
                if k == "terminal":
                    s.circle(X(c), Y(r), 6, fill="#cfd8dc", stroke="#455a64")
                    s.line(X(c) - 4, Y(r), X(c) + 4, Y(r), stroke="#455a64", sw=1.4)
                else:
                    s.rect(X(c) - 3, Y(r) - 3, 6, 6, fill="#777" if k != "jst" else "#c9a227", stroke="none")
            # Pin labels beside the connector, away from the board's middle.
            vertical = len({c for _, (c, _), _ in pins}) == 1
            for l, (c, r), net in pins:
                col = net_color(net) if net != "NC" else MUTED
                if vertical:
                    right = c >= bd.COLS / 2
                    s.text(X(c) + (pad + 4 if right else -pad - 4), Y(r) + 3.5, l, 9.5,
                           "start" if right else "end", "bold", fill=col)
                else:
                    s.text(X(c), y1 + 11, l, 8.5, "middle", "bold", fill=col, rotate=0)
            ref_x = (x0 + x1) / 2
            if k == "module" and not vertical:   # keep clear of the module title
                s.text(x0 - 6, y0 + 13, p["ref"], 11, "end", "bold")
            elif vertical:
                right = pins[0][1][0] >= bd.COLS / 2
                lx = x1 + 40 if right else x0 - 40
                s.text(lx, y0 - 6, p["ref"], 11, "middle", "bold")
            else:
                s.text(ref_x, y0 - 5, p["ref"], 11, "middle", "bold")


def jumper_path(v, a, b):
    """A gentle arc between two holes, so jumpers read as wires laid over the board."""
    x1, y1, x2, y2 = v.X(a[0]), v.Y(a[1]), v.X(b[0]), v.Y(b[1])
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    dx, dy = x2 - x1, y2 - y1
    L = math.hypot(dx, dy) or 1
    bow = min(28, 0.12 * L)
    cx, cy = mx - dy / L * bow, my + dx / L * bow
    return f"M{x1:.1f},{y1:.1f} Q{cx:.1f},{cy:.1f} {x2:.1f},{y2:.1f}", (0.25 * x1 + 0.5 * cx + 0.25 * x2,
                                                                        0.25 * y1 + 0.5 * cy + 0.25 * y2)


def draw_underside(s, v, board):
    X, Y = v.X, v.Y
    for net, holes in board.bare:
        col = net_color(net)
        d = "M" + " L".join(f"{X(c):.1f},{Y(r):.1f}" for c, r in holes)
        s.path(d, stroke=col, sw=6.5)
        s.path(d, stroke="#ffffff", sw=1.6, opacity=0.55)
        for c, r in holes:
            s.circle(X(c), Y(r), 4.2, fill=col, stroke="#fff", sw=0.8)
    for p, label, (c, r), net in board.pins():
        s.circle(X(c), Y(r), 4.6, fill="#b9b9b9", stroke="#6f6f6f", sw=1)
    for p in board.parts:
        cs = [h[0] for _, h, _ in p["pins"]]
        rs = [h[1] for _, h, _ in p["pins"]]
        if p["kind"] == "esp32":
            s.text((X(min(cs)) + X(max(cs))) / 2, Y(7) + 4, "U1 (ESP32 pins)", 11, "middle", fill=MUTED)
            continue
        s.text(X(sum(cs) / len(cs)), Y(min(rs)) - 7, p["ref"], 9, "middle", fill=MUTED)
    for net, a, b in board.jumpers:
        d, (lx, ly) = jumper_path(v, a, b)
        s.path(d, stroke="#ffffff", sw=6)
        s.path(d, stroke=net_color(net), sw=3.2)
        for h in (a, b):
            s.circle(X(h[0]), Y(h[1]), 4, fill=net_color(net), stroke="#fff", sw=1)
        s.text(lx, ly - 4, net, 9, "middle", "bold", fill=net_color(net))
    # Legend: one entry per colour, naming the nets that share it.
    groups = {}
    for n in sorted({n for n, _ in board.bare} | {n for n, _, _ in board.jumpers}):
        groups.setdefault(net_color(n), []).append(n)
    lx, ly = v.ml, v.H - 62
    s.text(lx, ly - 8, "Thick straight lines: bare tinned wire soldered at every pad it crosses. "
           "Curved lines: insulated wire between two pads. Grey dots: component leads.", 11, fill=INK2)
    x = lx
    for col, names in groups.items():
        label = names[0] if len(names) == 1 else f"{names[0]} to {names[-1]}"
        if names[0].startswith("NTC") and len(names) > 1:
            label = "NTC1 to NTC5"
        s.line(x, ly + 10, x + 22, ly + 10, stroke=col, sw=6)
        s.text(x + 27, ly + 14, label, 11, fill=INK)
        x += 40 + 6.6 * len(label)
        if x > v.W - 160:
            x, ly = lx, ly + 22


# ============================================================================================
# Single-line diagram of the power path.

def sld():
    s = Svg(1180, 640)
    s.text(30, 32, "Single-line diagram: power path and auxiliary supply", 18, weight="bold")
    s.text(30, 52, "Architecture sections 3 and 4. One line stands for the positive and negative "
           "conductors together; the relay contacts switch the negative (P−) side.", 12, fill=INK2)
    y = 170
    end = battery(s, 40, y)
    s.text(30, y + 40, "4S1P NCR18650GA", 11, weight="bold")
    s.text(30, y + 55, "14.4 V nominal, 16.8 V max", 10.5, fill=INK2)
    s.text(30, y + 69, "3.3 Ah (label)", 10.5, fill=INK2)
    box(s, end, y - 52, 130, 104, "Hardware BMS", ["layer A, 4S NMC", "OV 4.25 V · UV 2.7 V", "short circuit", "balance 30 mA"])
    s.text(end + 65, y + 70, "B−, B1, B2, B3, B+ in", 10, "middle", fill=INK2)
    x = end + 130
    s.line(x, y, x + 20, y)
    s.text(x + 4, y - 8, "P+", 11, weight="bold")
    fuse(s, x + 20, y, x + 110, "F1", "7.5 A blade fuse at B+")
    xn = x + 125
    s.line(x + 110, y, xn, y)
    dot(s, xn, y)
    s.text(xn, y - 10, "X", 11, "middle", weight="bold")
    # shunt with ammeter
    resistor(s, xn, y, xn + 110, y, "R_SH", "5 mΩ 3 W, Kelvin")
    s.circle(xn + 55, y + 48, 13, fill="#fff")
    s.text(xn + 55, y + 52.5, "A", 12, "middle", "bold")
    s.line(xn + 45, y + 6, xn + 48, y + 37, sw=1, dash="3 2")
    s.line(xn + 65, y + 6, xn + 62, y + 37, sw=1, dash="3 2")
    s.text(xn + 55, y + 78, "INA226 (I and V)", 10, "middle", fill=INK2)
    xb = xn + 150
    s.line(xn + 110, y, xb, y)
    s.line(xb, y - 90, xb, y + 90, sw=5)
    s.text(xb, y - 98, "FUSED+", 11, "middle", "bold")
    # load feeder
    yl, yc = y - 70, y + 70
    s.line(xb, yl, xb + 40, yl)
    contact_no(s, xb + 40, yl, xb + 120, "K_LOAD (NO)")
    s.line(xb + 120, yl, xb + 160, yl)
    box(s, xb + 160, yl - 30, 190, 60, "Load, via XT60", ["5 A continuous (5.0 A trip)", "LOAD+ / LOAD−"])
    s.line(xb, yc, xb + 40, yc)
    contact_no(s, xb + 40, yc, xb + 120, "K_CHARGE (NO)")
    s.line(xb + 120, yc, xb + 160, yc)
    box(s, xb + 160, yc - 30, 190, 60, "Charger 16.8 V CC/CV", ["isolated, 1.5 A max", "CHARGE+ / CHARGE−"])
    # auxiliary supply from X
    ya = 330
    s.line(xn, y, xn, ya)
    box(s, xn - 70, ya, 140, 70, "LM2596", ["DC/DC buck", "set to 5.00 V"])
    s.text(xn + 8, ya - 12, "fused, before the shunt", 10, fill=INK2)
    s.line(xn, ya + 70, xn, ya + 110)
    s.line(xn - 260, ya + 110, xn + 300, ya + 110, sw=4, stroke="#e07b00")
    s.text(xn + 304, ya + 114, "5 V auxiliary", 11, weight="bold", fill="#e07b00")
    for k, (t, lines) in enumerate([
            ("ESP32 DevKit", ["VIN 5 V; makes 3.3 V", "for the sensors"]),
            ("Relay module", ["2 coils, 5 V", "contacts in the feeders"]),
            ("Buzzer + LED", ["latched alarm", "GPIO27"])]):
        bx = xn - 250 + k * 190
        s.line(bx + 80, ya + 110, bx + 80, ya + 140)
        box(s, bx, ya + 140, 160, 64, t, lines)
    # notes
    notes = [
        "Ratings: 5 A continuous discharge, 1.5 A charge; 16 AWG for the power path, 22 AWG for sense wires.",
        "Charge and load are never used at the same time in the prototype (one current monitor serves both).",
        "The LM2596 takes P−, so a hardware BMS cut-off also removes controller power (section 4).",
        "Feeding it before the shunt keeps its own current out of the measurement, so the pack can read 'at rest'.",
    ]
    for k, n in enumerate(notes):
        s.text(30, 560 + 18 * k, "• " + n, 11.5, fill=INK2)
    s.save("sld.svg")


# ============================================================================================
# Circuit diagrams.

def schematic_taps():
    s = Svg(1180, 760)
    s.text(30, 32, "Circuit: cell-tap voltage sensing (board A, architecture section 5)", 18, weight="bold")
    s.text(30, 52, "Four identical channels. Divider ratio about 0.145: 16.8 V at B+ becomes 2.44 V at the ADC. "
           "Each channel is calibrated at Gate 1.", 12, fill=INK2)
    taps = [("B1", "4.2 V", "A0"), ("B2", "8.4 V", "A1"), ("B3", "12.6 V", "A2"), ("B+", "16.8 V", "A3")]
    s.add('<g transform="translate(36,0)">')
    # pack side
    s.text(40, 92, "Pack taps", 12, weight="bold")
    x_ads = 880
    for k, (tap, vmax, a) in enumerate(taps):
        y = 130 + 140 * k
        s.circle(60, y, 5, fill="#fff")
        s.text(48, y + 4, tap, 12, "end", "bold")
        s.text(48, y + 18, vmax + " max", 10, "end", fill=INK2)
        resistor(s, 65, y, 185, y, "R_entry", "1–10 kΩ at the pack")
        s.line(185, y, 215, y)
        s.circle(215, y, 4, fill="#fff")
        s.text(215, y - 10, f"J1-{k + 2}", 10, "middle", fill=INK2)
        resistor(s, 219, y, 380, y, f"R{k + 1}", "330 kΩ 1 %")
        dot(s, 400, y)
        s.line(380, y, 400, y)
        resistor(s, 400, y, 400, y + 80, f"R{k + 9}", "56 kΩ 1 %")
        ground(s, 400, y + 80)
        resistor(s, 400, y, 560, y, f"R{k + 5}", "10 kΩ")
        dot(s, 600, y)
        s.line(560, y, 600, y)
        capacitor(s, 600, y, y + 80, f"C{k + 1}", "100 nF")
        ground(s, 600, y + 80)
        diode(s, 600, y - 40, 720, f"D{k + 1}", "low-leakage clamp, TBD", dashed=True)
        s.line(600, y, 600, y - 40)
        rail(s, 720, y - 40, "3V3")
        s.line(600, y, x_ads, y)
        s.text(x_ads - 6, y - 6, a, 11, "end", "bold")
    # ADS1115 block
    s.add("</g>")
    x_ads += 36
    box(s, x_ads, 90, 200, 560, "ADS1115", ["16-bit, ±4.096 V range", "128 samples/s, single-shot", "", "", "", "",
                                             "VDD → 3V3", "GND → GND", "ADDR → GND (0x48)", "SCL → GPIO22", "SDA → GPIO21",
                                             "ALRT not used"], fill="#eef4fb", stroke="#2a78d6")
    s.text(40, 700, "Ground: the 56 kΩ legs and the ADS1115 share the electronics ground (P−). J1 pin 1 (B−) is left "
           "unconnected: joining B− to this ground would bypass the hardware BMS switch.", 11.5, fill=INK2)
    s.text(40, 720, "Cell voltages are differences of taps: V1 = A0, V2 = A1 − A0, V3 = A2 − A1, V4 = A3 − A2 "
           "(after calibration).", 11.5, fill=INK2)
    s.save("circuit-taps.svg")


def schematic_ntc_current():
    s = Svg(1180, 640)
    s.text(30, 32, "Circuit: temperatures and current (board B, architecture sections 4 and 6)", 18, weight="bold")
    # NTC divider
    s.text(40, 80, "Five NTC dividers (NTC1–4 on the cells, NTC5 in the air)", 13, weight="bold")
    x = 120
    rail(s, x, 120, "3V3")
    resistor(s, x, 120, x, 220, "R1–R5", "10 kΩ 1 %")
    dot(s, x, 220)
    ntc_symbol(s, x, 220, 330, "NTC 10k B3950")
    ground(s, x, 330)
    s.line(x, 220, x + 110, 220)
    dot(s, x + 110, 220)
    capacitor(s, x + 110, 220, 300, "C1–C5", "100 nF")
    ground(s, x + 110, 300)
    s.line(x + 110, 220, x + 230, 220)
    s.text(x + 236, 224, "to ESP32 ADC1", 11, weight="bold")
    rows = [("NTC1", "cell 1", "GPIO32", "ADC1_CH4"), ("NTC2", "cell 2", "GPIO33", "ADC1_CH5"),
            ("NTC3", "cell 3", "GPIO34", "ADC1_CH6"), ("NTC4", "cell 4", "GPIO35", "ADC1_CH7"),
            ("NTC5", "air", "GPIO36 (VP)", "ADC1_CH0")]
    tx, ty = 470, 120
    s.text(tx, ty - 22, "Sensor", 11, weight="bold")
    s.text(tx + 90, ty - 22, "Where", 11, weight="bold")
    s.text(tx + 170, ty - 22, "Pin", 11, weight="bold")
    s.text(tx + 290, ty - 22, "Channel", 11, weight="bold")
    for k, (a, b, c, d) in enumerate(rows):
        yy = ty + 20 * k
        for off, t in zip((0, 90, 170, 290), (a, b, c, d)):
            s.text(tx + off, yy, t, 11, fill=INK if off == 0 else INK2)
    s.text(tx, ty + 120, "ADC1 only: ADC2 does not work while Wi-Fi is on. At 25 °C the node sits at 1.65 V.",
           11, fill=INK2)
    s.text(tx, ty + 138, "Bond NTC1–4 at mid-can with insulating, thermally conductive tape; never on nickel.",
           11, fill=INK2)
    # current
    y0 = 420
    s.text(40, y0 - 30, "Pack current: 5 mΩ shunt with Kelvin sense, INA226", 13, weight="bold")
    s.line(60, y0, 120, y0, sw=3)
    s.text(60, y0 - 8, "from F1 (X)", 10.5, fill=INK2)
    s.line(120, y0, 200, y0, sw=3)
    s.rect(200, y0 - 10, 120, 20, fill="#fff", sw=1.6)
    s.text(260, y0 + 4, "R_SH 5 mΩ", 10.5, "middle", "bold")
    s.line(320, y0, 440, y0, sw=3)
    s.text(440, y0 - 8, "FUSED+ to the feeders", 10.5, "end", fill=INK2)
    s.line(205, y0 + 10, 205, y0 + 70, stroke="#00897b", sw=1.6)
    s.line(315, y0 + 10, 315, y0 + 70, stroke="#00695c", sw=1.6)
    s.text(198, y0 + 50, "IN+", 10.5, "end", "bold", fill="#00897b")
    s.text(322, y0 + 50, "IN−", 10.5, weight="bold", fill="#00695c")
    box(s, 160, y0 + 70, 200, 110, "INA226", ["IN+ / IN− across the shunt only", "VBS joined to IN−",
                                              "VCC 3V3 · GND", "SCL GPIO22 · SDA GPIO21", "address 0x40 (A0, A1 to GND)"],
        fill="#eef4fb", stroke="#2a78d6")
    notes = ["Remove or bypass the module's own R100 shunt (BOM item 12).",
             "Twist the two sense leads; take them from the shunt's own pads (Kelvin).",
             "At 5 A the shunt drops 25 mV and dissipates 0.125 W.",
             "Positive current = discharge (IN+ on the fuse side)."]
    for k, n in enumerate(notes):
        s.text(470, y0 + 20 + 20 * k, "• " + n, 11.5, fill=INK2)
    s.save("circuit-ntc-current.svg")


def schematic_control():
    s = Svg(1180, 700)
    s.text(30, 32, "Circuit: ESP32 control, relays and alarm (board B, architecture section 7)", 18, weight="bold")
    box(s, 420, 80, 260, 420, "ESP32 DevKit V1", [], fill="#eef4fb", stroke="#2a78d6", title_size=13)
    left = [("GPIO25", "K_LOAD", 140), ("GPIO26", "K_CHARGE", 220), ("GPIO27", "alarm", 330), ("GPIO0 (BOOT)", "reset 3 s", 430)]
    for pin, what, y in left:
        s.line(380, y, 420, y)
        s.text(426, y + 4, pin, 11, weight="bold")
    right = [("VIN", 120), ("GND", 160), ("3V3 out", 200), ("GPIO21 SDA", 280), ("GPIO22 SCL", 310),
             ("GPIO32–36", 380)]
    for pin, y in right:
        s.line(680, y, 720, y)
        s.text(674, y + 4, pin, 11, "end", "bold")
    s.text(726, 124, "5 V from the LM2596 (J4)", 11, fill=INK2)
    s.text(726, 164, "electronics ground (P−)", 11, fill=INK2)
    s.text(726, 204, "ADS1115, INA226, pull-ups, NTC dividers", 11, fill=INK2)
    s.text(726, 284, "ADS1115 and INA226 (I2C)", 11, fill=INK2)
    s.text(726, 314, "", 11, fill=INK2)
    s.text(726, 384, "NTC1–NTC5 dividers", 11, fill=INK2)
    # relay inputs with pull-ups
    for k, (pin, what, y) in enumerate(left[:2]):
        dot(s, 330, y)
        s.line(330, y, 380, y)
        resistor(s, 330, y, 330, y - 60 if k == 0 else y - 40, f"R{6 + k}", "10 kΩ", side=-1)
        rail(s, 330, y - 60 if k == 0 else y - 40, "3V3")
        s.line(160, y, 330, y)
        s.text(150, y + 4, f"relay IN{k + 1} ({what})", 11, "end", "bold")
    box(s, 40, 530, 170, 64, "Relay module", ["2 × 5 V inputs, active LOW", "VCC 5 V · GND"])
    s.text(226, 556, "LOW closes a contact. HIGH or floating leaves it open, so reset,", 11, fill=INK2)
    s.text(226, 572, "a crash or an unpowered ESP32 leave both branches open.", 11, fill=INK2)
    # alarm
    y = 330
    s.line(200, y, 380, y)
    dot(s, 300, y)
    s.text(196, y + 4, "buzzer module I/O", 11, "end", "bold")
    resistor(s, 300, y, 300, y + 70, "R8", "330 Ω", side=-1)
    s.line(300, y + 70, 300, y + 80)
    s.poly([(290, y + 80), (310, y + 80), (300, y + 96)], fill="#fff", close=True)
    s.line(290, y + 97, 310, y + 97, sw=2)
    s.text(316, y + 92, "LED1 red", 11, weight="bold")
    s.line(300, y + 97, 300, y + 110)
    ground(s, 300, y + 110)
    s.text(700, 440, "LED current ≈ (3.3 V − LED voltage) / R8:", 11, fill=INK2)
    s.text(700, 456, "about 4 mA with a 2 V red LED.", 11, fill=INK2)
    s.text(700, 480, "Set CONFIG_BMS_ALARM_ACTIVE_LOW if the buzzer", 11, fill=INK2)
    s.text(700, 496, "module sounds on LOW (check at Gate 2).", 11, fill=INK2)
    s.text(40, 630, "Steady alarm = latched trip. Pulsing at 1 Hz = risk level Warning.", 12, weight="bold")
    s.text(40, 650, "Check at Gate 2 that a 3.3 V HIGH fully releases each 5 V relay input; if not, add a "
           "transistor stage (section 7).", 11, fill=INK2)
    s.save("circuit-control.svg")


# ============================================================================================
# Wiring overview, enclosure, module pinouts.

def wiring_overview():
    s = Svg(1240, 860)
    s.text(30, 32, "Wiring: every connection between the units", 18, weight="bold")
    s.text(30, 52, "Thick lines: 16 AWG power (red +, black −). Thin lines: 22 AWG signals. Connector names as on "
           "the board drawings.", 12, fill=INK2)
    # pack
    box(s, 30, 90, 260, 300, "Pack 4S1P", ["welded nickel, spacers, sleeve"], fill="#fdf2e9")
    for k in range(4):
        cx = 60 + k * 58
        s.rect(cx, 150, 44, 150, fill="#fbe3d6", stroke="#8a6d3b", rx=8)
        s.text(cx + 22, 230, f"C{k + 1}", 12, "middle", "bold")
        s.circle(cx + 22, 260, 5, fill="#0f8a8a", stroke="#0f8a8a")
    s.text(160, 320, "NTC1–4 at mid-can (teal dots)", 10.5, "middle", fill=INK2)
    s.text(160, 340, "taps B−, B1, B2, B3, B+", 10.5, "middle", fill=INK2)
    # BMS
    box(s, 340, 110, 150, 120, "Hardware BMS", ["B−, B+ power", "5-pin balance lead", "P+ / P− out"])
    s.line(290, 160, 340, 160, stroke="#d03b3b", sw=5)
    s.line(290, 200, 340, 200, stroke="#222", sw=5)
    s.text(300, 152, "B+", 10, weight="bold")
    s.text(300, 216, "B−", 10, weight="bold")
    s.line(290, 260, 330, 260, stroke="#6a3fd0", sw=2)
    s.line(330, 260, 330, 225, stroke="#6a3fd0", sw=2)
    s.text(296, 276, "balance", 10, fill="#6a3fd0")
    # fuse, shunt
    box(s, 540, 110, 110, 56, "F1 7.5 A", ["at the B+ exit"])
    box(s, 700, 110, 120, 56, "Shunt 5 mΩ", ["Kelvin pads"])
    s.line(490, 138, 540, 138, stroke="#d03b3b", sw=5)
    s.line(650, 138, 700, 138, stroke="#d03b3b", sw=5)
    s.text(495, 130, "P+", 10, weight="bold")
    # feeders
    box(s, 900, 90, 150, 56, "XT60 load", ["LOAD+ / LOAD−"])
    box(s, 900, 190, 150, 56, "Charge plug", ["CHARGE+ / CHARGE−"])
    s.line(820, 138, 860, 138, stroke="#d03b3b", sw=5)
    s.line(860, 118, 860, 218, stroke="#d03b3b", sw=5)
    s.line(860, 118, 900, 118, stroke="#d03b3b", sw=5)
    s.line(860, 218, 900, 218, stroke="#d03b3b", sw=5)
    s.text(864, 112, "FUSED+", 10, weight="bold")
    box(s, 900, 300, 170, 100, "Relay module", ["K_LOAD: COM P−, NO LOAD−", "K_CHARGE: COM P−, NO CHARGE−",
                                                 "inputs: GND IN1 IN2 VCC"])
    s.line(490, 200, 520, 200, stroke="#222", sw=5)
    s.line(520, 200, 520, 388, stroke="#222", sw=5)
    s.line(520, 388, 900, 388, stroke="#222", sw=5)
    s.text(526, 382, "P−", 10, weight="bold")
    s.line(1070, 320, 1110, 320, stroke="#222", sw=5)
    s.line(1110, 320, 1110, 128, stroke="#222", sw=5)
    s.line(1110, 128, 1050, 128, stroke="#222", sw=5)
    s.line(1070, 370, 1130, 370, stroke="#222", sw=5)
    s.line(1130, 370, 1130, 228, stroke="#222", sw=5)
    s.line(1130, 228, 1050, 228, stroke="#222", sw=5)
    s.text(1116, 300, "LOAD−", 10, weight="bold")
    s.text(1136, 400, "CHARGE−", 10, weight="bold")
    # LM2596
    box(s, 560, 230, 140, 70, "LM2596", ["set 5.00 V first"])
    s.line(595, 166, 595, 230, stroke="#d03b3b", sw=2.5)
    s.text(600, 200, "from F1/shunt junction", 9.5, fill=INK2)
    s.line(620, 300, 620, 388, stroke="#222", sw=2.5)
    s.text(626, 330, "P−", 9.5, fill=INK2)
    # boards
    box(s, 340, 470, 260, 200, "Board A: taps + ADS1115", ["J1 tap harness in", "J2 ADS1115 module", "J3 link to board B"],
        fill="#f4f0fb", stroke="#6a3fd0")
    box(s, 700, 470, 340, 260, "Board B: ESP32", ["J4 5 V in · J5 relays · J6 buzzer", "J7 link to board A",
                                                   "J8 INA226 module · J14 shunt sense", "J9–J12 NTC1–4 · J13 NTC5 (air)"],
        fill="#eef4fb", stroke="#2a78d6")
    # tap harness
    s.path("M200,345 C200,420 300,560 340,560", stroke="#6a3fd0", sw=2.2)
    s.text(205, 430, "tap harness: 5 wires, 1–10 kΩ", 10.5, fill="#6a3fd0", weight="bold")
    s.text(205, 444, "at the pack end of each tap", 10.5, fill="#6a3fd0")
    # NTC wires
    s.path("M80,300 C80,700 500,760 760,730", stroke="#0f8a8a", sw=2, dash="6 3")
    s.text(90, 640, "NTC1–4: twisted pairs to J9–J12", 10.5, fill="#0f8a8a", weight="bold")
    # link A-B
    s.line(600, 600, 700, 600, stroke="#2a78d6", sw=2.2)
    s.text(650, 592, "J3 ↔ J7", 10, "middle", weight="bold", fill="#2a78d6")
    s.text(650, 616, "3V3 GND SCL SDA", 9.5, "middle", fill=INK2)
    # shunt sense
    s.path("M760,166 C760,300 800,400 820,470", stroke="#00897b", sw=2)
    s.text(770, 420, "Kelvin pair to J14", 10.5, fill="#00897b", weight="bold")
    # 5V to board B
    s.path("M680,300 C700,380 720,420 720,470", stroke="#e07b00", sw=2.5)
    s.text(728, 440, "5 V to J4", 10.5, fill="#e07b00", weight="bold")
    # relay inputs
    s.path("M1040,520 C1100,500 1100,420 1000,400", stroke="#c2185b", sw=2)
    s.text(1050, 470, "J5 → relay inputs", 10.5, fill="#c2185b", weight="bold")
    # buzzer
    box(s, 1080, 600, 130, 56, "Buzzer + LED", ["J6"])
    s.line(1040, 628, 1080, 628, stroke="#6d4c41", sw=2)
    # NTC5
    s.circle(1160, 760, 7, fill="#0f8a8a", stroke="#0f8a8a")
    s.text(1150, 790, "NTC5 in the vent air → J13", 10.5, "end", fill="#0f8a8a", weight="bold")
    s.line(1040, 700, 1160, 752, stroke="#0f8a8a", sw=2, dash="6 3")
    s.text(30, 820, "Never hot-plug an unchecked tap harness: measure every adjacent pin first (one cell voltage each, "
           "rising in order). Connect B− first (section 10).", 11.5, fill=INK2)
    s.save("wiring-overview.svg")


def enclosure():
    s = Svg(1100, 600)
    s.text(30, 32, "Enclosure layout (top view, lid removed)", 18, weight="bold")
    s.text(30, 52, "Vented PETG case (section 2 and 11). Not a fire enclosure: never seal it.", 12, fill=INK2)
    s.rect(40, 80, 1020, 460, fill="#f7f6f2", stroke=INK, sw=2, rx=14)
    s.rect(60, 100, 420, 200, fill="#fdf2e9", stroke="#8a6d3b", rx=10)
    s.text(270, 130, "Pack bay", 14, "middle", "bold")
    s.text(270, 150, "4S1P in spacers, fish paper, sleeve", 11, "middle", fill=INK2)
    for k in range(4):
        s.rect(90 + k * 95, 170, 70, 110, fill="#fbe3d6", stroke="#8a6d3b", rx=12)
        s.text(125 + k * 95, 230, f"C{k + 1}", 12, "middle", "bold")
    s.rect(60, 320, 420, 200, fill="#fbeaea", stroke="#d03b3b", rx=10, dash="6 4")
    s.text(270, 350, "Power side", 14, "middle", "bold", fill="#b02a2a")
    for k, t in enumerate(["Hardware BMS on insulated standoffs", "F1 fuse holder at the B+ exit (access hatch)",
                           "Shunt, then the branch wiring", "Relay module: contacts away from the sensing",
                           "LM2596", "XT60 load and charge plugs in cable glands"]):
        s.text(80, 380 + 22 * k, "• " + t, 11.5, fill=INK2)
    s.rect(520, 100, 520, 300, fill="#eef4fb", stroke="#2a78d6", rx=10, dash="6 4")
    s.text(780, 130, "Sensing side (removable electronics lid)", 14, "middle", "bold", fill="#1f5fae")
    s.rect(550, 160, 210, 160, fill="#f4f0fb", stroke="#6a3fd0", rx=6)
    s.text(655, 245, "Board A", 13, "middle", "bold")
    s.rect(790, 160, 230, 160, fill="#e3eefa", stroke="#2a78d6", rx=6)
    s.text(905, 245, "Board B (ESP32)", 13, "middle", "bold")
    s.text(780, 350, "USB of the ESP32 reachable through a slot for the console", 11, "middle", fill=INK2)
    s.text(780, 370, "Tap and NTC wires restrained, away from relay and power wiring", 11, "middle", fill=INK2)
    s.rect(520, 420, 520, 100, fill="#f0f7f0", stroke="#2e7d32", rx=10, dash="6 4")
    s.text(780, 450, "Vent path", 14, "middle", "bold", fill="#2e7d32")
    s.circle(940, 480, 9, fill="#0f8a8a", stroke="#0f8a8a")
    s.text(925, 485, "NTC5 in free air here, away from cells, LM2596, relays", 11, "end", fill=INK2)
    for k in range(10):
        s.rect(560 + k * 30, 500, 18, 8, fill="#cfd8cf", stroke="#2e7d32", sw=0.8)
    s.text(40, 570, "Metal fasteners never near a cell can · strain relief on every cable · labels: B−, B1, B2, B3, B+, "
           "P−, P+, LOAD−, CHARGE−, fuse rating.", 11.5, fill=INK2)
    s.save("enclosure.svg")


def module_pinouts():
    s = Svg(1200, 760)
    s.text(30, 32, "Module pin orders assumed by the board drawings", 18, weight="bold")
    s.text(30, 52, "Generic modules differ. Check the printing on each module against these before soldering "
           "its header, and move the header if yours differs.", 12, fill=INK2)
    # ESP32
    x0, y0 = 40, 90
    s.rect(x0, y0, 400, 140, fill="#eef4fb", stroke="#2a78d6", rx=8)
    s.text(x0 + 200, y0 + 75, "ESP32 DevKit V1, 30 pins (top view)", 12, "middle", "bold")
    s.rect(x0 - 26, y0 + 50, 26, 40, fill="#bbb", stroke="#777")
    s.text(x0 - 30, y0 + 105, "USB", 10, "end", fill=INK2)
    used = {"VIN", "GND", "D27", "D26", "D25", "D33", "D32", "D35", "D34", "VP", "3V3", "D21", "D22"}
    for i, n in enumerate(bd.ESP_TOP):
        x = x0 + 18 + i * 26
        s.circle(x, y0 + 14, 5, fill="#2a78d6" if n in used else "#fff", stroke="#2a78d6")
        s.text(x, y0 - 4, n, 9, "middle", "bold" if n in used else "normal", fill=INK if n in used else MUTED,
               rotate=-50)
    for i, n in enumerate(bd.ESP_BOTTOM):
        x = x0 + 18 + i * 26
        s.circle(x, y0 + 126, 5, fill="#2a78d6" if n in used else "#fff", stroke="#2a78d6")
        s.text(x, y0 + 152, n, 9, "middle", "bold" if n in used else "normal", fill=INK if n in used else MUTED,
               rotate=50)
    s.text(x0, y0 + 200, "Filled pins are used. The two rows are usually 25.4 mm (10 holes) apart.", 11, fill=INK2)
    # small modules
    def row_module(x, y, title, pins, note):
        w = 40 + 34 * len(pins)
        s.rect(x, y, w, 70, fill="#f6f4ee", stroke=INK, rx=6)
        s.text(x + w / 2, y + 26, title, 12, "middle", "bold")
        s.text(x + w / 2, y + 44, note, 10, "middle", fill=INK2)
        for i, n in enumerate(pins):
            px = x + 20 + 34 * i + 17
            s.circle(px, y + 70, 5, fill="#fff", stroke=INK)
            s.text(px, y + 92, n, 10, "middle", "bold")
    row_module(520, 100, "ADS1115", ["VDD", "GND", "SCL", "SDA", "ADDR", "ALRT", "A0", "A1", "A2", "A3"],
               "board A, J2 (1 × 10)")
    row_module(520, 230, "INA226", ["VBS", "IN−", "IN+", "ALE", "SDA", "SCL", "GND", "VCC"],
               "board B, J8 (1 × 8); remove its R100 shunt")
    row_module(40, 360, "Relay module, inputs", ["GND", "IN1", "IN2", "VCC"], "board B, J5")
    row_module(300, 360, "Buzzer module", ["VCC", "I/O", "GND"], "board B, J6")
    row_module(520, 360, "LM2596", ["IN+", "IN−", "OUT+", "OUT−"], "set 5.00 V with no load first")
    s.rect(820, 360, 330, 120, fill="#f6f4ee", stroke=INK, rx=6)
    s.text(985, 386, "Relay contacts (each channel)", 12, "middle", "bold")
    for i, n in enumerate(["NO", "COM", "NC"]):
        s.rect(860 + i * 90, 410, 60, 34, fill="#2e7d32", stroke="#1b5e20", rx=4)
        s.text(890 + i * 90, 432, n, 12, "middle", "bold", fill="#fff")
    s.text(985, 465, "use COM and NO only; NC stays empty", 10.5, "middle", fill=INK2)
    s.text(40, 540, "Connectors on the boards", 13, weight="bold")
    rows = [("J1 (A)", "JST-XH 5-pin", "B−, B1, B2, B3, B+ (pin 1 = B−, not connected on the board)"),
            ("J3 (A) ↔ J7 (B)", "4-pin headers", "3V3, GND, SCL, SDA: a 4-wire cable, same order both ends"),
            ("J4 (B)", "2-pin screw terminal", "+5V, GND from the LM2596"),
            ("J9–J13 (B)", "JST-XH 2-pin", "T (signal), G (ground) for NTC1–NTC5"),
            ("J14 (B)", "2-pin header", "IN−, IN+ Kelvin pair from the shunt")]
    for k, (a, b, c) in enumerate(rows):
        y = 568 + 22 * k
        s.text(40, y, a, 11, weight="bold")
        s.text(200, y, b, 11, fill=INK2)
        s.text(380, y, c, 11, fill=INK2)
    s.save("module-pinouts.svg")


def firmware_flow():
    s = Svg(1200, 600)
    s.text(30, 32, "How the supervisor decides: one 5 Hz sample (safety task, ESP32 core 1)", 18, weight="bold")
    s.text(30, 52, "Every block is in firmware/components/bms_core and runs unchanged in the simulator. "
           "Wi-Fi and the dashboard only read a copy; nothing safe waits for them.", 12, fill=INK2)

    def arrow(x1, y1, x2, y2, dash=None):
        s.line(x1, y1, x2, y2, sw=1.6, dash=dash)
        a = math.atan2(y2 - y1, x2 - x1)
        s.poly([(x2, y2), (x2 - 9 * math.cos(a - 0.4), y2 - 9 * math.sin(a - 0.4)),
                (x2 - 9 * math.cos(a + 0.4), y2 - 9 * math.sin(a + 0.4))], fill=INK, close=True, sw=1)

    blue, green, warm, red = "#eef4fb", "#eaf6ef", "#fdf2e9", "#fdeceb"
    box(s, 30, 80, 190, 96, "Sensors", ["ADS1115: 4 taps", "INA226: pack current", "ADC1: 5 NTCs"], fill=blue)
    box(s, 260, 80, 230, 96, "Front end (sections 5, 6, 8)", ["calibration · plausibility", "median of 5 · 10 s low-pass",
                                                              "dT/dt over 30 s"], fill=blue)
    box(s, 530, 80, 230, 96, "Fixed limits (section 8)", ["V, I, temperature, spread,", "rate of rise; persistence,",
                                                          "hysteresis"], fill=warm)
    box(s, 260, 220, 230, 110, "Thermal model + Kalman", ["per cell, 9.1 and 9.2:", "core temperature T_c,",
                                                           "abnormal heat Q_ab (W),", "cell vs the other three"], fill=green)
    box(s, 530, 220, 230, 110, "Predict and confirm (9.3)", ["forecast 1 and 5 min ahead,", "check each when due,",
                                                              "RMS accuracy record"], fill=green)
    box(s, 800, 220, 220, 110, "Forecasts (9.6)", ["settling temperature,", "time to limit,", "safe continuous current"],
        fill=green)
    box(s, 260, 370, 230, 96, "Electrical evidence", ["online resistance (9.4)", "rest leak estimate (9.5)",
                                                      "energy cross-check"], fill=green)
    box(s, 530, 370, 230, 110, "Risk level (9.7, 9.8)", ["Normal → Watch → Warning → Trip", "thermal + electrical must agree",
                                                          "for a soft fault; self-", "acceleration trips at once"], fill=warm)
    box(s, 830, 80, 330, 110, "Latch and outputs", ["K_LOAD, K_CHARGE: each trip opens", "its own branch, or both",
                                                     "latched in flash; manual reset only", "alarm: steady trip, 1 Hz Warning"], fill=red)
    box(s, 830, 400, 330, 80, "Telemetry (not safety)", ["dashboard JSON once a second", "CSV log for the Gate 9 fit"],
        fill="#f6f4ee", dash="6 4")
    arrow(220, 128, 260, 128)
    arrow(490, 128, 530, 128)
    arrow(760, 128, 830, 128)
    arrow(375, 176, 375, 220)
    arrow(490, 275, 530, 275)
    arrow(760, 275, 800, 275)
    s.poly([(262, 168), (243, 168), (243, 418)], sw=1.6)   # front end to electrical evidence
    arrow(243, 418, 260, 418)
    arrow(645, 330, 645, 370)
    arrow(490, 418, 530, 418)
    arrow(910, 330, 760, 400)
    s.poly([(760, 440), (786, 440), (786, 172)], sw=1.6)   # risk level to the latch, between the boxes
    arrow(786, 172, 830, 172)
    arrow(760, 450, 830, 440, dash="5 4")
    s.text(30, 520, "Hardware BMS (layer A) acts on its own, below all of this: over- and under-voltage, short circuit, "
           "balancing.", 12, fill=INK2)
    s.text(30, 540, "Watchdog: if this task stops for 2 s the ESP32 restarts, both relays open, and the restart itself "
           "is latched (section 10).", 12, fill=INK2)
    s.save("firmware-flow.svg")


def all_figures():
    for make in bd.BOARDS:
        b = make()
        bd.check(b)
        draw_board(b, False).save(f"board-{b.name.lower()}-top.svg")
        draw_board(b, True).save(f"board-{b.name.lower()}-bottom.svg")
    sld()
    schematic_taps()
    schematic_ntc_current()
    schematic_control()
    wiring_overview()
    enclosure()
    module_pinouts()
    firmware_flow()


if __name__ == "__main__":
    all_figures()
    print("figures written to", OUT)
