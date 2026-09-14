#!/usr/bin/env python3
"""Run the deterministic production acceptance path with generated narration.

This is intentionally dependency-light: CI can prove the complete video/audio/QA
plumbing without requiring a paid API, local LLM, or a particular TTS engine.
Real TTS is tested separately when FLVYT_TTS_COMMAND is configured.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.audio import concat_wavs
from engine.project import Project


def make_tone(path: Path, seconds: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        "ffmpeg", "-v", "error", "-y",
        "-f", "lavfi", "-i", f"sine=frequency=220:duration={seconds:.3f}",
        "-ar", "48000", "-ac", "1", str(path),
    ], check=True)


def main() -> int:
    project_path = ROOT / "projects/production_acceptance.json"
    project = Project.load(project_path)
    narration_dir = ROOT / "out/acceptance/narration"
    narration_dir.mkdir(parents=True, exist_ok=True)
    wavs = []
    for beat in project.beats:
        wav = narration_dir / f"{beat.id}.wav"
        make_tone(wav, beat.seconds)
        wavs.append(wav)
    master = concat_wavs(wavs, narration_dir / "master.wav")
    out = ROOT / "out/acceptance/acceptance.mp4"
    subprocess.run([
        sys.executable, str(ROOT / "scripts/render.py"),
        str(project_path), "--out", str(out), "--narration", str(master),
    ], cwd=ROOT, check=True)
    print(f"ACCEPTANCE PASS: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
