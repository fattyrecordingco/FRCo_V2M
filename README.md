# VINS (Voice Input Notation System)

VINS is a local-first audio-to-MIDI desktop/web application designed for rapid idea capture from voice, instruments, and beatboxing.

## Stack

- `frontend/`: React + TypeScript + Vite + Tailwind UI (browser-first)
- `backend/`: FastAPI + Python offline analysis engine (pitch/chords/drums + MIDI/audio export)
- `frontend/src-tauri/`: Tauri desktop shell for Windows/macOS packaging
- `plugin/`: JUCE VST3/AU scaffold for DAW integration roadmap

## Features Implemented

- 4-step wizard UI in one view:
  1. Input (mic recording device selection, upload, drag/drop, waveform + playback)
  2. Pre-processing (mode select, auto pitch/time, manual root/scale/BPM/signature, custom scale piano)
  3. Processing & preview (loading state, note visualization, instrument audition, play/pause, loop, solo/mute, file panel)
  4. Output management (MIDI/audio panels, download buttons, session ZIP export)
- Offline analysis pipeline:
  - Monophonic note extraction
  - Polyphonic chord recognition
  - Drum onset + spectral class transcription
  - Mono/poly auto-detection with override
  - Quantization and optional retime/retune
- Session archive persisted in `projects/`
- Regeneration creates new run folders per session
- Rename updates files on disk (replaces existing target file if same name exists)
- API endpoints:
  - `POST /api/v1/analyze`
  - `POST /api/v1/convert-notes`
  - `POST /api/v1/convert-chords`
  - `POST /api/v1/convert-drums`
  - Session/file/zip endpoints for archive management

## Repository Layout

```text
backend/     Python FastAPI engine
frontend/    React app + Tauri shell
plugin/      JUCE plugin scaffold
docs/        architecture, API, roadmap, plugin integration docs
tests/       backend unit tests
examples/    sample audio for demo and testing
src/shared/  shared engine contracts and planning assets
scripts/     setup/run helper scripts
```

## Quick Start

1. Install Python 3.11+, Node.js 20+, and Rust toolchain (for Tauri builds).
2. Run setup:
   - Windows: `powershell -ExecutionPolicy Bypass -File scripts/setup_first_time.ps1`
   - macOS/Linux: install backend and frontend dependencies manually:
     - `cd backend && python -m pip install -e ".[dev]"`
     - `cd ../frontend && npm install`
3. Start backend + frontend:
   - Windows: `powershell -ExecutionPolicy Bypass -File scripts/start_ui.ps1`
   - macOS/Linux: `bash scripts/start_ui.sh`
4. Open `http://127.0.0.1:5173`.

## Tests

From repository root:

```bash
python -m pytest
```

Covered areas:
- Pitch detection
- Drum transcription
- Chord recognition
- MIDI/audio export + ZIP packaging

## Desktop Packaging

- Dev shell: `cd frontend/src-tauri && cargo tauri dev`
- Build installers:
  - Windows: `cargo tauri build --bundles msi`
  - macOS: `cargo tauri build --bundles dmg,app`

## Plugin

See:
- `plugin/PLUGIN.md`
- `docs/PLUGIN.md`

