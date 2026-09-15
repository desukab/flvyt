#!/usr/bin/env python3
"""FLVYT: one command, fully local faceless tech documentary production.

Usage:
  flvyt <topic-or-file> [flags]  Research, ground, script and produce an MP4.
  flvyt build <topic-or-file> [flags]   Same, explicit command form.
  flvyt plan <evidence.json>     Deterministic documentary project plan.
  flvyt render <project.json>    Render a ready project.
  flvyt ingest <name> <file>     Add a license-cleared visual asset.
  flvyt doctor                   Preflight all local tools required.

Flags on the topic/build form (TTS comes from FLVYT_TTS_COMMAND/FLVYT_TTS_MODEL):
  --out PATH, --music PATH, --assets PATH, --max-results N,
  --captions-model NAME, --ground-model NAME, --ground-endpoint URL,
  --no-auto-captions
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.pipeline import produce, StageFailed

COMMANDS = {"build", "plan", "render", "ingest", "doctor"}
PRODUCTION_FLAGS = {
    "--out", "--music", "--assets", "--max-results", "--captions-model",
    "--ground-model", "--ground-endpoint", "--no-auto-captions", "--force",
}


def _doctor() -> int:
    from engine.env import default_reports, render_text, summarize
    reports = default_reports(tts_command=_tts_env())
    print(render_text(reports))
    return 0 if summarize(reports)["ok"] else 1


def _tts_env() -> str | None:
    return os.environ.get("FLVYT_TTS_COMMAND")


def _plan(evidence: str) -> int:
    subprocess.run([sys.executable, "scripts/plan.py", evidence, "--out", "projects/generated.json"], cwd=ROOT, check=True)
    print("projects/generated.json")
    return 0


def _render(project: str) -> int:
    subprocess.run([sys.executable, "scripts/render.py", project, "--out", "out/final.mp4"], cwd=ROOT, check=True)
    return 0


def _ingest(name: str, file: str) -> int:
    subprocess.run([sys.executable, "scripts/ingest_asset.py", file], cwd=ROOT, check=True)
    print(f"ingested {file}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(add_help=False, prog="flvyt")
    p.add_argument("--out", default="out/final.mp4")
    p.add_argument("--tts-command", default=_tts_env())
    p.add_argument("--tts-model", default=os.environ.get("FLVYT_TTS_MODEL"))
    p.add_argument("--music")
    p.add_argument("--assets", default="assets/registry.json")
    p.add_argument("--max-results", type=int, default=12)
    p.add_argument("--captions-model", default=os.environ.get("FLVYT_WHISPER_MODEL", "small"))
    p.add_argument("--ground-model", default=os.environ.get("FLVYT_LLM_MODEL", "llama3.2"))
    p.add_argument("--ground-endpoint", default=os.environ.get("FLVYT_LLM_ENDPOINT",
                                                               "http://127.0.0.1:11434/api/generate"))
    p.add_argument("--no-auto-captions", action="store_true")
    p.add_argument("--force", action="store_true",
                   help="Re-run every stage, ignoring the resume state file")
    return p


def _build(target: str, flags: list[str]) -> int:
    ns, unknown = _build_parser().parse_known_args(flags)
    if unknown:
        print(f"unknown flags: {' '.join(unknown)}")
        return 2
    path = ROOT / target
    topic = None
    if not Path(target).exists() and not path.exists():
        topic = target
    source = None if topic else str(path if path.exists() else target)
    try:
        report = produce(
            source,
            topic=topic,
            out=ns.out,
            tts_command=ns.tts_command,
            tts_model=ns.tts_model,
            music=ns.music,
            assets=ns.assets,
            max_results=ns.max_results,
            captions_model=ns.captions_model,
            ground_model=ns.ground_model,
            ground_endpoint=ns.ground_endpoint,
            auto_captions=not ns.no_auto_captions,
            force=ns.force,
        )
    except StageFailed as exc:
        failure = (exc.report or {}).get("failure", {})
        print()
        print(f"FLVYT stage '{failure.get('step', exc.stage)}' failed:")
        print("  command:", failure.get("command") or " ".join(exc.cmd))
        if exc.output:
            print("  output: " + exc.output.replace("\n", "\n          "))
        print("  " + failure.get("resume", "re-run the same build command"))
        return 1
    print("stages:", " -> ".join(s["step"] for s in report["steps"]))
    print(f"FLVYT production build {'OK' if report['qa'].get('ok') else 'FAILED'}: {report['out']}")
    return 0 if report["qa"].get("ok") else 1


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    cmd, args = argv[0], argv[1:]
    if cmd == "doctor":
        return _doctor()
    if cmd == "plan":
        if not args:
            print(__doc__)
            return 2
        return _plan(args[0])
    if cmd == "render":
        if not args:
            print(__doc__)
            return 2
        return _render(args[0])
    if cmd == "ingest":
        if len(args) < 2:
            print(__doc__)
            return 2
        return _ingest(args[0], args[1])
    if cmd == "build":
        if not args:
            print(__doc__)
            return 2
        return _build(args[0], args[1:])
    if cmd in PRODUCTION_FLAGS or cmd.startswith("-"):
        print(__doc__)
        return 2
    return _build(cmd, args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))