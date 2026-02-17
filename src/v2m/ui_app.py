"""Interactive UI for the V2M prototype."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
import textwrap

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


def _producer_assistant_response(
    *,
    idea_description: str,
    genre_tags: list[str],
    mood: str,
    energy: int,
) -> str:
    genres = {tag.lower() for tag in genre_tags}
    progression = "I - V - vi - IV"
    if "trap" in genres:
        progression = "i - bVII - bVI - bVI"
    elif "lofi" in genres:
        progression = "ii - V - I - vi"
    elif "edm" in genres:
        progression = "I - V - vi - IV (with 8-bar riser)"

    drum_advice = "Use punchy kick + clap backbeat + syncopated hat variations."
    if energy <= 3:
        drum_advice = "Keep sparse drums with soft hats and ghost snare notes."
    elif energy >= 8:
        drum_advice = "Push transients harder with layered kick/snare and fast hat rolls."

    mood_layer = {
        "dark": "detuned pad + low-pass texture + sub drone",
        "uplifting": "bright pluck + wide supersaw stack + octave lead doubles",
        "melancholic": "warm piano + tape pad + low cello-like bass",
        "aggressive": "distorted bass layer + transient shaper + clipped drums",
        "dreamy": "chorused keys + shimmer reverb + airy vocal-like synth",
    }.get(mood.lower(), "primary lead + support pad + bass foundation")

    return textwrap.dedent(
        f"""
        **Producer Assistant Plan**

        Idea summary:
        - `{idea_description or "No text prompt provided"}`
        - Mood: `{mood}`
        - Energy: `{energy}/10`
        - Genres: `{", ".join(genre_tags) if genre_tags else "open experimentation"}`

        Suggested harmony route:
        - `{progression}`

        Layering route:
        - `{mood_layer}`
        - Add countermelody in final 4 bars of each phrase.
        - Duplicate melody one octave down for bass guide notes.

        Drum route:
        - {drum_advice}
        - Keep 60-80% quantize if groove feels too robotic.

        Arrangement route:
        - 8 bars intro (filtered melody only)
        - 16 bars main idea (full drums + bass)
        - 8 bars variation (remove kick, keep hat/perc movement)
        - 16 bars payoff (full stack + adlibs/fills)
        """
    ).strip()


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
    recorded = st.audio_input("Record from microphone")
    uploaded = st.file_uploader("Or upload audio", type=["wav", "mp3", "flac", "ogg", "m4a"])
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
        source_file = recorded if recorded is not None else uploaded
        if source_file is None:
            st.error("Record from mic or upload an audio file first.")
            return

        UI_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        suffix = Path(source_file.name).suffix or ".wav"
        upload_name = f"{_timestamp()}-{_slugify(Path(source_file.name).stem)}{suffix}"
        upload_path = UI_UPLOAD_DIR / upload_name
        upload_path.write_bytes(source_file.getvalue())

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


def _render_assistant() -> None:
    st.header("Producer Assistant")
    st.caption("Text-guided exploration to extend your hum/beatbox idea into full production routes.")

    idea_description = st.text_area(
        "Describe your idea",
        value="hummed dark bassline with punchy beatbox groove",
        height=100,
    )
    c1, c2, c3 = st.columns(3)
    mood = c1.selectbox("Mood", ["dark", "uplifting", "melancholic", "aggressive", "dreamy"])
    energy = c2.slider("Energy", min_value=1, max_value=10, value=7)
    tag_text = c3.text_input("Genre tags", value="trap,experimental")
    tags = [tag.strip() for tag in tag_text.split(",") if tag.strip()]

    if st.button("Generate Assistant Plan"):
        st.markdown(
            _producer_assistant_response(
                idea_description=idea_description,
                genre_tags=tags,
                mood=mood,
                energy=energy,
            )
        )


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
            options=[
                "Home",
                "Generate MIDI Idea",
                "Analyze Audio",
                "Producer Assistant",
                "Project Explorer",
            ],
            index=0,
        )

    if section == "Home":
        _render_home()
    elif section == "Generate MIDI Idea":
        _render_generate()
    elif section == "Analyze Audio":
        _render_analyze()
    elif section == "Producer Assistant":
        _render_assistant()
    elif section == "Project Explorer":
        _render_project_explorer()


if __name__ == "__main__":
    main()
