from __future__ import annotations

from pathlib import Path
import subprocess
import json

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor" / "video-autopilot-kit"


def _gate():
    import sys
    sys.path.insert(0, str(VENDOR / "src"))
    try:
        from longform_maker.gate_core import report
        return report
    except ImportError:
        return lambda fails=None, warns=None, **extra: {"ok": not (fails or []), "fails": list(fails or []), "warns": list(warns or []), **extra}


def probe(path: str | Path) -> dict:
    """Basic deterministic delivery QA using ffprobe."""
    p = Path(path)
    if not p.exists():
        return _gate()([f"missing output: {p}"])
    cmd = ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(p)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return _gate()(["ffprobe failed: " + result.stderr[-500:]])
    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    video = [s for s in streams if s.get("codec_type") == "video"]
    audio = [s for s in streams if s.get("codec_type") == "audio"]
    fails = []
    if not video:
        fails.append("no video stream")
    if not audio:
        fails.append("no audio stream")
    if video and (video[0].get("width", 0) < 1280 or video[0].get("height", 0) < 720):
        fails.append("video resolution below 1280x720")
    return _gate()(fails, format=data.get("format", {}).get("format_name"))
