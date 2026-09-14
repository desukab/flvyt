"""Local audio assembly using FFmpeg only."""
from __future__ import annotations

import subprocess
from pathlib import Path


def run(args: list[str]) -> None:
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError((result.stderr or "ffmpeg failed")[-2000:])


def duration(path: str | Path) -> float:
    result = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", str(path)
    ], capture_output=True, text=True, check=True)
    return float(result.stdout.strip() or 0)


def concat_wavs(paths: list[str | Path], output: str | Path) -> Path:
    if not paths:
        raise ValueError("No narration WAV files supplied")
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    listing = out.with_suffix(".concat.txt")
    listing.write_text("".join(f"file '{Path(p).resolve().as_posix()}'\n" for p in paths), encoding="utf-8")
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
         "-ar", "48000", "-ac", "2", "-c:a", "pcm_s24le", str(out)])
    return out


def mix(narration: str | Path, music: str | Path | None, output: str | Path,
        music_volume: float = 0.20) -> Path:
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    if not music:
        run(["ffmpeg", "-v", "error", "-y", "-i", str(narration), "-af",
             "highpass=f=70,acompressor=threshold=-18dB:ratio=3:attack=15:release=250,loudnorm=I=-14:TP=-1.5:LRA=11",
             "-ar", "48000", "-ac", "2", str(out)])
        return out
    dur = duration(narration)
    filt = (
        f"[0:a]highpass=f=70,acompressor=threshold=-18dB:ratio=3:attack=15:release=250[v];"
        f"[1:a]atrim=0:{dur:.3f},volume={music_volume},afade=t=in:d=1,"
        f"afade=t=out:st={max(0,dur-2):.3f}:d=2[m];"
        f"[m][v]sidechaincompress=threshold=0.03:ratio=8:attack=5:release=300[duck];"
        f"[v][duck]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11"
    )
    run(["ffmpeg", "-v", "error", "-y", "-i", str(narration), "-stream_loop", "-1", "-i", str(music),
         "-filter_complex", filt, "-ar", "48000", "-ac", "2", "-t", f"{dur:.3f}", str(out)])
    return out
