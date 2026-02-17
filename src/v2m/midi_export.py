"""MIDI export for generated ideas."""

from __future__ import annotations

from pathlib import Path

from mido import Message, MetaMessage, MidiFile, MidiTrack, bpm2tempo

from .generator import GeneratedIdea, NoteEvent


def _append_note_events(track: MidiTrack, events: list[NoteEvent], ticks_per_beat: int) -> None:
    timeline: list[tuple[int, Message]] = []

    for event in events:
        start_tick = int(round(event.start_beat * ticks_per_beat))
        end_tick = int(round((event.start_beat + event.duration_beats) * ticks_per_beat))
        timeline.append(
            (
                start_tick,
                Message(
                    "note_on",
                    note=event.pitch,
                    velocity=event.velocity,
                    channel=event.channel,
                    time=0,
                ),
            )
        )
        timeline.append(
            (
                end_tick,
                Message(
                    "note_off",
                    note=event.pitch,
                    velocity=0,
                    channel=event.channel,
                    time=0,
                ),
            )
        )

    timeline.sort(key=lambda item: (item[0], 0 if item[1].type == "note_off" else 1))
    last_tick = 0
    for tick, msg in timeline:
        msg.time = tick - last_tick
        track.append(msg)
        last_tick = tick

    track.append(MetaMessage("end_of_track", time=0))


def export_idea_to_midi(idea: GeneratedIdea, output_path: str | Path) -> Path:
    """Export a GeneratedIdea to a MIDI file and return the written path."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    midi = MidiFile(ticks_per_beat=480)
    chord_track = MidiTrack()
    melody_track = MidiTrack()
    midi.tracks.append(chord_track)
    midi.tracks.append(melody_track)

    chord_track.append(MetaMessage("track_name", name="Chords", time=0))
    chord_track.append(MetaMessage("set_tempo", tempo=bpm2tempo(idea.bpm), time=0))
    _append_note_events(chord_track, idea.chords, midi.ticks_per_beat)

    melody_track.append(MetaMessage("track_name", name="Melody", time=0))
    _append_note_events(melody_track, idea.melody, midi.ticks_per_beat)

    midi.save(output)
    return output
