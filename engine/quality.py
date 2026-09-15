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


def probe_frames(path: str | Path) -> dict:
    """Frame-level delivery QA: sample the picture stream with signalstats.

    Catches the failures a container probe cannot see: an entirely black or
    void render. The documentary is deliberately dark (letterbox gradients,
    navy glass cards), so this checks for an absence of ANY bright signal
    (white text, charts, highlights) rather than a low average luma.
    """
    p = Path(path)
    if not p.exists():
        return _gate()([f"missing output: {p}"])
    ffmpeg = subprocess.run([
        "ffmpeg", "-v", "error", "-i", str(p), "-vf",
        "fps=1,signalstats,metadata=print:file=-",
        "-f", "null", "-",
    ], capture_output=True, text=True, timeout=600)
    if ffmpeg.returncode != 0:
        return _gate()([f"signalstats failed: {ffmpeg.stderr[-400:]}"])
    avg, mx = _luma_samples(ffmpeg.stdout)
    fails: list[str] = []
    warns: list[str] = []
    info: dict = {}
    if mx:
        dim = [v for v in mx if v < 24.0]
        share_dim = len(dim) / len(mx)
        if share_dim > 0.95:
            fails.append(f"render carries no visible signal: {share_dim * 100:.0f}% of samples never exceed 24 luma")
        elif share_dim > 0.40:
            warns.append(f"long stretches with no bright pixels: {share_dim * 100:.0f}% of samples cap below 24 luma")
        mx_sorted = sorted(mx)
        avg_sorted = sorted(avg)
        info = {
            "samples": len(mx),
            "luma_max_min": round(mx_sorted[0], 1),
            "luma_max_p5": round(mx_sorted[max(0, int(len(mx) * 0.05) - 1)], 1),
            "luma_avg_p5": round(avg_sorted[max(0, int(len(avg) * 0.05) - 1)], 1),
            "dim_share": round(share_dim, 3),
        }
    else:
        fails.append("no luma samples extracted")
    return _gate()(fails, warns=warns, **info)


def _luma_samples(stdout: str) -> tuple[list[float], list[float]]:
    avg: list[float] = []
    mx: list[float] = []
    for line in stdout.splitlines():
        if "signalstats.YAVG=" in line and "lavfi." in line:
            try:
                avg.append(float(line.split("=")[1].strip()))
            except ValueError:
                pass
        elif "signalstats.YMAX=" in line and "lavfi." in line:
            try:
                mx.append(float(line.split("=")[1].strip()))
            except ValueError:
                pass
    return avg, mx
