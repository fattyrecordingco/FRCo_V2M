"""Music theory helpers for key handling and chord construction."""

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

MAJOR_INTERVALS = (0, 2, 4, 5, 7, 9, 11)
MINOR_INTERVALS = (0, 2, 3, 5, 7, 8, 10)
SUPPORTED_MODES = {"major", "minor"}


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
    """Parse a key string, e.g. 'C major' or 'A minor'."""
    parts = key.strip().split()
    if not parts:
        raise ValueError("Key cannot be empty.")

    if len(parts) == 1:
        tonic = _normalize_tonic(parts[0])
        mode = "major"
    else:
        tonic = _normalize_tonic("".join(parts[:-1]))
        mode = parts[-1].lower()

    if mode not in SUPPORTED_MODES:
        raise ValueError(f"Unsupported mode: {mode!r}. Use 'major' or 'minor'.")
    return tonic, mode


def note_to_midi(note: str, octave: int) -> int:
    """Convert note name and octave to a MIDI pitch number."""
    semitone = NOTE_TO_SEMITONE[note]
    return (octave + 1) * 12 + semitone


def build_scale_pitches(key: str, base_octave: int = 4) -> list[int]:
    """Build the seven scale tones for a key at a given octave."""
    tonic, mode = parse_key(key)
    root_pitch = note_to_midi(tonic, base_octave)
    intervals = MAJOR_INTERVALS if mode == "major" else MINOR_INTERVALS
    return [root_pitch + interval for interval in intervals]


def _degree_pitch(scale: list[int], degree_index: int) -> int:
    scale_len = len(scale)
    octaves, idx = divmod(degree_index, scale_len)
    return scale[idx] + (12 * octaves)


def triad_for_degree(scale: list[int], degree: int) -> list[int]:
    """Return root-position triad pitches for the 1-7 scale degree."""
    if not 1 <= degree <= 7:
        raise ValueError("Degree must be between 1 and 7.")
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
