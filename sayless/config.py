"""Film constants: timing grid, palette, output formats, scene table.

Everything in the film is derived from these numbers, so the picture, the
audio and the review overlays can never drift apart.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
CACHE = ROOT / ".cache"

# --- timing -----------------------------------------------------------------
FPS = 60
DURATION = 24.0
N_FRAMES = 1440
BPM = 100
BEAT = 60.0 / BPM          # 0.6 s
BAR = 4 * BEAT             # 2.4 s = 144 frames
STORY_END = 21.6           # end card starts here and must hold to 24.0
SR = 48000                 # audio sample rate


def frame_time(i: int) -> float:
    return i / FPS


# --- palette (sRGB, 0..1) ---------------------------------------------------
def hex_rgb(h: str) -> tuple[float, float, float]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


CHARCOAL = hex_rgb("#171615")
ORANGE = hex_rgb("#B45328")
CREAM = hex_rgb("#E8DDCA")
TAUPE = hex_rgb("#8E8171")
DENIM = hex_rgb("#A8B6BC")


# --- formats ----------------------------------------------------------------
@dataclass(frozen=True)
class Format:
    name: str
    width: int
    height: int
    # copy-safe margins in px at full resolution: left, top, right, bottom
    safe: tuple[int, int, int, int]
    # looser rectangle used to frame garments (left, top, right, bottom margins)
    frame: tuple[int, int, int, int]

    @property
    def size(self) -> tuple[int, int]:
        return self.width, self.height

    def safe_rect(self) -> tuple[float, float, float, float]:
        l, t, r, b = self.safe
        return l, t, self.width - r, self.height - b

    def frame_rect(self) -> tuple[float, float, float, float]:
        l, t, r, b = self.frame
        return l, t, self.width - r, self.height - b


FORMATS = {
    # 5 % title-safe on the landscape master
    "landscape": Format("landscape", 1920, 1080, (96, 54, 96, 54), (60, 50, 60, 50)),
    # brief: 120 px sides, 180 px top, 300 px bottom on 1080 x 1920
    "portrait": Format("portrait", 1080, 1920, (120, 180, 120, 300), (50, 170, 50, 290)),
}

# --- scenes: (start frame, end frame, number, title) -- end exclusive --------
SCENES = [
    (0, 144, "01", "THE STITCH"),
    (144, 288, "02", "TWO MOODS"),
    (288, 432, "03", "THE ACADEMY"),
    (432, 576, "04", "THE LAYER"),
    (576, 720, "05", "THE PATTERN"),
    (720, 864, "06", "THE DENIM"),
    (864, 1008, "07", "THE HERO"),
    (1008, 1296, "08", "SAY LESS."),
    (1296, 1440, "09", "END CARD"),
]


def scene_at(frame: int):
    for s in SCENES:
        if s[0] <= frame < s[1]:
            return s
    return SCENES[-1]


# --- products: working labels only, not official product names ---------------
GARMENTS = [
    ("raglan_black", "Camo raglan / black body"),
    ("raglan_white", "Camo raglan / white body"),
    ("crest_crew", "Crest crewneck / burnt orange"),
    ("charcoal_ls", "Graphic long sleeve / charcoal"),
    ("bomber", "Hooded bomber / dark"),
    ("plaid", "Plaid zip jacket"),
    ("denim", "Camo denim"),
    ("track", "Track jacket / burnt-orange pile"),
]
GARMENT_KEYS = [k for k, _ in GARMENTS]
GARMENT_LABEL = dict(GARMENTS)
HERO = "track"

# --- on-screen copy: the only three lines allowed outside product artwork ----
COPY_TITLE = "SAY LESS."
COPY_BRAND = "OMERTÀ ACADEMY"
COPY_CTA = "EXPLORE THE COLLECTION."

# --- voiceover: suggested starts from the brief ------------------------------
VO_LINES = [
    (0.60, "You don’t have to say much."),
    (5.10, "The details speak."),
    (9.90, "In every line."),
    (12.30, "Every layer."),
    (18.00, "Omertà Academy."),
    (21.80, "Say less."),
]

FONT_DISPLAY = ASSETS / "fonts" / "Anton-Regular.ttf"
FONT_SANS = ASSETS / "fonts" / "Inter-Medium.otf"
FONT_SANS_BOLD = ASSETS / "fonts" / "Inter-SemiBold.otf"
