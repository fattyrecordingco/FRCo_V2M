"""Audio loading and saving helpers."""

from __future__ import annotations

import os
import tempfile
from io import BytesIO
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf

from app.core.constants import SUPPORTED_AUDIO_EXTENSIONS


def validate_extension(filename: str) -> None:
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_AUDIO_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_AUDIO_EXTENSIONS))
        msg = f"Unsupported audio file type: {suffix}. Supported: {supported}"
        raise ValueError(msg)


def load_audio_from_bytes(raw_bytes: bytes, sample_rate: int) -> tuple[np.ndarray, int]:
    try:
        with sf.SoundFile(BytesIO(raw_bytes)) as sf_desc:
            data = sf_desc.read(always_2d=False)
            src_sr = sf_desc.samplerate
    except Exception:
        fd, tmp_path = tempfile.mkstemp(suffix=".wav")
        try:
            with os.fdopen(fd, "wb") as tmp_file:
                tmp_file.write(raw_bytes)
            try:
                data, src_sr = librosa.load(tmp_path, sr=None, mono=False)
            except Exception as exc:
                msg = (
                    "Unable to decode audio input. Please upload WAV/MP3/FLAC, "
                    "or re-record using browser recording in this app."
                )
                raise ValueError(msg) from exc
        finally:
            Path(tmp_path).unlink(missing_ok=True)
    if data.ndim > 1:
        data = np.mean(data, axis=1)
    data = data.astype(np.float32)
    if src_sr != sample_rate:
        data = librosa.resample(y=data, orig_sr=src_sr, target_sr=sample_rate)
        src_sr = sample_rate
    if data.size == 0:
        raise ValueError("Audio file is empty.")
    return data, src_sr


def save_wav(path: Path, audio: np.ndarray, sample_rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, audio, sample_rate, subtype="PCM_16")


def is_silent(audio: np.ndarray, threshold: float = 1e-4) -> bool:
    return float(np.max(np.abs(audio))) < threshold
