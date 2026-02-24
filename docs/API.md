# API Reference

Base URL: `http://127.0.0.1:8000/api/v1`

## `POST /analyze`

Analyzes uploaded audio and generates MIDI/audio assets for a conversion run.

Form fields:
- `file` (required): audio file
- `mode`: `notes | chords | drums | auto`
- `auto_pitch_time`: `true | false`
- `root_note`: `C..B`
- `scale`: `major | minor | ... | custom`
- `custom_scale_notes`: comma-separated note names
- `bpm`: numeric optional override
- `time_signature`: e.g. `4/4`
- `mono_poly_override`: `auto | mono | poly`
- `session_id`: optional existing session for regeneration

Returns:
- metadata (tempo, time signature, key/scale, confidence, timestamps, selections)
- `midi_files[]` and `audio_files[]` including URLs and base64 payloads
- `session_id` and `run_id`

## `POST /convert-notes`

Forces notes mode conversion.

## `POST /convert-chords`

Forces chords mode conversion.

## `POST /convert-drums`

Forces drums mode conversion.

## `GET /sessions`

Lists saved session summaries.

## `GET /sessions/{session_id}/files`

Lists all MIDI/audio files for all runs in session.

## `GET /files/{session_id}/{file_path}`

Downloads an individual file.

## `POST /files/{session_id}/rename`

Renames a file on disk.

Body:

```json
{
  "kind": "midi",
  "relative_path": "runs/run_001/midi/notes.mid",
  "new_name": "lead_take.mid"
}
```

## `GET /sessions/{session_id}/zip`

Downloads ZIP containing all generated files for that session with `midi/`, `audio/`, and `metadata/`.

## `GET /demo-files`

Lists WAV files in `examples/` for "Try Demo".

