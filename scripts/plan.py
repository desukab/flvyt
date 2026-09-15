#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.grounding import attach_provenance
from engine.story import StoryPack, save_project

p = argparse.ArgumentParser(description="Build a deterministic documentary project from an evidence pack")
p.add_argument("evidence_json")
p.add_argument("--out", default="projects/generated.json")
a = p.parse_args()

pack = StoryPack.load(a.evidence_json)
out = save_project(pack, a.out)
raw = json.loads(Path(a.evidence_json).read_text(encoding="utf-8"))
grounding = raw.get("grounding") or {}
attach_provenance(out, {
    "evidence_pack": str(a.evidence_json),
    "method": grounding.get("method") or "unknown",
    "grounding": grounding,
    "sources": sorted({e.get("source", "") for e in raw.get("evidence", []) if e.get("source")}),
})
print(out)