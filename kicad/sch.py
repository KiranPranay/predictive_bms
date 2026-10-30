"""A small writer for KiCad schematics (.kicad_sch), used by make_schematics.py.

Symbols are copied from KiCad's own libraries, so every schematic uses the standard KiCad
symbols and simulation fields. Coordinates are in millimetres on KiCad's 1.27 mm grid; y grows
downwards, as on the KiCad page.
"""

import json
import math
import os
import pathlib
import re
import uuid


# Where KiCad keeps its symbol libraries: a Flatpak install (per user or system), a normal Linux
# install, or the folder named by KICAD_SYMBOL_DIR (KiCad sets KICAD10_SYMBOL_DIR on Windows).
SYMBOL_DIRS = [
    os.environ.get("KICAD_SYMBOL_DIR", ""),
    os.environ.get("KICAD10_SYMBOL_DIR", ""),
    str(pathlib.Path.home() / ".local/share/flatpak/runtime/org.kicad.KiCad.Library.Symbols/x86_64/stable/active/files/symbols"),
    "/var/lib/flatpak/runtime/org.kicad.KiCad.Library.Symbols/x86_64/stable/active/files/symbols",
    "/usr/share/kicad/symbols",
    "C:/Program Files/KiCad/10.0/share/kicad/symbols",
]


def symbol_dir():
    for d in SYMBOL_DIRS:
        if d and any((pathlib.Path(d) / f).exists() for f in ("Device.kicad_symdir", "Device.kicad_sym")):
            return pathlib.Path(d)
    raise SystemExit("KiCad's symbol libraries were not found; set KICAD_SYMBOL_DIR")


# --- S-expressions -------------------------------------------------------------------------

TOKEN = re.compile(r'\s*(?:(\()|(\))|("(?:[^"\\]|\\.)*")|([^\s()"]+))')


def parse(text):
    """Parses an S-expression into nested lists. Quoted strings keep their quotes."""
    stack, out, pos = [], [], 0
    while pos < len(text):
        m = TOKEN.match(text, pos)
        if not m:
            break
        pos = m.end()
        if m.group(1):
            stack.append(out)
            out = []
        elif m.group(2):
            done, out = out, stack.pop()
            out.append(done)
        elif m.group(3) or m.group(4):
            out.append(m.group(3) or m.group(4))
    return out[0]


def dump(node, indent=0):
    if not isinstance(node, list):
        return node
    simple = all(not isinstance(x, list) for x in node)
    if simple or len(node) <= 2 and all(not isinstance(x, list) or len(x) < 4 for x in node):
        return "(" + " ".join(dump(x) for x in node) + ")"
    pad = "\t" * (indent + 1)
    head = " ".join(dump(x) for x in node if not isinstance(x, list))
    body = "".join("\n" + pad + dump(x, indent + 1) for x in node if isinstance(x, list))
    return "(" + head + body + "\n" + "\t" * indent + ")"


def q(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def unq(s):
    return s[1:-1].replace('\\"', '"').replace("\\\\", "\\") if s.startswith('"') else s


def find(node, key):
    return [x for x in node if isinstance(x, list) and x and x[0] == key]


# --- Library symbols -----------------------------------------------------------------------

class Library:
    def __init__(self):
        self.dir = symbol_dir()
        self.cache = {}

    def load(self, lib, name):
        """KiCad 10 keeps a library as a folder with one file per symbol; older versions use
        one file per library. Both are read."""
        folder = self.dir / f"{lib}.kicad_symdir"
        path = folder / f"{name}.kicad_sym" if folder.is_dir() else self.dir / f"{lib}.kicad_sym"
        if path not in self.cache:
            self.cache[path] = parse(path.read_text(encoding="utf-8"))
        return self.cache[path]

    def symbol(self, lib_id):
        """Returns the library symbol as nested lists, renamed to lib_id for embedding."""
        lib, name = lib_id.split(":")
        for s in find(self.load(lib, name), "symbol"):
            if unq(s[1]) == name:
                break
        else:
            raise KeyError(lib_id)
        ext = find(s, "extends")
        if ext:   # a derived symbol: take the parent's drawing and the child's fields
            parent = self.symbol(f"{lib}:{unq(ext[0][1])}")
            props = find(s, "property")
            keep = [x for x in parent if not (isinstance(x, list) and x[0] == "property")]
            s = keep[:2] + props + keep[2:]
            s = [x if not (isinstance(x, list) and x[0] == "symbol")
                 else ["symbol", q(unq(x[1]).replace(unq(ext[0][1]), name, 1))] + x[2:] for x in s]
        s = list(s)
        s[1] = q(lib_id)
        return s

    def pins(self, lib_id):
        """{pin number: (x, y)} in library coordinates (y up), for unit 1."""
        out = {}

        def walk(node):
            for x in node:
                if isinstance(x, list) and x[0] == "symbol":
                    walk(x)
                elif isinstance(x, list) and x[0] == "pin":
                    at = find(x, "at")[0]
                    num = unq(find(x, "number")[0][1])
                    out[num] = (float(at[1]), float(at[2]))
        walk(self.symbol(lib_id))
        return out


def fmt(v):
    return f"{round(v, 4):g}"


def rotate(x, y, angle):
    a = math.radians(angle)
    return (x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a))


# --- The schematic -------------------------------------------------------------------------

class Schematic:
    def __init__(self, name, title, lib, comments=()):
        self.name, self.title, self.lib = name, title, lib
        self.root = str(uuid.uuid5(uuid.NAMESPACE_URL, "predictive_bms/" + name))
        self.items, self.used, self.count = [], {}, 0
        self.comments = comments

    def uid(self):
        self.count += 1
        return str(uuid.uuid5(uuid.UUID(self.root), str(self.count)))

    def part(self, lib_id, ref, value, x, y, angle=0, fields=None, ref_at=None, val_at=None,
             hide_value=False, sim=True, centre=False):
        """Places a symbol. Returns {pin number: (x, y)} on the page."""
        self.used[lib_id] = True
        lib_sym = self.lib.symbol(lib_id)
        props = {unq(p[1]): unq(p[2]) for p in find(lib_sym, "property")}
        props.update({"Reference": ref, "Value": value})
        props.update(fields or {})
        pins = {n: (x + rotate(px, py, angle)[0], y - rotate(px, py, angle)[1])
                for n, (px, py) in self.lib.pins(lib_id).items()}
        vertical = angle % 180 == 0
        dx = 3.81 if lib_id.startswith("Simulation_SPICE:") else 2.54   # clear of a source's circle
        ref_at = ref_at or ((x + dx, y - 1.27) if vertical else (x, y - 2.54))
        val_at = val_at or ((x + dx, y + 1.27) if vertical else (x, y + 2.54))
        # A part turned by 180 degrees mirrors its fields' justification, so "right" reads as left.
        just = ["justify", "right" if angle == 180 else "left"] if vertical and not centre else None
        # KiCad turns a field with its symbol: on a part turned by 90 degrees, a field at 90
        # degrees reads horizontally.
        text_angle = "0" if vertical else "90"
        node = ["symbol", ["lib_id", q(lib_id)], ["at", fmt(x), fmt(y), fmt(angle)], ["unit", "1"],
                ["exclude_from_sim", "no" if sim else "yes"], ["in_bom", "yes"], ["on_board", "yes"],
                ["dnp", "no"], ["uuid", q(self.uid())]]
        for key, val in props.items():
            if key == "Reference":
                at, hide = ref_at, False
            elif key == "Value":
                at, hide = val_at, hide_value
            else:
                at, hide = (x, y), True
            eff = ["effects", ["font", ["size", "1.27", "1.27"]]]
            if just and key in ("Reference", "Value"):
                eff.append(just)
            prop = ["property", q(key), q(val), ["at", fmt(at[0]), fmt(at[1]), text_angle]]
            if hide:
                prop.append(["hide", "yes"])
            prop.append(eff)
            node.append(prop)
        for n in self.lib.pins(lib_id):
            node.append(["pin", q(n), ["uuid", q(self.uid())]])
        node.append(["instances", ["project", q(self.name),
                                   ["path", q("/" + self.root), ["reference", q(ref)], ["unit", "1"]]]])
        self.items.append(node)
        return pins

    def power(self, lib_id, x, y):
        """A power symbol (GND, +3V3); its pin is at its anchor, (x, y)."""
        self.npower = getattr(self, "npower", 0) + 1
        name = lib_id.split(":")[1]
        prefix, dy = {"GND": ("#PWR", 6.35), "PWR_FLAG": ("#FLG", -5.08)}.get(name, ("#PWR", -3.81))
        self.part(lib_id, f"{prefix}{self.npower:02d}", name, x, y,
                  ref_at=(x, y), val_at=(x, y + dy), centre=True)
        for p in find(self.items[-1], "property"):   # a power symbol's reference stays hidden
            if unq(p[1]) == "Reference":
                p.insert(4, ["hide", "yes"])

    def wire(self, *pts):
        for a, b in zip(pts, pts[1:]):
            if a == b:
                continue
            self.items.append(["wire", ["pts", ["xy", fmt(a[0]), fmt(a[1])], ["xy", fmt(b[0]), fmt(b[1])]],
                               ["stroke", ["width", "0"], ["type", "default"]], ["uuid", q(self.uid())]])

    def junction(self, x, y):
        self.items.append(["junction", ["at", fmt(x), fmt(y)], ["diameter", "0"],
                           ["color", "0", "0", "0", "0"], ["uuid", q(self.uid())]])

    def label(self, name, x, y, angle=0, glob=False):
        """A net label. A global label is used for a net named inside a simulation formula."""
        just = "right" if angle == 180 else "left"
        if glob:
            self.items.append(["global_label", q(name), ["shape", "passive"],
                               ["at", fmt(x), fmt(y), fmt(angle)], ["fields_autoplaced", "yes"],
                               ["effects", ["font", ["size", "1.27", "1.27"]], ["justify", just]],
                               ["uuid", q(self.uid())]])
        else:
            self.items.append(["label", q(name), ["at", fmt(x), fmt(y), fmt(angle)],
                               ["fields_autoplaced", "yes"],
                               ["effects", ["font", ["size", "1.27", "1.27"]], ["justify", just, "bottom"]],
                               ["uuid", q(self.uid())]])

    def text(self, body, x, y, size=1.27, sim=False):
        """Free text. A simulation command (".tran ...") must be passed with sim=True."""
        self.items.append(["text", q(body), ["exclude_from_sim", "no" if sim else "yes"],
                           ["at", fmt(x), fmt(y), "0"],
                           ["effects", ["font", ["size", fmt(size), fmt(size)]], ["justify", "left", "top"]],
                           ["uuid", q(self.uid())]])

    def write(self, folder, version, date, rev, company):
        folder = pathlib.Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        tb = ["title_block", ["title", q(self.title)], ["date", q(date)], ["rev", q(rev)],
              ["company", q(company)]]
        for i, c in enumerate(self.comments, 1):
            tb.append(["comment", str(i), q(c)])
        doc = ["kicad_sch", ["version", version], ["generator", q("eeschema")],
               ["generator_version", q("10.0")], ["uuid", q(self.root)], ["paper", q("A4")], tb,
               ["lib_symbols"] + [self.lib.symbol(s) for s in self.used]]
        doc += self.items
        doc.append(["sheet_instances", ["path", q("/"), ["page", q("1")]]])
        (folder / f"{self.name}.kicad_sch").write_text(dump(doc) + "\n", encoding="utf-8")
        pro = {"meta": {"filename": f"{self.name}.kicad_pro", "version": 3},
               "sheets": [[self.root, "Root"]]}
        (folder / f"{self.name}.kicad_pro").write_text(json.dumps(pro, indent=2) + "\n", encoding="utf-8")
