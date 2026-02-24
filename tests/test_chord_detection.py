import numpy as np
from app.services.analysis_service import detect_chords


def test_detect_chords_finds_c_major() -> None:
    sr = 22050
    duration = 2.0
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    freqs = [261.63, 329.63, 392.0]
    signal = sum(np.sin(2 * np.pi * freq * t) for freq in freqs) / len(freqs)
    signal = signal.astype(np.float32) * 0.35

    chords = detect_chords(signal, sr)
    assert len(chords) >= 1
    assert any(chord["root"] == "C" for chord in chords)

