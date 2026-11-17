"""The shared camera: one continuous journey through the tableau.

A list of moves ``(t0, t1, pose)``. Between moves the camera holds. Every
move uses the same ease - a long, soft approach with one brief acceleration -
applied to position and log-zoom together, so nothing ever cuts.
A very small, slow drift keeps holds alive; it fades out before the end card.
"""
from __future__ import annotations

import numpy as np

from .config import STORY_END
from .curves import beta_ease, smoothstep


class Camera:
    def __init__(self, start_pose, moves, ease=(2.0, 3.2)):
        self.start = np.float64([start_pose[0], start_pose[1], np.log(start_pose[2])])
        self.moves = []
        prev = self.start
        last_t = -1e9
        for mv in moves:
            t0, t1, pose = mv[0], mv[1], mv[2]
            e = mv[3] if len(mv) > 3 else ease
            assert t1 > t0 >= last_t - 1e-9, f"camera moves overlap at {t0}"
            tgt = np.float64([pose[0], pose[1], np.log(pose[2])])
            self.moves.append((t0, t1, prev, tgt, e))
            prev, last_t = tgt, t1
        self.end = prev

    def base(self, t: float) -> np.ndarray:
        """Pose without drift, as (cx, cy, log zoom)."""
        cur = self.start
        for t0, t1, a, b, e in self.moves:
            if t < t0:
                return cur
            if t < t1:
                f = float(beta_ease((t - t0) / (t1 - t0), *e))
                return a + (b - a) * f
            cur = b
        return cur

    def pose(self, t: float) -> tuple[float, float, float]:
        cx, cy, lz = self.base(t)
        z = float(np.exp(lz))
        env = float(1.0 - smoothstep(STORY_END - 1.6, STORY_END - 0.25, t))
        amp = 5.0 * env / z                       # ~5 px of screen drift, whatever the zoom
        cx += amp * np.sin(2 * np.pi * t / 11.3 + 1.0)
        cy += amp * 0.6 * np.sin(2 * np.pi * t / 7.9 + 0.4)
        z *= 1.0 + 0.004 * env * np.sin(2 * np.pi * t / 9.1)
        return float(cx), float(cy), z

    def speed_px(self, t: float, fmt, dt: float = 1 / 240) -> float:
        """Approximate screen-space speed (full-res px per second) at the frame edge."""
        a, b = self.pose(t - dt), self.pose(t + dt)
        z = 0.5 * (a[2] + b[2])
        pan = np.hypot(b[0] - a[0], b[1] - a[1]) * z
        zoomv = abs(np.log(b[2] / a[2])) * 0.5 * np.hypot(fmt.width, fmt.height) * 0.5
        return float((pan + zoomv) / (2 * dt))
