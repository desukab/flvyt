"""Local audio assembly using FFmpeg only."""
from __future__ import annotations

import subprocess
from pathlib import Path

from typing import Any


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


def _silence_bank(out_dir: Path, seconds: float) -> Path:
    """One reusable silent WAV per pad length, so pauses stay cheap and local."""
    name = f"pause_{seconds:g}s.wav"
    silence = out_dir / name
    if not silence.exists():
        run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
             f"anullsrc=r=48000:cl=stereo", "-t", f"{seconds:.3f}",
             "-ar", "48000", "-ac", "2", str(silence)])
    return silence


def concat_wavs(paths: list[str | Path], output: str | Path,
                tail_pads: list[float] | None = None) -> Path:
    """Concatenate narration clips, inserting a pause after each clip.

    `tail_pads` carries the exact silence budget a beat's timing already
    reserved, so the narration master always lines up with the picture, and
    emphatic beats get a deliberate breath instead of narration butting into
    the next clip.
    """
    if not paths:
        raise ValueError("No narration WAV files supplied")
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    pads = [float(p or 0) for p in (tail_pads or [])]
    if len(pads) < len(paths):
        pads.extend([0.0] * (len(paths) - len(pads)))
    bank: dict[float, Path] = {}
    for sec in sorted({p for p in pads if p > 0}):
        bank[sec] = _silence_bank(out.parent, sec)
    listing = out.with_suffix(".concat.txt")
    lines: list[str] = []
    for path, pad in zip(paths, pads):
        lines.append(f"file '{Path(path).resolve().as_posix()}'")
        if pad > 0:
            lines.append(f"file '{bank[pad].resolve().as_posix()}'")
    listing.write_text("\n".join(lines) + "\n", encoding="utf-8")
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
         "-ar", "48000", "-ac", "2", "-c:a", "pcm_s24le", str(out)])
    return out


def assemble_narration(beats: list[dict[str, Any]], manifest: dict[str, str],
                       output: str | Path, cwd: str | Path | None = None) -> Path:
    """Build the narration master from a project's beat plan and TTS manifest.

    The pad schedule comes from the same timing pass that sized each beat, so
    audio and picture can never drift once both are derived from the clips.
    """
    root = Path(cwd) if cwd else Path.cwd()
    paths: list[Path] = []
    pads: list[float] = []
    for beat in beats:
        audio = manifest.get(str(beat.get("id")))
        if not audio:
            continue
        path = Path(audio)
        if not path.is_absolute():
            candidate = root / path
            if candidate.exists():
                path = candidate
        if not path.exists():
            path = Path.cwd() / path
        paths.append(path)
        pads.append(float(beat.get("pad_after", 0) or 0))
    return concat_wavs(paths, output, tail_pads=pads)


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
        f"[0:a]highpass=f=70,acompressor=threshold=-18dB:ratio=3:attack=15:release=250[voice];"
        f"[voice]asplit=2[vo_a][vo_b];"
        f"[1:a]atrim=0:{dur:.3f},volume={music_volume},afade=t=in:d=1,"
        f"afade=t=out:st={max(0, dur - 2):.3f}:d=2[bedminus];"
        f"[bedminus][vo_a]sidechaincompress=threshold=0.03:ratio=8:attack=5:release=300[ducked];"
        f"[vo_b][ducked]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11"
    )
    run(["ffmpeg", "-v", "error", "-y", "-i", str(narration), "-stream_loop", "-1", "-i", str(music),
         "-filter_complex", filt, "-ar", "48000", "-ac", "2", "-t", f"{dur:.3f}", str(out)])
    return out