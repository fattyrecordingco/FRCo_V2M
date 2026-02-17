"""Command-line interface for V2M MVP."""

from __future__ import annotations

import argparse

from .audio_to_midi import analyze_audio_to_project
from .generator import STYLE_PRESETS, generate_idea
from .music_theory import list_supported_keys
from .midi_export import export_idea_to_midi


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="v2m",
        description="Generate AI-assisted MIDI ideas for DAW workflows.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate_cmd = subparsers.add_parser("generate", help="Generate and export a MIDI idea.")
    generate_cmd.add_argument("--style", default="pop", choices=sorted(STYLE_PRESETS.keys()))
    generate_cmd.add_argument("--key", default="C major", help="Example: 'C major', 'A minor'.")
    generate_cmd.add_argument("--bpm", type=int, default=120)
    generate_cmd.add_argument("--bars", type=int, default=8)
    generate_cmd.add_argument("--complexity", type=int, default=5, help="Range: 1-10.")
    generate_cmd.add_argument("--seed", type=int, default=None, help="Optional for repeatable output.")
    generate_cmd.add_argument("--output", default="out/idea.mid")

    analyze_cmd = subparsers.add_parser(
        "analyze",
        help="Analyze humming/beatbox audio and export MIDI + recipe artifacts.",
    )
    analyze_cmd.add_argument("--input", required=True, help="Path to local audio file.")
    analyze_cmd.add_argument("--projects-dir", default="projects")
    analyze_cmd.add_argument("--project-name", default=None)
    analyze_cmd.add_argument("--scale-mode", choices=["auto", "manual"], default="auto")
    analyze_cmd.add_argument(
        "--key",
        default="C major",
        help="Used when --scale-mode manual; supports extended scales like 'A harmonic minor'.",
    )
    analyze_cmd.add_argument("--genre-tags", default="", help="Comma-separated tags, e.g. trap,lofi.")
    analyze_cmd.add_argument("--quantize-strength", type=float, default=0.90)
    analyze_cmd.add_argument(
        "--list-scales",
        action="store_true",
        help="Print supported scale modes and exit.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "generate":
        idea = generate_idea(
            style=args.style,
            key=args.key,
            bpm=args.bpm,
            bars=args.bars,
            complexity=args.complexity,
            seed=args.seed,
        )
        output_path = export_idea_to_midi(idea, args.output)
        print(
            f"Generated {idea.style} idea in {idea.key} at {idea.bpm} BPM "
            f"({idea.bars} bars)."
        )
        print(f"Chord events: {len(idea.chords)} | Melody events: {len(idea.melody)}")
        print(f"MIDI saved to: {output_path}")
    elif args.command == "analyze":
        if args.list_scales:
            print("Supported scales:")
            for mode in list_supported_keys():
                print(f"- {mode}")
            return

        genre_tags = [tag.strip() for tag in args.genre_tags.split(",") if tag.strip()]
        result = analyze_audio_to_project(
            input_audio_path=args.input,
            projects_dir=args.projects_dir,
            project_name=args.project_name,
            scale_mode=args.scale_mode,
            manual_key=args.key,
            genre_tags=genre_tags,
            quantize_strength=args.quantize_strength,
        )
        print(f"Project: {result.project_dir}")
        print(f"Tempo/Time: {result.tempo_bpm} BPM / {result.time_signature}")
        print(f"Key: {result.detected_key}")
        print(
            "Events: "
            f"melody={result.melody_event_count}, drums={result.drum_event_count}"
        )
        print("Outputs:")
        print(f"- {result.melody_midi_path}")
        print(f"- {result.drums_midi_path}")
        print(f"- {result.combined_midi_path}")
        print(f"- {result.analysis_path}")
        print(f"- {result.recipe_path}")


if __name__ == "__main__":
    main()
