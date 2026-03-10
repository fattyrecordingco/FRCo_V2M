"""MIDI export helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pretty_midi


def write_midi_bundle(
    output_dir: Path,
    bpm: float,
    note_events: list[dict[str, Any]],
    chord_events: list[dict[str, Any]],
    drum_events: list[dict[str, Any]],
    controller_data: dict[str, Any] | None = None,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    files: dict[str, Path] = {}

    if note_events:
        notes_pm = pretty_midi.PrettyMIDI(initial_tempo=max(30.0, float(bpm)))
        inst = pretty_midi.Instrument(program=0, name="notes")
        _append_note_events(inst, note_events)
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
        _append_note_events(inst, drum_events)
        drums_pm.instruments.append(inst)
        path = output_dir / "drums.mid"
        drums_pm.write(str(path))
        files["drums"] = path

    if controller_data:
        control_pm = pretty_midi.PrettyMIDI(initial_tempo=max(30.0, float(bpm)))
        inst = pretty_midi.Instrument(program=89, name="controller")
        _append_note_events(inst, controller_data.get("events", {}).get("notes", []))
        _append_control_events(inst, controller_data)
        control_pm.instruments.append(inst)
        path = output_dir / "controller.mid"
        control_pm.write(str(path))
        files["controller"] = path

    if note_events or chord_events or drum_events:
        combined_pm = pretty_midi.PrettyMIDI(initial_tempo=max(30.0, float(bpm)))
        if note_events:
            notes_inst = pretty_midi.Instrument(program=0, name="notes")
            _append_note_events(notes_inst, note_events)
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
            _append_note_events(drum_inst, drum_events)
            combined_pm.instruments.append(drum_inst)
        if controller_data:
            controller_inst = pretty_midi.Instrument(program=89, name="controller")
            _append_note_events(controller_inst, controller_data.get("events", {}).get("notes", []))
            _append_control_events(controller_inst, controller_data)
            combined_pm.instruments.append(controller_inst)
        path = output_dir / "combined.mid"
        combined_pm.write(str(path))
        files["combined"] = path

    return files


def _append_note_events(inst: pretty_midi.Instrument, events: list[dict[str, Any]]) -> None:
    for event in events:
        inst.notes.append(
            pretty_midi.Note(
                velocity=int(event.get("velocity", 90)),
                pitch=int(event["pitch"]),
                start=float(event["start"]),
                end=float(event["end"]),
            )
        )
        pitch_curve = event.get("pitch_curve") or []
        if pitch_curve and not inst.is_drum:
            _append_pitch_curve(inst, int(event["pitch"]), pitch_curve)
        expression_curve = event.get("expression_curve") or []
        if expression_curve and not inst.is_drum:
            _append_expression_curve(inst, expression_curve)


def _append_pitch_curve(
    inst: pretty_midi.Instrument,
    base_pitch: int,
    pitch_curve: list[dict[str, Any]],
) -> None:
    for point in pitch_curve:
        midi_value = float(point.get("midi", base_pitch))
        bend = int(np.clip(round(((midi_value - float(base_pitch)) / 2.0) * 8192.0), -8192, 8191))
        inst.pitch_bends.append(pretty_midi.PitchBend(pitch=bend, time=float(point["time"])))


def _append_expression_curve(inst: pretty_midi.Instrument, expression_curve: list[dict[str, Any]]) -> None:
    for point in expression_curve:
        value = int(np.clip(round(float(point.get("value", 0.0)) * 127.0), 0, 127))
        when = float(point["time"])
        inst.control_changes.append(pretty_midi.ControlChange(number=11, value=value, time=when))
        inst.control_changes.append(pretty_midi.ControlChange(number=1, value=min(127, value // 2), time=when))


def _append_control_events(inst: pretty_midi.Instrument, controller_data: dict[str, Any]) -> None:
    events = controller_data.get("events", {})
    for event in events.get("cc", []):
        inst.control_changes.append(
            pretty_midi.ControlChange(
                number=int(event["number"]),
                value=int(event["value"]),
                time=float(event["time"]),
            )
        )
    for event in events.get("pitch_bends", []):
        inst.pitch_bends.append(
            pretty_midi.PitchBend(
                pitch=int(event["value"]),
                time=float(event["time"]),
            )
        )
