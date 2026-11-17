"""Small numeric helpers: easing, monotone interpolation, splines, noise."""
from __future__ import annotations

import numpy as np


def clamp01(x):
    return np.clip(x, 0.0, 1.0)


def smoothstep(a, b, x):
    t = clamp01((np.asarray(x, dtype=np.float64) - a) / (b - a + 1e-12))
    return t * t * (3 - 2 * t)


def smootherstep(a, b, x):
    t = clamp01((np.asarray(x, dtype=np.float64) - a) / (b - a + 1e-12))
    return t * t * t * (t * (t * 6 - 15) + 10)


# --- "long eased move with one brief acceleration" ---------------------------
# Velocity follows a beta-shaped bump x^a (1-x)^b; its integral is the ease.
# a < b puts the acceleration early and leaves a long, soft settle.
_EASE_CACHE: dict[tuple[float, float], np.ndarray] = {}


def beta_ease(x, a: float = 2.0, b: float = 3.2):
    key = (a, b)
    lut = _EASE_CACHE.get(key)
    if lut is None:
        xs = np.linspace(0.0, 1.0, 4097)
        v = xs ** a * (1 - xs) ** b
        c = np.concatenate([[0.0], np.cumsum((v[1:] + v[:-1]) * 0.5)])
        lut = c / c[-1]
        _EASE_CACHE[key] = lut
    x = clamp01(x)
    return np.interp(x, np.linspace(0.0, 1.0, lut.size), lut)


# --- monotone cubic (Fritsch-Carlson PCHIP) ----------------------------------
class Pchip:
    """Shape-preserving cubic through (x, y). Never overshoots, so a
    monotone list of keys gives a monotone curve (the stitch never runs
    backwards) and repeated values give true holds."""

    def __init__(self, x, y):
        x = np.asarray(x, dtype=np.float64)
        y = np.asarray(y, dtype=np.float64)
        assert x.ndim == 1 and x.size >= 2 and np.all(np.diff(x) > 0), "keys must increase"
        h = np.diff(x)
        d = np.diff(y) / h
        m = np.zeros_like(y)
        if x.size == 2:
            m[:] = d[0]
        else:
            for i in range(1, x.size - 1):
                if d[i - 1] * d[i] > 0:
                    w1 = 2 * h[i] + h[i - 1]
                    w2 = h[i] + 2 * h[i - 1]
                    m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])
            m[0] = self._end(h[0], h[1], d[0], d[1])
            m[-1] = self._end(h[-1], h[-2], d[-1], d[-2])
        self.x, self.y, self.m, self.h = x, y, m, h

    @staticmethod
    def _end(h0, h1, d0, d1):
        m = ((2 * h0 + h1) * d0 - h0 * d1) / (h0 + h1)
        if np.sign(m) != np.sign(d0):
            return 0.0
        if np.sign(d0) != np.sign(d1) and abs(m) > 3 * abs(d0):
            return 3 * d0
        return m

    def __call__(self, t):
        t = np.clip(np.asarray(t, dtype=np.float64), self.x[0], self.x[-1])
        i = np.clip(np.searchsorted(self.x, t, side="right") - 1, 0, self.x.size - 2)
        h = self.h[i]
        s = (t - self.x[i]) / h
        y0, y1, m0, m1 = self.y[i], self.y[i + 1], self.m[i], self.m[i + 1]
        s2, s3 = s * s, s * s * s
        return ((2 * s3 - 3 * s2 + 1) * y0 + (s3 - 2 * s2 + s) * h * m0
                + (-2 * s3 + 3 * s2) * y1 + (s3 - s2) * h * m1)


def keyed(keys, t, ease=smoothstep):
    """Piecewise eased interpolation through [(time, value), ...]."""
    ts = [k[0] for k in keys]
    vs = [k[1] for k in keys]
    if t <= ts[0]:
        return vs[0]
    if t >= ts[-1]:
        return vs[-1]
    i = int(np.searchsorted(ts, t, side="right") - 1)
    f = float(ease(ts[i], ts[i + 1], t))
    return vs[i] + (vs[i + 1] - vs[i]) * f


# --- centripetal Catmull-Rom --------------------------------------------------
def catmull_rom(points: np.ndarray, per_seg: int = 48) -> tuple[np.ndarray, np.ndarray]:
    """Return (dense points, index of the source segment for each point)."""
    p = np.asarray(points, dtype=np.float64)
    n = len(p)
    ext = np.vstack([2 * p[0] - p[1], p, 2 * p[-1] - p[-2]])
    out, seg = [], []
    for i in range(n - 1):
        p0, p1, p2, p3 = ext[i], ext[i + 1], ext[i + 2], ext[i + 3]

        def tj(ti, a, b):
            return ti + max(np.linalg.norm(b - a), 1e-6) ** 0.5

        t0 = 0.0
        t1 = tj(t0, p0, p1)
        t2 = tj(t1, p1, p2)
        t3 = tj(t2, p2, p3)
        t = np.linspace(t1, t2, per_seg, endpoint=False)[:, None]
        a1 = (t1 - t) / (t1 - t0) * p0 + (t - t0) / (t1 - t0) * p1
        a2 = (t2 - t) / (t2 - t1) * p1 + (t - t1) / (t2 - t1) * p2
        a3 = (t3 - t) / (t3 - t2) * p2 + (t - t2) / (t3 - t2) * p3
        b1 = (t2 - t) / (t2 - t0) * a1 + (t - t0) / (t2 - t0) * a2
        b2 = (t3 - t) / (t3 - t1) * a2 + (t - t1) / (t3 - t1) * a3
        c = (t2 - t) / (t2 - t1) * b1 + (t - t1) / (t2 - t1) * b2
        out.append(c)
        seg.append(np.full(per_seg, i))
    out.append(p[-1:])
    seg.append(np.array([n - 2]))
    return np.vstack(out), np.concatenate(seg)


# --- deterministic value noise -----------------------------------------------
def value_noise_1d(x, seed: int = 0):
    x = np.asarray(x, dtype=np.float64)
    rng = np.random.default_rng(seed)
    tab = rng.random(1024)
    i = np.floor(x).astype(np.int64)
    f = x - i
    f = f * f * (3 - 2 * f)
    return tab[i % 1024] * (1 - f) + tab[(i + 1) % 1024] * f


def tile_noise(size: int, octaves, seed: int) -> np.ndarray:
    """Tileable fractal noise in [0, 1], built in the Fourier domain."""
    rng = np.random.default_rng(seed)
    acc = np.zeros((size, size), np.float64)
    fy = np.fft.fftfreq(size)[:, None] * size
    fx = np.fft.fftfreq(size)[None, :] * size
    rad = np.hypot(fx, fy)
    for freq, amp in octaves:
        spec = np.exp(-0.5 * ((rad - freq) / (0.35 * freq + 0.5)) ** 2)
        phase = np.exp(2j * np.pi * rng.random((size, size)))
        n = np.real(np.fft.ifft2(spec * phase))
        n /= n.std() + 1e-9
        acc += amp * n
    acc -= acc.min()
    acc /= acc.max() + 1e-9
    return acc.astype(np.float32)
