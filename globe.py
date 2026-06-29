#!/usr/bin/env python3.12
"""Render Earth as an orthographic disc in the terminal.

Inspired by the "that's no earth! / it's a space station" poster: a real
equirectangular Earth texture is back-projected onto a sphere, sampled per
terminal cell and recoloured into a cool blue palette, with a limb ring,
scattered stars and captions.

Glyph modes: a dense 64-level UTF-8 ramp (default), a Braille sub-pixel render
for max detail, or the plain ASCII letter weave. Drive it live with the keyboard
or the mouse.
"""

import argparse
import math
import os
import shutil
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image

# ==========================
# ===  Texture handling  ===
# ==========================

TEXTURE_URL = (
    "https://eoimages.gsfc.nasa.gov/images/imagerecords/"
    "57000/57752/land_shallow_topo_2048.jpg"
)
CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "ascii-earth"
CACHE_FILE = CACHE_DIR / "land_shallow_topo_2048.jpg"


def fetch_texture(url: str = TEXTURE_URL, dest: Path = CACHE_FILE) -> Path:
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "ascii-earth/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r, open(dest, "wb") as f:
            f.write(r.read())
    except Exception as exc:  # noqa: BLE001 - friendly message, not a trace
        if dest.exists():
            dest.unlink(missing_ok=True)
        sys.exit(f"could not fetch Earth texture ({exc}).\ndownload it to {dest} from:\n  {url}")
    return dest


def load_texture(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.uint8)


# ==========================
# ===  Glyph ramps       ===
# ==========================

# 64 UTF-8 glyphs ordered dark -> dense, weights measured in JetBrains Mono.
# Mixes ASCII, Greek, Cyrillic, geometric shapes and block elements so the
# surface reads as a busy many-symbol weave rather than a few ASCII letters.
UNICODE_RAMP = (
    " .,-▫!<гLт◇rJ{уTc▗IYZsк▬◑◗✦ъонζЧVα6д3ыимЗUdшψOЛGΩδ0ΘRΨВИШЮ▍▝▞▅▙▆▛█"
)

# Plain ASCII weave, closest to the source poster's lettering.
ASCII_RAMP = " .,;:~=+tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"

STAR_GLYPHS = ".`'+*"

# ==========================
# ===  Palette           ===
# ==========================

# Cool palette, but saturated enough that the blue survives 256-colour
# quantisation (the flat poster tones collapsed to grey there).
OCEAN_RGB = ((10, 28, 70), (95, 165, 215))
LAND_RGB = ((112, 122, 112), (240, 245, 235))
RING_RGB = (216, 230, 240)
STAR_LO, STAR_HI = (44, 48, 60), (232, 238, 248)
LABEL_RGB = (232, 240, 245)

_CUBE = (0, 95, 135, 175, 215, 255)


def _nearest_256(r: int, g: int, b: int) -> int:
    """Closest xterm-256 code. Chroma-aware: saturated colours never fall into
    the grey ramp (that was turning the blue ocean monochrome)."""
    def cidx(v):
        best, bi = 1 << 30, 0
        for i, c in enumerate(_CUBE):
            d = (v - c) ** 2
            if d < best:
                best, bi = d, i
        return bi

    ri, gi, bi = cidx(r), cidx(g), cidx(b)
    cube = 16 + 36 * ri + 6 * gi + bi
    chroma = max(r, g, b) - min(r, g, b)
    if chroma > 20:
        return cube
    cr, cg, cb = _CUBE[ri], _CUBE[gi], _CUBE[bi]
    cube_err = (cr - r) ** 2 + (cg - g) ** 2 + (cb - b) ** 2
    grey = round((r + g + b) / 3)
    gi2 = min(23, max(0, round((grey - 8) / 10)))
    gv = 8 + gi2 * 10
    return (232 + gi2) if (gv - grey) ** 2 < cube_err else cube


def _lerp(a, b, t: float):
    return (
        int(round(a[0] + (b[0] - a[0]) * t)),
        int(round(a[1] + (b[1] - a[1]) * t)),
        int(round(a[2] + (b[2] - a[2]) * t)),
    )


def _seq(col, truecolor):
    if truecolor:
        return f"\x1b[38;2;{col[0]};{col[1]};{col[2]}m"
    return f"\x1b[38;5;{_nearest_256(*col)}m"


def _star_at(row: int, col: int, density: float):
    h = ((row * 73856093) ^ (col * 19349663)) & 0xFFFFFFFF
    if (h % 1000) < density * 1000:
        glyph = STAR_GLYPHS[(h >> 10) % len(STAR_GLYPHS)]
        return glyph, _lerp(STAR_LO, STAR_HI, ((h >> 14) & 0xFF) / 255.0)
    return None


# ==========================
# ===  Sphere sampling   ===
# ==========================


def _project(width, height, rx, ry, lon0, lat0, tex):
    """Return (inside, z, brightness, is_ocean, rgb) on a width x height grid."""
    th, tw = tex.shape[:2]
    cx, cy = (width - 1) / 2.0, (height - 1) / 2.0
    NX, NY = np.meshgrid((np.arange(width) - cx) / rx, (np.arange(height) - cy) / ry)
    r2 = NX * NX + NY * NY
    inside = r2 <= 1.0
    z = np.sqrt(np.clip(1.0 - r2, 0.0, None))

    Y, Z = -NY, z
    t = math.radians(lat0)
    Y2 = Y * math.cos(t) - Z * math.sin(t)
    Z2 = Y * math.sin(t) + Z * math.cos(t)
    lat = np.arcsin(np.clip(Y2, -1.0, 1.0))
    lon = np.arctan2(NX, Z2) + math.radians(lon0)
    u = (lon / (2 * math.pi) + 0.5) % 1.0
    v = np.clip(0.5 - lat / math.pi, 0.0, 1.0)
    rgb = tex[
        np.clip((v * (th - 1)).astype(int), 0, th - 1),
        np.clip((u * (tw - 1)).astype(int), 0, tw - 1),
    ].astype(np.float32)
    R, G, B = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    lum = 0.2126 * R + 0.7152 * G + 0.0722 * B
    is_ocean = B > (R + 8)
    ocean_b = 0.24 + 0.30 * np.clip(lum / 80.0, 0.0, 1.0)
    land_b = 0.50 + 0.50 * np.clip((lum - 55.0) / 190.0, 0.0, 1.0)
    bright = np.where(is_ocean, ocean_b, land_b)
    bright = np.clip(bright * (0.62 + 0.38 * z), 0.0, 1.0)
    return inside, z, bright, is_ocean, rgb


def _boost(r, g, b, sat=1.9, gain=1.35, lift=20):
    """Push texture colour toward map-like saturation + brightness. Blue Marble
    is dark, so lift the shadows or the ocean reads near-black."""
    m = (r + g + b) / 3.0
    r, g, b = m + (r - m) * sat, m + (g - m) * sat, m + (b - m) * sat
    return (
        max(0, min(255, int(r * gain + lift))),
        max(0, min(255, int(g * gain + lift))),
        max(0, min(255, int(b * gain + lift))),
    )


def cell_color(rgb, is_ocean, bright, z, tint):
    shade = 0.64 + 0.36 * z  # mild limb darkening; keep the rim from going black
    if tint == "blue":
        a, b = (OCEAN_RGB if is_ocean else LAND_RGB)
        c = _lerp(a, b, float(bright))
    else:  # natural map colours straight from the Blue Marble texture
        c = _boost(float(rgb[0]), float(rgb[1]), float(rgb[2]))
    return (int(c[0] * shade), int(c[1] * shade), int(c[2] * shade))


# ==========================
# ===  Renderers         ===
# ==========================


def render_ramp(tex, size, lon0, lat0, ramp, color, stars, ring, aspect, tint):
    rx = size / 2.0
    ry = rx / aspect
    width = int(round(2 * rx)) + 2
    height = int(round(2 * ry)) + 2
    inside, z, bright, is_ocean, rgb = _project(width, height, rx, ry, lon0, lat0, tex)
    nramp = len(ramp)
    idx = np.clip((bright * (nramp - 1)).round().astype(int), 0, nramp - 1)
    # limb ring: inside but near the rim
    yy, xx = np.mgrid[0:height, 0:width]
    rr = ((xx - (width - 1) / 2) / rx) ** 2 + ((yy - (height - 1) / 2) / ry) ** 2
    ring_band = inside & (rr >= 0.975 * 0.975)

    truecolor = color == "truecolor"
    mono = color == "none"
    out = []
    for r in range(height):
        line, last = [], None
        for c in range(width):
            if inside[r, c]:
                if ring and ring_band[r, c]:
                    glyph, col = "·", RING_RGB
                else:
                    glyph = ramp[idx[r, c]]
                    if glyph == " ":
                        glyph = "."
                    col = cell_color(rgb[r, c], is_ocean[r, c], bright[r, c], z[r, c], tint)
            else:
                star = _star_at(r, c, stars)
                if star is None:
                    line.append(" ")
                    continue
                glyph, col = star
            if mono:
                line.append(glyph)
                continue
            if col != last:
                last = col
                line.append(_seq(col, truecolor))
            line.append(glyph)
        if not mono:
            line.append("\x1b[0m")
        out.append("".join(line))
    return out, width


# Braille dot bit layout (col, row) -> bit value.
_BRAILLE_BITS = ((0x01, 0x08), (0x02, 0x10), (0x04, 0x20), (0x40, 0x80))
# 4x4 Bayer matrix for ordered dithering, normalised to (0,1).
_BAYER = np.array(
    [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], dtype=np.float32
) / 16.0


def render_braille(tex, size, lon0, lat0, color, stars, ring, aspect, tint):
    """Sub-pixel render: each cell is a 2x4 Braille dot matrix. Dots fill nearly
    solid (so the globe reads as a filled map); colour carries land/sea/ice."""
    width = int(round(size)) + 2
    height = int(round(size / aspect)) + 2
    sw, sh = width * 2, height * 4
    rx, ry = sw / 2.0, sh / 2.0
    inside, z, bright, is_ocean, rgb = _project(sw, sh, rx, ry, lon0, lat0, tex)

    yy, xx = np.mgrid[0:sh, 0:sw]
    rr = ((xx - (sw - 1) / 2) / rx) ** 2 + ((yy - (sh - 1) / 2) / ry) ** 2
    ring_band = inside & (rr >= 0.985 * 0.985)

    thr = _BAYER[yy % 4, xx % 4]
    fill = np.clip(0.5 + 0.5 * bright, 0.0, 1.0)  # near-solid; modulate texture
    dot = inside & (fill > thr)

    truecolor = color == "truecolor"
    mono = color == "none"
    out = []
    for r in range(height):
        line, last = [], None
        for c in range(width):
            bits = 0
            for dy in range(4):
                for dx in range(2):
                    sy, sx = r * 4 + dy, c * 2 + dx
                    if dot[sy, sx] or (ring and ring_band[sy, sx]):
                        bits |= _BRAILLE_BITS[dy][dx]
            cy, cx = r * 4 + 2, c * 2  # cell-centre sample for colour/region
            if bits:
                if ring and ring_band[cy, cx] and not inside[cy, cx]:
                    col = RING_RGB
                else:
                    col = cell_color(
                        rgb[cy, cx], bool(is_ocean[cy, cx]),
                        float(bright[cy, cx]), float(z[cy, cx]), tint,
                    )
                glyph = chr(0x2800 + bits)
            else:
                star = _star_at(r, c, stars) if not inside[cy, cx] else None
                if star is None:
                    line.append(" ")
                    continue
                glyph, col = star
            if mono:
                line.append(glyph)
                continue
            if col != last:
                last = col
                line.append(_seq(col, truecolor))
            line.append(glyph)
        if not mono:
            line.append("\x1b[0m")
        out.append("".join(line))
    return out, width


def _center(text, width, color):
    pad = max(0, (width - len(text)) // 2)
    line = " " * pad + text
    if color == "none" or not text:
        return line
    return _seq(LABEL_RGB, color == "truecolor") + line + "\x1b[0m"


def build_frame(tex, args, status=None):
    if args.glyphs == "braille":
        body, width = render_braille(
            tex, args.size, args.lon, args.lat, args.color,
            0.0 if args.no_stars else args.stars, not args.no_ring, args.aspect, args.tint,
        )
    else:
        ramp = args.ramp or (ASCII_RAMP if args.glyphs == "ascii" else UNICODE_RAMP)
        body, width = render_ramp(
            tex, args.size, args.lon, args.lat, ramp, args.color,
            0.0 if args.no_stars else args.stars, not args.no_ring, args.aspect, args.tint,
        )
    lines = []
    if not args.no_labels:
        lines += [_center(args.top, width, args.color), ""]
    lines += body
    if not args.no_labels:
        lines += ["", _center(args.bottom, width, args.color)]
    if status is not None:
        lines.append(_center(status, width, args.color))
    return "\n".join(lines)


# ==========================
# ===  Sizing / colour   ===
# ==========================


def auto_size(aspect: float) -> int:
    cols, rows = shutil.get_terminal_size((100, 40))
    return max(20, min(cols - 2, int((rows - 6) * aspect)))


def resolve_color(choice: str) -> str:
    if choice != "auto":
        return choice
    ct = os.environ.get("COLORTERM", "").lower()
    return "truecolor" if ct in ("truecolor", "24bit") else "256"


# ==========================
# ===  Interactive mode  ===
# ==========================

HELP = "drag/hjkl spin · wheel/+- zoom · g glyphs · space auto · r reset · q quit"


def _parse_input(buf):
    """Yield ('key', ch) and ('mouse', btn, x, y) events from a raw read."""
    i, n = 0, len(buf)
    while i < n:
        ch = buf[i]
        if ch == "\x1b" and buf[i + 1 : i + 2] == "[":
            if buf[i + 2 : i + 3] == "<":  # SGR mouse: ESC[<b;x;y(M|m)
                j = i + 3
                while j < n and buf[j] not in "Mm":
                    j += 1
                try:
                    b, x, y = buf[i + 3 : j].split(";")
                    yield ("mouse", int(b), int(x), int(y), buf[j])
                except ValueError:
                    pass
                i = j + 1
                continue
            if buf[i + 2 : i + 3] in "ABCD":  # arrow
                yield ("key", "\x1b[" + buf[i + 2])
                i += 3
                continue
            i += 1
            continue
        yield ("key", ch)
        i += 1


def interactive(tex, args):
    import select
    import termios
    import tty

    fd = sys.stdin.fileno()
    if not os.isatty(fd):
        sys.exit("interactive mode needs a real terminal (stdin is not a tty)")
    old = termios.tcgetattr(fd)
    start = (args.lon, args.lat, args.size)
    modes = ["braille", "unicode", "ascii"]
    autospin = False
    drag = None  # last (x, y) while dragging
    try:
        tty.setcbreak(fd)
        sys.stdout.write("\x1b[2J\x1b[?25l\x1b[?1000h\x1b[?1002h\x1b[?1006h")
        while True:
            status = f"{args.glyphs}  lon {args.lon:>4.0f} lat {args.lat:>3.0f} sz {args.size}  {HELP}"
            sys.stdout.write("\x1b[H" + build_frame(tex, args, status))
            sys.stdout.flush()
            timeout = (1.0 / max(args.fps, 1.0)) if autospin else None
            if select.select([fd], [], [], timeout)[0]:
                buf = os.read(fd, 256).decode(errors="ignore")
                for ev in _parse_input(buf):
                    if ev[0] == "mouse":
                        _, b, x, y, press = ev
                        if b == 64:
                            args.size += 4
                        elif b == 65:
                            args.size = max(20, args.size - 4)
                        elif press == "m":
                            drag = None
                        elif b in (32, 0):  # left press / drag
                            if drag is not None:
                                args.lon = (args.lon - (x - drag[0]) * 2) % 360
                                args.lat = max(-90, min(90, args.lat + (y - drag[1]) * 2))
                            drag = (x, y)
                        continue
                    k = ev[1]
                    if k in ("q", "\x1b"):
                        raise KeyboardInterrupt
                    elif k in ("h", "\x1b[D"):
                        args.lon = (args.lon - args.step) % 360
                    elif k in ("l", "\x1b[C"):
                        args.lon = (args.lon + args.step) % 360
                    elif k in ("k", "\x1b[A"):
                        args.lat = min(90, args.lat + args.step)
                    elif k in ("j", "\x1b[B"):
                        args.lat = max(-90, args.lat - args.step)
                    elif k in ("+", "="):
                        args.size += 4
                    elif k in ("-", "_"):
                        args.size = max(20, args.size - 4)
                    elif k == "g":
                        args.glyphs = modes[(modes.index(args.glyphs) + 1) % len(modes)]
                    elif k == " ":
                        autospin = not autospin
                    elif k == "r":
                        args.lon, args.lat, args.size = start
                        autospin = False
            if autospin:
                args.lon = (args.lon + args.step) % 360
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\x1b[?1000l\x1b[?1002l\x1b[?1006l\x1b[?25h\x1b[0m\n")
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        sys.stdout.flush()


# ==========================
# ===  Entry point       ===
# ==========================


def main():
    p = argparse.ArgumentParser(description="UTF-8 Earth poster for the terminal")
    p.add_argument("--glyphs", choices=["braille", "unicode", "ascii"], default="braille")
    p.add_argument("--tint", choices=["natural", "blue"], default="natural",
                   help="natural = real map colours from the texture; blue = stylised")
    p.add_argument("--size", type=int, default=0, help="disc diameter in columns (0 = fit terminal)")
    p.add_argument("--lon", type=float, default=-30.0, help="central longitude (spin)")
    p.add_argument("--lat", type=float, default=18.0, help="axial tilt / view latitude")
    p.add_argument("--aspect", type=float, default=2.0, help="cell height:width ratio")
    p.add_argument("--ramp", default="", help="override glyph ramp dark->bright")
    p.add_argument("--color", choices=["auto", "256", "truecolor", "none"], default="auto")
    p.add_argument("--stars", type=float, default=0.03, help="starfield density 0..1")
    p.add_argument("--no-stars", action="store_true")
    p.add_argument("--no-ring", action="store_true")
    p.add_argument("--no-labels", action="store_true")
    p.add_argument("--top", default="THAT'S NO EARTH!")
    p.add_argument("--bottom", default="IT'S A SPACE STATION.")
    p.add_argument("-i", "--interactive", action="store_true", help="drive with keyboard + mouse")
    p.add_argument("--spin", action="store_true", help="auto-rotate instead of printing once")
    p.add_argument("--fps", type=float, default=12.0)
    p.add_argument("--step", type=float, default=6.0, help="degrees per spin/key step")
    args = p.parse_args()

    args.color = resolve_color(args.color)
    if args.size <= 0:
        args.size = auto_size(args.aspect)
    tex = load_texture(fetch_texture())

    if args.interactive:
        interactive(tex, args)
        return
    if not args.spin:
        print(build_frame(tex, args))
        return
    delay = 1.0 / max(args.fps, 1.0)
    try:
        sys.stdout.write("\x1b[2J\x1b[?25l")
        while True:
            args.lon = (args.lon + args.step) % 360
            sys.stdout.write("\x1b[H" + build_frame(tex, args))
            sys.stdout.flush()
            time.sleep(delay)
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\x1b[?25h\x1b[0m\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
