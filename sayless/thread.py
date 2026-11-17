"""The stitch: one burnt-orange thread with one continuous progress value.

``ThreadPath`` is a single world-space curve through the whole collection.
``draw_thread(time, layout)`` draws everything from its start up to
``progress(time)``; it never restarts at a scene boundary.

Depth is real, not painted on:

* LOOSE  - thread lying on the stage; drawn *under* the garments, so it
           slips beneath a hem or sleeve and is hidden by the fabric;
* STITCH - running stitch on a garment; drawn *over* the fabric as dashes
           (the gaps are where the thread is inside the cloth);
* FRONT  - thread lifted toward the lens between two garments; drawn over
           everything, larger and out of focus.

The fibre is matte: twisted-ply shading, a soft cylinder falloff and a small
contact shadow. No glow, no additive light.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from .config import ORANGE
from .curves import Pchip, catmull_rom, value_noise_1d

LOOSE, STITCH, FRONT = 0, 1, 2
DS = 1.0                    # world units between stored samples
WIDTH = 2.4                 # thread diameter in world units at zoom 3
DASH, GAP = 10.5, 5.5       # running-stitch dash and gap, world units
PERIOD = DASH + GAP


@dataclass
class Way:
    x: float
    y: float
    mode: int = LOOSE       # mode of the span that starts at this waypoint
    lift: float = 1.0       # parallax at this waypoint (1 = on the stage plane)
    label: str = ""
    span: int = -1          # id of the lifted span this waypoint starts, if any


class ThreadPath:
    def __init__(self, ways: list[Way], keys: list[tuple[float, str]], span_env: dict | None = None):
        self.ways = ways
        self.span_env = span_env or {}
        pts = np.float64([[w.x, w.y] for w in ways])
        per = 64
        dense, _ = catmull_rom(pts, per_seg=per)
        d = np.hypot(*np.diff(dense, axis=0).T)
        cum = np.concatenate([[0.0], np.cumsum(d)])
        self.way_s = cum[np.arange(len(ways)) * per]
        self.length = float(cum[-1])
        n = int(self.length / DS) + 1
        s = np.linspace(0.0, self.length, n)
        x = np.interp(s, cum, dense[:, 0])
        y = np.interp(s, cum, dense[:, 1])
        seg = np.clip(np.searchsorted(self.way_s, s, side="right") - 1, 0, len(ways) - 2)
        modes = np.int32([w.mode for w in ways])
        lifts = np.float64([w.lift for w in ways])
        f = (s - self.way_s[seg]) / np.maximum(self.way_s[seg + 1] - self.way_s[seg], 1e-6)
        fs = f * f * (3 - 2 * f)
        self.mode = modes[seg]
        self.lift = lifts[seg] * (1 - fs) + lifts[seg + 1] * fs
        self.span = np.int32([w.span for w in ways])[seg]
        # a loose thread never lies perfectly straight: add a slow, small wander
        tx, ty = np.gradient(x), np.gradient(y)
        nrm = np.maximum(np.hypot(tx, ty), 1e-6)
        wander = (value_noise_1d(s / 46.0, 3) - 0.5) * 2 + (value_noise_1d(s / 17.0, 5) - 0.5)
        amp = np.where(self.mode == LOOSE, 2.4, 0.0) * np.sin(np.pi * f) ** 0.7
        self.x = x + (-ty / nrm) * wander * amp
        self.y = y + (tx / nrm) * wander * amp
        self.s = s
        self.labels = {w.label: float(self.way_s[i]) for i, w in enumerate(ways) if w.label}
        ts = [t for t, _ in keys]
        ss = [self.labels[lab] for _, lab in keys]
        assert all(b >= a for a, b in zip(ss, ss[1:])), "thread keys must not run backwards"
        self.keys = list(zip(ts, ss))
        self._prog = Pchip(ts, ss)

    def progress(self, t: float) -> float:
        """Arclength of the head at time t. Monotone: the stitch never retreats."""
        return float(self._prog(t))

    def head(self, t: float) -> np.ndarray:
        s = self.progress(t)
        return np.float64([np.interp(s, self.s, self.x), np.interp(s, self.s, self.y)])

    def state(self, t: float):
        """Mode, lift and opacity of every sample at time t.

        A lifted span is only in the air while the camera travels past it;
        afterwards it settles onto the stage and becomes ordinary loose thread.
        Returns a list of passes: (mode array, lift array, opacity array).
        """
        mode = self.mode.copy()
        lift = np.ones_like(self.lift)
        op_front = np.ones_like(self.lift)
        op_loose = np.ones_like(self.lift)
        both = np.zeros(self.lift.shape, bool)
        for sid, keys in self.span_env.items():
            m = self.span == sid
            ts = [k[0] for k in keys]
            vs = [k[1] for k in keys]
            e = float(np.interp(t, ts, vs))
            e = e * e * (3 - 2 * e)
            if e <= 1e-4:
                mode[m] = LOOSE
                continue
            lift[m] = 1.0 + (self.lift[m] - 1.0) * e
            x = min(e / 0.3, 1.0)                 # cross-fade air <-> stage, so nothing pops
            op_front[m] = x
            op_loose[m] = 1.0 - x
            both |= m & (x < 1.0)
        loose_mode = np.where(both, LOOSE, mode)
        return mode, loose_mode, lift, op_front, op_loose

    def at(self, label: str) -> np.ndarray:
        s = self.labels[label]
        return np.float64([np.interp(s, self.s, self.x), np.interp(s, self.s, self.y)])


# ---------------------------------------------------------------------------
_NOISE = np.random.default_rng(11).random(4096).astype(np.float32)


def _fiber(u: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Cheap streaky noise aligned with the ply (u along, v across)."""
    q = u * 1.7 + v * 5.3
    i = np.floor(q).astype(np.int64)
    f = (q - i).astype(np.float32)
    return _NOISE[i % 4096] * (1 - f) + _NOISE[(i + 1) % 4096] * f


def thread_width(zoom: float) -> float:
    """World diameter. Slightly fatter when the camera is far, so the stitch
    still reads in the eight-piece frame; slimmer in close-ups."""
    return WIDTH * (max(zoom, 0.2) / 3.0) ** -0.25


def _raster(path: ThreadPath, mode: int, s_head: float, pose, scale: float, size, pad_px: float,
            mode_arr=None, lift_arr=None, op_arr=None):
    """Rasterise one depth layer. Returns None or a dict of per-pixel data."""
    W, H = size
    cx, cy, zoom = pose
    zs = zoom * scale
    mode_arr = path.mode if mode_arr is None else mode_arr
    lift_arr = path.lift if lift_arr is None else lift_arr
    op_arr = np.ones_like(path.lift) if op_arr is None else op_arr
    sel = (mode_arr == mode) & (path.s <= s_head + 0.5) & (op_arr > 1e-3)
    if not sel.any():
        return None
    w_world = thread_width(zoom)
    # contiguous runs of this mode
    idx = np.nonzero(sel)[0]
    breaks = np.nonzero(np.diff(idx) > 1)[0]
    starts = np.concatenate([[0], breaks + 1])
    ends = np.concatenate([breaks, [idx.size - 1]])
    segs = []          # per segment arrays collected over runs
    for a, b in zip(starts, ends):
        i0, i1 = idx[a], idx[b]
        if i1 - i0 < 1:
            continue
        p = lift_arr[i0:i1 + 1]
        opv = op_arr[i0:i1 + 1]
        sx = (path.x[i0:i1 + 1] - cx) * p * zs + W / 2
        sy = (path.y[i0:i1 + 1] - cy) * p * zs + H / 2
        su = path.s[i0:i1 + 1]
        # a lifted thread is close to the lens: it reads much larger than its parallax alone
        wpx = np.maximum(w_world * zs * p ** 1.6, 1.25 * scale ** 0.5)
        # decimate to ~1.6 px (or a third of the width) on screen
        d = np.hypot(np.diff(sx), np.diff(sy))
        cum = np.concatenate([[0.0], np.cumsum(d)])
        step = float(np.clip(np.median(wpx) / 3.0, 1.6, 9.0))
        tgt = np.arange(0.0, cum[-1] + step, step)
        j = np.unique(np.clip(np.searchsorted(cum, tgt), 0, cum.size - 1))
        if j.size < 2:
            continue
        sx, sy, su, wpx, p, opv = sx[j], sy[j], su[j], wpx[j], p[j], opv[j]
        ua = float(path.s[i0])
        ub = float(min(path.s[i1], s_head))
        n = sx.size - 1
        segs.append(dict(x0=sx[:-1], y0=sy[:-1], x1=sx[1:], y1=sy[1:], u0=su[:-1], u1=su[1:],
                         w=(wpx[:-1] + wpx[1:]) / 2, p=(p[:-1] + p[1:]) / 2,
                         op=(opv[:-1] + opv[1:]) / 2, ua=np.full(n, ua), ub=np.full(n, ub)))
    if not segs:
        return None
    S = {k: np.concatenate([g[k] for g in segs]) for k in segs[0]}
    # cull segments outside the frame
    m = S["w"] * 0.5 + pad_px + 2
    vis = ((np.maximum(S["x0"], S["x1"]) > -m) & (np.minimum(S["x0"], S["x1"]) < W + m)
           & (np.maximum(S["y0"], S["y1"]) > -m) & (np.minimum(S["y0"], S["y1"]) < H + m))
    if not vis.any():
        return None
    S = {k: v[vis] for k, v in S.items()}
    n = S["x0"].size
    lab = np.full((H, W), -1, np.int32)
    sh = 3
    f = 1 << sh
    # clamp far-off coordinates so the fixed-point rasteriser cannot overflow
    lim = 30000.0
    X0 = np.round(np.clip(S["x0"], -lim, lim) * f).astype(np.int64)
    Y0 = np.round(np.clip(S["y0"], -lim, lim) * f).astype(np.int64)
    X1 = np.round(np.clip(S["x1"], -lim, lim) * f).astype(np.int64)
    Y1 = np.round(np.clip(S["y1"], -lim, lim) * f).astype(np.int64)
    T = np.ceil(S["w"] + 3).astype(np.int64)
    for k in range(n):
        cv2.line(lab, (int(X0[k]), int(Y0[k])), (int(X1[k]), int(Y1[k])), k, int(T[k]), cv2.LINE_8, sh)
    ys, xs = np.nonzero(lab >= 0)
    if ys.size == 0:
        return None
    k = lab[ys, xs]
    ax, ay = S["x0"][k], S["y0"][k]
    dx, dy = S["x1"][k] - ax, S["y1"][k] - ay
    ln = np.maximum(np.hypot(dx, dy), 1e-6)
    px, py = xs - ax, ys - ay
    tt = np.clip((px * dx + py * dy) / (ln * ln), -0.6, 1.6)
    v = (dx * py - dy * px) / ln                               # signed distance, px
    u = S["u0"][k] + tt * (S["u1"][k] - S["u0"][k])            # world arclength
    w = S["w"][k]
    upx = w / thread_width(zoom)                               # px per world unit along the thread here
    return dict(ys=ys, xs=xs, u=u, v=v, w=w, upx=upx, p=S["p"][k], op=S["op"][k], ua=S["ua"][k], ub=S["ub"][k],
                nx=-dy / ln, ny=dx / ln)


def _shade(R: dict, mode: int, zoom: float) -> tuple[np.ndarray, np.ndarray]:
    """Per-pixel alpha and colour for a rasterised layer."""
    u, v, w, upx = R["u"], R["v"], R["w"], R["upx"]
    r = w * 0.5
    # distance past the ends of the drawn span (round caps, incl. the moving head)
    du = np.maximum(np.maximum(R["ua"] - u, u - R["ub"]), 0.0) * upx
    if mode == STITCH:
        c = (u % PERIOD) - DASH * 0.5                           # centred on a dash
        c = np.where(c > PERIOD * 0.5, c - PERIOD, c)
        half = np.maximum(DASH * 0.5 * upx - r, 0.0)
        dd = np.maximum(np.abs(c) * upx - half, 0.0)
        du = np.maximum(du, dd)
        along = np.clip(np.abs(c) / (DASH * 0.5), 0, 1)         # 0 mid-dash -> 1 at the dive
    else:
        along = np.zeros_like(u)
    dist = np.hypot(du, v)
    alpha = np.clip(r - dist + 0.5, 0.0, 1.0)
    thin = np.clip(w, 0.0, 1.0)                                 # sub-pixel threads fade, not alias
    alpha = alpha * thin * R["op"]
    # --- matte fibre shading ---------------------------------------------
    n = np.clip(v / np.maximum(r, 1e-3), -1, 1)
    height = np.sqrt(np.maximum(1 - n * n, 0.0))
    # light from the upper-left; the thread normal decides which flank is lit
    flank = -(R["nx"] * -0.55 + R["ny"] * -0.83) * n
    lit = np.clip(0.60 + 0.34 * height + 0.20 * flank, 0.0, 1.15)
    detail = float(np.clip((np.median(w) - 2.5) / 5.0, 0.0, 1.0))  # no ply pattern when it would alias
    pitch = WIDTH * 1.15
    ply = 0.5 + 0.5 * np.cos(2 * np.pi * (u / pitch + n * 0.5))
    lit = lit * (1 - detail * 0.26 * ply ** 1.4)
    lit = lit * (1 + detail * 0.10 * (_fiber(u * 2.2, n) - 0.5))
    if mode == STITCH:
        lit = lit * (1 - 0.30 * along ** 3)                      # each stitch sinks into the cloth
    base = np.float32(ORANGE)
    col = base[None, :] * lit[:, None].astype(np.float32)
    # the ply valleys go slightly redder/darker, the crowns slightly paler
    col = col * np.float32([1.0, 0.985, 0.96])[None, :] + (lit[:, None] > 0.98) * 0.012
    return alpha.astype(np.float32), np.clip(col, 0, 1).astype(np.float32)


def draw_thread(time: float, layout, pose=None, scale: float = 1.0, size=None) -> dict:
    """Draw the stitch as it stands at `time`.

    Returns {LOOSE|STITCH|FRONT: layer}. A layer is None or a dict with
    ``alpha`` (H, W), ``rgb`` premultiplied (H, W, 3), ``shadow`` (H, W)
    and, for FRONT, ``lift`` (H, W) so the renderer can defocus it.
    `layout` owns the thread path and the camera; `pose`/`scale`/`size`
    default to the layout's camera at `time` and the full frame.
    """
    path: ThreadPath = layout.thread
    if pose is None:
        pose = layout.camera.pose(time)
    if size is None:
        size = (int(round(layout.fmt.width * scale)), int(round(layout.fmt.height * scale)))
    W, H = size
    s_head = path.progress(time)
    zoom = pose[2]
    out = {}
    mode_t, loose_mode_t, lift_t, op_front, op_loose = path.state(time)
    for mode in (LOOSE, STITCH, FRONT):
        if mode == LOOSE:
            R = _raster(path, mode, s_head, pose, scale, size, 12 * scale, loose_mode_t,
                        np.ones_like(lift_t), np.where(loose_mode_t != mode_t, op_loose, 1.0))
        else:
            R = _raster(path, mode, s_head, pose, scale, size, 12 * scale, mode_t, lift_t,
                        op_front if mode == FRONT else None)
        if R is None:
            out[mode] = None
            continue
        a, col = _shade(R, mode, zoom)
        alpha = np.zeros((H, W), np.float32)
        rgb = np.zeros((H, W, 3), np.float32)
        ys, xs = R["ys"], R["xs"]
        alpha[ys, xs] = a
        rgb[ys, xs] = col * a[:, None]
        layer = dict(alpha=alpha, rgb=rgb)
        # small contact shadow: offset down-right, a little soft. Matte, not a glow.
        wmed = float(np.median(R["w"]))
        if mode != FRONT:
            k = 0.34 if mode == STITCH else 0.55
            off = np.float32([[1, 0, 0.55 * k * wmed + 0.4], [0, 1, 0.85 * k * wmed + 0.6]])
            sh = cv2.warpAffine(alpha, off, (W, H))
            sh = cv2.GaussianBlur(sh, (0, 0), max(0.22 * wmed, 0.6))
            layer["shadow"] = sh * (0.50 if mode == STITCH else 0.62)
        else:
            lift = np.zeros((H, W), np.float32)
            lift[ys, xs] = R["p"].astype(np.float32)
            layer["lift"] = lift
            layer["shadow"] = None
        out[mode] = layer
    out["progress"] = s_head
    return out
