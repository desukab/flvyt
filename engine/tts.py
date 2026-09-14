"""Local TTS adapter.

No cloud provider is baked in. The default interface expects a locally installed
speech engine such as Piper, but any executable accepting text/stdin and an output
path can be wired through the command template.
"""
from __future__ import annotations

import json
import shlex
import subprocess
from pathlib import Path
from typing import Any


def synthesize(text: str, output: str | Path, command: str,
               model: str | None = None) -> Path:
    """Run a local TTS command.

    Template variables: {model}, {output}. Text is always sent over stdin.
    Example: piper --model {model} --output_file {output}
    """
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    values = {"model": model or "", "output": str(out)}
    argv = shlex.split(command.format(**values))
    if not argv:
        raise ValueError("TTS command is empty")
    subprocess.run(argv, input=text, text=True, check=True)
    if not out.exists() or out.stat().st_size == 0:
        raise RuntimeError(f"TTS command completed but produced no audio: {out}")
    return out


def synthesize_beats(beats: list[dict[str, Any]], out_dir: str | Path,
                     command: str, model: str | None = None) -> dict[str, str]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, str] = {}
    for beat in beats:
        beat_id = str(beat["id"])
        text = str(beat.get("narration") or beat.get("text") or "").strip()
        if not text:
            continue
        path = out / f"{beat_id}.wav"
        synthesize(text, path, command, model)
        manifest[beat_id] = str(path)
    (out / "tts_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return manifest
