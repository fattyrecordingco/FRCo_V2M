import numpy as np
from app.services.analysis_service import transcribe_drums


def test_drum_transcription_classifies_low_and_high_energy_hits() -> None:
    sr = 44100
    duration = 1.5
    audio = np.zeros(int(sr * duration), dtype=np.float32)

    for pos in [0.2, 0.9]:
        start = int(pos * sr)
        size = int(0.09 * sr)
        t = np.linspace(0, 0.09, size, endpoint=False)
        kick = np.sin(2 * np.pi * 70 * t) * np.exp(-28 * t)
        audio[start : start + size] += kick * 0.85

    rng = np.random.default_rng(7)
    for pos in [0.5, 1.2]:
        start = int(pos * sr)
        size = int(0.05 * sr)
        hat = rng.normal(0, 1, size) * np.hanning(size)
        audio[start : start + size] += hat * 0.25

    events = transcribe_drums(audio, sr)

    assert len(events) >= 2
    classes = {event["class"] for event in events}
    assert "kick" in classes or "snare" in classes
    assert any(cls.startswith("hihat") or cls == "crash" for cls in classes)
