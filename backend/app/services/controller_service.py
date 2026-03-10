"""Voice-controller feature extraction and MIDI mapping."""

from __future__ import annotations

from typing import Any

import librosa
import numpy as np

from app.services.analysis_service import _estimate_pitch, enhance_for_analysis


def analyze_controller_input(
    audio: np.ndarray,
    sr: int,
    workflow_mode: str = "live",
    hop_length: int = 256,
    already_enhanced: bool = False,
    enhancement_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if already_enhanced:
        analysis_audio = np.asarray(audio, dtype=np.float32)
        enhancement = enhancement_meta or {}
    else:
        analysis_audio, enhancement = enhance_for_analysis(audio, sr)
    target_sr = 16000 if workflow_mode == "live" else 22050
    if sr > target_sr:
        working = librosa.resample(analysis_audio, orig_sr=sr, target_sr=target_sr)
        working_sr = target_sr
    else:
        working = analysis_audio
        working_sr = sr

    f0, voiced, voiced_probs = _estimate_pitch(working, working_sr, hop_length)
    times = librosa.times_like(f0, sr=working_sr, hop_length=hop_length)
    rms = librosa.feature.rms(y=working, frame_length=2048, hop_length=hop_length).flatten()
    centroid = librosa.feature.spectral_centroid(y=working, sr=working_sr, hop_length=hop_length).flatten()
    onset_strength = librosa.onset.onset_strength(y=working, sr=working_sr, hop_length=hop_length)
    if rms.size < times.size:
        rms = np.pad(rms, (0, times.size - rms.size), mode="edge")
    if centroid.size < times.size:
        centroid = np.pad(centroid, (0, times.size - centroid.size), mode="edge")
    if onset_strength.size < times.size:
        onset_strength = np.pad(onset_strength, (0, times.size - onset_strength.size), mode="edge")

    loudness = _normalize_and_smooth(rms)
    brightness = _normalize_and_smooth(centroid / max(working_sr / 2.0, 1.0))
    pitch_midi = np.where(np.isfinite(f0), librosa.hz_to_midi(f0), np.nan)
    vibrato = _estimate_vibrato(pitch_midi)

    frames: list[dict[str, Any]] = []
    control_changes: list[dict[str, Any]] = []
    pitch_bends: list[dict[str, Any]] = []
    note_windows: list[dict[str, Any]] = []
    voiced_state = False
    gate_open_time = 0.0

    for idx, frame_time in enumerate(times):
        voiced_score = float(voiced_probs[idx]) if idx < voiced_probs.size else 0.0
        active = _hysteresis_active(voiced_state, voiced_score, float(loudness[idx]))
        midi_value = float(pitch_midi[idx]) if idx < pitch_midi.size and np.isfinite(pitch_midi[idx]) else None
        cutoff = int(np.clip(round(loudness[idx] * 95.0 + 20.0), 0, 127))
        tone = int(np.clip(round(brightness[idx] * 127.0), 0, 127))
        mod = int(np.clip(round(vibrato[idx] * 127.0), 0, 127))

        frames.append(
            {
                "time": round(float(frame_time), 4),
                "voiced": active,
                "voiced_score": round(voiced_score, 4),
                "pitch_hz": round(float(f0[idx]), 3) if idx < f0.size and np.isfinite(f0[idx]) else None,
                "pitch_midi": round(midi_value, 3) if midi_value is not None else None,
                "loudness": round(float(loudness[idx]), 4),
                "brightness": round(float(brightness[idx]), 4),
                "vibrato": round(float(vibrato[idx]), 4),
                "onset": round(float(onset_strength[idx]), 4),
            }
        )

        control_changes.extend(
            [
                {"time": round(float(frame_time), 4), "number": 11, "value": cutoff},
                {"time": round(float(frame_time), 4), "number": 74, "value": tone},
                {"time": round(float(frame_time), 4), "number": 1, "value": mod},
            ]
        )

        if midi_value is not None:
            base_pitch = int(round(midi_value))
            bend = int(np.clip(round(((midi_value - base_pitch) / 2.0) * 8192.0), -8192, 8191))
            pitch_bends.append({"time": round(float(frame_time), 4), "value": bend})

        if active and not voiced_state:
            voiced_state = True
            gate_open_time = float(frame_time)
        elif voiced_state and not active:
            note_windows.append(
                {
                    "pitch": 60,
                    "start": round(gate_open_time, 4),
                    "end": round(float(frame_time), 4),
                    "velocity": int(np.clip(round(np.max(loudness) * 110.0), 50, 118)),
                }
            )
            voiced_state = False

    if voiced_state:
        note_windows.append(
            {
                "pitch": 60,
                "start": round(gate_open_time, 4),
                "end": round(float(times[-1]) if times.size else 0.0, 4),
                "velocity": int(np.clip(round(np.max(loudness) * 110.0), 50, 118)),
            }
        )

    return {
        "frames": frames,
        "events": {
            "notes": [note for note in note_windows if note["end"] > note["start"]],
            "cc": _dedupe_control_changes(control_changes),
            "pitch_bends": _dedupe_pitch_bends(pitch_bends),
        },
        "summary": {
            "frame_count": len(frames),
            "active_ratio": round(float(np.mean([frame["voiced"] for frame in frames])), 4) if frames else 0.0,
            "loudness_mean": round(float(np.mean(loudness)), 4) if loudness.size else 0.0,
            "brightness_mean": round(float(np.mean(brightness)), 4) if brightness.size else 0.0,
            "vibrato_mean": round(float(np.mean(vibrato)), 4) if vibrato.size else 0.0,
            "enhancement": enhancement,
        },
    }


def _normalize_and_smooth(values: np.ndarray) -> np.ndarray:
    if values.size == 0:
        return values
    lo = float(np.percentile(values, 5))
    hi = float(np.percentile(values, 95))
    spread = max(hi - lo, 1e-6)
    normalized = np.clip((values - lo) / spread, 0.0, 1.0)
    smoothed = np.array(normalized, copy=True)
    for idx in range(1, smoothed.size):
        smoothed[idx] = 0.72 * smoothed[idx - 1] + 0.28 * smoothed[idx]
    return smoothed


def _estimate_vibrato(pitch_midi: np.ndarray) -> np.ndarray:
    if pitch_midi.size == 0:
        return pitch_midi
    filled = np.where(np.isfinite(pitch_midi), pitch_midi, np.nan)
    median = np.nanmedian(filled)
    baseline = np.where(np.isfinite(filled), filled, median)
    smoothed = np.convolve(baseline, np.ones(7) / 7.0, mode="same")
    deviation = np.abs(baseline - smoothed)
    return np.clip(deviation / 0.35, 0.0, 1.0)


def _hysteresis_active(previous: bool, voiced_score: float, loudness: float) -> bool:
    open_threshold = 0.44
    close_threshold = 0.28
    if previous:
        return voiced_score >= close_threshold and loudness >= 0.05
    return voiced_score >= open_threshold and loudness >= 0.08


def _dedupe_control_changes(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not events:
        return []
    deduped: list[dict[str, Any]] = []
    last_by_cc: dict[int, int] = {}
    for event in events:
        cc_num = int(event["number"])
        value = int(event["value"])
        last_value = last_by_cc.get(cc_num)
        if last_value is not None and abs(last_value - value) < 2:
            continue
        last_by_cc[cc_num] = value
        deduped.append(event)
    return deduped


def _dedupe_pitch_bends(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not events:
        return []
    deduped = [events[0]]
    for event in events[1:]:
        if abs(int(event["value"]) - int(deduped[-1]["value"])) < 128:
            continue
        deduped.append(event)
    return deduped
