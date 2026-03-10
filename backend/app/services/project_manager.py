"""Persistent local project/session file management."""

from __future__ import annotations

import json
import shutil
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.config import settings
from app.models.schemas import FileEntry, SessionSummary
from app.utils.file_utils import sanitize_filename


@dataclass(slots=True)
class SessionContext:
    session_id: str
    path: Path
    run_id: str
    run_path: Path
    midi_path: Path
    audio_path: Path
    source_path: Path


class ProjectManager:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or settings.projects_dir
        self.root.mkdir(parents=True, exist_ok=True)

    def create_or_resume_session(self, source_filename: str, session_id: str | None = None) -> SessionContext:
        if session_id:
            session_path = self.root / sanitize_filename(session_id)
            if not session_path.exists():
                msg = f"Session {session_id} does not exist."
                raise FileNotFoundError(msg)
        else:
            timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            session_id = f"session_{timestamp}_{uuid4().hex[:6]}"
            session_path = self.root / session_id
            session_path.mkdir(parents=True, exist_ok=True)

        (session_path / "original").mkdir(parents=True, exist_ok=True)
        (session_path / "runs").mkdir(parents=True, exist_ok=True)

        run_id = self._next_run_id(session_path)
        run_path = session_path / "runs" / run_id
        midi_path = run_path / "midi"
        audio_path = run_path / "audio"
        for folder in (run_path, midi_path, audio_path):
            folder.mkdir(parents=True, exist_ok=True)
        source_path = session_path / "original" / sanitize_filename(source_filename)
        return SessionContext(
            session_id=session_id,
            path=session_path,
            run_id=run_id,
            run_path=run_path,
            midi_path=midi_path,
            audio_path=audio_path,
            source_path=source_path,
        )

    def write_run_metadata(self, ctx: SessionContext, payload: dict[str, Any]) -> Path:
        run_metadata = ctx.run_path / "metadata.json"
        run_metadata.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        session_index = ctx.path / "session.json"
        base = {
            "session_id": ctx.session_id,
            "created_at": payload["timestamps"]["created_at"],
            "updated_at": payload["timestamps"]["created_at"],
            "source_file": payload.get("source_file", ""),
            "latest_mode": payload.get("mode", "auto"),
            "run_count": 1,
        }
        if session_index.exists():
            base = json.loads(session_index.read_text(encoding="utf-8"))
            base["updated_at"] = payload["timestamps"]["created_at"]
            base["run_count"] = int(base.get("run_count", 0)) + 1
            base["latest_mode"] = payload.get("mode", base.get("latest_mode", "auto"))
            base["source_file"] = payload.get("source_file", base.get("source_file", ""))
        session_index.write_text(json.dumps(base, indent=2), encoding="utf-8")
        return run_metadata

    def list_sessions(self) -> list[SessionSummary]:
        sessions: list[SessionSummary] = []
        for path in sorted(self.root.glob("session_*"), reverse=True):
            session_file = path / "session.json"
            if not session_file.exists():
                continue
            raw = json.loads(session_file.read_text(encoding="utf-8"))
            sessions.append(
                SessionSummary(
                    session_id=raw["session_id"],
                    created_at=raw["created_at"],
                    updated_at=raw["updated_at"],
                    latest_mode=raw.get("latest_mode", "auto"),
                    run_count=int(raw.get("run_count", 0)),
                    source_file=raw.get("source_file", ""),
                )
            )
        return sessions

    def list_files(self, session_id: str, run_id: str | None = None) -> dict[str, list[FileEntry]]:
        session_path = self.root / sanitize_filename(session_id)
        if not session_path.exists():
            msg = f"Unknown session: {session_id}"
            raise FileNotFoundError(msg)
        midi_files: list[FileEntry] = []
        audio_files: list[FileEntry] = []
        run_paths = sorted((session_path / "runs").glob("run_*"))
        if run_id:
            run_paths = [path for path in run_paths if path.name == sanitize_filename(run_id)]
        for run_path in run_paths:
            current_run_id = run_path.name
            for midi_file in sorted((run_path / "midi").glob("*.mid")):
                rel = str(midi_file.relative_to(session_path)).replace("\\", "/")
                midi_files.append(
                    FileEntry(
                        name=midi_file.name,
                        relative_path=rel,
                        kind="midi",
                        mime_type="audio/midi",
                        run_id=current_run_id,
                        url=f"/api/v1/files/{session_id}/{rel}",
                    )
                )
            for audio_file in sorted((run_path / "audio").glob("*")):
                if not audio_file.is_file():
                    continue
                rel = str(audio_file.relative_to(session_path)).replace("\\", "/")
                mime = "audio/wav" if audio_file.suffix.lower() == ".wav" else "audio/mpeg"
                audio_files.append(
                    FileEntry(
                        name=audio_file.name,
                        relative_path=rel,
                        kind="audio",
                        mime_type=mime,
                        run_id=current_run_id,
                        url=f"/api/v1/files/{session_id}/{rel}",
                    )
                )
        return {"midi": midi_files, "audio": audio_files}

    def rename_file(self, session_id: str, relative_path: str, new_name: str) -> FileEntry:
        session_path = self.root / sanitize_filename(session_id)
        source = self.resolve_file_path(session_id, relative_path)
        if not source.is_file():
            msg = "File not found for rename."
            raise FileNotFoundError(msg)
        sanitized_name = sanitize_filename(new_name)
        if not Path(sanitized_name).suffix:
            sanitized_name = f"{sanitized_name}{source.suffix.lower()}"
        target = source.with_name(sanitized_name)
        if session_path.resolve() not in target.resolve().parents:
            msg = "Invalid rename target."
            raise ValueError(msg)
        if target.exists() and source.resolve() != target.resolve():
            msg = "A file with that name already exists."
            raise ValueError(msg)
        source.rename(target)
        rel = str(target.relative_to(session_path)).replace("\\", "/")
        kind = "midi" if target.suffix.lower() == ".mid" else "audio"
        mime = "audio/midi" if kind == "midi" else ("audio/mpeg" if target.suffix.lower() == ".mp3" else "audio/wav")
        return FileEntry(
            name=target.name,
            relative_path=rel,
            kind=kind,
            mime_type=mime,
            run_id=target.parents[1].name if len(target.parents) > 1 else "run_001",
            url=f"/api/v1/files/{session_id}/{rel}",
        )

    def resolve_file_path(self, session_id: str, relative_path: str) -> Path:
        session_path = self.root / sanitize_filename(session_id)
        target = (session_path / Path(relative_path)).resolve()
        if session_path.resolve() not in target.parents and target != session_path.resolve():
            msg = "Invalid file path."
            raise ValueError(msg)
        if not target.exists():
            msg = "Requested file does not exist."
            raise FileNotFoundError(msg)
        return target

    def build_session_zip(self, session_id: str) -> Path:
        session_path = self.root / sanitize_filename(session_id)
        if not session_path.exists():
            msg = f"Session {session_id} not found."
            raise FileNotFoundError(msg)
        zip_dir = session_path / "exports"
        zip_dir.mkdir(parents=True, exist_ok=True)
        out_zip = zip_dir / f"{session_id}.zip"
        with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for run_path in sorted((session_path / "runs").glob("run_*")):
                run_id = run_path.name
                for midi_file in sorted((run_path / "midi").glob("*.mid")):
                    arcname = f"midi/{run_id}_{midi_file.name}"
                    zf.write(midi_file, arcname=arcname)
                for audio_file in sorted((run_path / "audio").glob("*")):
                    if audio_file.is_file():
                        arcname = f"audio/{run_id}_{audio_file.name}"
                        zf.write(audio_file, arcname=arcname)
                metadata = run_path / "metadata.json"
                if metadata.exists():
                    zf.write(metadata, arcname=f"metadata/{run_id}_metadata.json")

            source_dir = session_path / "original"
            for source_file in sorted(source_dir.glob("*")):
                if source_file.is_file():
                    zf.write(source_file, arcname=f"audio/original_{source_file.name}")
            session_index = session_path / "session.json"
            if session_index.exists():
                zf.write(session_index, arcname="metadata/session.json")
        return out_zip

    def clear_session(self, session_id: str) -> None:
        session_path = self.root / sanitize_filename(session_id)
        if session_path.exists():
            shutil.rmtree(session_path)

    def read_latest_run(self, session_id: str) -> dict[str, Any]:
        session_path = self.root / sanitize_filename(session_id)
        if not session_path.exists():
            msg = f"Unknown session: {session_id}"
            raise FileNotFoundError(msg)
        run_paths = sorted((session_path / "runs").glob("run_*"))
        if not run_paths:
            msg = f"Session {session_id} has no runs."
            raise FileNotFoundError(msg)
        latest_run = run_paths[-1]
        metadata_path = latest_run / "metadata.json"
        if not metadata_path.exists():
            msg = f"Session {session_id} latest run is missing metadata."
            raise FileNotFoundError(msg)
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        files = self.list_files(session_id, run_id=latest_run.name)
        return {
            "session_id": session_id,
            "run_id": latest_run.name,
            "metadata": metadata,
            "midi_files": [item.model_dump() for item in files["midi"]],
            "audio_files": [item.model_dump() for item in files["audio"]],
        }

    @staticmethod
    def _next_run_id(session_path: Path) -> str:
        run_numbers = []
        for run_dir in (session_path / "runs").glob("run_*"):
            if not run_dir.is_dir():
                continue
            suffix = run_dir.name.split("_")[-1]
            if suffix.isdigit():
                run_numbers.append(int(suffix))
        next_num = max(run_numbers, default=0) + 1
        return f"run_{next_num:03d}"
