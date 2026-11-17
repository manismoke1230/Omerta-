"""Parallel frame rendering and H.264 encoding (Rec.709, yuv420p, 60 fps)."""
from __future__ import annotations

import multiprocessing as mp
import os
import subprocess
import time
from pathlib import Path

import cv2
import numpy as np

from . import film, render, review
from .config import FPS, N_FRAMES

_JOB = {}


def _init(name, scale, mode, samples):
    cv2.setNumThreads(1)
    _JOB.update(L=film.build(name), scale=scale, mode=mode, samples=samples)


def _one(i):
    L = _JOB["L"]
    fr = render.render_frame(L, i, scale=_JOB["scale"], samples=_JOB["samples"])
    if _JOB["mode"] in ("animatic", "preview"):
        fr = review.burn_in(fr, i, L.fmt, _JOB["mode"])
    return i, fr.tobytes()


def frames(name: str, scale: float, mode: str = "clean", samples=None, start=0, stop=N_FRAMES, procs=None):
    """Yield (index, HxWx3 uint8 bytes) in order, rendered across processes."""
    film.build(name)                        # warm caches before forking
    render._copy_textures()
    render._stage_tile()
    procs = procs or max(1, (os.cpu_count() or 2))
    ctx = mp.get_context("fork")
    with ctx.Pool(procs, initializer=_init, initargs=(name, scale, mode, samples)) as pool:
        yield from pool.imap(_one, range(start, stop), chunksize=2)


def encode(name: str, out: Path, scale: float = 1.0, mode: str = "clean", crf: int = 16,
           preset: str = "slow", samples=None, start=0, stop=N_FRAMES, on_frame=None) -> Path:
    """Render and encode the picture only (audio is muxed afterwards)."""
    L = film.build(name)
    W, H = int(round(L.fmt.width * scale)), int(round(L.fmt.height * scale))
    W, H = W - W % 2, H - H % 2
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p",
           "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-profile:v", "high",
           "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
           "-movflags", "+faststart", "-an", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    n = 0
    for i, buf in frames(name, scale, mode, samples, start, stop):
        if on_frame is not None:
            on_frame(i, buf, (W, H))
        proc.stdin.write(buf)
        n += 1
        if n % 240 == 0:
            el = time.time() - t0
            print(f"  {name} {mode}: frame {i + 1}/{stop}  {n / el:.1f} fps", flush=True)
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg failed")
    print(f"  wrote {out}  ({n} frames, {time.time() - t0:.0f}s)", flush=True)
    return out


def mux(video: Path, audio: Path, out: Path) -> Path:
    """Attach a stereo 48 kHz WAV as AAC without touching the picture."""
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-i", str(audio),
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-ac", "2",
                    "-movflags", "+faststart", "-shortest", str(out)], check=True)
    return out


def probe(path: Path) -> str:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "stream=codec_name,profile,width,height,r_frame_rate,pix_fmt,color_space,color_transfer,"
                        "color_primaries,color_range,sample_rate,channels,nb_frames,duration",
                        "-of", "compact=p=0:nk=0", str(path)], capture_output=True, text=True)
    return r.stdout.strip()


def still(name: str, t: float, scale: float = 1.0) -> np.ndarray:
    return render.render_time(film.build(name), t, scale=scale, grain_seed=int(round(t * FPS)))
