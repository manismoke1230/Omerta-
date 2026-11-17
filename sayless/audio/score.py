"""Original score and sound design, synthesised in code (NumPy only).

Music: 100 BPM, warm low bass, muted keys, dry percussion, generous space.
  0.0  fibre movement only          7.2  weight added (bomber reveal)
  2.4  the pulse comes in          16.8  percussion stripped
                                   19.2  warm chord lands; tail under the end card

Sound design: every cue is tied to something visibly moving in the picture
(the cue list is built from the same timings as the camera and the stitch).
Nothing here is sampled, so there is nothing to license.
"""
from __future__ import annotations

import numpy as np

from ..config import BAR, DURATION, SR

N = int(round(DURATION * SR))
TWO_PI = 2 * np.pi


def db(x: float) -> float:
    return 10 ** (x / 20)


def midi(n: float) -> float:
    return 440.0 * 2 ** ((n - 69) / 12)


def fft_filter(x: np.ndarray, lo: float | None = None, hi: float | None = None, order: int = 2) -> np.ndarray:
    """Zero-phase Butterworth-shaped band limit (lo = high-pass corner, hi = low-pass corner)."""
    n = x.shape[0]
    X = np.fft.rfft(x, axis=0)
    f = np.fft.rfftfreq(n, 1 / SR)
    H = np.ones_like(f)
    if hi is not None:
        H *= 1 / np.sqrt(1 + (f / hi) ** (2 * order))
    if lo is not None:
        H *= 1 / np.sqrt(1 + (lo / np.maximum(f, 1e-6)) ** (2 * order))
    if X.ndim == 2:
        H = H[:, None]
    return np.fft.irfft(X * H, n=n, axis=0)


def place(buf: np.ndarray, t: float, sig: np.ndarray, gain: float = 1.0, pan=0.0) -> None:
    """Add a mono or stereo signal at time t. `pan` is -1..1 (scalar or per-sample)."""
    i0 = int(round(t * SR))
    if i0 >= N or i0 + sig.shape[0] <= 0:
        return
    if sig.ndim == 1:
        th = (np.clip(pan, -1, 1) + 1) * np.pi / 4
        sig = np.stack([sig * np.cos(th), sig * np.sin(th)], axis=1)     # equal-power pan
    a = max(i0, 0)
    b = min(i0 + sig.shape[0], N)
    buf[a:b] += sig[a - i0:b - i0] * gain


def _t(dur: float) -> np.ndarray:
    return np.arange(int(dur * SR)) / SR


# ---------------------------------------------------------------------------
# instruments
# ---------------------------------------------------------------------------
def key_note(f: float, dur: float, vel: float, tau: float = 0.6, bright: float = 1.0) -> np.ndarray:
    """Muted electric-piano tone (two-operator FM), returned as stereo."""
    t = _t(dur + 0.08)
    out = []
    for det in (1 - 0.0011, 1 + 0.0011):
        ph = TWO_PI * f * det * t
        idx = bright * (1.25 * np.exp(-t / 0.075) + 0.20)
        car = np.sin(ph + idx * np.sin(ph))
        tine = 0.07 * np.sin(ph * 7.0) * np.exp(-t / 0.018)
        out.append(car + tine)
    y = np.stack(out, axis=1)
    amp = (1 - np.exp(-t / 0.005)) * np.exp(-t / tau) * np.clip((dur + 0.08 - t) / 0.08, 0, 1)
    y = y * amp[:, None] * vel
    return fft_filter(y, hi=2300.0)


def bass_note(f: float, dur: float, vel: float) -> np.ndarray:
    t = _t(dur + 0.06)
    ph = TWO_PI * f * t
    y = np.sin(ph) + 0.38 * np.sin(2 * ph) + 0.14 * np.sin(3 * ph)
    amp = (1 - np.exp(-t / 0.009)) * (0.55 + 0.45 * np.exp(-t / 0.22)) * np.clip((dur + 0.06 - t) / 0.06, 0, 1)
    y = np.tanh(1.35 * y * amp) * 0.8 * vel
    return fft_filter(y, hi=420.0)


def kick(vel: float, weight: float = 1.0, rng=None) -> np.ndarray:
    t = _t(0.45 * weight)
    f = 43 + (116 - 43) * np.exp(-t / 0.030)
    ph = TWO_PI * np.cumsum(f) / SR
    y = np.sin(ph) * np.exp(-t / (0.115 * weight))
    click = rng.standard_normal(t.size) * np.exp(-t / 0.0025) * 0.12
    y = np.tanh(1.5 * (y + fft_filter(click, hi=3000.0))) * (1 - np.exp(-t / 0.0015))
    return y * vel


def rim(vel: float, rng) -> np.ndarray:
    t = _t(0.09)
    nz = fft_filter(rng.standard_normal(t.size), lo=1300.0, hi=5200.0)
    y = (0.55 * nz + 0.7 * np.sin(TWO_PI * 1720 * t)) * np.exp(-t / 0.016)
    return y * vel


def shaker(vel: float, rng) -> np.ndarray:
    t = _t(0.13)
    nz = fft_filter(rng.standard_normal(t.size), lo=5200.0, hi=11500.0)
    return nz * (1 - np.exp(-t / 0.007)) * np.exp(-t / 0.032) * vel


def pad(notes, dur: float, attack: float = 0.4, tau_rel: float = 1.5, hold: float | None = None) -> np.ndarray:
    """Warm, dark sustained chord: band-limited saws, lightly detuned, stereo."""
    t = _t(dur)
    y = np.zeros((t.size, 2))
    for n in notes:
        f0 = midi(n)
        for det, pan in ((-0.0035, -0.6), (0.0, 0.0), (0.0035, 0.6)):
            f = f0 * (1 + det)
            v = np.zeros(t.size)
            k = 1
            while f * k < 1500 and k <= 14:
                v += np.sin(TWO_PI * f * k * t + 0.7 * k) / k * (1 / (1 + (f * k / 800) ** 2))
                k += 1
            th = (pan + 1) * np.pi / 4
            y[:, 0] += v * np.cos(th)
            y[:, 1] += v * np.sin(th)
    hold = dur if hold is None else hold
    env = 0.5 - 0.5 * np.cos(np.pi * np.clip(t / attack, 0, 1))
    env *= np.where(t < hold, 1.0, np.exp(-(t - hold) / tau_rel))
    return y * env[:, None] / max(len(notes), 1)


def reverb(x: np.ndarray, decay: float = 0.55, length: float = 2.4, seed: int = 21) -> np.ndarray:
    """Small dark room: convolution with decaying noise."""
    rng = np.random.default_rng(seed)
    t = _t(length)
    ir = rng.standard_normal((t.size, 2)) * np.exp(-t / decay)[:, None]
    ir[: int(0.012 * SR)] *= np.linspace(0, 1, int(0.012 * SR))[:, None]
    ir = fft_filter(ir, lo=220.0, hi=3600.0)
    ir /= np.sqrt((ir ** 2).sum(axis=0, keepdims=True))
    n = x.shape[0] + ir.shape[0]
    size = 1 << int(np.ceil(np.log2(n)))
    y = np.fft.irfft(np.fft.rfft(x, size, axis=0) * np.fft.rfft(ir, size, axis=0), size, axis=0)
    return y[: x.shape[0]]


# ---------------------------------------------------------------------------
# music
# ---------------------------------------------------------------------------
CHORDS = {
    "Fm9": dict(root=41, keys=[53, 56, 60, 63, 67]),
    "Dbmaj7": dict(root=37, keys=[49, 53, 56, 60, 63]),
    "Abmaj7": dict(root=44, keys=[56, 60, 63, 67]),
    "Eb69": dict(root=39, keys=[51, 55, 58, 60, 65]),
    "Abmaj9": dict(root=44, keys=[44, 51, 55, 58, 60, 63, 70]),
}
# bar -> chord. Bar 0 has no pulse; bar 7 is stripped; bar 8 lands; bar 9 is the tail.
PROGRESSION = [None, "Fm9", "Dbmaj7", "Fm9", "Dbmaj7", "Abmaj7", "Eb69", "Dbmaj7", "Abmaj9", None]


def build_music() -> np.ndarray:
    rng = np.random.default_rng(100)
    drums = np.zeros((N, 2))
    bass = np.zeros((N, 2))
    keys = np.zeros((N, 2))
    pads = np.zeros((N, 2))

    def chord(t, notes, vel, tau, dur, roll=0.011, bright=1.0):
        for j, n in enumerate(notes):
            v = vel * (0.86 + 0.14 * rng.random()) * (0.92 if j == 0 else 1.0)
            place(keys, t + j * roll, key_note(midi(n), dur, v, tau, bright), 1.0)

    # bar 0: fibre movement belongs to the sound design; music only breathes in
    place(pads, 1.0, pad([41, 48], 1.8, attack=1.2, tau_rel=0.4, hold=1.3), db(-25))
    chord(1.2, [56, 63], 0.20, 1.0, 1.1)

    for bar in range(1, 7):
        t0 = bar * BAR
        c = CHORDS[PROGRESSION[bar]]
        heavy = bar >= 3                                   # weight arrives with the bomber, 7.20
        k = c["keys"]
        # muted keys: sparse, with room between phrases
        if bar % 2 == 1:
            chord(t0, k, 0.52, 0.62, 0.8)
            chord(t0 + 0.90, k[-3:], 0.36, 0.5, 0.5)
            chord(t0 + 2.10, k[-1:], 0.30, 0.6, 0.3)
        else:
            chord(t0, k, 0.48, 0.62, 0.8)
            chord(t0 + 1.05, k[-2:], 0.34, 0.5, 0.4)
            chord(t0 + 1.50, k[1:4], 0.30, 0.7, 0.7)
        # warm low bass
        r = c["root"]
        for dt, n, dur, v in ((0.0, r, 0.72, 1.0), (1.05, r, 0.26, 0.66), (1.5, r + 7, 0.40, 0.8), (2.1, r + 12, 0.22, 0.55)):
            place(bass, t0 + dt, bass_note(midi(n), dur, v), 1.0)
            if heavy and dt == 0.0:
                place(bass, t0 + dt, bass_note(midi(n - 12), dur + 0.25, 0.75), 1.0)
        # dry percussion
        place(drums, t0, kick(1.0, 1.25 if bar == 3 else 1.0, rng), db(-1.5 if heavy else -4))
        place(drums, t0 + 1.5, kick(0.8, 1.0, rng), db(-3 if heavy else -5.5))
        if heavy:
            place(drums, t0 + 2.25, kick(0.5, 0.8, rng), db(-6))
        for dt in ((1.8,) if bar == 1 else (0.6, 1.8)):
            place(drums, t0 + dt, rim(1.0, rng), db(-17), pan=0.18)
        start = 4 if bar == 1 else 0                      # the shaker only joins halfway through bar 1
        for step in range(start, 8):
            off = step % 2 == 1
            place(drums, t0 + step * 0.3 + (0.012 if off else 0.0), shaker(1.0, rng),
                  db(-22 if off else -26) * (0.9 + 0.2 * rng.random()), pan=-0.3)

    # bar 7 (16.8): percussion stripped. Held keys and one long bass note.
    t0 = 7 * BAR
    c = CHORDS["Dbmaj7"]
    chord(t0, c["keys"], 0.30, 1.5, 2.2, roll=0.016)
    chord(t0 + 1.2, c["keys"][1:], 0.18, 1.2, 1.1, roll=0.016)
    place(bass, t0, bass_note(midi(c["root"]), 2.25, 0.55), 1.0)
    place(pads, t0, pad([49, 56, 60, 63], 2.9, attack=1.4, tau_rel=0.35, hold=2.35), db(-23))

    # bar 8 (19.2): the warm chord lands, and its tail carries the end card
    t0 = 8 * BAR
    c = CHORDS["Abmaj9"]
    chord(t0, c["keys"], 0.36, 2.4, 4.6, roll=0.020, bright=0.9)
    place(bass, t0, bass_note(midi(32), 3.4, 0.55), 1.0)
    place(bass, t0, bass_note(midi(44), 3.0, 0.32), 1.0)
    place(pads, t0, pad([44, 51, 55, 58, 63], 4.75, attack=0.5, tau_rel=0.9, hold=2.6), db(-20.5))
    chord(21.6, [63, 70], 0.22, 1.6, 2.2, roll=0.03)        # a last quiet answer under the end card

    wet = reverb(keys * 0.9 + pads * 1.0)
    mix = (drums * db(-9.0) + bass * db(-10.5) + keys * db(-11.5) + pads + wet * db(-15.5))
    # the tail resolves to silence exactly at 24.0
    fade = np.clip((DURATION - np.arange(N) / SR) / 1.1, 0, 1) ** 1.5
    return mix * fade[:, None]


# ---------------------------------------------------------------------------
# sound design
# ---------------------------------------------------------------------------
def _bands(n: int, rng):
    nz = rng.standard_normal(n)
    return (fft_filter(nz, lo=260.0, hi=1100.0), fft_filter(nz, lo=1000.0, hi=3400.0),
            fft_filter(nz, lo=3000.0, hi=9000.0))


def sfx_fiber(dur: float, rng, bright: float = 1.0) -> np.ndarray:
    """A thread being drawn across cloth."""
    t = _t(dur)
    lo, mid, hi = _bands(t.size, rng)
    wob = np.interp(t, np.linspace(0, dur, max(int(dur * 11), 2)), 0.45 + 0.55 * rng.random(max(int(dur * 11), 2)))
    env = np.clip(t / 0.14, 0, 1) * np.clip((dur - t) / 0.28, 0, 1)
    return (0.25 * mid + 0.75 * bright * hi) * wob * env


def sfx_tick(rng, pitch: float = 1.0) -> np.ndarray:
    """One stitch biting into fabric."""
    t = _t(0.06)
    nz = fft_filter(rng.standard_normal(t.size), lo=2800.0) * np.exp(-t / 0.0035)
    tone = np.sin(TWO_PI * 2050 * pitch * t) * np.exp(-t / 0.004)
    thup = np.sin(TWO_PI * 185 * t) * np.exp(-t / 0.013)
    return 0.5 * nz + 0.45 * tone + 0.6 * thup


def sfx_brush(dur: float, rng, dark: bool = False) -> np.ndarray:
    """Fabric passing the lens."""
    t = _t(dur)
    lo, mid, hi = _bands(t.size, rng)
    x = t / dur
    bell = np.sin(np.pi * np.clip(x, 0, 1)) ** 1.6
    w_hi = np.exp(-((x - 0.55) / 0.22) ** 2)
    trem = 0.8 + 0.2 * np.sin(TWO_PI * 23 * t + 1.0)
    if dark:
        y = 1.0 * lo + 0.75 * mid + 0.25 * hi * w_hi
    else:
        y = 0.45 * lo + 0.8 * mid + 0.75 * hi * w_hi
    return y * bell * trem


def sfx_whoosh(dur: float, rng) -> np.ndarray:
    """A thread whipping past, close."""
    t = _t(dur)
    lo, mid, hi = _bands(t.size, rng)
    x = t / dur
    bell = np.sin(np.pi * np.clip(x, 0, 1)) ** 2.4
    return (0.15 * lo + 0.5 * mid * (1 - x) + 0.9 * hi * x ** 0.6) * bell


def sfx_zip(dur: float, rng, r0: float = 20.0, r1: float = 46.0, rise: bool = True) -> np.ndarray:
    """Zipper teeth, one at a time."""
    n = int(dur * SR)
    y = np.zeros(n + int(0.02 * SR))
    tc = 0.0
    while tc < dur:
        x = tc / dur
        rate = r0 + (r1 - r0) * x
        m = int(0.012 * SR)
        tt = np.arange(m) / SR
        f = 3100 * (1 + 0.22 * x) * (0.94 + 0.12 * rng.random())
        c = (np.sin(TWO_PI * f * tt) * np.exp(-tt / 0.0018)
             + 0.5 * fft_filter(rng.standard_normal(m), lo=2400.0, hi=7000.0) * np.exp(-tt / 0.0012))
        amp = (0.55 + 0.45 * rng.random()) * ((0.35 + 0.65 * x) if rise else np.sin(np.pi * x) ** 0.8)
        i = int(tc * SR)
        y[i:i + m] += c * amp
        tc += (1 / rate) * (0.92 + 0.16 * rng.random())
    return y[:n]


def sfx_clink(rng) -> np.ndarray:
    """A small metal ring touched."""
    t = _t(0.22)
    y = (np.sin(TWO_PI * 2860 * t) * np.exp(-t / 0.05) + 0.6 * np.sin(TWO_PI * 4330 * t) * np.exp(-t / 0.035)
         + 0.3 * np.sin(TWO_PI * 6210 * t) * np.exp(-t / 0.02))
    y += 0.4 * fft_filter(rng.standard_normal(t.size), lo=3000.0) * np.exp(-t / 0.002)
    return y


def sfx_impact(weight: float = 1.0) -> np.ndarray:
    """Restrained low impact."""
    t = _t(0.9)
    f = 37 + (64 - 37) * np.exp(-t / 0.085)
    ph = TWO_PI * np.cumsum(f) / SR
    y = np.sin(ph) * np.exp(-t / (0.30 * weight)) * (1 - np.exp(-t / 0.006))
    y += 0.25 * np.sin(2 * ph) * np.exp(-t / 0.12)
    return np.tanh(1.2 * y)


# (time, kind, level dB, pan, what is visibly moving). Pan follows the action on screen.
CUES = [
    (0.00, "fiber", -14, (-0.25, 0.0), "the stitch already travelling over dark knit (dur 1.3 s)"),
    (0.20, "tick", -16, -0.2, "stitch bites the black body"),
    (0.82, "tick", -16, -0.3, "stitch turns onto the raglan seam at the armpit"),
    (1.32, "tick", -17, -0.1, "stitch reaches the collar"),
    (2.04, "brush", -10, (-0.7, 0.7), "camo sleeve sweeps across the lens (dur 0.75 s)"),
    (2.98, "tick", -17, 0.3, "stitch turns onto the white raglan's seam"),
    (3.72, "tick", -17, 0.45, "stitch leaves the white raglan's collar"),
    (4.40, "whoosh", -12, (0.5, -0.6), "the stitch crosses the foreground (dur 0.62 s)"),
    (5.02, "tick", -16, -0.5, "stitch enters the crest crewneck"),
    (5.76, "tick", -17, -0.05, "stitch leaves the crewneck"),
    (5.92, "tick", -16, 0.1, "stitch enters the charcoal long sleeve"),
    (6.74, "tick", -17, 0.5, "stitch leaves the long sleeve"),
    (6.90, "brush_dark", -8, (-0.6, 0.6), "camera passes behind fabric (dur 0.6 s)"),
    (7.20, "impact", -11, 0.0, "bomber revealed, front-on"),
    (8.10, "zip", -16, 0.0, "stitch climbs beside the zip teeth (dur 1.0 s)"),
    (9.14, "clink", -15, 0.0, "stitch reaches the circular pull"),
    (9.32, "zipwhip", -12, 0.0, "camera runs up the zip axis into the plaid jacket (dur 0.46 s)"),
    (10.52, "tick", -16, 0.0, "stitch turns off the zip onto the plaid line"),
    (11.40, "tick", -17, 0.3, "stitch crossing the plaid body"),
    (11.52, "fiber_bright", -15, (0.0, 0.6), "the line carries out of the jacket into the denim (dur 0.7 s)"),
    (12.92, "tick", -16, 0.0, "stitch crosses the fly seam"),
    (13.60, "tick", -17, 0.3, "stitch reaches the far leg"),
    (14.02, "whoosh", -10, (-0.6, 0.6), "foreground thread sweep (dur 0.62 s)"),
    (14.40, "impact", -14, 0.0, "the hero revealed"),
    (14.82, "tick", -16, -0.3, "stitch surfaces on the chest band"),
    (16.10, "tick", -17, 0.3, "stitch leaves the chest band"),
    (19.20, "impact", -12, 0.0, "the stitch sets off toward the O; lineup starts to drift"),
    (19.24, "fiber", -15, (-0.5, 0.0), "the stitch runs to the O (dur 1.2 s)"),
    (20.42, "tick", -14, 0.0, "the stitch arrives at the O"),
]


def build_sfx() -> np.ndarray:
    rng = np.random.default_rng(300)
    out = np.zeros((N, 2))
    for t, kind, lvl, pan, _ in CUES:
        if kind == "fiber":
            y = sfx_fiber(1.3 if t < 1 else 1.2, rng)
        elif kind == "fiber_bright":
            y = sfx_fiber(0.7, rng, bright=1.3)
        elif kind == "tick":
            y = sfx_tick(rng, 0.94 + 0.12 * rng.random())
        elif kind == "brush":
            y = sfx_brush(0.75, rng)
        elif kind == "brush_dark":
            y = sfx_brush(0.6, rng, dark=True)
        elif kind == "whoosh":
            y = sfx_whoosh(0.62, rng)
        elif kind == "zip":
            y = sfx_zip(1.0, rng)
        elif kind == "zipwhip":
            y = sfx_zip(0.46, rng, r0=110.0, r1=260.0, rise=False)
        elif kind == "clink":
            y = sfx_clink(rng)
        elif kind == "impact":
            y = sfx_impact()
        else:
            raise ValueError(kind)
        y = y / (np.abs(y).max() + 1e-9)
        if isinstance(pan, tuple):
            pan = np.linspace(pan[0], pan[1], y.size)
        place(out, t, y, db(lvl), pan)
    return out
