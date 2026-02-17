"""Command-line interface for V2M MVP."""

from __future__ import annotations

import argparse

from .generator import STYLE_PRESETS, generate_idea
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


if __name__ == "__main__":
    main()
