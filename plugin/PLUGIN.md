# VINS Plugin Plan

This folder contains a JUCE scaffold for VST3/AU builds and defines the path to integrate the shared VINS transcription engine.

## Current State

- Builds a loadable plugin target (`VST3`, `AU`) with a minimal editor.
- Accepts and produces MIDI.
- Pass-through audio processor with a simple parameter state.

## Build

1. Install CMake 3.22+ and a native compiler:
   - Windows: Visual Studio 2022 with C++ workload
   - macOS: Xcode command line tools
2. Configure and build:
   - `cmake -S plugin -B plugin/build`
   - `cmake --build plugin/build --config Release`

## Integration Strategy

1. Move analysis algorithms into a portable shared engine (`src/shared`) with deterministic interfaces.
2. Add an offline worker process exposed via local IPC for plugin requests.
3. In JUCE:
   - Capture audio/MIDI input buffer windows.
   - Stream windows to shared engine.
   - Receive note/chord/drum events and emit MIDI in sample-accurate timing.
4. Add DAW-facing controls:
   - Mode (notes/chords/drums/auto)
   - Scale/root/BPM/time signature
   - Quantize strength
   - Drum class confidence threshold
5. Add preset and state serialization through JUCE ValueTree.

## Validation Gates Before Full Plugin Feature Rollout

- Real-time safety (no allocation in audio thread)
- Offline batch bounce accuracy against standalone backend
- Host compatibility matrix:
  - Ableton Live (Win/macOS)
  - Logic Pro (macOS/AU)
  - FL Studio (Win/VST3)
  - Reaper (Win/macOS)

