"""File and path helpers."""

from __future__ import annotations

import base64
import re
from pathlib import Path


def sanitize_filename(name: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9._-]+", "_", name.strip())
    clean = clean.strip("._")
    return clean or "untitled"


def encode_file_base64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")

