#!/usr/bin/env python3
"""Run the deterministic production acceptance path with generated narration.

This proves the real video/audio/mux/QA plumbing without requiring paid APIs or a
particular TTS engine. The same renderer is used by the live local build path.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.audio import concat_wavs
from engine.project import Project
from engine.quality import probe


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

    wavs: list[Path] = []
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

    report = probe(out)
    if not report.get("ok"):
        raise SystemExit("Acceptance delivery QA failed")

    # The acceptance render must contain both streams and must not silently collapse
    # to the short silent-smoke path. Compare the measured output against the project.
    probe_json = subprocess.run([
        "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(out)
    ], capture_output=True, text=True, check=True)
    data = json.loads(probe_json.stdout)
    streams = data.get("streams", [])
    if not any(s.get("codec_type") == "video" for s in streams):
        raise SystemExit("Acceptance output has no video stream")
    if not any(s.get("codec_type") == "audio" for s in streams):
        raise SystemExit("Acceptance output has no audio stream")

    duration = float(data.get("format", {}).get("duration", 0) or 0)
    expected = project.duration_frames() / project.fps
    if duration < expected - 0.25:
        raise SystemExit(f"Acceptance output is too short: {duration:.2f}s < {expected:.2f}s")

    print(json.dumps({"ok": True, "output": str(out), "duration": duration, "expected": expected}, indent=2))
    print(f"ACCEPTANCE PASS: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
