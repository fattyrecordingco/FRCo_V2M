import numpy as np
from app.services import audio_io
from app.services.analysis_service import enhance_for_analysis, extract_monophonic_notes


def test_low_volume_hum_detects_pitch_after_enhancement() -> None:
    sr = 44100
    duration = 1.6
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    rng = np.random.default_rng(9)

    hum = 0.015 * np.sin(2 * np.pi * 220.0 * t)
    harmonic = 0.0055 * np.sin(2 * np.pi * 440.0 * t)
    noise = rng.normal(0.0, 0.0016, size=t.shape)
    signal = (hum + harmonic + noise).astype(np.float32)

    enhanced, meta = enhance_for_analysis(signal, sr)
    notes = extract_monophonic_notes(enhanced, sr)

    assert meta["gain"] > 1.0
    assert 0.08 <= meta["output_active_rms"] <= 0.24
    assert len(notes) >= 1
    mean_pitch = sum(note["pitch"] for note in notes) / len(notes)
    assert abs(mean_pitch - 57) <= 2.0


def test_clipped_input_is_attenuated_into_analysis_window() -> None:
    sr = 44100
    duration = 1.4
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    raw = (1.35 * np.sin(2 * np.pi * 329.63 * t)).astype(np.float32)
    clipped = np.clip(raw, -1.0, 1.0)

    enhanced, meta = enhance_for_analysis(clipped, sr)
    notes = extract_monophonic_notes(enhanced, sr)

    assert meta["clip_ratio"] > 0.0
    assert meta["clipped_segments"] >= 1.0
    assert meta["peak"] <= 0.96 + 1e-3
    assert meta["output_active_rms"] <= 0.24
    assert notes
    mean_pitch = sum(note["pitch"] for note in notes) / len(notes)
    assert abs(mean_pitch - 64) <= 2.0


def test_load_audio_from_bytes_fallback_downmixes_channels_first(monkeypatch) -> None:
    sr = 22050
    sample_count = 1600
    left = np.linspace(-0.25, 0.25, sample_count, dtype=np.float32)
    right = np.linspace(0.35, -0.35, sample_count, dtype=np.float32)
    channels_first = np.stack([left, right], axis=0)

    def fail_soundfile(*_args, **_kwargs):
        raise RuntimeError("decode failed")

    monkeypatch.setattr(audio_io.sf, "SoundFile", fail_soundfile)
    monkeypatch.setattr(
        audio_io.librosa,
        "load",
        lambda _path, sr=None, mono=False: (channels_first, 22050),
    )

    audio, out_sr = audio_io.load_audio_from_bytes(b"fake-bytes", sr)
    expected = (left + right) * 0.5

    assert out_sr == sr
    assert audio.shape[0] == sample_count
    np.testing.assert_allclose(audio[:100], expected[:100], atol=2e-4)
