"""Deterministic 2.5D compositor.

``render_frame(layout, i)`` -> uint8 RGB. Same inputs, same pixels: every
random element (grain, textures) is seeded from the frame number.

Draw order, back to front:
  stage -> garment shadows -> loose thread -> garments -> stitches ->
  world-anchored copy -> fabric wipes -> lifted thread -> vignette + grain
"""
from __future__ import annotations

import functools

import cv2
import numpy as np

from . import assets, film, typeset
from .config import (CHARCOAL, COPY_BRAND, COPY_CTA, COPY_TITLE, CREAM, FPS, GARMENT_KEYS, HERO,
                     STORY_END)
from .curves import keyed, smoothstep, tile_noise
from .thread import FRONT, LOOSE, STITCH, draw_thread

AMBIENT = 0.13            # brightness of a garment that is not lit
STAGE_PAR = 0.94          # the stage floor sits a touch behind the garments
STAGE_TEX_PER_UNIT = 1.4


# ---------------------------------------------------------------------------
# primitives
# ---------------------------------------------------------------------------
def _screen(pose, scale, size, par=1.0):
    cx, cy, z = pose
    zs = z * scale * par
    W, H = size
    return np.float64([[zs, 0, W / 2 - cx * zs], [0, zs, H / 2 - cy * zs]])


def _compose(S, M):
    """S after M (both 2x3)."""
    out = np.empty((2, 3))
    out[:, :2] = S[:, :2] @ M[:, :2]
    out[:, 2] = S[:, :2] @ M[:, 2] + S[:, 2]
    return out


def _roi(M, w, h, W, H, pad):
    c = np.float64([[0, 0], [w, 0], [w, h], [0, h]])
    p = c @ M[:, :2].T + M[:, 2]
    x0 = int(np.floor(p[:, 0].min() - pad))
    y0 = int(np.floor(p[:, 1].min() - pad))
    x1 = int(np.ceil(p[:, 0].max() + pad)) + 1
    y1 = int(np.ceil(p[:, 1].max() + pad)) + 1
    x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, W), min(y1, H)
    if x1 - x0 < 1 or y1 - y0 < 1:
        return None
    return x0, y0, x1, y1


def draw_tex(dst, tex, M, opacity=1.0, gain=1.0, blur=0.0):
    """Composite a premultiplied mip texture through affine M (tex px -> screen px)."""
    H, W = dst.shape[:2]
    if opacity <= 0.002:
        return
    sc = float(np.sqrt(abs(np.linalg.det(M[:, :2]))))
    lvl = 0
    if sc < 1.0:
        lvl = int(min(np.floor(np.log2(1.0 / max(sc, 1e-6)) + 0.35), len(tex.levels) - 1))
    src = tex.levels[lvl]
    f = float(2 ** lvl)
    ML = M.copy()
    ML[:, :2] *= f
    r = _roi(ML, src.shape[1], src.shape[0], W, H, pad=blur * 3 + 2)
    if r is None:
        return
    x0, y0, x1, y1 = r
    ML[:, 2] -= (x0, y0)
    interp = cv2.INTER_LINEAR if sc * f <= 1.02 else cv2.INTER_CUBIC
    warp = cv2.warpAffine(src, ML[:2].astype(np.float64), (x1 - x0, y1 - y0), flags=interp,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    w = warp.astype(np.float32) * (1.0 / 255.0)
    if blur > 0.35:
        w = cv2.GaussianBlur(w, (0, 0), blur)
    a = w[..., 3:4] * opacity
    rgb = w[..., :3] * (np.float32(gain) * opacity)
    reg = dst[y0:y1, x0:x1]
    reg *= (1.0 - a)
    reg += rgb


def draw_shadow(dst, sh, pad, ds, M, strength):
    """Darken dst by a single-channel shadow map (stored at 1/ds, padded)."""
    H, W = dst.shape[:2]
    if strength <= 0.003:
        return
    Ms = M.copy()
    Ms[:, 2] = M[:, 2] - M[:, :2] @ np.float64([pad, pad])
    Ms[:, :2] = M[:, :2] * ds
    r = _roi(Ms, sh.shape[1], sh.shape[0], W, H, pad=2)
    if r is None:
        return
    x0, y0, x1, y1 = r
    Ms[:, 2] -= (x0, y0)
    warp = cv2.warpAffine(sh, Ms.astype(np.float64), (x1 - x0, y1 - y0), flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    dst[y0:y1, x0:x1] *= (1.0 - np.clip(warp * strength, 0, 0.92))[..., None]


def over(dst, layer):
    dst *= (1.0 - layer["alpha"])[..., None]
    dst += layer["rgb"]


# ---------------------------------------------------------------------------
# cached, resolution-independent pieces
# ---------------------------------------------------------------------------
@functools.lru_cache(maxsize=None)
def _stage_tile() -> np.ndarray:
    fine = tile_noise(1024, [(180, 1.0), (90, 0.7), (40, 0.5)], seed=7)
    mott = tile_noise(1024, [(3, 1.0), (7, 0.6), (15, 0.3)], seed=8)
    return (0.55 * fine + 0.45 * mott).astype(np.float32)


@functools.lru_cache(maxsize=None)
def _copy_textures():
    title = assets.Texture(typeset.text_rgba(COPY_TITLE, "display", 420, CREAM, tracking=0.012))
    brand = assets.Texture(typeset.text_rgba(COPY_BRAND, "display", 240, CREAM, tracking=0.07))
    cta = assets.Texture(typeset.text_rgba(COPY_CTA, "sans_bold", 120, tuple(0.84 * c for c in CREAM),
                                           tracking=0.26))
    o = assets.load_o_mark()
    return dict(title=title, brand=brand, cta=cta, o=assets.Texture(o) if o is not None else None)


@functools.lru_cache(maxsize=None)
def _sweep_texture(slot: str):
    """A soft, dark, out-of-focus crop of real fabric for a lens wipe."""
    g = assets.garments()[slot]
    x0, y0, x1, y1 = assets.SWEEP_CROPS[slot]
    ax, ay = g.px(x0, y0)
    bx, by = g.px(x1, y1)
    crop = g.tex.levels[0][int(ay):int(by), int(ax):int(bx)].astype(np.float32)
    # stretch the fabric to fill the sprite: this is a blur of colour and weave, not a product view
    a = crop[..., 3:4] / 255.0
    rgb = crop[..., :3] / np.maximum(a, 0.02)
    fill = cv2.blur(crop[..., :3], (61, 61)) / np.maximum(cv2.blur(a[..., 0], (61, 61)), 0.02)[..., None]
    rgb = np.where(a > 0.5, rgb, fill)
    small = cv2.resize(rgb, (192, 384), interpolation=cv2.INTER_AREA)
    small = cv2.GaussianBlur(small, (0, 0), 5.0) * 0.50          # near the lens: dark and soft
    yy, xx = np.mgrid[0:384, 0:192].astype(np.float32)
    ex = np.minimum(xx, 191 - xx) / 191.0
    alpha = np.clip(ex / 0.16, 0, 1) ** 1.5                       # soft leading and trailing edge
    rgba = np.dstack([np.clip(small, 0, 255), alpha * 255.0]).astype(np.uint8)
    return assets.Texture(rgba)


@functools.lru_cache(maxsize=8)
def _vignette(W: int, H: int) -> np.ndarray:
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.hypot((xx - W / 2) / (W / 2), (yy - H / 2) / (H / 2)) / np.sqrt(2)
    return (1.0 - 0.20 * np.clip(r, 0, 1) ** 2.4)[..., None].astype(np.float32)


# ---------------------------------------------------------------------------
# stage and light
# ---------------------------------------------------------------------------
def _pool(xs, ys, box, fall):
    x0, y0, x1, y1 = box
    dx = np.maximum(np.abs(xs - (x0 + x1) / 2) - (x1 - x0) / 2, 0)
    dy = np.maximum(np.abs(ys - (y0 + y1) / 2) - (y1 - y0) / 2, 0)
    return np.exp(-(np.hypot(dx, dy) / fall) ** 2)


def _stage(L, t, pose, scale, size, weights):
    W, H = size
    cx, cy, z = pose
    zs = z * scale
    # low-res light field in world space
    gw, gh = max(W // 12, 8), max(H // 12, 8)
    xs = (np.linspace(0, W, gw)[None, :] - W / 2) / zs + cx
    ys = (np.linspace(0, H, gh)[:, None] - H / 2) / zs + cy
    dark = np.ones((gh, gw), np.float64)
    drift = np.float64([10 * np.sin(t * 0.52 + 0.3), 7 * np.sin(t * 0.37 + 1.1)])   # residual light movement
    for slot in GARMENT_KEYS:
        wgt = weights[slot]
        if wgt > 0.003:
            b = L.P[slot].bbox
            box = (b[0] + drift[0], b[1] + drift[1], b[2] + drift[0], b[3] + drift[1])
            dark *= 1.0 - wgt * _pool(xs, ys, box, 135.0)
    wl = keyed(film.LOCK_LIGHT, t)
    if wl > 0.003:
        lx, ly = L.lockup["c"]
        d2 = 26 * np.float64([np.sin(t * 0.61), np.cos(t * 0.43)])
        box = (lx - 250 + d2[0], ly - 120 + d2[1], lx + 250 + d2[0], ly + 120 + d2[1])
        dark *= 1.0 - 0.80 * wl * _pool(xs, ys, box, 330.0)
    pool = (1.0 - dark).astype(np.float32)
    pool = cv2.resize(pool, (W, H), interpolation=cv2.INTER_CUBIC)
    # stage texture, slightly behind the garments
    tile = _stage_tile()
    k = zs * STAGE_PAR / STAGE_TEX_PER_UNIT
    M = np.float64([[k, 0, W / 2 - cx * zs * STAGE_PAR], [0, k, H / 2 - cy * zs * STAGE_PAR]])
    tex = cv2.warpAffine(tile, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
    lum = (0.60 + 1.02 * pool) * (1.0 + 0.16 * (tex - 0.5))
    frame = np.empty((H, W, 3), np.float32)
    warm = np.float32([1.045, 1.0, 0.945])
    for c in range(3):
        frame[..., c] = CHARCOAL[c] * lum * (1.0 + (warm[c] - 1.0) * pool)
    return frame, pool


# ---------------------------------------------------------------------------
# one sub-frame
# ---------------------------------------------------------------------------
def _render(L, t, scale, size, motion=(0.0, 0.0)):
    W, H = size
    pose = L.camera.pose(t)
    zs = pose[2] * scale
    S = _screen(pose, scale, size)
    weights = {k: film.light_weight(L.lights[k], t) for k in GARMENT_KEYS}
    frame, pool = _stage(L, t, pose, scale, size, weights)

    # garment shadows on the stage (only as strong as the light that makes them)
    for p in L.order:
        sh, pad, ds = p.shadow
        vis = 0.35 + 0.65 * weights[p.slot]
        draw_shadow(frame, sh, pad, ds, _compose(S, p.matrix()), strength=vis)

    th = draw_thread(t, L, pose=pose, scale=scale, size=size)

    stage_light = (0.42 + 0.58 * np.clip(pool * 1.25, 0, 1))[..., None]
    lay = th[LOOSE]
    if lay is not None:
        frame *= (1.0 - lay["shadow"])[..., None]
        frame *= (1.0 - lay["alpha"])[..., None]
        frame += lay["rgb"] * stage_light

    # garments: lit ones at their true colour, the rest dim and a little soft
    lit_mask = np.zeros((H, W), np.float32)      # how lit the garment under each pixel is
    for p in L.order:
        wgt = weights[p.slot]
        gain = AMBIENT + (1 - AMBIENT) * wgt
        focus = float(smoothstep(0.08, 0.6, wgt))
        blur = (1 - focus) * 2.2 * zs ** 0.5
        M = _compose(S, p.matrix())
        draw_tex(frame, p.garment.tex, M, gain=gain, blur=blur)
        # track the lit level for the stitches drawn on top
        g = p.garment
        r = _roi(M, g.tex.w, g.tex.h, W, H, pad=2)
        if r is not None:
            x0, y0, x1, y1 = r
            lvl = min(2, len(g.tex.levels) - 1)
            ML = M.copy()
            ML[:, :2] *= 2 ** lvl
            ML[:, 2] -= (x0, y0)
            a = cv2.warpAffine(np.ascontiguousarray(g.tex.levels[lvl][..., 3]), ML.astype(np.float64),
                               (x1 - x0, y1 - y0), flags=cv2.INTER_LINEAR).astype(np.float32) / 255.0
            reg = lit_mask[y0:y1, x0:x1]
            reg *= (1 - a)
            reg += a * gain

    lay = th[STITCH]
    if lay is not None:
        # the stitch stays readable on unlit pieces: it is the one thing that links them
        lm = np.clip(0.46 + 0.62 * lit_mask, 0, 1)[..., None]
        frame *= (1.0 - lay["shadow"] * np.clip(lit_mask + 0.3, 0, 1))[..., None]
        frame *= (1.0 - lay["alpha"])[..., None]
        frame += lay["rgb"] * lm

    _draw_copy(frame, L, t, S, zs)

    # fabric wipes
    for sw in film.SWEEPS:
        if sw["t0"] - 0.05 <= t <= sw["t1"] + 0.05:
            _draw_sweep(frame, L, t, sw, pose, scale, size)

    lay = th[FRONT]
    if lay is not None:
        _draw_front(frame, lay, zs, motion)
    return frame


def _draw_copy(frame, L, t, S, zs):
    T = _copy_textures()

    def place(tex, centre, height, opacity, scale=1.0, blur=0.0):
        if opacity <= 0.002:
            return
        k = height * scale / tex.h
        M = np.float64([[k, 0, centre[0] - k * tex.w / 2], [0, k, centre[1] - k * tex.h / 2]])
        draw_tex(frame, tex, _compose(S, M), opacity=opacity, blur=blur)

    # SAY LESS. sits in the world, over the collection, and drifts away with it
    op = keyed(film.TITLE["opacity"], t)
    if op > 0.002:
        tex = T["title"]
        h = L.title["width"] * tex.h / tex.w
        place(tex, L.title["c"], h, op, keyed(film.TITLE["scale"], t), keyed(film.TITLE["blur"], t) * zs / 1.0 * 0.5)
    lx, ly = L.lockup["c"]
    if T["o"] is not None:
        place(T["o"], (lx, ly + film.LOCK_O_Y), film.LOCK_O_H, keyed(film.LOCK_O["opacity"], t),
              keyed(film.LOCK_O["scale"], t))
    tb = T["brand"]
    hb = film.LOCK_BRAND_CAP * typeset.sprite_height_per_cap("display")
    place(tb, (lx, ly + film.LOCK_BRAND_Y + keyed(film.LOCK_BRAND["rise"], t)), hb,
          keyed(film.LOCK_BRAND["opacity"], t))
    hc = film.LOCK_CTA_CAP * typeset.sprite_height_per_cap("sans_bold")
    place(T["cta"], (lx, ly + film.LOCK_CTA_Y), hc, keyed(film.LOCK_CTA["opacity"], t))


def _draw_sweep(frame, L, t, sw, pose, scale, size):
    """A sleeve of real fabric passing close to the lens, tied to the camera move."""
    W, H = size
    cam = L.camera
    c0, cc, c1 = cam.pose(sw["t0"]), cam.pose(sw["cover"]), cam.pose(sw["t1"])
    d = np.float64([c1[0] - c0[0], c1[1] - c0[1]])
    horiz = abs(d[0]) >= abs(d[1])
    Fa, Fc = (W, H) if horiz else (H, W)
    Ea, Ec = 1.9 * Fa, 1.5 * Fc                      # on-screen extent along / across the move
    d0 = np.hypot(cc[0] - c0[0], cc[1] - c0[1]) * c0[2] * scale
    d1 = np.hypot(c1[0] - cc[0], c1[1] - cc[1]) * c1[2] * scale
    par = 1.04 * (Ea + Fa) / (2 * max(min(d0, d1), 1e-3))
    tex = _sweep_texture(sw["slot"])
    zc = cc[2] * scale * par
    wa, wc = Ea / zc, Ec / zc                        # world size at that parallax
    if horiz:
        kx, ky = wa / tex.w, wc / tex.h
    else:
        kx, ky = wc / tex.w, wa / tex.h
    M = np.float64([[kx, 0, cc[0] - kx * tex.w / 2], [0, ky, cc[1] - ky * tex.h / 2]])
    S = _screen(pose, scale, size, par=par)
    draw_tex(frame, tex, _compose(S, M), opacity=1.0)


def _line_kernel(v, length):
    n = int(min(max(length, 1), 181)) | 1
    ker = np.zeros((n, n), np.float32)
    c = n // 2
    u = np.float64(v) / (np.hypot(*v) + 1e-9)
    cv2.line(ker, (int(round(c - u[0] * c)), int(round(c - u[1] * c))),
             (int(round(c + u[0] * c)), int(round(c + u[1] * c))), 1.0, 1)
    return ker / ker.sum()


def _draw_front(frame, lay, zs, motion=(0.0, 0.0)):
    """Lifted thread: larger, defocused by how far it has risen, and streaked
    by its own (much faster) motion across the lens."""
    a = lay["alpha"]
    ys, xs = np.nonzero(a > 0)
    if ys.size == 0:
        return
    H, W = a.shape
    pmax = float(lay["lift"].max())
    streak = float(np.hypot(*motion)) * (pmax - 1.0) * 0.8
    if streak >= 3.0:
        ker = _line_kernel(motion, streak)
        lay = dict(lay, alpha=cv2.filter2D(a, -1, ker), rgb=cv2.filter2D(lay["rgb"], -1, ker),
                   lift=np.where(lay["lift"] > 0, lay["lift"], 0))
        num = cv2.filter2D(lay["lift"] * a, -1, ker)
        lay["lift"] = np.where(lay["alpha"] > 1e-4, num / np.maximum(lay["alpha"], 1e-4), 0).astype(np.float32)
        a = lay["alpha"]
        ys, xs = np.nonzero(a > 1e-3)
        if ys.size == 0:
            return
    smax = 1.15 * (pmax - 1.0) * zs
    if smax < 0.6:
        over(frame, dict(alpha=a, rgb=lay["rgb"] * 0.96))
        return
    padr = int(smax * 3 + 4)
    y0, y1 = max(ys.min() - padr, 0), min(ys.max() + padr + 1, H)
    x0, x1 = max(xs.min() - padr, 0), min(xs.max() + padr + 1, W)
    a = a[y0:y1, x0:x1]
    rgb = lay["rgb"][y0:y1, x0:x1] * 0.94
    lift = lay["lift"][y0:y1, x0:x1]
    # spread the lift value beyond the thread so the blur amount varies smoothly
    sg = max(smax * 1.2, 2.0)
    num = cv2.GaussianBlur(lift * a, (0, 0), sg)
    den = cv2.GaussianBlur(a, (0, 0), sg)
    pm = np.where(den > 1e-4, num / np.maximum(den, 1e-4), 1.0)
    want = np.clip(1.15 * (pm - 1.0) * zs / smax, 0, 1)          # 0..1 of the strongest blur
    stack = np.dstack([rgb, a])
    levels = [stack] + [cv2.GaussianBlur(stack, (0, 0), smax * f) for f in (0.34, 0.67, 1.0)]
    x = want * 3.0
    out = np.zeros_like(stack)
    for i, lv in enumerate(levels):
        wgt = np.clip(1.0 - np.abs(x - i), 0, 1)[..., None]
        out += lv * wgt
    reg = frame[y0:y1, x0:x1]
    reg *= (1.0 - out[..., 3:4])
    reg += out[..., :3]


# ---------------------------------------------------------------------------
# public
# ---------------------------------------------------------------------------
def render_time(L, t: float, scale: float = 1.0, samples: int | None = None, grain_seed: int = 0,
                grain: bool = True) -> np.ndarray:
    """Render the frame at time t as uint8 RGB, with temporal motion blur."""
    W = int(round(L.fmt.width * scale))
    H = int(round(L.fmt.height * scale))
    size = (W, H)
    shutter = 0.5 / FPS                                    # 180 degree shutter
    speed = L.camera.speed_px(t, L.fmt) * scale            # px / s on this canvas
    blur_px = speed * shutter
    a, b = L.camera.pose(t - shutter / 2), L.camera.pose(t + shutter / 2)
    v = np.float64([-(b[0] - a[0]), -(b[1] - a[1])]) * 0.5 * (a[2] + b[2]) * scale   # px over the shutter
    if samples is None:
        samples = int(np.clip(np.ceil(blur_px / 5.0), 1, 6))
    if samples <= 1:
        frame = _render(L, t, scale, size, motion=tuple(v))
    else:
        acc = np.zeros((H, W, 3), np.float32)
        for j in range(samples):
            tj = t + ((j + 0.5) / samples - 0.5) * shutter
            f = np.clip(_render(L, tj, scale, size, motion=tuple(v / samples)), 0, None)
            acc += f * f                                    # average in (approximately) linear light
        frame = np.sqrt(acc / samples)
        # smooth the gaps between temporal samples along the direction of travel
        seg = float(np.hypot(*v)) / samples
        if seg >= 2.0:
            frame = cv2.filter2D(frame, -1, _line_kernel(v, min(seg, 48)), borderType=cv2.BORDER_REPLICATE)
    frame *= _vignette(W, H)
    if grain:
        rng = np.random.default_rng(1000 + grain_seed)
        n = rng.standard_normal((H, W)).astype(np.float32)
        n = cv2.GaussianBlur(n, (0, 0), 0.55 * max(scale, 0.6) ** 0.5)
        lum = frame.mean(axis=2)
        frame += (n * (0.011 + 0.020 * np.clip(lum, 0, 1) * (1 - np.clip(lum, 0, 1)) * 4 * 0.5))[..., None]
    return (np.clip(frame, 0, 1) * 255.0 + 0.5).astype(np.uint8)


def render_frame(L, i: int, scale: float = 1.0, samples: int | None = None, grain: bool = True) -> np.ndarray:
    t = i / FPS
    if t >= STORY_END + 0.2:
        samples = 1
    return render_time(L, t, scale=scale, samples=samples, grain_seed=i, grain=grain)
