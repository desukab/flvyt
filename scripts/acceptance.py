#!/usr/bin/env python3
"""Run the deterministic production acceptance path with generated narration."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.audio import concat_wavs
from engine.editorial import add_shots
from engine.editorial_gate import raise_if_invalid
from engine.project import INTRO_SECONDS, Project
from engine.quality import probe
from engine.transitions import assign_transitions


def make_tone(path: Path, seconds: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        "ffmpeg", "-v", "error", "-y",
        "-f", "lavfi", "-i", f"sine=frequency=220:duration={seconds:.3f}",
        "-ar", "48000", "-ac", "1", str(path),
    ], check=True)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Run the deterministic production acceptance render")
    p.add_argument("project", nargs="?", default="projects/production_acceptance.json")
    p.add_argument("--out", default="out/acceptance/acceptance.mp4")
    args = p.parse_args(argv)

    project_path = ROOT / args.project if not Path(args.project).is_absolute() else Path(args.project)
    out = ROOT / args.out if not Path(args.out).is_absolute() else Path(args.out)
    project = Project.load(project_path)
    # Exercise the same executable shot grammar used by production builds.
    add_shots(project.beats)
    assign_transitions(project.beats)
    raise_if_invalid(project.beats, fps=project.fps)
    # The tones below are authored to each beat's seconds, so the picture must
    # follow those exact durations instead of re-flooring to a reading rate.
    # Floor the fixture's own durations to the readability budget here so the
    # editorial density gate sees real-time card text.
    from engine.story import read_need
    for beat in project.beats:
        beat.seconds = round(max(float(beat.seconds), read_need(beat.text)), 2)
    project.timed_by_audio = True
    runtime_project = ROOT / "out/acceptance/production_runtime.json"
    runtime_project.parent.mkdir(parents=True, exist_ok=True)
    runtime_project.write_text(json.dumps(project.props(), indent=2, ensure_ascii=False), encoding="utf-8")

    narration_dir = ROOT / "out/acceptance/narration"
    narration_dir.mkdir(parents=True, exist_ok=True)
    wavs: list[Path] = []
    for beat in project.beats:
        wav = narration_dir / f"{beat.id}.wav"
        make_tone(wav, beat.seconds)
        wavs.append(wav)

    master = concat_wavs(wavs, narration_dir / "master.wav", lead_in=INTRO_SECONDS)
    subprocess.run([
        sys.executable, str(ROOT / "scripts/render.py"),
        str(runtime_project), "--out", str(out), "--narration", str(master),
    ], cwd=ROOT, check=True)

    report = probe(out)
    if not report.get("ok"):
        raise SystemExit("Acceptance delivery QA failed")

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
    runtime_reloaded = Project.load(runtime_project)
    expected = runtime_reloaded.duration_frames() / runtime_reloaded.fps
    if duration < expected - 0.25:
        raise SystemExit(f"Acceptance output is too short: {duration:.2f}s < {expected:.2f}s")

    print(json.dumps({"ok": True, "output": str(out), "duration": duration, "expected": expected}, indent=2))
    print(f"ACCEPTANCE PASS: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
