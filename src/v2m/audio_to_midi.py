"""Audio-to-MIDI prototype pipeline for humming and beatbox ideas."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import json
from pathlib import Path
import shutil
import re

import librosa
import numpy as np
import soundfile as sf

from .generator import NoteEvent
from .midi_export import export_tracks_to_midi
from .music_theory import infer_best_key, parse_key, snap_pitch_to_scale
from .recipe import RecipeContext, build_recipe_markdown


@dataclass(frozen=True)
class PrototypeProjectResult:
    project_dir: Path
    raw_audio_path: Path
    cleaned_audio_path: Path
    melody_midi_path: Path
    drums_midi_path: Path
    combined_midi_path: Path
    analysis_path: Path
    recipe_path: Path
    detected_key: str
    tempo_bpm: int
    time_signature: str
    melody_event_count: int
    drum_event_count: int


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return normalized or "session"


def _make_project_dir(base_dir: Path, project_name: str | None) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    suffix = _slugify(project_name) if project_name else "audio-idea"
    project_dir = base_dir / f"{timestamp}-{suffix}"
    (project_dir / "audio").mkdir(parents=True, exist_ok=True)
    (project_dir / "midi").mkdir(parents=True, exist_ok=True)
    return project_dir


def _noise_reduce(y: np.ndarray) -> np.ndarray:
    if y.size == 0:
        return y
    abs_y = np.abs(y)
    floor = float(np.percentile(abs_y, 20))
    threshold = floor * 1.2
    reduced = y.copy()
    mask = abs_y < threshold
    reduced[mask] *= 0.7
    return librosa.util.normalize(reduced)


def _quantize_beat(beat_pos: float, grid: float, strength: float) -> float:
    snapped = round(beat_pos / grid) * grid
    return beat_pos + (snapped - beat_pos) * strength


def _extract_melody_events(
    harmonic: np.ndarray,
    *,
    sr: int,
    bpm: int,
    quantize_strength: float,
) -> list[NoteEvent]:
    hop_length = 256
    f0, voiced_flag, _ = librosa.pyin(
        harmonic,
        sr=sr,
        fmin=librosa.note_to_hz("C2"),
        fmax=librosa.note_to_hz("C7"),
        hop_length=hop_length,
    )

    if f0 is None or voiced_flag is None:
        return []

    times = librosa.times_like(f0, sr=sr, hop_length=hop_length)
    events: list[NoteEvent] = []
    start_index: int | None = None
    pitch_buffer: list[float] = []

    def flush_segment(end_index: int) -> None:
        nonlocal start_index, pitch_buffer
        if start_index is None or not pitch_buffer:
            start_index = None
            pitch_buffer = []
            return

        start_time = float(times[start_index])
        end_time = float(times[min(end_index, len(times) - 1)])
        if end_time - start_time < 0.06:
            start_index = None
            pitch_buffer = []
            return

        midi_pitch = int(round(float(np.median(pitch_buffer))))
        start_beat = _quantize_beat(start_time * bpm / 60.0, grid=0.25, strength=quantize_strength)
        end_beat = _quantize_beat(end_time * bpm / 60.0, grid=0.25, strength=quantize_strength)
        duration = max(0.125, end_beat - start_beat)
        events.append(
            NoteEvent(
                start_beat=max(0.0, start_beat),
                duration_beats=duration,
                pitch=max(0, min(127, midi_pitch)),
                velocity=88,
                channel=0,
            )
        )
        start_index = None
        pitch_buffer = []

    for idx, hz_value in enumerate(f0):
        voiced = bool(voiced_flag[idx]) if idx < len(voiced_flag) else False
        if voiced and not np.isnan(hz_value):
            midi = float(librosa.hz_to_midi(hz_value))
            if start_index is None:
                start_index = idx
                pitch_buffer = [midi]
            else:
                running = float(np.median(pitch_buffer[-4:]))
                if abs(midi - running) > 2.8:
                    flush_segment(idx - 1)
                    start_index = idx
                    pitch_buffer = [midi]
                else:
                    pitch_buffer.append(midi)
        elif start_index is not None:
            flush_segment(idx - 1)

    if start_index is not None:
        flush_segment(len(f0) - 1)

    return events


def _fallback_melody_events(
    harmonic: np.ndarray,
    *,
    sr: int,
    bpm: int,
    quantize_strength: float,
) -> list[NoteEvent]:
    hop_length = 256
    f0 = librosa.yin(
        harmonic,
        sr=sr,
        fmin=librosa.note_to_hz("C2"),
        fmax=librosa.note_to_hz("C7"),
        hop_length=hop_length,
    )
    rms = librosa.feature.rms(y=harmonic, hop_length=hop_length)[0]
    times = librosa.times_like(f0, sr=sr, hop_length=hop_length)
    energy_threshold = float(np.percentile(rms, 55))

    events: list[NoteEvent] = []
    start: int | None = None

    def flush(end_idx: int) -> None:
        nonlocal start
        if start is None:
            return
        start_time = float(times[start])
        end_time = float(times[min(end_idx, len(times) - 1)])
        if end_time - start_time < 0.08:
            start = None
            return
        hz = float(np.median(f0[start:end_idx + 1]))
        note = int(round(float(librosa.hz_to_midi(hz))))
        start_beat = _quantize_beat(start_time * bpm / 60.0, grid=0.25, strength=quantize_strength)
        end_beat = _quantize_beat(end_time * bpm / 60.0, grid=0.25, strength=quantize_strength)
        events.append(
            NoteEvent(
                start_beat=max(0.0, start_beat),
                duration_beats=max(0.125, end_beat - start_beat),
                pitch=max(0, min(127, note)),
                velocity=82,
                channel=0,
            )
        )
        start = None

    for i in range(min(len(f0), len(rms))):
        active = not np.isnan(f0[i]) and float(rms[i]) >= energy_threshold
        if active and start is None:
            start = i
        if not active and start is not None:
            flush(i - 1)
    if start is not None:
        flush(min(len(f0), len(rms)) - 1)

    return events


def _classify_drum(snippet: np.ndarray, sr: int) -> tuple[int, float]:
    if snippet.size == 0:
        return 42, 0.125
    windowed = snippet * np.hanning(snippet.size)
    spectrum = np.abs(np.fft.rfft(windowed))
    if not np.any(spectrum):
        return 42, 0.125

    freqs = np.fft.rfftfreq(windowed.size, d=1.0 / sr)
    low_ratio = float(np.sum(spectrum[freqs < 180]) / (np.sum(spectrum) + 1e-9))
    centroid = float(np.sum(freqs * spectrum) / (np.sum(spectrum) + 1e-9))

    if low_ratio > 0.47:
        return 36, 0.5  # kick
    if centroid < 2200:
        return 38, 0.25  # snare
    return 42, 0.125  # hi-hat


def _extract_drum_events(
    percussive: np.ndarray,
    *,
    sr: int,
    bpm: int,
    quantize_strength: float,
) -> list[NoteEvent]:
    hop_length = 256
    onset_frames = librosa.onset.onset_detect(
        y=percussive,
        sr=sr,
        hop_length=hop_length,
        units="frames",
        pre_max=8,
        post_max=8,
        pre_avg=8,
        post_avg=8,
        delta=0.08,
        wait=2,
    )

    events: list[NoteEvent] = []
    event_map: dict[tuple[float, int], NoteEvent] = {}
    sample_count = percussive.shape[0]

    for frame in onset_frames:
        time_sec = float(librosa.frames_to_time(frame, sr=sr, hop_length=hop_length))
        beat_pos = _quantize_beat(time_sec * bpm / 60.0, grid=0.25, strength=quantize_strength)
        center = int(time_sec * sr)
        start = max(0, center - int(0.03 * sr))
        end = min(sample_count, center + int(0.05 * sr))
        snippet = percussive[start:end]

        note, duration = _classify_drum(snippet, sr)
        rms = float(np.sqrt(np.mean(np.square(snippet)))) if snippet.size else 0.0
        velocity = int(max(40, min(122, 40 + rms * 900)))
        event = NoteEvent(
            start_beat=max(0.0, beat_pos),
            duration_beats=duration,
            pitch=note,
            velocity=velocity,
            channel=9,
        )
        key = (event.start_beat, event.pitch)
        previous = event_map.get(key)
        if previous is None or event.velocity > previous.velocity:
            event_map[key] = event

    events.extend(sorted(event_map.values(), key=lambda e: (e.start_beat, e.pitch)))
    return events


def _suggest_progression(key: str, genre_tags: list[str]) -> str:
    _, mode = parse_key(key)
    genres = {tag.strip().lower() for tag in genre_tags if tag.strip()}
    if "trap" in genres:
        return "i - bVII - bVI - bVI"
    if "lofi" in genres:
        return "ii - V - I - vi (with 7th chord color tones)"
    if "edm" in genres:
        return "I - V - vi - IV (8-bar energy lift)"
    if "cinematic" in genres:
        return "i - VI - III - VII (or pedal-point variations)"
    if "minor" in mode:
        return "i - VI - III - VII"
    return "I - V - vi - IV"


def _tempo_to_int(raw_tempo: object) -> int:
    arr = np.asarray(raw_tempo, dtype=float).flatten()
    if arr.size == 0:
        return 120
    tempo = float(arr[0])
    return int(round(tempo)) if tempo > 0 else 120


def _resolve_key(scale_mode: str, manual_key: str, melody_events: list[NoteEvent]) -> tuple[str, float]:
    if scale_mode == "manual":
        return manual_key, 1.0
    pitches = [event.pitch for event in melody_events]
    inferred_key, score = infer_best_key(pitches)
    if score < 0.30:
        return manual_key, score
    return inferred_key, score


def _snap_melody_to_key(melody_events: list[NoteEvent], key: str) -> list[NoteEvent]:
    snapped: list[NoteEvent] = []
    for event in melody_events:
        snapped.append(
            NoteEvent(
                start_beat=event.start_beat,
                duration_beats=event.duration_beats,
                pitch=snap_pitch_to_scale(event.pitch, key),
                velocity=event.velocity,
                channel=event.channel,
            )
        )
    return snapped


def analyze_audio_to_project(
    *,
    input_audio_path: str | Path,
    projects_dir: str | Path = "projects",
    project_name: str | None = None,
    scale_mode: str = "auto",
    manual_key: str = "C major",
    genre_tags: list[str] | None = None,
    quantize_strength: float = 0.90,
) -> PrototypeProjectResult:
    """Run end-to-end analysis and export a local project artifact package."""
    if scale_mode not in {"auto", "manual"}:
        raise ValueError("scale_mode must be either 'auto' or 'manual'.")
    if not 0.0 <= quantize_strength <= 1.0:
        raise ValueError("quantize_strength must be within [0.0, 1.0].")

    input_path = Path(input_audio_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Input audio not found: {input_path}")

    genres = genre_tags or []
    base_dir = Path(projects_dir)
    project_dir = _make_project_dir(base_dir, project_name)

    y, sr = librosa.load(input_path, sr=22050, mono=True)
    cleaned = _noise_reduce(y)
    harmonic, percussive = librosa.effects.hpss(cleaned)

    tempo_raw, _ = librosa.beat.beat_track(y=cleaned, sr=sr)
    tempo_bpm = _tempo_to_int(tempo_raw)
    time_signature = "4/4"

    melody_events = _extract_melody_events(
        harmonic, sr=sr, bpm=tempo_bpm, quantize_strength=quantize_strength
    )
    if len(melody_events) < 4:
        melody_events = _fallback_melody_events(
            harmonic, sr=sr, bpm=tempo_bpm, quantize_strength=quantize_strength
        )
    resolved_key, key_confidence = _resolve_key(scale_mode, manual_key, melody_events)
    melody_events = _snap_melody_to_key(melody_events, resolved_key)

    drum_events = _extract_drum_events(
        percussive, sr=sr, bpm=tempo_bpm, quantize_strength=quantize_strength
    )

    raw_path = project_dir / "audio" / f"raw{input_path.suffix.lower() or '.wav'}"
    cleaned_path = project_dir / "audio" / "cleaned.wav"
    shutil.copy2(input_path, raw_path)
    sf.write(cleaned_path, cleaned, sr)

    melody_midi = project_dir / "midi" / "melody.mid"
    drums_midi = project_dir / "midi" / "drums.mid"
    combined_midi = project_dir / "midi" / "combined.mid"
    export_tracks_to_midi(bpm=tempo_bpm, output_path=melody_midi, track_specs=[("Melody", melody_events)])
    export_tracks_to_midi(bpm=tempo_bpm, output_path=drums_midi, track_specs=[("Drums", drum_events)])
    export_tracks_to_midi(
        bpm=tempo_bpm,
        output_path=combined_midi,
        track_specs=[("Melody", melody_events), ("Drums", drum_events)],
    )

    progression = _suggest_progression(resolved_key, genres)
    recipe = build_recipe_markdown(
        RecipeContext(
            project_name=project_dir.name,
            tempo_bpm=tempo_bpm,
            time_signature=time_signature,
            key=resolved_key,
            scale_mode=scale_mode,
            genre_tags=genres,
            melody_events=len(melody_events),
            drum_events=len(drum_events),
            chord_recommendation=progression,
        )
    )
    recipe_path = project_dir / "recipe.md"
    recipe_path.write_text(recipe, encoding="utf-8")

    analysis_payload = {
        "project_name": project_dir.name,
        "input_audio": str(raw_path),
        "cleaned_audio": str(cleaned_path),
        "tempo_bpm": tempo_bpm,
        "time_signature_estimate": time_signature,
        "detected_key": resolved_key,
        "key_confidence": round(float(key_confidence), 3),
        "scale_mode": scale_mode,
        "genre_tags": genres,
        "melody_event_count": len(melody_events),
        "drum_event_count": len(drum_events),
        "duration_seconds": round(float(len(cleaned) / sr), 3),
        "midi_outputs": {
            "melody": str(melody_midi),
            "drums": str(drums_midi),
            "combined": str(combined_midi),
        },
        "recipe_path": str(recipe_path),
        "preview_events": {
            "melody": [asdict(event) for event in melody_events[:20]],
            "drums": [asdict(event) for event in drum_events[:40]],
        },
    }
    analysis_path = project_dir / "analysis.json"
    analysis_path.write_text(json.dumps(analysis_payload, indent=2), encoding="utf-8")

    return PrototypeProjectResult(
        project_dir=project_dir,
        raw_audio_path=raw_path,
        cleaned_audio_path=cleaned_path,
        melody_midi_path=melody_midi,
        drums_midi_path=drums_midi,
        combined_midi_path=combined_midi,
        analysis_path=analysis_path,
        recipe_path=recipe_path,
        detected_key=resolved_key,
        tempo_bpm=tempo_bpm,
        time_signature=time_signature,
        melody_event_count=len(melody_events),
        drum_event_count=len(drum_events),
    )
