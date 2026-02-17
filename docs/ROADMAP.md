# V2M Roadmap

## Completed (`v0.1.0-dev`)
- Local MIDI idea generation CLI.
- Multi-style preset support.
- MIDI export and automated test baseline.
- Initial GitHub repo + tag publishing flow.

## Next (`v0.2.0`) Hum/Beatbox Core
- Audio file import workflow for humming and beatbox recordings.
- Baseline hum-to-melody MIDI extraction.
- Baseline beatbox-to-drum MIDI mapping.
- Manual scale lock and auto-scale suggestion.
- First DAW recipe card output.

## Next+ (`v0.3.0`) Producer Assistant
- Chord progression recommendations from melody context.
- Layer/arrangement suggestion engine.
- Genre filter system with optional no-filter mode.
- Multi-output package export (MIDI + recipe + analysis metadata).

## Later (`v0.4.0`) Combined Performance Input
- Hum + beatbox separation in one recording.
- Simultaneous melodic and rhythmic track extraction.
- Confidence scoring and user-editable corrections.

## Later (`v0.5.0`) Plugin Path
- Prototype DAW plugin shell (likely JUCE).
- Bridge core V2M reasoning engine to plugin UI.
- Evaluate deployment path for Ableton/FL Studio workflows.

## Risk Management
- Model quality risk: stage quality gates by workflow (hum, beatbox, combined).
- Scope risk: ship each journey incrementally before adding real-time complexity.
- Compatibility risk: maintain manual test matrix for Ableton + FL Studio.
