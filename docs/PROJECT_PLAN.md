# V2M Project Plan

## 1) Goal
Build a local-first AI music tool, test thoroughly, then publish the first official release on a new GitHub repository.

## 2) MVP Definition (`v0.1.0`)
- Input: style, key, tempo, length, complexity.
- Output: generated MIDI ideas (chords + melody pattern).
- User flow:
  - Create idea
  - Preview data summary
  - Export `.mid`
  - Import into DAW (Ableton/FL Studio)

## 3) Technical Strategy
- Keep architecture modular so plugin integration can be added later.
- Start with a single app (CLI or desktop UI) and stable MIDI generation core.
- Add tests around deterministic generation and export integrity.

## 4) Milestones

## M0: Foundation
- Create repo, structure, docs, and baseline standards.
- Define coding conventions and semantic versioning approach.
- Confirm local dev setup works end-to-end.

## M1: Core MVP Build
- Implement generation engine.
- Implement MIDI export.
- Implement basic UI/CLI controls.
- Add tests for key/tempo/length constraints.

## M1 Exit Criteria
- Generate valid MIDI in at least 5 styles/presets.
- Pass local test suite.
- Run manual DAW import tests in Ableton + FL Studio.

## M2: First Public Release
- Create GitHub repo.
- Push complete history.
- Tag release `v0.1.0`.
- Publish release notes and known limitations.

## M3: Plugin Learning Track
- Evaluate JUCE-based plugin prototype.
- Define bridge strategy between core engine and plugin shell.
- Build first minimal VST prototype (single feature pass-through).

## 5) Quality Bar
- Every feature ships with test coverage or documented manual test steps.
- No breaking behavior merged without updating release notes.
- Keep all changes isolated from BECA and `BECAFirmware`.

## 6) Success Metrics (First 60 Days)
- `v0.1.0` shipped publicly.
- At least 3 update cycles completed (`v0.1.1+`).
- Reproducible release process documented.
