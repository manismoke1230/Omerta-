"""Separate each garment from its studio backdrop.

The photographs are the source of truth, so the matte is conservative:

* the backdrop is found by flooding inward from the image border, so white
  fabric, labels and highlights *inside* the garment are never keyed out;
* soft cast shadows on the backdrop are peeled (they belong to the studio,
  not the product); shading on the fabric itself is untouched;
* edge colour is pulled from just inside the silhouette, which removes the
  light fringe a white backdrop leaves on a dark stage.

A hand-painted override always wins: drop ``assets/garments/masks/<key>.png``
(white = garment) next to the sources.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

from .config import ASSETS, CACHE

SRC = ASSETS / "garments" / "source"
MASKS = ASSETS / "garments" / "masks"
MANIFEST = ASSETS / "garments" / "manifest.json"

DEFAULTS = dict(
    trim=(2, 2, 2, 2),   # px shaved off left, top, right, bottom (screenshot rules)
    tol=9.0,             # max channel distance from the local backdrop colour
    shadow=0.0,          # how far below backdrop luminance a neutral pixel may be and still count as cast shadow
    chroma=7.0,          # max chroma for "neutral" (shadow) pixels
    smooth=0,            # median pre-filter for noisy backdrops
    grad=0.0,            # >0: the flood also stops at luminance edges (for backdrops close to the fabric colour)
    close=0,             # closing radius to heal bites out of the silhouette
    refine=10.0,         # px: re-seat the edge at the 50 % point of the photo's own edge blur
    calm=3.0,            # px: smooth the silhouette only where fabric and backdrop are nearly the same colour
    refine_min=35.0,     # minimum fabric/backdrop colour distance for that re-seating
    open_holes=(),       # [x, y] seeds (trimmed source px) of real see-through gaps to keep open
    remove=(),           # polygons (trimmed source px) of backdrop shadow the key cannot tell from white fabric
    round_cut=0,         # px: soften the corners where the photo itself crops the garment
    band=5.0,            # px inside the silhouette where alpha/colour are re-estimated
    choke=1.0,           # px the geometric edge is pulled in where colour unmixing is unreliable
    gain=1.15,           # steepness of the unmixed alpha ramp (kills residual fringe)
)


def load_manifest() -> dict:
    return json.loads(MANIFEST.read_text())


def _backdrop_field(img: np.ndarray, tol: float) -> np.ndarray:
    """Smooth estimate of the backdrop colour everywhere (handles vignettes)."""
    h, w = img.shape[:2]
    border = np.concatenate([img[:6].reshape(-1, 3), img[-6:].reshape(-1, 3),
                             img[:, :6].reshape(-1, 3), img[:, -6:].reshape(-1, 3)])
    med = np.median(border, axis=0)
    near = (np.abs(img - med).max(axis=2) < max(tol * 3.5, 30)).astype(np.float32)
    small = cv2.resize(img, (w // 8, h // 8), interpolation=cv2.INTER_AREA)
    wsm = cv2.resize(near, (w // 8, h // 8), interpolation=cv2.INTER_AREA)
    wsm = (wsm > 0.98).astype(np.float32)
    sig = max(h, w) / 8 * 0.06
    num = cv2.GaussianBlur(small * wsm[..., None], (0, 0), sig)
    den = cv2.GaussianBlur(wsm, (0, 0), sig)[..., None]
    # where no backdrop sample is near (deep inside the garment) fall back to the median
    field = np.where(den > 1e-3, num / np.maximum(den, 1e-6), med)
    return cv2.resize(field.astype(np.float32), (w, h), interpolation=cv2.INTER_CUBIC)


def _border_connected(cand: np.ndarray) -> np.ndarray:
    """Pixels of `cand` reachable from the image border."""
    h, w = cand.shape
    pad = np.zeros((h + 2, w + 2), np.uint8)
    pad[1:-1, 1:-1] = cand.astype(np.uint8)
    pad[0, :] = pad[-1, :] = pad[:, 0] = pad[:, -1] = 1
    ff = np.zeros((h + 4, w + 4), np.uint8)
    cv2.floodFill(pad, ff, (0, 0), 2)
    return pad[1:-1, 1:-1] == 2


def _extend(bgr: np.ndarray, sure: np.ndarray) -> np.ndarray:
    """Every pixel takes the colour of the nearest `sure` pixel."""
    _, idx = cv2.distanceTransformWithLabels((~sure).astype(np.uint8), cv2.DIST_L2, 5,
                                             labelType=cv2.DIST_LABEL_PIXEL)
    ys, xs = np.nonzero(sure)
    lut_y = np.zeros(idx.max() + 1, np.int32)
    lut_x = np.zeros(idx.max() + 1, np.int32)
    lut_y[idx[ys, xs]] = ys
    lut_x[idx[ys, xs]] = xs
    return cv2.blur(bgr, (3, 3))[lut_y[idx], lut_x[idx]]


def compute_matte(key: str, params: dict | None = None) -> tuple[np.ndarray, np.ndarray, dict]:
    """Return (rgb uint8 with edge colours extended, alpha float32, info)."""
    man = load_manifest()[key]
    p = {**DEFAULTS, **man.get("matte", {}), **(params or {})}
    bgr = cv2.imread(str(SRC / man["file"]), cv2.IMREAD_COLOR)
    if bgr is None:
        raise FileNotFoundError(SRC / man["file"])
    l, t, r, b = p["trim"]
    bgr = bgr[t:bgr.shape[0] - b, l:bgr.shape[1] - r]
    img = bgr.astype(np.float32)
    work = cv2.medianBlur(bgr, p["smooth"]).astype(np.float32) if p["smooth"] else img

    override = MASKS / f"{key}.png"
    if override.exists():
        hard = cv2.imread(str(override), cv2.IMREAD_GRAYSCALE) > 127
        hard = hard[t:hard.shape[0] - b, l:hard.shape[1] - r]
    else:
        field = _backdrop_field(work, p["tol"])
        diff = np.abs(work - field).max(axis=2)
        lum = cv2.GaussianBlur(work.mean(axis=2), (0, 0), 1.0)
        gx = cv2.Sobel(lum, cv2.CV_32F, 1, 0, ksize=3) / 8
        gy = cv2.Sobel(lum, cv2.CV_32F, 0, 1, ksize=3) / 8
        gmag = np.hypot(gx, gy)
        cand = diff < p["tol"]
        if p["grad"] > 0:
            cand &= gmag < p["grad"]
        if p["shadow"] > 0:
            flum = field.mean(axis=2)
            chroma = work.max(axis=2) - work.min(axis=2)
            # cast shadow = neutral, lighter than the limit, and smooth (hardware and
            # fabric edges are not smooth, so the flood cannot walk into them)
            cand |= ((chroma < p["chroma"]) & (work.mean(axis=2) > flum - p["shadow"])
                     & (work.mean(axis=2) < flum + p["tol"]) & (gmag < 7.0))
        back = _border_connected(cand)
        hard = ~back
        if p["close"]:
            k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * p["close"] + 1,) * 2)
            hard = cv2.morphologyEx(hard.astype(np.uint8), cv2.MORPH_CLOSE, k) > 0
        # keep the garment only: largest component, then fill every interior hole
        n, lab, stats, _ = cv2.connectedComponentsWithStats(hard.astype(np.uint8), connectivity=8)
        if n > 1:
            keep = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
            hard = lab == keep
        hard = ~_border_connected(~hard)

    field = _backdrop_field(work, p["tol"])
    if p["refine"] > 0 and not override.exists():
        # The flood stops where the backdrop *starts* to darken, which on a soft
        # photo is several px outside the fabric. Unmix against fabric colour
        # sampled well inside and move the edge to the half-way point. Only
        # where fabric and backdrop differ clearly; white-on-white keeps the flood edge.
        ins0 = cv2.distanceTransform(hard.astype(np.uint8), cv2.DIST_L2, 5)
        ext0 = _extend(bgr, ins0 > p["refine"]).astype(np.float32)
        d0 = ext0 - field
        c2 = (d0 * d0).sum(axis=2)
        a0 = ((img - field) * d0).sum(axis=2) / np.maximum(c2, 1.0)
        keep = (a0 > 0.5) | (ins0 > p["refine"]) | (np.sqrt(c2) < p["refine_min"])
        hard = hard & keep
        n, lab, stats, _ = cv2.connectedComponentsWithStats(hard.astype(np.uint8), connectivity=8)
        if n > 1:
            hard = lab == 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        hard = ~_border_connected(~hard)
    if not override.exists():
        if p["calm"] > 0:
            ins0 = cv2.distanceTransform(hard.astype(np.uint8), cv2.DIST_L2, 5)
            ext0 = _extend(bgr, ins0 > 8).astype(np.float32)
            low = (np.sqrt(((ext0 - field) ** 2).sum(axis=2)) < 45.0).astype(np.float32)
            low = cv2.GaussianBlur(low, (0, 0), 4.0)
            soft = cv2.GaussianBlur(hard.astype(np.float32), (0, 0), p["calm"]) > 0.5
            hard = np.where(low > 0.5, soft, hard)
        for poly in p["remove"]:
            cut = np.zeros(hard.shape, np.uint8)
            cv2.fillPoly(cut, [np.asarray(poly, np.int32)], 1)
            hard = hard & (cut == 0)
        for sx, sy in p["open_holes"]:
            gap = (np.abs(work - field).max(axis=2) < p["tol"] * 2.5).astype(np.uint8)
            if gap[int(sy), int(sx)]:
                ff = np.zeros((gap.shape[0] + 2, gap.shape[1] + 2), np.uint8)
                cv2.floodFill(gap, ff, (int(sx), int(sy)), 2)
                hard = hard & (gap != 2)
    inside = cv2.distanceTransform(hard.astype(np.uint8), cv2.DIST_L2, 5)

    # --- edge colour: copy from pixels safely inside the silhouette -----------
    R = float(p["band"])
    sure = inside > R
    ext = _extend(bgr, sure).astype(np.float32)

    # --- alpha in the band: unmix the photo's own edge blur --------------------
    # pixel = a * fabric + (1 - a) * backdrop  ->  a = <c - bg, fg - bg> / |fg - bg|^2
    dfg = ext - field
    con2 = (dfg * dfg).sum(axis=2)
    a_unmix = np.clip(((img - field) * dfg).sum(axis=2) / np.maximum(con2, 1.0), 0, 1)
    a_unmix = np.clip((a_unmix - 0.5) * p["gain"] + 0.5, 0, 1)
    a_geo = np.clip((inside - p["choke"]) / 1.2 + 0.5, 0, 1)
    trust = np.clip((np.sqrt(con2) - 30.0) / 50.0, 0, 1)      # low contrast -> geometry
    a_band = trust * np.minimum(a_unmix, np.clip(inside / 1.0, 0, 1)) + (1 - trust) * a_geo
    t_in = np.clip((inside - R * 0.55) / (R * 0.45), 0, 1)     # 0 in the band -> 1 inside
    alpha = (a_band * (1 - t_in) + t_in).astype(np.float32)
    alpha = cv2.GaussianBlur(alpha, (0, 0), 0.6)
    alpha[~hard] = 0
    if p["round_cut"]:
        # the photo crops this garment at the frame edge: round the two cut corners
        # so the crop does not read as a razor-straight line (nothing is invented)
        r = int(p["round_cut"])
        for edge in ("top", "bottom"):
            row = hard[0] if edge == "top" else hard[-1]
            xs_ = np.nonzero(row)[0]
            if xs_.size < 20:
                continue
            xa, xb = int(xs_.min()), int(xs_.max())
            yy, xx = np.mgrid[0:r, 0:r].astype(np.float32)
            corner = np.clip(r - np.hypot(r - xx - 0.5, r - yy - 0.5) + 0.5, 0, 1)
            rows = slice(0, r) if edge == "top" else slice(alpha.shape[0] - r, alpha.shape[0])
            cl = corner if edge == "top" else corner[::-1]
            alpha[rows, xa:xa + r] *= cl
            alpha[rows, xb - r + 1:xb + 1] *= cl[:, ::-1]
    rgb_ext = img * t_in[..., None] + ext * (1 - t_in[..., None])
    rgb_ext = np.clip(rgb_ext, 0, 255).astype(np.uint8)

    ys, xs = np.nonzero(alpha > 0.02)
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    info = dict(key=key, file=man["file"], source_size=[int(bgr.shape[1]), int(bgr.shape[0])],
                bbox=[int(x0), int(y0), int(x1), int(y1)], trim=list(p["trim"]),
                coverage=float(hard.mean()), override=override.exists(), params=p)
    return cv2.cvtColor(rgb_ext, cv2.COLOR_BGR2RGB), alpha, info


def cutout(key: str) -> tuple[np.ndarray, dict]:
    """Cached RGBA cutout cropped to the garment (straight alpha, uint8)."""
    man = load_manifest()[key]
    src = SRC / man["file"]
    override = MASKS / f"{key}.png"
    sig = hashlib.sha1()
    sig.update(src.read_bytes())
    sig.update(json.dumps({**DEFAULTS, **man.get("matte", {})}, sort_keys=True).encode())
    sig.update(Path(__file__).read_bytes())
    if override.exists():
        sig.update(override.read_bytes())
    CACHE.mkdir(exist_ok=True)
    f = CACHE / f"cutout_{key}_{sig.hexdigest()[:12]}.npz"
    if f.exists():
        z = np.load(f, allow_pickle=False)
        return z["rgba"], json.loads(str(z["info"]))
    rgb, alpha, info = compute_matte(key)
    pad = 6
    x0, y0, x1, y1 = info["bbox"]
    h, w = alpha.shape
    X0, Y0, X1, Y1 = max(x0 - pad, 0), max(y0 - pad, 0), min(x1 + pad, w), min(y1 + pad, h)
    rgba = np.dstack([rgb[Y0:Y1, X0:X1], (alpha[Y0:Y1, X0:X1] * 255 + 0.5).astype(np.uint8)])
    info["crop"] = [int(X0), int(Y0), int(X1), int(Y1)]
    info["tight"] = [int(x0 - X0), int(y0 - Y0), int(x1 - X0), int(y1 - Y0)]
    for old in CACHE.glob(f"cutout_{key}_*.npz"):
        old.unlink()
    np.savez_compressed(f, rgba=rgba, info=json.dumps(info))
    return rgba, info
