from __future__ import annotations

from pathlib import Path
import re
import statistics
import subprocess
import json

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor" / "video-autopilot-kit"

# MP4-level editorial gates. These run on the *delivered* file, so a build that
# slips a silent tail or a stalled edit past a plan check still fails here.
MAX_SILENT_TAIL = 1.5       # seconds of dead air allowed after the last word
CUT_MEDIAN_LIMIT = 8.0      # median cut-to-cut interval a slide-show exceeds
CUT_MAX_GAP = 15.0          # longest no-cut stretch before the edit is stalling
CUT_MIN_INTERVAL = 1.0      # group cuts closer than this as one transition
CUT_THRESHOLD = 0.10        # libav scene-change score treated as a cut
# (hard cuts and dips register well above 0.10 while text changes and camera
# drift on a documentary slide-show sit between 0.02 and 0.08, so the absolute
# scene-score keeps the edit-cadence gate honest.)


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


def media_duration(path: str | Path) -> float | None:
    result = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", str(path),
    ], capture_output=True, text=True)
    try:
        return float(result.stdout.strip() or 0)
    except (ValueError, OSError):
        return None


def _ffmpeg(stdout_only: list[str], *, timeout: int = 600) -> tuple[str | None, str]:
    """Run ffmpeg capturing combined output; (output, error) or (None, error)."""
    try:
        proc = subprocess.run(stdout_only, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, str(exc)
    return (proc.stdout or "") + "\n" + (proc.stderr or ""), ""


def scene_cuts(path: str | Path, threshold: float = CUT_THRESHOLD,
               min_interval: float = CUT_MIN_INTERVAL) -> dict:
    """Cut times from libav's scene-change detector, grouped by transition.

    Hard cuts and dips register well above the 0.10 scene-score while text
    changes and camera drift stay below it, so an absolute score keeps the gate
    honest. Low on machinery (ffmpeg only, stdlib parsing), so it runs in CI.
    A video with no cuts at all — or one whose cuts are minutes apart — is a
    slideshow.
    """
    p = Path(path)
    if not p.exists():
        return _gate()([f"missing output: {p}"])
    duration = media_duration(p) or 0.0
    text, err = _ffmpeg([
        "ffmpeg", "-v", "info", "-i", str(p),
        "-vf", f"select='gt(scene,{threshold})',showinfo",
        "-an", "-f", "null", "-",
    ])
    if text is None:
        return _gate()([f"scene-cut probe failed: {err[-200:]}"])
    times: list[float] = []
    for line in text.splitlines():
        m = re.search(r"pts_time:(\d+(?:\.\d+)?)", line)
        if m:
            times.append(float(m.group(1)))
    times.sort()
    cuts: list[float] = []
    for t in times:
        if not cuts or t - cuts[-1] >= min_interval:
            cuts.append(t)
    intervals = [cuts[i + 1] - cuts[i] for i in range(len(cuts) - 1)]
    median = statistics.median(intervals) if intervals else duration
    max_gap = max(intervals) if intervals else duration
    fails: list[str] = []
    warns: list[str] = []
    if len(cuts) and median > CUT_MEDIAN_LIMIT:
        fails.append(f"median cut interval {median:.1f}s exceeds {CUT_MEDIAN_LIMIT:.0f}s")
    if len(cuts) and max_gap > CUT_MAX_GAP:
        fails.append(f"longest no-cut stretch {max_gap:.1f}s exceeds {CUT_MAX_GAP:.0f}s")
    if not cuts and duration > CUT_MEDIAN_LIMIT:
        fails.append(f"no scene cuts detected in a {duration:.0f}s video: it never cuts")
    return _gate()(
        fails, warns=warns, cuts=len(cuts), cut_median=round(median, 2),
        cut_max_gap=round(max_gap, 2),
        first_cut_at=round(cuts[0], 2) if cuts else None,
        last_cut_at=round(cuts[-1], 2) if cuts else None,
    )


def silence_tail(path: str | Path, noise_db: float = -45.0,
                 min_silence: float = 1.0) -> dict:
    """Dead-air after the final word, via libav's silencedetect.

    The last narration word should land within ~1.5s of the end. Anything more
    is a build that stretched its picture past the voice (or a botched mix).
    """
    p = Path(path)
    if not p.exists():
        return _gate()([f"missing output: {p}"])
    duration = media_duration(p) or 0.0
    text, err = _ffmpeg([
        "ffmpeg", "-v", "info", "-i", str(p), "-af",
        f"silencedetect=n={noise_db}dB:d={min_silence}", "-f", "null", "-",
    ])
    if text is None:
        return _gate()([f"silence probe failed: {err[-200:]}"])
    starts: list[float] = []
    ends: list[float] = []
    for line in text.splitlines():
        m = re.search(r"silence_start:\s*([\d.]+)", line)
        if m:
            starts.append(float(m.group(1)))
        m = re.search(r"silence_end:\s*([\d.]+)", line)
        if m:
            ends.append(float(m.group(1)))
    last_sound = 0.0
    trailing = None
    if starts:
        for i, start in enumerate(starts):
            end = ends[i] if i < len(ends) else None
            if end is None:
                trailing = start            # silence never resumes
            elif end >= duration - 1.0 and i == len(starts) - 1:
                trailing = start            # silence runs to end of container
            else:
                last_sound = max(last_sound, end)
        if trailing is not None:
            last_sound = max(last_sound, trailing)
    tail = 0.0 if not starts else max(0.0, duration - last_sound)
    ok = tail <= MAX_SILENT_TAIL
    fails = [] if ok else [
        f"silent tail {tail:.1f}s exceeds {MAX_SILENT_TAIL:.1f}s "
        f"(audio ends at {last_sound:.1f}s of {duration:.1f}s)"]
    return _gate()(fails, warns=[], tail=round(tail, 3),
                   last_sound=round(last_sound, 3), silent_blocks=len(starts))


def probe_delivery(path: str | Path, *, expect_narration: bool = False) -> dict:
    """Delivery QA: container, picture signal, edit cadence and (if narrated)
    silent-tail. This is the gate a shipped MP4 must clear."""
    base = probe(path)
    frames = probe_frames(path)
    edits = scene_cuts(path)
    fails = list(base.get("fails") or []) + list(frames.get("fails") or [])
    warns = list(base.get("warns") or []) + list(frames.get("warns") or [])
    fails += edits.get("fails") or []
    warns += edits.get("warns") or []
    tails: dict = {"ok": True, "tail": 0.0, "note": "no narration; tail not scored"}
    if expect_narration:
        tails = silence_tail(path)
        fails += tails.get("fails") or []
        warns += tails.get("warns") or []
    metrics = {k: v for k, v in edits.items()
               if k not in {"ok", "fails", "warns", "engine"}}
    metrics.update({k: v for k, v in tails.items()
                    if k not in {"ok", "fails", "warns", "engine"}})
    return _gate()(fails, warns=warns, duration=base.get("duration"),
                   **metrics)
