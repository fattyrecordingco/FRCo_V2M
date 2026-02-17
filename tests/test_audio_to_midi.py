from pathlib import Path
import json
import math

import numpy as np
import soundfile as sf
from mido import MidiFile

from v2m.audio_to_midi import analyze_audio_to_project


def _add_burst(signal: np.ndarray, sr: int, time_sec: float, freq: float, amp: float, dur: float) -> None:
    start = int(time_sec * sr)
    length = int(dur * sr)
    end = min(signal.size, start + length)
    if start >= signal.size or end <= start:
        return
    t = np.arange(end - start, dtype=np.float32) / sr
    env = np.exp(-8.0 * t)
    signal[start:end] += amp * np.sin(2 * math.pi * freq * t) * env


def _create_test_audio(path: Path, sr: int = 22050) -> None:
    duration_sec = 8.0
    total = int(duration_sec * sr)
    y = np.zeros(total, dtype=np.float32)

    # Four-note hummed idea.
    notes = [220.0, 246.94, 261.63, 293.66]
    note_dur = 1.0
    for idx, hz in enumerate(notes * 2):
        start = int(idx * note_dur * sr)
        end = min(total, int((idx + 1) * note_dur * sr))
        t = np.arange(end - start, dtype=np.float32) / sr
        y[start:end] += 0.14 * np.sin(2 * math.pi * hz * t)

    # Beatbox-like transients: kick/snare/hat pattern.
    beat_sec = 0.5  # 120 BPM
    for beat in range(int(duration_sec / beat_sec)):
        onset = beat * beat_sec
        if beat % 2 == 0:
            _add_burst(y, sr, onset, freq=90, amp=0.75, dur=0.10)  # kick-ish
        else:
            _add_burst(y, sr, onset, freq=230, amp=0.65, dur=0.08)  # snare-ish
        _add_burst(y, sr, onset + 0.25, freq=3500, amp=0.30, dur=0.03)  # hat-ish

    peak = float(np.max(np.abs(y)))
    if peak > 0:
        y = y / peak * 0.8
    sf.write(path, y, sr)


def test_audio_to_midi_prototype_pipeline(tmp_path: Path) -> None:
    input_wav = tmp_path / "input.wav"
    _create_test_audio(input_wav)

    result = analyze_audio_to_project(
        input_audio_path=input_wav,
        projects_dir=tmp_path / "projects",
        project_name="prototype-test",
        scale_mode="auto",
        manual_key="C major",
        genre_tags=["trap"],
        quantize_strength=0.9,
    )

    assert result.project_dir.exists()
    assert result.raw_audio_path.exists()
    assert result.cleaned_audio_path.exists()
    assert result.melody_midi_path.exists()
    assert result.drums_midi_path.exists()
    assert result.combined_midi_path.exists()
    assert result.analysis_path.exists()
    assert result.recipe_path.exists()

    melody_midi = MidiFile(result.melody_midi_path)
    drum_midi = MidiFile(result.drums_midi_path)
    melody_note_count = sum(
        1 for track in melody_midi.tracks for msg in track if msg.type == "note_on" and msg.velocity > 0
    )
    drum_note_count = sum(
        1 for track in drum_midi.tracks for msg in track if msg.type == "note_on" and msg.velocity > 0
    )

    assert melody_note_count > 0
    assert drum_note_count > 0

    analysis_payload = json.loads(result.analysis_path.read_text(encoding="utf-8"))
    assert analysis_payload["melody_event_count"] > 0
    assert analysis_payload["drum_event_count"] > 0
    assert isinstance(analysis_payload["detected_key"], str)
