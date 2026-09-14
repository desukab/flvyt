#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.director import direct
from engine.project import Project
from engine.quality import probe


def main() -> int:
    p = argparse.ArgumentParser(description="Render a FLVYT documentary project")
    p.add_argument("project", help="Path to project JSON")
    p.add_argument("--out", default="out/final.mp4")
    args = p.parse_args()

    project = direct(Project.load(args.project))
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="flvyt_") as td:
        props = Path(td) / "props.json"
        rendered = Path(td) / "rendered.mp4"
        final = Path(td) / "final.mp4"
        props.write_text(json.dumps(project.props(), indent=2), encoding="utf-8")
        frames = project.duration_frames()
        cmd = [
            "npx", "remotion", "render", "remotion/src/index.tsx", "Documentary",
            str(rendered), "--props", str(props), "--frames", f"0-{frames - 1}",
        ]
        print("Rendering:", " ".join(cmd))
        subprocess.run(cmd, cwd=ROOT, check=True)

        # The documentary pipeline will later replace this silent track with
        # narration + music from the upstream audio chain. Keeping a real audio
        # stream now makes delivery QA exercise the same final contract.
        subprocess.run([
            "ffmpeg", "-v", "error", "-y", "-i", str(rendered),
            "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
            "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac",
            "-b:a", "192k", "-shortest", str(final),
        ], check=True)
        final.replace(out)

    report = probe(out)
    print(json.dumps(report, indent=2))
    if not report.get("ok"):
        raise SystemExit("FLVYT delivery QA failed")
    print(f"Rendered and QA-passed: {out}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
