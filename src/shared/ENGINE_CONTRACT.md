# Shared Engine Contract (Draft)

This document defines the cross-runtime interface to keep the standalone app and future plugin aligned.

## Request

```json
{
  "mode": "notes|chords|drums|auto",
  "bpm": 120,
  "time_signature": "4/4",
  "root_note": "C",
  "scale": "major",
  "custom_scale_notes": ["C", "D", "E"],
  "mono_poly_override": "auto|mono|poly"
}
```

## Response

```json
{
  "metadata": {},
  "tracks": {
    "notes": [],
    "chords": [],
    "drums": []
  },
  "confidence": {}
}
```

