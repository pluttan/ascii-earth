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
import datetime
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

CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "ascii-earth"

# Earth = NASA Blue Marble (public domain). All other bodies = Solar System
# Scope equirectangular textures (CC-BY 4.0), pulled via Wikimedia's stable
# Special:FilePath redirect. See README for attribution.
_NASA_EARTH = (
    "https://eoimages.gsfc.nasa.gov/images/imagerecords/"
    "57000/57752/land_shallow_topo_2048.jpg"
)
_SSS = "https://commons.wikimedia.org/wiki/Special:FilePath/Solarsystemscope_texture_2k_"

BODIES = {
    "earth":   {"url": _NASA_EARTH, "file": "earth.jpg", "ocean": True, "r": 6371},
    "sun":     {"url": _SSS + "sun.jpg", "file": "sun.jpg", "ocean": False, "r": 696340},
    "mercury": {"url": _SSS + "mercury.jpg", "file": "mercury.jpg", "ocean": False, "r": 2440},
    "venus":   {"url": _SSS + "venus_atmosphere.jpg", "file": "venus.jpg", "ocean": False, "r": 6052},
    "moon":    {"url": _SSS + "moon.jpg", "file": "moon.jpg", "ocean": False, "r": 1737},
    "mars":    {"url": _SSS + "mars.jpg", "file": "mars.jpg", "ocean": False, "r": 3390},
    "jupiter": {"url": _SSS + "jupiter.jpg", "file": "jupiter.jpg", "ocean": False, "r": 69911},
    "saturn":  {"url": _SSS + "saturn.jpg", "file": "saturn.jpg", "ocean": False, "r": 58232,
                "rings": {"inner": 1.24, "outer": 2.30, "color": (220, 200, 165)}},
    "uranus":  {"url": _SSS + "uranus.jpg", "file": "uranus.jpg", "ocean": False, "r": 25362,
                "rings": {"inner": 1.55, "outer": 1.95, "color": (120, 140, 150)}},
    "neptune": {"url": _SSS + "neptune.jpg", "file": "neptune.jpg", "ocean": False, "r": 24622},
    "ceres":   {"url": _SSS + "ceres_fictional.jpg", "file": "ceres.jpg", "ocean": False, "r": 473},
}
BODY_NAMES = list(BODIES)
_EARTH_R = 6371.0


def scaled_size(scale, body, ref):
    """Disc diameter for a body under a scaling mode. 'fit' returns None (use
    auto-fit); 'sqrt'/'real' size it by real radius relative to Earth. No upper
    cap — the viewport clips anything bigger, and capping made the Sun stick at
    the ceiling so zoom couldn't shrink it."""
    if scale == "fit":
        return None
    ratio = BODIES[body].get("r", _EARTH_R) / _EARTH_R
    s = ref * (ratio ** 0.5) if scale == "sqrt" else ref * ratio
    return int(max(5, s))

# Descriptive UA: Wikimedia blocks generic/empty agents.
_UA = "ascii-earth/1.0 (terminal globe renderer; +https://github.com/pluttan/ascii-earth)"


def fetch_texture(url: str, dest: Path) -> Path:
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    try:
        with urllib.request.urlopen(req, timeout=45) as r, open(dest, "wb") as f:
            f.write(r.read())
    except Exception as exc:  # noqa: BLE001 - friendly message, not a trace
        if dest.exists():
            dest.unlink(missing_ok=True)
        sys.exit(f"could not fetch texture ({exc}).\ndownload it to {dest} from:\n  {url}")
    return dest


def load_texture(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.uint8)


def body_texture(body: str) -> np.ndarray:
    """Fetch (cached) and load the texture for a named body."""
    info = BODIES[body]
    return load_texture(fetch_texture(info["url"], CACHE_DIR / info["file"]))


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


def _project(width, height, rx, ry, lon0, lat0, tex, ocean=True):
    """Return (inside, z, brightness, is_ocean, rgb) on a width x height grid.
    ocean=False (non-Earth bodies) disables sea detection: every cell is land
    and keeps the texture's own colour."""
    th, tw = tex.shape[:2]
    cx, cy = (width - 1) / 2.0, (height - 1) / 2.0
    NX, NY = np.meshgrid((np.arange(width) - cx) / rx, (np.arange(height) - cy) / ry)
    r2 = NX * NX + NY * NY
    inside = r2 <= 1.0
    z = np.sqrt(np.clip(1.0 - r2, 0.0, None))

    Y, Z = -NY, z
    # Negate so +lat0 looks NORTH (intuitive). Without this the tilt was
    # inverted: positive lat0 pointed south, making drag/keys feel upside down.
    t = math.radians(-lat0)
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
    is_ocean = ((B > R) & (B > G)) if ocean else np.zeros_like(R, dtype=bool)
    ocean_b = 0.24 + 0.30 * np.clip(lum / 80.0, 0.0, 1.0)
    land_b = 0.50 + 0.50 * np.clip((lum - 55.0) / 190.0, 0.0, 1.0)
    # No z term here: a radial brightness gradient drew a bright "circle" on the
    # open sea. Depth/relief come from the texture luminance alone.
    bright = np.clip(np.where(is_ocean, ocean_b, land_b), 0.0, 1.0)
    return inside, z, bright, is_ocean, rgb, lat, lon


# Saturation + a gamma LUT (<1 lifts shadows so dark ocean reads bright).
# Both are tunable from the CLI via set_color().
_SAT = 2.0
_GLUT = [int(round(255 * (i / 255.0) ** 0.6)) for i in range(256)]


def set_color(saturation: float, gamma: float):
    global _SAT, _GLUT
    _SAT = saturation
    g = max(0.05, gamma)
    _GLUT = [int(round(255 * (i / 255.0) ** g)) for i in range(256)]


def _grade(c):
    """Saturation + gamma applied to ANY colour. Going through here for every
    palette means the sat/brightness controls hit ocean, land and false-colour
    schemes alike (the ocean used to bypass them)."""
    m = (c[0] + c[1] + c[2]) / 3.0
    r = max(0, min(255, int(m + (c[0] - m) * _SAT)))
    g = max(0, min(255, int(m + (c[1] - m) * _SAT)))
    b = max(0, min(255, int(m + (c[2] - m) * _SAT)))
    return (_GLUT[r], _GLUT[g], _GLUT[b])


# Atlas-style ocean: bright blue, deep -> shallow. The raw Blue Marble ocean is
# near-black in deep water, so we restyle it like a physical map instead.
SEA_DEEP, SEA_SHALLOW = (26, 78, 150), (120, 198, 226)


def _lum(c):
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def _sea_t(bright):
    return max(0.0, min(1.0, (float(bright) - 0.24) / 0.30))


def _colormap(v, stops):
    v = max(0.0, min(1.0, v))
    n = len(stops) - 1
    f = v * n
    i = min(int(f), n - 1)
    return _lerp(stops[i], stops[i + 1], f - i)


def _pal_natural(rgb, ocean, bright):
    if ocean:
        return _lerp(SEA_DEEP, SEA_SHALLOW, _sea_t(bright))
    return (float(rgb[0]), float(rgb[1]), float(rgb[2]))


def _pal_political(rgb, ocean, bright):
    if ocean:
        return _lerp((18, 92, 178), (150, 210, 238), _sea_t(bright))
    return (float(rgb[0]), min(255.0, rgb[1] * 1.15), float(rgb[2]))  # greener land


def _pal_blue(rgb, ocean, bright):
    a, b = (OCEAN_RGB if ocean else LAND_RGB)
    return _lerp(a, b, float(bright))


def _mono(rgb, ocean, bright, lo, hi):
    v = (_lum(_pal_natural(rgb, ocean, bright)) / 255.0) ** 0.85
    return _lerp(lo, hi, v)


def _pal_inferno(rgb, ocean, bright):
    v = _lum(_pal_natural(rgb, ocean, bright)) / 255.0
    return _colormap(v, [(0, 0, 4), (40, 11, 84), (139, 41, 129),
                         (225, 82, 73), (252, 164, 38), (252, 255, 164)])


def _pal_neon(rgb, ocean, bright):
    if ocean:
        return _lerp((30, 0, 50), (255, 40, 220), _sea_t(bright))
    v = min(1.0, _lum((float(rgb[0]), float(rgb[1]), float(rgb[2]))) / 160.0)
    return _lerp((0, 40, 45), (40, 255, 210), v)


# Catppuccin Mocha accents mapped onto the globe.
_CAT_SKY, _CAT_TEAL, _CAT_GREEN = (137, 220, 235), (148, 226, 213), (166, 227, 161)
_CAT_YELLOW, _CAT_PEACH, _CAT_TEXT = (249, 226, 175), (250, 179, 135), (205, 214, 244)


def _pal_catppuccin(rgb, ocean, bright):
    if ocean:
        return _lerp((54, 70, 140), _CAT_SKY, _sea_t(bright))  # blue -> sky by depth
    r, g, b = float(rgb[0]), float(rgb[1]), float(rgb[2])
    lum = _lum(rgb)
    if lum > 170 and (max(r, g, b) - min(r, g, b)) < 45:  # bright & neutral = ice
        return _CAT_TEXT
    if g + 8 >= r:                                  # vegetation -> teal..green
        return _lerp(_CAT_TEAL, _CAT_GREEN, min(1.0, g / 190.0))
    return _lerp(_CAT_PEACH, _CAT_YELLOW, min(1.0, lum / 200.0))  # arid -> peach..yellow


# Map-style schemes plus a pile of monochrome/false-colour looks.
PALETTES = {
    "natural": _pal_natural,
    "political": _pal_political,
    "blue": _pal_blue,
    "green": lambda r, o, b: _mono(r, o, b, (0, 10, 2), (120, 255, 135)),
    "amber": lambda r, o, b: _mono(r, o, b, (8, 4, 0), (255, 188, 60)),
    "ice": lambda r, o, b: _mono(r, o, b, (4, 10, 30), (150, 205, 255)),
    "mono": lambda r, o, b: _mono(r, o, b, (10, 10, 12), (240, 242, 245)),
    "inferno": _pal_inferno,
    "neon": _pal_neon,
    "catppuccin": _pal_catppuccin,
}
PALETTE_NAMES = list(PALETTES)


def cell_color(rgb, is_ocean, bright, palette):
    # Flat shading on purpose: a radial gradient drew a bright "circle" on the
    # open sea. Depth/relief come from the texture itself. _grade applies the
    # sat/brightness controls uniformly (ocean included) — except branded
    # palettes (catppuccin), whose pastel tones must stay exact.
    base = PALETTES.get(palette, _pal_natural)(rgb, is_ocean, bright)
    if palette == "catppuccin":
        return (int(base[0]), int(base[1]), int(base[2]))
    return _grade(base)


# ==========================
# ===  Day / night       ===
# ==========================


def subsolar(dt: datetime.datetime):
    """Approximate sub-solar point (lat, lon in radians) for a UTC datetime.
    Declination from day-of-year; longitude from UTC hour (no equation-of-time,
    so it's good to ~a couple degrees — fine for a day/night terminator)."""
    n = dt.timetuple().tm_yday
    decl = math.radians(-23.44) * math.cos(math.radians(360.0 / 365.0 * (n + 10)))
    utc_h = dt.hour + dt.minute / 60.0 + dt.second / 3600.0
    sunlon = math.radians(((-15.0 * (utc_h - 12.0) + 180.0) % 360.0) - 180.0)
    return decl, sunlon


def terminator(lat, lon, decl, sunlon):
    """0 = night, 1 = day, soft band across the terminator."""
    cz = np.sin(lat) * math.sin(decl) + np.cos(lat) * math.cos(decl) * np.cos(lon - sunlon)
    return np.clip((cz + 0.12) / 0.24, 0.0, 1.0)


def _night(col, f: float, ocean: bool = False):
    """Night side goes black & white (gamma-lifted grey, f: 1 day .. 0 night).
    Ocean is kept darker than land so coastlines still read in the dark."""
    ng = (_lum(col) / 255.0) ** 0.55 * 235.0
    if ocean:
        ng *= 0.4  # night sea darker than night land
    mix = 1.0 - f
    return (
        max(0, min(255, int(col[0] * (1 - mix) + ng * mix))),
        max(0, min(255, int(col[1] * (1 - mix) + ng * mix))),
        max(0, min(255, int(col[2] * (1 - mix) + ng * mix))),
    )


# ==========================
# ===  Renderers         ===
# ==========================


def render_ramp(tex, vw, vh, rx, ry, lon0, lat0, ramp, color, stars, ring, palette, sun, ocean=True, rings=None):
    """Glyph-ramp render into a vw x vh viewport; planet centred, clipped at the
    edges, starfield everywhere outside the disc."""
    width, height = vw, vh
    inside, z, bright, is_ocean, rgb, lat, lon = _project(width, height, rx, ry, lon0, lat0, tex, ocean)
    illum = terminator(lat, lon, *sun) if sun else None
    nramp = len(ramp)
    idx = np.clip((bright * (nramp - 1)).round().astype(int), 0, nramp - 1)
    # limb ring: inside but near the rim
    yy, xx = np.mgrid[0:height, 0:width]
    rr = ((xx - (width - 1) / 2) / rx) ** 2 + ((yy - (height - 1) / 2) / ry) ** 2
    ring_band = inside & (rr >= 0.975 * 0.975)
    ring_m, ring_c = (_ring_overlay(width, height, rx, ry, lon0, lat0, rings)
                      if rings else (None, None))
    ring_glyph = ramp[int(0.72 * (nramp - 1))]

    truecolor = color == "truecolor"
    mono = color == "none"
    out = []
    for r in range(height):
        line, last = [], None
        for c in range(width):
            if ring_m is not None and ring_m[r, c]:
                rc = ring_c[r, c]
                glyph = ring_glyph
                col = (min(255, int(rc[0])), min(255, int(rc[1])), min(255, int(rc[2])))
            elif inside[r, c]:
                if ring and ring_band[r, c]:
                    glyph, col = "·", RING_RGB
                else:
                    glyph = ramp[idx[r, c]]
                    if glyph == " ":
                        glyph = "."
                    col = cell_color(rgb[r, c], is_ocean[r, c], bright[r, c], palette)
                    if illum is not None:
                        col = _night(col, float(illum[r, c]), bool(is_ocean[r, c]))
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
    return out


# Braille dot bit layout (col, row) -> bit value.
_BRAILLE_BITS = ((0x01, 0x08), (0x02, 0x10), (0x04, 0x20), (0x40, 0x80))
# 4x4 Bayer matrix for ordered dithering, normalised to (0,1).
_BAYER = np.array(
    [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], dtype=np.float32
) / 16.0


def _ring_overlay(width, height, rx, ry, lon0, lat0, rings):
    """(mask, colour) per cell for a planet's rings. Rings sit in the equatorial
    plane; tilt lat0 sets how open the ellipse is. Front arc draws over the disc,
    back arc is hidden behind the sphere (proper depth occlusion). The azimuthal
    clumping rotates with lon0 so the spin is actually visible."""
    t = math.radians(-lat0)
    s = math.sin(t)
    mask = np.zeros((height, width), dtype=bool)
    color = np.zeros((height, width, 3), dtype=np.float32)
    if abs(s) < 0.05:
        return mask, color  # edge-on: rings invisible
    cx, cy = (width - 1) / 2.0, (height - 1) / 2.0
    NX, NY = np.meshgrid((np.arange(width) - cx) / rx, (np.arange(height) - cy) / ry)
    rho = np.sqrt(NX ** 2 + (NY / s) ** 2)              # radius in the ring plane
    phi = np.arctan2(NY / s, NX)                         # azimuth in the ring plane
    az = phi + math.radians(lon0)                        # spins with the planet
    inner, outer = rings["inner"], rings["outer"]
    band = (rho >= inner) & (rho <= outer)
    depth = -NY / math.tan(t)                            # +toward camera
    disc = NX ** 2 + NY ** 2
    zsph = np.sqrt(np.clip(1.0 - disc, 0.0, None))
    mask = band & ((disc > 1.0) | (depth > zsph))        # outside disc, or in front
    base = np.array(rings["color"], dtype=np.float32)
    span = max(1e-6, outer - inner)
    rn = (rho - inner) / span                            # 0..1 across the ring
    bn = 0.40 + 0.60 * (0.5 + 0.5 * np.cos(rho * 17.0))  # sharp radial bands
    bn *= 0.7 + 0.3 * rn                                 # outer ring a touch brighter
    # Irregular azimuthal clumps (several frequencies) so rotation reads clearly.
    azmod = (0.60 + 0.22 * np.sin(az * 5.0 + 0.7) + 0.13 * np.sin(az * 13.0 + 2.1)
             + 0.09 * np.sin(az * 29.0 + 4.0))
    gap = (rn > 0.58) & (rn < 0.66)                      # Cassini-ish division
    shade = np.where(gap, 0.18, bn) * np.clip(azmod, 0.30, 1.2)
    color = base[None, None, :] * shade[..., None]
    return mask, color


def render_braille(tex, vw, vh, rx_c, ry_c, lon0, lat0, color, stars, ring, palette, sun, ocean=True, rings=None):
    """Sub-pixel render into a vw x vh viewport. The planet (radius rx_c, ry_c
    cells) is centred; anything past the viewport edge is simply clipped, and the
    whole field outside the disc is starfield."""
    width, height = vw, vh
    sw, sh = width * 2, height * 4
    rx, ry = rx_c * 2.0, ry_c * 4.0  # planet radius in sub-pixels
    inside, z, bright, is_ocean, rgb, lat, lon = _project(sw, sh, rx, ry, lon0, lat0, tex, ocean)

    yy, xx = np.mgrid[0:sh, 0:sw]
    rr = ((xx - (sw - 1) / 2) / rx) ** 2 + ((yy - (sh - 1) / 2) / ry) ** 2
    ring_band = inside & (rr >= 0.985 * 0.985)

    thr = _BAYER[yy % 4, xx % 4]
    fill = np.clip(0.5 + 0.5 * bright, 0.0, 1.0)  # near-solid; modulate texture
    dot = inside & (fill > thr)

    # Supersample colour over each cell's 2x4 sub-pixels: averages out stray
    # single land pixels (sea "spots") and the nearest-sample smear at the limb.
    ins4 = inside.reshape(height, 4, width, 2).astype(np.float32)
    wsum = np.clip(ins4.sum((1, 3)), 1.0, None)
    rgb_c = (rgb * inside[..., None]).reshape(height, 4, width, 2, 3).sum((1, 3)) / wsum[..., None]
    bright_c = (bright * inside).reshape(height, 4, width, 2).sum((1, 3)) / wsum
    # Respect the body's ocean flag: without it the Moon's bluish maria get
    # mis-tagged as sea and painted blue.
    ocean_c = (((rgb_c[..., 2] > rgb_c[..., 0]) & (rgb_c[..., 2] > rgb_c[..., 1]))
               if ocean else np.zeros((height, width), dtype=bool))
    if sun:
        illum = terminator(lat, lon, *sun)
        illum_c = (illum * inside).reshape(height, 4, width, 2).sum((1, 3)) / wsum
    else:
        illum_c = None

    ring_m, ring_c = (_ring_overlay(width, height, rx_c, ry_c, lon0, lat0, rings)
                      if rings else (None, None))

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
            if ring_m is not None and ring_m[r, c]:
                rc = ring_c[r, c]
                col = (min(255, int(rc[0])), min(255, int(rc[1])), min(255, int(rc[2])))
                glyph = "⣿"  # solid braille block = ring band
            elif bits:
                if ring and ring_band[cy, cx] and not inside[cy, cx]:
                    col = RING_RGB
                else:
                    col = cell_color(
                        rgb_c[r, c], bool(ocean_c[r, c]), float(bright_c[r, c]), palette,
                    )
                    if illum_c is not None:
                        col = _night(col, float(illum_c[r, c]), bool(ocean_c[r, c]))
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
    return out


def _center(text, width, color):
    pad = max(0, (width - len(text)) // 2)
    line = " " * pad + text
    if color == "none" or not text:
        return line
    return _seq(LABEL_RGB, color == "truecolor") + line + "\x1b[0m"


def build_frame(tex, args, status=None):
    lon0, lat0 = args.lon, args.lat
    if getattr(args, "follow", False):
        # Sun-locked, real time: centre on the actual sub-solar point. Earth
        # turns under it at the real rate -> one turn per 24h. Always day side,
        # no manual control; the clock drives it.
        decl, sunlon = subsolar(datetime.datetime.now(datetime.timezone.utc))
        lat0, lon0 = math.degrees(decl), math.degrees(sunlon)
        sun = (decl, sunlon)
    elif args.sun:
        # Recompute every frame so day/night tracks the real sun.
        sun = subsolar(datetime.datetime.now(datetime.timezone.utc))
    else:
        sun = None
    binfo = BODIES.get(getattr(args, "body", "earth"), {})
    ocean = binfo.get("ocean", True)
    rings = None if getattr(args, "no_rings", False) else binfo.get("rings")

    # Viewport = the whole terminal. Captions glue to the top and bottom rows,
    # status (interactive) to the very last row; the disc fills the middle. The
    # planet is drawn at its own size and clipped at the edges if it's bigger,
    # and the starfield fills the full viewport width.
    cols, rows = shutil.get_terminal_size((100, 40))
    labels = not args.no_labels
    n_status = len(status.split("\n")) if status is not None else 0
    disc_h = max(1, rows - (2 if labels else 0) - n_status)
    rx_c = args.size / 2.0
    ry_c = args.size / (2.0 * args.aspect)
    stars = 0.0 if args.no_stars else args.stars
    if args.glyphs == "braille":
        body = render_braille(tex, cols, disc_h, rx_c, ry_c, lon0, lat0, args.color,
                              stars, not args.no_ring, args.palette, sun, ocean, rings)
    else:
        ramp = args.ramp or (ASCII_RAMP if args.glyphs == "ascii" else UNICODE_RAMP)
        body = render_ramp(tex, cols, disc_h, rx_c, ry_c, lon0, lat0, ramp, args.color,
                           stars, not args.no_ring, args.palette, sun, ocean, rings)
    lines = []
    if labels:
        lines.append(_center(args.top, cols, args.color))
    lines += body
    if labels:
        lines.append(_center(args.bottom, cols, args.color))
    if status is not None:
        for sline in status.split("\n"):
            lines.append(_center(sline, cols, args.color))
    return "\n".join(lines)


# ==========================
# ===  Sizing / colour   ===
# ==========================


def auto_size(aspect: float) -> int:
    # Largest planet that fits the disc area (terminal minus the two caption
    # rows) with a little breathing room. Anything bigger just gets clipped.
    cols, rows = shutil.get_terminal_size((100, 40))
    return max(16, int(min(cols, (rows - 4) * aspect) * 0.94))


def resolve_color(choice: str) -> str:
    if choice != "auto":
        return choice
    ct = os.environ.get("COLORTERM", "").lower()
    return "truecolor" if ct in ("truecolor", "24bit") else "256"


# ==========================
# ===  Interactive mode  ===
# ==========================



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
    snap = {k: getattr(args, k) for k in (
        "lon", "lat", "size", "glyphs", "palette", "color", "sun", "follow",
        "saturation", "gamma", "no_stars", "no_ring", "no_labels", "body", "top",
        "bottom", "scale", "no_rings", "scale_ref")}
    modes = ["braille", "unicode", "ascii"]
    colors = ["truecolor", "256", "none"]
    autospin = False
    drag = None  # last (x, y) while dragging
    help_open = False
    HELP_LINES = [
        "ascii-earth  —  hotkeys",
        "",
        "<   /   >           previous / next body  (planets, moon, sun)",
        "m                   scale mode  (fit / sqrt / real radius)",
        "R                   planetary rings on / off",
        "arrows / h j k l    rotate   (disabled in follow)",
        "+   -               zoom",
        "space               auto-spin",
        "g                   glyph mode  (braille / unicode / ascii)",
        "p   /   P           palette  next / prev",
        "c                   colour mode  (truecolor / 256 / none)",
        "n                   day / night  (real sun)",
        "f                   follow sun  (locked day side, slow spin)",
        "s                   stars on / off",
        "o                   ring on / off",
        "b                   labels on / off",
        "[   ]               saturation  -  /  +",
        ",   .               brightness  darker / lighter",
        "r                   reset all",
        "?                   show / hide this list",
        "q  /  esc           quit",
    ]

    def cycle(seq, cur, d=1):
        return seq[(seq.index(cur) + d) % len(seq)] if cur in seq else seq[0]

    def toggle_follow():
        nonlocal autospin
        args.follow = not args.follow
        if args.follow:
            decl, _ = subsolar(datetime.datetime.now(datetime.timezone.utc))
            args.lat = math.degrees(decl)  # seasonal tilt; longitude keeps spinning
            args.sun, autospin = False, False

    def apply_scale():
        s = scaled_size(args.scale, args.body, args.scale_ref)
        if s is None:  # fit
            args.size = auto_size(args.aspect)
            ri = BODIES[args.body].get("rings")
            if ri and not args.no_rings:
                args.size = int(args.size / ri["outer"])
        else:
            args.size = s

    def zoom(d):
        cols = shutil.get_terminal_size((100, 40))[0]
        if args.scale == "fit":  # zoom this body directly
            args.size = (min(args.size + 4, 4 * cols) if d > 0 else max(20, args.size - 4))
        else:  # zoom the shared scale -> every body scales together
            args.scale_ref = max(2.0, min(args.scale_ref * (1.12 if d > 0 else 1 / 1.12), 2.0 * cols))
            apply_scale()

    def rotate(dlon=0.0, dlat=0.0):
        if args.follow:  # rotation is automatic in follow; manual is disabled
            return
        if dlon:
            args.lon = (args.lon + dlon) % 360
        if dlat:
            args.lat = max(-90, min(90, args.lat + dlat))

    try:
        tty.setcbreak(fd)
        sys.stdout.write("\x1b[2J\x1b[?25l\x1b[?1000h\x1b[?1002h\x1b[?1006h")
        while True:
            if help_open:
                cols, rows = shutil.get_terminal_size((80, 40))
                pad = max(0, (rows - len(HELP_LINES)) // 2)
                lead = max(0, (cols - 48) // 2)
                out = ["\x1b[H"] + ["\x1b[K\n"] * pad
                for ln in HELP_LINES:
                    out.append(" " * lead + ln + "\x1b[K\n")
                sys.stdout.write("".join(out) + "\x1b[J")
                sys.stdout.flush()
            else:
                bar = (f"  {args.body} · {args.scale} · sz {args.size} · {args.palette} · "
                       f"sun {'on' if args.sun else 'off'} · follow {'on' if args.follow else 'off'} · "
                       f"sat {args.saturation:.1f} gam {args.gamma:.2f}     <>body · m scale · ? keys · q")
                frame = build_frame(tex, args, bar).replace("\n", "\x1b[K\n")
                sys.stdout.write("\x1b[H" + frame + "\x1b[K\x1b[J")
                sys.stdout.flush()
            if help_open:
                timeout = None
            elif autospin:
                timeout = 1.0 / max(args.fps, 1.0)
            elif args.sun or args.follow:
                timeout = 1.0  # real-time creep (24h/turn); redraw ~1/s
            else:
                timeout = None
            if select.select([fd], [], [], timeout)[0]:
                buf = os.read(fd, 256).decode(errors="ignore")
                for ev in _parse_input(buf):
                    if ev[0] == "mouse":
                        if help_open:
                            continue
                        _, b, x, y, press = ev
                        if b == 64:
                            zoom(1)
                        elif b == 65:
                            zoom(-1)
                        elif press == "m":
                            drag = None
                        elif b in (32, 0) and not args.follow:  # drag (off in follow)
                            if drag is not None:
                                args.lon = (args.lon - (x - drag[0]) * 2) % 360
                                args.lat = max(-90, min(90, args.lat + (y - drag[1]) * 2))
                            drag = (x, y)
                        continue
                    k = ev[1]
                    if help_open:
                        if k == "q":
                            raise KeyboardInterrupt
                        help_open = False  # any key closes the list
                        sys.stdout.write("\x1b[2J")
                        continue
                    if k in ("q", "\x1b"):
                        raise KeyboardInterrupt
                    elif k == "?":
                        help_open = True
                    elif k in ("<", ">"):  # previous / next body
                        args.body = cycle(BODY_NAMES, args.body, -1 if k == "<" else 1)
                        tex = body_texture(args.body)
                        bi = BODIES[args.body]
                        args.top = bi.get("top", args.body.upper())
                        args.bottom = bi.get("bottom", "")
                        apply_scale()
                    elif k == "m":  # scale mode: fit -> sqrt -> real
                        args.scale = cycle(["fit", "sqrt", "real"], args.scale)
                        apply_scale()
                    elif k == "R":  # planetary rings on / off
                        args.no_rings = not args.no_rings
                        apply_scale()
                    elif k in ("h", "\x1b[D"):
                        rotate(dlon=-args.step)
                    elif k in ("l", "\x1b[C"):
                        rotate(dlon=args.step)
                    elif k in ("k", "\x1b[A"):
                        rotate(dlat=args.step)
                    elif k in ("j", "\x1b[B"):
                        rotate(dlat=-args.step)
                    elif k in ("+", "="):
                        zoom(1)
                    elif k in ("-", "_"):
                        zoom(-1)
                    elif k == "g":
                        args.glyphs = cycle(modes, args.glyphs)
                    elif k == "p":
                        args.palette = cycle(PALETTE_NAMES, args.palette)
                    elif k == "P":
                        args.palette = cycle(PALETTE_NAMES, args.palette, -1)
                    elif k == "c":
                        args.color = cycle(colors, args.color)
                    elif k == "n":
                        args.sun = not args.sun
                    elif k == "f":
                        toggle_follow()
                    elif k == "s":
                        args.no_stars = not args.no_stars
                    elif k == "o":
                        args.no_ring = not args.no_ring
                    elif k == "b":
                        args.no_labels = not args.no_labels
                    elif k == "]":
                        args.saturation = min(4.0, args.saturation + 0.1); set_color(args.saturation, args.gamma)
                    elif k == "[":
                        args.saturation = max(0.0, args.saturation - 0.1); set_color(args.saturation, args.gamma)
                    elif k == ".":
                        args.gamma = max(0.2, args.gamma - 0.05); set_color(args.saturation, args.gamma)
                    elif k == ",":
                        args.gamma = min(1.5, args.gamma + 0.05); set_color(args.saturation, args.gamma)
                    elif k == " ":
                        autospin = not autospin
                    elif k == "r":
                        for key, val in snap.items():
                            setattr(args, key, val)
                        set_color(args.saturation, args.gamma)
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
    p = argparse.ArgumentParser(description="UTF-8 planet renderer for the terminal")
    p.add_argument("--body", choices=BODY_NAMES, default="earth",
                   help="celestial body: " + ", ".join(BODY_NAMES))
    p.add_argument("--scale", choices=["fit", "sqrt", "real"], default="fit",
                   help="fit each body, or size by real radius (sqrt = compressed)")
    p.add_argument("--no-rings", action="store_true", help="hide planetary rings")
    p.add_argument("--glyphs", choices=["braille", "unicode", "ascii"], default="braille")
    p.add_argument("--palette", choices=PALETTE_NAMES, default="natural",
                   help="colour scheme: " + ", ".join(PALETTE_NAMES))
    p.add_argument("--saturation", type=float, default=2.1, help="colour saturation (1 = none)")
    p.add_argument("--gamma", type=float, default=0.55, help="brightness gamma (<1 = brighter)")
    p.add_argument("--size", type=int, default=0, help="disc diameter in columns (0 = fit terminal)")
    p.add_argument("--lon", type=float, default=None, help="central longitude (spin)")
    p.add_argument("--lat", type=float, default=None, help="view latitude (+north); default seasonal tilt under --sun")
    p.add_argument("--sun", action="store_true", help="real-time day/night terminator (now, UTC)")
    p.add_argument("--follow", action="store_true",
                   help="sun-locked view: always show the day side, slowly rotate the globe")
    p.add_argument("--aspect", type=float, default=2.0, help="cell height:width ratio")
    p.add_argument("--ramp", default="", help="override glyph ramp dark->bright")
    p.add_argument("--color", choices=["auto", "256", "truecolor", "none"], default="auto")
    p.add_argument("--stars", type=float, default=0.03, help="starfield density 0..1")
    p.add_argument("--no-stars", action="store_true")
    p.add_argument("--no-ring", action="store_true")
    p.add_argument("--no-labels", action="store_true")
    p.add_argument("--top", default=None, help="top caption (default: per body)")
    p.add_argument("--bottom", default=None, help="bottom caption (default: per body)")
    p.add_argument("-i", "--interactive", action="store_true", help="drive with keyboard + mouse")
    p.add_argument("--spin", action="store_true", help="auto-rotate instead of printing once")
    p.add_argument("--fps", type=float, default=12.0)
    p.add_argument("--step", type=float, default=6.0, help="degrees per spin/key step")
    args = p.parse_args()

    args.color = resolve_color(args.color)
    set_color(args.saturation, args.gamma)
    info = BODIES[args.body]
    if args.top is None:
        args.top = info.get("top", args.body.upper())
    if args.bottom is None:
        args.bottom = info.get("bottom", "")
    now = datetime.datetime.now(datetime.timezone.utc)
    if args.follow:
        # Sun-locked view starts looking straight at the current sub-solar point.
        decl, sunlon = subsolar(now)
        if args.lon is None:
            args.lon = math.degrees(sunlon)
        if args.lat is None:
            args.lat = math.degrees(decl)
    elif args.sun:
        # Day/night view: terminator across the centre, seasonal tilt.
        decl, sunlon = subsolar(now)
        if args.lon is None:
            args.lon = (math.degrees(sunlon) + 90.0 + 180.0) % 360.0 - 180.0
        if args.lat is None:
            args.lat = math.degrees(decl)
    if args.lon is None:
        args.lon = -30.0
    if args.lat is None:
        args.lat = 18.0
    # scale_ref = the common scale knob for real/sqrt modes (zoom adjusts it, so
    # all bodies shrink/grow together and keep their relative sizes).
    args.scale_ref = float(auto_size(args.aspect))
    if args.size <= 0:
        s = scaled_size(args.scale, args.body, args.scale_ref)
        if s is None:  # fit mode
            args.size = auto_size(args.aspect)
            if info.get("rings") and not args.no_rings:  # leave room for the rings
                args.size = int(args.size / info["rings"]["outer"])
        else:
            args.size = s
    tex = body_texture(args.body)

    if args.interactive:
        interactive(tex, args)
        return
    if not (args.spin or args.follow):
        print(build_frame(tex, args))
        return
    # follow advances via the real clock (in build_frame); only spin steps lon.
    delay = 1.0 if (args.follow and not args.spin) else 1.0 / max(args.fps, 1.0)
    try:
        sys.stdout.write("\x1b[2J\x1b[?25l")
        while True:
            if args.spin:
                args.lon = (args.lon + args.step) % 360
            frame = build_frame(tex, args).replace("\n", "\x1b[K\n")
            sys.stdout.write("\x1b[H" + frame + "\x1b[K\x1b[J")
            sys.stdout.flush()
            time.sleep(delay)
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\x1b[?25h\x1b[0m\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
