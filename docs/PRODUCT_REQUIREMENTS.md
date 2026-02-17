# V2M Product Requirements

## Product Vision
V2M helps musicians turn hummed and beatboxed ideas into usable DAW building blocks, even when they cannot yet recreate those ideas with traditional production skills.

## Primary User Problem
- Users can hear musical ideas in their heads.
- They can hum/beatbox those ideas.
- They struggle to convert ideas into MIDI patterns, arrangement decisions, and DAW-ready tracks.

## Target Users
- Vocal-first songwriters.
- Beginner/intermediate producers.
- Artists with strong musical intuition but limited DAW execution speed.

## Core User Journeys

## Journey A: Hum to Melody/Chords
1. User records humming through laptop or external mic.
2. App cleans noise and analyzes pitch/rhythm.
3. App infers or applies scale.
4. App exports MIDI melody.
5. App recommends chord progression alternatives.
6. App outputs a DAW recipe card (step-by-step build instructions).

## Journey B: Beatbox to Drums
1. User records beatbox groove.
2. App detects kick/snare/hihat/percussion events.
3. App maps events to drum MIDI notes.
4. App exports quantized (and optional humanized) drum MIDI.
5. App provides sample/drum-kit suggestions.

## Journey C: Hum + Beatbox Combined
1. User records both simultaneously.
2. App separates tonal and percussive components.
3. App outputs separate MIDI tracks (melody/chords/drums/bass candidate).
4. App suggests arrangement layering paths.

## Functional Requirements

## FR1 Input and Capture
- Support onboard and external microphone selection.
- Support audio file import for offline analysis.
- Save raw recordings locally with project metadata.

## FR2 Audio Cleanup
- Reduce background noise before feature extraction.
- Keep original audio unchanged as reference.

## FR3 Musical Analysis
- Estimate tempo and time signature confidence.
- Detect pitch contour and note boundaries for humming.
- Detect drum transients and classify drum roles for beatbox.

## FR4 Scale and Tonality
- Manual mode:
  - User selects root + scale.
  - Notes are snapped to nearest in-scale pitch.
- Auto mode:
  - Model proposes best-fit tonal center and scale.
- Global scale library must expand beyond basic major/minor sets.

## FR5 MIDI and DAW Outputs
- Export multitrack MIDI (`melody.mid`, `drums.mid`, `combined.mid`).
- Export optional alternate takes/variations.
- Export DAW recipe card with build steps and plugin/sound suggestions.

## FR6 Producer Assistant
- Recommend chord progressions if melody suggests harmonic movement.
- Suggest layer ideas (bass doubles, countermelody, percussion accents).
- Support optional genre tags as filters.
- Allow no-filter exploratory mode.

## FR7 Local-First Data Handling
- Recordings and generated outputs saved locally by default.
- User can reopen previous ideas and continue from snapshots.

## Non-Functional Requirements
- Local prototype should run on typical creator laptops.
- Processing should be transparent with confidence indicators.
- Exported MIDI must import cleanly into Ableton and FL Studio.

## Out of Scope (Initial Releases)
- Cloud collaboration and team sessions.
- Commercial sample marketplace integration.
- Full DAW plugin hosting inside V2M.

## MVP Acceptance Criteria (`v0.2.0` Target)
- User can record humming and get usable melody MIDI.
- User can record beatbox and get usable drum MIDI.
- User receives at least one DAW recipe card.
- User can choose manual scale or auto-detected scale.
- Manual tests pass in Ableton and FL Studio imports.
