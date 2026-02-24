from app.services.analysis_service import smooth_drum_events, smooth_note_events


def test_smooth_note_events_merges_adjacent_same_pitch() -> None:
    events = [
        {"pitch": 69, "start": 0.0, "end": 0.125, "velocity": 80, "track": "notes"},
        {"pitch": 69, "start": 0.156, "end": 0.25, "velocity": 82, "track": "notes"},
        {"pitch": 71, "start": 0.375, "end": 0.5, "velocity": 80, "track": "notes"},
    ]
    smoothed = smooth_note_events(events)
    assert len(smoothed) == 2
    assert smoothed[0]["pitch"] == 69
    assert smoothed[0]["start"] == 0.0
    assert smoothed[0]["end"] == 0.25


def test_smooth_drum_events_deduplicates_near_hits() -> None:
    events = [
        {
            "pitch": 36,
            "start": 0.50,
            "end": 0.62,
            "velocity": 75,
            "confidence": 0.7,
            "class": "kick",
            "track": "drums",
        },
        {
            "pitch": 36,
            "start": 0.53,
            "end": 0.64,
            "velocity": 95,
            "confidence": 0.9,
            "class": "kick",
            "track": "drums",
        },
        {
            "pitch": 38,
            "start": 0.75,
            "end": 0.86,
            "velocity": 80,
            "confidence": 0.8,
            "class": "snare",
            "track": "drums",
        },
    ]
    smoothed = smooth_drum_events(events)
    assert len(smoothed) == 2
    kick = smoothed[0]
    assert kick["pitch"] == 36
    assert kick["velocity"] == 95
