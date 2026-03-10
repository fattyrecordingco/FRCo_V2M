from io import BytesIO

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from app.api import routes
from app.main import app
from app.models.schemas import AnalyzeOptions
from app.services.analysis_service import quantize_events
from app.services.conversion_service import ConversionService
from app.services.project_manager import ProjectManager


def _wav_bytes(freq: float = 220.0, duration: float = 1.2, sr: int = 44100) -> bytes:
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    signal = (0.3 * np.sin(2 * np.pi * freq * t)).astype(np.float32)
    buffer = BytesIO()
    sf.write(buffer, signal, sr, format="WAV")
    return buffer.getvalue()


def test_quantize_events_strength_blends_timing() -> None:
    events = [{"pitch": 69, "start": 0.13, "end": 0.41, "velocity": 90, "track": "notes"}]
    blended = quantize_events(events, bpm=120, strength=0.5)

    assert len(blended) == 1
    assert blended[0]["start"] == pytest.approx(0.1275)
    assert blended[0]["end"] == pytest.approx(0.3925)


def test_project_manager_latest_run_and_secure_rename(tmp_path) -> None:
    manager = ProjectManager(root=tmp_path / "projects")
    service = ConversionService(manager=manager)
    payload = _wav_bytes(freq=440.0)

    first = service.analyze_and_convert("voice.wav", payload, AnalyzeOptions(mode="notes", profile_name="test"))
    second = service.analyze_and_convert(
        "voice.wav",
        payload,
        AnalyzeOptions(mode="notes", session_id=first.session_id, profile_name="test"),
    )

    latest = manager.read_latest_run(first.session_id)
    assert latest["run_id"] == second.run_id
    assert latest["metadata"]["run_id"] == second.run_id
    assert latest["midi_files"]

    with pytest.raises((ValueError, FileNotFoundError)):
        manager.rename_file(first.session_id, "../outside.mid", "escape.mid")

    with pytest.raises(ValueError):
        manager.rename_file(first.session_id, second.midi_files[0].relative_path, "combined.mid")


def test_api_latest_run_and_controller_stream(tmp_path, monkeypatch) -> None:
    manager = ProjectManager(root=tmp_path / "projects")
    conversion = ConversionService(manager=manager)
    monkeypatch.setattr(routes, "manager", manager)
    monkeypatch.setattr(routes, "conversion", conversion)

    client = TestClient(app)
    payload = _wav_bytes(freq=261.63)

    analyze_response = client.post(
        "/api/v1/analyze",
        files={"file": ("capture.wav", payload, "audio/wav")},
        data={"mode": "notes", "workflow_mode": "studio", "profile_name": "api_test"},
    )
    assert analyze_response.status_code == 200
    session_id = analyze_response.json()["session_id"]

    latest_response = client.get(f"/api/v1/sessions/{session_id}/latest-run")
    assert latest_response.status_code == 200
    latest_payload = latest_response.json()
    assert latest_payload["session_id"] == session_id
    assert latest_payload["metadata"]["mode"] == "notes"
    assert latest_payload["midi_files"]

    control_response = client.post(
        "/api/v1/control/stream",
        files={"file": ("controller.wav", payload, "audio/wav")},
        data={"workflow_mode": "live"},
    )
    assert control_response.status_code == 200
    control_payload = control_response.json()
    assert control_payload["frames"]
    assert control_payload["midi_events"]["cc"]
