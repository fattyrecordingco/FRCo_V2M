"""Pydantic request and response models."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ProcessingMode(str, Enum):
    notes = "notes"
    chords = "chords"
    drums = "drums"
    auto = "auto"


class MonoPolyOverride(str, Enum):
    auto = "auto"
    mono = "mono"
    poly = "poly"


class AnalyzeOptions(BaseModel):
    mode: ProcessingMode = ProcessingMode.auto
    auto_pitch_time: bool = False
    root_note: str = Field(default="C")
    scale: str = Field(default="major")
    custom_scale_notes: list[str] = Field(default_factory=list)
    bpm: float | None = None
    time_signature: str | None = None
    mono_poly_override: MonoPolyOverride = MonoPolyOverride.auto
    session_id: str | None = None


class FileEntry(BaseModel):
    name: str
    relative_path: str
    kind: str
    mime_type: str
    run_id: str
    selected: bool = False
    url: str
    base64: str | None = None


class AnalyzeResponse(BaseModel):
    session_id: str
    run_id: str
    mode_used: ProcessingMode
    metadata: dict[str, Any]
    midi_files: list[FileEntry]
    audio_files: list[FileEntry]


class RenameRequest(BaseModel):
    kind: str
    relative_path: str
    new_name: str


class SessionSummary(BaseModel):
    session_id: str
    created_at: str
    updated_at: str
    latest_mode: str
    run_count: int
    source_file: str

