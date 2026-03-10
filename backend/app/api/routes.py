"""HTTP API routes for conversion and file management."""

from __future__ import annotations

import logging

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.core.config import settings
from app.models.schemas import AnalyzeOptions, AnalyzeResponse, ControllerStreamResponse, RenameRequest, SessionSummary
from app.services.conversion_service import ConversionService
from app.services.controller_service import analyze_controller_input
from app.services.audio_io import load_audio_from_bytes, validate_extension
from app.services.project_manager import ProjectManager
from app.utils.file_utils import sanitize_filename

router = APIRouter()
manager = ProjectManager()
conversion = ConversionService(manager=manager)
logger = logging.getLogger(__name__)


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    file: UploadFile = File(...),
    mode: str = Form("auto"),
    workflow_mode: str = Form("studio"),
    feel_mode: str = Form("balanced"),
    auto_pitch_time: bool = Form(False),
    root_note: str = Form(""),
    scale: str = Form(""),
    custom_scale_notes: str = Form(""),
    bpm: float | None = Form(None),
    time_signature: str = Form(""),
    mono_poly_override: str = Form("auto"),
    session_id: str | None = Form(None),
    quantize_strength: float = Form(0.35),
    preserve_expression: bool = Form(True),
    embed_file_data: bool = Form(False),
    profile_name: str = Form(""),
) -> AnalyzeResponse:
    payload = b""
    try:
        payload = await file.read()
        options = AnalyzeOptions(
            mode=mode,
            workflow_mode=workflow_mode,
            feel_mode=feel_mode,
            auto_pitch_time=auto_pitch_time,
            root_note=root_note or None,
            scale=scale or None,
            custom_scale_notes=[x.strip() for x in custom_scale_notes.split(",") if x.strip()],
            bpm=bpm,
            time_signature=time_signature or None,
            mono_poly_override=mono_poly_override,
            session_id=session_id or None,
            quantize_strength=quantize_strength,
            preserve_expression=preserve_expression,
            embed_file_data=embed_file_data,
            profile_name=profile_name or None,
        )
        return conversion.analyze_and_convert(file.filename or "recording.wav", payload, options)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - safety net
        logger.exception(
            "Analyze failed filename=%s content_type=%s bytes=%s",
            file.filename,
            file.content_type,
            len(payload),
        )
        detail = str(exc).strip() or exc.__class__.__name__
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed ({exc.__class__.__name__}): {detail}",
        ) from exc


@router.post("/convert-notes", response_model=AnalyzeResponse)
async def convert_notes(
    file: UploadFile = File(...),
    session_id: str | None = Form(None),
    root_note: str = Form(""),
    scale: str = Form(""),
    bpm: float | None = Form(None),
    time_signature: str = Form(""),
    workflow_mode: str = Form("studio"),
    feel_mode: str = Form("balanced"),
    quantize_strength: float = Form(0.35),
    preserve_expression: bool = Form(True),
    profile_name: str = Form(""),
) -> AnalyzeResponse:
    payload = b""
    try:
        payload = await file.read()
        options = AnalyzeOptions(
            mode="notes",
            workflow_mode=workflow_mode,
            feel_mode=feel_mode,
            auto_pitch_time=False,
            root_note=root_note or None,
            scale=scale or None,
            bpm=bpm,
            time_signature=time_signature or None,
            session_id=session_id or None,
            quantize_strength=quantize_strength,
            preserve_expression=preserve_expression,
            profile_name=profile_name or None,
        )
        return conversion.analyze_and_convert(file.filename or "recording.wav", payload, options)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        logger.exception("convert-notes failed filename=%s bytes=%s", file.filename, len(payload))
        detail = str(exc).strip() or exc.__class__.__name__
        msg = f"convert-notes failed ({exc.__class__.__name__}): {detail}"
        raise HTTPException(status_code=500, detail=msg) from exc


@router.post("/convert-chords", response_model=AnalyzeResponse)
async def convert_chords(
    file: UploadFile = File(...),
    session_id: str | None = Form(None),
    root_note: str = Form(""),
    scale: str = Form(""),
    bpm: float | None = Form(None),
    time_signature: str = Form(""),
    workflow_mode: str = Form("studio"),
    feel_mode: str = Form("balanced"),
    quantize_strength: float = Form(0.35),
) -> AnalyzeResponse:
    payload = b""
    try:
        payload = await file.read()
        options = AnalyzeOptions(
            mode="chords",
            workflow_mode=workflow_mode,
            feel_mode=feel_mode,
            auto_pitch_time=False,
            root_note=root_note or None,
            scale=scale or None,
            bpm=bpm,
            time_signature=time_signature or None,
            session_id=session_id or None,
            quantize_strength=quantize_strength,
        )
        return conversion.analyze_and_convert(file.filename or "recording.wav", payload, options)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        logger.exception("convert-chords failed filename=%s bytes=%s", file.filename, len(payload))
        detail = str(exc).strip() or exc.__class__.__name__
        msg = f"convert-chords failed ({exc.__class__.__name__}): {detail}"
        raise HTTPException(status_code=500, detail=msg) from exc


@router.post("/convert-drums", response_model=AnalyzeResponse)
async def convert_drums(
    file: UploadFile = File(...),
    session_id: str | None = Form(None),
    bpm: float | None = Form(None),
    time_signature: str = Form(""),
    workflow_mode: str = Form("live"),
    quantize_strength: float = Form(0.45),
) -> AnalyzeResponse:
    payload = b""
    try:
        payload = await file.read()
        options = AnalyzeOptions(
            mode="drums",
            workflow_mode=workflow_mode,
            auto_pitch_time=False,
            bpm=bpm,
            time_signature=time_signature or None,
            session_id=session_id or None,
            quantize_strength=quantize_strength,
        )
        return conversion.analyze_and_convert(file.filename or "recording.wav", payload, options)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        logger.exception("convert-drums failed filename=%s bytes=%s", file.filename, len(payload))
        detail = str(exc).strip() or exc.__class__.__name__
        msg = f"convert-drums failed ({exc.__class__.__name__}): {detail}"
        raise HTTPException(status_code=500, detail=msg) from exc


@router.get("/sessions", response_model=list[SessionSummary])
def sessions() -> list[SessionSummary]:
    return manager.list_sessions()


@router.get("/sessions/{session_id}/files")
def list_session_files(session_id: str) -> dict[str, list]:
    try:
        files = manager.list_files(session_id)
        return {"midi": files["midi"], "audio": files["audio"]}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/sessions/{session_id}/latest-run", response_model=AnalyzeResponse)
def latest_run(session_id: str) -> AnalyzeResponse:
    try:
        payload = manager.read_latest_run(session_id)
        payload["mode_used"] = payload["metadata"].get("mode", "auto")
        return AnalyzeResponse.model_validate(payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/files/{session_id}/{file_path:path}")
def get_file(session_id: str, file_path: str) -> FileResponse:
    try:
        target = manager.resolve_file_path(session_id, file_path)
        return FileResponse(target, filename=target.name)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/files/{session_id}/rename")
def rename_file(session_id: str, request: RenameRequest):
    try:
        renamed = manager.rename_file(session_id, request.relative_path, request.new_name)
        return renamed
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/sessions/{session_id}/zip")
def download_session_zip(session_id: str) -> FileResponse:
    try:
        zip_path = manager.build_session_zip(session_id)
        return FileResponse(zip_path, filename=zip_path.name, media_type="application/zip")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/demo-files")
def demo_files() -> dict[str, list[dict[str, str]]]:
    items = []
    for path in sorted(settings.examples_dir.glob("*.wav")):
        items.append(
            {
                "name": path.name,
                "url": f"/api/v1/examples/{sanitize_filename(path.name)}",
            }
        )
    return {"files": items}


@router.get("/examples/{name}")
def demo_file(name: str) -> FileResponse:
    path = settings.examples_dir / sanitize_filename(name)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Demo file not found.")
    return FileResponse(path, media_type="audio/wav", filename=path.name)


@router.post("/control/stream", response_model=ControllerStreamResponse)
async def control_stream(
    file: UploadFile = File(...),
    workflow_mode: str = Form("live"),
) -> ControllerStreamResponse:
    payload = b""
    try:
        validate_extension(file.filename or "recording.wav")
        payload = await file.read()
        audio, sr = load_audio_from_bytes(payload, settings.default_sample_rate)
        controller = analyze_controller_input(audio, sr, workflow_mode=workflow_mode)
        return ControllerStreamResponse(
            frames=controller["frames"],
            midi_events=controller["events"],
            summary=controller["summary"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        logger.exception("control-stream failed filename=%s bytes=%s", file.filename, len(payload))
        detail = str(exc).strip() or exc.__class__.__name__
        raise HTTPException(status_code=500, detail=f"control-stream failed ({exc.__class__.__name__}): {detail}") from exc
