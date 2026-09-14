#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str]) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)


p = argparse.ArgumentParser(description="Build a FLVYT documentary from an evidence pack or project")
p.add_argument("input", help="Evidence JSON or ready project JSON")
p.add_argument("--out", default="out/final.mp4")
p.add_argument("--tts-command", help="Optional local TTS command template")
p.add_argument("--tts-model")
p.add_argument("--music")
args = p.parse_args()

source = Path(args.input)
if not source.is_absolute():
    source = ROOT / source
project = source
if source.name.endswith("evidence.example.json") or "evidence" in source.name:
    project = ROOT / "projects/generated.json"
    run([sys.executable, "scripts/plan.py", str(source), "--out", str(project)])

if args.tts_command:
    cmd = [sys.executable, "scripts/synthesize.py", str(project), "--command", args.tts_command, "--out-dir", "out/narration"]
    if args.tts_model:
        cmd += ["--model", args.tts_model]
    run(cmd)

render = [sys.executable, "scripts/render.py", str(project), "--out", args.out]
if args.music:
    render += ["--music", args.music]
run(render)
print(f"FLVYT build complete: {args.out}")
