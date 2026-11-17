"""Automated checks over all 1,440 frames.

These do not replace looking at the film; they catch the mechanical faults
the brief names: disappearing stitches, clipped type, jumps in lighting,
edge halos, a hero that never reads, an end card that does not hold.
"""
from __future__ import annotations

import json
import multiprocessing as mp
import os

import cv2
import numpy as np

from . import assets, film, matte, render
from .config import FPS, GARMENT_KEYS, HERO, N_FRAMES, STORY_END
from .curves import keyed
from .thread import FRONT, LOOSE, STITCH, draw_thread

_J = {}


def _init(name, scale):
    cv2.setNumThreads(1)
    _J.update(L=film.build(name), scale=scale)


def _frame(i):
    L, scale = _J["L"], _J["scale"]
    t = i / FPS
    fr = render.render_time(L, t, scale=scale, samples=1, grain=False)
    W, H = fr.shape[1], fr.shape[0]
    pose = L.camera.pose(t)
    th = draw_thread(t, L, pose=pose, scale=scale, size=(W, H))
    px = sum(int((th[m]["alpha"] > 0.3).sum()) for m in (LOOSE, STITCH, FRONT) if th[m] is not None)
    head = L.thread.head(t)
    hx = (head[0] - pose[0]) * pose[2] * scale + W / 2
    hy = (head[1] - pose[1]) * pose[2] * scale + H / 2
    inside = (0.06 * W < hx < 0.94 * W) and (0.06 * H < hy < 0.94 * H)
    small = cv2.resize(fr, (64, 64 * H // W if W > H else 64), interpolation=cv2.INTER_AREA).astype(np.float32)
    return dict(i=i, luma=float(fr.mean() / 255.0), thread_px=px, head_inside=bool(inside),
                progress=th["progress"], speed=L.camera.speed_px(t, L.fmt), thumb=small)


def _halo(key: str) -> dict:
    """Is the cut edge brighter than the fabric just inside it? (white-backdrop fringe)"""
    rgba, _ = matte.cutout(key)
    a = rgba[..., 3].astype(np.float32) / 255
    lum = rgba[..., :3].astype(np.float32).mean(axis=2)
    inside = cv2.distanceTransform((a > 0.5).astype(np.uint8), cv2.DIST_L2, 5)
    edge = (a > 0.25) & (inside <= 2.0)
    inner = (inside > 4.0) & (inside <= 9.0)
    e, n = float(lum[edge].mean()), float(lum[inner].mean())
    return dict(edge_luma=round(e, 1), inner_luma=round(n, 1), edge_minus_inner=round(e - n, 1))


def run(name: str, scale: float = 0.25, procs: int | None = None) -> dict:
    L = film.build(name)
    render._copy_textures()
    ctx = mp.get_context("spawn")      # fork + OpenCV threads can deadlock
    with ctx.Pool(procs or os.cpu_count(), initializer=_init, initargs=(name, scale)) as pool:
        rows = pool.map(_frame, range(N_FRAMES), chunksize=8)
    luma = np.float64([r["luma"] for r in rows])
    speed = np.float64([r["speed"] for r in rows])
    prog = np.float64([r["progress"] for r in rows])
    px = np.int64([r["thread_px"] for r in rows])
    inside = np.array([r["head_inside"] for r in rows])
    rep: dict = dict(format=name, frames=N_FRAMES, checked_at_scale=scale)

    # 1 the stitch: one progress value, never backwards, never vanishing while its head is in frame
    rep["stitch"] = dict(
        monotone=bool(np.all(np.diff(prog) >= -1e-6)),
        restarts=int((np.diff(prog) < -1e-6).sum()),
        frames_head_in_frame=int(inside.sum()),
        frames_head_in_frame_but_no_thread=[int(i) for i in np.nonzero(inside & (px == 0))[0]],
        frames_with_thread_visible=int((px > 0).sum()),
    )
    # 2 lighting: frame-to-frame change in mean level, judged on holds (transitions legitimately change)
    d = np.abs(np.diff(luma))
    hold = (speed[1:] < 250) & (speed[:-1] < 250)
    rep["lighting"] = dict(
        max_step_all=round(float(d.max()), 4), at_frame=int(d.argmax() + 1),
        max_step_on_holds=round(float(d[hold].max()), 4),
        hold_frames_over_1pct=[int(i + 1) for i in np.nonzero(hold & (d > 0.01))[0]],
    )
    # 3 type inside the copy-safe area while it is fully on
    sl, st, sr, sb = L.fmt.safe_rect()
    T = render._copy_textures()
    clipped = []

    def box(tex, centre, height, t):
        pose = L.camera.pose(t)
        w = height * tex.w / tex.h
        # trim the sprite padding: measure the visible ink
        a = tex.levels[0][..., 3]
        ys, xs = np.nonzero(a > 40)
        fx0, fx1, fy0, fy1 = xs.min() / tex.w, xs.max() / tex.w, ys.min() / tex.h, ys.max() / tex.h
        x0 = (centre[0] - w / 2 + fx0 * w - pose[0]) * pose[2] + L.fmt.width / 2
        x1 = (centre[0] - w / 2 + fx1 * w - pose[0]) * pose[2] + L.fmt.width / 2
        y0 = (centre[1] - height / 2 + fy0 * height - pose[1]) * pose[2] + L.fmt.height / 2
        y1 = (centre[1] - height / 2 + fy1 * height - pose[1]) * pose[2] + L.fmt.height / 2
        return [round(float(v), 1) for v in (x0, y0, x1, y1)]

    from . import typeset
    lx, ly = L.lockup["c"]
    items = {
        "SAY LESS. (18.6-19.3 s)": (T["title"], L.title["c"], L.title["width"] * T["title"].h / T["title"].w, [18.7, 19.0, 19.3]),
        "OMERTÀ ACADEMY (end card)": (T["brand"], (lx, ly + film.LOCK_BRAND_Y),
                                      film.LOCK_BRAND_CAP * typeset.sprite_height_per_cap("display"), [21.6, 23.9]),
        "EXPLORE THE COLLECTION. (end card)": (T["cta"], (lx, ly + film.LOCK_CTA_Y),
                                               film.LOCK_CTA_CAP * typeset.sprite_height_per_cap("sans_bold"), [21.6, 23.9]),
    }
    if T["o"] is not None:
        items["O mark (end card)"] = (T["o"], (lx, ly + film.LOCK_O_Y), film.LOCK_O_H, [21.6, 23.9])
    boxes = {}
    for label, (tex, c, h, times) in items.items():
        for t in times:
            b = box(tex, c, h, t)
            ok = b[0] >= sl and b[1] >= st and b[2] <= sr and b[3] <= sb
            boxes[f"{label} @ {t}"] = dict(box=b, inside_safe=bool(ok))
            if not ok:
                clipped.append(f"{label} @ {t}")
    rep["type"] = dict(safe_rect=[sl, st, sr, sb], boxes=boxes, clipped=clipped)
    # 4 end card: a full 2.4 s hold with only residual light movement
    f0 = int(STORY_END * FPS)
    poses = np.float64([L.camera.pose(i / FPS) for i in range(f0, N_FRAMES)])
    ref = rows[f0]["thumb"]
    diffs = [float(np.abs(rows[i]["thumb"] - ref).mean()) for i in range(f0, N_FRAMES)]
    ops = [keyed(film.LOCK_O["opacity"], f0 / FPS), keyed(film.LOCK_BRAND["opacity"], f0 / FPS),
           keyed(film.LOCK_CTA["opacity"], f0 / FPS)]
    rep["end_card"] = dict(frames=N_FRAMES - f0, seconds=(N_FRAMES - f0) / FPS,
                           camera_travel_px=round(float(np.ptp(poses[:, :2], axis=0).max() * poses[0, 2]), 3),
                           max_mean_pixel_change_8bit=round(max(diffs), 3),
                           all_copy_fully_on_at_21_6=bool(min(ops) >= 0.999))
    # 5 coverage: every piece lit and wholly in frame at some point; the hero on its own
    cov = {}
    for slot in GARMENT_KEYS:
        b = L.P[slot].bbox
        n = 0
        for i in range(0, N_FRAMES):
            t = i / FPS
            if film.light_weight(L.lights[slot], t) < 0.95:
                continue
            p = L.camera.pose(t)
            x0 = (b[0] - p[0]) * p[2] + L.fmt.width / 2
            x1 = (b[2] - p[0]) * p[2] + L.fmt.width / 2
            y0 = (b[1] - p[1]) * p[2] + L.fmt.height / 2
            y1 = (b[3] - p[1]) * p[2] + L.fmt.height / 2
            if x0 >= 0 and y0 >= 0 and x1 <= L.fmt.width and y1 <= L.fmt.height:
                n += 1
        cov[slot] = dict(frames_lit_and_fully_in_frame=n, seconds=round(n / FPS, 2))
    rep["coverage"] = cov
    rep["all_eight_appear"] = bool(all(v["frames_lit_and_fully_in_frame"] > 0 for v in cov.values()))
    rep["hero_reads"] = cov[HERO]["seconds"] >= 1.5
    # 6 how far each photo is enlarged at its tightest shot (brief: only crops the source supports)
    shots = {"raglan_black": ["open", "g1"], "raglan_white": ["pair12"], "crest_crew": ["prints", "pair34"],
             "charcoal_ls": ["prints", "pair34"], "bomber": ["pull", "bomber"], "plaid": ["line", "zip", "script", "plaid"],
             "denim": ["denim_in", "denim"], "track": ["stripe", "hero"]}
    rep["source_enlargement"] = {
        slot: {s: round(L.shots[s][2] * L.P[slot].k, 2) for s in names} for slot, names in shots.items()}
    # 7 matte edges
    rep["edges"] = {slot: _halo(assets.SLOT_FILE_KEY.get(slot, slot)) for slot in GARMENT_KEYS}
    rep["passed"] = bool(rep["stitch"]["monotone"] and not rep["stitch"]["frames_head_in_frame_but_no_thread"]
                         and not clipped and not rep["lighting"]["hold_frames_over_1pct"]
                         and rep["all_eight_appear"] and rep["hero_reads"]
                         and rep["end_card"]["camera_travel_px"] < 0.5 and rep["end_card"]["all_copy_fully_on_at_21_6"])
    return rep


def to_json(rep: dict) -> str:
    return json.dumps(rep, indent=2, ensure_ascii=False)
