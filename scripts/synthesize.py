#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.project import Project
from engine.tts import synthesize_beats, voice_command

p = argparse.ArgumentParser(description="Synthesize documentary narration with a local TTS executable")
p.add_argument("project")
p.add_argument("--command", help="Command template, e.g. 'piper --model {model} --output_file {output}'. Defaults to a named voice slot.")
p.add_argument("--voice", default="espeak", help="Named voice slot (espeak, piper) or a command template")
p.add_argument("--model")
p.add_argument("--out-dir", default="out/narration")
a = p.parse_args()
project = Project.load(a.project)
beats = [b.__dict__ for b in project.beats]
command = a.command or voice_command(a.voice, a.model)
manifest = synthesize_beats(beats, a.out_dir, command, a.model)
print(json.dumps(manifest, indent=2))
