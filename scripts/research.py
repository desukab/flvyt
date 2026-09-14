#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.research import collect

p = argparse.ArgumentParser(description="Collect candidate sources for a FLVYT documentary")
p.add_argument("topic")
p.add_argument("--out", default="projects/research.json")
p.add_argument("--max-results", type=int, default=12)
a = p.parse_args()
print(collect(a.topic, a.out, a.max_results))
