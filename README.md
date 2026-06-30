<div align="center">

<img src="screenshots/earth.gif" alt="ascii-earth — Earth" width="560">
<img src="screenshots/demo.gif" alt="ascii-earth — Saturn &amp; Uranus rings" width="560">

# ascii-earth

**Render the planets, the Moon and the Sun as a live colour ASCII/Braille globe in your terminal**

[![License](https://img.shields.io/github/license/pluttan/ascii-earth?style=for-the-badge&color=2C2C2C&labelColor=1E1E1E)](https://github.com/pluttan/ascii-earth/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.9+-2C2C2C?style=for-the-badge&logo=python&labelColor=1E1E1E)](https://python.org)
[![Platform](https://img.shields.io/badge/terminal-POSIX-2C2C2C?style=for-the-badge&labelColor=1E1E1E)](https://github.com/pluttan/ascii-earth)

</div>

A real equirectangular texture is back-projected onto a sphere (orthographic projection), sampled per terminal cell and recoloured. The disc sits in a full starfield, captions pin to the top and bottom edges, and everything is driven live from the keyboard and the mouse — day/night by the real Sun, Saturn's rings, real relative sizes and a pile of palettes.

> THAT'S NO EARTH! — IT'S A SPACE STATION.

## ■ Features

- ❖ **11 bodies** — Earth, Sun, Mercury, Venus, Moon, Mars, Jupiter, Saturn, Uranus, Neptune, Ceres. Switch on the fly with `<` / `>`.
- ❖ **Rings** for Saturn and Uranus — an ellipse with proper sphere occlusion (front arc over the disc, back arc hidden), a Cassini-style gap and azimuthal clumps so the spin is visible.
- ❖ **Real-time day / night** (`--sun`) — lit by the actual current position of the Sun; the night side fades to bright black-and-white.
- ❖ **Follow the Sun** (`--follow`) — a Sun-locked view that always shows the day side while Earth turns under it at the real rate (one turn per 24 h).
- ❖ **Scale modes** (`m`) — `fit`, `real` (true relative radii: the Sun is a wall, Ceres is a dot) and `sqrt` (a readable compromise). Zoom rescales the whole system together.
- ❖ **3 glyph modes** (`g`) — braille (2×4 sub-pixel, default), unicode (a dense 56-level UTF-8 ramp) and ascii.
- ❖ **10 palettes** (`p`) — natural, political, blue, green, amber, ice, mono, inferno, neon, catppuccin.
- ❖ **Mouse + keyboard**, truecolor / 256 / mono output, works over tmux & mosh, ships its textures so it runs offline.

## ■ Installation

### pip (one-line)

```bash
pip install "git+https://github.com/pluttan/ascii-earth"
ascii-earth -i
```

### From Source

```bash
git clone https://github.com/pluttan/ascii-earth.git
cd ascii-earth
make install        # venv in ~/.cache + pillow/numpy
make run            # interactive
```

### Requirements

- Python 3.9+
- `pillow`, `numpy`
- a 256-colour (or truecolor) terminal; braille mode needs a font with Braille glyphs

Textures are bundled, so it works fully offline.

## ■ Usage

```bash
ascii-earth -i                              # interactive
ascii-earth --body saturn --lat 26          # Saturn, rings open
ascii-earth --body jupiter --spin           # auto-rotating Jupiter
ascii-earth --sun                           # Earth right now: day & night
ascii-earth --scale real --body mars        # true relative size
ascii-earth --palette catppuccin --color truecolor
```

| Option | Default | Description |
|--------|---------|-------------|
| `--body NAME` | `earth` | celestial body (earth/sun/mars/jupiter/saturn/…) |
| `--scale {fit,sqrt,real}` | `fit` | fit / sqrt-compressed / real radii |
| `--no-rings` | — | hide Saturn/Uranus rings |
| `--glyphs {braille,unicode,ascii}` | `braille` | render glyph set |
| `--palette NAME` | `natural` | colour scheme |
| `--color {auto,256,truecolor,none}` | `auto` | colour depth |
| `--sun` | — | real-time day/night terminator |
| `--follow` | — | Sun-locked view, 24 h rotation |
| `--spin` | — | auto-rotate |
| `--size N` | `0` (auto) | disc diameter in columns; `0` fits the terminal |
| `--lon DEG` / `--lat DEG` | auto | central longitude / view latitude (+north) |
| `--saturation F` / `--gamma F` | `2.1` / `0.55` | colour saturation / brightness |
| `--no-stars` / `--no-ring` / `--no-labels` | — | drop elements |
| `-i`, `--interactive` | — | keyboard + mouse mode |

## ■ Interactive Keys

Minimal keys; the rest live under `?`.

| Key | Action |
|-----|--------|
| `<` / `>` | previous / next body |
| `m` | scale mode (fit → sqrt → real) |
| `R` | planetary rings on / off |
| drag / arrows / `h j k l` | rotate (disabled in follow) |
| wheel / `+` `-` | zoom |
| `g` | glyph mode (braille / unicode / ascii) |
| `p` / `P` | palette next / previous |
| `c` | colour mode (truecolor / 256 / none) |
| `n` | day / night (real Sun) |
| `f` | follow Sun |
| `s` `o` `b` | stars / limb ring / captions |
| `[` `]` | saturation − / + |
| `,` `.` | brightness darker / lighter |
| `space` | auto-spin |
| `r` | reset |
| `?` | show / hide the full key list |
| `q` / `Esc` | quit |

## ■ Palettes

| Palette | Look |
|---------|------|
| `natural` | real map colours (blue ocean, green/brown land, white ice) |
| `political` | brighter, punchier map |
| `blue` | stylised blue-grey |
| `green` / `amber` / `ice` | phosphor / amber / blueprint monochrome |
| `mono` | black & white |
| `inferno` | false-colour heatmap |
| `neon` | acid cyan / magenta |
| `catppuccin` | Catppuccin Mocha |

## ■ Textures & Attribution

Textures are bundled in `ascii_earth/textures/` and keep their own licenses (see [NOTICE](NOTICE)):

- **Earth** — NASA Blue Marble (*land + shallow topography*), public domain.
- **All other bodies** — [Solar System Scope](https://www.solarsystemscope.com/textures) equirectangular textures, **CC-BY 4.0**. Attribution to Solar System Scope is required when redistributing them.

## ■ License

MIT © [pluttan](https://github.com/pluttan)
