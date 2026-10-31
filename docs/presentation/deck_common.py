"""Shared slide furniture for the review decks.

Every measurement below was taken from the review-deck template these slides
have to match: 13.333 x 7.5 in (16:9), Times New Roman, centred underlined
headings, a grey Calibri footer and the college logo in the top-left corner.
See template-notes.md for how the values were measured.

A build script calls configure() first, then uses the slide builders.
"""
import os
import copy
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR, MSO_AUTO_SIZE
from pptx.oxml.ns import qn
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
LOGO = os.path.join(HERE, "logo.png")

DIAG = None            # set by configure()

# ── design tokens, measured from the template ───────────────────────────
SLIDE_W, SLIDE_H = 13.333, 7.5

ACCENT_NAVY = RGBColor(0x00, 0x20, 0x60)
TEXT_BLACK = RGBColor(0x00, 0x00, 0x00)
FOOTER_GREY = RGBColor(0x89, 0x89, 0x89)
TABLE_BAND = RGBColor(0xED, 0xED, 0xED)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

HEADING_FONT = "Times New Roman"
BODY_FONT = "Times New Roman"
BULLET_FONT = "Arial"
FOOTER_FONT = "Calibri"
MONO_FONT = "Consolas"

LOGO_L, LOGO_T, LOGO_W, LOGO_H = 0.313, 0.120, 0.707, 1.040
HEAD_T, HEAD_H = 0.42, 0.60
BODY_L, BODY_R = 1.278, 12.428
BODY_T, BODY_B = 1.52, 6.72
IMG_L, IMG_R = 0.72, 12.61
IMG_T, IMG_B = 1.42, 6.70
FOOT_T = 6.95

HEAD_SIZE, BODY_SIZE = 24, 18
FOOT_SIZE = 12

REVIEW_LABEL = ""      # e.g. "First Review-2026-27"; set by configure()
EXPORT_DATE = ""       # e.g. "27-08-2026";            set by configure()
TITLE_LINES = []       # the project title, one entry per line
REVIEW_HEADING = ""    # e.g. "Major Project Stage-1 First Review Presentation"

WARNINGS = []

# "classic" is the 16:9 template above. "banded" is the 4:3 design the department
# used for the first review: green bars top and bottom, large left-aligned
# headings, blue tables. See template-notes.md.
THEME = "classic"
TABLE_HEAD, TABLE_CELL = ACCENT_NAVY, WHITE
BAR_GREEN = RGBColor(0x4F, 0x7A, 0x28)
BAR_BLACK = RGBColor(0x11, 0x11, 0x11)
TITLE_RED = RGBColor(0xFF, 0x00, 0x00)
DEPT_PURPLE = RGBColor(0x7F, 0x00, 0x7F)
COLLEGE_NAVY = RGBColor(0x1F, 0x38, 0x64)


def _use_banded():
    global THEME, SLIDE_W, HEAD_T, HEAD_H, HEAD_SIZE, BODY_L, BODY_R, BODY_T, BODY_B
    global IMG_L, IMG_R, IMG_T, IMG_B, TABLE_HEAD, TABLE_CELL, TABLE_BAND
    THEME = "banded"
    SLIDE_W = 10.0
    HEAD_T, HEAD_H, HEAD_SIZE = 0.50, 0.70, 32
    BODY_L, BODY_R = 0.62, 9.45
    BODY_T, BODY_B = 1.38, 6.80
    IMG_L, IMG_R = 0.40, 9.60
    IMG_T, IMG_B = 1.32, 6.82
    TABLE_HEAD = RGBColor(0x4F, 0x81, 0xBD)
    TABLE_CELL = TABLE_BAND = RGBColor(0xD0, 0xD8, 0xE8)


def configure(review_label, export_date, diagram_dir, review_heading, title_lines,
              theme="classic"):
    """Set everything that differs between one review deck and the next."""
    global REVIEW_LABEL, EXPORT_DATE, DIAG, REVIEW_HEADING, TITLE_LINES
    if theme == "banded":
        _use_banded()
    REVIEW_LABEL = review_label
    EXPORT_DATE = export_date
    DIAG = diagram_dir
    REVIEW_HEADING = review_heading
    TITLE_LINES = list(title_lines)
    WARNINGS.clear()


# ── low-level helpers ───────────────────────────────────────────────────
def textbox(slide, l, t, w, h):
    box = slide.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.auto_size = MSO_AUTO_SIZE.NONE
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    return box, tf


def run(p, text, size, bold=False, color=TEXT_BLACK, font=BODY_FONT,
        italic=False, underline=False):
    r = p.add_run()
    r.text = text
    f = r.font
    f.size = Pt(size)
    f.bold = bold
    f.italic = italic
    f.underline = underline
    f.color.rgb = color
    f.name = font
    return r


def set_bullet(p, char="•", font=BULLET_FONT, indent_in=0.31):
    """Real PowerPoint bullet with a hanging indent, matching the template."""
    pPr = p._p.get_or_add_pPr()
    pPr.set("marL", str(Emu(Inches(indent_in)).emu))
    pPr.set("indent", str(-Emu(Inches(indent_in)).emu))
    for tag in ("a:buNone", "a:buChar", "a:buAutoNum"):
        for el in pPr.findall(qn(tag)):
            pPr.remove(el)
    bu = pPr.makeelement(qn("a:buFont"), {"typeface": font})
    pPr.append(bu)
    bc = pPr.makeelement(qn("a:buChar"), {"char": char})
    pPr.append(bc)
    if THEME == "banded":
        p.alignment = PP_ALIGN.JUSTIFY


def no_bullet(p):
    pPr = p._p.get_or_add_pPr()
    for tag in ("a:buChar", "a:buAutoNum"):
        for el in pPr.findall(qn(tag)):
            pPr.remove(el)
    pPr.append(pPr.makeelement(qn("a:buNone"), {}))


def check_overflow(name, text_lines, size, width_in, height_in):
    """Rough fit check: python-pptx cannot shrink text, so warn instead."""
    chars_per_line = max(1, int(width_in * 96 / (size * 0.52)))
    lines = 0
    for ln in text_lines:
        lines += max(1, -(-len(ln) // chars_per_line))
    needed = lines * size * 1.35 / 72.0
    if needed > height_in:
        WARNINGS.append("%s: text needs ~%.2f in but the box is %.2f in"
                        % (name, needed, height_in))


# ── slide furniture ─────────────────────────────────────────────────────
def heading_box(slide, heading, top):
    if THEME == "banded":
        # Dynamic font scaling to guarantee headings fit on a single line with zero overlap
        nchars = len(heading)
        if nchars > 46:
            size = 21
        elif nchars > 38:
            size = 23
        elif nchars > 28:
            size = 25
        else:
            size = 28
        _, tf = textbox(slide, BODY_L - 0.12, top, BODY_R - BODY_L + 0.12, HEAD_H)
        run(tf.paragraphs[0], heading, size, font=HEADING_FONT, bold=True)
        return
    _, tf = textbox(slide, 1.30, top, SLIDE_W - 2.60, HEAD_H)
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    run(p, heading, HEAD_SIZE, bold=True, font=HEADING_FONT, underline=True)


def _poly(slide, points, color):
    fb = slide.shapes.build_freeform(Inches(points[0][0]), Inches(points[0][1]))
    fb.add_line_segments([(Inches(x), Inches(y)) for x, y in points[1:]], close=True)
    shape = fb.convert_to_shape()
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()
    shape.shadow.inherit = False
    return shape


def bars(slide, wide=False):
    """The green bars of the banded design. The title slide uses the wide pair."""
    if wide:
        _poly(slide, [(0.22, 0.04), (9.78, 0.04), (9.50, 0.34), (0.50, 0.34)], BAR_BLACK)
        _poly(slide, [(0.30, 0.04), (9.70, 0.04), (9.48, 0.27), (0.52, 0.27)], BAR_GREEN)
        l, r = 0.25, 9.85
    else:
        _poly(slide, [(0.17, 0.06), (9.83, 0.06), (9.83, 0.28), (9.78, 0.33),
                      (0.17, 0.33)], BAR_BLACK)
        _poly(slide, [(0.17, 0.06), (9.83, 0.06), (9.83, 0.27), (0.17, 0.27)], BAR_GREEN)
        l, r = 0.95, 8.95
    _poly(slide, [(l + 0.30, 6.98), (r - 0.35, 6.98), (r, 7.30), (l, 7.30)], BAR_BLACK)
    _poly(slide, [(l + 0.37, 7.04), (r - 0.42, 7.04), (r - 0.15, 7.30), (l + 0.15, 7.30)],
          BAR_GREEN)


def base(prs, heading=None, number=None):
    slide = prs.slides.add_slide(prs.slide_layouts[6])          # blank
    if THEME == "banded":
        bars(slide, wide=(number == 1))
        if number is not None and number > 1:
            _, tf = textbox(slide, 9.05, 7.02, 0.60, 0.28)
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.RIGHT
            run(p, str(number), FOOT_SIZE, font=HEADING_FONT)
    else:
        slide.shapes.add_picture(LOGO, Inches(LOGO_L), Inches(LOGO_T),
                                 Inches(LOGO_W), Inches(LOGO_H))
    if heading:
        heading_box(slide, heading, HEAD_T)
    if number is not None and THEME != "banded":
        foot(slide, number)
    return slide


def foot(slide, number):
    _, tf = textbox(slide, 1.017, FOOT_T, 2.5, 0.32)
    run(tf.paragraphs[0], EXPORT_DATE, FOOT_SIZE, color=FOOTER_GREY, font=FOOTER_FONT)

    _, tf = textbox(slide, 4.3, FOOT_T, 4.7, 0.32)
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    run(p, REVIEW_LABEL, FOOT_SIZE, color=FOOTER_GREY, font=FOOTER_FONT)

    _, tf = textbox(slide, 11.0, FOOT_T, 1.317, 0.32)
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.RIGHT
    run(p, str(number), FOOT_SIZE, color=FOOTER_GREY, font=FOOTER_FONT)


def notes(slide, text):
    slide.notes_slide.notes_text_frame.text = text.strip()


# ── slide builders ──────────────────────────────────────────────────────
def _banded_title_slide(prs, n, note):
    slide = base(prs, number=n)

    _, tf = textbox(slide, 0.50, 0.40, SLIDE_W - 1.00, 0.62)
    for i, line in enumerate([REVIEW_HEADING, "on"]):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.CENTER
        run(p, line, 18, bold=True, color=COLLEGE_NAVY, font=HEADING_FONT)

    _, tf = textbox(slide, 8.30, 0.75, 1.20, 0.28)
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.RIGHT
    run(p, EXPORT_DATE, 12)

    _, tf = textbox(slide, 0.40, 1.10, SLIDE_W - 0.80, 0.95)
    for i, line in enumerate(TITLE_LINES):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.CENTER
        run(p, line, 24, bold=True, color=TITLE_RED, font=HEADING_FONT)

    logo_h = 1.45
    logo_w = logo_h * LOGO_W / LOGO_H
    slide.shapes.add_picture(LOGO, Inches((SLIDE_W - logo_w) / 2), Inches(2.18),
                             Inches(logo_w), Inches(logo_h))

    _, tf = textbox(slide, 1.55, 3.95, 3.8, 1.5)
    run(tf.paragraphs[0], "Presented by", 18, bold=True)
    for line in ["Ms. Muskan Sulathana", "Roll No.  :  23WH1A0208"]:
        p = tf.add_paragraph()
        p.space_before = Pt(4)
        run(p, line, 16)

    _, tf = textbox(slide, 5.60, 3.95, 3.6, 1.5)
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    run(p, "Guide", 18, bold=True)
    for line in ["Dr. M. Rupesh", "Associate Professor,", "EEE Department"]:
        p = tf.add_paragraph()
        p.alignment = PP_ALIGN.CENTER
        p.space_before = Pt(2)
        run(p, line, 16)

    _, tf = textbox(slide, 0.30, 5.95, SLIDE_W - 0.60, 0.90)
    for i, (line, color) in enumerate((
            ("Department of Electrical & Electronics Engineering", DEPT_PURPLE),
            ("BVRIT HYDERABAD College of Engineering for Women", COLLEGE_NAVY))):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.CENTER
        run(p, line, 22, bold=True, color=color, font=HEADING_FONT)

    notes(slide, note)
    return slide


def title_slide(prs, n, note):
    if THEME == "banded":
        return _banded_title_slide(prs, n, note)
    slide = base(prs, number=n)

    _, tf = textbox(slide, 1.30, 0.83, SLIDE_W - 2.60, 0.90)
    for i, line in enumerate([REVIEW_HEADING, "on"]):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.CENTER
        run(p, line, 18, bold=True, color=ACCENT_NAVY, font=HEADING_FONT)

    _, tf = textbox(slide, 0.90, 1.68, SLIDE_W - 1.80, 1.30)
    for i, line in enumerate(TITLE_LINES):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.CENTER
        run(p, line, 28, bold=True, font=HEADING_FONT)

    _, tf = textbox(slide, 1.65, 3.72, 5.0, 2.4)
    p = tf.paragraphs[0]
    run(p, "Presented by", 18, bold=True)
    for line in ["", "Ms. Muskan Sulathana", "Roll No.  :  23WH1A0208"]:
        p = tf.add_paragraph()
        run(p, line, 18)

    _, tf = textbox(slide, 7.10, 3.72, 5.4, 2.4)
    p = tf.paragraphs[0]
    run(p, "Guide", 18, bold=True)
    for line in ["", "Dr. M. Rupesh", "Associate Professor", "EEE Department",
                 "BVRIT HYDERABAD College of Engineering", "for Women, Hyderabad"]:
        p = tf.add_paragraph()
        run(p, line, 18)

    notes(slide, note)
    return slide


def content_slide(prs, n, heading, bullets, note, size=BODY_SIZE, sub=None,
                  numbered=False, number_format="[%d]  "):
    slide = base(prs, heading, n)
    top = BODY_T
    if sub:
        _, tf = textbox(slide, BODY_L, top, BODY_R - BODY_L, 0.45)
        run(tf.paragraphs[0], sub, size, italic=True, color=FOOTER_GREY)
        top += 0.55
    _, tf = textbox(slide, BODY_L, top, BODY_R - BODY_L, BODY_B - top)
    gap = 26 if len(bullets) <= 4 else (20 if len(bullets) == 5 else 13)
    for i, b in enumerate(bullets):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(gap)
        p.line_spacing = 1.10
        if numbered:
            no_bullet(p)
            pPr = p._p.get_or_add_pPr()
            pPr.set("marL", str(Emu(Inches(0.42)).emu))
            pPr.set("indent", str(-Emu(Inches(0.42)).emu))
            if THEME == "banded":
                p.alignment = PP_ALIGN.JUSTIFY
            run(p, number_format % (i + 1), size)
        else:
            set_bullet(p)
        run(p, b, size)
    check_overflow(heading, bullets, size, BODY_R - BODY_L, BODY_B - top)
    notes(slide, note)
    return slide


def two_section_slide(prs, n, h1, b1, h2, b2, note, size=BODY_SIZE):
    """Two headings on one slide, the way the template does Problem + Objective."""
    slide = base(prs, h1, n)
    banded = THEME == "banded"
    top = BODY_T - 0.10
    first_h = 2.25 if banded else 2.55
    gap = 10 if banded else 16
    _, tf = textbox(slide, BODY_L, top, BODY_R - BODY_L, first_h)
    for i, b in enumerate(b1):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(gap)
        p.line_spacing = 1.10
        set_bullet(p)
        run(p, b, size)
    check_overflow(h1, b1, size, BODY_R - BODY_L, first_h)

    mid = top + first_h + (0.05 if banded else 0.20)
    heading_box(slide, h2, mid)

    body_top = mid + (0.76 if banded else 0.78)
    _, tf = textbox(slide, BODY_L, body_top, BODY_R - BODY_L, BODY_B - body_top)
    for i, b in enumerate(b2):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(gap)
        p.line_spacing = 1.10
        set_bullet(p)
        run(p, b, size)
    check_overflow(h2, b2, size, BODY_R - BODY_L, BODY_B - body_top)
    notes(slide, note)
    return slide


def _fit(img, l, t, w, h):
    with Image.open(img) as im:
        iw, ih = im.size
    scale = min(w / iw, h / ih)
    dw, dh = iw * scale, ih * scale
    return l + (w - dw) / 2, t + (h - dh) / 2, dw, dh


def image_slide(prs, n, heading, image, note, caption=None, bullets=None,
                bullet_size=17):
    slide = base(prs, heading, n)
    top, bottom = IMG_T, IMG_B
    if bullets:
        _, tf = textbox(slide, BODY_L, IMG_T, BODY_R - BODY_L, 1.0)
        for i, b in enumerate(bullets):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.space_after = Pt(6)
            set_bullet(p)
            run(p, b, bullet_size)
        top = IMG_T + 0.42 * len(bullets) + 0.22
    if caption:
        bottom -= 0.42
    l, t, w, h = _fit(os.path.join(DIAG, image), IMG_L, top, IMG_R - IMG_L, bottom - top)
    slide.shapes.add_picture(os.path.join(DIAG, image), Inches(l), Inches(t),
                             Inches(w), Inches(h))
    if caption:
        _, tf = textbox(slide, BODY_L, IMG_B - 0.36, BODY_R - BODY_L, 0.34)
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        run(p, caption, 14, italic=True, color=FOOTER_GREY)
    notes(slide, note)
    return slide


def two_image_slide(prs, n, heading, img1, img2, cap1, cap2, note, bullets=None, bullet_size=14):
    slide = base(prs, heading, n)
    half = (IMG_R - IMG_L - 0.40) / 2
    bullet_lines = len(bullets) if bullets else 0
    bullet_h = 0.38 * bullet_lines + 0.15 if bullet_lines else 0
    img_top = 1.35
    avail_h = (BODY_B - img_top - 0.40 - bullet_h)
    for i, (img, cap) in enumerate(((img1, cap1), (img2, cap2))):
        left = IMG_L + i * (half + 0.40)
        img_p = os.path.join(DIAG, img) if DIAG and not os.path.isabs(img) else img
        l, t, w, h = _fit(img_p, left, img_top + 0.36, half, avail_h)
        slide.shapes.add_picture(img_p, Inches(l), Inches(t), Inches(w), Inches(h))
        # Caption safely placed with generous headroom below the heading
        _, tf = textbox(slide, left, img_top, half, 0.32)
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        run(p, cap, 15, bold=True, color=ACCENT_NAVY)
    if bullets:
        bt = img_top + 0.36 + avail_h + 0.10
        _, tf = textbox(slide, BODY_L, bt, BODY_R - BODY_L, BODY_B - bt)
        for i, b in enumerate(bullets):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.space_after = Pt(4)
            set_bullet(p)
            run(p, b, bullet_size)
    notes(slide, note)
    return slide


def wide_image_slide(prs, n, heading, image, bullets, note,
                     img_h=None, bullet_size=14, caption=None, two_cols=False):
    """Layout for wide aspect ratio images (e.g. 3:1 to 6:1) spanning nearly full slide width."""
    slide = base(prs, heading, n)
    img_path = os.path.join(DIAG, image) if DIAG and not os.path.isabs(image) else image
    with Image.open(img_path) as im:
        iw, ih = im.size
    aspect = iw / ih

    full_w = IMG_R - IMG_L  # 9.20 inches
    calc_h = full_w / aspect

    max_img_h = 3.20 if (bullets and len(bullets) > 2) else 3.90
    actual_h = min(calc_h, max_img_h) if img_h is None else img_h
    actual_w = min(full_w, actual_h * aspect)
    img_left = IMG_L + (full_w - actual_w) / 2
    img_top = 1.30

    slide.shapes.add_picture(img_path, Inches(img_left), Inches(img_top),
                             Inches(actual_w), Inches(actual_h))

    bt = img_top + actual_h + 0.15
    rem_h = BODY_B - bt

    if caption:
        _, tf = textbox(slide, BODY_L, bt, BODY_R - BODY_L, 0.28)
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        run(p, caption, 13, italic=True, color=FOOTER_GREY)
        bt += 0.30
        rem_h -= 0.30

    if bullets:
        if two_cols and len(bullets) >= 2:
            mid = (len(bullets) + 1) // 2
            col_w = (BODY_R - BODY_L - 0.40) / 2
            for c, b_list in enumerate((bullets[:mid], bullets[mid:])):
                cx = BODY_L + c * (col_w + 0.40)
                _, tf = textbox(slide, cx, bt, col_w, rem_h)
                for i, b in enumerate(b_list):
                    p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
                    p.space_after = Pt(4)
                    set_bullet(p)
                    run(p, b, bullet_size)
        else:
            _, tf = textbox(slide, BODY_L, bt, BODY_R - BODY_L, rem_h)
            for i, b in enumerate(bullets):
                p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
                p.space_after = Pt(4)
                set_bullet(p)
                run(p, b, bullet_size)
    notes(slide, note)
    return slide


def image_and_text_slide(prs, n, heading, image, bullets, note, caption=None,
                         img_w_frac=0.55, bullet_size=14, img_on_left=True):
    slide = base(prs, heading, n)
    total_w = IMG_R - IMG_L
    img_w = total_w * img_w_frac - 0.20
    text_w = total_w * (1.0 - img_w_frac) - 0.20

    if img_on_left:
        img_left = IMG_L
        text_left = IMG_L + img_w + 0.35
    else:
        text_left = IMG_L
        img_left = IMG_L + text_w + 0.35

    top = IMG_T
    bottom = IMG_B - (0.35 if caption else 0)

    img_path = os.path.join(DIAG, image) if DIAG and not os.path.isabs(image) else image
    l, t, w, h = _fit(img_path, img_left, top, img_w, bottom - top)
    slide.shapes.add_picture(img_path, Inches(l), Inches(t), Inches(w), Inches(h))

    if caption:
        _, tf = textbox(slide, img_left, bottom + 0.05, img_w, 0.30)
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        run(p, caption, 12, italic=True, color=FOOTER_GREY)

    _, tf = textbox(slide, text_left, top, text_w, bottom - top)
    gap = 12 if len(bullets) <= 4 else (8 if len(bullets) <= 6 else 4)
    for i, b in enumerate(bullets):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(gap)
        p.line_spacing = 1.10
        set_bullet(p)
        run(p, b, bullet_size)

    notes(slide, note)
    return slide


def _cell_text(cell, val, size, bold, align):
    """A cell holds a string, a {"b": bold lead-in, "t": rest} dict, or a list of
    those, one paragraph each."""
    parts = val if isinstance(val, (list, tuple)) else [val]
    tf = cell.text_frame
    for k, part in enumerate(parts):
        p = tf.paragraphs[0] if k == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.CENTER if align == "c" else PP_ALIGN.LEFT
        if isinstance(part, dict):
            run(p, part["b"], size, bold=True)
            run(p, part["t"], size, bold=bold)
        else:
            run(p, part, size, bold=bold)


def table_slide(prs, n, heading, headers, rows, note, widths,
                size=15, total_row=False, sub=None, row_h=0.40, aligns=None,
                statement=None, head_size=None, bold_cols=(), legend=None):
    slide = base(prs, heading, n)
    top = BODY_T
    if statement:
        _, tf = textbox(slide, BODY_L, top - 0.08, BODY_R - BODY_L, 0.46)
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        run(p, statement, 18, bold=True)
        top += 0.62
    if sub:
        _, tf = textbox(slide, BODY_L, top - 0.06, BODY_R - BODY_L, 0.40)
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        run(p, sub, 14, italic=True, color=FOOTER_GREY)
        top += 0.42

    total_w = sum(widths)
    left = (SLIDE_W - total_w) / 2
    nrows = len(rows) + 1
    bottom = BODY_B - (0.62 if legend else 0)
    height = min(bottom - top, row_h * nrows)
    shape = slide.shapes.add_table(nrows, len(headers), Inches(left), Inches(top),
                                   Inches(total_w), Inches(height))
    table = shape.table
    table.first_row = True
    table.horz_banding = False
    for i, w in enumerate(widths):
        table.columns[i].width = Inches(w)

    for c, htext in enumerate(headers):
        cell = table.cell(0, c)
        cell.fill.solid()
        cell.fill.fore_color.rgb = TABLE_HEAD
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        cell.margin_left = cell.margin_right = Inches(0.07)
        p = cell.text_frame.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        run(p, htext, head_size or size, bold=True, color=WHITE)

    for r, row in enumerate(rows, start=1):
        banded = (r % 2 == 0)
        is_total = total_row and r == len(rows)
        for c, val in enumerate(row):
            cell = table.cell(r, c)
            cell.fill.solid()
            cell.fill.fore_color.rgb = TABLE_BAND if (banded or is_total) else TABLE_CELL
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.margin_left = cell.margin_right = Inches(0.07)
            cell.margin_top = cell.margin_bottom = Inches(0.03)
            align = aligns[c] if aligns else ("c" if c > 0 else "l")
            _cell_text(cell, val, size, is_total or c in bold_cols, align)
    if legend:
        _, tf = textbox(slide, BODY_R - 3.2, BODY_B - 0.56, 3.2, 0.56)
        for k, text in enumerate(legend):
            p = tf.paragraphs[0] if k == 0 else tf.add_paragraph()
            p.alignment = PP_ALIGN.RIGHT
            run(p, text, 15)
    notes(slide, note)
    return slide


def code_slide(prs, n, heading, intro, code, tail, note):
    slide = base(prs, heading, n)
    _, tf = textbox(slide, BODY_L, BODY_T, BODY_R - BODY_L, 0.85)
    for i, b in enumerate(intro):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(6)
        set_bullet(p)
        run(p, b, 17)

    top = BODY_T + 0.40 * len(intro) + 0.30
    line_h = 15 * 1.30 / 72.0                      # 15 pt monospace, 1.3 spacing
    code_h = line_h * len(code) + 0.26
    box = slide.shapes.add_textbox(Inches(BODY_L + 0.55), Inches(top),
                                   Inches(BODY_R - BODY_L - 1.10), Inches(code_h))
    box.fill.solid()
    box.fill.fore_color.rgb = RGBColor(0xF5, 0xF5, 0xF5)
    box.line.color.rgb = RGBColor(0xD8, 0xD8, 0xD8)
    tf = box.text_frame
    tf.word_wrap = False
    tf.auto_size = MSO_AUTO_SIZE.NONE
    tf.margin_left = tf.margin_right = Inches(0.16)
    tf.margin_top = tf.margin_bottom = Inches(0.10)
    for i, line in enumerate(code):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        no_bullet(p)
        p.space_after = Pt(0)
        run(p, line, 15, font=MONO_FONT)

    bottom = top + code_h + 0.30
    check_overflow(heading + " (tail)", tail, 17, BODY_R - BODY_L, BODY_B - bottom)
    _, tf = textbox(slide, BODY_L, bottom, BODY_R - BODY_L, BODY_B - bottom)
    for i, b in enumerate(tail):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(8)
        set_bullet(p)
        run(p, b, 17)
    notes(slide, note)
    return slide


def closing_slide(prs, n):
    slide = base(prs, number=n)
    big = THEME == "banded"
    _, tf = textbox(slide, 1.30, 2.75 if big else 2.85, SLIDE_W - 2.60, 2.0 if big else 1.6)
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    run(p, "Thank You", 54 if big else 40, bold=not big, font=HEADING_FONT)
    p = tf.add_paragraph()
    p.alignment = PP_ALIGN.CENTER
    run(p, "", 18)
    p = tf.add_paragraph()
    p.alignment = PP_ALIGN.CENTER
    run(p, "Questions are welcome", 20, color=ACCENT_NAVY)
    notes(slide, """
That is the end of my presentation. Thank you for listening. I am happy to take
questions on the circuit, the choice of threshold, or the schedule.
""")
    return slide
