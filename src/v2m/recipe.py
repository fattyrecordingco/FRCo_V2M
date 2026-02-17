"""Recipe card generator for DAW reconstruction guidance."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RecipeContext:
    project_name: str
    tempo_bpm: int
    time_signature: str
    key: str
    scale_mode: str
    genre_tags: list[str]
    melody_events: int
    drum_events: int
    chord_recommendation: str


def build_recipe_markdown(context: RecipeContext) -> str:
    genres = ", ".join(context.genre_tags) if context.genre_tags else "none (open exploration mode)"
    lines = [
        f"# V2M Recipe Card: {context.project_name}",
        "",
        "## Session Summary",
        f"- Tempo: {context.tempo_bpm} BPM",
        f"- Time Signature (estimated): {context.time_signature}",
        f"- Key/Scale: {context.key} ({context.scale_mode})",
        f"- Genre Filters: {genres}",
        f"- Melody Events: {context.melody_events}",
        f"- Drum Events: {context.drum_events}",
        "",
        "## Build in Your DAW",
        "1. Create MIDI tracks for Melody, Drums, and Harmony.",
        "2. Import `midi/melody.mid` and route to a lead/pad instrument.",
        "3. Import `midi/drums.mid` and route to a drum rack or sampler.",
        "4. Keep quantization at 50-80% if you want natural groove.",
        "5. Layer a bass instrument doubling melody root notes every bar.",
        "",
        "## Harmony Suggestion",
        f"- Suggested progression route: {context.chord_recommendation}",
        "",
        "## Producer Assistant Suggestions",
        "- Try a second layer one octave above key melody notes in hook sections.",
        "- Add call-and-response percussion in empty melody phrases.",
        "- Use filtered pad automation to open up in chorus/drop sections.",
        "",
        "## Optional Iterations",
        "- Regenerate drums with tighter quantize for electronic styles.",
        "- Keep melody and swap scale mode to compare tonal color.",
        "- Duplicate the project and test a half-time or double-time groove.",
    ]
    return "\n".join(lines) + "\n"
