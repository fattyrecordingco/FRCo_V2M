"""Rule-based musical suggestions derived from analysis output."""

from __future__ import annotations

from typing import Any

import numpy as np


def build_musical_suggestions(
    summary: dict[str, Any],
    note_events: list[dict[str, Any]],
    chord_events: list[dict[str, Any]],
    drum_events: list[dict[str, Any]],
) -> dict[str, Any]:
    role = infer_role(note_events, chord_events, drum_events)
    note_lengths = [float(note["end"]) - float(note["start"]) for note in note_events]
    mean_length = float(np.mean(note_lengths)) if note_lengths else 0.0
    pitch_values = [int(note["pitch"]) for note in note_events if "pitch" in note]
    median_pitch = float(np.median(pitch_values)) if pitch_values else 60.0
    rhythmic_density = len(note_events) + len(drum_events)

    production: list[dict[str, str]] = []
    sound_design: list[dict[str, str]] = []
    arrangement: list[dict[str, str]] = []

    if role == "bassline":
        arrangement.append(
            {
                "title": "Lock With Kick",
                "reason": "The detected line sits in a low register and will read best when doubled or side-chained to the kick.",
            }
        )
        sound_design.append(
            {
                "title": "Rounded Mono Bass",
                "reason": "A filtered mono synth or picked electric bass will suit the detected range and contour.",
            }
        )
    elif role == "melody":
        arrangement.append(
            {
                "title": "Layer A Counterline",
                "reason": "The phrase is clearly monophonic, so a simple third-above or call-and-response layer should stay readable.",
            }
        )
        sound_design.append(
            {
                "title": "Lead Patch With Glide",
                "reason": "The detected contour includes expressive motion that will translate well on a legato lead or vocal-style synth.",
            }
        )
    elif role == "pad_chords":
        arrangement.append(
            {
                "title": "Add Bass Foundation",
                "reason": "The input behaves harmonically. A root-following bassline will make the progression feel finished faster.",
            }
        )
        sound_design.append(
            {
                "title": "Wide Pad Or Piano Stack",
                "reason": "Chord density is stable enough for layered pad, keys, or soft guitar voicings.",
            }
        )
    elif role == "groove":
        production.append(
            {
                "title": "Tighten Transients",
                "reason": "The input looks percussive. Shortening attack tails and adding parallel compression should improve punch.",
            }
        )

    if mean_length > 0.45:
        production.append(
            {
                "title": "Preserve Feel",
                "reason": "Long connected notes suggest a legato performance. Use light quantization and keep pitch bends enabled.",
            }
        )
    elif note_events:
        production.append(
            {
                "title": "Tighten Grid",
                "reason": "Short detached notes can usually take stronger timing correction without sounding robotic.",
            }
        )

    if summary.get("scale") == "minor":
        sound_design.append(
            {
                "title": "Dark Harmonic Support",
                "reason": "The detected minor context points toward lower-mid pads, plucks, or filtered guitars.",
            }
        )

    if rhythmic_density >= 18:
        arrangement.append(
            {
                "title": "Leave Space For Topline",
                "reason": "The current take is already dense. Keep the counterline sparse or use call-and-response phrasing.",
            }
        )

    return {
        "role": role,
        "harmonic_role": "progression" if chord_events else "single_line",
        "production": production[:3],
        "sound_design": sound_design[:3],
        "arrangement": arrangement[:3],
        "explanation": {
            "median_pitch": median_pitch,
            "mean_note_length": mean_length,
            "note_count": len(note_events),
            "chord_count": len(chord_events),
            "drum_count": len(drum_events),
        },
    }


def infer_role(
    note_events: list[dict[str, Any]],
    chord_events: list[dict[str, Any]],
    drum_events: list[dict[str, Any]],
) -> str:
    if drum_events and len(drum_events) >= max(10, len(note_events) * 2):
        return "groove"
    if chord_events and len(chord_events) >= max(2, len(note_events) // 3):
        return "pad_chords"
    if not note_events:
        return "texture"
    median_pitch = float(np.median([int(note["pitch"]) for note in note_events]))
    if median_pitch < 55:
        return "bassline"
    return "melody"
