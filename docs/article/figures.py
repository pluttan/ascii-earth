"""Figures for the Habr article (docs/article/habr-ascii-earth.md).

The globe on the cover is the program's own output: build_frame() prints the
same coloured Braille text as in a terminal, and this script lays that text out
as dots instead of a terminal doing it. The other card is drawn here.

Each figure is a self-contained card, filled edge to edge: the Habr dark grey
round, a darker field inside, the Catppuccin Mocha colours and the GOST Type BU
font (docs/fonts), titles in Exo 2 Bold Italic.

Run:  make figures   ->  docs/article/img/*

Signed: pluttan
"""

from __future__ import annotations

import datetime
import os
import sys
import types
from argparse import Namespace
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager, patheffects, rcParams
from matplotlib.text import Text
from matplotlib.transforms import Affine2D
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
OUT = HERE / "img"
sys.path.insert(0, str(HERE.parent.parent))
from ascii_earth import globe as g  # noqa: E402

# ==============================
# ===  Look                  ===
# ==============================

C = {
    "card": "#171717",     # Habr dark --background-primary, hsl(0, 0%, 9%)
    "panel": "#040404",    # the field inside the card
    "ink": "#cdd6f4",      # Catppuccin Mocha: Text
    "muted": "#a6adc8",    # Subtext 0
    "dim": "#313244",      # Surface 0: a dot that is off
    "mine": "#74c7ec",     # Sapphire: a dot that is on, the accent
}
DPI = 300
MARGIN, RADIUS = 0.1, 0.2  # the field inside the card, inches
TITLE = {"family": "Exo 2", "fontweight": "bold", "fontstyle": "italic", "gid": "title"}
SLANT = 15                 # ГОСТ 2.304: the slanted type leans at 75 degrees to the line


def style():
    for name in ("GOSTtypeB.ttf", "Exo2-BoldItalic.ttf"):
        font_manager.fontManager.addfont(str(HERE.parent / "fonts" / name))
    rcParams.update({"font.family": "GOST Type BU", "font.size": 11, "text.color": C["ink"],
                     "figure.dpi": DPI, "savefig.dpi": DPI})


class Slanted(patheffects.AbstractPathEffect):
    """Draw a text effect with its glyphs leaned forward: GOST Type BU has no italic face."""

    def __init__(self, inner, deg: float):
        super().__init__()
        self.inner, self.deg = inner, deg

    def draw_path(self, renderer, gc, tpath, affine, rgbFace=None):
        self.inner.draw_path(renderer, gc, tpath, Affine2D().skew_deg(self.deg, 0) + affine, rgbFace)


def slant(fig):
    """Lean every GOST text of the figure; titles and pictures stay upright."""
    for t in fig.findobj(Text):
        if t.get_gid() in ("title", "plain"):
            continue
        effects = t.get_path_effects() or [patheffects.Normal()]
        t.set_path_effects([Slanted(e, SLANT) for e in effects])


def field(fig):
    """The Habr grey round the card and the dark round field inside it."""
    w, h = (int(round(v * DPI)) for v in fig.get_size_inches())
    m, r = int(MARGIN * DPI), int(RADIUS * DPI)
    im = Image.new("RGB", (w, h), C["card"])
    ImageDraw.Draw(im).rounded_rectangle((m, m, w - m, h - m), r, fill=C["panel"])
    ax = fig.add_axes([0, 0, 1, 1], zorder=-100)
    ax.imshow(np.asarray(im), extent=(0, 1, 0, 1), aspect="auto", interpolation="none")
    ax.axis("off")


def save(fig, name: str):
    OUT.mkdir(exist_ok=True)
    slant(fig)
    fig.savefig(OUT / name, facecolor=C["card"])
    plt.close(fig)
    print(f"  {name}")


# ==============================
# ===  The program's frame   ===
# ==============================


def fix_clock(when: datetime.datetime):
    """build_frame reads the real clock for the Sun; hand it a fixed moment instead."""
    class Fixed(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return when
    g.datetime = types.SimpleNamespace(datetime=Fixed, timezone=datetime.timezone)


def frame(cols: int, rows: int, **kw) -> str:
    """The text the program prints for a terminal of cols x rows cells."""
    os.environ["COLUMNS"], os.environ["LINES"] = str(cols), str(rows)
    args = Namespace(body="earth", lon=-30.0, lat=18.0, follow=False, sun=False, no_rings=False,
                     top="", bottom="", no_labels=True, size=cols - 2, aspect=2.0,
                     no_stars=True, stars=0.03, glyphs="braille", color="truecolor",
                     no_ring=False, palette="natural", ramp="")
    vars(args).update(kw)
    g.set_color(2.1, 0.55)  # the program's defaults
    return g.build_frame(g.body_texture(args.body), args)


def cells(text: str):
    """Rows of (glyph, rgb) from the program's ANSI text; rgb None means no colour set."""
    rows = []
    for line in text.split("\n"):
        row, cur, i = [], None, 0
        while i < len(line):
            if line[i] == "\x1b":
                j = line.index("m", i)
                code = line[i + 2:j]
                cur = tuple(int(v) for v in code[5:].split(";")) if code.startswith("38;2;") else None
                i = j + 1
                continue
            row.append((line[i], cur))
            i += 1
        rows.append(row)
    return rows


MONO = Path(matplotlib.get_data_path()) / "fonts" / "ttf" / "DejaVuSansMono.ttf"


def lay_out(text, cw: float, ch: float, sub: int = 4) -> Image.Image:
    """Lay the text out the way a terminal would, Braille as round dots.

    A Braille glyph is drawn as its own dots in the 2 x 4 grid of the cell, at
    sub times the size and then scaled down, so the edges come out smooth. The
    stars round the disc are plain glyphs in DejaVu Sans Mono. Takes the text
    or rows of cells already split.
    """
    from PIL import ImageFont
    rows = cells(text) if isinstance(text, str) else text
    ncol = max(len(r) for r in rows)
    w, h = int(ncol * cw * sub), int(len(rows) * ch * sub)
    im = Image.new("RGB", (w, h), C["panel"])
    d = ImageDraw.Draw(im)
    font = ImageFont.truetype(str(MONO), int(ch * 0.7 * sub))
    rad = 0.19 * cw * sub
    for r, row in enumerate(rows):
        for c, (glyph, rgb) in enumerate(row):
            code = ord(glyph)
            if rgb is None or glyph == " ":
                continue
            if not 0x2800 <= code <= 0x28FF:
                d.text(((c + 0.5) * cw * sub, (r + 0.5) * ch * sub), glyph, fill=rgb,
                       font=font, anchor="mm")
                continue
            bits = code - 0x2800
            for dy in range(4):
                for dx in range(2):
                    if bits & g._BRAILLE_BITS[dy][dx]:
                        x = (c + 0.25 + 0.5 * dx) * cw * sub
                        y = (r + 0.125 + 0.25 * dy) * ch * sub
                        d.ellipse((x - rad, y - rad, x + rad, y + rad), fill=rgb)
    return im.resize((w // sub, h // sub), Image.LANCZOS)


# ==============================
# ===  Figures               ===
# ==============================


def fig_braille():
    """One Braille glyph: eight dots in a 2 x 4 cell, each dot a bit."""
    fig = plt.figure(figsize=(8, 3.6), facecolor=C["card"])
    field(fig)
    fig.text(0.055, 0.86, "Клетка Брайля: восемь точек в одном знаке", fontsize=21, va="top", **TITLE)
    fig.text(0.055, 0.73, "каждая точка задаёт свой бит, знак равен U+2800 плюс сумма битов",
             fontsize=10.5, color=C["muted"], va="top")
    on = 0x01 | 0x02 | 0x08 | 0x10 | 0x40   # the dots lit in the example
    ax = fig.add_axes([0.08, 0.1, 0.36, 0.56])
    ax.set_xlim(-0.9, 2.9)
    ax.set_ylim(-0.6, 3.6)
    ax.set_aspect("equal")
    ax.axis("off")
    for dy in range(4):
        for dx in range(2):
            bit = g._BRAILLE_BITS[dy][dx]
            ax.add_patch(plt.Circle((dx, 3 - dy), 0.3, color=C["mine"] if on & bit else C["dim"]))
            ax.text(dx + (-0.5 if dx == 0 else 0.5), 3 - dy, str(bit), fontsize=10.5,
                    color=C["muted"], va="center", ha="right" if dx == 0 else "left")
    fig.text(0.52, 0.48, f"1 + 2 + 8 + 16 + 64 = {on}", fontsize=14, va="center")
    fig.text(0.52, 0.32, f"U+2800 + {on} = U+{0x2800 + on:04X}", fontsize=14, va="center")
    save(fig, "braille.png")


def fig_cover():
    """Feed cover at three times 780x440: Earth at dusk on the right, the title on the left."""
    # 16:00 UTC: the line between day and night runs down the middle of the disc.
    fix_clock(DUSK)
    d = 110
    disc = lay_out(frame(d + 2, d // 2 + 1, size=d, sun=True, lon=28.0, lat=20.0), 10, 20)
    disc = np.asarray(disc, float) / 255
    fig = plt.figure(figsize=(7.8, 4.4), dpi=100, facecolor=C["card"])
    field(fig)
    side = 0.84 * 4.4
    ax = fig.add_axes([1 - (side + 0.32) / 7.8, (1 - side / 4.4) / 2,
                       side / 7.8, side / 4.4])
    ax.imshow(disc, interpolation="lanczos")
    ax.axis("off")
    for y, line, color in ((0.80, "Земля", C["ink"]), (0.68, "в терминале", C["mine"])):
        fig.text(0.06, y, line, fontsize=27, va="top", color=color, **TITLE)
    fig.text(0.06, 0.47, "точки Брайля и настоящая\nграница дня и ночи", fontsize=12.5,
             color=C["muted"], va="top", linespacing=1.45)
    fig.text(0.06, 0.11, "11 тел Солнечной системы", fontsize=12, va="bottom")
    OUT.mkdir(exist_ok=True)
    slant(fig)
    fig.savefig(OUT / "cover.png", dpi=300, facecolor=C["card"])
    plt.close(fig)
    # Habr takes a cover of 1 MB at most: a JPEG copy, the best quality that fits.
    im = Image.open(OUT / "cover.png").convert("RGB")
    for q in range(95, 60, -3):
        im.save(OUT / "cover.jpg", quality=q, optimize=True)
        if (OUT / "cover.jpg").stat().st_size <= 1_000_000:
            break
    print(f"  cover.png, cover.jpg (quality {q})")


def framed(im: Image.Image, name: str, pad: float = 0.12):
    """A frame of the program alone on the card: the field round it, corners round."""
    w, h = im.size
    m = int((MARGIN + pad) * DPI)
    card = Image.new("RGB", (w + 2 * m, h + 2 * m), C["card"])
    edge = int(MARGIN * DPI)
    ImageDraw.Draw(card).rounded_rectangle((edge, edge, w + 2 * m - edge, h + 2 * m - edge),
                                           int(RADIUS * DPI), fill=C["panel"])
    card.paste(im, (m, m))
    OUT.mkdir(exist_ok=True)
    card.save(OUT / name)
    print(f"  {name}")


DUSK = datetime.datetime(2026, 10, 28, 16, 0, tzinfo=datetime.timezone.utc)


def fig_daynight():
    """The day/night view at a fixed moment, with the starfield round it."""
    fix_clock(DUSK)
    framed(lay_out(frame(150, 56, size=100, sun=True, lon=28.0, lat=20.0, no_stars=False), 14, 28),
           "daynight.png")


# Bodies left to right; names on the card, the Sun cut by the left edge.
LINEUP = (("sun", "Солнце"), ("mercury", "Меркурий"), ("venus", "Венера"), ("earth", "Земля"),
          ("moon", "Луна"), ("mars", "Марс"), ("ceres", "Церера"), ("jupiter", "Юпитер"),
          ("saturn", "Сатурн"), ("uranus", "Уран"), ("neptune", "Нептун"))
EARTH_D = 14   # Earth across, in columns
GAP = 3        # empty columns between bodies
SUN_SHOWN = 22 # columns of the Sun left on the card


def fig_scale():
    """Every body in the sqrt mode, side by side: one frame of the program per body."""
    rows = 34
    strip = [[] for _ in range(rows)]
    names = []
    for body, name in LINEUP:
        size = g.scaled_size("sqrt", body, EARTH_D)
        ring = g.BODIES[body].get("rings")
        cols = int(size * (ring["outer"] if ring else 1)) + 2
        lat = 26.0 if ring else 12.0
        grid = cells(frame(cols, rows, body=body, size=size, lon=-30.0, lat=lat))
        if body == "sun":
            grid = [r[-SUN_SHOWN:] for r in grid]
            cols = SUN_SHOWN
        x0 = len(strip[0])
        for r in range(rows):
            strip[r] += (grid[r] + [(" ", None)] * cols)[:cols] + [(" ", None)] * GAP
        names.append((name, x0 + cols / 2, body))
    # Stars into the empty cells, the program's own field.
    for r in range(rows):
        for c, (glyph, rgb) in enumerate(strip[r]):
            if glyph == " ":
                star = g._star_at(r, c, 0.03)
                if star:
                    strip[r][c] = star
    total = len(strip[0])
    im = np.asarray(lay_out(strip, 8, 16), float) / 255
    width = 8.0
    side = 0.055 * width
    img_w = width - 2 * side
    img_h = img_w * im.shape[0] / im.shape[1]
    height = 1.25 + img_h + 0.55
    fig = plt.figure(figsize=(width, height), facecolor=C["card"])
    field(fig)
    fig.text(0.055, 1 - 0.38 / height, "Солнечная система в режиме sqrt", fontsize=21, va="top", **TITLE)
    fig.text(0.055, 1 - 0.80 / height, "радиус под корнем: Солнце в 10 раз больше Земли, а не в 109",
             fontsize=10.5, color=C["muted"], va="top")
    bottom = 0.55 / height
    ax = fig.add_axes([side / width, bottom, img_w / width, img_h / height])
    ax.imshow(im, interpolation="lanczos")
    ax.axis("off")
    for i, (name, x, body) in enumerate(names):
        if body == "sun":
            x = SUN_SHOWN * 0.35
        y = bottom - (0.12 if i % 2 == 0 else 0.30) / height
        fig.text((side + img_w * x / total) / width, y, name, fontsize=9.5, color=C["muted"],
                 ha="center", va="top")
    save(fig, "scale.png")


def main():
    style()
    print(f"рисую в {OUT}")
    for fig in (fig_braille, fig_daynight, fig_scale, fig_cover):
        fig()


if __name__ == "__main__":
    main()
