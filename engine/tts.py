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

# Named voice slots. Anything local and consenting works; the value is an
# executable template using {model} and {output}, piped text on stdin.
VOICES: dict[str, str] = {
    "espeak": "espeak-ng -w {output}",
    "piper": "piper --model {model} --output_file {output}",
}


def voice_command(name: str, model: str | None = None) -> str:
    """Resolve a named voice slot to a command template.

    `name` may be a registered key or a literal command template, so existing
    callers keep working while new backends stay one line away.
    """
    template = VOICES.get(name, name)
    if not template:
        raise ValueError("voice slot is empty; pass a template or a known name")
    # Validate eagerly: the template must leave an output path placeholder and
    # must not introduce placeholders besides the two we can fill.
    try:
        template.format(model=model or "", output="X")
    except (KeyError, IndexError) as exc:
        raise ValueError(f"bad voice command template: {exc}") from exc
    return VOICES[name] if name in VOICES else name


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
