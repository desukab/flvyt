#!/usr/bin/env python3
"""Production FLVYT research/evidence-to-video build.

Delegates to the shared engine pipeline so the documented `flvyt` flow and this
script always behave identically.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.pipeline import produce, StageFailed

p = argparse.ArgumentParser(description="Production FLVYT research/evidence-to-video build")
p.add_argument("input", nargs="?", help="Research JSON, evidence JSON or ready project JSON")
p.add_argument("--topic", help="Documentary topic; triggers research and grounding")
p.add_argument("--out", default="out/final.mp4")
p.add_argument("--tts-command", default=os.environ.get("FLVYT_TTS_COMMAND"), help="Local TTS command template")
p.add_argument("--tts-model", default=os.environ.get("FLVYT_TTS_MODEL"))
p.add_argument("--music")
p.add_argument("--assets", default="assets/registry.json", help="License-cleared asset registry")
p.add_argument("--captions-model", default=os.environ.get("FLVYT_WHISPER_MODEL", "small"))
p.add_argument("--ground-model", default=os.environ.get("FLVYT_LLM_MODEL", "llama3.2"))
p.add_argument("--ground-endpoint", default=os.environ.get("FLVYT_LLM_ENDPOINT", "http://127.0.0.1:11434/api/generate"))
p.add_argument("--no-auto-captions", action="store_true")
p.add_argument("--force", action="store_true",
               help="Re-run every stage, ignoring the resume state file")
args = p.parse_args()

try:
    report = produce(
        args.input,
        topic=args.topic,
        out=args.out,
        tts_command=args.tts_command,
        tts_model=args.tts_model,
        music=args.music,
        assets=args.assets,
        captions_model=args.captions_model,
        ground_model=args.ground_model,
        ground_endpoint=args.ground_endpoint,
        auto_captions=not args.no_auto_captions,
        force=args.force,
    )
except StageFailed as exc:
    failure = (exc.report or {}).get("failure", {})
    print()
    print(f"FLVYT stage '{failure.get('step', exc.stage)}' failed:")
    print("  command:", failure.get("command") or " ".join(exc.cmd))
    if exc.output:
        print("  output: " + exc.output.replace("\n", "\n          "))
    print("  " + failure.get("resume", "re-run the same build command"))
    raise SystemExit(1)
ok = bool(report["qa"].get("ok"))
print("stages:", " -> ".join(s["step"] for s in report["steps"]))
print(f"FLVYT production build {'OK' if ok else 'FAILED'}: {report['out']}")
raise SystemExit(0 if ok else 1)