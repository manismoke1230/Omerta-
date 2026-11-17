"""Type: supersampled text sprites with tracking.

Fonts are bundled and openly licensed (SIL OFL): Anton for the compact
display copy, Inter for small text. Swap the files in assets/fonts and the
two constants in config.py to use the brand's own licensed faces.
"""
from __future__ import annotations

import functools

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .config import ASSETS, FONT_DISPLAY, FONT_SANS, FONT_SANS_BOLD

FONTS = {"display": FONT_DISPLAY, "sans": FONT_SANS, "sans_bold": FONT_SANS_BOLD}
PAD = 0.18      # sprite padding, as a fraction of the font size


@functools.lru_cache(maxsize=None)
def _font(kind: str, px: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS[kind]), px)


@functools.lru_cache(maxsize=None)
def cap_height(kind: str, px: int = 400) -> float:
    b = _font(kind, px).getbbox("H")
    return (b[3] - b[1]) / px


def sprite_height_per_cap(kind: str) -> float:
    """World height of a text sprite for a cap height of 1."""
    px = 400
    f = _font(kind, px)
    asc, desc = f.getmetrics()
    return (asc + desc + 2 * PAD * px) / (cap_height(kind, px) * px)


def text_rgba(text: str, kind: str, px: int, colour, tracking: float = 0.0) -> np.ndarray:
    """Straight-alpha RGBA uint8 of one line of text. `tracking` is in em."""
    f = _font(kind, px)
    asc, desc = f.getmetrics()
    pad = int(PAD * px)
    xs = [f.getlength(text[:i]) + i * tracking * px for i in range(len(text) + 1)]
    width = int(np.ceil(xs[-1] - tracking * px)) + 2 * pad
    height = asc + desc + 2 * pad
    mask = Image.new("L", (width, height), 0)
    d = ImageDraw.Draw(mask)
    for i, ch in enumerate(text):
        d.text((pad + xs[i], pad), ch, font=f, fill=255)
    a = np.asarray(mask)
    out = np.zeros((height, width, 4), np.uint8)
    out[..., :3] = (np.float32(colour) * 255 + 0.5).astype(np.uint8)
    out[..., 3] = a
    return out


def label(text: str, px: int, colour=(255, 255, 255), kind: str = "sans") -> Image.Image:
    """Small PIL label for review overlays and sheets."""
    f = _font(kind, px)
    b = f.getbbox(text)
    im = Image.new("RGBA", (b[2] + 4, f.getmetrics()[0] + f.getmetrics()[1] + 4), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((2, 2), text, font=f, fill=tuple(colour) + (255,))
    return im
