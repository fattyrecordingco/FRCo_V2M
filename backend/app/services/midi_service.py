"""MIDI export helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pretty_midi


def write_midi_bundle(
    output_dir: Path,
    bpm: float,
    note_events: list[dict[str, Any]],
    chord_events: list[dict[str, Any]],
    drum_events: list[dict[str, Any]],
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    files: dict[str, Path] = {}

    if note_events:
        notes_pm = pretty_midi.PrettyMIDI(initial_tempo=max(30.0, float(bpm)))
        inst = pretty_midi.Instrument(program=0, name="notes")
        for event in note_events:
            inst.notes.append(
                pretty_midi.Note(
                    velocity=int(event.get("velocity", 90)),
                    pitch=int(event["pitch"]),
                    start=float(event["start"]),
                    end=float(event["end"]),
                )
            )
        notes_pm.instruments.append(inst)
        path = output_dir / "notes.mid"
        notes_pm.write(str(path))
        files["notes"] = path

    if chord_events:
        chords_pm = pretty_midi.PrettyMIDI(initial_tempo=max(30.0, float(bpm)))
        inst = pretty_midi.Instrument(program=48, name="chords")
        for event in chord_events:
            for pitch in event["pitches"]:
                inst.notes.append(
                    pretty_midi.Note(
                        velocity=int(event.get("velocity", 84)),
                        pitch=int(pitch),
                        start=float(event["start"]),
                        end=float(event["end"]),
                    )
                )
        chords_pm.instruments.append(inst)
        path = output_dir / "chords.mid"
        chords_pm.write(str(path))
        files["chords"] = path

    if drum_events:
        drums_pm = pretty_midi.PrettyMIDI(initial_tempo=max(30.0, float(bpm)))
        inst = pretty_midi.Instrument(program=0, is_drum=True, name="drums")
        for event in drum_events:
            inst.notes.append(
                pretty_midi.Note(
                    velocity=int(event.get("velocity", 95)),
                    pitch=int(event["pitch"]),
                    start=float(event["start"]),
                    end=float(event["end"]),
                )
            )
        drums_pm.instruments.append(inst)
        path = output_dir / "drums.mid"
        drums_pm.write(str(path))
        files["drums"] = path

    if note_events or chord_events or drum_events:
        combined_pm = pretty_midi.PrettyMIDI(initial_tempo=max(30.0, float(bpm)))
        if note_events:
            notes_inst = pretty_midi.Instrument(program=0, name="notes")
            for event in note_events:
                notes_inst.notes.append(
                    pretty_midi.Note(
                        velocity=int(event.get("velocity", 90)),
                        pitch=int(event["pitch"]),
                        start=float(event["start"]),
                        end=float(event["end"]),
                    )
                )
            combined_pm.instruments.append(notes_inst)
        if chord_events:
            chord_inst = pretty_midi.Instrument(program=48, name="chords")
            for event in chord_events:
                for pitch in event["pitches"]:
                    chord_inst.notes.append(
                        pretty_midi.Note(
                            velocity=int(event.get("velocity", 84)),
                            pitch=int(pitch),
                            start=float(event["start"]),
                            end=float(event["end"]),
                        )
                    )
            combined_pm.instruments.append(chord_inst)
        if drum_events:
            drum_inst = pretty_midi.Instrument(program=0, is_drum=True, name="drums")
            for event in drum_events:
                drum_inst.notes.append(
                    pretty_midi.Note(
                        velocity=int(event.get("velocity", 95)),
                        pitch=int(event["pitch"]),
                        start=float(event["start"]),
                        end=float(event["end"]),
                    )
                )
            combined_pm.instruments.append(drum_inst)
        path = output_dir / "combined.mid"
        combined_pm.write(str(path))
        files["combined"] = path

    return files

