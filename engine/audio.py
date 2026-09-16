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
                tail_pads: list[float] | None = None,
                lead_in: float = 0.0) -> Path:
    """Concatenate narration clips, inserting a pause after each clip.

    `tail_pads` carries the exact silence budget a beat's timing already
    reserved, so the narration master always lines up with the picture, and
    emphatic beats get a deliberate breath instead of narration butting into
    the next clip.
    `lead_in` prepends a fixed silence (e.g. the title-card intro) so the
    narration starts exactly when the first beat appears on screen.
    """
    if not paths:
        raise ValueError("No narration WAV files supplied")
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    pads = [float(p or 0) for p in (tail_pads or [])]
    if len(pads) < len(paths):
        pads.extend([0.0] * (len(paths) - len(pads)))
    lead = float(lead_in or 0.0)
    bank: dict[float, Path] = {}
    for sec in sorted({p for p in pads + [lead] if p > 0}):
        bank[sec] = _silence_bank(out.parent, sec)
    clips: list[Path] = []
    if lead > 0:
        clips.append(bank[lead])
    for path, pad in zip(paths, pads):
        clips.append(Path(path))
        if pad > 0:
            clips.append(bank[pad])
    # Normalize every clip (narration wavs can be 22.05k mono while the pause
    # bank is 48k stereo) through a concat *filter*, not the concat demuxer,
    # which would stitch raw samples at the wrong rate and shrink each clip.
    graph = (
        "".join(f"[{i}:a]aformat=sample_rates=48000:channel_layouts=stereo[a{i}];"
                for i in range(len(clips)))
        + "".join(f"[a{i}]" for i in range(len(clips)))
        + f"concat=n={len(clips)}:v=0:a=1[aout]"
    )
    inputs: list[str] = []
    for clip in clips:
        inputs += ["-i", str(clip)]
    run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", graph,
         "-map", "[aout]", "-ar", "48000", "-ac", "2", "-c:a", "pcm_s24le", str(out)])
    return out


def assemble_narration(beats: list[dict[str, Any]], manifest: dict[str, str],
                       output: str | Path, cwd: str | Path | None = None) -> Path:
    """Build the narration master from a project's beat plan and TTS manifest.

    The pad schedule comes from the same timing pass that sized each beat, so
    audio and picture can never drift once both are derived from the clips.
    A lead-in matching the title card widths the master to the picture, so the
    narration starts on the first beat instead of playing over the intro.
    A beat with no clip in the manifest holds its reserved screen time as
    silence, so the master always equals the picture even if one clip is lost.
    """
    from .project import INTRO_SECONDS
    root = Path(cwd) if cwd else Path.cwd()
    clips: list[Path] = []
    pads: list[float] = []
    silent: dict[float, Path] = {}
    for beat in beats:
        reserved = max(0.5, float(beat.get("seconds", 0) or 0))
        audio = manifest.get(str(beat.get("id")))
        path: Path | None = None
        if audio:
            candidate = Path(audio)
            if not candidate.is_absolute():
                probe = root / candidate
                if probe.exists():
                    candidate = probe
            if not candidate.exists():
                candidate = Path.cwd() / candidate
            if candidate.exists():
                path = candidate
        if path is None:
            if reserved not in silent:
                silent[reserved] = _silence_bank(root, reserved)
            clips.append(silent[reserved])
            pads.append(0.0)
        else:
            clips.append(path)
            pads.append(float(beat.get("pad_after", 0) or 0))
    return concat_wavs(clips, output, tail_pads=pads, lead_in=INTRO_SECONDS)


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