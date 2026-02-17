"""Music theory helpers for key handling, scales, and pitch mapping."""

from __future__ import annotations

from typing import Iterable

NOTE_TO_SEMITONE: dict[str, int] = {
    "C": 0,
    "C#": 1,
    "Db": 1,
    "D": 2,
    "D#": 3,
    "Eb": 3,
    "E": 4,
    "F": 5,
    "F#": 6,
    "Gb": 6,
    "G": 7,
    "G#": 8,
    "Ab": 8,
    "A": 9,
    "A#": 10,
    "Bb": 10,
    "B": 11,
}
SEMITONE_TO_NOTE: dict[int, str] = {
    0: "C",
    1: "C#",
    2: "D",
    3: "D#",
    4: "E",
    5: "F",
    6: "F#",
    7: "G",
    8: "G#",
    9: "A",
    10: "A#",
    11: "B",
}

SCALE_INTERVALS: dict[str, tuple[int, ...]] = {
    "major": (0, 2, 4, 5, 7, 9, 11),
    "minor": (0, 2, 3, 5, 7, 8, 10),
    "dorian": (0, 2, 3, 5, 7, 9, 10),
    "phrygian": (0, 1, 3, 5, 7, 8, 10),
    "lydian": (0, 2, 4, 6, 7, 9, 11),
    "mixolydian": (0, 2, 4, 5, 7, 9, 10),
    "locrian": (0, 1, 3, 5, 6, 8, 10),
    "harmonic minor": (0, 2, 3, 5, 7, 8, 11),
    "melodic minor": (0, 2, 3, 5, 7, 9, 11),
    "major pentatonic": (0, 2, 4, 7, 9),
    "minor pentatonic": (0, 3, 5, 7, 10),
    "blues": (0, 3, 5, 6, 7, 10),
    "whole tone": (0, 2, 4, 6, 8, 10),
    "chromatic": (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11),
}
SUPPORTED_MODES = set(SCALE_INTERVALS.keys())


def _normalize_tonic(raw_tonic: str) -> str:
    tonic = raw_tonic.strip().replace("♯", "#").replace("♭", "b")
    if not tonic:
        raise ValueError("Key tonic cannot be empty.")

    letter = tonic[0].upper()
    accidental = tonic[1:]
    if accidental not in {"", "#", "b"}:
        raise ValueError(f"Unsupported tonic format: {raw_tonic!r}.")

    normalized = f"{letter}{accidental}"
    if normalized not in NOTE_TO_SEMITONE:
        raise ValueError(f"Unsupported tonic: {normalized!r}.")
    return normalized


def parse_key(key: str) -> tuple[str, str]:
    """Parse key strings such as 'C major' or 'A harmonic minor'."""
    parts = key.strip().split()
    if not parts:
        raise ValueError("Key cannot be empty.")

    tonic = _normalize_tonic(parts[0])
    mode = "major" if len(parts) == 1 else " ".join(parts[1:]).lower()

    if mode not in SUPPORTED_MODES:
        supported = ", ".join(sorted(SUPPORTED_MODES))
        raise ValueError(f"Unsupported mode: {mode!r}. Supported: {supported}.")
    return tonic, mode


def list_supported_keys() -> list[str]:
    return sorted(SUPPORTED_MODES)


def note_to_midi(note: str, octave: int) -> int:
    semitone = NOTE_TO_SEMITONE[note]
    return (octave + 1) * 12 + semitone


def build_scale_pitches(key: str, base_octave: int = 4) -> list[int]:
    tonic, mode = parse_key(key)
    root_pitch = note_to_midi(tonic, base_octave)
    intervals = SCALE_INTERVALS[mode]
    return [root_pitch + interval for interval in intervals]


def build_scale_pitch_classes(key: str) -> set[int]:
    tonic, mode = parse_key(key)
    root = NOTE_TO_SEMITONE[tonic]
    return {(root + interval) % 12 for interval in SCALE_INTERVALS[mode]}


def snap_pitch_to_scale(pitch: int, key: str) -> int:
    """Snap a MIDI pitch to the nearest in-scale pitch for the given key."""
    pitch_classes = build_scale_pitch_classes(key)
    if pitch % 12 in pitch_classes:
        return pitch

    for distance in range(1, 12):
        up = pitch + distance
        if up % 12 in pitch_classes and up <= 127:
            return up
        down = pitch - distance
        if down % 12 in pitch_classes and down >= 0:
            return down
    return pitch


def infer_best_key(pitches: list[int]) -> tuple[str, float]:
    """
    Infer the best matching key from detected MIDI pitches.
    Returns key string and match score in [0, 1].
    """
    if not pitches:
        return "C major", 0.0

    pitch_classes = [pitch % 12 for pitch in pitches]
    best_key = "C major"
    best_score = -1.0

    for root in range(12):
        for mode, intervals in SCALE_INTERVALS.items():
            allowed = {(root + interval) % 12 for interval in intervals}
            hits = sum(1 for pc in pitch_classes if pc in allowed)
            coverage = hits / len(pitch_classes)
            complexity_penalty = max(0.0, (len(intervals) - 5) * 0.03)
            if mode == "chromatic":
                complexity_penalty += 0.2
            score = coverage - complexity_penalty
            if score > best_score:
                best_score = score
                best_key = f"{SEMITONE_TO_NOTE[root]} {mode}"

    return best_key, max(0.0, min(1.0, best_score))


def _degree_pitch(scale: list[int], degree_index: int) -> int:
    scale_len = len(scale)
    octaves, idx = divmod(degree_index, scale_len)
    return scale[idx] + (12 * octaves)


def triad_for_degree(scale: list[int], degree: int) -> list[int]:
    if not 1 <= degree <= 7:
        raise ValueError("Degree must be between 1 and 7.")
    if len(scale) < 7:
        raise ValueError("Triad generation requires a 7-note scale.")
    index = degree - 1
    return [
        _degree_pitch(scale, index),
        _degree_pitch(scale, index + 2),
        _degree_pitch(scale, index + 4),
    ]


def clamp_midi_pitch(value: int, min_pitch: int = 0, max_pitch: int = 127) -> int:
    return max(min_pitch, min(max_pitch, value))


def repeat_to_length(values: Iterable[int], length: int) -> list[int]:
    values_list = list(values)
    if not values_list:
        raise ValueError("Cannot repeat an empty list.")
    return [values_list[i % len(values_list)] for i in range(length)]
