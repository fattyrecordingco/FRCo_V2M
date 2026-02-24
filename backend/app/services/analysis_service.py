"""Offline analysis algorithms for pitch, chords, and drums."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import librosa
import numpy as np
from scipy.signal import medfilt

from app.core.constants import DRUM_MIDI_MAP, NOTE_NAMES, SCALE_INTERVALS

MAJOR_PROFILE = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR_PROFILE = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

CHORD_TEMPLATES: dict[str, list[int]] = {
    "maj": [0, 4, 7],
    "min": [0, 3, 7],
    "dim": [0, 3, 6],
    "aug": [0, 4, 8],
    "sus2": [0, 2, 7],
    "sus4": [0, 5, 7],
    "maj7": [0, 4, 7, 11],
    "min7": [0, 3, 7, 10],
    "dom7": [0, 4, 7, 10],
}

DRUM_PROTOTYPES: dict[str, np.ndarray] = {
    "kick": np.array([0.68, 0.22, 0.10, 0.07, 0.18, 0.10, 0.08]),
    "snare": np.array([0.25, 0.52, 0.23, 0.28, 0.42, 0.35, 0.24]),
    "hihat_closed": np.array([0.08, 0.22, 0.70, 0.80, 0.78, 0.62, 0.45]),
    "hihat_open": np.array([0.10, 0.30, 0.60, 0.72, 0.73, 0.50, 0.40]),
    "tom_low": np.array([0.50, 0.38, 0.12, 0.20, 0.30, 0.24, 0.18]),
    "tom_mid": np.array([0.35, 0.50, 0.15, 0.24, 0.36, 0.28, 0.22]),
    "tom_high": np.array([0.26, 0.51, 0.23, 0.30, 0.45, 0.30, 0.26]),
    "crash": np.array([0.08, 0.25, 0.67, 0.90, 0.88, 0.70, 0.45]),
}


@dataclass(slots=True)
class AnalysisSummary:
    tempo_bpm: float
    time_signature: str
    root_note: str
    scale: str
    key_confidence: float
    mono_poly_label: str
    mono_poly_confidence: float


def enhance_for_analysis(audio: np.ndarray, sr: int) -> tuple[np.ndarray, dict[str, float]]:
    """Apply gentle denoise + gain normalization for more stable transcription."""
    if audio.size == 0:
        return audio, {"gain": 1.0, "noise_floor": 0.0, "peak": 0.0}

    working = np.nan_to_num(audio.astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0)
    working = working - float(np.mean(working))

    noise_floor = float(np.percentile(np.abs(working), 20))
    gate = max(noise_floor * 1.9, 1.5e-4)
    gated = np.sign(working) * np.maximum(np.abs(working) - gate, 0.0)

    stft = librosa.stft(gated, n_fft=1024, hop_length=256)
    mag, phase = np.abs(stft), np.exp(1j * np.angle(stft))
    noise_profile = np.percentile(mag, 18, axis=1, keepdims=True)
    mag_clean = np.maximum(mag - noise_profile * 0.72, 0.0)
    cleaned = librosa.istft(mag_clean * phase, hop_length=256, length=len(gated))
    working = (0.7 * cleaned + 0.3 * gated).astype(np.float32)

    rms = float(np.sqrt(np.mean(working * working)) + 1e-9)
    target_rms = 0.12
    gain = float(np.clip(target_rms / rms, 1.0, 6.0))
    working = working * gain

    peak = float(np.max(np.abs(working)) + 1e-9)
    if peak > 0.98:
        working = working * (0.96 / peak)
        peak = float(np.max(np.abs(working)) + 1e-9)

    return working.astype(np.float32), {"gain": gain, "noise_floor": noise_floor, "peak": peak}


def detect_tempo_and_time_signature(audio: np.ndarray, sr: int) -> tuple[float, str]:
    onset_env = librosa.onset.onset_strength(y=audio, sr=sr)
    tempo, beat_frames = librosa.beat.beat_track(y=audio, sr=sr, onset_envelope=onset_env, trim=False)
    tempo_value = float(np.atleast_1d(tempo)[0])
    tempo = float(tempo_value if np.isfinite(tempo_value) and tempo_value > 0 else 120.0)
    if len(beat_frames) < 6:
        return tempo, "4/4"

    beat_times = librosa.frames_to_time(beat_frames, sr=sr)
    beat_intervals = np.diff(beat_times)
    mean_interval = float(np.mean(beat_intervals)) if beat_intervals.size else 0.0
    if mean_interval <= 1e-9:
        return tempo, "4/4"
    regularity = float(np.std(beat_intervals) / mean_interval)
    if regularity > 0.6:
        return tempo, "4/4"

    beat_strength = np.interp(beat_times, librosa.times_like(onset_env, sr=sr), onset_env)
    scores: dict[int, float] = {}
    for numerator in (3, 4, 5):
        chunks = [
            beat_strength[idx : idx + numerator]
            for idx in range(0, len(beat_strength) - numerator + 1, numerator)
            if len(beat_strength[idx : idx + numerator]) == numerator
        ]
        if not chunks:
            scores[numerator] = 0.0
            continue
        downbeat_energy = np.array([float(chunk[0]) for chunk in chunks])
        intra_energy = np.array([float(np.mean(chunk[1:])) for chunk in chunks])
        scores[numerator] = float(np.mean(downbeat_energy) - np.mean(intra_energy))
    numerator = max(scores, key=scores.get)
    return tempo, f"{numerator}/4"


def detect_key_scale(audio: np.ndarray, sr: int) -> tuple[str, str, float]:
    chroma_cqt = librosa.feature.chroma_cqt(y=audio, sr=sr)
    chroma_cens = librosa.feature.chroma_cens(y=audio, sr=sr)
    chroma = 0.65 * chroma_cqt + 0.35 * chroma_cens
    if chroma.size == 0:
        return "C", "major", 0.0
    chroma_mean = chroma.mean(axis=1)
    chroma_mean = chroma_mean / (np.linalg.norm(chroma_mean) + 1e-9)

    best_label = ("C", "major", -1.0)
    runner_up = ("C", "minor", -1.0)
    for root_idx, root_name in enumerate(NOTE_NAMES):
        maj_profile = np.roll(MAJOR_PROFILE, root_idx)
        min_profile = np.roll(MINOR_PROFILE, root_idx)
        maj_score = float(np.dot(chroma_mean, maj_profile / np.linalg.norm(maj_profile)))
        min_score = float(np.dot(chroma_mean, min_profile / np.linalg.norm(min_profile)))
        for label in ((root_name, "major", maj_score), (root_name, "minor", min_score)):
            if label[2] > best_label[2]:
                runner_up = best_label
                best_label = label
            elif label[2] > runner_up[2]:
                runner_up = label
    score_gap = max(0.0, best_label[2] - runner_up[2])
    confidence = float(np.clip((best_label[2] + 1.0) * 0.35 + score_gap * 0.9, 0.0, 1.0))
    return best_label[0], best_label[1], confidence


def detect_mono_poly(audio: np.ndarray, sr: int) -> tuple[str, float]:
    stft = np.abs(librosa.stft(audio, n_fft=2048, hop_length=512))
    if stft.size == 0:
        return "mono", 0.0
    threshold = np.median(stft) * 2.4
    spectral_polyphony = float(np.mean((stft > threshold).sum(axis=0) >= 7))

    chroma = librosa.feature.chroma_cens(y=audio, sr=sr, hop_length=512)
    chroma_activity = float(np.mean((chroma > 0.32).sum(axis=0))) if chroma.size else 1.0

    harmonic, percussive = librosa.effects.hpss(audio)
    harmonic_ratio = float(np.mean(np.abs(harmonic)) / (np.mean(np.abs(percussive)) + 1e-9))
    poly_score = 0.62 * spectral_polyphony + 0.25 * (chroma_activity / 6.0) + 0.13 * min(harmonic_ratio / 2.0, 1.0)

    label = "poly" if poly_score >= 0.42 else "mono"
    confidence = float(np.clip(abs(poly_score - 0.42) * 2.2 + 0.45, 0.0, 1.0))
    return label, confidence


def summarize_analysis(audio: np.ndarray, sr: int) -> AnalysisSummary:
    tempo, signature = detect_tempo_and_time_signature(audio, sr)
    root, scale, key_conf = detect_key_scale(audio, sr)
    mono_poly, mono_poly_conf = detect_mono_poly(audio, sr)
    return AnalysisSummary(
        tempo_bpm=tempo,
        time_signature=signature,
        root_note=root,
        scale=scale,
        key_confidence=key_conf,
        mono_poly_label=mono_poly,
        mono_poly_confidence=mono_poly_conf,
    )


def extract_monophonic_notes(audio: np.ndarray, sr: int, hop_length: int = 256) -> list[dict[str, Any]]:
    if audio.size == 0:
        return []

    f0, voiced, voiced_probs = _estimate_pitch(audio, sr, hop_length)
    times = librosa.times_like(f0, sr=sr, hop_length=hop_length)
    midi_values = np.where(np.isfinite(f0), librosa.hz_to_midi(f0), np.nan)
    valid_idx = np.where(np.isfinite(midi_values))[0]
    if valid_idx.size:
        midi_values[valid_idx] = medfilt(midi_values[valid_idx], kernel_size=5)

    rms = librosa.feature.rms(y=audio, frame_length=2048, hop_length=hop_length).flatten()
    onset_strength = librosa.onset.onset_strength(y=audio, sr=sr, hop_length=hop_length)
    if rms.size < times.size:
        rms = np.pad(rms, (0, times.size - rms.size), mode="edge")
    if onset_strength.size < times.size:
        onset_strength = np.pad(onset_strength, (0, times.size - onset_strength.size), mode="edge")

    onset_frames = librosa.onset.onset_detect(
        y=audio,
        sr=sr,
        hop_length=hop_length,
        units="frames",
        backtrack=True,
    )
    pitch_jump_frames = np.where(np.abs(np.diff(np.nan_to_num(midi_values, nan=0.0))) >= 1.7)[0] + 1
    boundaries = np.unique(np.concatenate(([0], onset_frames, pitch_jump_frames, [len(times) - 1]))).astype(int)
    boundaries = boundaries[(boundaries >= 0) & (boundaries < len(times))]
    if boundaries.size < 2:
        boundaries = np.array([0, len(times) - 1], dtype=int)

    notes: list[dict[str, Any]] = []
    for idx in range(len(boundaries) - 1):
        start_idx = int(boundaries[idx])
        end_idx = int(boundaries[idx + 1])
        if end_idx <= start_idx:
            continue
        seg_voiced_ratio = float(np.mean(voiced[start_idx:end_idx]))
        if seg_voiced_ratio < 0.42:
            continue
        segment = midi_values[start_idx:end_idx]
        valid = segment[np.isfinite(segment)]
        if valid.size == 0:
            continue
        notes.extend(_flush_note(start_idx, end_idx, int(round(np.median(valid))), times, rms, onset_strength))

    if not notes:
        return []
    return notes


def _estimate_pitch(audio: np.ndarray, sr: int, hop_length: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    try:
        f0, voiced_flag, voiced_prob = librosa.pyin(
            audio,
            fmin=librosa.note_to_hz("C2"),
            fmax=librosa.note_to_hz("C7"),
            sr=sr,
            hop_length=hop_length,
            frame_length=2048,
        )
        f0 = np.asarray(f0, dtype=float)
        voiced_flag = np.asarray(voiced_flag, dtype=bool)
        voiced_prob = np.asarray(voiced_prob, dtype=float)
        voiced = voiced_flag & (voiced_prob > 0.56)
        f0 = np.where(voiced, f0, np.nan)
        return f0, voiced, voiced_prob
    except Exception:
        f0 = librosa.yin(
            audio,
            fmin=librosa.note_to_hz("C2"),
            fmax=librosa.note_to_hz("C7"),
            sr=sr,
            hop_length=hop_length,
            trough_threshold=0.1,
        )
        voiced = np.isfinite(f0)
        probs = np.where(voiced, 0.75, 0.0)
        return f0, voiced, probs


def _flush_note(
    start_idx: int,
    end_idx: int,
    midi_pitch: int,
    times: np.ndarray,
    rms: np.ndarray,
    onset_strength: np.ndarray,
) -> list[dict[str, Any]]:
    if end_idx <= start_idx:
        return []
    start = float(times[start_idx])
    end = float(times[end_idx])
    if end - start < 0.05:
        return []

    base_vel = float(np.mean(rms[start_idx:end_idx]) * 230.0)
    attack_boost = float(np.max(onset_strength[start_idx:end_idx]) * 8.0)
    velocity = int(np.clip(base_vel + attack_boost + 20, 30, 122))
    return [
        {
            "pitch": int(np.clip(midi_pitch, 24, 108)),
            "start": start,
            "end": end,
            "velocity": velocity,
            "track": "notes",
        }
    ]


def detect_chords(audio: np.ndarray, sr: int) -> list[dict[str, Any]]:
    tempo, beat_frames = librosa.beat.beat_track(y=audio, sr=sr, trim=False)
    tempo_value = float(np.atleast_1d(tempo)[0])
    tempo = float(tempo_value if np.isfinite(tempo_value) and tempo_value > 0 else 120.0)
    if len(beat_frames) < 4:
        hop = int(0.45 * sr)
        beat_frames = np.arange(0, len(audio), hop, dtype=int)
        beat_times = beat_frames / sr
    else:
        beat_times = librosa.frames_to_time(beat_frames, sr=sr)

    hop_length = 512
    chroma_cqt = librosa.feature.chroma_cqt(y=audio, sr=sr, hop_length=hop_length)
    chroma_cens = librosa.feature.chroma_cens(y=audio, sr=sr, hop_length=hop_length)
    chroma = 0.65 * chroma_cqt + 0.35 * chroma_cens
    chroma = chroma / (np.linalg.norm(chroma, axis=0, keepdims=True) + 1e-9)
    if chroma.shape[1] >= 5:
        chroma = medfilt(chroma, kernel_size=(1, 5))
    chroma_times = librosa.frames_to_time(np.arange(chroma.shape[1]), sr=sr, hop_length=hop_length)

    segment_edges = beat_times[::2] if len(beat_times) > 6 else beat_times
    if segment_edges.size < 2:
        segment_edges = np.array([0.0, max(len(audio) / sr, 0.5)])
    if segment_edges[-1] < len(audio) / sr:
        segment_edges = np.append(segment_edges, len(audio) / sr)

    raw_chords: list[dict[str, Any]] = []
    for idx in range(len(segment_edges) - 1):
        start = float(segment_edges[idx])
        end = float(segment_edges[idx + 1])
        if end - start < 0.15:
            continue
        mask = (chroma_times >= start) & (chroma_times < end)
        if not np.any(mask):
            continue
        seg = chroma[:, mask].mean(axis=1)
        root_idx, quality, score = _classify_chord(seg)
        if score < 0.22:
            continue
        root_name = NOTE_NAMES[root_idx]
        pitches = [60 + ((root_idx + interval) % 12) for interval in CHORD_TEMPLATES[quality][:4]]
        raw_chords.append(
            {
                "start": start,
                "end": end,
                "root": root_name,
                "quality": quality,
                "label": f"{root_name}{quality}",
                "pitches": pitches,
                "confidence": float(np.clip(score * 1.7, 0.1, 1.0)),
                "velocity": 84,
                "track": "chords",
            }
        )
    chords = _merge_chord_segments(raw_chords)
    if chords:
        return chords

    beat_len = 60.0 / tempo if tempo > 0 else 0.5
    return [
        {
            "start": 0.0,
            "end": beat_len,
            "root": "C",
            "quality": "maj",
            "label": "Cmaj",
            "pitches": [60, 64, 67],
            "confidence": 0.2,
            "velocity": 80,
            "track": "chords",
        }
    ]


def _classify_chord(chroma: np.ndarray) -> tuple[int, str, float]:
    chroma = chroma / (np.linalg.norm(chroma) + 1e-9)
    best = (0, "maj", -1.0)
    for root_idx in range(12):
        for quality, intervals in CHORD_TEMPLATES.items():
            template = np.zeros(12)
            for interval in intervals:
                template[(root_idx + interval) % 12] = 1.0
            template = template / (np.linalg.norm(template) + 1e-9)
            score = float(np.dot(chroma, template))
            if quality in {"maj", "min"}:
                score += 0.03
            if score > best[2]:
                best = (root_idx, quality, score)
    return best


def _merge_chord_segments(chords: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not chords:
        return []
    merged = [dict(chords[0])]
    for chord in chords[1:]:
        prev = merged[-1]
        if chord["label"] == prev["label"] and chord["start"] - prev["end"] <= 0.08:
            prev["end"] = chord["end"]
            prev["confidence"] = float((prev["confidence"] + chord["confidence"]) / 2.0)
            continue
        if chord["end"] - chord["start"] < 0.2:
            continue
        merged.append(dict(chord))
    return merged


def transcribe_drums(audio: np.ndarray, sr: int) -> list[dict[str, Any]]:
    _, percussive = librosa.effects.hpss(audio, margin=(1.0, 6.0))
    onset_main_times = librosa.onset.onset_detect(
        y=percussive,
        sr=sr,
        units="time",
        pre_max=20,
        post_max=20,
        pre_avg=10,
        post_avg=10,
        delta=0.12,
        wait=1,
    )
    low_onsets = _detect_band_onsets(audio, sr, (20, 220), threshold_q=72)
    high_onsets = _detect_band_onsets(audio, sr, (2000, 9000), threshold_q=75)
    low_times = librosa.frames_to_time(low_onsets, sr=sr, hop_length=256)
    high_times = librosa.frames_to_time(high_onsets, sr=sr, hop_length=256)
    onset_times = np.sort(np.concatenate([onset_main_times, low_times, high_times]))
    if onset_times.size:
        deduped = [float(onset_times[0])]
        for onset in onset_times[1:]:
            if float(onset - deduped[-1]) > 0.04:
                deduped.append(float(onset))
        onset_times = np.array(deduped)

    events: list[dict[str, Any]] = []
    win = int(sr * 0.10)
    for onset_time in onset_times:
        start = int(max(0, onset_time * sr))
        stop = min(len(audio), start + win)
        clip = audio[start:stop]
        if clip.size < 32:
            continue
        features = _extract_drum_features(clip, sr)
        label, confidence = _classify_drum(features)
        midi_pitch = DRUM_MIDI_MAP.get(label, DRUM_MIDI_MAP["snare"])
        duration = 0.14 if "hihat_open" in label or label == "crash" else 0.11
        velocity = int(np.clip(38 + features["rms"] * 900 + confidence * 18, 45, 124))
        events.append(
            {
                "pitch": midi_pitch,
                "start": float(onset_time),
                "end": float(onset_time + duration),
                "velocity": velocity,
                "class": label,
                "confidence": float(confidence),
                "track": "drums",
            }
        )
    return events


def _extract_drum_features(clip: np.ndarray, sr: int) -> dict[str, float]:
    windowed = clip * np.hanning(len(clip))
    spectrum = np.abs(np.fft.rfft(windowed))
    freqs = np.fft.rfftfreq(len(windowed), d=1.0 / sr)
    low = float(np.sum(spectrum[(freqs >= 20) & (freqs < 180)]))
    mid = float(np.sum(spectrum[(freqs >= 180) & (freqs < 2000)]))
    high = float(np.sum(spectrum[(freqs >= 2000) & (freqs < 10000)]))
    total = low + mid + high + 1e-9

    centroid = float(np.sum(freqs * spectrum) / (np.sum(spectrum) + 1e-9))
    rolloff = float(librosa.feature.spectral_rolloff(y=clip, sr=sr).mean())
    flatness = float(librosa.feature.spectral_flatness(y=clip).mean())
    zcr = float(librosa.feature.zero_crossing_rate(clip, frame_length=min(2048, len(clip))).mean())
    rms = float(np.sqrt(np.mean(clip * clip)) + 1e-9)
    return {
        "low_n": low / total,
        "mid_n": mid / total,
        "high_n": high / total,
        "centroid_n": min(centroid / 9000.0, 1.0),
        "rolloff_n": min(rolloff / 10000.0, 1.0),
        "flatness": flatness,
        "zcr": zcr,
        "rms": rms,
    }


def _classify_drum(features: dict[str, float]) -> tuple[str, float]:
    vec = np.array(
        [
            features["low_n"],
            features["mid_n"],
            features["high_n"],
            features["centroid_n"],
            features["rolloff_n"],
            features["flatness"],
            min(features["zcr"], 1.0),
        ]
    )
    vec_norm = vec / (np.linalg.norm(vec) + 1e-9)
    best_label = "snare"
    best_score = -1.0
    for label, proto in DRUM_PROTOTYPES.items():
        proto_norm = proto / (np.linalg.norm(proto) + 1e-9)
        score = float(np.dot(vec_norm, proto_norm))
        if score > best_score:
            best_score = score
            best_label = label

    if (
        features["low_n"] > 0.42
        and features["centroid_n"] < 0.25
        and features["low_n"] > features["mid_n"]
    ):
        best_label = "kick"
        best_score = max(best_score, 0.82)
    elif features["high_n"] > 0.62 and features["flatness"] > 0.35:
        best_label = "hihat_closed"
        best_score = max(best_score, 0.78)
    elif features["high_n"] > 0.58 and features["rolloff_n"] > 0.72:
        best_label = "crash"
        best_score = max(best_score, 0.75)
    elif features["mid_n"] > 0.5 and features["low_n"] > 0.2 and features["centroid_n"] < 0.35:
        best_label = "snare"
        best_score = max(best_score, 0.73)

    confidence = float(np.clip((best_score + 1.0) / 2.0, 0.35, 0.98))
    return best_label, confidence


def _detect_band_onsets(audio: np.ndarray, sr: int, band: tuple[int, int], threshold_q: int) -> np.ndarray:
    hop_length = 256
    spectrum = np.abs(librosa.stft(audio, n_fft=1024, hop_length=hop_length))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=1024)
    mask = (freqs >= band[0]) & (freqs < band[1])
    if not np.any(mask):
        return np.array([], dtype=int)
    band_energy = np.sum(spectrum[mask, :], axis=0)
    flux = np.maximum(0.0, np.diff(band_energy, prepend=band_energy[0]))
    if flux.size < 3:
        return np.array([], dtype=int)
    delta = max(1e-6, float(np.percentile(flux, threshold_q) * 0.32))
    peaks = librosa.util.peak_pick(
        flux,
        pre_max=3,
        post_max=3,
        pre_avg=3,
        post_avg=4,
        delta=delta,
        wait=4,
    )
    return peaks.astype(int)


def _detect_low_band_onsets(audio: np.ndarray, sr: int) -> np.ndarray:
    return _detect_band_onsets(audio, sr, (20, 220), threshold_q=70)


def split_stems(audio: np.ndarray) -> dict[str, np.ndarray]:
    harmonic, percussive = librosa.effects.hpss(audio, margin=(1.2, 5.5))
    return {"harmonic": harmonic.astype(np.float32), "percussive": percussive.astype(np.float32)}


def quantize_events(events: list[dict[str, Any]], bpm: float, grid_division: int = 4) -> list[dict[str, Any]]:
    if bpm <= 0:
        return events
    step = (60.0 / bpm) / grid_division
    quantized: list[dict[str, Any]] = []
    for event in events:
        cur = dict(event)
        start = round(float(event["start"]) / step) * step
        end = round(float(event["end"]) / step) * step
        if end <= start:
            end = start + step
        cur["start"] = float(max(0.0, start))
        cur["end"] = float(end)
        quantized.append(cur)
    return quantized


def smooth_note_events(
    events: list[dict[str, Any]],
    min_duration: float = 0.08,
    merge_gap: float = 0.06,
) -> list[dict[str, Any]]:
    if not events:
        return []

    ordered = sorted(events, key=lambda evt: (float(evt["start"]), float(evt["end"])))
    filtered = [
        dict(evt)
        for evt in ordered
        if float(evt["end"]) - float(evt["start"]) >= min_duration and int(evt.get("velocity", 80)) >= 34
    ]
    if not filtered:
        return []

    merged: list[dict[str, Any]] = [filtered[0]]
    for evt in filtered[1:]:
        prev = merged[-1]
        gap = float(evt["start"]) - float(prev["end"])
        same_pitch = int(evt.get("pitch", -1)) == int(prev.get("pitch", -2))
        if same_pitch and gap <= merge_gap:
            prev["end"] = max(float(prev["end"]), float(evt["end"]))
            prev["velocity"] = int(np.clip((int(prev["velocity"]) + int(evt["velocity"])) / 2, 1, 127))
            continue
        merged.append(evt)

    smoothed: list[dict[str, Any]] = []
    for idx, evt in enumerate(merged):
        duration = float(evt["end"]) - float(evt["start"])
        if idx == 0 or idx == len(merged) - 1:
            smoothed.append(evt)
            continue
        prev_pitch = int(merged[idx - 1]["pitch"])
        next_pitch = int(merged[idx + 1]["pitch"])
        cur_pitch = int(evt["pitch"])
        # Remove likely transient glitches: very short jumps that do not match neighboring contour.
        if duration < (min_duration * 1.4):
            if (
                abs(cur_pitch - prev_pitch) >= 9
                and abs(cur_pitch - next_pitch) >= 9
                and abs(prev_pitch - next_pitch) <= 2
            ):
                continue
        smoothed.append(evt)

    return smoothed if smoothed else merged


def smooth_drum_events(events: list[dict[str, Any]], min_gap: float = 0.045) -> list[dict[str, Any]]:
    if not events:
        return []

    ordered = sorted(events, key=lambda evt: (float(evt["start"]), int(evt.get("pitch", 0))))
    by_pitch: dict[int, list[dict[str, Any]]] = {}
    for evt in ordered:
        pitch = int(evt.get("pitch", 0))
        bucket = by_pitch.setdefault(pitch, [])
        current = dict(evt)
        if not bucket:
            bucket.append(current)
            continue
        prev = bucket[-1]
        if float(current["start"]) - float(prev["start"]) <= min_gap:
            prev_score = int(prev.get("velocity", 64)) + float(prev.get("confidence", 0.5)) * 30.0
            cur_score = int(current.get("velocity", 64)) + float(current.get("confidence", 0.5)) * 30.0
            if cur_score > prev_score:
                prev["start"] = float(current["start"])
                prev["end"] = float(current["end"])
                prev["velocity"] = int(current["velocity"])
                prev["class"] = current.get("class", prev.get("class"))
                prev["confidence"] = float(current.get("confidence", prev.get("confidence", 0.5)))
            else:
                prev["end"] = max(float(prev["end"]), float(current["end"]))
            continue
        bucket.append(current)

    compact: list[dict[str, Any]] = []
    for bucket in by_pitch.values():
        compact.extend(bucket)
    compact.sort(key=lambda evt: float(evt["start"]))
    return compact


def constrain_to_scale(
    events: list[dict[str, Any]],
    root_note: str,
    scale: str,
    custom_scale_notes: list[str] | None = None,
) -> list[dict[str, Any]]:
    if not events:
        return events
    root_idx = NOTE_NAMES.index(root_note) if root_note in NOTE_NAMES else 0
    if scale == "custom":
        custom_scale_notes = custom_scale_notes or []
        allowed_pcs = {NOTE_NAMES.index(name) for name in custom_scale_notes if name in NOTE_NAMES}
        if not allowed_pcs:
            return events
    else:
        intervals = SCALE_INTERVALS.get(scale, SCALE_INTERVALS["chromatic"])
        allowed_pcs = {(root_idx + interval) % 12 for interval in intervals}

    constrained: list[dict[str, Any]] = []
    for event in events:
        cur = dict(event)
        if "pitch" in cur:
            cur["pitch"] = _nearest_pitch_in_scale(int(cur["pitch"]), allowed_pcs)
        if "pitches" in cur:
            cur["pitches"] = [_nearest_pitch_in_scale(int(p), allowed_pcs) for p in cur["pitches"]]
        constrained.append(cur)
    return constrained


def _nearest_pitch_in_scale(pitch: int, allowed_pcs: set[int]) -> int:
    if pitch % 12 in allowed_pcs:
        return pitch
    for distance in range(1, 12):
        up = pitch + distance
        down = pitch - distance
        if up % 12 in allowed_pcs:
            return up
        if down % 12 in allowed_pcs:
            return down
    return pitch


def retune_audio(
    audio: np.ndarray,
    sr: int,
    detected_bpm: float,
    target_bpm: float | None,
    detected_root: str,
    target_root: str,
) -> np.ndarray:
    retuned = audio
    if target_bpm and target_bpm > 0 and detected_bpm > 0:
        rate = float(target_bpm / detected_bpm)
        rate = float(np.clip(rate, 0.5, 2.0))
        retuned = librosa.effects.time_stretch(retuned, rate=rate)
    if target_root in NOTE_NAMES and detected_root in NOTE_NAMES:
        shift = NOTE_NAMES.index(target_root) - NOTE_NAMES.index(detected_root)
        if shift != 0:
            retuned = librosa.effects.pitch_shift(retuned, sr=sr, n_steps=float(shift))
    return retuned
