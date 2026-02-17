from v2m.generator import generate_idea


def _signature(idea) -> tuple:
    chord_sig = tuple(
        (e.start_beat, e.duration_beats, e.pitch, e.velocity, e.channel) for e in idea.chords
    )
    melody_sig = tuple(
        (e.start_beat, e.duration_beats, e.pitch, e.velocity, e.channel) for e in idea.melody
    )
    return chord_sig, melody_sig


def test_seed_reproducibility() -> None:
    idea_a = generate_idea(style="pop", key="C major", bpm=120, bars=8, complexity=5, seed=42)
    idea_b = generate_idea(style="pop", key="C major", bpm=120, bars=8, complexity=5, seed=42)
    assert _signature(idea_a) == _signature(idea_b)


def test_bar_count_drives_chord_layout() -> None:
    bars = 6
    idea = generate_idea(style="lofi", key="A minor", bpm=92, bars=bars, complexity=4, seed=3)
    start_beats = {event.start_beat for event in idea.chords}
    assert len(start_beats) == bars
    assert len(idea.chords) == bars * 3


def test_note_ranges_and_durations() -> None:
    idea = generate_idea(style="trap", key="D minor", bpm=140, bars=4, complexity=8, seed=9)
    for event in idea.chords + idea.melody:
        assert 0 <= event.pitch <= 127
        assert 0 <= event.velocity <= 127
        assert event.duration_beats > 0
