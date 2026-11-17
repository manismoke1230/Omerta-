"""World layout: where each garment lies on the stage, per aspect ratio.

One fixed tableau per format. The camera travels through it and finally
pulls back to show that everything it visited was one collection. Portrait
is a separate composition (restacked, shorter lateral travel), never a crop
of the landscape master.

World units: at camera zoom 1.0 one unit is one pixel of the full-resolution
frame (1920x1080 or 1080x1920).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import assets
from .config import FORMATS, Format, HERO


@dataclass
class Placement:
    slot: str
    garment: assets.Garment
    cx: float
    cy: float
    height: float          # world height of the garment's tight box
    tilt: float = 0.0      # degrees, in-plane
    z: int = 0             # draw order

    def __post_init__(self):
        g = self.garment
        self.k = self.height / g.th                    # world units per texture px
        self.width = g.tw * self.k
        self.shadow = assets.shadow_map(g, self.k)

    # texture px -> world ---------------------------------------------------
    def matrix(self) -> np.ndarray:
        g = self.garment
        th = np.deg2rad(self.tilt)
        c, s = np.cos(th) * self.k, np.sin(th) * self.k
        pcx = g.tight[0] + g.tw / 2
        pcy = g.tight[1] + g.th / 2
        return np.float64([[c, -s, self.cx - c * pcx + s * pcy],
                           [s, c, self.cy - s * pcx - c * pcy]])

    def world(self, nx: float, ny: float) -> np.ndarray:
        px, py = self.garment.px(nx, ny)
        m = self.matrix()
        return m[:, :2] @ np.float64([px, py]) + m[:, 2]

    def A(self, name: str) -> np.ndarray:
        return self.world(*self.garment.anchors[name])

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        return (self.cx - self.width / 2, self.cy - self.height / 2,
                self.cx + self.width / 2, self.cy + self.height / 2)

    def rect(self, x0: float, y0: float, x1: float, y1: float):
        a, b = self.world(x0, y0), self.world(x1, y1)
        return (min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))


# Garment heights (world units). Scaled so the body widths of the tops agree
# with each other and the jeans read at a believable length beside them.
HEIGHTS = dict(raglan_black=250, raglan_white=250, crest_crew=300, charcoal_ls=385,
               bomber=292, plaid=262, denim=420, track=640)

# The stitch runs as one straight line under both chest prints, so the long
# sleeve sits a touch lower than the crewneck (a "calm staggered pair").
_UNDERLINE_STAGGER = 17.4

SPECS = {
    "landscape": dict(
        slots=dict(
            raglan_black=(-759, -215), raglan_white=(-452, -215),
            crest_crew=(-759, 138), charcoal_ls=(-452, 138 + _UNDERLINE_STAGGER),
            plaid=(-155, -215), bomber=(-154, 196),
            denim=(142, -102), track=(644, 0),
        ),
        heights={},
        mirror=False,                  # hero and denim are entered from the left
        lineup=(0.0, 2.0, 1.0),        # camera pose (cx, cy, zoom) for the eight-piece frame
        title=dict(c=(-318, -18), width=1010),
        lockup=dict(c=(1800, 0), zoom=1.3),
    ),
    "portrait": dict(
        slots=dict(
            raglan_black=(-297, -634), raglan_white=(10, -634),
            crest_crew=(-297, -318), charcoal_ls=(10, -318 + _UNDERLINE_STAGGER),
            plaid=(307, -634), bomber=(308, -300),
            denim=(270, 258), track=(-180, 300),
        ),
        heights=dict(track=600, denim=470),
        mirror=True,                   # the stack turns back on itself: enter from the right
        lineup=(0.0, -60.0, 1.0),
        title=dict(c=(0, -486), width=800),
        lockup=dict(c=(0, 1700), zoom=1.22),
    ),
}


class Layout:
    def __init__(self, name: str):
        self.name = name
        self.fmt: Format = FORMATS[name]
        spec = SPECS[name]
        self.spec = spec
        self.mirror: bool = spec["mirror"]
        G = assets.garments()
        self.P: dict[str, Placement] = {}
        for z, (slot, (cx, cy)) in enumerate(spec["slots"].items()):
            h = spec["heights"].get(slot, HEIGHTS[slot])
            self.P[slot] = Placement(slot, G[slot], cx, cy, h, 0.0, z)
        # the hero is drawn last so it sits on top of anything it touches
        self.P[HERO].z = 99
        self.order = sorted(self.P.values(), key=lambda p: p.z)
        self.title = spec["title"]
        self.lockup = spec["lockup"]
        self.lineup = spec["lineup"]

    # ------------------------------------------------------------------ shots
    def fit(self, rect, pad: float = 0.08, zoom_mul: float = 1.0):
        """Camera pose that frames a world rect inside the garment-safe frame."""
        x0, y0, x1, y1 = rect
        fl, ft, fr, fb = self.fmt.frame_rect()
        aw, ah = fr - fl, fb - ft
        bw, bh = (x1 - x0) * (1 + 2 * pad), (y1 - y0) * (1 + 2 * pad)
        z = min(aw / bw, ah / bh) * zoom_mul
        return self.centre_on(((x0 + x1) / 2, (y0 + y1) / 2), z)

    def centre_on(self, point, zoom: float, bias=(0.0, 0.0)):
        """Pose placing a world point at the centre of the garment-safe frame."""
        fl, ft, fr, fb = self.fmt.frame_rect()
        fcx, fcy = (fl + fr) / 2 + bias[0], (ft + fb) / 2 + bias[1]
        cx = point[0] - (fcx - self.fmt.width / 2) / zoom
        cy = point[1] - (fcy - self.fmt.height / 2) / zoom
        return (float(cx), float(cy), float(zoom))

    def union(self, *slots: str):
        b = np.array([self.P[s].bbox for s in slots])
        return (b[:, 0].min(), b[:, 1].min(), b[:, 2].max(), b[:, 3].max())

    def max_zoom(self, slot: str, upscale: float = 1.6) -> float:
        """Largest zoom at which this garment's photo is enlarged by at most
        `upscale` on the full-resolution frame (brief: use only a crop the
        source resolution supports)."""
        return upscale / self.P[slot].k
