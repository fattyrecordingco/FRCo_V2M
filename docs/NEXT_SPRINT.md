# Next Sprint: `v0.2.0` Foundation

## Objective
Deliver the first hum/beatbox-to-MIDI pipeline from imported audio files.

## Build Tasks
1. Add audio import command (`v2m analyze --input <file.wav>`).
2. Add project folder persistence for analysis artifacts.
3. Add tempo + beat grid estimation baseline.
4. Add humming note extraction baseline.
5. Add beatbox transient/drum-role extraction baseline.
6. Add scale mode option:
   - `--scale-mode manual --key "C major"`
   - `--scale-mode auto`
7. Export:
   - `melody.mid`
   - `drums.mid`
   - `recipe.md`
8. Add end-to-end tests for one fixed sample file.

## Validation
1. Import MIDI outputs into Ableton and FL Studio.
2. Verify groove and tonal contour match source idea.
3. Confirm artifacts are saved under a local project directory.
