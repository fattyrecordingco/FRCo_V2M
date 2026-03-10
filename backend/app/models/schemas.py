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
    control = "control"


class MonoPolyOverride(str, Enum):
    auto = "auto"
    mono = "mono"
    poly = "poly"


class WorkflowMode(str, Enum):
    live = "live"
    studio = "studio"
    hybrid = "hybrid"


class FeelMode(str, Enum):
    preserve = "preserve"
    balanced = "balanced"
    tight = "tight"


class AnalyzeOptions(BaseModel):
    mode: ProcessingMode = ProcessingMode.auto
    workflow_mode: WorkflowMode = WorkflowMode.studio
    feel_mode: FeelMode = FeelMode.balanced
    auto_pitch_time: bool = False
    root_note: str | None = Field(default=None)
    scale: str | None = Field(default=None)
    custom_scale_notes: list[str] = Field(default_factory=list)
    bpm: float | None = None
    time_signature: str | None = None
    mono_poly_override: MonoPolyOverride = MonoPolyOverride.auto
    session_id: str | None = None
    quantize_strength: float = Field(default=0.35, ge=0.0, le=1.0)
    preserve_expression: bool = True
    embed_file_data: bool = False
    profile_name: str | None = None


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


class ControllerStreamResponse(BaseModel):
    frames: list[dict[str, Any]]
    midi_events: dict[str, list[dict[str, Any]]]
    summary: dict[str, Any]


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
