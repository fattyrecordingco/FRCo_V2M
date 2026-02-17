"""Interactive UI for the V2M prototype with a chat-like musician workflow."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
import textwrap

import streamlit as st

from v2m.audio_to_midi import analyze_audio_to_project
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
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;700;800&display=swap');
:root {
  --ink: #101820;
  --surface: rgba(255, 255, 255, 0.84);
  --line: rgba(16, 24, 32, 0.16);
  --mint: #74f0c5;
  --sun: #ffc983;
  --sky: #a7d7ff;
}

html, body, [class*="css"] {
  font-family: 'Plus Jakarta Sans', sans-serif;
  color: var(--ink);
}

[data-testid="stAppViewContainer"] {
  background:
    radial-gradient(circle at 12% 20%, rgba(116, 240, 197, 0.26), transparent 24%),
    radial-gradient(circle at 85% 10%, rgba(167, 215, 255, 0.34), transparent 28%),
    radial-gradient(circle at 76% 92%, rgba(255, 201, 131, 0.26), transparent 24%),
    linear-gradient(145deg, #f6f8f2 0%, #f8f2ea 45%, #ecf6ff 100%);
}

.v2m-card {
  border: 1px solid var(--line);
  border-radius: 18px;
  padding: 14px 16px;
  background: var(--surface);
}

.v2m-chat {
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 12px 14px;
  margin-bottom: 8px;
  background: rgba(255, 255, 255, 0.75);
}

.v2m-chat.user {
  border-left: 5px solid #83c6ff;
}

.v2m-chat.copilot {
  border-left: 5px solid #6fe6b9;
}

.v2m-metric {
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.7);
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


def _init_session() -> None:
    if "copilot_chat" not in st.session_state:
        st.session_state["copilot_chat"] = [
            {
                "role": "copilot",
                "content": (
                    "Upload or record a hum/beatbox idea and I will convert it into"
                    " melody and drum MIDI plus a DAW recipe card."
                ),
            }
        ]
    if "active_project" not in st.session_state:
        st.session_state["active_project"] = ""


def _add_chat(role: str, content: str) -> None:
    st.session_state["copilot_chat"].append({"role": role, "content": content})


def _project_assets(project_dir: Path) -> dict[str, Path]:
    analysis = project_dir / "analysis.json"
    payload = _safe_json(analysis)

    midi_map = payload.get("midi_outputs", {}) if isinstance(payload, dict) else {}
    melody = Path(str(midi_map.get("melody", project_dir / "midi" / "melody.mid")))
    drums = Path(str(midi_map.get("drums", project_dir / "midi" / "drums.mid")))
    combined = Path(str(midi_map.get("combined", project_dir / "midi" / "combined.mid")))

    recipe = Path(str(payload.get("recipe_path", project_dir / "recipe.md")))
    raw_audio = Path(str(payload.get("input_audio", project_dir / "audio" / "raw.wav")))
    cleaned_audio = Path(str(payload.get("cleaned_audio", project_dir / "audio" / "cleaned.wav")))

    return {
        "analysis": analysis,
        "recipe": recipe,
        "melody": melody,
        "drums": drums,
        "combined": combined,
        "raw_audio": raw_audio,
        "cleaned_audio": cleaned_audio,
    }


def _list_projects(base_dir: Path) -> list[Path]:
    if not base_dir.exists():
        return []
    return sorted([p for p in base_dir.iterdir() if p.is_dir()], reverse=True)


def _assistant_from_project(project_dir: Path, focus: str) -> str:
    payload = _safe_json(project_dir / "analysis.json")
    tempo = payload.get("tempo_bpm", "?")
    key = payload.get("detected_key", "?")
    genres = payload.get("genre_tags", [])
    genre_txt = ", ".join(genres) if genres else "open"

    if focus == "arrangement":
        return (
            f"Use {tempo} BPM and {key} to structure 8+16+8+16 bars. "
            "Start minimal, then add bass layer in section two and percussion fills in section four."
        )
    if focus == "sound":
        return (
            f"For {genre_txt} direction: pair your melody MIDI with one warm lead and one noisy texture. "
            "Keep drums dry first, then add room reverb only to snare/clap."
        )
    return (
        f"Next move: open melody and drum MIDI from this project, lock DAW to {tempo} BPM, "
        "then A/B two instrument stacks before writing new notes."
    )


def _render_chat_panel() -> None:
    st.subheader("Studio Copilot")
    for msg in st.session_state["copilot_chat"][-10:]:
        role = "copilot" if msg["role"] == "copilot" else "user"
        title = "V2M Copilot" if role == "copilot" else "You"
        st.markdown(
            (
                f"<div class='v2m-chat {role}'><strong>{title}</strong><br/>"
                f"{msg['content']}</div>"
            ),
            unsafe_allow_html=True,
        )

    prompt = st.text_input("Ask for guidance", placeholder="How should I layer this groove?")
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Next Move"):
            active = Path(st.session_state.get("active_project") or "")
            if active.exists():
                _add_chat("copilot", _assistant_from_project(active, "next"))
            else:
                _add_chat("copilot", "Analyze audio first, then I can guide arrangement and sound design.")
            st.rerun()
    with c2:
        if st.button("Arrange"):
            active = Path(st.session_state.get("active_project") or "")
            if active.exists():
                _add_chat("copilot", _assistant_from_project(active, "arrangement"))
            else:
                _add_chat("copilot", "Record or upload an idea first so arrangement suggestions fit your material.")
            st.rerun()
    with c3:
        if st.button("Sound Design"):
            active = Path(st.session_state.get("active_project") or "")
            if active.exists():
                _add_chat("copilot", _assistant_from_project(active, "sound"))
            else:
                _add_chat("copilot", "Analyze one idea first, then I can suggest sound layers tied to your groove.")
            st.rerun()

    if prompt.strip():
        _add_chat("user", prompt.strip())
        active = Path(st.session_state.get("active_project") or "")
        if "scale" in prompt.lower():
            reply = "Use auto scale first, then compare against manual root/scale lock to pick stronger emotional color."
        elif "drum" in prompt.lower():
            reply = "Duplicate drum MIDI, keep one tight quantized and one humanized at 60-75% for groove depth."
        elif active.exists():
            reply = _assistant_from_project(active, "next")
        else:
            reply = "Give me one recording first, then I can provide project-specific advice."
        _add_chat("copilot", reply)
        st.rerun()


def _run_analysis(
    *,
    source_bytes: bytes,
    source_name: str,
    project_name: str,
    projects_dir: str,
    scale_mode: str,
    manual_key: str,
    genre_tags: list[str],
    quantize_strength: float,
) -> Path:
    UI_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    suffix = Path(source_name).suffix or ".wav"
    upload_name = f"{_timestamp()}-{_slugify(Path(source_name).stem)}{suffix}"
    upload_path = UI_UPLOAD_DIR / upload_name
    upload_path.write_bytes(source_bytes)

    result = analyze_audio_to_project(
        input_audio_path=upload_path,
        projects_dir=projects_dir,
        project_name=project_name,
        scale_mode=scale_mode,
        manual_key=manual_key,
        genre_tags=genre_tags,
        quantize_strength=quantize_strength,
    )
    return result.project_dir


def _render_active_project(project_dir: Path) -> None:
    assets = _project_assets(project_dir)
    payload = _safe_json(assets["analysis"])

    tempo = payload.get("tempo_bpm", "?")
    key = payload.get("detected_key", "?")
    melody_count = payload.get("melody_event_count", 0)
    drum_count = payload.get("drum_event_count", 0)

    st.markdown("### Current Output")
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f"<div class='v2m-metric'><strong>Tempo</strong><br/>{tempo} BPM</div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='v2m-metric'><strong>Key</strong><br/>{key}</div>", unsafe_allow_html=True)
    c3.markdown(f"<div class='v2m-metric'><strong>Melody</strong><br/>{melody_count} events</div>", unsafe_allow_html=True)
    c4.markdown(f"<div class='v2m-metric'><strong>Drums</strong><br/>{drum_count} events</div>", unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs(["Files", "Recipe", "Audio", "Analysis"])
    with tab1:
        b1, b2, b3 = st.columns(3)
        with b1:
            _download_button(assets["melody"], "Melody MIDI", "audio/midi")
        with b2:
            _download_button(assets["drums"], "Drums MIDI", "audio/midi")
        with b3:
            _download_button(assets["combined"], "Combined MIDI", "audio/midi")
    with tab2:
        st.code(_read_text(assets["recipe"]), language="markdown")
    with tab3:
        if assets["raw_audio"].exists():
            st.caption("Raw audio")
            st.audio(assets["raw_audio"].read_bytes(), format="audio/wav")
        if assets["cleaned_audio"].exists():
            st.caption("Cleaned audio")
            st.audio(assets["cleaned_audio"].read_bytes(), format="audio/wav")
    with tab4:
        st.json(payload)


def _render_copilot_workspace() -> None:
    st.title("V2M Studio Flow")
    st.markdown(
        """
<div class="v2m-card">
Your main path is simple: capture one musical idea, convert it to MIDI, then iterate with copilot guidance.
</div>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.05, 1.25], gap="large")
    with left:
        _render_chat_panel()

    with right:
        st.subheader("1) Capture and Analyze")
        recorded = st.audio_input("Record idea")
        uploaded = st.file_uploader("Or upload audio", type=["wav", "mp3", "flac", "ogg", "m4a"])

        c1, c2 = st.columns(2)
        default_name = f"idea-{datetime.now().strftime('%H%M')}"
        project_name = c1.text_input("Project Name", value=default_name)
        genre_tags_text = c2.text_input("Genre Tags", value="trap,experimental")

        with st.expander("Advanced Controls"):
            a1, a2 = st.columns(2)
            scale_mode = a1.selectbox("Scale Mode", ["auto", "manual"], index=0)
            manual_key = a2.text_input("Manual Key", value="C major")
            quantize_strength = a1.slider("Quantize Strength", min_value=0.0, max_value=1.0, value=0.9)
            projects_dir = a2.text_input("Projects Directory", value=str(DEFAULT_PROJECTS_DIR))
            st.caption("Supported scales: " + ", ".join(list_supported_keys()))

        source = recorded if recorded is not None else uploaded
        if st.button("Analyze Idea and Build Project", type="primary", use_container_width=True):
            if source is None:
                st.error("Record or upload audio first.")
            else:
                tags = [tag.strip() for tag in genre_tags_text.split(",") if tag.strip()]
                _add_chat("user", "Convert this idea into a full music pack.")
                try:
                    with st.spinner("Analyzing audio, creating MIDI, and generating recipe card..."):
                        project_dir = _run_analysis(
                            source_bytes=source.getvalue(),
                            source_name=source.name,
                            project_name=project_name,
                            projects_dir=projects_dir,
                            scale_mode=scale_mode,
                            manual_key=manual_key,
                            genre_tags=tags,
                            quantize_strength=quantize_strength,
                        )
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Analysis failed: {exc}")
                    _add_chat("copilot", f"I could not process that audio yet: {exc}")
                else:
                    st.session_state["active_project"] = str(project_dir)
                    payload = _safe_json(project_dir / "analysis.json")
                    _add_chat(
                        "copilot",
                        (
                            f"Done. I detected {payload.get('tempo_bpm', '?')} BPM and "
                            f"{payload.get('detected_key', 'unknown key')}. "
                            "Use the Files tab to drop MIDI into your DAW now."
                        ),
                    )
                    st.rerun()

        active = Path(st.session_state.get("active_project") or "")
        if active.exists():
            _render_active_project(active)


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
        progression = "I - V - vi - IV (8-bar lift)"

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
        - 16 bars main section (full drums + bass)
        - 8 bars variation (remove kick, keep hats/perc)
        - 16 bars payoff (full stack + fills)
        """
    ).strip()


def _render_generate_extension() -> None:
    st.subheader("Extension: Fast MIDI Generator")
    with st.form("generate_form"):
        c1, c2 = st.columns(2)
        style = c1.selectbox("Style", sorted(STYLE_PRESETS.keys()), index=0)
        key = c2.text_input("Key", value="C major")
        bpm = c1.slider("BPM", min_value=50, max_value=220, value=120)
        bars = c2.slider("Bars", min_value=1, max_value=32, value=8)
        complexity = c1.slider("Complexity", min_value=1, max_value=10, value=6)
        seed_text = c2.text_input("Seed (optional)", value="")
        output_label = c2.text_input("Output Name", value="idea")
        submitted = st.form_submit_button("Generate")

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
    st.success(f"Generated: {output_path}")
    _download_button(output_path, "Download MIDI", "audio/midi")


def _render_assistant_extension() -> None:
    st.subheader("Extension: Producer Brainstorm")
    idea_description = st.text_area(
        "Describe your idea",
        value="hummed dark bassline with punchy beatbox groove",
        height=90,
    )
    c1, c2, c3 = st.columns(3)
    mood = c1.selectbox("Mood", ["dark", "uplifting", "melancholic", "aggressive", "dreamy"])
    energy = c2.slider("Energy", min_value=1, max_value=10, value=7)
    tag_text = c3.text_input("Genre tags", value="trap,experimental")
    tags = [tag.strip() for tag in tag_text.split(",") if tag.strip()]

    if st.button("Generate Plan"):
        st.markdown(
            _producer_assistant_response(
                idea_description=idea_description,
                genre_tags=tags,
                mood=mood,
                energy=energy,
            )
        )


def _render_extensions() -> None:
    st.title("Extensions")
    st.caption("Secondary tools that support the core audio-to-MIDI flow.")
    tab1, tab2 = st.tabs(["Fast Generator", "Producer Brainstorm"])
    with tab1:
        _render_generate_extension()
    with tab2:
        _render_assistant_extension()


def _render_project_explorer() -> None:
    st.title("Project Explorer")
    base = Path(st.text_input("Projects Directory", value=str(DEFAULT_PROJECTS_DIR)))
    projects = _list_projects(base)
    if not projects:
        st.info("No projects found yet.")
        return

    selected_name = st.selectbox("Select Project", [p.name for p in projects])
    selected = next((p for p in projects if p.name == selected_name), projects[0])
    st.write(f"Path: `{selected}`")

    st.session_state["active_project"] = str(selected)
    _render_active_project(selected)


def main() -> None:
    st.set_page_config(page_title="V2M Studio", layout="wide")
    _styled_header()
    _init_session()

    with st.sidebar:
        st.title("V2M")
        section = st.radio(
            "Navigate",
            options=["Studio Copilot", "Extensions", "Project Explorer"],
            index=0,
        )

    if section == "Studio Copilot":
        _render_copilot_workspace()
    elif section == "Extensions":
        _render_extensions()
    elif section == "Project Explorer":
        _render_project_explorer()


if __name__ == "__main__":
    main()
