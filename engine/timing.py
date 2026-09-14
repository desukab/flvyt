"""Audio-driven editorial timing for production renders."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


def media_duration(path: str | Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return max(0.01, float(result.stdout.strip() or 0))


def retime_project(project_path: str | Path, manifest_path: str | Path,
                   min_seconds: float = 1.2, pad_seconds: float = 0.18) -> dict[str, Any]:
    """Make visual beat durations follow the actual local narration durations."""
    project_file = Path(project_path)
    manifest_file = Path(manifest_path)
    project = json.loads(project_file.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    changed: dict[str, float] = {}
    for beat in project.get("beats", []):
        audio = manifest.get(str(beat.get("id")))
        if not audio:
            continue
        audio_path = Path(audio)
        if not audio_path.is_absolute():
            audio_path = project_file.parent / audio_path
        if not audio_path.exists():
            # Manifest paths may be rooted at the repository output directory.
            alt = Path.cwd() / audio_path
            if alt.exists():
                audio_path = alt
            else:
                continue
        duration = media_duration(audio_path) + pad_seconds
        new_seconds = max(min_seconds, duration)
        beat["seconds"] = round(new_seconds, 3)
        changed[str(beat.get("id"))] = round(new_seconds, 3)
    project_file.write_text(json.dumps(project, indent=2, ensure_ascii=False), encoding="utf-8")
    return changed


def load_manifest(path: str | Path) -> dict[str, str]:
    return json.loads(Path(path).read_text(encoding="utf-8"))
