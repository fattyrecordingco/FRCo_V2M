# Plugin Integration Design

## Goal

Expose VINS conversion features directly inside DAWs through VST3/AU.

## Shared Engine Contract

- Inputs:
  - audio buffer windows
  - transport tempo/time signature (when host provides)
  - mode/settings (notes/chords/drums/auto, key/scale, quantization)
- Outputs:
  - per-track MIDI event streams
  - confidence + diagnostics metadata

## Runtime Model

1. Plugin collects input windows from host buffers.
2. Background worker process performs analysis outside audio thread.
3. Plugin receives event queues and flushes MIDI in sample-accurate timing.

## Safety Constraints

- No allocations in audio callback.
- Bounded queue sizes with overflow handling.
- Worker crash isolation and restart behavior.
- Deterministic fallback mode if advanced model unavailable.

## Milestones

1. Build IPC prototype from JUCE to local backend process.
2. Add session-less "stream mode" endpoint in backend.
3. Implement DAW sync handling for timeline and loop points.
4. Validate against major hosts on Windows/macOS.

