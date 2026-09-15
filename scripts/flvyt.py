#!/usr/bin/env python3
"""FLVYT: one command, fully local faceless tech documentary production.

Usage:
  flvyt <topic>                 Research, ground, script and produce an MP4.
  flvyt build <file>            Build from a research/evidence/project JSON.
  flvyt plan <evidence.json>    Deterministic documentary project plan.
  flvyt render <project.json>   Render a ready project to out/final.mp4.
  flvyt ingest <name> <file>    Add a license-cleared visual asset.
  flvyt doctor                  Preflight all local tools required.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.pipeline import produce

TOPIC_PATTERN = re.compile(r"^(build|plan|render|ingest|doctor)$")


def _doctor() -> int:
    from engine.env import default_reports, render_text, summarize
    reports = default_reports()
    tts_command = _tts_env()
    if tts_command:
        tts = next((r for r in reports if r["name"] == "tts"), None)
        if tts:
            tts["present"] = True
            tts["detail"] = tts_command
    print(render_text(reports))
    return 0 if summarize(reports)["ok"] else 1


def _tts_env() -> str | None:
    import os
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
        target = args[0] if args else _topic_or_usage()
        return _build(target)
    if cmd.startswith("-"):
        print(__doc__)
        return 2
    return _build(cmd, extra=args)


def _topic_or_usage() -> str:
    print(__doc__)
    raise SystemExit(2)


def _build(target: str, extra: list[str] = None) -> int:
    if TOPIC_PATTERN.match(target):
        print(f"No file listed for '{target}'; pass a topic or a JSON file")
        return 2
    path = ROOT / target
    origin = path if path.exists() else target
    topic = None
    if not Path(origin).exists():
        topic = target
    report = produce(topic=topic, source=None if topic else str(origin),
                     tts_command=_tts_env())
    print("stages:", " -> ".join(s["step"] for s in report["steps"]))
    print(f"FLVYT production build {'OK' if report['qa'].get('ok') else 'FAILED'}: {report['out']}")
    return 0 if report["qa"].get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))