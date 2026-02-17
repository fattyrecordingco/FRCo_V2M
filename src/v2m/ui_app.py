"""Interactive UI for the V2M prototype."""

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


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return normalized or "session"


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _styled_header() -> None:
    st.markdown(
        """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&display=swap');
html, body, [class*="css"] {
  font-family: 'Space Grotesk', sans-serif;
}
[data-testid="stAppViewContainer"] {
  background: linear-gradient(120deg, #f5f0e6 0%, #dbeeff 45%, #fce6d0 100%);
}
.v2m-card {
  border: 1px solid rgba(20, 30, 45, 0.15);
  border-radius: 16px;
  padding: 14px 16px;
  background: rgba(255, 255, 255, 0.75);
}
</style>
        """,
        unsafe_allow_html=True,
    )


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _safe_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _download_button(path: Path, label: str, mime: str) -> None:
    if path.exists():
        st.download_button(
            label=label,
            data=path.read_bytes(),
            file_name=path.name,
            mime=mime,
        )


def _render_home() -> None:
    st.title("V2M Music Prototype")
    st.markdown(
        """
<div class="v2m-card">
Turn humming and beatboxing into DAW-ready MIDI packs.
Use the sidebar to move between generation, audio analysis, and project browsing.
</div>
        """,
        unsafe_allow_html=True,
    )
    st.subheader("Workflow")
    st.markdown(
        "1. `Generate MIDI Idea` for fast inspiration.\n"
        "2. `Analyze Audio` to convert hummed/beatboxed recordings.\n"
        "3. `Project Explorer` to reopen exports, recipe cards, and analysis data."
    )
    st.subheader("Prototype Outputs")
    st.markdown(
        "- `melody.mid`\n"
        "- `drums.mid`\n"
        "- `combined.mid`\n"
        "- `analysis.json`\n"
        "- `recipe.md`"
    )


def _render_generate() -> None:
    st.header("Generate MIDI Idea")
    with st.form("generate_form"):
        c1, c2 = st.columns(2)
        style = c1.selectbox("Style", sorted(STYLE_PRESETS.keys()), index=3)
        key = c2.text_input("Key", value="C major")
        bpm = c1.slider("BPM", min_value=50, max_value=220, value=120)
        bars = c2.slider("Bars", min_value=1, max_value=32, value=8)
        complexity = c1.slider("Complexity", min_value=1, max_value=10, value=6)
        seed_text = c2.text_input("Seed (optional)", value="")
        output_label = c2.text_input("Output Name", value="idea")
        submitted = st.form_submit_button("Generate MIDI")

    if not submitted:
        return

    seed = int(seed_text) if seed_text.strip() else None
    try:
        idea = generate_idea(
            style=style,
            key=key,
            bpm=bpm,
            bars=bars,
            complexity=complexity,
            seed=seed,
        )
    except ValueError as exc:
        st.error(str(exc))
        return

    UI_OUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = UI_OUT_DIR / f"{_timestamp()}-{_slugify(output_label)}.mid"
    export_idea_to_midi(idea, output_path)
    st.success(f"Generated and saved: {output_path}")
    st.metric("Chord Events", len(idea.chords))
    st.metric("Melody Events", len(idea.melody))
    _download_button(output_path, "Download Generated MIDI", "audio/midi")


def _render_result(result: PrototypeProjectResult) -> None:
    st.success(f"Project created: {result.project_dir}")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Tempo", f"{result.tempo_bpm} BPM")
    m2.metric("Key", result.detected_key)
    m3.metric("Melody Events", result.melody_event_count)
    m4.metric("Drum Events", result.drum_event_count)

    st.subheader("Downloads")
    c1, c2, c3 = st.columns(3)
    with c1:
        _download_button(result.melody_midi_path, "Melody MIDI", "audio/midi")
    with c2:
        _download_button(result.drums_midi_path, "Drums MIDI", "audio/midi")
    with c3:
        _download_button(result.combined_midi_path, "Combined MIDI", "audio/midi")

    st.subheader("Audio")
    if result.raw_audio_path.exists():
        st.audio(result.raw_audio_path.read_bytes(), format="audio/wav")
    if result.cleaned_audio_path.exists():
        st.audio(result.cleaned_audio_path.read_bytes(), format="audio/wav")

    st.subheader("Recipe")
    st.code(_read_text(result.recipe_path), language="markdown")

    st.subheader("Analysis JSON")
    st.json(_safe_json(result.analysis_path))


def _render_analyze() -> None:
    st.header("Analyze Humming / Beatbox Audio")
    uploaded = st.file_uploader("Upload audio", type=["wav", "mp3", "flac", "ogg", "m4a"])
    c1, c2 = st.columns(2)
    project_name = c1.text_input("Project Name", value="session")
    projects_dir = c2.text_input("Projects Directory", value=str(DEFAULT_PROJECTS_DIR))
    scale_mode = c1.selectbox("Scale Mode", ["auto", "manual"], index=0)
    key = c2.text_input("Manual Key", value="C major")
    genre_tags_text = c1.text_input("Genre Tags (comma separated)", value="trap")
    quantize_strength = c2.slider("Quantize Strength", min_value=0.0, max_value=1.0, value=0.9)

    with st.expander("Supported Scales"):
        st.write(", ".join(list_supported_keys()))

    if st.button("Analyze and Build Project", type="primary"):
        if uploaded is None:
            st.error("Upload an audio file first.")
            return

        UI_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        upload_name = f"{_timestamp()}-{_slugify(uploaded.name)}"
        upload_path = UI_UPLOAD_DIR / upload_name
        upload_path.write_bytes(uploaded.getvalue())

        genre_tags = [tag.strip() for tag in genre_tags_text.split(",") if tag.strip()]
        try:
            with st.spinner("Analyzing audio and building project artifacts..."):
                result = analyze_audio_to_project(
                    input_audio_path=upload_path,
                    projects_dir=projects_dir,
                    project_name=project_name,
                    scale_mode=scale_mode,
                    manual_key=key,
                    genre_tags=genre_tags,
                    quantize_strength=quantize_strength,
                )
        except Exception as exc:  # noqa: BLE001
            st.error(f"Analysis failed: {exc}")
            return

        _render_result(result)


def _list_projects(base_dir: Path) -> list[Path]:
    if not base_dir.exists():
        return []
    return sorted([p for p in base_dir.iterdir() if p.is_dir()], reverse=True)


def _render_project_explorer() -> None:
    st.header("Project Explorer")
    base = Path(st.text_input("Projects Directory", value=str(DEFAULT_PROJECTS_DIR)))
    projects = _list_projects(base)
    if not projects:
        st.info("No projects found yet.")
        return

    selected_name = st.selectbox("Select Project", [p.name for p in projects])
    selected = next((p for p in projects if p.name == selected_name), projects[0])
    st.write(f"Path: `{selected}`")

    analysis_path = selected / "analysis.json"
    recipe_path = selected / "recipe.md"
    midi_dir = selected / "midi"

    c1, c2, c3 = st.columns(3)
    with c1:
        _download_button(midi_dir / "melody.mid", "Download Melody", "audio/midi")
    with c2:
        _download_button(midi_dir / "drums.mid", "Download Drums", "audio/midi")
    with c3:
        _download_button(midi_dir / "combined.mid", "Download Combined", "audio/midi")

    st.subheader("Recipe")
    st.code(_read_text(recipe_path), language="markdown")
    st.subheader("Analysis")
    st.json(_safe_json(analysis_path))


def main() -> None:
    st.set_page_config(
        page_title="V2M Prototype",
        page_icon="🎵",
        layout="wide",
    )
    _styled_header()
    with st.sidebar:
        st.title("V2M")
        section = st.radio(
            "Navigate",
            options=["Home", "Generate MIDI Idea", "Analyze Audio", "Project Explorer"],
            index=0,
        )

    if section == "Home":
        _render_home()
    elif section == "Generate MIDI Idea":
        _render_generate()
    elif section == "Analyze Audio":
        _render_analyze()
    elif section == "Project Explorer":
        _render_project_explorer()


if __name__ == "__main__":
    main()
