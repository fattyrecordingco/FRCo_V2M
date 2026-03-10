"""Local deterministic singer profile persistence."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from app.core.config import settings
from app.utils.file_utils import sanitize_filename


class SingerProfileService:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or (settings.projects_dir / "profiles")
        self.root.mkdir(parents=True, exist_ok=True)

    def load_profile(self, name: str | None) -> dict[str, Any] | None:
        if not name:
            return None
        path = self._profile_path(name)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def update_profile(
        self,
        name: str | None,
        note_events: list[dict[str, Any]],
        analysis_audio: np.ndarray,
        sr: int,
    ) -> dict[str, Any] | None:
        if not name or not note_events:
            return None

        current = self.load_profile(name) or {
            "name": sanitize_filename(name),
            "sample_count": 0,
            "low_midi": None,
            "high_midi": None,
            "center_midi": None,
            "vibrato_cents": 0.0,
            "drift_cents": 0.0,
            "attack_ms": 0.0,
            "noise_floor_db": -90.0,
        }
        sample_count = int(current.get("sample_count", 0))

        pitches = [float(note["pitch"]) for note in note_events if "pitch" in note]
        if not pitches:
            return current

        vibrato_values = []
        drift_values = []
        attack_values = []
        for note in note_events:
            curve = note.get("pitch_curve") or []
            if curve:
                base_pitch = float(note.get("pitch", 60))
                curve_midi = np.array([float(point.get("midi", base_pitch)) for point in curve], dtype=float)
                if curve_midi.size >= 3:
                    deviations = (curve_midi - base_pitch) * 100.0
                    vibrato_values.append(float(np.percentile(np.abs(deviations), 80)))
                    drift_values.append(float((curve_midi[-1] - curve_midi[0]) * 100.0))
            expr = note.get("expression_curve") or []
            if expr:
                attack_time = float(expr[min(1, len(expr) - 1)].get("time", note["start"])) - float(note["start"])
                attack_values.append(max(0.0, attack_time) * 1000.0)

        noise_floor = float(np.percentile(np.abs(analysis_audio), 15) + 1e-9)
        noise_floor_db = float(20.0 * np.log10(noise_floor))

        fresh = {
            "name": sanitize_filename(name),
            "sample_count": sample_count + 1,
            "low_midi": float(np.min(pitches)),
            "high_midi": float(np.max(pitches)),
            "center_midi": float(np.median(pitches)),
            "vibrato_cents": float(np.mean(vibrato_values)) if vibrato_values else float(current.get("vibrato_cents", 0.0)),
            "drift_cents": float(np.mean(drift_values)) if drift_values else float(current.get("drift_cents", 0.0)),
            "attack_ms": float(np.mean(attack_values)) if attack_values else float(current.get("attack_ms", 0.0)),
            "noise_floor_db": noise_floor_db,
            "updated_at": datetime.now(UTC).isoformat(),
            "analysis_sample_rate": sr,
        }

        merged = {
            "name": fresh["name"],
            "sample_count": fresh["sample_count"],
            "low_midi": _blend(current.get("low_midi"), fresh["low_midi"], sample_count),
            "high_midi": _blend(current.get("high_midi"), fresh["high_midi"], sample_count),
            "center_midi": _blend(current.get("center_midi"), fresh["center_midi"], sample_count),
            "vibrato_cents": _blend(current.get("vibrato_cents"), fresh["vibrato_cents"], sample_count),
            "drift_cents": _blend(current.get("drift_cents"), fresh["drift_cents"], sample_count),
            "attack_ms": _blend(current.get("attack_ms"), fresh["attack_ms"], sample_count),
            "noise_floor_db": _blend(current.get("noise_floor_db"), fresh["noise_floor_db"], sample_count),
            "updated_at": fresh["updated_at"],
            "analysis_sample_rate": sr,
        }
        self._profile_path(name).write_text(json.dumps(merged, indent=2), encoding="utf-8")
        return merged

    def list_profiles(self) -> list[dict[str, Any]]:
        profiles = []
        for path in sorted(self.root.glob("*.json")):
            profiles.append(json.loads(path.read_text(encoding="utf-8")))
        return profiles

    def _profile_path(self, name: str) -> Path:
        return self.root / f"{sanitize_filename(name)}.json"


def _blend(previous: Any, current: float, prior_samples: int) -> float:
    if previous is None:
        return float(current)
    weight = float(np.clip(prior_samples / max(prior_samples + 1, 1), 0.0, 0.92))
    return float(previous) * weight + float(current) * (1.0 - weight)
