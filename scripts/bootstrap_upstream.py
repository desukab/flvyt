#!/usr/bin/env python3
"""Fetch the reusable open-source production components used by FLVYT.

We intentionally keep upstream source as an explicit vendor step instead of
silently copying it without attribution. The copied files remain under
vendor/video-autopilot-kit and retain the upstream MIT notice.
"""
from __future__ import annotations
import json, shutil, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "vendor" / "upstream.lock.json"
VENDOR = ROOT / "vendor" / "video-autopilot-kit"
TMP = ROOT / ".cache" / "video-autopilot-kit"

# These are the high-value reusable pieces for FLVYT. More can be added as
# integration tests prove they are needed.
FILES = [
    "src/longform_maker/fx_lib.py",
    "src/longform_maker/audio_chain.py",
    "src/longform_maker/gate_core.py",
    "src/longform_maker/grade_lib.py",
    "src/longform_maker/grade_gate.py",
    "src/longform_maker/asset_forge.py",
    "src/longform_maker/color_workflow.py",
    "src/longform_maker/delivery.py",
    "src/longform_maker/emphasis_overlays.py",
    "src/longform_maker/word_captions.py",
    "src/longform_maker/script_gate.py",
    "src/longform_maker/plan_gate.py",
    "src/longform_maker/screen_clean.py",
]

def run(*args: str) -> None:
    print("+", " ".join(args))
    subprocess.run(args, cwd=ROOT, check=True)

def main() -> None:
    spec = json.loads(LOCK.read_text(encoding="utf-8"))["video_autopilot_kit"]
    TMP.parent.mkdir(parents=True, exist_ok=True)
    if TMP.exists():
        shutil.rmtree(TMP)
    run("git", "clone", "--depth", "1", "--branch", spec["ref"], spec["repository"], str(TMP))
    VENDOR.mkdir(parents=True, exist_ok=True)
    for rel in FILES:
        src = TMP / rel
        if not src.exists():
            raise FileNotFoundError(src)
        dst = VENDOR / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    shutil.copy2(TMP / "LICENSE", VENDOR / "LICENSE")
    (VENDOR / "UPSTREAM_SOURCE.txt").write_text(
        "Source: https://github.com/Hao0321/video-autopilot-kit\n"
        f"Ref: {spec['ref']}\n"
        "Copied by scripts/bootstrap_upstream.py\n",
        encoding="utf-8",
    )
    print(f"Vendored {len(FILES)} upstream modules into {VENDOR}")

if __name__ == "__main__":
    main()
