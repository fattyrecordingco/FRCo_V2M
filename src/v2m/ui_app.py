"""Dark, chat-first UI for the V2M producer copilot."""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from v2m.copilot_agent import ProducerCopilotAgent

UI_UPLOAD_DIR = Path("out/ui/uploads")
DEFAULT_PROJECTS_DIR = Path("projects")
ALLOWED_AUDIO_TYPES = ["wav", "mp3", "flac", "ogg", "m4a"]


def _inject_theme() -> None:
    st.markdown(
        """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&display=swap');

:root {
  --bg: #080d16;
  --panel: #111a2b;
  --panel-2: #162238;
  --border: #2a3a56;
  --text: #f2f7ff;
  --muted: #b5c4db;
  --accent: #5ac8ff;
}

html, body, [class*="css"] {
  font-family: 'Space Grotesk', sans-serif;
  color: var(--text) !important;
}

[data-testid="stAppViewContainer"] {
  background: radial-gradient(circle at 18% 0%, #1a2942 0%, var(--bg) 48%);
}

[data-testid="stHeader"] {
  background: transparent;
}

[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #0f1727 0%, #0b111d 100%);
  border-right: 1px solid var(--border);
}

p, li, h1, h2, h3, h4, h5, h6, label, span, div {
  color: var(--text);
}

[data-testid="stChatMessage"] {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 14px;
}

[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] p,
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] li {
  color: var(--text) !important;
}

.v2m-card {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 12px 14px;
}

.v2m-muted {
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
  background: #1a2a42 !important;
  color: var(--text) !important;
  border: 1px solid #365173 !important;
  border-radius: 10px !important;
}

.stButton > button:hover,
.stDownloadButton > button:hover {
  border-color: var(--accent) !important;
}

hr {
  border-color: var(--border) !important;
}
</style>
        """,
        unsafe_allow_html=True,
    )


def _init_state() -> None:
    if "messages" not in st.session_state:
        st.session_state["messages"] = []
    if "audio_inputs" not in st.session_state:
        st.session_state["audio_inputs"] = {}
    if "active_project" not in st.session_state:
        st.session_state["active_project"] = ""
    if "llm_model" not in st.session_state:
        st.session_state["llm_model"] = os.getenv("V2M_LLM_MODEL", "gpt-4.1-mini")
    if "api_key" not in st.session_state:
        st.session_state["api_key"] = os.getenv("OPENAI_API_KEY", "")

    if not st.session_state["messages"]:
        intro = (
            "I am your V2M Producer Copilot. I help you turn rough musical ideas into DAW-ready output.\n\n"
            "What I can do:\n"
            "- Analyze your hum/beatbox audio into melody + drum MIDI\n"
            "- Suggest chords, arrangement flow, and sound layers\n"
            "- Generate quick MIDI sketches if you do not have an audio idea yet\n"
            "- Guide you step-by-step like a producer in the room\n\n"
            "Example prompts:\n"
            "- Analyze my latest upload and make a chill lofi groove\n"
            "- Build a slow Indian-influenced outro from this machine texture\n"
            "- Give me chord and layering options for this melody\n"
            "- Make this beatbox pattern tighter but still human"
        )
        st.session_state["messages"] = [
            {
                "role": "assistant",
                "content": intro,
                "kind": "intro",
            }
        ]


def _push_message(role: str, content: str, **meta: str) -> None:
    payload: dict[str, str] = {"role": role, "content": content}
    for key, value in meta.items():
        payload[key] = str(value)
    st.session_state["messages"].append(payload)


def _audio_format(path: Path) -> str:
    mapping = {
        ".wav": "audio/wav",
        ".mp3": "audio/mpeg",
        ".ogg": "audio/ogg",
        ".flac": "audio/flac",
        ".m4a": "audio/mp4",
    }
    return mapping.get(path.suffix.lower(), "audio/wav")


def _save_upload(file_obj, prefix: str) -> tuple[str, Path]:
    UI_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    suffix = Path(file_obj.name).suffix or ".wav"
    stem = Path(file_obj.name).stem.replace(" ", "-")
    audio_id = f"{prefix}-{len(st.session_state['audio_inputs']) + 1:02d}"
    output = UI_UPLOAD_DIR / f"{audio_id}-{stem}{suffix}"
    output.write_bytes(file_obj.getvalue())
    return audio_id, output


def _render_project_outputs(project_dir: Path, key_prefix: str) -> None:
    analysis = project_dir / "analysis.json"
    if not analysis.exists():
        st.warning(f"No analysis.json found in {project_dir}")
        return

    import json

    payload = json.loads(analysis.read_text(encoding="utf-8"))
    outputs = payload.get("midi_outputs", {})
    melody = Path(str(outputs.get("melody", project_dir / "midi" / "melody.mid")))
    drums = Path(str(outputs.get("drums", project_dir / "midi" / "drums.mid")))
    combined = Path(str(outputs.get("combined", project_dir / "midi" / "combined.mid")))
    recipe = Path(str(payload.get("recipe_path", project_dir / "recipe.md")))
    raw_audio = Path(str(payload.get("input_audio", project_dir / "audio" / "raw.wav")))
    cleaned_audio = Path(str(payload.get("cleaned_audio", project_dir / "audio" / "cleaned.wav")))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tempo", f"{payload.get('tempo_bpm', '?')} BPM")
    c2.metric("Key", str(payload.get("detected_key", "?")))
    c3.metric("Melody", int(payload.get("melody_event_count", 0)))
    c4.metric("Drums", int(payload.get("drum_event_count", 0)))

    d1, d2, d3 = st.columns(3)
    with d1:
        if melody.exists():
            st.download_button(
                "Melody MIDI",
                melody.read_bytes(),
                file_name=melody.name,
                mime="audio/midi",
                key=f"{key_prefix}-melody",
            )
    with d2:
        if drums.exists():
            st.download_button(
                "Drums MIDI",
                drums.read_bytes(),
                file_name=drums.name,
                mime="audio/midi",
                key=f"{key_prefix}-drums",
            )
    with d3:
        if combined.exists():
            st.download_button(
                "Combined MIDI",
                combined.read_bytes(),
                file_name=combined.name,
                mime="audio/midi",
                key=f"{key_prefix}-combined",
            )

    with st.expander("Recipe", expanded=False):
        st.code(recipe.read_text(encoding="utf-8") if recipe.exists() else "No recipe file.", language="markdown")

    with st.expander("Audio Preview", expanded=False):
        if raw_audio.exists():
            st.caption("Raw")
            st.audio(raw_audio.read_bytes(), format=_audio_format(raw_audio))
        if cleaned_audio.exists():
            st.caption("Cleaned")
            st.audio(cleaned_audio.read_bytes(), format=_audio_format(cleaned_audio))


def _render_messages() -> None:
    for idx, msg in enumerate(st.session_state["messages"]):
        role = "assistant" if msg.get("role") == "assistant" else "user"
        with st.chat_message(role):
            st.markdown(msg.get("content", ""))
            project_dir = msg.get("project_dir", "").strip()
            if project_dir:
                path = Path(project_dir)
                if path.exists():
                    _render_project_outputs(path, key_prefix=f"m{idx}")

            sketch_path = msg.get("sketch_path", "").strip()
            if sketch_path:
                sketch = Path(sketch_path)
                if sketch.exists():
                    st.download_button(
                        "Download Sketch MIDI",
                        sketch.read_bytes(),
                        file_name=sketch.name,
                        mime="audio/midi",
                        key=f"m{idx}-sketch",
                    )


def _sidebar_controls() -> None:
    with st.sidebar:
        st.markdown("## Copilot Settings")
        st.session_state["api_key"] = st.text_input(
            "OpenAI API Key",
            value=st.session_state.get("api_key", ""),
            type="password",
        )
        st.session_state["llm_model"] = st.text_input(
            "Model",
            value=st.session_state.get("llm_model", "gpt-4.1-mini"),
        )
        st.caption("Set `OPENAI_API_KEY` to enable real LLM tool-calling responses.")

        st.markdown("---")
        st.markdown("### Context")
        st.write(f"Audio Inputs: {len(st.session_state['audio_inputs'])}")
        active = st.session_state.get("active_project", "")
        st.write(f"Active Project: {Path(active).name if active else 'None'}")

        if st.button("Clear Chat", use_container_width=True):
            st.session_state["messages"] = []
            st.session_state["audio_inputs"] = {}
            st.session_state["active_project"] = ""
            st.rerun()


def _handle_user_turn() -> None:
    chat_value = st.chat_input(
        "Message your producer copilot...",
        accept_file="multiple",
        file_type=ALLOWED_AUDIO_TYPES,
        accept_audio=True,
    )

    if chat_value is None:
        return

    if isinstance(chat_value, str):
        user_text = chat_value
        files = []
        audio = None
    else:
        user_text = chat_value.text
        files = list(chat_value.files)
        audio = chat_value.audio

    if audio is not None:
        files.append(audio)

    new_ids: list[str] = []
    for index, file_obj in enumerate(files, start=1):
        audio_id, path = _save_upload(file_obj, prefix=f"audio-{index}")
        st.session_state["audio_inputs"][audio_id] = str(path)
        new_ids.append(audio_id)

    if new_ids:
        _push_message(
            "assistant",
            "Added new audio inputs: " + ", ".join(f"`{item}`" for item in new_ids),
        )

    prompt = user_text.strip()
    if not prompt and new_ids:
        prompt = "Analyze the latest uploaded audio and build a project pack."
    if not prompt:
        return

    _push_message("user", prompt)

    agent = ProducerCopilotAgent(
        api_key=st.session_state.get("api_key", ""),
        model=st.session_state.get("llm_model", "gpt-4.1-mini"),
        projects_dir=DEFAULT_PROJECTS_DIR,
        sketch_dir="out/ui",
    )

    plain_history = [
        {"role": msg.get("role", "user"), "content": msg.get("content", "")}
        for msg in st.session_state["messages"]
        if msg.get("role") in {"user", "assistant"}
    ]

    audio_map = {key: Path(value) for key, value in st.session_state["audio_inputs"].items()}
    active = st.session_state.get("active_project", "").strip()
    active_path = Path(active) if active else None

    with st.spinner("Copilot is thinking..."):
        result = agent.run_turn(
            chat_history=plain_history,
            user_prompt=prompt,
            audio_inputs=audio_map,
            active_project=active_path,
        )

    meta: dict[str, str] = {}
    if result.active_project is not None:
        st.session_state["active_project"] = str(result.active_project)
        meta["project_dir"] = str(result.active_project)
    if result.generated_sketch is not None:
        meta["sketch_path"] = str(result.generated_sketch)
    if result.tool_trace:
        trace = ", ".join(result.tool_trace)
        content = f"{result.assistant_text}\n\nExtensions used: `{trace}`"
    else:
        content = result.assistant_text

    _push_message("assistant", content, **meta)
    st.rerun()


def main() -> None:
    st.set_page_config(page_title="V2M Producer Copilot", layout="wide")
    _inject_theme()
    _init_state()
    _sidebar_controls()

    st.markdown("# V2M Producer Copilot")
    st.markdown(
        "<div class='v2m-card'>"
        "Everything is chat-driven: upload/record in the message box, then ask naturally. "
        "The copilot calls analysis, arrangement, harmony, groove, and sketch extensions for you."
        "</div>",
        unsafe_allow_html=True,
    )

    _render_messages()
    _handle_user_turn()


if __name__ == "__main__":
    main()
