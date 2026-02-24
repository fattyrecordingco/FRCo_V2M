# Architecture

## Overview

VINS is a local-first monorepo with a browser-first UI and desktop packaging path.

```text
React UI (frontend) -> FastAPI API (backend) -> analysis services -> project archive
                                                -> MIDI/audio outputs
```

## Frontend

- Vite React app exposing a 4-step workflow in one window.
- Uses browser APIs:
  - `MediaDevices` for microphone selection
  - `MediaRecorder` for capture
  - HTML5 drag/drop and file inputs
  - Web Audio + Tone.js for in-app MIDI audition
- Calls backend over HTTP (`/api/v1/*`).

## Backend

- FastAPI service with deterministic offline algorithms.
- Core modules:
  - `analysis_service.py`: tempo/time/key detection, mono/poly detection, notes/chords/drums extraction, quantization
  - `conversion_service.py`: end-to-end run orchestration
  - `midi_service.py`: MIDI file writing
  - `project_manager.py`: session persistence, rename, zip export, archive listing
- Persists generated outputs in `projects/`.

## Session Storage Model

```text
projects/
  session_<timestamp>_<id>/
    original/
      source.wav
    runs/
      run_001/
        audio/
        midi/
        metadata.json
      run_002/
        ...
    session.json
    exports/
      session_...zip
```

## Desktop Packaging Path

- Tauri shell in `frontend/src-tauri`.
- On startup the shell can spawn backend process (`uvicorn`) locally.
- Frontend runs in embedded webview and still supports browser test mode.

## Plugin Path

- JUCE scaffold in `plugin/`.
- Planned integration:
  - shared engine interface in `src/shared`
  - plugin IPC bridge to offline analysis runtime
  - sample-accurate MIDI emission in DAW host

