"""The film itself: stitch route, camera moves, light cues and wipes.

Everything here is written against garment anchors, so the same score plays
on both layouts. Times are seconds; scene boundaries fall on the 2.4 s bar.
"""
from __future__ import annotations

import functools

import numpy as np

from . import assets
from .camera import Camera
from .config import GARMENT_KEYS, HERO
from .curves import smoothstep
from .layout import Layout
from .thread import FRONT, LOOSE, STITCH, ThreadPath, Way

# Journey order (also the order the pieces light up in the final frame)
ORDER = ["raglan_black", "raglan_white", "crest_crew", "charcoal_ls", "bomber", "plaid", "denim", "track"]

# Lockup geometry in world units, relative to the lockup centre
LOCK_O_H = 150.0          # height of the O mark
LOCK_O_Y = -98.0
LOCK_BRAND_CAP = 60.0     # cap height of OMERTÀ ACADEMY
LOCK_BRAND_Y = 52.0
LOCK_CTA_CAP = 19.5
LOCK_CTA_Y = 138.0


# ---------------------------------------------------------------------------
# The stitch route
# ---------------------------------------------------------------------------
def _thread(L: Layout, cam: Camera) -> ThreadPath:
    P = L.P
    ways: list[Way] = []

    def g(slot, name, mode, label="", lift=1.0):
        x, y = P[slot].A(name)
        ways.append(Way(float(x), float(y), mode, lift, label))

    def w(pt, mode, label="", lift=1.0):
        ways.append(Way(float(pt[0]), float(pt[1]), mode, lift, label))

    span_env = {}

    def lifted(a, b, t_mid, peak, reach, env):
        """Span that rises toward the lens between stage points a and b.

        It passes through the point the camera occupies at `t_mid`, running
        across the direction of travel, so it sweeps the whole frame as the
        camera goes by. `env` is [(time, 0..1)]: how far it is in the air.
        """
        a, b = np.float64(a), np.float64(b)
        c = cam.base(t_mid)[:2]
        v = cam.base(t_mid + 0.05)[:2] - cam.base(t_mid - 0.05)[:2]
        n = np.float64([-v[1], v[0]]) / max(np.hypot(*v), 1e-6)
        if np.dot(a - c, n) < 0:
            n = -n                                  # n points to the side `a` is on
        sid = len(span_env)
        span_env[sid] = env
        q1, q2 = c + n * reach, c - n * reach
        air = [a, (a + q1) / 2, q1, c, q2, (q2 + b) / 2]
        lifts = [1.0, 1 + (peak - 1) * 0.35, 1 + (peak - 1) * 0.8, peak, 1 + (peak - 1) * 0.8, 1 + (peak - 1) * 0.35]
        # at rest the same thread lies in one calm arc from a to b
        d = b - a
        m = np.float64([-d[1], d[0]]) / max(np.hypot(*d), 1e-6)
        if np.dot(c - (a + b) / 2, m) < 0:
            m = -m
        sag = min(0.16 * np.hypot(*d), 26.0)
        for k, (pa, lf) in enumerate(zip(air, lifts)):
            f = k / 6.0
            rest = a + d * f + m * sag * np.sin(np.pi * f)
            ways.append(Way(float(rest[0]), float(rest[1]), FRONT, lf, "", sid,
                            float(pa[0] - rest[0]), float(pa[1] - rest[1])))
        w(b, LOOSE, lift=1.0)

    # 01  black-body raglan: up the dark knit, along both raglan seams, out the sleeve
    g("raglan_black", "tail", LOOSE, "start")
    g("raglan_black", "hem", STITCH, "g1_hem")
    g("raglan_black", "b1", STITCH)
    g("raglan_black", "b2", STITCH, "g1_b2")
    g("raglan_black", "b3", STITCH)
    g("raglan_black", "arm_l", STITCH, "g1_arm_l")
    g("raglan_black", "seam_l", STITCH)
    g("raglan_black", "col_l", STITCH, "g1_col_l")
    g("raglan_black", "col_c", STITCH)
    g("raglan_black", "col_r", STITCH, "g1_col_r")
    g("raglan_black", "seam_r", STITCH)
    g("raglan_black", "arm_r", STITCH, "g1_arm_r")
    g("raglan_black", "slv_r", STITCH)
    g("raglan_black", "out_r", LOOSE, "g1_out")
    # 02  white-body raglan: same seams, shoulders aligned, then down the side
    g("raglan_white", "in_l", STITCH, "g2_in")
    g("raglan_white", "slv_l", STITCH)
    g("raglan_white", "arm_l", STITCH, "g2_arm_l")
    g("raglan_white", "seam_l", STITCH)
    g("raglan_white", "col_l", STITCH, "g2_col_l")
    g("raglan_white", "col_c", STITCH)
    g("raglan_white", "col_r", STITCH, "g2_col_r")
    g("raglan_white", "seam_r", STITCH)
    g("raglan_white", "arm_r", STITCH, "g2_arm_r")
    g("raglan_white", "side_r", STITCH)
    g("raglan_white", "side_r2", STITCH)
    g("raglan_white", "hem_r", LOOSE, "g2_hem")
    # ... the same stitch crosses the foreground into the next piece
    a = P["raglan_white"].A("out")
    crew_in = P["crest_crew"].A("in_l")
    b = crew_in + np.float64([-30.0, -34.0])
    lifted(a, b, t_mid=4.74, peak=6.0, reach=46.0,
           env=[(4.12, 0.0), (4.40, 1.0), (5.02, 1.0), (5.44, 0.0)])
    # 03  one straight line under both worn prints; every letter stays clear
    g("crest_crew", "in_l", STITCH, "crew_in")
    g("crest_crew", "u_l", STITCH)
    g("crest_crew", "u_r", STITCH)
    g("crest_crew", "out_r", LOOSE, "crew_out")
    g("charcoal_ls", "in_l", STITCH, "ls_in")
    g("charcoal_ls", "u_l", STITCH)
    g("charcoal_ls", "u_r", STITCH)
    g("charcoal_ls", "out_r", LOOSE, "ls_out")
    # 04  behind the fabric, then up the bomber's zip to the ring
    g("bomber", "below", LOOSE)
    g("bomber", "hem", STITCH, "bom_hem")
    g("bomber", "z1", STITCH)
    g("bomber", "z2", STITCH)
    g("bomber", "z3", STITCH)
    g("bomber", "pull", LOOSE, "bom_pull")       # through the ring, then behind the hood
    g("bomber", "top", LOOSE)
    g("bomber", "hood", LOOSE)
    g("bomber", "above", LOOSE)
    # 05  the same axis becomes the plaid jacket's centre zip, then one plaid line
    g("plaid", "below", LOOSE)
    g("plaid", "hem", STITCH, "plaid_hem")
    g("plaid", "z1", STITCH)
    g("plaid", "z2", STITCH)
    g("plaid", "turn", STITCH, "plaid_turn")
    g("plaid", "line0", STITCH)
    g("plaid", "line1", STITCH, "plaid_l1")
    g("plaid", "line2", STITCH)
    g("plaid", "out_r", LOOSE, "plaid_out")
    # 06  that line carries into the denim camo
    if not L.mirror:
        dn = ["in_l", "hip_l", "d1", "d2", "d3", "thigh_r", "out_r"]
    else:
        pout = P["plaid"].A("out_r")
        din = P["denim"].A("in_r")
        w(pout + np.float64([30, 44]), LOOSE)
        w(np.float64([pout[0] + 16, (pout[1] * 2 + din[1]) / 3]), LOOSE)
        w(np.float64([din[0] + 30, (pout[1] + din[1] * 2) / 3]), LOOSE)
        w(din + np.float64([24, -58]), LOOSE)
        dn = ["in_r", "hip_r", "m1", "m2", "m3", "thigh_l", "out_l"]
    g("denim", dn[0], STITCH, "denim_in")
    g("denim", dn[1], STITCH)
    g("denim", dn[2], STITCH)
    g("denim", dn[3], STITCH, "denim_mid")
    g("denim", dn[4], STITCH)
    g("denim", dn[5], STITCH)
    g("denim", dn[6], LOOSE, "denim_out")
    # ... a foreground thread sweep carries the camera to the hero
    hero = P[HERO]
    seq = (["in_l", "b_l", "c1a", "c1b", "c2a", "c2b", "b_r", "out_r", "beside_r"] if not L.mirror
           else ["out_r", "b_r", "c2b", "c2a", "c1b", "c1a", "b_l", "in_l", "beside_l"])
    a = P["denim"].A(dn[6]) + np.float64([10.0 if not L.mirror else -10.0, 6.0])
    hin = hero.A(seq[0])
    b = hin + np.float64([-16.0 if not L.mirror else 16.0, 5.0])
    lifted(a, b, t_mid=14.34, peak=7.0, reach=40.0,
           env=[(13.74, 0.0), (14.02, 1.0), (14.64, 1.0), (15.10, 0.0)])
    # 07  along the top edge of the chest band, under both drawcords
    g(HERO, seq[0], LOOSE, "hero_in")            # hidden under the sleeve
    g(HERO, seq[1], STITCH, "hero_band")
    g(HERO, seq[2], LOOSE)                       # under the drawcord
    g(HERO, seq[3], STITCH)
    g(HERO, seq[4], LOOSE)
    g(HERO, seq[5], STITCH)
    g(HERO, seq[6], LOOSE, "hero_out")           # under the far sleeve
    g(HERO, seq[7], LOOSE)
    g(HERO, seq[8], LOOSE, "beside")
    # 08  ... and on to the O
    lx, ly = L.lockup["c"]
    beside = hero.A(seq[8])
    end = np.float64([lx - 0.5 * LOCK_O_H * 1.32 - 34.0, ly + LOCK_O_Y + 12.0])
    d = end - beside
    if abs(d[0]) > abs(d[1]):       # lockup lies to the side
        w(beside + np.float64([d[0] * 0.30, 46.0]), LOOSE)
        w(beside + np.float64([d[0] * 0.66, d[1] * 0.5 + 58.0]), LOOSE)
        w(end + np.float64([-150.0, 34.0]), LOOSE)
    else:                           # lockup lies below
        w(beside + np.float64([-34.0, d[1] * 0.28]), LOOSE)
        w(beside + np.float64([d[0] * 0.25 - 40.0, d[1] * 0.62]), LOOSE)
        w(end + np.float64([-120.0, -130.0]), LOOSE)
    w(end, LOOSE, "end")

    keys = [
        (-0.90, "start"), (-0.45, "g1_hem"), (0.30, "g1_b2"), (0.82, "g1_arm_l"), (1.32, "g1_col_l"),
        (1.74, "g1_col_r"), (2.10, "g1_arm_r"), (2.46, "g1_out"),
        (2.62, "g2_in"), (2.98, "g2_arm_l"), (3.38, "g2_col_l"), (3.72, "g2_col_r"), (4.02, "g2_arm_r"),
        (4.42, "g2_hem"),
        (4.98, "crew_in"), (5.76, "crew_out"), (5.90, "ls_in"), (6.74, "ls_out"),
        (7.34, "bom_hem"), (9.14, "bom_pull"),
        (9.52, "plaid_hem"), (10.52, "plaid_turn"), (11.52, "plaid_l1"), (11.88, "plaid_out"),
        (12.06, "denim_in"), (12.92, "denim_mid"), (13.82, "denim_out"),
        (14.56, "hero_in"), (14.80, "hero_band"), (16.10, "hero_out"), (16.95, "beside"),
        (19.18, "beside"), (20.42, "end"),
    ]
    return ThreadPath(ways, keys, span_env)


# ---------------------------------------------------------------------------
# Camera
# ---------------------------------------------------------------------------
def _camera(L: Layout) -> tuple[Camera, dict]:
    P = L.P
    S: dict[str, tuple[float, float, float]] = {}
    S["g1"] = L.fit(P["raglan_black"].bbox, 0.08)
    z_open = min(L.max_zoom("raglan_black", 3.2), S["g1"][2] * 3.0)
    S["open"] = L.centre_on(P["raglan_black"].world(0.385, 0.76), z_open)   # where the stitch is at 0.2 s
    pad12 = 0.06 if L.name == "landscape" else 0.03
    S["pair12"] = L.fit(L.union("raglan_black", "raglan_white"), pad12)
    S["pair34"] = L.fit(L.union("crest_crew", "charcoal_ls"), pad12 - 0.01)
    cr = P["crest_crew"].rect(0.22, 0.28, 0.78, 0.66)
    lr = P["charcoal_ls"].rect(0.10, 0.09, 0.90, 0.58)
    pr = (min(cr[0], lr[0]), min(cr[1], lr[1]), max(cr[2], lr[2]), max(cr[3], lr[3]))
    prints = L.fit(pr, 0.05)
    zp = min(prints[2], S["pair34"][2] * 1.42)
    S["prints"] = L.centre_on(((pr[0] + pr[2]) / 2, (pr[1] + pr[3]) / 2), zp)
    S["bomber"] = L.fit(P["bomber"].bbox, 0.07)
    zb = min(S["bomber"][2] * 1.8, L.max_zoom("bomber", 1.5), L.max_zoom("plaid", 1.5))
    S["pull"] = L.centre_on(P["bomber"].world(0.50, 0.215), zb)
    S["zip"] = L.centre_on(P["plaid"].world(0.515, 0.42), zb)
    S["plaid"] = L.fit(P["plaid"].bbox, 0.07)
    S["script"] = L.centre_on(P["plaid"].world(0.63, 0.34), min(S["plaid"][2] * 1.5, zb))
    zl = min(S["plaid"][2] * 1.9, L.max_zoom("plaid", 1.6), L.max_zoom("denim", 1.6))
    S["line"] = L.centre_on(P["plaid"].A("line2"), zl)
    S["denim_in"] = L.centre_on(P["denim"].A("hip_r" if L.mirror else "hip_l"), zl * 0.96)
    S["denim"] = L.fit(P["denim"].bbox, 0.05)
    S["hero"] = L.fit(P[HERO].bbox, 0.07)
    S["stripe"] = L.centre_on(P[HERO].world(0.70 if L.mirror else 0.30, 0.40), S["hero"][2] * 1.75)
    S["lineup"] = L.lineup
    lx, ly = L.lockup["c"]
    sl, st, sr, sb = L.fmt.safe_rect()
    zc = L.lockup["zoom"]
    S["lockup"] = (lx - ((sl + sr) / 2 - L.fmt.width / 2) / zc,
                   ly - ((st + sb) / 2 - L.fmt.height / 2) / zc, zc)
    whip = (2.2, 2.6)       # the one brief acceleration of each transition
    moves = [
        (-0.30, 1.20, S["g1"], (1.5, 3.0)),      # 01 already moving at frame 0; settled by 1.20
        (2.00, 3.00, S["pair12"]),               # 02 camo sleeve sweeps the lens
        (4.30, 5.30, S["pair34"]),               # 03 stitch crosses the foreground
        (5.55, 6.20, S["prints"], (2.0, 2.0)),   #    briefly approach the worn prints
        (6.25, 6.84, S["pair34"], (2.0, 2.0)),   #    and return to both silhouettes
        (6.86, 7.70, S["bomber"], whip),         # 04 pass behind fabric; reveal on the bar
        (8.10, 9.16, S["pull"], (2.0, 2.4)),     #    hood lining -> ring
        (9.30, 9.90, S["zip"], whip),            # 05 zip matches zip
        (9.96, 10.72, S["script"], (2.0, 2.2)),  #    across the chest script
        (10.78, 11.42, S["plaid"], (2.0, 2.6)),  #    widen to the full front
        (11.50, 11.94, S["line"], (2.0, 1.6)),   #    in on one orange plaid line
        (11.94, 12.32, S["denim_in"], (1.5, 2.4)),  # 06 carried into the denim
        (12.34, 13.34, S["denim"], (2.0, 3.0)),  #    both legs and the waistband
        (13.98, 14.68, S["stripe"], whip),       # 07 foreground thread sweep; hero lands on the bar
        (14.70, 15.20, S["hero"], (1.8, 2.6)),   #    complete front view by 15.20
        (16.80, 18.20, S["lineup"], (2.0, 3.0)), # 08 ease out to the collection
        (19.20, 21.40, S["lockup"], (2.0, 2.6)), #    the stitch leads to the O
    ]
    return Camera(S["open"], moves), S


# ---------------------------------------------------------------------------
# Light: each garment has a key-light weight over time
# ---------------------------------------------------------------------------
def _lights(L: Layout) -> dict[str, list[tuple[float, float]]]:
    def on_off(t_on, t_off, ramp=0.34):
        k = []
        if t_on is not None:
            k += [(t_on - ramp, 0.0), (t_on + ramp * 0.4, 1.0)]
        else:
            k += [(-1.0, 1.0)]
        k += [(t_off - ramp * 0.5, 1.0), (t_off + ramp, 0.0)]
        return k

    solo = {
        "raglan_black": on_off(None, 4.78),
        "raglan_white": on_off(2.36, 4.78),
        "crest_crew": on_off(4.84, 7.12),
        "charcoal_ls": on_off(4.90, 7.12),
        "bomber": on_off(7.18, 9.56),
        "plaid": on_off(9.60, 12.02),
        "denim": on_off(12.02, 14.44),
        "track": [(14.20, 0.0), (14.58, 1.0)],
    }
    keys = {}
    for i, slot in enumerate(ORDER):
        k = list(solo[slot])
        if slot != HERO:
            t = 16.86 + 0.10 * i                 # the collection lights up in journey order
            k += [(t, 0.0), (t + 0.55, 1.0), (17.95, 1.0), (18.50, 0.46), (19.30, 0.46)]
        else:
            k += [(19.30, 1.0)]
        k += [(19.60, k[-1][1]), (21.10, 0.0)]
        keys[slot] = k
    return keys


def light_weight(keys, t: float) -> float:
    ts = [k[0] for k in keys]
    if t <= ts[0]:
        return keys[0][1]
    if t >= ts[-1]:
        return keys[-1][1]
    i = int(np.searchsorted(ts, t, side="right") - 1)
    a, b = keys[i], keys[i + 1]
    if b[0] - a[0] < 1e-9:
        return b[1]
    return a[1] + (b[1] - a[1]) * float(smoothstep(a[0], b[0], t))


# ---------------------------------------------------------------------------
# Fabric wipes (the lens passes close to a garment)
# ---------------------------------------------------------------------------
SWEEPS = [
    dict(slot="raglan_black", t0=2.00, t1=3.00, cover=2.37),   # "the camo sleeve sweeps across the lens"
    dict(slot="charcoal_ls", t0=6.86, t1=7.70, cover=7.13),    # "pass behind fabric to continue"
]

# World-anchored copy. (time, value) keys.
TITLE = dict(opacity=[(17.95, 0.0), (18.55, 1.0), (19.35, 1.0), (19.95, 0.0)],
             blur=[(17.95, 14.0), (18.62, 0.0)], scale=[(17.95, 1.035), (18.95, 1.0)])
LOCK_O = dict(opacity=[(20.12, 0.0), (20.62, 1.0)], scale=[(20.12, 0.93), (20.95, 1.0)])
LOCK_BRAND = dict(opacity=[(20.42, 0.0), (20.95, 1.0)], rise=[(20.42, 12.0), (21.10, 0.0)])
LOCK_CTA = dict(opacity=[(20.88, 0.0), (21.36, 1.0)])
LOCK_LIGHT = [(19.60, 0.0), (21.00, 1.0)]


@functools.lru_cache(maxsize=None)
def build(name: str) -> Layout:
    """Layout with its thread, camera and light score attached."""
    assets.build_o_extraction()
    L = Layout(name)
    L.camera, L.shots = _camera(L)
    L.thread = _thread(L, L.camera)
    L.lights = _lights(L)
    assert set(L.P) == set(GARMENT_KEYS)
    return L
