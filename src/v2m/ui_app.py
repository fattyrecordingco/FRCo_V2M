"""Dark, chat-first UI for the V2M producer copilot."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re

import streamlit as st

from v2m.audio_to_midi import PrototypeProjectResult, analyze_audio_to_project
from v2m.generator import STYLE_PRESETS, generate_idea
from v2m.midi_export import export_idea_to_midi
from v2m.music_theory import list_supported_keys

UI_OUT_DIR = Path("out/ui")
UI_UPLOAD_DIR = UI_OUT_DIR / "uploads"
DEFAULT_PROJECTS_DIR = Path("projects")


ChatMessage = dict[str, str]


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return normalized or "session"


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _safe_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _list_projects(base_dir: Path) -> list[Path]:
    if not base_dir.exists():
        return []
    return sorted([p for p in base_dir.iterdir() if p.is_dir()], reverse=True)


def _inject_theme() -> None:
    st.markdown(
        """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&display=swap');

:root {
  --bg: #0a0e14;
  --panel: #111826;
  --panel-2: #151f30;
  --border: #2a3648;
  --text: #f5f8ff;
  --muted: #b7c4d8;
  --accent: #4ec5ff;
  --accent-2: #55e4a6;
}

html, body, [class*="css"] {
  font-family: 'Space Grotesk', sans-serif;
  color: var(--text) !important;
}

[data-testid="stAppViewContainer"] {
  background: radial-gradient(circle at 20% 0%, #162235 0%, var(--bg) 45%);
}

[data-testid="stHeader"] {
  background: transparent;
}

[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #101826 0%, #0c121d 100%);
  border-right: 1px solid var(--border);
}

.stMarkdown, .stText, .stCaption, label, p, li, h1, h2, h3, h4 {
  color: var(--text) !important;
}

[data-testid="stChatMessage"] {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 14px;
}

[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] p {
  color: var(--text) !important;
}

.v2m-badge {
  display: inline-block;
  background: #16314a;
  border: 1px solid #2e4f70;
  border-radius: 999px;
  color: #bde8ff;
  padding: 4px 10px;
  font-size: 12px;
  margin-bottom: 6px;
}

.v2m-card {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 12px 14px;
}

.v2m-small {
  color: var(--muted);
  font-size: 13px;
}

.stTextInput > div > div > input,
.stTextArea textarea {
  background: var(--panel-2) !important;
  color: var(--text) !important;
  border: 1px solid var(--border) !important;
}

.stSelectbox div[data-baseweb="select"] > div,
.stMultiSelect div[data-baseweb="select"] > div {
  background: var(--panel-2) !important;
  border: 1px solid var(--border) !important;
}

.stButton > button,
.stDownloadButton > button {
  background: #18263a !important;
  color: var(--text) !important;
  border: 1px solid #314763 !important;
  border-radius: 10px !important;
}

.stButton > button:hover,
.stDownloadButton > button:hover {
  border-color: var(--accent) !important;
  color: #ffffff !important;
}

.st-emotion-cache-16txtl3 h1,
.st-emotion-cache-16txtl3 h2,
.st-emotion-cache-16txtl3 h3,
.st-emotion-cache-16txtl3 p {
  color: var(--text);
}

hr {
  border-color: var(--border);
}
</style>
        """,
        unsafe_allow_html=True,
    )


def _init_state() -> None:
    if "messages" not in st.session_state:
        st.session_state["messages"] = [
            {
                "role": "assistant",
                "content": (
                    "I am your V2M Producer Copilot. Record or upload your idea from the sidebar, "
                    "and I will turn it into melody and drum MIDI plus a DAW-ready recipe."
                ),
                "kind": "text",
            }
        ]
    if "active_project" not in st.session_state:
        st.session_state["active_project"] = ""
    if "projects_dir" not in st.session_state:
        st.session_state["projects_dir"] = str(DEFAULT_PROJECTS_DIR)


def _push_message(role: str, content: str, kind: str = "text", meta: dict | None = None) -> None:
    message: dict[str, str] = {"role": role, "content": content, "kind": kind}
    if meta:
        for key, value in meta.items():
            message[key] = str(value)
    st.session_state["messages"].append(message)


def _project_assets(project_dir: Path) -> dict[str, Path]:
    analysis = project_dir / "analysis.json"
    payload = _safe_json(analysis)
    midi = payload.get("midi_outputs", {}) if isinstance(payload, dict) else {}

    return {
        "analysis": analysis,
        "recipe": Path(str(payload.get("recipe_path", project_dir / "recipe.md"))),
        "melody": Path(str(midi.get("melody", project_dir / "midi" / "melody.mid"))),
        "drums": Path(str(midi.get("drums", project_dir / "midi" / "drums.mid"))),
        "combined": Path(str(midi.get("combined", project_dir / "midi" / "combined.mid"))),
        "raw_audio": Path(str(payload.get("input_audio", project_dir / "audio" / "raw.wav"))),
        "cleaned_audio": Path(str(payload.get("cleaned_audio", project_dir / "audio" / "cleaned.wav"))),
    }


def _download_button(path: Path, label: str, key: str, mime: str = "application/octet-stream") -> None:
    if path.exists():
        st.download_button(
            label=label,
            data=path.read_bytes(),
            file_name=path.name,
            mime=mime,
            key=key,
        )


def _audio_format(path: Path) -> str:
    suffix = path.suffix.lower()
    mapping = {
        ".wav": "audio/wav",
        ".mp3": "audio/mpeg",
        ".ogg": "audio/ogg",
        ".flac": "audio/flac",
        ".m4a": "audio/mp4",
    }
    return mapping.get(suffix, "audio/wav")


def _compose_reply(prompt: str, active_project: Path | None) -> str:
    lower = prompt.lower()
    used_extensions: list[str] = []
    suggestions: list[str] = []

    if any(token in lower for token in ["arrange", "structure", "section", "song form"]):
        used_extensions.append("Arrangement Planner")
        suggestions.extend(
            [
                "Map your idea into 8-bar blocks: intro, verse, pre, hook.",
                "Mute drums for the first 4 bars, then re-introduce with hats only.",
                "Add a contrast section with a half-time drum variant.",
            ]
        )

    if any(token in lower for token in ["sound", "synth", "layer", "texture", "mix"]):
        used_extensions.append("Sound Stack Engine")
        suggestions.extend(
            [
                "Primary layer: mono lead for definition.",
                "Secondary layer: airy pad with high-pass filter.",
                "Third layer: transient pluck for rhythmic clarity.",
            ]
        )

    if any(token in lower for token in ["chord", "harmony", "progression"]):
        used_extensions.append("Harmony Guide")
        suggestions.extend(
            [
                "Try two harmonic routes and keep the one that supports your melody contour.",
                "Route A: i - bVII - bVI - bVI",
                "Route B: i - VI - III - VII",
            ]
        )

    if any(token in lower for token in ["drum", "beat", "groove", "rhythm"]):
        used_extensions.append("Groove Refiner")
        suggestions.extend(
            [
                "Duplicate your drum MIDI and offset the second hats track by 5-12 ms.",
                "Lower kick velocity on every second hit to create movement.",
                "Use 60-80% quantization for a human feel.",
            ]
        )

    if not suggestions:
        used_extensions.append("Producer Copilot")
        suggestions.extend(
            [
                "Start from your analyzed melody and drums, then build one bass line before adding extra layers.",
                "Commit one 8-bar loop first, then duplicate and mutate the second loop.",
                "Keep your first pass fast; refine sound design after arrangement is stable.",
            ]
        )

    project_hint = ""
    if active_project and active_project.exists():
        payload = _safe_json(active_project / "analysis.json")
        project_hint = (
            f"\nCurrent project context: {payload.get('tempo_bpm', '?')} BPM, "
            f"{payload.get('detected_key', '?')} key, "
            f"{payload.get('melody_event_count', 0)} melody events, "
            f"{payload.get('drum_event_count', 0)} drum events."
        )
    else:
        project_hint = "\nNo active analysis yet. Record or upload one idea in the sidebar first."

    body = "\n".join(f"- {item}" for item in suggestions[:5])
    extension_line = ", ".join(dict.fromkeys(used_extensions))
    return (
        f"Extensions used: `{extension_line}`{project_hint}\n\n"
        f"Recommended next steps:\n{body}"
    )


def _run_audio_analysis(
    *,
    source_bytes: bytes,
    source_name: str,
    project_name: str,
    projects_dir: str,
    scale_mode: str,
    manual_key: str,
    genre_tags: list[str],
    quantize_strength: float,
) -> PrototypeProjectResult:
    UI_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    suffix = Path(source_name).suffix or ".wav"
    upload_name = f"{_timestamp()}-{_slugify(Path(source_name).stem)}{suffix}"
    upload_path = UI_UPLOAD_DIR / upload_name
    upload_path.write_bytes(source_bytes)

    return analyze_audio_to_project(
        input_audio_path=upload_path,
        projects_dir=projects_dir,
        project_name=project_name,
        scale_mode=scale_mode,
        manual_key=manual_key,
        genre_tags=genre_tags,
        quantize_strength=quantize_strength,
    )


def _run_quick_sketch(style: str, key: str, bpm: int, bars: int, complexity: int) -> Path:
    idea = generate_idea(style=style, key=key, bpm=bpm, bars=bars, complexity=complexity)
    UI_OUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = UI_OUT_DIR / f"{_timestamp()}-sketch-{_slugify(style)}.mid"
    export_idea_to_midi(idea, output_path)
    return output_path


def _render_project_bundle(project_dir: Path, key_prefix: str) -> None:
    assets = _project_assets(project_dir)
    payload = _safe_json(assets["analysis"])

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tempo", f"{payload.get('tempo_bpm', '?')} BPM")
    c2.metric("Key", str(payload.get("detected_key", "?")))
    c3.metric("Melody", int(payload.get("melody_event_count", 0)))
    c4.metric("Drums", int(payload.get("drum_event_count", 0)))

    d1, d2, d3 = st.columns(3)
    with d1:
        _download_button(assets["melody"], "Melody MIDI", key=f"{key_prefix}-melody", mime="audio/midi")
    with d2:
        _download_button(assets["drums"], "Drums MIDI", key=f"{key_prefix}-drums", mime="audio/midi")
    with d3:
        _download_button(assets["combined"], "Combined MIDI", key=f"{key_prefix}-combined", mime="audio/midi")

    with st.expander("Recipe Card", expanded=False):
        st.code(_read_text(assets["recipe"]), language="markdown")

    with st.expander("Audio Preview", expanded=False):
        if assets["raw_audio"].exists():
            st.caption("Raw input")
            st.audio(assets["raw_audio"].read_bytes(), format=_audio_format(assets["raw_audio"]))
        if assets["cleaned_audio"].exists():
            st.caption("Cleaned")
            st.audio(assets["cleaned_audio"].read_bytes(), format=_audio_format(assets["cleaned_audio"]))

    with st.expander("Analysis JSON", expanded=False):
        st.json(payload)


def _render_messages() -> None:
    for idx, msg in enumerate(st.session_state["messages"]):
        role = msg.get("role", "assistant")
        with st.chat_message("assistant" if role == "assistant" else "user"):
            if msg.get("kind") == "project":
                st.markdown(msg.get("content", ""))
                project_dir = Path(msg.get("project_dir", ""))
                if project_dir.exists():
                    _render_project_bundle(project_dir, key_prefix=f"m{idx}")
            elif msg.get("kind") == "midi_sketch":
                st.markdown(msg.get("content", ""))
                midi_path = Path(msg.get("midi_path", ""))
                _download_button(midi_path, "Download Sketch MIDI", key=f"m{idx}-sketch", mime="audio/midi")
            else:
                st.markdown(msg.get("content", ""))


def _render_sidebar() -> None:
    with st.sidebar:
        st.markdown("## V2M Producer Copilot")
        st.markdown("<div class='v2m-small'>Main action: Audio to DAW package</div>", unsafe_allow_html=True)

        st.markdown("### Analyze Audio")
        recorded = st.audio_input("Record idea")
        uploaded = st.file_uploader("or Upload audio", type=["wav", "mp3", "flac", "ogg", "m4a"])

        default_name = f"idea-{datetime.now().strftime('%H%M')}"
        project_name = st.text_input("Project name", value=default_name)
        tags_text = st.text_input("Genre tags", value="trap,experimental")

        with st.expander("Advanced analysis settings", expanded=False):
            scale_mode = st.selectbox("Scale mode", ["auto", "manual"], index=0)
            manual_key = st.text_input("Manual key", value="C major")
            quantize_strength = st.slider("Quantize strength", min_value=0.0, max_value=1.0, value=0.9)
            st.session_state["projects_dir"] = st.text_input(
                "Projects directory",
                value=st.session_state.get("projects_dir", str(DEFAULT_PROJECTS_DIR)),
            )
            st.caption("Supported scales: " + ", ".join(list_supported_keys()))

        source = recorded if recorded is not None else uploaded
        if st.button("Analyze and Create Project", use_container_width=True, type="primary"):
            if source is None:
                _push_message("assistant", "Please record or upload audio first.")
                st.rerun()

            _push_message("user", "Convert this idea into a production-ready toolkit.")
            tags = [tag.strip() for tag in tags_text.split(",") if tag.strip()]
            try:
                with st.spinner("Analyzing and generating files..."):
                    result = _run_audio_analysis(
                        source_bytes=source.getvalue(),
                        source_name=source.name,
                        project_name=project_name,
                        projects_dir=st.session_state["projects_dir"],
                        scale_mode=scale_mode,
                        manual_key=manual_key,
                        genre_tags=tags,
                        quantize_strength=quantize_strength,
                    )
            except Exception as exc:  # noqa: BLE001
                _push_message("assistant", f"Analysis failed: {exc}")
            else:
                st.session_state["active_project"] = str(result.project_dir)
                summary = (
                    "Analysis complete. Extensions used: `Audio Cleanup`, `Groove Translator`, `Recipe Builder`."
                    f"\n\nProject: `{result.project_dir}`"
                    f"\nDetected: `{result.tempo_bpm} BPM`, `{result.detected_key}`"
                )
                _push_message(
                    "assistant",
                    summary,
                    kind="project",
                    meta={"project_dir": str(result.project_dir)},
                )
            st.rerun()

        st.markdown("---")
        st.markdown("### Load Existing Project")
        projects = _list_projects(Path(st.session_state.get("projects_dir", str(DEFAULT_PROJECTS_DIR))))
        if projects:
            selected = st.selectbox("Project", [p.name for p in projects], key="project_selector")
            if st.button("Load Project", use_container_width=True):
                project_dir = next((p for p in projects if p.name == selected), projects[0])
                st.session_state["active_project"] = str(project_dir)
                _push_message(
                    "assistant",
                    f"Loaded project `{project_dir.name}`. Ask me for arrangement, harmony, or sound-layer help.",
                    kind="project",
                    meta={"project_dir": str(project_dir)},
                )
                st.rerun()
        else:
            st.caption("No projects found yet.")

        st.markdown("---")
        st.markdown("### Quick Sketch Extension")
        style = st.selectbox("Style", sorted(STYLE_PRESETS.keys()), index=0)
        sketch_key = st.text_input("Sketch key", value="C major")
        bpm = st.slider("Sketch BPM", min_value=50, max_value=220, value=120)
        bars = st.slider("Sketch bars", min_value=1, max_value=16, value=8)
        complexity = st.slider("Sketch complexity", min_value=1, max_value=10, value=6)
        if st.button("Generate Sketch MIDI", use_container_width=True):
            try:
                midi_path = _run_quick_sketch(style=style, key=sketch_key, bpm=bpm, bars=bars, complexity=complexity)
            except Exception as exc:  # noqa: BLE001
                _push_message("assistant", f"Could not generate sketch: {exc}")
            else:
                _push_message(
                    "assistant",
                    (
                        "Sketch generated. Extensions used: `Idea Generator`. "
                        "Use this as a starting point if you do not have a recording yet."
                    ),
                    kind="midi_sketch",
                    meta={"midi_path": str(midi_path)},
                )
            st.rerun()


def _handle_quick_actions() -> None:
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Suggest Arrangement", use_container_width=True):
            prompt = "Give me an arrangement plan for this idea"
            _push_message("user", prompt)
            active = Path(st.session_state.get("active_project", ""))
            _push_message("assistant", _compose_reply(prompt, active if active.exists() else None))
            st.rerun()
    with c2:
        if st.button("Suggest Sound Stack", use_container_width=True):
            prompt = "How should I layer sounds and textures for this track"
            _push_message("user", prompt)
            active = Path(st.session_state.get("active_project", ""))
            _push_message("assistant", _compose_reply(prompt, active if active.exists() else None))
            st.rerun()
    with c3:
        if st.button("Improve Groove", use_container_width=True):
            prompt = "How can I improve drum groove and rhythm feel"
            _push_message("user", prompt)
            active = Path(st.session_state.get("active_project", ""))
            _push_message("assistant", _compose_reply(prompt, active if active.exists() else None))
            st.rerun()


def main() -> None:
    st.set_page_config(page_title="V2M Producer Copilot", layout="wide")
    _inject_theme()
    _init_state()
    _render_sidebar()

    st.markdown("# V2M Producer Copilot")
    st.markdown(
        "<div class='v2m-card'>"
        "Main workflow: analyze your hum/beatbox idea, then iterate with chat guidance and built-in producer extensions."
        "</div>",
        unsafe_allow_html=True,
    )

    active_project = Path(st.session_state.get("active_project", ""))
    if active_project.exists():
        st.markdown(
            f"<div class='v2m-badge'>Active Project: {active_project.name}</div>",
            unsafe_allow_html=True,
        )

    _handle_quick_actions()
    _render_messages()

    prompt = st.chat_input("Ask your producer copilot anything about arrangement, harmony, groove, and sound design...")
    if prompt:
        _push_message("user", prompt)
        active = Path(st.session_state.get("active_project", ""))
        _push_message("assistant", _compose_reply(prompt, active if active.exists() else None))
        st.rerun()


if __name__ == "__main__":
    main()
