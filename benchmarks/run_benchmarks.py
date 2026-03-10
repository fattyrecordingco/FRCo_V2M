from __future__ import annotations

import json
import math
import sys
import time
import tracemalloc
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.analysis_service import (  # noqa: E402
    _estimate_pitch,
    detect_chords,
    enhance_for_analysis,
    extract_monophonic_notes,
    split_stems,
    transcribe_drums,
)
from app.services.controller_service import analyze_controller_input  # noqa: E402

SR = 44100
HOP_LENGTH = 256
FIXTURE_DIR = ROOT / "benchmarks" / "workspace" / "fixtures"
RESULTS_DIR = ROOT / "benchmarks" / "results"


@dataclass(slots=True)
class NoteRef:
    pitch: int
    start: float
    end: float


@dataclass(slots=True)
class ChordRef:
    label: str
    start: float
    end: float


@dataclass(slots=True)
class DrumRef:
    label: str
    start: float
    end: float


@dataclass(slots=True)
class BenchmarkCase:
    name: str
    kind: str
    path: Path
    notes: list[NoteRef]
    chords: list[ChordRef]
    drums: list[DrumRef]
    frame_pitch_hz: np.ndarray | None = None
    controller_windows: list[tuple[float, float]] | None = None
    smoke_only: bool = False


def main() -> None:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    cases = build_cases()
    results = [run_case(case) for case in cases]
    aggregate = summarize_results(results)
    generated_at = datetime.now(UTC).isoformat()
    payload = {
        "generated_at": generated_at,
        "sample_rate": SR,
        "hop_length": HOP_LENGTH,
        "aggregate": aggregate,
        "cases": results,
    }

    stem = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    json_path = RESULTS_DIR / f"benchmark_{stem}.json"
    md_path = RESULTS_DIR / f"benchmark_{stem}.md"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")

    print(f"saved_json {json_path}")
    print(f"saved_md {md_path}")
    print(f"aggregate_note_f1 {aggregate.get('note_f1_mean', 0.0):.3f}")
    print(f"aggregate_chord_acc {aggregate.get('chord_accuracy_mean', 0.0):.3f}")
    print(f"aggregate_drum_f1 {aggregate.get('drum_f1_mean', 0.0):.3f}")
    print(f"aggregate_false_notes_per_s {aggregate.get('noise_false_notes_per_s_mean', 0.0):.3f}")


def build_cases() -> list[BenchmarkCase]:
    cases = [
        build_clean_melody_case(),
        build_low_hum_case(),
        build_noisy_room_case(),
        build_octave_jumps_case(),
        build_legato_case(),
        build_staccato_case(),
        build_poly_case(),
        build_drum_case(),
        build_silence_case(),
        build_long_form_case(),
        build_controller_case(),
    ]
    cases.extend(discover_smoke_cases())
    return cases


def build_clean_melody_case() -> BenchmarkCase:
    notes = [
        NoteRef(60, 0.00, 0.22),
        NoteRef(62, 0.22, 0.44),
        NoteRef(64, 0.44, 0.66),
        NoteRef(67, 0.66, 0.88),
        NoteRef(69, 0.88, 1.10),
        NoteRef(67, 1.10, 1.32),
        NoteRef(64, 1.32, 1.54),
        NoteRef(62, 1.54, 1.76),
    ]
    audio, frame_pitch = synth_note_phrase(notes, gain=0.30, release=0.20, noise=0.0)
    return write_case("clean_sung_melody", "notes", audio, notes=notes, frame_pitch_hz=frame_pitch)


def build_low_hum_case() -> BenchmarkCase:
    duration = 1.8
    sample_count = int(SR * duration)
    t = np.arange(sample_count) / SR
    rng = np.random.default_rng(9)
    hum = 0.014 * np.sin(2 * np.pi * 220.0 * t)
    harmonic = 0.005 * np.sin(2 * np.pi * 440.0 * t)
    room = rng.normal(0.0, 0.0018, size=sample_count)
    audio = (hum + harmonic + room).astype(np.float32)
    frame_pitch = np.full(frame_count_for_samples(sample_count), 220.0, dtype=np.float32)
    notes = [NoteRef(57, 0.10, duration - 0.10)]
    return write_case("low_volume_humming", "notes", audio, notes=notes, frame_pitch_hz=frame_pitch)


def build_noisy_room_case() -> BenchmarkCase:
    notes = [
        NoteRef(64, 0.05, 0.35),
        NoteRef(66, 0.35, 0.67),
        NoteRef(67, 0.67, 1.02),
        NoteRef(69, 1.02, 1.40),
    ]
    audio, frame_pitch = synth_note_phrase(notes, gain=0.19, release=0.32, noise=0.006)
    t = np.arange(audio.size) / SR
    aircon = 0.010 * np.sin(2 * np.pi * 120.0 * t)
    audio = np.clip(audio + aircon, -1.0, 1.0).astype(np.float32)
    return write_case("noisy_room_vocal", "notes", audio, notes=notes, frame_pitch_hz=frame_pitch)


def build_octave_jumps_case() -> BenchmarkCase:
    notes = [
        NoteRef(48, 0.00, 0.28),
        NoteRef(60, 0.28, 0.56),
        NoteRef(72, 0.56, 0.86),
        NoteRef(67, 0.86, 1.16),
        NoteRef(79, 1.16, 1.46),
        NoteRef(55, 1.46, 1.78),
    ]
    audio, frame_pitch = synth_note_phrase(notes, gain=0.26, release=0.16, noise=0.001)
    return write_case("octave_jumps", "notes", audio, notes=notes, frame_pitch_hz=frame_pitch)


def build_legato_case() -> BenchmarkCase:
    notes = [
        NoteRef(62, 0.00, 0.46),
        NoteRef(64, 0.42, 0.92),
        NoteRef(67, 0.88, 1.45),
        NoteRef(69, 1.38, 1.95),
    ]
    audio, frame_pitch = synth_note_phrase(notes, gain=0.24, release=0.44, noise=0.0007, glide=0.07)
    return write_case("legato_phrase", "notes", audio, notes=notes, frame_pitch_hz=frame_pitch)


def build_staccato_case() -> BenchmarkCase:
    notes = [
        NoteRef(72, 0.00, 0.10),
        NoteRef(74, 0.20, 0.30),
        NoteRef(76, 0.42, 0.52),
        NoteRef(77, 0.63, 0.73),
        NoteRef(79, 0.84, 0.95),
        NoteRef(81, 1.06, 1.16),
    ]
    audio, frame_pitch = synth_note_phrase(notes, gain=0.28, release=0.06, noise=0.0008)
    return write_case("staccato_phrase", "notes", audio, notes=notes, frame_pitch_hz=frame_pitch)


def build_poly_case() -> BenchmarkCase:
    chords = [
        ChordRef("Cmaj", 0.0, 0.6),
        ChordRef("Amin", 0.6, 1.2),
        ChordRef("Gmaj", 1.2, 1.8),
        ChordRef("A#maj", 1.8, 2.4),
    ]
    mapping = {
        "Cmaj": [60, 64, 67],
        "Amin": [57, 60, 64],
        "Gmaj": [55, 59, 62],
        "A#maj": [58, 62, 65],
    }
    total = int(SR * chords[-1].end)
    audio = np.zeros(total, dtype=np.float32)
    t = np.arange(total) / SR
    for chord in chords:
        start = int(chord.start * SR)
        end = int(chord.end * SR)
        seg_t = t[: end - start]
        chord_wave = np.zeros(end - start, dtype=np.float32)
        for pitch in mapping[chord.label]:
            hz = midi_to_hz(pitch)
            chord_wave += np.sin(2 * np.pi * hz * seg_t).astype(np.float32)
        env = np.linspace(1.0, 0.45, end - start, dtype=np.float32)
        audio[start:end] += 0.22 * (chord_wave / max(len(mapping[chord.label]), 1)) * env
    return write_case("polyphonic_progression", "chords", np.clip(audio, -1.0, 1.0), chords=chords)


def build_drum_case() -> BenchmarkCase:
    duration = 3.0
    total = int(SR * duration)
    audio = np.zeros(total, dtype=np.float32)
    drums: list[DrumRef] = []
    kick_times = [0.0, 0.75, 1.5, 2.25]
    snare_times = [0.38, 1.12, 1.88, 2.62]
    hat_times = np.arange(0.0, duration, 0.25)
    rng = np.random.default_rng(14)

    for hit in kick_times:
        start = int(hit * SR)
        size = int(0.09 * SR)
        t = np.arange(size) / SR
        wave = np.sin(2 * np.pi * 58.0 * t) * np.exp(-28 * t)
        audio[start : start + size] += 0.95 * wave.astype(np.float32)
        drums.append(DrumRef("kick", hit, hit + 0.11))

    for hit in snare_times:
        start = int(hit * SR)
        size = int(0.07 * SR)
        noise = rng.normal(0.0, 1.0, size).astype(np.float32) * np.hanning(size).astype(np.float32)
        audio[start : start + size] += 0.42 * noise
        drums.append(DrumRef("snare", hit, hit + 0.11))

    for hit in hat_times:
        start = int(hit * SR)
        size = int(0.03 * SR)
        noise = rng.normal(0.0, 1.0, size).astype(np.float32) * np.hanning(size).astype(np.float32)
        audio[start : start + size] += 0.18 * noise
        drums.append(DrumRef("hihat_closed", float(hit), float(hit + 0.08)))

    drums.sort(key=lambda event: event.start)
    return write_case("drum_percussive_input", "drums", np.clip(audio, -1.0, 1.0), drums=drums)


def build_silence_case() -> BenchmarkCase:
    duration = 2.0
    total = int(SR * duration)
    t = np.arange(total) / SR
    rng = np.random.default_rng(23)
    air = 0.0006 * np.sin(2 * np.pi * 92.0 * t)
    hiss = rng.normal(0.0, 0.00025, size=total)
    audio = (air + hiss).astype(np.float32)
    return write_case("silence_background_noise_only", "silence", audio)


def build_long_form_case() -> BenchmarkCase:
    phrase = build_clean_melody_case()
    audio, sr = sf.read(phrase.path, dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    repeats = 14
    merged = np.tile(audio, repeats)
    notes: list[NoteRef] = []
    phrase_duration = audio.shape[0] / sr
    for idx in range(repeats):
        offset = idx * phrase_duration
        for note in phrase.notes:
            notes.append(NoteRef(note.pitch, note.start + offset, note.end + offset))
    frame_pitch = np.tile(phrase.frame_pitch_hz, repeats) if phrase.frame_pitch_hz is not None else None
    return write_case("long_form_audio", "notes", merged.astype(np.float32), notes=notes, frame_pitch_hz=frame_pitch)


def build_controller_case() -> BenchmarkCase:
    duration = 2.6
    total = int(SR * duration)
    t = np.arange(total) / SR
    active_mask = ((t >= 0.25) & (t <= 1.45)) | ((t >= 1.72) & (t <= 2.38))
    envelope = np.where(
        active_mask,
        0.18 + 0.08 * np.sin(2 * np.pi * 1.4 * t),
        0.0,
    )
    pitch_midi = np.where(
        t < 1.55,
        57.0 + 0.14 * np.sin(2 * np.pi * 5.1 * t),
        60.0 + 0.18 * np.sin(2 * np.pi * 6.2 * t),
    )
    freq = 440.0 * (2.0 ** ((pitch_midi - 69.0) / 12.0))
    phase = 2.0 * np.pi * np.cumsum(freq) / SR
    audio = (envelope * np.sin(phase)).astype(np.float32)
    frame_pitch = samples_to_frame_pitch(freq * active_mask.astype(np.float32))
    return write_case(
        "controller_input_stability",
        "controller",
        audio,
        frame_pitch_hz=frame_pitch,
        controller_windows=[(0.25, 1.45), (1.72, 2.38)],
    )


def discover_smoke_cases(limit: int = 3) -> list[BenchmarkCase]:
    patterns = [
        ROOT / "projects",
    ]
    found: list[BenchmarkCase] = []
    seen: set[Path] = set()
    for base in patterns:
        if not base.exists():
            continue
        candidates = list(base.glob("**/original/*.wav")) + list(base.glob("**/audio/raw.wav"))
        for candidate in sorted(candidates):
            resolved = candidate.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            found.append(
                BenchmarkCase(
                    name=f"smoke_{candidate.stem}_{len(found) + 1}",
                    kind="smoke",
                    path=resolved,
                    notes=[],
                    chords=[],
                    drums=[],
                    smoke_only=True,
                )
            )
            if len(found) >= limit:
                return found
    return found


def write_case(
    name: str,
    kind: str,
    audio: np.ndarray,
    *,
    notes: list[NoteRef] | None = None,
    chords: list[ChordRef] | None = None,
    drums: list[DrumRef] | None = None,
    frame_pitch_hz: np.ndarray | None = None,
    controller_windows: list[tuple[float, float]] | None = None,
) -> BenchmarkCase:
    path = FIXTURE_DIR / f"{name}.wav"
    sf.write(path, np.asarray(audio, dtype=np.float32), SR, subtype="PCM_16")
    return BenchmarkCase(
        name=name,
        kind=kind,
        path=path,
        notes=notes or [],
        chords=chords or [],
        drums=drums or [],
        frame_pitch_hz=frame_pitch_hz,
        controller_windows=controller_windows,
    )


def synth_note_phrase(
    notes: list[NoteRef],
    *,
    gain: float,
    release: float,
    noise: float,
    glide: float = 0.0,
) -> tuple[np.ndarray, np.ndarray]:
    total_seconds = max(note.end for note in notes) + 0.15
    total_samples = int(total_seconds * SR)
    audio = np.zeros(total_samples, dtype=np.float32)
    pitch_trace = np.zeros(total_samples, dtype=np.float32)
    vibrato_t = np.arange(total_samples) / SR
    vibrato = 0.12 * np.sin(2 * np.pi * 5.6 * vibrato_t)

    for idx, note in enumerate(notes):
        start = int(note.start * SR)
        end = int(note.end * SR)
        if end <= start:
            continue
        seg_len = end - start
        t = np.arange(seg_len) / SR
        freq = np.full(seg_len, midi_to_hz(note.pitch), dtype=np.float32)
        if glide > 0.0 and idx > 0:
            prev_pitch = notes[idx - 1].pitch
            glide_len = min(int(glide * SR), seg_len)
            if glide_len > 0:
                freq[:glide_len] = np.linspace(midi_to_hz(prev_pitch), midi_to_hz(note.pitch), glide_len)
        env = np.ones(seg_len, dtype=np.float32)
        attack = max(1, int(0.018 * SR))
        release_len = max(1, min(seg_len, int(release * SR)))
        env[:attack] = np.linspace(0.0, 1.0, attack)
        env[-release_len:] *= np.linspace(1.0, 0.35 if release > 0.16 else 0.08, release_len)
        mod_freq = freq * (2.0 ** (vibrato[start:end] / 12.0))
        phase = 2.0 * np.pi * np.cumsum(mod_freq) / SR
        wave = np.sin(phase) + 0.23 * np.sin(phase * 2.0)
        audio[start:end] += (gain * env * wave).astype(np.float32)
        pitch_trace[start:end] = mod_freq

    if noise > 0.0:
        rng = np.random.default_rng(5)
        audio += rng.normal(0.0, noise, size=audio.size).astype(np.float32)
    audio = np.clip(audio, -1.0, 1.0).astype(np.float32)
    frame_pitch = samples_to_frame_pitch(pitch_trace)
    return audio, frame_pitch


def samples_to_frame_pitch(pitch_trace: np.ndarray) -> np.ndarray:
    frame_count = frame_count_for_samples(pitch_trace.size)
    frame_pitch = np.zeros(frame_count, dtype=np.float32)
    for idx in range(frame_count):
        start = idx * HOP_LENGTH
        stop = min(pitch_trace.size, start + HOP_LENGTH)
        window = pitch_trace[start:stop]
        voiced = window[window > 1e-3]
        if voiced.size:
            frame_pitch[idx] = float(np.median(voiced))
    return frame_pitch


def frame_count_for_samples(sample_count: int) -> int:
    return max(1, int(math.ceil(sample_count / HOP_LENGTH)))


def midi_to_hz(pitch: int) -> float:
    return float(440.0 * (2.0 ** ((pitch - 69) / 12.0)))


def run_case(case: BenchmarkCase) -> dict[str, Any]:
    audio, sr = sf.read(case.path, dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)

    tracemalloc.start()
    wall_start = time.perf_counter()
    cpu_start = time.process_time()

    analysis_audio, enhancement = enhance_for_analysis(audio, sr)
    stems = split_stems(analysis_audio)
    note_events = extract_monophonic_notes(stems["harmonic"], sr)
    chord_events = detect_chords(stems["harmonic"], sr)
    drum_events = transcribe_drums(analysis_audio, sr)
    f0, _, _ = _estimate_pitch(stems["harmonic"], sr, HOP_LENGTH)

    cpu_ms = (time.process_time() - cpu_start) * 1000.0
    wall_ms = (time.perf_counter() - wall_start) * 1000.0
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    metrics: dict[str, Any] = {
        "latency_ms": round(wall_ms, 3),
        "cpu_ms": round(cpu_ms, 3),
        "peak_memory_mb": round(peak / (1024.0 * 1024.0), 3),
        "detected_note_count": len(note_events),
        "detected_chord_count": len(chord_events),
        "detected_drum_count": len(drum_events),
        "analysis_gain": round(float(enhancement["gain"]), 4),
        "analysis_snr_db": round(float(enhancement["snr_db"]), 4),
    }

    if case.kind in {"notes", "silence"}:
        metrics.update(score_note_case(case, note_events, f0))
    if case.kind == "chords":
        metrics.update(score_chord_case(case, chord_events))
    if case.kind == "drums":
        metrics.update(score_drum_case(case, drum_events))
    if case.kind == "controller":
        controller = analyze_controller_input(audio, sr, workflow_mode="live")
        metrics.update(score_controller_case(case, controller))
    if case.kind == "smoke":
        metrics.update(score_smoke_case(audio, note_events, chord_events, drum_events))

    return {
        "name": case.name,
        "kind": case.kind,
        "path": str(case.path),
        "smoke_only": case.smoke_only,
        "metrics": metrics,
    }


def score_note_case(case: BenchmarkCase, predicted: list[dict[str, Any]], f0: np.ndarray) -> dict[str, Any]:
    truth = case.notes
    matched_pairs = match_notes(truth, predicted)
    tp = len(matched_pairs)
    fp = max(len(predicted) - tp, 0)
    fn = max(len(truth) - tp, 0)
    precision = safe_div(tp, tp + fp)
    recall = safe_div(tp, tp + fn)
    f1 = safe_div(2 * precision * recall, precision + recall)

    onset_errors = [abs(pred["start"] - ref.start) for ref, pred in matched_pairs]
    offset_errors = [abs(pred["end"] - ref.end) for ref, pred in matched_pairs]

    metrics: dict[str, Any] = {
        "note_precision": round(precision, 4),
        "note_recall": round(recall, 4),
        "note_f1": round(f1, 4),
        "onset_mae_ms": round(np.mean(onset_errors) * 1000.0, 3) if onset_errors else None,
        "offset_mae_ms": round(np.mean(offset_errors) * 1000.0, 3) if offset_errors else None,
        "false_notes_per_s": round(len(predicted) / max(duration_from_notes(truth), 1e-6), 4) if not truth else 0.0,
    }

    if case.frame_pitch_hz is not None:
        metrics.update(score_pitch_frames(case.frame_pitch_hz, f0))
    else:
        metrics["median_abs_cents"] = None
        metrics["octave_error_rate"] = None

    if case.kind == "silence":
        metrics["noise_false_notes_per_s"] = round(len(predicted) / 2.0, 4)
        metrics["note_f1"] = 1.0 if not predicted else 0.0
        metrics["note_precision"] = 1.0 if not predicted else 0.0
        metrics["note_recall"] = 1.0
    else:
        metrics["noise_false_notes_per_s"] = 0.0
    return metrics


def score_pitch_frames(reference_hz: np.ndarray, estimated_hz: np.ndarray) -> dict[str, Any]:
    frame_count = min(reference_hz.size, estimated_hz.size)
    ref = reference_hz[:frame_count]
    est = estimated_hz[:frame_count]
    valid_mask = (ref > 1e-3) & np.isfinite(est) & (est > 1e-3)
    if not np.any(valid_mask):
        return {"median_abs_cents": None, "octave_error_rate": 1.0, "voiced_frame_recall": 0.0}
    cents = 1200.0 * np.log2(est[valid_mask] / ref[valid_mask])
    voiced_ref = ref > 1e-3
    voiced_est = np.isfinite(est) & (est > 1e-3)
    return {
        "median_abs_cents": round(float(np.median(np.abs(cents))), 3),
        "octave_error_rate": round(float(np.mean(np.abs(cents) >= 600.0)), 4),
        "voiced_frame_recall": round(float(np.mean(voiced_est[voiced_ref])), 4) if np.any(voiced_ref) else 1.0,
    }


def score_chord_case(case: BenchmarkCase, predicted: list[dict[str, Any]]) -> dict[str, Any]:
    truth = case.chords
    matched = 0
    labels = []
    for ref in truth:
        best = best_overlap_event(ref.start, ref.end, predicted)
        labels.append(best.get("label") if best else None)
        if best and best.get("label") == ref.label:
            matched += 1
    return {
        "chord_accuracy": round(safe_div(matched, len(truth)), 4),
        "predicted_labels": [event.get("label") for event in predicted],
        "reference_labels": [ref.label for ref in truth],
        "aligned_labels": labels,
    }


def score_drum_case(case: BenchmarkCase, predicted: list[dict[str, Any]]) -> dict[str, Any]:
    truth = case.drums
    matched_truth: set[int] = set()
    matched_pred: set[int] = set()
    for pred_idx, event in enumerate(predicted):
        for truth_idx, ref in enumerate(truth):
            if truth_idx in matched_truth:
                continue
            if abs(event["start"] - ref.start) > 0.08:
                continue
            event_label = str(event.get("class", ""))
            if event_label != ref.label and not event_label.startswith(ref.label):
                continue
            matched_truth.add(truth_idx)
            matched_pred.add(pred_idx)
            break
    tp = len(matched_truth)
    fp = len(predicted) - len(matched_pred)
    fn = len(truth) - len(matched_truth)
    precision = safe_div(tp, tp + fp)
    recall = safe_div(tp, tp + fn)
    f1 = safe_div(2 * precision * recall, precision + recall)
    return {
        "drum_precision": round(precision, 4),
        "drum_recall": round(recall, 4),
        "drum_f1": round(f1, 4),
        "predicted_classes": [event.get("class") for event in predicted],
    }


def score_smoke_case(
    audio: np.ndarray,
    note_events: list[dict[str, Any]],
    chord_events: list[dict[str, Any]],
    drum_events: list[dict[str, Any]],
) -> dict[str, Any]:
    duration = audio.size / SR
    return {
        "duration_s": round(duration, 3),
        "note_density_per_s": round(len(note_events) / max(duration, 1e-6), 4),
        "chord_density_per_s": round(len(chord_events) / max(duration, 1e-6), 4),
        "drum_density_per_s": round(len(drum_events) / max(duration, 1e-6), 4),
    }


def score_controller_case(case: BenchmarkCase, controller: dict[str, Any]) -> dict[str, Any]:
    frames = controller.get("frames", [])
    events = controller.get("events", {})
    note_windows = events.get("notes", [])
    loudness = np.array([float(frame.get("loudness", 0.0)) for frame in frames], dtype=float)
    voiced = np.array([1.0 if frame.get("voiced") else 0.0 for frame in frames], dtype=float)
    times = np.array([float(frame.get("time", 0.0)) for frame in frames], dtype=float)
    expected_windows = case.controller_windows or []

    accidental = max(len(note_windows) - len(expected_windows), 0)
    active_ratio_truth = sum(end - start for start, end in expected_windows) / max(times[-1] if times.size else 1.0, 1e-6)
    active_ratio_pred = float(np.mean(voiced)) if voiced.size else 0.0
    jitter = float(np.mean(np.abs(np.diff(loudness)))) if loudness.size >= 2 else 0.0

    matched_windows = 0
    for expected_start, expected_end in expected_windows:
        for note in note_windows:
            if abs(float(note["start"]) - expected_start) <= 0.12 and abs(float(note["end"]) - expected_end) <= 0.18:
                matched_windows += 1
                break

    return {
        "controller_window_recall": round(safe_div(matched_windows, len(expected_windows)), 4),
        "controller_accidental_triggers": accidental,
        "controller_active_ratio_error": round(abs(active_ratio_pred - active_ratio_truth), 4),
        "controller_jitter": round(jitter, 4),
        "controller_cc_count": len(events.get("cc", [])),
    }


def match_notes(truth: list[NoteRef], predicted: list[dict[str, Any]]) -> list[tuple[NoteRef, dict[str, Any]]]:
    matched: list[tuple[NoteRef, dict[str, Any]]] = []
    used_pred: set[int] = set()
    for ref in truth:
        best_idx = None
        best_score = None
        for pred_idx, event in enumerate(predicted):
            if pred_idx in used_pred:
                continue
            if abs(int(event["pitch"]) - ref.pitch) > 1:
                continue
            onset_error = abs(float(event["start"]) - ref.start)
            offset_error = abs(float(event["end"]) - ref.end)
            if onset_error > 0.12 or offset_error > 0.24:
                continue
            score = onset_error + offset_error
            if best_score is None or score < best_score:
                best_idx = pred_idx
                best_score = score
        if best_idx is None:
            continue
        used_pred.add(best_idx)
        matched.append((ref, predicted[best_idx]))
    return matched


def best_overlap_event(start: float, end: float, predicted: list[dict[str, Any]]) -> dict[str, Any] | None:
    best = None
    best_overlap = 0.0
    for event in predicted:
        overlap = max(0.0, min(float(event["end"]), end) - max(float(event["start"]), start))
        if overlap > best_overlap:
            best = event
            best_overlap = overlap
    return best


def duration_from_notes(notes: list[NoteRef]) -> float:
    if not notes:
        return 0.0
    return max(note.end for note in notes)


def safe_div(num: float, den: float) -> float:
    return float(num / den) if den else 0.0


def summarize_results(results: list[dict[str, Any]]) -> dict[str, float]:
    return {
        "note_f1_mean": rounded_mean(results, "note_f1"),
        "median_abs_cents_mean": rounded_mean(results, "median_abs_cents"),
        "octave_error_rate_mean": rounded_mean(results, "octave_error_rate"),
        "chord_accuracy_mean": rounded_mean(results, "chord_accuracy"),
        "drum_f1_mean": rounded_mean(results, "drum_f1"),
        "noise_false_notes_per_s_mean": rounded_mean(results, "noise_false_notes_per_s"),
        "controller_jitter_mean": rounded_mean(results, "controller_jitter"),
        "controller_trigger_recall_mean": rounded_mean(results, "controller_window_recall"),
        "latency_ms_mean": rounded_mean(results, "latency_ms"),
        "peak_memory_mb_mean": rounded_mean(results, "peak_memory_mb"),
    }


def rounded_mean(results: list[dict[str, Any]], key: str) -> float:
    values = []
    for result in results:
        value = result["metrics"].get(key)
        if value is None:
            continue
        values.append(float(value))
    return round(float(np.mean(values)), 4) if values else 0.0


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Benchmark Report",
        "",
        f"Generated: {payload['generated_at']}",
        "",
        "## Aggregate",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
    ]
    for key, value in payload["aggregate"].items():
        lines.append(f"| {key} | {value} |")
    lines.extend(["", "## Cases", "", "| Case | Kind | Latency ms | Note F1 | Chord Acc | Drum F1 | Median cents |", "| --- | --- | ---: | ---: | ---: | ---: | ---: |"])
    for result in payload["cases"]:
        metrics = result["metrics"]
        lines.append(
            "| "
            + " | ".join(
                [
                    result["name"],
                    result["kind"],
                    str(metrics.get("latency_ms", "")),
                    str(metrics.get("note_f1", "")),
                    str(metrics.get("chord_accuracy", "")),
                    str(metrics.get("drum_f1", "")),
                    str(metrics.get("median_abs_cents", "")),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
