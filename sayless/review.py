"""Review material: burn-ins, storyboard, contact sheet, transition strips.

Nothing in this module reaches a final export; it exists so each review gate
can show a concrete result.
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from . import assets
from .config import (BAR, BEAT, CHARCOAL, CREAM, DURATION, FONT_DISPLAY, FONT_SANS, FONT_SANS_BOLD, FPS,
                     N_FRAMES, ORANGE, SCENES, VO_LINES, scene_at)

STORYBOARD_TIMES = [0.90, 3.55, 5.42, 8.90, 11.35, 13.45, 15.70, 18.85, 22.60]
SCENE_NOTES = {
    "01": "Already moving at frame 0. The stitch climbs dark knit; pull out to the black-body raglan and its O. Settled by 1.20.",
    "02": "The camo sleeve sweeps the lens and reveals the white-body raglan beside it, shoulders aligned.",
    "03": "Crest crewneck and charcoal long sleeve as a staggered pair. One stitch line runs under both prints; no letter is covered.",
    "04": "Dark hooded bomber, front-on. The stitch climbs beside the zip to the circular pull.",
    "05": "The same vertical axis becomes the plaid jacket's centre zip. Across the chest script, widen, then out along one plaid line.",
    "06": "That line carries into the faded camo denim. Pull back until both wide legs and the waistband read.",
    "07": "A foreground thread sweep reveals the hero. The stitch rides the top edge of its chest band; full front by 15.20.",
    "08": "Ease out to all eight pieces, hero dominant. SAY LESS. resolves in cream; at 19.20 the stitch leads to the O.",
    "09": "Stable charcoal end card: O, OMERTÀ ACADEMY, EXPLORE THE COLLECTION. Holds the full 2.4 s.",
}


def _f(path, px):
    return ImageFont.truetype(str(path), px)


def _rgb(c, k=1.0):
    return tuple(int(max(0, min(1, v * k)) * 255) for v in c)


def notes() -> list[str]:
    """Stand-in notices that every review build must carry."""
    n = []
    if not assets.hero_is_brief_item():
        n.append("HERO SLOT: striped hoodie stands in for the brief's burnt-orange track jacket")
    st = assets.o_mark_status()
    if st == "extraction":
        n.append("O MARK: extracted from garment print, pending approved artwork")
    elif st == "missing":
        n.append("O MARK: missing")
    n.append("VOICE: not recorded yet, lines shown as captions")
    return n


def burn_in(frame: np.ndarray, i: int, fmt, mode: str = "animatic") -> np.ndarray:
    """Timecode, scene, bar grid and VO caption over a rendered frame."""
    im = Image.fromarray(frame).convert("RGBA")
    W, H = im.size
    u = H / 1080 if fmt.name == "landscape" else W / 1080     # scale unit
    ov = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    t = i / FPS
    s0, s1, num, title = scene_at(i)
    small, tiny, big = _f(FONT_SANS_BOLD, int(22 * u)), _f(FONT_SANS, int(17 * u)), _f(FONT_SANS_BOLD, int(26 * u))
    m = int(28 * u)
    top = int((30 if fmt.name == "landscape" else 70) * u)
    cream, orange = _rgb(CREAM) + (235,), _rgb(ORANGE, 1.25) + (255,)
    d.text((m, top), f"{num} / {title}", font=big, fill=cream)
    tc = f"{int(t):02d}.{int(round((t % 1) * 100)) % 100:02d}s   f{i:04d}   bar {int(t // BAR) + 1}.{int((t % BAR) // BEAT) + 1}"
    d.text((m, top + int(34 * u)), tc, font=tiny, fill=cream)
    label = "ANIMATIC" if mode == "animatic" else "PREVIEW - NOT FOR RELEASE"
    tw = d.textlength(label, font=small)
    d.text((W - m - tw, top), label, font=small, fill=orange)
    y = top + int(34 * u)
    for line in notes():
        tw = d.textlength(line, font=tiny)
        d.text((W - m - tw, y), line, font=tiny, fill=cream[:3] + (170,))
        y += int(23 * u)
    # bar / beat grid with playhead (animatic only)
    gy = H - int((34 if fmt.name == "landscape" else 250) * u)
    gx0, gx1 = m, W - m
    if mode == "animatic":
        d.line([(gx0, gy), (gx1, gy)], fill=cream[:3] + (120,), width=max(1, int(1.5 * u)))
        nb = int(round(DURATION / BEAT))
        for b in range(nb + 1):
            x = gx0 + (gx1 - gx0) * b / nb
            bar = b % 4 == 0
            hgt = int((12 if bar else 5) * u)
            d.line([(x, gy - hgt), (x, gy)], fill=cream[:3] + (220 if bar else 120,), width=max(1, int((2 if bar else 1) * u)))
        px = gx0 + (gx1 - gx0) * t / DURATION
        d.polygon([(px, gy - int(16 * u)), (px - int(6 * u), gy - int(27 * u)), (px + int(6 * u), gy - int(27 * u))], fill=orange)
    # VO caption while the line is expected to be spoken
    for k, (ts, text) in enumerate(VO_LINES):
        dur = 0.5 + 0.075 * len(text)
        if ts <= t < ts + dur:
            cap = f"VO  “{text}”"
            fcap = _f(FONT_SANS, int(27 * u))
            tw = d.textlength(cap, font=fcap)
            cy = gy - int(64 * u)
            d.rectangle([(W - tw) / 2 - 14 * u, cy - 7 * u, (W + tw) / 2 + 14 * u, cy + 38 * u], fill=(0, 0, 0, 150))
            d.text(((W - tw) / 2, cy), cap, font=fcap, fill=cream)
    return np.asarray(Image.alpha_composite(im, ov).convert("RGB"))


def _wrap(d, text, font, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        if d.textlength((cur + " " + w).strip(), font=font) <= width:
            cur = (cur + " " + w).strip()
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def storyboard_sheet(frames: list[np.ndarray], fmt, title: str) -> Image.Image:
    """Nine frames with scene number, timing and the beat-sheet note."""
    fw, fh = frames[0].shape[1], frames[0].shape[0]
    cols = 3 if fmt.name == "landscape" else 5
    rows = int(np.ceil(9 / cols))
    gap, cap_h, head = 28, 132 if fmt.name == "landscape" else 190, 120
    W = cols * fw + (cols + 1) * gap
    H = head + rows * (fh + cap_h) + gap
    sheet = Image.new("RGB", (W, H), _rgb(CHARCOAL, 0.8))
    d = ImageDraw.Draw(sheet)
    d.text((gap, 26), "SAY LESS.", font=_f(FONT_DISPLAY, 56), fill=_rgb(CREAM))
    d.text((gap + 250, 44), title, font=_f(FONT_SANS, 24), fill=_rgb(CREAM, 0.75))
    x = gap + 250
    for line in notes():
        d.text((x, 78), line, font=_f(FONT_SANS, 16), fill=_rgb(ORANGE, 1.3))
        x += int(d.textlength(line, font=_f(FONT_SANS, 16))) + 30
    body, bold = _f(FONT_SANS, 17), _f(FONT_SANS_BOLD, 19)
    for k, fr in enumerate(frames):
        r, c = divmod(k, cols)
        x = gap + c * (fw + gap)
        y = head + r * (fh + cap_h)
        sheet.paste(Image.fromarray(fr), (x, y))
        s0, s1, num, name = SCENES[k]
        d.text((x, y + fh + 10), f"{num} / {name}", font=bold, fill=_rgb(ORANGE, 1.3))
        tt = f"{s0 / FPS:04.1f}-{s1 / FPS:04.1f} s   [{s0}, {s1})   still at {STORYBOARD_TIMES[k]:.2f} s"
        d.text((x, y + fh + 36), tt, font=body, fill=_rgb(CREAM, 0.7))
        for j, line in enumerate(_wrap(d, SCENE_NOTES[num], body, fw)):
            d.text((x, y + fh + 62 + j * 22), line, font=body, fill=_rgb(CREAM))
    return sheet


def contact_sheet(frames: list[np.ndarray], labels: list[str], cols: int, title: str) -> Image.Image:
    fw, fh = frames[0].shape[1], frames[0].shape[0]
    rows = int(np.ceil(len(frames) / cols))
    gap, head, lab = 8, 64, 22
    sheet = Image.new("RGB", (cols * (fw + gap) + gap, head + rows * (fh + lab + gap)), _rgb(CHARCOAL, 0.8))
    d = ImageDraw.Draw(sheet)
    d.text((gap, 16), title, font=_f(FONT_SANS_BOLD, 26), fill=_rgb(CREAM))
    f = _f(FONT_SANS, 15)
    for k, fr in enumerate(frames):
        r, c = divmod(k, cols)
        x, y = gap + c * (fw + gap), head + r * (fh + lab + gap)
        sheet.paste(Image.fromarray(fr), (x, y))
        d.text((x + 2, y + fh + 2), labels[k], font=f, fill=_rgb(CREAM, 0.8))
    return sheet


TRANSITIONS = [(2.4, "01-02 sleeve sweep"), (4.8, "02-03 stitch crosses foreground"), (7.2, "03-04 behind fabric"),
               (9.6, "04-05 zip match"), (12.0, "05-06 plaid line into denim"), (14.4, "06-07 thread sweep"),
               (16.8, "07-08 ease out"), (19.2, "08 stitch to the O"), (21.6, "08-09 end card")]
