"""Idea generation engine for chords and melody events."""

from __future__ import annotations

from dataclasses import dataclass
import random

from .music_theory import build_scale_pitches, clamp_midi_pitch, repeat_to_length, triad_for_degree

BARS_TO_BEATS = 4

STYLE_PRESETS: dict[str, dict[str, object]] = {
    "pop": {
        "progressions": ([1, 5, 6, 4], [1, 6, 4, 5], [6, 4, 1, 5]),
        "melody_bias_chord_tone": 0.65,
        "velocity_range": (72, 98),
    },
    "trap": {
        "progressions": ([1, 7, 6, 6], [6, 5, 1, 7], [1, 6, 7, 5]),
        "melody_bias_chord_tone": 0.72,
        "velocity_range": (68, 110),
    },
    "lofi": {
        "progressions": ([2, 5, 1, 6], [1, 3, 6, 4], [4, 5, 3, 6]),
        "melody_bias_chord_tone": 0.70,
        "velocity_range": (58, 85),
    },
    "edm": {
        "progressions": ([1, 5, 6, 4], [1, 4, 6, 5], [6, 5, 4, 5]),
        "melody_bias_chord_tone": 0.55,
        "velocity_range": (78, 112),
    },
    "cinematic": {
        "progressions": ([1, 6, 3, 7], [1, 4, 6, 5], [6, 3, 4, 5]),
        "melody_bias_chord_tone": 0.60,
        "velocity_range": (64, 96),
    },
}


@dataclass(frozen=True)
class NoteEvent:
    start_beat: float
    duration_beats: float
    pitch: int
    velocity: int
    channel: int


@dataclass(frozen=True)
class GeneratedIdea:
    style: str
    key: str
    bpm: int
    bars: int
    chords: list[NoteEvent]
    melody: list[NoteEvent]


def _validate(style: str, bpm: int, bars: int, complexity: int) -> None:
    if style not in STYLE_PRESETS:
        supported = ", ".join(sorted(STYLE_PRESETS))
        raise ValueError(f"Unsupported style {style!r}. Choose one of: {supported}.")
    if bpm < 50 or bpm > 220:
        raise ValueError("BPM must be between 50 and 220.")
    if bars < 1 or bars > 64:
        raise ValueError("Bars must be between 1 and 64.")
    if complexity < 1 or complexity > 10:
        raise ValueError("Complexity must be between 1 and 10.")


def _events_per_bar(complexity: int) -> int:
    if complexity <= 3:
        return 2
    if complexity <= 7:
        return 4
    return 8


def generate_idea(
    *,
    style: str = "pop",
    key: str = "C major",
    bpm: int = 120,
    bars: int = 8,
    complexity: int = 5,
    seed: int | None = None,
) -> GeneratedIdea:
    """Generate a deterministic (if seeded) musical idea."""
    _validate(style=style, bpm=bpm, bars=bars, complexity=complexity)
    rng = random.Random(seed)

    preset = STYLE_PRESETS[style]
    progression_base = list(rng.choice(preset["progressions"]))  # type: ignore[index]
    progression = repeat_to_length(progression_base, bars)
    scale = build_scale_pitches(key=key, base_octave=4)

    velocity_min, velocity_max = preset["velocity_range"]  # type: ignore[index]
    melody_bias_chord_tone = float(preset["melody_bias_chord_tone"])  # type: ignore[index]
    events_per_bar = _events_per_bar(complexity)
    slot_duration = BARS_TO_BEATS / events_per_bar
    rest_probability = max(0.04, 0.22 - (complexity * 0.015))

    chord_events: list[NoteEvent] = []
    melody_events: list[NoteEvent] = []

    for bar in range(bars):
        bar_start = bar * BARS_TO_BEATS
        degree = progression[bar]
        chord = triad_for_degree(scale, degree)

        for pitch in chord:
            chord_events.append(
                NoteEvent(
                    start_beat=bar_start,
                    duration_beats=BARS_TO_BEATS,
                    pitch=clamp_midi_pitch(pitch - 12),
                    velocity=rng.randint(max(45, velocity_min - 15), velocity_max - 8),
                    channel=0,
                )
            )

        melody_pool = scale + [p + 12 for p in scale]
        chord_tones = chord + [p + 12 for p in chord]
        for slot in range(events_per_bar):
            if rng.random() < rest_probability:
                continue

            start_beat = bar_start + (slot * slot_duration)
            duration = slot_duration
            if events_per_bar >= 4 and rng.random() < 0.35:
                duration = slot_duration * 0.5

            pitch_source = chord_tones if rng.random() < melody_bias_chord_tone else melody_pool
            pitch = clamp_midi_pitch(rng.choice(pitch_source), min_pitch=48, max_pitch=90)
            melody_events.append(
                NoteEvent(
                    start_beat=start_beat,
                    duration_beats=duration,
                    pitch=pitch,
                    velocity=rng.randint(velocity_min, velocity_max),
                    channel=1,
                )
            )

    return GeneratedIdea(
        style=style,
        key=key,
        bpm=bpm,
        bars=bars,
        chords=chord_events,
        melody=melody_events,
    )
