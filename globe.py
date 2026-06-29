#!/usr/bin/env python3.12
"""Render Earth as an orthographic ASCII disc in the terminal.

Inspired by the "that's no earth! / it's a space station" poster: a real
equirectangular Earth texture is back-projected onto a sphere, sampled per
terminal cell, mapped to a dense character ramp and recoloured into the poster's
cool blue/grey palette, with a limb ring, scattered stars and captions.

Modes: print once (default), --spin (auto rotate), -i/--interactive (drive it
with the keyboard).
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

# NASA Blue Marble "land + shallow topography", public domain. 2048x1024
# equirectangular. Small enough (~240 KB) to cache once and reuse.
TEXTURE_URL = (
    "https://eoimages.gsfc.nasa.gov/images/imagerecords/"
    "57000/57752/land_shallow_topo_2048.jpg"
)
CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "ascii-earth"
CACHE_FILE = CACHE_DIR / "land_shallow_topo_2048.jpg"


def fetch_texture(url: str = TEXTURE_URL, dest: Path = CACHE_FILE) -> Path:
    """Download the Earth texture into the cache once; reuse afterwards."""
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "ascii-earth/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r, open(dest, "wb") as f:
            f.write(r.read())
    except Exception as exc:  # noqa: BLE001 - want a friendly message, not a trace
        if dest.exists():
            dest.unlink(missing_ok=True)
        sys.exit(
            f"could not fetch Earth texture ({exc}).\n"
            f"download it manually to {dest} from:\n  {url}"
        )
    return dest


def load_texture(path: Path) -> np.ndarray:
    """Return the texture as an (H, W, 3) uint8 array."""
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.uint8)


# ==========================
# ===  Palette (sampled  ===
# ===  from the poster)   ===
# ==========================

# Density ramp dark -> bright. Paul Bourke's ladder, but with the grid/line
# punctuation (?[]{}()\/|_-<>) stripped out: on big flat ocean areas those line
# up into ugly bands of "?????" / "____". What's left is the letter-weighted
# weave the source poster actually uses, ordered dark -> dense.
RAMP = " .,;:~=+tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"

# Anchors measured straight off the source image (low -> high brightness).
OCEAN_RGB = ((20, 35, 50), (141, 172, 193))
LAND_RGB = ((133, 146, 141), (247, 250, 243))
RING_RGB = (236, 242, 244)
STAR_LO, STAR_HI = (44, 48, 58), (236, 240, 248)
LABEL_RGB = (235, 240, 244)

STAR_GLYPHS = ".`'+*"

# 6x6x6 xterm cube levels, for the 256-colour fallback.
_CUBE = (0, 95, 135, 175, 215, 255)


def _nearest_256(r: int, g: int, b: int) -> int:
    """Closest xterm-256 code to an RGB triple (cube + grey ramp)."""

    def idx(v):
        # nearest cube level index
        best, bi = 1 << 30, 0
        for i, c in enumerate(_CUBE):
            d = (v - c) * (v - c)
            if d < best:
                best, bi = d, i
        return bi

    ri, gi, bi = idx(r), idx(g), idx(b)
    cube = 16 + 36 * ri + 6 * gi + bi
    cr, cg, cb = _CUBE[ri], _CUBE[gi], _CUBE[bi]
    cube_err = (cr - r) ** 2 + (cg - g) ** 2 + (cb - b) ** 2
    # grey ramp 232..255
    grey = round((r + g + b) / 3)
    gi2 = min(23, max(0, round((grey - 8) / 10)))
    gv = 8 + gi2 * 10
    grey_err = 3 * (gv - grey) ** 2
    return (232 + gi2) if grey_err < cube_err else cube


def _lerp(a, b, t: float):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


# ==========================
# ===  Core rendering    ===
# ==========================


def _star_at(row: int, col: int, density: float):
    """Deterministic sparse starfield so frames are stable."""
    h = ((row * 73856093) ^ (col * 19349663)) & 0xFFFFFFFF
    if (h % 1000) < density * 1000:
        glyph = STAR_GLYPHS[(h >> 10) % len(STAR_GLYPHS)]
        t = ((h >> 14) & 0xFF) / 255.0
        return glyph, _lerp(STAR_LO, STAR_HI, t)
    return None


def render(tex, size, lon0, lat0, ramp, color, stars, ring, aspect):
    th, tw = tex.shape[:2]
    rx = size / 2.0
    ry = rx / aspect  # cells are taller than wide; keep the disc round

    width = int(round(2 * rx)) + 2
    height = int(round(2 * ry)) + 2
    cx = (width - 1) / 2.0
    cy = (height - 1) / 2.0

    cols = np.arange(width)
    rows = np.arange(height)
    NX, NY = np.meshgrid((cols - cx) / rx, (rows - cy) / ry)
    r2 = NX * NX + NY * NY
    inside = r2 <= 1.0
    z = np.sqrt(np.clip(1.0 - r2, 0.0, None))

    # Back-project to the sphere, tilt about X, read lat/lon, sample the texture.
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

    # Per-surface density windows: ocean = mid weave, land = bright + dense.
    ocean_b = 0.24 + 0.30 * np.clip(lum / 80.0, 0.0, 1.0)
    land_b = 0.50 + 0.50 * np.clip((lum - 55.0) / 190.0, 0.0, 1.0)
    bright = np.where(is_ocean, ocean_b, land_b)
    bright = np.clip(bright * (0.62 + 0.38 * z), 0.0, 1.0)  # mild limb darkening

    nramp = len(ramp)
    idx = np.clip((bright * (nramp - 1)).round().astype(int), 0, nramp - 1)
    ring_band = inside & (r2 >= 0.975 * 0.975)

    truecolor = color == "truecolor"
    mono = color == "none"

    out = []
    for r in range(height):
        line = []
        last = None  # current colour for run-length coalescing
        for c in range(width):
            if inside[r, c]:
                if ring and ring_band[r, c]:
                    glyph, col = ".", RING_RGB
                else:
                    glyph = ramp[idx[r, c]]
                    if glyph == " ":
                        glyph = "."
                    a, b = (OCEAN_RGB if is_ocean[r, c] else LAND_RGB)
                    col = _lerp(a, b, float(bright[r, c]))
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
                if truecolor:
                    line.append(f"\x1b[38;2;{col[0]};{col[1]};{col[2]}m")
                else:
                    line.append(f"\x1b[38;5;{_nearest_256(*col)}m")
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
    if color == "truecolor":
        c = LABEL_RGB
        return f"\x1b[38;2;{c[0]};{c[1]};{c[2]}m{line}\x1b[0m"
    return f"\x1b[38;5;{_nearest_256(*LABEL_RGB)}m{line}\x1b[0m"


def build_frame(tex, args, status=None):
    body, width = render(
        tex,
        size=args.size,
        lon0=args.lon,
        lat0=args.lat,
        ramp=args.ramp,
        color=args.color,
        stars=0.0 if args.no_stars else args.stars,
        ring=not args.no_ring,
        aspect=args.aspect,
    )
    lines = []
    if not args.no_labels:
        lines.append(_center(args.top, width, args.color))
        lines.append("")
    lines.extend(body)
    if not args.no_labels:
        lines.append("")
        lines.append(_center(args.bottom, width, args.color))
    if status is not None:
        lines.append(_center(status, width, args.color))
    return "\n".join(lines)


# ==========================
# ===  Sizing / colour   ===
# ==========================


def auto_size(aspect: float) -> int:
    """Largest disc that fits the current terminal (cols and rows)."""
    cols, rows = shutil.get_terminal_size((100, 40))
    by_w = cols - 2
    by_h = int((rows - 6) * aspect)  # rows -> diameter (disc height = size/aspect)
    return max(20, min(by_w, by_h))


def resolve_color(choice: str) -> str:
    if choice != "auto":
        return choice
    ct = os.environ.get("COLORTERM", "").lower()
    return "truecolor" if ct in ("truecolor", "24bit") else "256"


# ==========================
# ===  Interactive mode  ===
# ==========================

HELP = "hjkl/arrows spin · +/- zoom · space auto · r reset · q quit"


def interactive(tex, args):
    import select
    import termios
    import tty

    fd = sys.stdin.fileno()
    if not os.isatty(fd):
        sys.exit("interactive mode needs a real terminal (stdin is not a tty)")
    old = termios.tcgetattr(fd)
    start = (args.lon, args.lat, args.size)
    autospin = False
    try:
        tty.setcbreak(fd)
        sys.stdout.write("\x1b[2J\x1b[?25l")
        while True:
            status = f"lon {args.lon:>4.0f}  lat {args.lat:>3.0f}  size {args.size}   {HELP}"
            sys.stdout.write("\x1b[H" + build_frame(tex, args, status))
            sys.stdout.flush()
            timeout = (1.0 / max(args.fps, 1.0)) if autospin else None
            if select.select([fd], [], [], timeout)[0]:
                ch = os.read(fd, 3).decode(errors="ignore")
                if ch in ("q", "\x1b") and len(ch) == 1:
                    break
                elif ch in ("h", "\x1b[D"):
                    args.lon = (args.lon - args.step) % 360
                elif ch in ("l", "\x1b[C"):
                    args.lon = (args.lon + args.step) % 360
                elif ch in ("k", "\x1b[A"):
                    args.lat = min(90, args.lat + args.step)
                elif ch in ("j", "\x1b[B"):
                    args.lat = max(-90, args.lat - args.step)
                elif ch in ("+", "="):
                    args.size += 4
                elif ch in ("-", "_"):
                    args.size = max(20, args.size - 4)
                elif ch == " ":
                    autospin = not autospin
                elif ch == "r":
                    args.lon, args.lat, args.size = start
                    autospin = False
            if autospin:
                args.lon = (args.lon + args.step) % 360
    except KeyboardInterrupt:
        pass
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        sys.stdout.write("\x1b[?25h\x1b[0m\n")
        sys.stdout.flush()


# ==========================
# ===  Entry point       ===
# ==========================


def main():
    p = argparse.ArgumentParser(description="ASCII Earth poster for the terminal")
    p.add_argument("--size", type=int, default=0, help="disc diameter in columns (0 = fit terminal)")
    p.add_argument("--lon", type=float, default=-30.0, help="central longitude (spin)")
    p.add_argument("--lat", type=float, default=18.0, help="axial tilt / view latitude")
    p.add_argument("--aspect", type=float, default=2.0, help="cell height:width ratio")
    p.add_argument("--ramp", default=RAMP, help="density ramp dark->bright")
    p.add_argument("--color", choices=["auto", "256", "truecolor", "none"], default="auto")
    p.add_argument("--stars", type=float, default=0.03, help="starfield density 0..1")
    p.add_argument("--no-stars", action="store_true")
    p.add_argument("--no-ring", action="store_true")
    p.add_argument("--no-labels", action="store_true")
    p.add_argument("--top", default="THAT'S NO EARTH!")
    p.add_argument("--bottom", default="IT'S A SPACE STATION.")
    p.add_argument("-i", "--interactive", action="store_true", help="drive it with the keyboard")
    p.add_argument("--spin", action="store_true", help="auto-rotate instead of printing once")
    p.add_argument("--fps", type=float, default=12.0, help="frames/sec when spinning")
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
