import zipfile
from io import BytesIO

import numpy as np
import soundfile as sf
from app.models.schemas import AnalyzeOptions
from app.services.conversion_service import ConversionService
from app.services.project_manager import ProjectManager


def test_conversion_creates_midi_audio_and_zip(tmp_path) -> None:
    manager = ProjectManager(root=tmp_path / "projects")
    service = ConversionService(manager=manager)

    sr = 44100
    duration = 1.0
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    tone = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)

    buf = BytesIO()
    sf.write(buf, tone, sr, format="WAV")
    options = AnalyzeOptions(mode="notes", root_note="C", scale="major", bpm=120)
    response = service.analyze_and_convert("unit.wav", buf.getvalue(), options)

    assert response.session_id
    assert response.run_id
    assert any(file.name.endswith(".mid") for file in response.midi_files)
    assert any(file.name.endswith(".wav") for file in response.audio_files)

    archive_path = manager.build_session_zip(response.session_id)
    with zipfile.ZipFile(archive_path) as zf:
        names = zf.namelist()
    assert any(name.startswith("midi/") for name in names)
    assert any(name.startswith("audio/") for name in names)
    assert any(name.startswith("metadata/") for name in names)

