"""Offline analysis algorithms for pitch, chords, and drums."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import librosa
import numpy as np
from scipy.signal import butter, find_peaks, medfilt, sosfiltfilt

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

MIN_VOICE_HZ = float(librosa.note_to_hz("A0"))
MAX_VOICE_HZ = float(librosa.note_to_hz("C8"))
MIN_MIDI_NOTE = 21
MAX_MIDI_NOTE = 120
MAX_HARMONIC_ORDER = 6
ANALYSIS_CLIP_THRESHOLD = 0.985
ANALYSIS_LEVEL_TARGET_RMS = 0.145
ANALYSIS_LEVEL_TARGET_RMS_LOW = 0.165
ANALYSIS_LEVEL_MIN_ACTIVE_RMS = 0.085
ANALYSIS_LEVEL_MAX_ACTIVE_RMS = 0.22
ANALYSIS_OUTPUT_CEILING = 0.96


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
    """Apply denoise, input leveling, and clipping control for stable transcription."""
    if audio.size == 0:
        return audio, {"gain": 1.0, "noise_floor": 0.0, "peak": 0.0, "snr_db": 0.0}

    working = np.nan_to_num(audio.astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0)
    working = working - float(np.mean(working))

    input_metrics = _measure_level_metrics(working)
    repaired_segments = 0.0
    if input_metrics["clip_ratio"] > 5e-4 or input_metrics["peak"] >= ANALYSIS_CLIP_THRESHOLD:
        working, repaired_segments = _repair_clipped_regions(working)
    working, pre_level = _apply_global_leveling(working)

    if sr > 8000:
        low_hz = max(30.0, MIN_VOICE_HZ * 0.55)
        high_hz = min(float(sr) * 0.48, 5200.0)
        if low_hz < high_hz:
            sos = butter(2, [low_hz, high_hz], btype="bandpass", fs=sr, output="sos")
            working = sosfiltfilt(sos, working).astype(np.float32)

    noise_floor = float(np.percentile(np.abs(working), 20))
    gate = max(noise_floor * 1.5, 1.2e-4)
    gated = np.sign(working) * np.maximum(np.abs(working) - gate, 0.0)

    n_fft = 2048 if len(gated) >= 4096 else 1024
    stft = librosa.stft(gated, n_fft=n_fft, hop_length=256)
    mag, phase = np.abs(stft), np.exp(1j * np.angle(stft))
    frame_rms = librosa.feature.rms(y=gated, frame_length=n_fft, hop_length=256).flatten()
    if frame_rms.size and frame_rms.size == mag.shape[1]:
        quiet_mask = frame_rms <= float(np.percentile(frame_rms, 35))
        if np.any(quiet_mask):
            noise_profile = np.percentile(mag[:, quiet_mask], 65, axis=1, keepdims=True)
        else:
            noise_profile = np.percentile(mag, 18, axis=1, keepdims=True)
    else:
        noise_profile = np.percentile(mag, 18, axis=1, keepdims=True)
    mag_floor = mag * 0.05
    mag_clean = np.maximum(mag - noise_profile * 0.82, mag_floor)
    cleaned = librosa.istft(mag_clean * phase, hop_length=256, length=len(gated)).astype(np.float32)
    working = (0.76 * cleaned + 0.24 * gated).astype(np.float32)

    target_rms = ANALYSIS_LEVEL_TARGET_RMS_LOW if input_metrics["active_rms"] < 0.055 else ANALYSIS_LEVEL_TARGET_RMS
    working, local_level = _apply_local_leveling(working, target_active_rms=target_rms)
    peak_before_limit = float(np.max(np.abs(working)) + 1e-9)
    ceiling_gain = 1.0
    if peak_before_limit > ANALYSIS_OUTPUT_CEILING:
        ceiling_gain = float(ANALYSIS_OUTPUT_CEILING / peak_before_limit)
        working = working * ceiling_gain

    output_metrics = _measure_level_metrics(working)
    gain = float(output_metrics["rms"] / max(input_metrics["rms"], 1e-9))

    signal_power = float(np.mean(working * working))
    noise_power = max(noise_floor * noise_floor, 1e-12)
    snr_db = float(10.0 * np.log10(max(signal_power - noise_power, 1e-12) / noise_power))
    metadata = {
        "gain": gain,
        "noise_floor": noise_floor,
        "peak": output_metrics["peak"],
        "snr_db": snr_db,
        "raw_rms": input_metrics["rms"],
        "raw_active_rms": input_metrics["active_rms"],
        "raw_peak": input_metrics["peak"],
        "clip_ratio": input_metrics["clip_ratio"],
        "clipped_segments": repaired_segments,
        "pre_gain": pre_level["global_gain"],
        "agc_gain_mean": local_level["gain_mean"],
        "agc_gain_max": local_level["gain_max"],
        "ceiling_gain": ceiling_gain,
        "output_rms": output_metrics["rms"],
        "output_active_rms": output_metrics["active_rms"],
    }
    return working.astype(np.float32), metadata


def _measure_level_metrics(audio: np.ndarray) -> dict[str, float]:
    if audio.size == 0:
        return {"rms": 0.0, "active_rms": 0.0, "peak": 0.0, "clip_ratio": 0.0}

    working = np.nan_to_num(audio.astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0)
    rms = float(np.sqrt(np.mean(working * working)) + 1e-12)
    peak = float(np.max(np.abs(working)) + 1e-12)
    clip_ratio = float(np.mean(np.abs(working) >= ANALYSIS_CLIP_THRESHOLD))
    if working.size < 64:
        return {"rms": rms, "active_rms": rms, "peak": peak, "clip_ratio": clip_ratio}

    frame_length = min(2048, max(256, working.size))
    hop_length = max(64, min(256, max(frame_length // 4, 1)))
    if frame_length <= hop_length:
        hop_length = max(1, frame_length // 2)
    frame_rms = librosa.feature.rms(y=working, frame_length=frame_length, hop_length=hop_length).flatten()
    if frame_rms.size == 0:
        return {"rms": rms, "active_rms": rms, "peak": peak, "clip_ratio": clip_ratio}

    noise_floor = float(np.percentile(frame_rms, 20))
    active_gate = max(noise_floor * 1.8, rms * 0.72, 6e-4)
    active_frames = frame_rms[frame_rms >= active_gate]
    if active_frames.size < max(2, frame_rms.size // 8):
        top_gate = float(np.percentile(frame_rms, 65))
        active_frames = frame_rms[frame_rms >= top_gate]
    active_rms = float(np.mean(active_frames)) if active_frames.size else rms
    return {"rms": rms, "active_rms": active_rms, "peak": peak, "clip_ratio": clip_ratio}


def _repair_clipped_regions(audio: np.ndarray) -> tuple[np.ndarray, float]:
    clipped = np.abs(audio) >= ANALYSIS_CLIP_THRESHOLD
    if not np.any(clipped):
        return audio.astype(np.float32), 0.0

    repaired = np.array(audio, copy=True, dtype=np.float32)
    segment_count = 0
    idx = 0
    while idx < clipped.size:
        if not clipped[idx]:
            idx += 1
            continue
        start = idx
        while idx + 1 < clipped.size and clipped[idx + 1]:
            idx += 1
        end = idx
        left_idx = start - 1
        right_idx = end + 1
        if left_idx >= 0 and right_idx < repaired.size:
            repaired[start : end + 1] = np.linspace(
                repaired[left_idx],
                repaired[right_idx],
                (end - start) + 3,
                dtype=np.float32,
            )[1:-1]
        elif left_idx >= 0:
            repaired[start : end + 1] = repaired[left_idx]
        elif right_idx < repaired.size:
            repaired[start : end + 1] = repaired[right_idx]
        else:
            repaired[start : end + 1] = 0.0
        segment_count += 1
        idx += 1
    return repaired, float(segment_count)


def _apply_global_leveling(audio: np.ndarray) -> tuple[np.ndarray, dict[str, float]]:
    metrics = _measure_level_metrics(audio)
    target_rms = ANALYSIS_LEVEL_TARGET_RMS_LOW if metrics["active_rms"] < 0.055 else ANALYSIS_LEVEL_TARGET_RMS
    desired_gain = target_rms / max(metrics["active_rms"], 1e-5)

    if metrics["active_rms"] < ANALYSIS_LEVEL_MIN_ACTIVE_RMS:
        global_gain = float(np.clip(desired_gain, 1.0, 10.0))
    elif metrics["active_rms"] > ANALYSIS_LEVEL_MAX_ACTIVE_RMS or metrics["peak"] > ANALYSIS_OUTPUT_CEILING:
        global_gain = float(np.clip(desired_gain, 0.25, 1.0))
    else:
        global_gain = float(np.clip(desired_gain, 0.75, 1.35))

    if metrics["peak"] > 0:
        global_gain = float(min(global_gain, 0.94 / metrics["peak"]))
    leveled = (audio * global_gain).astype(np.float32)
    return leveled, {"global_gain": global_gain}


def _apply_local_leveling(audio: np.ndarray, target_active_rms: float) -> tuple[np.ndarray, dict[str, float]]:
    if audio.size < 128:
        return audio.astype(np.float32), {"gain_mean": 1.0, "gain_max": 1.0}

    frame_length = min(2048, max(256, audio.size))
    hop_length = max(64, min(256, max(frame_length // 4, 1)))
    if frame_length <= hop_length:
        hop_length = max(1, frame_length // 2)

    frame_rms = librosa.feature.rms(y=audio, frame_length=frame_length, hop_length=hop_length).flatten()
    if frame_rms.size == 0:
        return audio.astype(np.float32), {"gain_mean": 1.0, "gain_max": 1.0}

    noise_floor = float(np.percentile(frame_rms, 20))
    active_gate = max(noise_floor * 1.9, float(np.mean(frame_rms)) * 0.74, 7e-4)
    active_mask = frame_rms >= active_gate
    if int(np.sum(active_mask)) < max(2, frame_rms.size // 10):
        fallback_gate = max(float(np.percentile(frame_rms, 55)), noise_floor * 1.08, 3e-4)
        active_mask = frame_rms >= fallback_gate
    if int(np.sum(active_mask)) < max(1, frame_rms.size // 16):
        active_mask = frame_rms >= max(float(np.percentile(frame_rms, 40)), 2e-4)
    desired_gains = np.clip(target_active_rms / np.maximum(frame_rms, 1e-4), 0.55, 6.0)
    desired_gains = np.where(active_mask, desired_gains, 1.0)

    smoothed_gains = np.empty_like(desired_gains, dtype=np.float32)
    current_gain = 1.0
    for idx, desired_gain in enumerate(desired_gains):
        smoothing = 0.18 if desired_gain > current_gain else 0.32
        current_gain = current_gain + (float(desired_gain) - current_gain) * smoothing
        smoothed_gains[idx] = current_gain

    frame_positions = np.arange(smoothed_gains.size, dtype=np.float32) * hop_length
    sample_positions = np.arange(audio.size, dtype=np.float32)
    sample_gains = np.interp(sample_positions, frame_positions, smoothed_gains, left=smoothed_gains[0], right=smoothed_gains[-1])
    leveled = (audio * sample_gains.astype(np.float32)).astype(np.float32)
    output_metrics = _measure_level_metrics(leveled)
    makeup_gain = 1.0
    if output_metrics["active_rms"] < ANALYSIS_LEVEL_MIN_ACTIVE_RMS and output_metrics["peak"] > 1e-5:
        needed_gain = target_active_rms / max(output_metrics["active_rms"], 1e-4)
        headroom_gain = ANALYSIS_OUTPUT_CEILING / output_metrics["peak"]
        makeup_gain = float(np.clip(min(needed_gain, headroom_gain), 1.0, 4.0))
        leveled = (leveled * makeup_gain).astype(np.float32)

    return leveled, {"gain_mean": float(np.mean(smoothed_gains) * makeup_gain), "gain_max": float(np.max(smoothed_gains) * makeup_gain)}


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
    working, working_sr = _prepare_analysis_audio(audio, sr, workflow_mode="studio", target_sr=22050)
    if working.size == 0:
        return "C", "major", 0.0
    chroma_stft = librosa.feature.chroma_stft(y=working, sr=working_sr, n_fft=4096, hop_length=512)
    chroma_cens = librosa.feature.chroma_cens(y=working, sr=working_sr, hop_length=512)
    chroma = 0.58 * chroma_stft + 0.42 * chroma_cens
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


def extract_monophonic_notes(
    audio: np.ndarray,
    sr: int,
    hop_length: int = 256,
    singer_profile: dict[str, Any] | None = None,
    workflow_mode: str = "studio",
    preserve_expression: bool = True,
) -> list[dict[str, Any]]:
    return extract_monophonic_notes_expressive(
        audio,
        sr,
        hop_length=hop_length,
        singer_profile=singer_profile,
        workflow_mode=workflow_mode,
        preserve_expression=preserve_expression,
    )


def extract_monophonic_notes_expressive(
    audio: np.ndarray,
    sr: int,
    hop_length: int = 256,
    singer_profile: dict[str, Any] | None = None,
    workflow_mode: str = "studio",
    preserve_expression: bool = True,
) -> list[dict[str, Any]]:
    if audio.size == 0:
        return []

    working, working_sr = _prepare_analysis_audio(audio, sr, workflow_mode=workflow_mode)
    if working.size == 0:
        return []

    f0, voiced, voiced_probs = _estimate_pitch(working, working_sr, hop_length)
    f0 = _refine_pitch_track_hps(f0, working, working_sr, hop_length)
    times = librosa.times_like(f0, sr=working_sr, hop_length=hop_length)
    midi_values = np.where(np.isfinite(f0), librosa.hz_to_midi(f0), np.nan)
    midi_values = _correct_octave_track(midi_values, singer_profile)
    midi_values = _smooth_midi_track(midi_values)

    rms = librosa.feature.rms(y=working, frame_length=2048, hop_length=hop_length).flatten()
    onset_strength = librosa.onset.onset_strength(y=working, sr=working_sr, hop_length=hop_length)
    flatness = librosa.feature.spectral_flatness(y=working, n_fft=1024, hop_length=hop_length).flatten()
    rms = _align_feature_length(rms, times.size)
    onset_strength = _align_feature_length(onset_strength, times.size)
    flatness = _align_feature_length(flatness, times.size)
    voice_mask = _build_voice_mask(voiced, voiced_probs, rms, flatness)
    if float(np.mean(voice_mask)) < 0.02:
        return []
    if float(np.percentile(rms, 90)) < 0.012 and float(np.mean(voiced_probs)) < 0.56:
        return []

    boundaries = _compute_note_boundaries(midi_values, voice_mask, onset_strength, working, working_sr, hop_length)
    if boundaries.size < 2:
        return []

    notes: list[dict[str, Any]] = []
    for idx in range(len(boundaries) - 1):
        start_idx = int(boundaries[idx])
        end_idx = int(boundaries[idx + 1])
        if end_idx - start_idx < 2:
            continue
        segment_mask = voice_mask[start_idx:end_idx]
        if float(np.mean(segment_mask)) < 0.42:
            continue
        segment = midi_values[start_idx:end_idx]
        valid = segment[np.isfinite(segment)]
        if valid.size == 0:
            continue

        start = float(times[start_idx])
        end = float(times[end_idx - 1] + (hop_length / working_sr))
        if end - start < 0.05:
            continue
        if float(np.mean(rms[start_idx:end_idx])) < 0.012:
            continue
        pitch = int(round(np.median(valid)))
        sample_start = int(max(0, round(start * working_sr)))
        sample_end = int(min(working.size, round(end * working_sr)))
        spectral_pitch = _segment_fundamental_midi(working[sample_start:sample_end], working_sr)
        if spectral_pitch is not None and 1 <= abs(spectral_pitch - pitch) <= 3:
            pitch = spectral_pitch
        confidence = _note_confidence(valid, voiced_probs[start_idx:end_idx], rms[start_idx:end_idx], flatness[start_idx:end_idx])
        if confidence < 0.22:
            continue
        pitch_curve = _build_pitch_curve(times[start_idx:end_idx], segment, pitch, preserve_expression)
        expression_curve = _build_expression_curve(times[start_idx:end_idx], rms[start_idx:end_idx], start, end)
        velocity = _velocity_from_features(rms[start_idx:end_idx], onset_strength[start_idx:end_idx], confidence)

        articulation = "detached"
        if notes:
            gap = start - float(notes[-1]["end"])
            if gap <= 0.055:
                articulation = "legato"

        notes.append(
            {
                "pitch": int(np.clip(pitch, MIN_MIDI_NOTE, MAX_MIDI_NOTE)),
                "start": round(start, 4),
                "end": round(end, 4),
                "velocity": velocity,
                "track": "notes",
                "confidence": round(confidence, 4),
                "articulation": articulation,
                "pitch_curve": pitch_curve,
                "expression_curve": expression_curve,
                "vibrato_cents": round(_estimate_vibrato_cents(pitch_curve, pitch), 3),
                "drift_cents": round(_estimate_drift_cents(pitch_curve, pitch), 3),
            }
        )

    if not notes:
        return []
    return smooth_note_events(notes, min_duration=0.06, merge_gap=0.12)


def _estimate_pitch(audio: np.ndarray, sr: int, hop_length: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    try:
        f0, voiced_flag, voiced_prob = librosa.pyin(
            audio,
            fmin=MIN_VOICE_HZ,
            fmax=MAX_VOICE_HZ,
            sr=sr,
            hop_length=hop_length,
            frame_length=4096,
        )
        f0 = np.asarray(f0, dtype=float)
        voiced_flag = np.asarray(voiced_flag, dtype=bool)
        voiced_prob = np.asarray(voiced_prob, dtype=float)
        voiced = voiced_flag & (voiced_prob > 0.48)
        f0 = np.where(voiced, f0, np.nan)
        if np.sum(np.isfinite(f0)) < 3:
            raise ValueError("pyin could not find stable voiced frames")
        return f0, voiced, voiced_prob
    except Exception:
        f0 = librosa.yin(
            audio,
            fmin=MIN_VOICE_HZ,
            fmax=MAX_VOICE_HZ,
            sr=sr,
            hop_length=hop_length,
            trough_threshold=0.14,
        )
        voiced = np.isfinite(f0)
        probs = np.where(voiced, 0.68, 0.0)
        return f0, voiced, probs


def _refine_pitch_track_hps(f0: np.ndarray, audio: np.ndarray, sr: int, hop_length: int) -> np.ndarray:
    """Refine frame-level F0 with harmonic-aware scoring from FFT bins."""
    if f0.size == 0 or audio.size == 0:
        return f0

    n_fft = 4096 if sr >= 32000 else 2048
    spectrum = np.abs(librosa.stft(audio, n_fft=n_fft, hop_length=hop_length, window="hann"))
    if spectrum.size == 0:
        return f0
    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)
    refined = np.array(f0, copy=True, dtype=float)

    frame_count = min(refined.size, spectrum.shape[1])
    for frame_idx in range(frame_count):
        base_hz = float(refined[frame_idx])
        if not np.isfinite(base_hz) or base_hz <= 0:
            continue
        mag = spectrum[:, frame_idx]
        if float(np.max(mag)) < 1e-7:
            continue
        best_hz = base_hz
        best_score = -1.0
        for octave_factor in (0.5, 1.0, 2.0):
            candidate_hz = base_hz * octave_factor
            if candidate_hz < MIN_VOICE_HZ or candidate_hz > MAX_VOICE_HZ:
                continue
            lo = max(MIN_VOICE_HZ, candidate_hz * 0.92)
            hi = min(MAX_VOICE_HZ, candidate_hz * 1.08)
            candidate_bins = np.where((freqs >= lo) & (freqs <= hi))[0]
            if candidate_bins.size == 0:
                continue
            local_scores = np.array(
                [_fundamental_candidate_score(freqs, mag, float(freqs[bin_idx])) for bin_idx in candidate_bins],
                dtype=np.float64,
            )
            local_best_idx = int(np.argmax(local_scores))
            local_hz = float(freqs[candidate_bins[local_best_idx]])
            local_score = float(local_scores[local_best_idx])
            if local_score > best_score:
                best_score = local_score
                best_hz = local_hz
        base_midi = float(librosa.hz_to_midi(base_hz))
        best_midi = float(librosa.hz_to_midi(best_hz))
        if abs(best_midi - base_midi) > 12.2:
            continue
        refined[frame_idx] = 0.25 * base_hz + 0.75 * best_hz
    return refined


def _fundamental_candidate_score(freqs: np.ndarray, mag: np.ndarray, candidate_hz: float) -> float:
    if candidate_hz <= 0:
        return -1.0
    score = 0.0
    for order in range(1, MAX_HARMONIC_ORDER + 1):
        harmonic_hz = candidate_hz * order
        if harmonic_hz > freqs[-1]:
            break
        harmonic_idx = int(np.argmin(np.abs(freqs - harmonic_hz)))
        harmonic_mag = float(np.max(mag[max(0, harmonic_idx - 1) : min(mag.size, harmonic_idx + 2)]))
        weight = 2.1 if order == 1 else (1.0 / (order**1.08))
        score += harmonic_mag * weight
    subharmonic_hz = candidate_hz * 0.5
    if subharmonic_hz >= freqs[0]:
        sub_idx = int(np.argmin(np.abs(freqs - subharmonic_hz)))
        sub_mag = float(np.max(mag[max(0, sub_idx - 1) : min(mag.size, sub_idx + 2)]))
        score -= sub_mag * 0.28
    return score


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
    if end - start < 0.04:
        return []

    base_vel = float(np.mean(rms[start_idx:end_idx]) * 230.0)
    attack_boost = float(np.max(onset_strength[start_idx:end_idx]) * 8.0)
    velocity = int(np.clip(base_vel + attack_boost + 20, 30, 122))
    return [
        {
            "pitch": int(np.clip(midi_pitch, MIN_MIDI_NOTE, MAX_MIDI_NOTE)),
            "start": start,
            "end": end,
            "velocity": velocity,
            "track": "notes",
        }
    ]


def detect_chords(audio: np.ndarray, sr: int) -> list[dict[str, Any]]:
    if audio.size == 0:
        return []
    working, working_sr = _prepare_analysis_audio(audio, sr, workflow_mode="studio", target_sr=22050)
    rms = float(np.sqrt(np.mean(working * working)) + 1e-9)
    if rms < 0.012:
        return []
    mono_poly, mono_conf = detect_mono_poly(working, working_sr)
    if mono_poly == "mono" and mono_conf >= 0.58:
        return []

    tempo, beat_frames = librosa.beat.beat_track(y=working, sr=working_sr, trim=False)
    tempo_value = float(np.atleast_1d(tempo)[0])
    tempo = float(tempo_value if np.isfinite(tempo_value) and tempo_value > 0 else 120.0)
    if len(beat_frames) < 4:
        hop = int(0.45 * working_sr)
        beat_frames = np.arange(0, len(working), hop, dtype=int)
        beat_times = beat_frames / working_sr
    else:
        beat_times = librosa.frames_to_time(beat_frames, sr=working_sr)

    hop_length = 512
    chroma_stft = librosa.feature.chroma_stft(y=working, sr=working_sr, n_fft=4096, hop_length=hop_length)
    chroma_cens = librosa.feature.chroma_cens(y=working, sr=working_sr, hop_length=hop_length)
    chroma = 0.55 * chroma_stft + 0.45 * chroma_cens
    chroma = chroma / (np.linalg.norm(chroma, axis=0, keepdims=True) + 1e-9)
    if chroma.shape[1] >= 5:
        chroma = medfilt(chroma, kernel_size=(1, 5))
    chroma_times = librosa.frames_to_time(np.arange(chroma.shape[1]), sr=working_sr, hop_length=hop_length)

    segment_edges = beat_times[::2] if len(beat_times) > 6 else beat_times
    if segment_edges.size < 2:
        segment_edges = np.array([0.0, max(len(working) / working_sr, 0.5)])
    if segment_edges[-1] < len(working) / working_sr:
        segment_edges = np.append(segment_edges, len(working) / working_sr)

    raw_chords: list[dict[str, Any]] = []
    bass_pc = _estimate_bass_pc(working, working_sr)
    score_threshold = 0.27 if mono_poly == "poly" else 0.33
    for idx in range(len(segment_edges) - 1):
        start = float(segment_edges[idx])
        end = float(segment_edges[idx + 1])
        if end - start < 0.18:
            continue
        mask = (chroma_times >= start) & (chroma_times < end)
        if not np.any(mask):
            continue
        seg = chroma[:, mask].mean(axis=1)
        root_idx, quality, score = _classify_chord(seg, bass_pc=bass_pc)
        if score < score_threshold:
            continue
        root_name = NOTE_NAMES[root_idx]
        raw_chords.append(
            {
                "start": round(start, 4),
                "end": round(end, 4),
                "root": root_name,
                "quality": quality,
                "label": f"{root_name}{quality}",
                "pitches": _build_chord_voicing(root_idx, quality, raw_chords[-1] if raw_chords else None),
                "confidence": float(np.clip(score * 1.45, 0.0, 1.0)),
                "velocity": 84,
                "track": "chords",
            }
        )
    chords = _merge_chord_segments(raw_chords)
    if chords:
        return chords

    harmonic_guess = _infer_chord_from_harmonics(working, working_sr)
    if harmonic_guess is not None and float(harmonic_guess.get("confidence", 0.0)) >= 0.45:
        harmonic_guess["pitches"] = _build_chord_voicing(
            NOTE_NAMES.index(harmonic_guess["root"]),
            harmonic_guess["quality"],
            None,
        )
        return [harmonic_guess]
    return []


def _infer_chord_from_harmonics(audio: np.ndarray, sr: int) -> dict[str, Any] | None:
    if audio.size < 256:
        return None
    n_fft = int(2 ** np.ceil(np.log2(min(max(audio.size, 2048), 16384))))
    windowed = audio[: min(audio.size, n_fft)] * np.hanning(min(audio.size, n_fft))
    spectrum = np.abs(np.fft.rfft(windowed, n=n_fft))
    freqs = np.fft.rfftfreq(n_fft, d=1.0 / sr)
    mask = (freqs >= MIN_VOICE_HZ) & (freqs <= 2000.0)
    if not np.any(mask):
        return None
    band_freqs = freqs[mask]
    band_mag = spectrum[mask]
    if band_mag.size < 8:
        return None

    peak_floor = max(float(np.percentile(band_mag, 65) * 1.35), 1e-9)
    peaks, props = find_peaks(band_mag, height=peak_floor, distance=4)
    if peaks.size == 0:
        return None
    peak_heights = np.asarray(props.get("peak_heights", np.zeros(peaks.size)), dtype=float)
    best_freq = None
    best_score = -1.0
    for idx, peak in enumerate(peaks):
        freq = float(band_freqs[int(peak)])
        score = float(peak_heights[idx] if idx < peak_heights.size else band_mag[int(peak)])
        for order in range(2, MAX_HARMONIC_ORDER + 1):
            harmonic_freq = freq * order
            if harmonic_freq > band_freqs[-1]:
                break
            harmonic_idx = int(np.argmin(np.abs(band_freqs - harmonic_freq)))
            score += float(band_mag[harmonic_idx]) / (order**1.1)
        if score > best_score:
            best_score = score
            best_freq = freq
    if best_freq is None or best_freq <= 0:
        return None

    root_midi = int(round(float(librosa.hz_to_midi(best_freq))))
    root_idx = root_midi % 12
    harmonic_pcs: set[int] = set()
    for peak in peaks:
        hz = float(band_freqs[int(peak)])
        if hz <= 0:
            continue
        midi = float(librosa.hz_to_midi(hz))
        if np.isfinite(midi):
            harmonic_pcs.add(int(round(midi)) % 12)
    if not harmonic_pcs:
        return None
    intervals = {(pc - root_idx) % 12 for pc in harmonic_pcs}
    if 3 in intervals and 7 in intervals:
        quality = "min"
    elif 4 in intervals and 7 in intervals:
        quality = "maj"
    elif 3 in intervals and 10 in intervals:
        quality = "min7"
    elif 4 in intervals and 10 in intervals:
        quality = "dom7"
    elif 5 in intervals and 7 in intervals:
        quality = "sus4"
    else:
        quality = "maj"

    duration = max(len(audio) / sr, 0.5)
    peak_norm = float(best_score / (np.max(band_mag) + 1e-9))
    confidence = float(np.clip(0.3 + peak_norm * 0.45, 0.2, 0.9))
    return {
        "start": 0.0,
        "end": float(duration),
        "root": NOTE_NAMES[root_idx],
        "quality": quality,
        "label": f"{NOTE_NAMES[root_idx]}{quality}",
        "pitches": [60 + ((root_idx + interval) % 12) for interval in CHORD_TEMPLATES[quality][:4]],
        "confidence": confidence,
        "velocity": 80,
        "track": "chords",
    }


def _classify_chord(chroma: np.ndarray, bass_pc: int | None = None) -> tuple[int, str, float]:
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
            if bass_pc is not None and bass_pc == root_idx:
                score += 0.05
            if quality.startswith("min") and chroma[(root_idx + 3) % 12] > chroma[(root_idx + 4) % 12]:
                score += 0.05
            if quality == "maj" and chroma[(root_idx + 4) % 12] > chroma[(root_idx + 3) % 12]:
                score += 0.04
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
    if audio.size == 0:
        return []
    working, working_sr = _prepare_analysis_audio(audio, sr, workflow_mode="live", target_sr=22050)
    if float(np.sqrt(np.mean(working * working)) + 1e-9) < 0.015:
        return []
    harmonic, percussive = librosa.effects.hpss(working, margin=(1.0, 6.0))
    percussive_ratio = float(np.mean(np.abs(percussive)) / (np.mean(np.abs(harmonic)) + 1e-9))
    flatness = float(librosa.feature.spectral_flatness(y=working).mean())
    if percussive_ratio < 0.26 and flatness < 0.24:
        return []
    onset_main_times = librosa.onset.onset_detect(
        y=percussive,
        sr=working_sr,
        units="time",
        pre_max=20,
        post_max=20,
        pre_avg=10,
        post_avg=10,
        delta=0.16,
        wait=1,
    )
    low_onsets = _detect_band_onsets(percussive, working_sr, (20, 220), threshold_q=74)
    high_onsets = _detect_band_onsets(percussive, working_sr, (2000, 9000), threshold_q=76)
    low_times = librosa.frames_to_time(low_onsets, sr=working_sr, hop_length=256)
    high_times = librosa.frames_to_time(high_onsets, sr=working_sr, hop_length=256)
    onset_times = np.sort(np.concatenate([onset_main_times, low_times, high_times]))
    if onset_times.size:
        deduped = [float(onset_times[0])]
        for onset in onset_times[1:]:
            if float(onset - deduped[-1]) > 0.085:
                deduped.append(float(onset))
        onset_times = np.array(deduped)

    events: list[dict[str, Any]] = []
    win = int(working_sr * 0.10)
    lookback = int(working_sr * 0.012)
    for onset_time in onset_times:
        start = int(max(0, onset_time * working_sr - lookback))
        stop = min(len(working), start + win)
        clip = percussive[start:stop]
        if clip.size < 32:
            continue
        harmonic_clip = harmonic[start:stop]
        if clip.size and np.mean(np.abs(harmonic_clip)) > np.mean(np.abs(clip)) * 1.2:
            continue
        features = _extract_drum_features(clip, working_sr)
        label, confidence = _classify_drum(features)
        if confidence < 0.56:
            continue
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
    if percussive_ratio < 0.42 and len(events) > 12:
        events = [event for event in events if float(event.get("confidence", 0.0)) >= 0.74]
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
    half = max(1, len(clip) // 2)
    decay_ratio = float((np.mean(np.abs(clip[half:])) + 1e-9) / (np.mean(np.abs(clip[:half])) + 1e-9))
    return {
        "low_n": low / total,
        "mid_n": mid / total,
        "high_n": high / total,
        "centroid_n": min(centroid / 9000.0, 1.0),
        "rolloff_n": min(rolloff / 10000.0, 1.0),
        "flatness": flatness,
        "zcr": zcr,
        "rms": rms,
        "decay_ratio": decay_ratio,
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
    elif features["high_n"] > 0.62:
        if features["rms"] > 0.08 and features.get("decay_ratio", 0.0) > 0.04:
            best_label = "snare"
            best_score = max(best_score, 0.8)
        else:
            best_label = "hihat_closed" if features.get("decay_ratio", 0.0) < 0.22 else "hihat_open"
            best_score = max(best_score, 0.8)
    elif features["high_n"] > 0.58 and features["rolloff_n"] > 0.72 and features.get("decay_ratio", 0.0) > 0.18:
        best_label = "crash"
        best_score = max(best_score, 0.75)
    elif (
        features["mid_n"] > 0.34
        and features["flatness"] > 0.18
        and features["low_n"] < 0.34
        and features["centroid_n"] < 0.48
    ):
        best_label = "snare"
        best_score = max(best_score, 0.73)

    confidence = float(np.clip((best_score + 1.0) / 2.0, 0.35, 0.98))
    if best_label == "hihat_open" and features.get("decay_ratio", 0.0) < 0.22:
        best_label = "hihat_closed"
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


def _prepare_analysis_audio(
    audio: np.ndarray,
    sr: int,
    workflow_mode: str,
    target_sr: int | None = None,
) -> tuple[np.ndarray, int]:
    desired_sr = target_sr or (16000 if workflow_mode == "live" else 22050)
    if sr <= desired_sr or audio.size < sr:
        return audio.astype(np.float32), sr
    working = librosa.resample(audio.astype(np.float32), orig_sr=sr, target_sr=desired_sr)
    return working.astype(np.float32), desired_sr


def _align_feature_length(values: np.ndarray, target_len: int) -> np.ndarray:
    if values.size == target_len:
        return values
    if values.size < target_len:
        if values.size == 0:
            return np.zeros(target_len, dtype=np.float32)
        return np.pad(values, (0, target_len - values.size), mode="edge")
    return values[:target_len]


def _smooth_midi_track(midi_values: np.ndarray) -> np.ndarray:
    valid_idx = np.where(np.isfinite(midi_values))[0]
    if valid_idx.size < 3:
        return midi_values
    kernel = 5 if valid_idx.size >= 5 else 3
    smoothed = np.array(midi_values, copy=True)
    smoothed[valid_idx] = medfilt(smoothed[valid_idx], kernel_size=kernel)
    return smoothed


def _build_voice_mask(
    voiced: np.ndarray,
    voiced_probs: np.ndarray,
    rms: np.ndarray,
    flatness: np.ndarray,
) -> np.ndarray:
    if rms.size == 0:
        return np.zeros_like(voiced, dtype=bool)
    rms_floor = float(np.percentile(rms, 15))
    rms_peak = float(np.percentile(rms, 90))
    rms_gate = rms_floor + max(rms_peak - rms_floor, 1e-6) * 0.14
    flatness_limit = float(np.percentile(flatness, 78) * 1.25) if flatness.size else 0.45
    mask = (voiced_probs >= 0.28) & (rms >= rms_gate) & (flatness <= max(flatness_limit, 0.24))
    mask = mask | (voiced & (voiced_probs >= 0.2) & (rms >= rms_gate * 0.8))
    return mask.astype(bool)


def _compute_note_boundaries(
    midi_values: np.ndarray,
    voice_mask: np.ndarray,
    onset_strength: np.ndarray,
    audio: np.ndarray,
    sr: int,
    hop_length: int,
) -> np.ndarray:
    if midi_values.size == 0:
        return np.array([], dtype=int)
    onset_frames = librosa.onset.onset_detect(
        y=audio,
        sr=sr,
        hop_length=hop_length,
        units="frames",
        backtrack=False,
        delta=max(0.05, float(np.percentile(onset_strength, 75)) * 0.08) if onset_strength.size else 0.05,
    )
    pitch_jump_frames: list[int] = []
    for idx in range(3, len(midi_values) - 3):
        if not voice_mask[idx]:
            continue
        left = midi_values[idx - 3 : idx]
        right = midi_values[idx : idx + 3]
        left_valid = left[np.isfinite(left)]
        right_valid = right[np.isfinite(right)]
        if left_valid.size < 2 or right_valid.size < 2:
            continue
        pitch_delta = abs(float(np.median(right_valid) - np.median(left_valid)))
        left_std = float(np.std(left_valid))
        right_std = float(np.std(right_valid))
        strong_boundary = pitch_delta >= 1.6 and float(onset_strength[idx]) >= float(np.percentile(onset_strength, 58))
        stable_shift = pitch_delta >= 0.95 and left_std <= 0.35 and right_std <= 0.35
        if strong_boundary or stable_shift:
            pitch_jump_frames.append(idx)
    voiced_edge_frames = np.where(np.diff(voice_mask.astype(np.int8)) != 0)[0] + 1
    boundaries = np.unique(
        np.concatenate(([0], onset_frames, np.array(pitch_jump_frames, dtype=int), voiced_edge_frames, [len(midi_values)]))
    ).astype(int)
    boundaries = boundaries[(boundaries >= 0) & (boundaries <= len(midi_values))]
    if boundaries.size < 2:
        return np.array([], dtype=int)
    return boundaries


def _correct_octave_track(midi_values: np.ndarray, singer_profile: dict[str, Any] | None) -> np.ndarray:
    corrected = np.array(midi_values, copy=True, dtype=float)
    valid_idx = np.where(np.isfinite(corrected))[0]
    if valid_idx.size < 2:
        return corrected
    if singer_profile is None:
        return corrected
    center = float(np.nanmedian(corrected[valid_idx]))
    low = center - 14.0
    high = center + 14.0
    profile_center = singer_profile.get("center_midi")
    if profile_center is not None:
        center = float(profile_center)
    profile_low = singer_profile.get("low_midi")
    profile_high = singer_profile.get("high_midi")
    if profile_low is not None:
        low = float(profile_low) - 5.0
    if profile_high is not None:
        high = float(profile_high) + 5.0
    previous = None
    for idx in valid_idx:
        value = float(corrected[idx])
        candidates = [value + (12.0 * offset) for offset in range(-2, 3)]
        target = previous if previous is not None else center
        best = value
        if value < low or value > high:
            best = min(
                candidates,
                key=lambda candidate: abs(candidate - target)
                + max(low - candidate, 0.0) * 0.3
                + max(candidate - high, 0.0) * 0.3,
            )
        corrected[idx] = best
        previous = best
    return corrected


def _note_confidence(
    midi_values: np.ndarray,
    voiced_probs: np.ndarray,
    rms: np.ndarray,
    flatness: np.ndarray,
) -> float:
    stability = 1.0 - min(float(np.std(midi_values)) / 0.55, 1.0)
    voiced_term = float(np.mean(voiced_probs)) if voiced_probs.size else 0.0
    rms_term = min(float(np.mean(rms)) * 18.0, 1.0) if rms.size else 0.0
    flatness_term = 1.0 - min(float(np.mean(flatness)) * 2.2, 1.0) if flatness.size else 0.0
    return float(np.clip(0.4 * voiced_term + 0.28 * stability + 0.2 * rms_term + 0.12 * flatness_term, 0.0, 1.0))


def _build_pitch_curve(
    times: np.ndarray,
    midi_values: np.ndarray,
    base_pitch: int,
    preserve_expression: bool,
) -> list[dict[str, float]]:
    if not preserve_expression:
        return []
    points: list[dict[str, float]] = []
    for idx in range(0, len(times), 2):
        value = float(midi_values[idx]) if idx < len(midi_values) else math.nan
        if not np.isfinite(value):
            continue
        if abs(value - float(base_pitch)) > 2.25:
            continue
        points.append({"time": round(float(times[idx]), 4), "midi": round(value, 4)})
    return points


def _build_expression_curve(times: np.ndarray, rms: np.ndarray, start: float, end: float) -> list[dict[str, float]]:
    if times.size == 0 or rms.size == 0:
        return []
    rms_min = float(np.min(rms))
    rms_span = max(float(np.max(rms)) - rms_min, 1e-6)
    points: list[dict[str, float]] = []
    for idx in range(0, len(times), 2):
        value = float(np.clip((rms[idx] - rms_min) / rms_span, 0.0, 1.0))
        points.append({"time": round(float(np.clip(times[idx], start, end)), 4), "value": round(value, 4)})
    return points


def _estimate_vibrato_cents(pitch_curve: list[dict[str, float]], base_pitch: int) -> float:
    if len(pitch_curve) < 3:
        return 0.0
    values = np.array([float(point["midi"]) for point in pitch_curve], dtype=float)
    return float(np.percentile(np.abs((values - float(base_pitch)) * 100.0), 80))


def _estimate_drift_cents(pitch_curve: list[dict[str, float]], base_pitch: int) -> float:
    if len(pitch_curve) < 2:
        return 0.0
    return float((float(pitch_curve[-1]["midi"]) - float(pitch_curve[0]["midi"])) * 100.0)


def _velocity_from_features(rms: np.ndarray, onset_strength: np.ndarray, confidence: float) -> int:
    base_vel = float(np.mean(rms) * 220.0) if rms.size else 40.0
    attack_boost = float(np.max(onset_strength) * 6.0) if onset_strength.size else 0.0
    return int(np.clip(base_vel + attack_boost + confidence * 22.0 + 18.0, 28, 123))


def _merge_time_series(
    left: list[dict[str, Any]] | None,
    right: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    points = []
    if left:
        points.extend(left)
    if right:
        points.extend(right)
    if not points:
        return []
    points.sort(key=lambda point: float(point.get("time", 0.0)))
    merged = [points[0]]
    for point in points[1:]:
        if abs(float(point.get("time", 0.0)) - float(merged[-1].get("time", 0.0))) <= 0.01:
            merged[-1] = point
            continue
        merged.append(point)
    return merged


def _estimate_bass_pc(audio: np.ndarray, sr: int) -> int | None:
    if audio.size < 256:
        return None
    spectrum = np.abs(np.fft.rfft(audio * np.hanning(audio.size)))
    freqs = np.fft.rfftfreq(audio.size, d=1.0 / sr)
    mask = (freqs >= 45.0) & (freqs <= 220.0)
    if not np.any(mask):
        return None
    band_freqs = freqs[mask]
    band_mag = spectrum[mask]
    if band_mag.size == 0 or float(np.max(band_mag)) < 1e-8:
        return None
    peak_freq = float(band_freqs[int(np.argmax(band_mag))])
    midi = float(librosa.hz_to_midi(max(peak_freq, 1e-6)))
    return int(round(midi)) % 12 if np.isfinite(midi) else None


def _build_chord_voicing(root_idx: int, quality: str, previous: dict[str, Any] | None) -> list[int]:
    intervals = CHORD_TEMPLATES[quality][:4]
    root_pitch = 48 + root_idx
    if previous and previous.get("pitches"):
        prev_root = min(int(pitch) for pitch in previous["pitches"])
        while root_pitch - prev_root > 7:
            root_pitch -= 12
        while prev_root - root_pitch > 7:
            root_pitch += 12
    pitches = [root_pitch + interval for interval in intervals]
    if len(pitches) >= 3 and quality.startswith("maj"):
        pitches.append(root_pitch + 12 + intervals[1])
    return [int(np.clip(pitch, 36, 84)) for pitch in pitches[:4]]


def _segment_fundamental_midi(segment_audio: np.ndarray, sr: int) -> int | None:
    if segment_audio.size < 128:
        return None
    windowed = segment_audio.astype(np.float32) * np.hanning(segment_audio.size)
    spectrum = np.abs(np.fft.rfft(windowed))
    freqs = np.fft.rfftfreq(segment_audio.size, d=1.0 / sr)
    mask = (freqs >= 70.0) & (freqs <= 1500.0)
    if not np.any(mask):
        return None
    band_freqs = freqs[mask]
    band_mag = spectrum[mask]
    if band_mag.size == 0 or float(np.max(band_mag)) < 1e-7:
        return None
    peak_threshold = float(np.max(band_mag) * 0.22)
    peak_indices = np.where(band_mag >= peak_threshold)[0]
    if peak_indices.size == 0:
        peak_indices = np.array([int(np.argmax(band_mag))])
    chosen_idx = int(peak_indices[0])
    chosen_hz = float(band_freqs[chosen_idx])
    midi_value = float(librosa.hz_to_midi(chosen_hz))
    if not np.isfinite(midi_value):
        return None
    return int(round(midi_value))


def quantize_events(
    events: list[dict[str, Any]],
    bpm: float,
    grid_division: int = 4,
    strength: float = 1.0,
) -> list[dict[str, Any]]:
    if bpm <= 0:
        return events
    strength = float(np.clip(strength, 0.0, 1.0))
    if strength <= 0.0:
        return [dict(event) for event in events]
    step = (60.0 / bpm) / grid_division
    quantized: list[dict[str, Any]] = []
    for event in events:
        cur = dict(event)
        start_raw = float(event["start"])
        end_raw = float(event["end"])
        original_duration = max(end_raw - start_raw, 1e-4)
        start_quant = round(start_raw / step) * step
        end_quant = round(end_raw / step) * step
        start = start_raw + (start_quant - start_raw) * strength
        end = end_raw + (end_quant - end_raw) * strength
        min_duration = min(original_duration, step)
        if end - start < min_duration:
            end = start + min_duration
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
        pitch_gap = abs(int(evt.get("pitch", -1)) - int(prev.get("pitch", -2)))
        same_pitch = pitch_gap == 0
        prev_duration = float(prev["end"]) - float(prev["start"])
        cur_duration = float(evt["end"]) - float(evt["start"])
        can_merge = same_pitch or (
            pitch_gap <= 1
            and gap <= (merge_gap * 1.5)
            and (prev.get("articulation") == "legato" or evt.get("articulation") == "legato")
            and (
                float(prev.get("confidence", 0.0)) < 0.58
                or float(evt.get("confidence", 0.0)) < 0.58
                or prev_duration < 0.16
                or cur_duration < 0.16
                or (int(prev.get("velocity", 0)) < 70 and int(evt.get("velocity", 0)) < 70)
            )
        )
        if can_merge and gap <= (merge_gap * 1.5):
            prev["end"] = max(float(prev["end"]), float(evt["end"]))
            prev["velocity"] = int(np.clip((int(prev["velocity"]) + int(evt["velocity"])) / 2, 1, 127))
            prev["confidence"] = float(max(float(prev.get("confidence", 0.0)), float(evt.get("confidence", 0.0))))
            prev["pitch_curve"] = _merge_time_series(prev.get("pitch_curve"), evt.get("pitch_curve"))
            prev["expression_curve"] = _merge_time_series(prev.get("expression_curve"), evt.get("expression_curve"))
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
            if abs(prev_pitch - next_pitch) <= 4 and min(prev_pitch, next_pitch) <= cur_pitch <= max(prev_pitch, next_pitch):
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
