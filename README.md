# V2M Software

AI-assisted music creation software built as a local-first experiment, then released publicly on GitHub.

## Current Status
- `v0.1.0.dev0` local MVP scaffold is active.
- Includes a CLI generator with style/key/bpm controls.
- Exports MIDI ideas for DAW import and testing.

## Mission
- Improve music-making workflows for artists using practical AI tools.
- Learn software engineering fundamentals through real product delivery.
- Build toward DAW integration and virtual plugin development over time.

## Scope (Phase 1)
- Local app workflow for generating musical ideas.
- AI-assisted MIDI suggestions (currently heuristic seed engine for MVP).
- MIDI export for DAW workflows (Ableton, FL Studio, others).
- Preset-driven controls for style, key, tempo, and complexity.

## Non-Goals (Phase 1)
- Full plugin (VST/AU/AAX) support.
- Cloud accounts, payments, or marketplace features.
- Advanced mixing/mastering automation.

## Project Structure
- `docs/` planning, architecture, roadmap, release process.
- `src/` application source code.
- `tests/` automated tests.
- `scripts/` helper scripts for development and release tasks.

## Milestones
- `M0` Foundation: repo setup, planning docs, baseline tooling.
- `M1` Core MVP: idea generation + MIDI export + local testing.
- `M2` First Public Release: GitHub repo + tagged `v0.1.0`.
- `M3` Plugin Track: DAW plugin prototype exploration.

## Quick Start
```powershell
python -m pip install -e .[dev]
python -m v2m.cli generate --style pop --key "C major" --bpm 120 --bars 8 --complexity 5 --seed 42 --output out/idea.mid
pytest
```

Generated MIDI files can be dragged into Ableton/FL Studio for manual validation.

## Available Styles
- `pop`
- `trap`
- `lofi`
- `edm`
- `cinematic`

## Separation Requirement
This project is independent from BECA Project and `BECAFirmware`.
No code, remotes, commits, or release history should be shared between them.
