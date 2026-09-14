"""Sentence-level editorial grammar for automated documentary pacing.

The planner does not render anything. It converts a narration beat into a small,
intentional sequence of shots so the renderer can cut like an editor instead of
holding one card for the entire sentence.
"""
from __future__ import annotations

import re
from typing import Any


def _tokens(text: str) -> list[str]:
    return re.findall(r"\b[\w'-]+\b", text)


def make_shots(text: str, seconds: float, visual: str, emphasis: str = "normal") -> list[dict[str, Any]]:
    """Create 1–3 restrained shots from one narration beat.

    Short beats stay single-shot. Longer beats receive an establishing shot,
    detail/punch-in, and (when useful) an emphasis hold. Durations always sum to
    the original beat duration so narration remains the master clock.
    """
    duration = max(0.8, float(seconds))
    words = len(_tokens(text))
    if duration < 3.0 or words < 8:
        return [{"id": "s1", "seconds": round(duration, 3), "visual": visual, "text": text, "mode": "hold"}]

    if visual in {"text", "claim", "quote"}:
        modes = [(0.42, visual, "establish"), (0.34, visual, "punch"), (0.24, visual, "hold")]
    elif visual in {"counter", "stat"}:
        modes = [(0.36, visual, "count"), (0.38, visual, "detail"), (0.26, visual, "hold")]
    elif visual in {"map", "timeline"}:
        modes = [(0.38, visual, "establish"), (0.36, visual, "move"), (0.26, visual, "hold")]
    else:
        modes = [(0.50, visual, "establish"), (0.30, visual, "punch"), (0.20, visual, "hold")]

    if emphasis == "high":
        modes = [(0.34, modes[0][1], modes[0][2]), (0.36, modes[1][1], modes[1][2]), (0.30, modes[2][1], modes[2][2])]

    shots: list[dict[str, Any]] = []
    used = 0.0
    for i, (fraction, shot_visual, mode) in enumerate(modes):
        shot_seconds = duration * fraction if i < len(modes) - 1 else duration - used
        shot_seconds = max(0.65, shot_seconds)
        if i == len(modes) - 1:
            shot_seconds = duration - used
        used += shot_seconds
        shots.append({
            "id": f"s{i+1}",
            "seconds": round(shot_seconds, 3),
            "visual": shot_visual,
            "text": text,
            "mode": mode,
        })
    # Correct rounding drift while preserving the exact narration duration.
    shots[-1]["seconds"] = round(duration - sum(float(s["seconds"]) for s in shots[:-1]), 3)
    return shots


def add_shots(beats: list[Any]) -> list[Any]:
    """Attach executable editorial shots to Beat-like objects."""
    for beat in beats:
        beat.shots = make_shots(beat.text, beat.seconds, beat.visual, beat.emphasis)
    return beats
