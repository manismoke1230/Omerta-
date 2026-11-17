"""Stems, voice ducking, loudness and true-peak control, WAV output.

Targets from the brief: about -14 LUFS integrated, true peak <= -1 dBTP,
music at least 12 dB under the voice while it speaks, stereo 48 kHz.
"""
from __future__ import annotations

import json
import re
import subprocess
import wave
from pathlib import Path

import cv2
import numpy as np

from ..config import ASSETS, DURATION, SR, VO_LINES
from . import score

TARGET_LUFS = -14.0
CEILING_DBTP = -1.0
VOICE_DIR = ASSETS / "voice"


def write_wav(path: Path, x: np.ndarray) -> None:
    """24-bit PCM stereo, 48 kHz."""
    path.parent.mkdir(parents=True, exist_ok=True)
    y = np.clip(x, -1, 1)
    i = np.round(y * 8388607.0).astype("<i4")
    raw = i.reshape(-1).astype("<i4").tobytes()
    b = np.frombuffer(raw, np.uint8).reshape(-1, 4)[:, :3].tobytes()
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(3)
        w.setframerate(SR)
        w.writeframes(b)


def read_wav_any(path: Path) -> np.ndarray:
    """Decode any audio file to float stereo 48 kHz via FFmpeg."""
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"],
                       capture_output=True, check=True)
    return np.frombuffer(r.stdout, "<f4").reshape(-1, 2).astype(np.float64)


def measure(x: np.ndarray, tmp: Path) -> dict:
    """Integrated loudness (LUFS) and true peak (dBTP) per EBU R128, via FFmpeg."""
    write_wav(tmp, x)
    r = subprocess.run(["ffmpeg", "-nostats", "-i", str(tmp), "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True)
    s = r.stderr[r.stderr.rfind("Summary:"):]
    i = float(re.search(r"I:\s+(-?[\d.]+) LUFS", s).group(1))
    lra = float(re.search(r"LRA:\s+(-?[\d.]+) LU", s).group(1))
    tp = float(re.search(r"Peak:\s+(-?[\d.]+) dBFS", s).group(1))
    return dict(lufs=i, lra=lra, true_peak=tp)


def load_voice() -> np.ndarray | None:
    """assets/voice/voice.wav (one take, aligned to 0:00) or line_1.wav .. line_6.wav
    placed at the brief's start times. Returns None when nothing is supplied."""
    n = score.N
    take = next((p for p in sorted(VOICE_DIR.glob("voice.*")) if p.suffix.lower() in (".wav", ".mp3", ".m4a", ".flac", ".aiff")), None)
    if take is not None:
        v = read_wav_any(take)
        out = np.zeros((n, 2))
        out[: min(n, len(v))] = v[:n]
        return out
    lines = sorted(VOICE_DIR.glob("line_*.*"))
    if not lines:
        return None
    out = np.zeros((n, 2))
    for p in lines:
        k = int(re.search(r"line_(\d+)", p.stem).group(1)) - 1
        v = read_wav_any(p)
        i0 = int(VO_LINES[k][0] * SR)
        m = min(len(v), n - i0)
        out[i0:i0 + m] += v[:m]
    return out


def duck(music: np.ndarray, voice: np.ndarray, margin_db: float = 12.0) -> tuple[np.ndarray, np.ndarray]:
    """Hold the music at least `margin_db` under the voice while it speaks."""
    win = int(0.05 * SR)

    def rms_db(x):
        p = cv2.blur((x ** 2).mean(axis=1).astype(np.float32).reshape(-1, 1), (1, win)).ravel()
        return 10 * np.log10(np.maximum(p, 1e-12))

    v, m = rms_db(voice), rms_db(music)
    speaking = v > (v.max() - 32)
    need = np.where(speaking, np.maximum(m - (v - margin_db) + 1.5, 0.0), 0.0).astype(np.float32)
    # hold the reduction across syllable gaps, then smooth: fast down, slow back up
    need = cv2.dilate(need.reshape(-1, 1), np.ones((int(0.30 * SR), 1), np.uint8)).ravel()
    need = cv2.GaussianBlur(need.reshape(-1, 1), (1, 0), sigmaX=1e-3, sigmaY=0.06 * SR).ravel()
    g = 10 ** (-need / 20)
    return music * g[:, None], g


def build(out_dir: Path) -> dict:
    """Synthesise, mix and master. Writes stems and masters; returns a report."""
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp = out_dir / "_measure.wav"
    music = score.build_music()
    sfx = score.build_sfx()
    voice = load_voice()
    report = dict(voice_supplied=voice is not None, cues=len(score.CUES))
    if voice is not None:
        music, g = duck(music, voice)
        report["max_duck_db"] = float(-20 * np.log10(g.min()))
    stems = dict(music=music, sfx=sfx)
    if voice is not None:
        stems["voice"] = voice

    def master(parts: list[str]) -> tuple[np.ndarray, float, np.ndarray, dict]:
        mix = sum(stems[p] for p in parts)
        gain = 1.0
        curve = np.ones(mix.shape[0], np.float32)
        m = {}
        for _ in range(4):
            y = mix * gain
            curve = _limit_curve(y, CEILING_DBTP - 0.3)
            y = y * curve[:, None]
            m = measure(y, tmp)
            err = TARGET_LUFS - m["lufs"]
            if abs(err) < 0.1:
                break
            gain *= 10 ** (err / 20)
        return y, gain, curve, m

    full_parts = [p for p in ("voice", "music", "sfx") if p in stems]
    full, gain, curve, m_full = master(full_parts)
    write_wav(out_dir / "master.wav", full)
    report["master"] = m_full
    # stems carry the master gain and limiter curve, so they sum back to the master exactly
    for name in full_parts:
        write_wav(out_dir / f"stem_{name}.wav", stems[name] * gain * curve[:, None])
    if voice is not None:
        clean, _, _, m_clean = master(["music", "sfx"])
        write_wav(out_dir / "master_no_voice.wav", clean)
        report["master_no_voice"] = m_clean
    else:
        # no voice recorded yet: the master *is* the clean version
        write_wav(out_dir / "master_no_voice.wav", full)
        report["master_no_voice"] = m_full
    tmp.unlink(missing_ok=True)
    report["duration_s"] = full.shape[0] / SR
    (out_dir / "audio_report.json").write_text(json.dumps(report, indent=2))
    return report


def _limit_curve(x: np.ndarray, ceiling_db: float) -> np.ndarray:
    """Look-ahead true-peak limiter gain (<= 1, smooth, never above what a peak needs)."""
    c = 10 ** (ceiling_db / 20)
    up = np.fft.irfft(np.fft.rfft(x, axis=0), n=x.shape[0] * 4, axis=0) * 4      # 4x oversampled
    pk = np.abs(up).max(axis=1).reshape(-1, 4).max(axis=1).astype(np.float32)
    need = np.minimum(1.0, c / np.maximum(pk, 1e-9)).astype(np.float32)
    hold = int(0.030 * SR) | 1
    low = cv2.erode(need.reshape(-1, 1), np.ones((hold, 1), np.uint8)).ravel()   # spread each dip +-15 ms
    smooth = cv2.blur(low.reshape(-1, 1), (1, int(0.012 * SR) | 1)).ravel()      # ramp inside that window
    return np.minimum(smooth, 1.0)


def cue_sheet_md() -> str:
    rows = ["| # | Time (s) | Cue | Level | What is moving on screen |", "|---|---|---|---|---|"]
    for i, (t, kind, lvl, pan, what) in enumerate(score.CUES, 1):
        rows.append(f"| {i} | {t:05.2f} | {kind.replace('_', ' ')} | {lvl} dB | {what} |")
    return "\n".join(rows)
