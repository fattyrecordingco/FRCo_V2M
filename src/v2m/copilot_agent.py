"""LLM-backed music producer copilot with tool orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import re
from typing import Any

from .audio_to_midi import analyze_audio_to_project
from .generator import STYLE_PRESETS, generate_idea
from .midi_export import export_idea_to_midi

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - dependency optional until installed
    OpenAI = None  # type: ignore[assignment]


DEFAULT_MODEL = os.getenv("V2M_LLM_MODEL", "gpt-4.1-mini")


@dataclass
class AgentTurnResult:
    assistant_text: str
    active_project: Path | None = None
    generated_sketch: Path | None = None
    tool_trace: list[str] | None = None
    error: str | None = None


class ProducerCopilotAgent:
    """Tool-using assistant that can analyze audio and guide production decisions."""

    def __init__(
        self,
        *,
        api_key: str | None,
        model: str | None = None,
        projects_dir: str | Path = "projects",
        sketch_dir: str | Path = "out/ui",
    ) -> None:
        self.api_key = (api_key or "").strip()
        self.model = (model or DEFAULT_MODEL).strip()
        self.projects_dir = Path(projects_dir)
        self.sketch_dir = Path(sketch_dir)

        self._client = None
        if self.api_key and OpenAI is not None:
            self._client = OpenAI(api_key=self.api_key)

    @property
    def llm_enabled(self) -> bool:
        return self._client is not None

    def introduction_message(self) -> str:
        return (
            "I am your V2M Producer Copilot. I can convert hums/beatbox into MIDI, suggest harmony, "
            "arrange sections, and propose sound-layer stacks.\n\n"
            "Example prompts:\n"
            "- Analyze my latest uploaded audio and turn it into melody + drums MIDI.\n"
            "- Build an outro inspired by this machine texture, cinematic and Indian-influenced.\n"
            "- Suggest a chord progression and layer plan for this melody.\n"
            "- Tighten this groove but keep a human feel.\n"
            "- Generate a quick trap sketch in A minor at 140 BPM."
        )

    def run_turn(
        self,
        *,
        chat_history: list[dict[str, str]],
        user_prompt: str,
        audio_inputs: dict[str, Path],
        active_project: Path | None,
    ) -> AgentTurnResult:
        if not self.llm_enabled:
            return AgentTurnResult(
                assistant_text=(
                    "LLM is not enabled yet. Add `OPENAI_API_KEY` to run the real AI copilot. "
                    "I can still guide basic next steps: analyze one uploaded audio input first, then ask for "
                    "arrangement/harmony/groove advice."
                ),
                active_project=active_project,
            )

        return self._run_llm_turn(
            chat_history=chat_history,
            user_prompt=user_prompt,
            audio_inputs=audio_inputs,
            active_project=active_project,
        )

    def _system_prompt(self, *, audio_ids: list[str], active_project: Path | None) -> str:
        active_text = str(active_project) if active_project else "none"
        return (
            "You are V2M Producer Copilot, an elite music-production AI assistant.\n"
            "Primary mission: bridge artist skill gaps by turning rough ideas into concrete DAW actions.\n"
            "Always be practical, concise, and production-oriented.\n"
            "When useful, call tools to analyze audio, inspect project context, load projects, or generate sketches.\n"
            "After tool use, explain what was done and give clear next actions.\n"
            "Mention extension modules used in your response when tools were invoked.\n"
            f"Available audio input ids: {audio_ids}\n"
            f"Current active project path: {active_text}\n"
        )

    def _tool_schemas(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "list_audio_inputs",
                    "description": "List uploaded/recorded audio input ids available for analysis.",
                    "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "analyze_audio",
                    "description": "Analyze one uploaded audio idea and create MIDI + recipe project artifacts.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "audio_id": {"type": "string"},
                            "project_name": {"type": "string"},
                            "genre_tags": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "scale_mode": {"type": "string", "enum": ["auto", "manual"]},
                            "manual_key": {"type": "string"},
                            "quantize_strength": {"type": "number"},
                        },
                        "required": ["audio_id"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "list_projects",
                    "description": "List existing analyzed projects.",
                    "parameters": {
                        "type": "object",
                        "properties": {"limit": {"type": "integer"}},
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "load_project",
                    "description": "Load a project by folder name.",
                    "parameters": {
                        "type": "object",
                        "properties": {"project_name": {"type": "string"}},
                        "required": ["project_name"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_project_snapshot",
                    "description": "Get summarized data from active or named project.",
                    "parameters": {
                        "type": "object",
                        "properties": {"project_name": {"type": "string"}},
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "generate_midi_sketch",
                    "description": "Generate a quick style-based MIDI sketch.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "style": {"type": "string", "enum": sorted(STYLE_PRESETS.keys())},
                            "key": {"type": "string"},
                            "bpm": {"type": "integer"},
                            "bars": {"type": "integer"},
                            "complexity": {"type": "integer"},
                        },
                        "required": ["style"],
                        "additionalProperties": False,
                    },
                },
            },
        ]

    def _run_llm_turn(
        self,
        *,
        chat_history: list[dict[str, str]],
        user_prompt: str,
        audio_inputs: dict[str, Path],
        active_project: Path | None,
    ) -> AgentTurnResult:
        assert self._client is not None

        tool_trace: list[str] = []
        current_project = active_project
        generated_sketch: Path | None = None

        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": self._system_prompt(
                    audio_ids=sorted(audio_inputs.keys()),
                    active_project=current_project,
                ),
            }
        ]
        for item in chat_history[-12:]:
            role = item.get("role", "user")
            if role not in {"user", "assistant"}:
                continue
            messages.append({"role": role, "content": item.get("content", "")})
        messages.append({"role": "user", "content": user_prompt})

        max_rounds = 4
        final_text = ""
        for _ in range(max_rounds):
            completion = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self._tool_schemas(),
                tool_choice="auto",
                temperature=0.35,
            )
            assistant_msg = completion.choices[0].message
            tool_calls = assistant_msg.tool_calls or []

            if tool_calls:
                messages.append(
                    {
                        "role": "assistant",
                        "content": assistant_msg.content or "",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": tc.type,
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                },
                            }
                            for tc in tool_calls
                        ],
                    }
                )

                for tc in tool_calls:
                    name = tc.function.name
                    try:
                        raw_args = json.loads(tc.function.arguments or "{}")
                    except json.JSONDecodeError:
                        raw_args = {}
                    result, current_project, generated_sketch = self._execute_tool(
                        name=name,
                        args=raw_args,
                        audio_inputs=audio_inputs,
                        active_project=current_project,
                        existing_sketch=generated_sketch,
                    )
                    tool_trace.append(name)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps(result),
                        }
                    )
                continue

            final_text = assistant_msg.content or ""
            break

        if not final_text:
            final_text = (
                "I completed tool calls, but the final language response was empty. "
                "Please ask me to summarize the current project and next steps."
            )

        return AgentTurnResult(
            assistant_text=final_text,
            active_project=current_project,
            generated_sketch=generated_sketch,
            tool_trace=tool_trace,
        )

    def _execute_tool(
        self,
        *,
        name: str,
        args: dict[str, Any],
        audio_inputs: dict[str, Path],
        active_project: Path | None,
        existing_sketch: Path | None,
    ) -> tuple[dict[str, Any], Path | None, Path | None]:
        current_project = active_project
        sketch = existing_sketch

        if name == "list_audio_inputs":
            return {"audio_inputs": sorted(audio_inputs.keys())}, current_project, sketch

        if name == "analyze_audio":
            audio_id = str(args.get("audio_id", "")).strip()
            if not audio_id and len(audio_inputs) == 1:
                audio_id = next(iter(audio_inputs.keys()))
            source = audio_inputs.get(audio_id)
            if source is None:
                return (
                    {
                        "error": (
                            f"audio_id '{audio_id}' not found. "
                            f"Available ids: {sorted(audio_inputs.keys())}"
                        )
                    },
                    current_project,
                    sketch,
                )

            project_name = str(args.get("project_name", "session")).strip() or "session"
            scale_mode = str(args.get("scale_mode", "auto")).strip()
            manual_key = str(args.get("manual_key", "C major")).strip()
            quantize = float(args.get("quantize_strength", 0.9))
            genre_tags_raw = args.get("genre_tags", [])
            genre_tags: list[str]
            if isinstance(genre_tags_raw, list):
                genre_tags = [str(tag).strip() for tag in genre_tags_raw if str(tag).strip()]
            else:
                genre_tags = [str(genre_tags_raw).strip()] if str(genre_tags_raw).strip() else []

            result = analyze_audio_to_project(
                input_audio_path=source,
                projects_dir=self.projects_dir,
                project_name=project_name,
                scale_mode=scale_mode if scale_mode in {"auto", "manual"} else "auto",
                manual_key=manual_key or "C major",
                genre_tags=genre_tags,
                quantize_strength=max(0.0, min(1.0, quantize)),
            )
            current_project = result.project_dir
            return (
                {
                    "project_dir": str(result.project_dir),
                    "tempo_bpm": result.tempo_bpm,
                    "detected_key": result.detected_key,
                    "melody_events": result.melody_event_count,
                    "drum_events": result.drum_event_count,
                    "outputs": {
                        "melody": str(result.melody_midi_path),
                        "drums": str(result.drums_midi_path),
                        "combined": str(result.combined_midi_path),
                        "recipe": str(result.recipe_path),
                    },
                    "extensions_used": ["Audio Cleanup", "Groove Translator", "Recipe Builder"],
                },
                current_project,
                sketch,
            )

        if name == "list_projects":
            limit = int(args.get("limit", 20))
            projects = sorted([p for p in self.projects_dir.glob("*") if p.is_dir()], reverse=True)
            return (
                {
                    "projects": [p.name for p in projects[: max(1, limit)]],
                    "total": len(projects),
                },
                current_project,
                sketch,
            )

        if name == "load_project":
            project_name = str(args.get("project_name", "")).strip()
            candidate = self.projects_dir / project_name
            if not candidate.exists():
                return {"error": f"Project not found: {project_name}"}, current_project, sketch
            current_project = candidate
            return {"project_dir": str(candidate), "loaded": True}, current_project, sketch

        if name == "get_project_snapshot":
            project_name = str(args.get("project_name", "")).strip()
            target = current_project
            if project_name:
                maybe = self.projects_dir / project_name
                if maybe.exists():
                    target = maybe
            if target is None:
                return {"error": "No active project."}, current_project, sketch
            analysis_path = target / "analysis.json"
            payload = _safe_json(analysis_path)
            if not payload:
                return {"error": f"No analysis found for {target.name}."}, current_project, sketch
            return (
                {
                    "project_name": payload.get("project_name", target.name),
                    "tempo_bpm": payload.get("tempo_bpm"),
                    "detected_key": payload.get("detected_key"),
                    "genre_tags": payload.get("genre_tags", []),
                    "melody_event_count": payload.get("melody_event_count", 0),
                    "drum_event_count": payload.get("drum_event_count", 0),
                    "recipe_path": payload.get("recipe_path"),
                    "extensions_available": [
                        "Arrangement Planner",
                        "Harmony Guide",
                        "Sound Stack Engine",
                        "Groove Refiner",
                    ],
                },
                current_project,
                sketch,
            )

        if name == "generate_midi_sketch":
            style = str(args.get("style", "pop"))
            key = str(args.get("key", "C major"))
            bpm = int(args.get("bpm", 120))
            bars = int(args.get("bars", 8))
            complexity = int(args.get("complexity", 6))
            idea = generate_idea(
                style=style if style in STYLE_PRESETS else "pop",
                key=key,
                bpm=max(50, min(220, bpm)),
                bars=max(1, min(32, bars)),
                complexity=max(1, min(10, complexity)),
            )
            self.sketch_dir.mkdir(parents=True, exist_ok=True)
            sketch_path = self.sketch_dir / f"{_timestamp()}-sketch-{_slugify(style)}.mid"
            export_idea_to_midi(idea, sketch_path)
            sketch = sketch_path
            return (
                {
                    "sketch_midi": str(sketch_path),
                    "style": style,
                    "key": key,
                    "bpm": bpm,
                    "bars": bars,
                    "extensions_used": ["Idea Generator"],
                },
                current_project,
                sketch,
            )

        return {"error": f"Unknown tool: {name}"}, current_project, sketch


def _safe_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return normalized or "session"


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")
