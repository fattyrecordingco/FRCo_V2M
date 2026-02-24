# Roadmap

## Phase 1 (Completed in this rebuild)

- Replace legacy MVP with full monorepo structure.
- Implement FastAPI backend and React 4-step wizard.
- Add local session archive, file management, and ZIP export.
- Add Tauri packaging scaffold and JUCE plugin scaffold.
- Add unit tests and CI baseline.

## Phase 2

- Improve drum transcription with optional heavier offline model packs.
- Add richer chord vocabulary and confidence visual diagnostics.
- Add waveform region editing and per-track quantize strength controls.
- Add real drag-to-DAW behavior in desktop shell (native file drag APIs).

## Phase 3

- Shared engine abstraction in `src/shared`.
- Plugin-to-engine local IPC transport.
- Real-time-safe buffering and low-latency conversion in JUCE host.
- Host compatibility test matrix automation.

## Phase 4

- Optional online model updates/downloads without account requirements.
- Automatic model quality selection based on device capability.
- Packaged model manager with version pinning and rollback.

