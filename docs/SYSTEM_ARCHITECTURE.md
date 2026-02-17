# V2M System Architecture

## Design Principles
- Local-first processing and storage.
- Modular pipeline (replace models without rewriting app).
- Deterministic export artifacts for reproducibility.

## High-Level Pipeline
1. Capture Layer
2. Audio Cleanup Layer
3. Analysis Layer
4. Musical Reasoning Layer
5. Output Layer
6. Project Memory Layer

## 1) Capture Layer
- Mic device selection (onboard/external).
- Session recording control (start/stop/monitor level).
- Audio file import path.
- Output: raw waveform + metadata (sample rate, duration, device id).

## 2) Audio Cleanup Layer
- Noise reduction pass.
- Loudness normalization.
- Optional silence trimming.
- Output: cleaned waveform + processing report.

## 3) Analysis Layer

## Tonal Analysis
- Pitch contour extraction.
- Note segmentation.
- Tempo + beat grid estimation.
- Time signature hypothesis with confidence.

## Percussive Analysis
- Transient detection.
- Beatbox event classification (kick/snare/hihat/tom/perc).
- Groove timing map.

## Joint Analysis (Hum + Beatbox)
- Harmonic/percussive source separation.
- Independent feature extraction per stream.

## 4) Musical Reasoning Layer
- Scale manager:
  - Manual lock mode (user-selected root/scale).
  - Auto mode (best-fit scale proposal).
  - Extended scale pack support (global/modal families).
- Quantizer:
  - Beat quantization strength control.
  - Scale snapping strength control.
- Harmony assistant:
  - Chord progression recommendations based on melody and genre context.
- Producer assistant:
  - Layering routes, arrangement suggestions, and timbral ideas.

## 5) Output Layer
- MIDI writer for multitrack export:
  - melody
  - chords
  - bass suggestions
  - drums
- Recipe card generator:
  - DAW build instructions
  - suggested instrument types
  - optional genre-specific guidance

## 6) Project Memory Layer
- Local project folder per idea:
  - raw audio
  - cleaned audio
  - extracted features (JSON)
  - MIDI exports
  - recipe card
- Session metadata index for recall/search.

## Suggested Implementation Order
1. Audio file import (faster iteration than live mic).
2. Hum-to-melody MIDI baseline.
3. Beatbox-to-drum MIDI baseline.
4. Combined hum+beatbox separation path.
5. Producer assistant + recipe refinement.
6. Live mic real-time UX improvements.

## Proposed Repo Modules
- `src/v2m/capture/`
- `src/v2m/audio/`
- `src/v2m/analysis/`
- `src/v2m/reasoning/`
- `src/v2m/export/`
- `src/v2m/assistant/`
- `src/v2m/projects/`

## Quality Gates per Module
- Unit tests for deterministic transforms.
- Golden-file tests for MIDI output consistency.
- Manual import tests for Ableton and FL Studio.
