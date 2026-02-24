from io import BytesIO

import numpy as np
import soundfile as sf
from app.services.analysis_service import extract_monophonic_notes
from app.services.audio_io import load_audio_from_bytes


def test_extract_monophonic_notes_detects_a4() -> None:
    sr = 44100
    duration = 1.2
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    signal = 0.35 * np.sin(2 * np.pi * 440.0 * t)

    buffer = BytesIO()
    sf.write(buffer, signal, sr, format="WAV")
    audio, sample_rate = load_audio_from_bytes(buffer.getvalue(), sr)
    notes = extract_monophonic_notes(audio, sample_rate)

    assert len(notes) >= 1
    mean_pitch = sum(note["pitch"] for note in notes) / len(notes)
    assert abs(mean_pitch - 69) <= 1.5

