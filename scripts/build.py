#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.asset_director import assign_assets
from engine.audio import assemble_narration, concat_wavs
from engine.editorial import add_shots
from engine.editorial_gate import raise_if_invalid
from engine.project import Project
from engine.timing import retime_project
from engine.transitions import assign_transitions


def run(cmd: list[str]) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)


def refresh_editorial_plan(path: Path) -> None:
    """Regenerate sentence-level shots after any timing mutation."""
    project = Project.load(path)
    add_shots(project.beats)
    assign_transitions(project.beats)
    raise_if_invalid(project.beats, fps=project.fps)
    path.write_text(json.dumps(project.props(), indent=2, ensure_ascii=False), encoding="utf-8")


p = argparse.ArgumentParser(description="Production FLVYT research/evidence-to-video build")
p.add_argument("input", help="Research JSON, evidence JSON or ready project JSON")
p.add_argument("--out", default="out/final.mp4")
p.add_argument("--tts-command", default=os.environ.get("FLVYT_TTS_COMMAND"), help="Local TTS command template")
p.add_argument("--tts-model", default=os.environ.get("FLVYT_TTS_MODEL"))
p.add_argument("--music")
p.add_argument("--assets", default="assets/registry.json", help="License-cleared asset registry")
p.add_argument("--captions-model", default=os.environ.get("FLVYT_WHISPER_MODEL", "small"))
p.add_argument("--ground-model", default=os.environ.get("FLVYT_LLM_MODEL", "llama3.2"))
p.add_argument("--ground-endpoint", default=os.environ.get("FLVYT_LLM_ENDPOINT", "http://127.0.0.1:11434/api/generate"))
p.add_argument("--no-auto-captions", action="store_true")
args = p.parse_args()

source = Path(args.input)
if not source.is_absolute():
    source = ROOT / source
raw = json.loads(source.read_text(encoding="utf-8"))
project = source

if isinstance(raw, dict) and "sources" in raw and "evidence" not in raw and "beats" not in raw:
    evidence = ROOT / "projects/evidence.generated.json"
    run([sys.executable, "scripts/ground.py", str(source), "--out", str(evidence), "--model", args.ground_model, "--endpoint", args.ground_endpoint])
    project = ROOT / "projects/generated.json"
    run([sys.executable, "scripts/plan.py", str(evidence), "--out", str(project)])
elif isinstance(raw, dict) and "evidence" in raw and "beats" not in raw:
    project = ROOT / "projects/generated.json"
    run([sys.executable, "scripts/plan.py", str(source), "--out", str(project)])

registry = ROOT / args.assets if not Path(args.assets).is_absolute() else Path(args.assets)
if registry.exists():
    planned = assign_assets(Project.load(project), registry, ROOT)
    project = ROOT / "projects/asset_planned.json"
    project.write_text(json.dumps(planned.props(), indent=2, ensure_ascii=False), encoding="utf-8")

# Establish an executable editorial plan before narration, and validate it.
refresh_editorial_plan(project)

manifest = ROOT / "out/narration/tts_manifest.json"
if args.tts_command:
    cmd = [sys.executable, "scripts/synthesize.py", str(project), "--command", args.tts_command, "--out-dir", "out/narration"]
    if args.tts_model:
        cmd += ["--model", args.tts_model]
    run(cmd)
    if manifest.exists():
        retime_project(project, manifest)
        # TTS is the master clock: regenerate shots from the new beat durations.
        refresh_editorial_plan(project)
        manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
        beats_data = json.loads(project.read_text(encoding="utf-8"))["beats"]
        if any(b["id"] in manifest_data for b in beats_data):
            assemble_narration(beats_data, manifest_data, ROOT / "out/narration/master.wav", cwd=ROOT)

transcript = None
if args.tts_command and not args.no_auto_captions:
    transcript = ROOT / "out/narration/transcript.json"
    run([sys.executable, "scripts/transcribe.py", "out/narration/master.wav", "--model", args.captions_model, "--output", str(transcript)])

render = [sys.executable, "scripts/render.py", str(project), "--out", args.out]
if args.music:
    render += ["--music", args.music]
if transcript:
    render += ["--transcript", str(transcript)]
run(render)
print(f"FLVYT production build complete: {args.out}")
