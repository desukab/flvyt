#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.director import direct
from engine.project import Project


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
        props.write_text(json.dumps(project.props(), indent=2), encoding="utf-8")
        frames = project.duration_frames()
        cmd = [
            "npx", "remotion", "render", "remotion/src/index.tsx", "Documentary",
            str(out), "--props", str(props), "--frames", f"0-{frames - 1}",
        ]
        print("Rendering:", " ".join(cmd))
        subprocess.run(cmd, cwd=ROOT, check=True)

    print(f"Rendered {out}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
