"""Garment textures: premultiplied mip pyramids, anchors, shadows, brand mark."""
from __future__ import annotations

import functools
import json

import cv2
import numpy as np

from . import matte
from .config import ASSETS, CACHE, GARMENT_KEYS

# Slot name -> manifest key. Slot 8 of the brief is the hero; whatever photo
# sits in the manifest under "hero" plays that part.
SLOT_FILE_KEY = {"track": "hero"}

# ---------------------------------------------------------------------------
# Anchors: points on the real artwork, normalised to the garment's tight box
# (0,0 = top-left of the cutout, 1,1 = bottom-right). Chosen by eye from the
# supplied photographs; see docs/02_asset_map.md.
# ---------------------------------------------------------------------------
ANCHORS = {
    "raglan_black": {
        "tail": (0.43, 1.07), "hem": (0.425, 0.975), "b1": (0.405, 0.84), "b2": (0.345, 0.62),
        "b3": (0.275, 0.455), "arm_l": (0.226, 0.352), "seam_l": (0.303, 0.215),
        "col_l": (0.386, 0.088), "col_c": (0.50, 0.112), "col_r": (0.614, 0.088),
        "seam_r": (0.697, 0.215), "arm_r": (0.774, 0.352), "slv_r": (0.865, 0.47),
        "out_r": (0.99, 0.565), "o_mark": (0.50, 0.245),
    },
    "raglan_white": {
        "in_l": (0.01, 0.565), "slv_l": (0.135, 0.47), "arm_l": (0.226, 0.352),
        "seam_l": (0.303, 0.215), "col_l": (0.386, 0.088), "col_c": (0.50, 0.112),
        "col_r": (0.614, 0.088), "seam_r": (0.697, 0.215), "arm_r": (0.774, 0.352),
        "side_r": (0.782, 0.62), "side_r2": (0.776, 0.90), "hem_r": (0.762, 0.972),
        "out": (0.75, 1.04), "o_mark": (0.50, 0.245),
    },
    "crest_crew": {
        "in_l": (0.035, 0.636), "u_l": (0.25, 0.636), "u_r": (0.75, 0.636), "out_r": (0.965, 0.636),
        "print_c": (0.50, 0.46),
    },
    "charcoal_ls": {
        "in_l": (0.0, 0.562), "u_l": (0.22, 0.562), "u_r": (0.78, 0.562), "out_r": (1.0, 0.562),
        "print_c": (0.50, 0.33),
    },
    "bomber": {
        "below": (0.53, 0.90), "hem": (0.53, 0.798), "z1": (0.53, 0.60), "z2": (0.53, 0.40),
        "z3": (0.53, 0.235), "pull": (0.503, 0.192), "top": (0.498, 0.14), "hood": (0.498, 0.05),
        "above": (0.50, -0.06), "pull_c": (0.498, 0.186), "o_mark": (0.656, 0.3025),
    },
    "plaid": {
        "below": (0.535, 1.06), "hem": (0.535, 0.935), "z1": (0.535, 0.80), "z2": (0.535, 0.62),
        "turn": (0.535, 0.535), "line0": (0.56, 0.523), "line1": (0.70, 0.523), "line2": (0.84, 0.523),
        "out_r": (0.995, 0.523), "zip_c": (0.502, 0.40), "script": (0.674, 0.297),
        "pull_c": (0.502, 0.226),
    },
    "denim": {
        "in_l": (0.0, 0.245), "hip_l": (0.20, 0.252), "d1": (0.42, 0.33), "d2": (0.58, 0.41),
        "d3": (0.72, 0.52), "thigh_r": (0.81, 0.625), "out_r": (0.965, 0.69),
        # mirrored route for the portrait stack
        "in_r": (1.0, 0.245), "hip_r": (0.80, 0.252), "m1": (0.58, 0.33), "m2": (0.42, 0.41),
        "m3": (0.28, 0.52), "thigh_l": (0.19, 0.625), "out_l": (0.035, 0.69),
    },
    # hero slot: currently the striped hoodie. The stitch rides the top edge of
    # its chest band and ducks under both drawcords.
    "track": {
        "in_l": (0.0, 0.345), "b_l": (0.215, 0.351), "c1a": (0.404, 0.351), "c1b": (0.431, 0.351),
        "c2a": (0.576, 0.351), "c2b": (0.603, 0.351), "b_r": (0.785, 0.351), "out_r": (1.0, 0.345),
        "beside_r": (1.075, 0.72), "beside_l": (-0.075, 0.72), "band_c": (0.50, 0.415),
    },
}

# Crops used as soft foreground wipes (fabric passing the lens), normalised.
SWEEP_CROPS = {
    "raglan_black": (0.78, 0.10, 1.0, 1.0),      # the camo sleeve
    "charcoal_ls": (0.80, 0.08, 1.0, 1.0),       # the washed charcoal sleeve
}


class Texture:
    """Premultiplied RGBA uint8 with a mip pyramid."""

    def __init__(self, rgba_straight: np.ndarray):
        a = rgba_straight[..., 3:4].astype(np.float32) / 255.0
        pm = np.dstack([rgba_straight[..., :3].astype(np.float32) * a, a * 255.0])
        lv = np.clip(pm + 0.5, 0, 255).astype(np.uint8)
        self.levels = [lv]
        while min(lv.shape[:2]) > 48:
            lv = cv2.pyrDown(lv)
            self.levels.append(lv)
        self.h, self.w = self.levels[0].shape[:2]


class Garment:
    def __init__(self, slot: str):
        self.slot = slot
        self.file_key = SLOT_FILE_KEY.get(slot, slot)
        rgba, info = matte.cutout(self.file_key)
        self.info = info
        self.tex = Texture(_rim_light(rgba))
        self.alpha = rgba[..., 3].astype(np.float32) / 255.0
        x0, y0, x1, y1 = info["tight"]
        self.tight = (x0, y0, x1, y1)
        self.tw, self.th = x1 - x0, y1 - y0
        self.anchors = ANCHORS[slot]

    def px(self, nx: float, ny: float) -> tuple[float, float]:
        """Normalised tight-box coordinate -> pixel in the cutout texture."""
        return self.tight[0] + nx * self.tw, self.tight[1] + ny * self.th

    def anchor_px(self, name: str) -> tuple[float, float]:
        return self.px(*self.anchors[name])


def _rim_light(rgba: np.ndarray) -> np.ndarray:
    """Bake a restrained warm edge light on the upper-left facing edges.

    Only a ~5 px band is touched and the lift is small, so the garment's own
    colours are preserved; it simply separates dark fabric from the dark stage.
    """
    a = rgba[..., 3].astype(np.float32) / 255.0
    soft = cv2.GaussianBlur(a, (0, 0), 3.0)
    m = np.float32([[1, 0, 4.0], [0, 1, 5.0]])           # light from upper-left
    shifted = cv2.warpAffine(soft, m, (a.shape[1], a.shape[0]))
    rim = np.clip(a - shifted, 0, 1) * a
    rim = cv2.GaussianBlur(rim, (0, 0), 0.8)
    rgb = rgba[..., :3].astype(np.float32)
    warm = np.float32([255, 214, 170])
    rgb = rgb + (warm - rgb) * (rim[..., None] * 0.22)
    out = rgba.copy()
    out[..., :3] = np.clip(rgb, 0, 255).astype(np.uint8)
    return out


@functools.lru_cache(maxsize=None)
def garments() -> dict[str, Garment]:
    return {k: Garment(k) for k in GARMENT_KEYS}


def hero_is_brief_item() -> bool:
    """False while the hero slot holds a stand-in for the brief's track jacket."""
    man = matte.load_manifest()
    return bool(man["hero"].get("matches_brief", False))


# ---------------------------------------------------------------------------
# Shadows (per placement scale, so they are built by the layout)
# ---------------------------------------------------------------------------
def shadow_map(g: Garment, units_per_px: float) -> tuple[np.ndarray, float, float]:
    """Soft contact + ambient shadow for a garment lying on the stage.

    Returns (map 0..1 at 1/4 texture resolution, pad in texture px, scale=4).
    Sizes are specified in world units so every garment casts the same shadow
    regardless of how large its photo is.
    """
    ds = 4
    contact_u, soft_u = 2.2, 13.0                          # world units
    off_u = np.float32([2.0, 3.2])                         # light from upper-left
    pad = int(np.ceil((soft_u * 3 + 6) / units_per_px / ds)) * ds
    a = cv2.copyMakeBorder(g.alpha, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=0)
    small = cv2.resize(a, (a.shape[1] // ds, a.shape[0] // ds), interpolation=cv2.INTER_AREA)
    px = units_per_px * ds                                 # world units per small px
    contact = cv2.GaussianBlur(small, (0, 0), contact_u / px)
    soft = cv2.GaussianBlur(small, (0, 0), soft_u / px)
    def shift(img, k):
        m = np.float32([[1, 0, off_u[0] * k / px], [0, 1, off_u[1] * k / px]])
        return cv2.warpAffine(img, m, (img.shape[1], img.shape[0]))
    sh = 1.0 - (1.0 - 0.62 * shift(contact, 1.0)) * (1.0 - 0.42 * shift(soft, 2.6))
    return sh.astype(np.float32), float(pad), float(ds)


# ---------------------------------------------------------------------------
# Brand mark
# ---------------------------------------------------------------------------
BRAND = ASSETS / "brand"
O_APPROVED = BRAND / "o_mark.png"            # drop approved artwork here (RGBA)
O_EXTRACT = BRAND / "o_mark_extraction.png"  # built from the garment print, pending approval


def o_mark_status() -> str:
    if O_APPROVED.exists():
        return "approved"
    return "extraction" if O_EXTRACT.exists() else "missing"


def build_o_extraction(force: bool = False) -> None:
    """Clean extraction of the O from the charcoal long-sleeve print.

    The printed O is the only logo artwork supplied, and it is distressed, so
    the worn specks are closed and the outline smoothed. Nothing is redrawn:
    the silhouette and the colour both come from the photograph. This is a
    proposal for approval, not approved artwork.
    """
    if O_EXTRACT.exists() and not force:
        return
    g = Garment("charcoal_ls")
    rgba, _ = matte.cutout("charcoal_ls")
    x0, y0 = g.px(0.31, 0.295)
    x1, y1 = g.px(0.65, 0.46)
    crop = rgba[int(y0):int(y1), int(x0):int(x1), :3].astype(np.float32)
    r, gch, b = crop[..., 0], crop[..., 1], crop[..., 2]
    orange = ((r - b) > 55) & (r > 120) & ((r - gch) > 25)
    px = crop[orange]
    sat = px.max(axis=1) - px.min(axis=1)
    colour = np.median(px[sat >= np.percentile(sat, 70)], axis=0)   # the un-worn ink colour
    m = orange.astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    m = (lab == 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))).astype(np.float32)
    up = 8
    big = cv2.resize(m, None, fx=up, fy=up, interpolation=cv2.INTER_CUBIC)
    big = cv2.GaussianBlur(big, (0, 0), up * 2.4)
    big = np.clip((big - 0.5) * 9.0 + 0.5, 0, 1)            # re-harden the smoothed edge
    ys, xs = np.nonzero(big > 0.02)
    pad = 24
    big = big[max(ys.min() - pad, 0):ys.max() + pad, max(xs.min() - pad, 0):xs.max() + pad]
    out = np.zeros(big.shape + (4,), np.uint8)
    out[..., :3] = np.clip(colour, 0, 255).astype(np.uint8)
    out[..., 3] = (big * 255 + 0.5).astype(np.uint8)
    BRAND.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(O_EXTRACT), cv2.cvtColor(out, cv2.COLOR_RGBA2BGRA))


def load_o_mark() -> np.ndarray | None:
    path = O_APPROVED if O_APPROVED.exists() else (O_EXTRACT if O_EXTRACT.exists() else None)
    if path is None:
        return None
    im = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    return cv2.cvtColor(im, cv2.COLOR_BGRA2RGBA)
