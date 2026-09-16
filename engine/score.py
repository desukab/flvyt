"""Deterministic procedural music bed (FFmpeg-only, licence-free).

Every build without a supplied music file gets a soft chapter-aware drone
composed on the spot: each chapter draws a fixed chord from a warm ladder by
its index, and stems are faded at the seams so switching is seamless. Nothing
random anywhere — the same project always produces the same WAV.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from engine.audio import run

# (root, third, fifth) in Hz for a soft documentary drone ladder.
CHORDS: list[tuple[float, float, float]] = [
    (110.00, 130.81, 164.81),   # A minor
    (130.81, 146.83, 196.00),   # C major
    (98.00, 116.54, 146.83),    # G major
    (87.31, 110.00, 130.81),    # F major
    (123.47, 146.83, 185.00),   # D minor
    (164.81, 174.61, 261.63),   # E minor
]

_TREM = "(0.72 + 0.28*sin(2*PI*0.11*t))"


def chapter_segments(beats: list[dict[str, Any]], total: float) -> list[tuple[float, float]]:
    """Time ranges covered by each chapter in the beat plan, in seconds."""
    segs: list[tuple[float, float]] = []
    last: int | None = None
    start = 0.0
    t = 0.0
    for beat in beats:
        sec = float(beat.get("seconds") or 1.0)
        chapter = int(beat.get("chapter") or 0)
        if last is None:
            last = chapter
        elif chapter != last:
            segs.append((start, t))
            start = t
            last = chapter
        t += sec
    if start < t:
        segs.append((start, t))
    if not segs:
        segs = [(0.0, max(total, 0.0))]
    elif segs[-1][1] < total:
        segs[-1] = (segs[-1][0], total)
    return segs


def _drone_expr(chord: tuple[float, float, float], detune: float) -> str:
    root, third, fifth = chord
    tones = [  # root, third, fifth, root octave — soft amplitudes, no clipping
        (root * detune, 0.050),
        (third * detune, 0.032),
        (fifth * detune, 0.020),
        (root * 2 * detune, 0.012),
    ]
    parts = [f"{a:g}*sin(2*PI*{f:g}*t)" for f, a in tones]
    return f"({' + '.join(parts)})*{_TREM}"


def _stem(chord: tuple[float, float, float], dur: float, out: Path) -> None:
    left = _drone_expr(chord, 1.000)
    right = _drone_expr(chord, 1.002)
    filters: list[str] = ["highpass=f=45", "lowpass=f=1500"]
    if dur > 1.6:
        filters.append("afade=t=in:d=0.8")
        filters.append(f"afade=t=out:st={dur - 0.8:.3f}:d=0.8")
    run([
        "ffmpeg", "-v", "error", "-y",
        "-f", "lavfi", "-i", f"aevalsrc=exprs='{left}|{right}':s=48000:d={dur:.3f}",
        "-af", ",".join(filters), "-ar", "48000", "-ac", "2",
        "-c:a", "pcm_s24le", str(out),
    ])


def render_bed(total: float, beats: list[dict[str, Any]], out: str | Path,
               work_dir: str | Path | None = None) -> dict[str, Any]:
    """Compose the chapter-aware bed and write a WAV of `total` seconds."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    work = Path(work_dir) if work_dir else out.parent
    work.mkdir(parents=True, exist_ok=True)
    total = max(total, 0.25)
    segments = chapter_segments(beats, total)
    stems: list[Path] = []
    chord_notes: list[list[float]] = []
    for chapter, (start, end) in enumerate(segments):
        chord = CHORDS[chapter % len(CHORDS)]
        dur = max(0.25, end - start)
        stem = work / f"stem_{chapter:02d}.wav"
        _stem(chord, dur, stem)
        stems.append(stem)
        chord_notes.append(list(chord))
    listing = out.with_suffix(".concat.txt")
    listing.write_text("\n".join(
        f"file '{s.resolve().as_posix()}'" for s in stems) + "\n", encoding="utf-8")
    filters: list[str] = ["volume=1.0"]
    if total > 2.4:
        filters.append("afade=t=in:d=1")
        filters.append(f"afade=t=out:st={total - 1.4:.3f}:d=1.4")
    run([
        "ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0",
        "-i", str(listing), "-af", ",".join(filters),
        "-ar", "48000", "-ac", "2", "-c:a", "pcm_s24le", str(out),
    ])
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    return {
        "wav": str(out),
        "sha256": digest,
        "chapters": len(segments),
        "seconds": round(total, 3),
        "chords": chord_notes,
        "note": "deterministic procedural bed generated locally (FFmpeg); licence-free",
    }