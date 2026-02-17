from pathlib import Path

from mido import MidiFile

from v2m.generator import generate_idea
from v2m.midi_export import export_idea_to_midi


def test_export_creates_valid_midi(tmp_path: Path) -> None:
    idea = generate_idea(style="edm", key="G minor", bpm=128, bars=8, complexity=6, seed=11)
    output = tmp_path / "idea.mid"
    written_path = export_idea_to_midi(idea, output)

    assert written_path.exists()
    midi = MidiFile(written_path)
    assert len(midi.tracks) >= 2

    has_tempo = any(msg.type == "set_tempo" for msg in midi.tracks[0])
    note_messages = sum(
        1
        for track in midi.tracks
        for msg in track
        if msg.type in {"note_on", "note_off"}
    )

    assert has_tempo
    assert note_messages > 0
