#!/usr/bin/env python3.12
"""Render Earth as an orthographic ASCII disc in the terminal.

Inspired by the "that's no earth! / it's a space station" poster: a real
equirectangular Earth texture is back-projected onto a sphere, sampled per
terminal cell, mapped to a density ramp and recoloured into a blue/white
palette, with a limb ring, scattered stars and captions.
"""

import argparse
import hashlib
import math
import os
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
    img = Image.open(path).convert("RGB")
    return np.asarray(img, dtype=np.uint8)


# ==========================
# ===  Colour palettes   ===
# ==========================

# Density ramp, dark -> bright. Tuned to read like the source poster.
DEFAULT_RAMP = " .,:;-~+oszYHMNDQO@"

# 256-colour ladders. Ocean stays blue, land goes pale blue -> white, so the
# globe reads as the stylised sea/land contrast instead of muddy satellite RGB.
OCEAN_256 = [17, 18, 19, 20, 25, 26, 32, 39]
LAND_256 = [60, 67, 74, 110, 152, 188, 195, 255]

# Truecolor anchors (low -> high brightness) interpolated per cell.
OCEAN_RGB = ((6, 12, 38), (60, 150, 230))
LAND_RGB = ((70, 92, 120), (240, 248, 255))
RING_RGB = (200, 214, 240)
STAR_RGB = (150, 165, 200)

RING_256 = 252
STAR_256 = 145

STAR_GLYPHS = ".`'+*"


def _lerp_rgb(a, b, t: float):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


# ==========================
# ===  Core rendering    ===
# ==========================


def _star_at(row: int, col: int, density: float) -> str:
    """Deterministic sparse starfield so the poster is reproducible."""
    h = (row * 73856093) ^ (col * 19349663)
    h &= 0xFFFFFFFF
    if (h % 1000) < density * 1000:
        return STAR_GLYPHS[(h >> 10) % len(STAR_GLYPHS)]
    return " "


def render(
    tex: np.ndarray,
    size: int,
    lon0: float,
    lat0: float,
    ramp: str,
    color: str,
    stars: float,
    ring: bool,
) -> str:
    th, tw = tex.shape[:2]

    # Terminal cells are ~twice as tall as wide; halve the vertical radius so
    # the disc renders round rather than egg-shaped.
    rx = size / 2.0
    ry = rx / 2.0

    width = int(round(2 * rx)) + 2
    height = int(round(2 * ry)) + 2
    cx = (width - 1) / 2.0
    cy = (height - 1) / 2.0

    cols = np.arange(width)
    rows = np.arange(height)
    nx = (cols - cx) / rx
    ny = (rows - cy) / ry
    NX, NY = np.meshgrid(nx, ny)
    r2 = NX * NX + NY * NY

    inside = r2 <= 1.0
    z = np.sqrt(np.clip(1.0 - r2, 0.0, None))

    # Back-project screen point -> sphere, apply axial tilt about X, then read
    # latitude/longitude and sample the equirectangular texture.
    X = NX
    Y = -NY
    Z = z
    t = math.radians(lat0)
    Y2 = Y * math.cos(t) - Z * math.sin(t)
    Z2 = Y * math.sin(t) + Z * math.cos(t)
    lat = np.arcsin(np.clip(Y2, -1.0, 1.0))
    lon = np.arctan2(X, Z2) + math.radians(lon0)

    u = (lon / (2 * math.pi) + 0.5) % 1.0
    v = np.clip(0.5 - lat / math.pi, 0.0, 1.0)
    tex_x = np.clip((u * (tw - 1)).astype(int), 0, tw - 1)
    tex_y = np.clip((v * (th - 1)).astype(int), 0, th - 1)
    rgb = tex[tex_y, tex_x].astype(np.float32)
    R, G, B = rgb[..., 0], rgb[..., 1], rgb[..., 2]

    lum = 0.2126 * R + 0.7152 * G + 0.0722 * B
    is_ocean = B > (R + 8)

    # Blue Marble ocean is near-black, so a raw luminance ramp erases the sea.
    # Remap each surface into its own density window instead: ocean shows a
    # mid-density blue weave, land a bright dense one -- matching the poster.
    ocean_b = 0.24 + 0.28 * np.clip(lum / 80.0, 0.0, 1.0)
    land_b = 0.50 + 0.50 * np.clip((lum - 55.0) / 190.0, 0.0, 1.0)
    bright = np.where(is_ocean, ocean_b, land_b)

    # Gentle limb darkening for curvature; kept mild so the sea stays readable.
    shade = 0.62 + 0.38 * z
    bright = np.clip(bright * shade, 0.0, 1.0)
    lum_s = bright * 255.0

    nramp = len(ramp)
    idx = np.clip((bright * (nramp - 1)).round().astype(int), 0, nramp - 1)

    # Thin, bright limb so the globe reads as a clean disc against space.
    ring_band = (r2 <= 1.0) & (r2 >= 0.975 * 0.975)

    out_lines = []
    truecolor = color == "truecolor"
    use_color = color != "none"

    for r in range(height):
        line = []
        for c in range(width):
            if inside[r, c]:
                if ring and ring_band[r, c]:
                    glyph = "."
                    if not use_color:
                        line.append(glyph)
                    elif truecolor:
                        line.append(_ansi_true(glyph, RING_RGB))
                    else:
                        line.append(_ansi_256(glyph, RING_256))
                    continue
                glyph = ramp[idx[r, c]]
                if glyph == " ":
                    glyph = "."
                if not use_color:
                    line.append(glyph)
                    continue
                bright = lum_s[r, c] / 255.0
                if truecolor:
                    anchors = OCEAN_RGB if is_ocean[r, c] else LAND_RGB
                    col_rgb = _lerp_rgb(anchors[0], anchors[1], bright)
                    line.append(_ansi_true(glyph, col_rgb))
                else:
                    ladder = OCEAN_256 if is_ocean[r, c] else LAND_256
                    code = ladder[min(int(bright * len(ladder)), len(ladder) - 1)]
                    line.append(_ansi_256(glyph, code))
            else:
                glyph = _star_at(r, c, stars)
                if glyph == " " or not use_color:
                    line.append(glyph)
                elif truecolor:
                    line.append(_ansi_true(glyph, STAR_RGB))
                else:
                    line.append(_ansi_256(glyph, STAR_256))
        out_lines.append("".join(line))

    return "\n".join(out_lines)


def _ansi_256(glyph: str, code: int) -> str:
    return f"\x1b[38;5;{code}m{glyph}\x1b[0m"


def _ansi_true(glyph: str, rgb) -> str:
    return f"\x1b[38;2;{rgb[0]};{rgb[1]};{rgb[2]}m{glyph}\x1b[0m"


def _center(text: str, width: int, color: str) -> str:
    pad = max(0, (width - len(text)) // 2)
    line = " " * pad + text
    if color == "none":
        return line
    if color == "truecolor":
        return f"\x1b[38;2;230;230;240m{line}\x1b[0m"
    return f"\x1b[38;5;253m{line}\x1b[0m"


# ==========================
# ===  Entry point       ===
# ==========================


def build_poster(args) -> str:
    tex = load_texture(fetch_texture())
    body = render(
        tex,
        size=args.size,
        lon0=args.lon,
        lat0=args.lat,
        ramp=args.ramp,
        color=args.color,
        stars=0.0 if args.no_stars else args.stars,
        ring=not args.no_ring,
    )
    width = len(body.split("\n", 1)[0])
    # visible width without ANSI: derive from first rendered row length in cells
    cell_width = int(round(args.size)) + 2
    parts = []
    if not args.no_labels:
        parts.append(_center(args.top, cell_width, args.color))
        parts.append("")
    parts.append(body)
    if not args.no_labels:
        parts.append("")
        parts.append(_center(args.bottom, cell_width, args.color))
    return "\n".join(parts)


def main():
    p = argparse.ArgumentParser(description="ASCII Earth poster for the terminal")
    p.add_argument("--size", type=int, default=72, help="disc diameter in columns")
    p.add_argument("--lon", type=float, default=-30.0, help="central longitude (spin)")
    p.add_argument("--lat", type=float, default=18.0, help="axial tilt / view latitude")
    p.add_argument("--ramp", default=DEFAULT_RAMP, help="density ramp dark->bright")
    p.add_argument(
        "--color",
        choices=["256", "truecolor", "none"],
        default="256",
        help="colour mode (256 is safe under tmux/mosh)",
    )
    p.add_argument("--stars", type=float, default=0.03, help="starfield density 0..1")
    p.add_argument("--no-stars", action="store_true")
    p.add_argument("--no-ring", action="store_true")
    p.add_argument("--no-labels", action="store_true")
    p.add_argument("--top", default="THAT'S NO EARTH!")
    p.add_argument("--bottom", default="IT'S A SPACE STATION.")
    p.add_argument(
        "--spin",
        action="store_true",
        help="animate rotation instead of printing once",
    )
    p.add_argument("--fps", type=float, default=12.0, help="frames/sec when spinning")
    p.add_argument("--step", type=float, default=4.0, help="degrees per spin frame")
    args = p.parse_args()

    if not args.spin:
        print(build_poster(args))
        return

    # Spin mode: redraw in place. lon advances each frame.
    delay = 1.0 / max(args.fps, 1.0)
    try:
        sys.stdout.write("\x1b[2J\x1b[?25l")  # clear + hide cursor
        while True:
            args.lon = (args.lon + args.step) % 360
            frame = build_poster(args)
            sys.stdout.write("\x1b[H" + frame)
            sys.stdout.flush()
            time.sleep(delay)
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\x1b[?25h\n")  # show cursor
        sys.stdout.flush()


if __name__ == "__main__":
    main()
