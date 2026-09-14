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
    """Deterministic delivery QA using ffprobe."""
    p = Path(path)
    if not p.exists():
        return _gate()([f"missing output: {p}"])
    result = subprocess.run([
        "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(p)
    ], capture_output=True, text=True)
    if result.returncode != 0:
        return _gate()(["ffprobe failed: " + result.stderr[-500:]])
    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    video = [s for s in streams if s.get("codec_type") == "video"]
    audio = [s for s in streams if s.get("codec_type") == "audio"]
    fmt = data.get("format", {})
    fails: list[str] = []
    warns: list[str] = []
    if not video:
        fails.append("no video stream")
    if not audio:
        fails.append("no audio stream")
    if video:
        if video[0].get("width", 0) < 1280 or video[0].get("height", 0) < 720:
            fails.append("video resolution below 1280x720")
        duration = float(fmt.get("duration", 0) or 0)
        if duration < 5:
            fails.append("video is shorter than 5 seconds")
        if video[0].get("codec_name") not in {"h264", "hevc", "vp9", "av1"}:
            warns.append(f"unusual video codec: {video[0].get('codec_name')}")
    if audio:
        if int(audio[0].get("sample_rate", 0) or 0) < 44100:
            warns.append("audio sample rate below 44.1 kHz")
        if audio[0].get("channels", 0) < 2:
            warns.append("audio is mono")
    return _gate()(fails, warns=warns, format=fmt.get("format_name"), duration=fmt.get("duration"))
