"""Conversion pipeline orchestration."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np

from app.core.config import settings
from app.models.schemas import AnalyzeOptions, AnalyzeResponse, FileEntry, ProcessingMode
from app.services.analysis_service import (
    constrain_to_scale,
    detect_chords,
    enhance_for_analysis,
    extract_monophonic_notes,
    quantize_events,
    retune_audio,
    smooth_drum_events,
    smooth_note_events,
    split_stems,
    summarize_analysis,
    transcribe_drums,
)
from app.services.audio_io import is_silent, load_audio_from_bytes, save_wav, validate_extension
from app.services.controller_service import analyze_controller_input
from app.services.midi_service import write_midi_bundle
from app.services.profile_service import SingerProfileService
from app.services.project_manager import ProjectManager
from app.services.suggestion_service import build_musical_suggestions
from app.utils.file_utils import encode_file_base64


class ConversionService:
    def __init__(
        self,
        manager: ProjectManager | None = None,
        profile_service: SingerProfileService | None = None,
    ) -> None:
        self.manager = manager or ProjectManager()
        self.profile_service = profile_service or SingerProfileService()

    def analyze_and_convert(self, filename: str, audio_bytes: bytes, options: AnalyzeOptions) -> AnalyzeResponse:
        validate_extension(filename)
        wall_start = perf_counter()
        audio, sr = load_audio_from_bytes(audio_bytes, settings.default_sample_rate)
        if is_silent(audio):
            raise ValueError("Silent recording detected. Please capture louder input.")

        session = self.manager.create_or_resume_session(filename, options.session_id)
        session.source_path.write_bytes(audio_bytes)

        analysis_audio, enhancement = enhance_for_analysis(audio, sr)
        if is_silent(analysis_audio):
            raise ValueError("Input is too quiet/noisy after enhancement. Try a cleaner or louder take.")

        stems = split_stems(analysis_audio)
        percussive_ratio = self._percussive_ratio(stems)
        summary = summarize_analysis(analysis_audio, sr)
        bpm = float(options.bpm if options.bpm is not None else summary.tempo_bpm)
        time_signature = options.time_signature or summary.time_signature
        root_note = options.root_note or summary.root_note
        scale = options.scale or summary.scale
        quantize_strength = self._quantize_strength(options.quantize_strength, options.feel_mode.value)
        profile = self.profile_service.load_profile(options.profile_name)

        mode = self._resolve_mode(options.mode, summary.mono_poly_label, options, percussive_ratio)
        note_events: list[dict[str, Any]] = []
        chord_events: list[dict[str, Any]] = []
        drum_events: list[dict[str, Any]] = []
        controller_data: dict[str, Any] | None = None

        apply_scale = options.scale is not None or summary.key_confidence >= 0.58

        if mode in {ProcessingMode.notes, ProcessingMode.auto}:
            note_events = extract_monophonic_notes(
                stems["harmonic"],
                sr,
                singer_profile=profile,
                workflow_mode=options.workflow_mode.value,
                preserve_expression=options.preserve_expression,
            )
            if apply_scale:
                note_events = constrain_to_scale(note_events, root_note, scale, options.custom_scale_notes)
            note_events = quantize_events(note_events, bpm, strength=quantize_strength)
            note_events = smooth_note_events(note_events)

        if mode in {ProcessingMode.chords, ProcessingMode.auto}:
            chord_events = detect_chords(stems["harmonic"], sr)
            if apply_scale and chord_events:
                chord_events = constrain_to_scale(chord_events, root_note, scale, options.custom_scale_notes)
            chord_events = quantize_events(chord_events, bpm, strength=min(quantize_strength + 0.15, 1.0))

        if mode in {ProcessingMode.drums, ProcessingMode.auto} and percussive_ratio >= 0.22:
            drum_events = transcribe_drums(analysis_audio, sr)
            drum_events = quantize_events(drum_events, bpm, strength=min(quantize_strength + 0.10, 1.0))
            drum_events = smooth_drum_events(drum_events)

        if mode == ProcessingMode.control:
            controller_data = analyze_controller_input(
                analysis_audio,
                sr,
                workflow_mode=options.workflow_mode.value,
                already_enhanced=True,
                enhancement_meta=enhancement,
            )

        profile_after = self.profile_service.update_profile(options.profile_name, note_events, analysis_audio, sr)
        suggestions = build_musical_suggestions(asdict(summary), note_events, chord_events, drum_events)
        midi_paths = write_midi_bundle(
            session.midi_path,
            bpm,
            note_events,
            chord_events,
            drum_events,
            controller_data=controller_data,
        )
        generated_audio = self._write_audio_outputs(
            session_audio_dir=session.audio_path,
            source_audio=audio,
            analysis_audio=analysis_audio,
            stems=stems,
            sr=sr,
            detected_bpm=summary.tempo_bpm,
            target_bpm=options.bpm if options.auto_pitch_time else None,
            detected_root=summary.root_note,
            target_root=root_note,
            auto_pitch_time=options.auto_pitch_time,
        )

        created_at = datetime.now(UTC).isoformat()
        metadata = {
            "session_id": session.session_id,
            "run_id": session.run_id,
            "mode": mode.value,
            "workflow_mode": options.workflow_mode.value,
            "feel_mode": options.feel_mode.value,
            "source_file": filename,
            "analysis": {
                **asdict(summary),
                "selected_bpm": bpm,
                "selected_time_signature": time_signature,
                "selected_root_note": root_note,
                "selected_scale": scale,
                "input_enhancement": enhancement,
                "percussive_ratio": round(percussive_ratio, 4),
                "processing_latency_ms": round((perf_counter() - wall_start) * 1000.0, 3),
            },
            "note_events": note_events,
            "chord_events": chord_events,
            "drum_events": drum_events,
            "controller": controller_data,
            "profile": profile_after or profile,
            "suggestions": suggestions,
            "user_selections": options.model_dump(),
            "timestamps": {"created_at": created_at},
            "detection_confidence": {
                "key": summary.key_confidence,
                "mono_poly": summary.mono_poly_confidence,
                "drums": _mean_confidence(drum_events),
                "chords": _mean_confidence(chord_events),
                "notes": _mean_confidence(note_events),
                "controller": float(controller_data.get("summary", {}).get("active_ratio", 0.0)) if controller_data else 0.0,
            },
        }
        metadata_path = session.run_path / "metadata.json"
        metadata_path.write_text(_to_pretty_json(metadata), encoding="utf-8")
        self.manager.write_run_metadata(session, metadata)

        midi_files = [
            self._to_file_entry(
                path=path,
                session_id=session.session_id,
                session_path=session.path,
                run_id=session.run_id,
                selected=(name == "combined" or (name == "notes" and "combined" not in midi_paths)),
                with_base64=options.embed_file_data,
            )
            for name, path in midi_paths.items()
        ]
        audio_files = [
            self._to_file_entry(
                path=path,
                session_id=session.session_id,
                session_path=session.path,
                run_id=session.run_id,
                selected=(idx == 0),
                with_base64=options.embed_file_data,
            )
            for idx, path in enumerate(generated_audio)
        ]

        return AnalyzeResponse(
            session_id=session.session_id,
            run_id=session.run_id,
            mode_used=mode,
            metadata=metadata,
            midi_files=midi_files,
            audio_files=audio_files,
        )

    def _resolve_mode(
        self,
        requested_mode: ProcessingMode,
        detected_mono_poly: str,
        options: AnalyzeOptions,
        percussive_ratio: float,
    ) -> ProcessingMode:
        if requested_mode != ProcessingMode.auto:
            return requested_mode
        if options.mono_poly_override.value == "mono":
            return ProcessingMode.notes
        if options.mono_poly_override.value == "poly":
            return ProcessingMode.chords
        if percussive_ratio >= 0.82:
            return ProcessingMode.drums
        return ProcessingMode.chords if detected_mono_poly == "poly" else ProcessingMode.notes

    @staticmethod
    def _quantize_strength(requested_strength: float, feel_mode: str) -> float:
        base = float(np.clip(requested_strength, 0.0, 1.0))
        if feel_mode == "preserve":
            return min(base, 0.18)
        if feel_mode == "tight":
            return max(base, 0.72)
        return base

    @staticmethod
    def _percussive_ratio(stems: dict[str, np.ndarray]) -> float:
        return float(np.mean(np.abs(stems["percussive"])) / (np.mean(np.abs(stems["harmonic"])) + 1e-9))

    @staticmethod
    def _write_audio_outputs(
        session_audio_dir: Path,
        source_audio: np.ndarray,
        analysis_audio: np.ndarray,
        stems: dict[str, np.ndarray],
        sr: int,
        detected_bpm: float,
        target_bpm: float | None,
        detected_root: str,
        target_root: str,
        auto_pitch_time: bool,
    ) -> list[Path]:
        files: list[Path] = []
        original_path = session_audio_dir / "original.wav"
        save_wav(original_path, source_audio, sr)
        files.append(original_path)

        analysis_input_path = session_audio_dir / "analysis_input.wav"
        save_wav(analysis_input_path, analysis_audio, sr)
        files.append(analysis_input_path)

        harmonic_path = session_audio_dir / "spliced_harmonic.wav"
        percussive_path = session_audio_dir / "spliced_percussive.wav"
        save_wav(harmonic_path, stems["harmonic"], sr)
        save_wav(percussive_path, stems["percussive"], sr)
        files.extend([harmonic_path, percussive_path])

        boosted = np.clip(analysis_audio, -1.0, 1.0)
        boosted_path = session_audio_dir / "boosted.wav"
        save_wav(boosted_path, boosted, sr)
        files.append(boosted_path)

        if auto_pitch_time:
            retuned = retune_audio(
                source_audio,
                sr,
                detected_bpm=detected_bpm,
                target_bpm=target_bpm,
                detected_root=detected_root,
                target_root=target_root,
            )
            retuned_path = session_audio_dir / "retuned.wav"
            save_wav(retuned_path, retuned, sr)
            files.append(retuned_path)
        return files

    @staticmethod
    def _to_file_entry(
        path: Path,
        session_id: str,
        session_path: Path,
        run_id: str,
        selected: bool,
        with_base64: bool,
    ) -> FileEntry:
        rel = str(path.relative_to(session_path)).replace("\\", "/")
        is_midi = path.suffix.lower() == ".mid"
        mime = "audio/midi" if is_midi else "audio/wav"
        base64_data = encode_file_base64(path) if with_base64 else None
        return FileEntry(
            name=path.name,
            relative_path=rel,
            kind="midi" if is_midi else "audio",
            mime_type=mime,
            run_id=run_id,
            selected=selected,
            url=f"/api/v1/files/{session_id}/{rel}",
            base64=base64_data,
        )


def _to_pretty_json(data: dict[str, Any]) -> str:
    import json

    return json.dumps(data, indent=2)


def _mean_confidence(events: list[dict[str, Any]]) -> float:
    values = [float(event.get("confidence", 0.0)) for event in events]
    if not values:
        return 0.0
    return float(sum(values) / len(values))
