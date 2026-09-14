#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.transcribe import transcribe

p = argparse.ArgumentParser(description="Transcribe audio locally with faster-whisper")
p.add_argument("audio")
p.add_argument("--model", default="small")
p.add_argument("--language")
p.add_argument("--output", default="out/transcript.json")
p.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
a = p.parse_args()
transcribe(a.audio, a.model, a.language, a.output, a.device)
print(a.output)
