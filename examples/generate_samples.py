from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent
SR = 44100


def write(name: str, data: np.ndarray) -> None:
    sf.write(ROOT / name, data.astype(np.float32), SR, subtype="PCM_16")


def demo_mono() -> np.ndarray:
    notes = [261.63, 293.66, 329.63, 392.0, 440.0, 392.0, 329.63, 293.66]
    chunk = int(SR * 0.22)
    out = np.zeros(chunk * len(notes), dtype=np.float32)
    for idx, freq in enumerate(notes):
        t = np.linspace(0, 0.22, chunk, endpoint=False)
        env = np.linspace(1.0, 0.3, chunk)
        out[idx * chunk : (idx + 1) * chunk] = 0.28 * np.sin(2 * np.pi * freq * t) * env
    return out


def demo_poly() -> np.ndarray:
    progression = [
        [261.63, 329.63, 392.0],
        [220.0, 277.18, 329.63],
        [196.0, 246.94, 392.0],
        [233.08, 293.66, 349.23],
    ]
    beat_len = int(SR * 0.6)
    out = np.zeros(beat_len * len(progression), dtype=np.float32)
    t = np.linspace(0, 0.6, beat_len, endpoint=False)
    env = np.linspace(1.0, 0.45, beat_len)
    for idx, chord in enumerate(progression):
        signal = sum(np.sin(2 * np.pi * freq * t) for freq in chord) / len(chord)
        out[idx * beat_len : (idx + 1) * beat_len] = 0.26 * signal * env
    return out


def demo_drums() -> np.ndarray:
    out = np.zeros(int(SR * 3.0), dtype=np.float32)
    kick_times = [0.0, 0.75, 1.5, 2.25]
    snare_times = [0.38, 1.12, 1.88, 2.62]
    hat_times = np.arange(0.0, 3.0, 0.25)

    for hit in kick_times:
        start = int(hit * SR)
        size = int(0.09 * SR)
        t = np.linspace(0, 0.09, size, endpoint=False)
        wave = np.sin(2 * np.pi * 60 * t) * np.exp(-28 * t)
        out[start : start + size] += 0.95 * wave

    rng = np.random.default_rng(14)
    for hit in snare_times:
        start = int(hit * SR)
        size = int(0.08 * SR)
        noise = rng.normal(0, 1, size) * np.hanning(size)
        out[start : start + size] += 0.42 * noise

    for hit in hat_times:
        start = int(hit * SR)
        size = int(0.03 * SR)
        noise = rng.normal(0, 1, size) * np.hanning(size)
        out[start : start + size] += 0.2 * noise
    return np.clip(out, -1.0, 1.0)


if __name__ == "__main__":
    write("demo_mono.wav", demo_mono())
    write("demo_poly.wav", demo_poly())
    write("demo_drums.wav", demo_drums())

