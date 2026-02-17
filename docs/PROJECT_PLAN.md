# V2M Project Plan

## 1) Goal
Build a local-first AI music tool, test thoroughly, then publish the first official release on a new GitHub repository.

## 2) Current Build (`v0.1.0-dev`)
- Input: style, key, tempo, length, complexity.
- Output: generated MIDI ideas (chords + melody pattern) via CLI.
- User flow:
  - Create idea
  - Preview data summary
  - Export `.mid`
  - Import into DAW (Ableton/FL Studio)

## 3) Target Product Increment (`v0.2.0`)
- Input: recorded/imported humming and beatbox audio.
- Output: melody MIDI + drum MIDI + DAW recipe card.
- Scale mode:
  - User-locked root/scale.
  - AI-detected best-fit scale mode.

## 4) Technical Strategy
- Keep architecture modular so plugin integration can be added later.
- Start with a single app (CLI or desktop UI) and stable MIDI generation core.
- Add tests around deterministic generation and export integrity.
- Add staged analysis pipeline: capture -> cleanup -> analyze -> reason -> export.

## 5) Milestones

## M0: Foundation
- Create repo, structure, docs, and baseline standards.
- Define coding conventions and semantic versioning approach.
- Confirm local dev setup works end-to-end.

Status: complete.

## M1: Core MIDI MVP Build
- Implement generation engine.
- Implement MIDI export.
- Implement basic UI/CLI controls.
- Add tests for key/tempo/length constraints.

Status: complete.

## M1 Exit Criteria
- Generate valid MIDI in at least 5 styles/presets.
- Pass local test suite.
- Run manual DAW import tests in Ableton + FL Studio.

## M2: GitHub Bootstrapping Release
- Create GitHub repo.
- Push complete history.
- Tag initial developer release `v0.1.0-dev`.

Status: complete.

## M3: Hum + Beatbox Core (`v0.2.0`)
- Implement audio import and mic capture.
- Build baseline hum-to-melody extraction.
- Build baseline beatbox-to-drum extraction.
- Implement manual scale lock and auto-detect mode.
- Export first recipe card guidance.

## M3 Exit Criteria
- One hum recording converts to usable melody MIDI.
- One beatbox recording converts to usable drum MIDI.
- Recipe card generated for both outputs.
- Local outputs reopenable from project folder.

## M4: Producer Assistant (`v0.3.0`)
- Recommend chord progressions when melody implies harmony.
- Suggest routes for layers, sound design, and arrangement.
- Add optional genre filters plus open exploration mode.

## M5: Plugin Learning Track
- Evaluate JUCE-based plugin prototype.
- Define bridge strategy between core engine and plugin shell.
- Build first minimal VST prototype (single feature pass-through).

## 6) Quality Bar
- Every feature ships with test coverage or documented manual test steps.
- No breaking behavior merged without updating release notes.
- Keep all changes isolated from BECA and `BECAFirmware`.

## 7) Success Metrics (First 90 Days)
- `v0.2.0` shipped with hum + beatbox conversion baseline.
- At least 3 update cycles completed after `v0.2.0`.
- Reproducible release process documented.
