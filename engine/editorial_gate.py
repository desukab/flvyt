"""Validation gates for executable beat/shot editorial plans."""
from __future__ import annotations

from typing import Any

SUPPORTED_MODES = {"establish", "punch", "hold", "count", "detail", "move"}
SUPPORTED_VISUALS = {
    "title", "text", "claim", "quote", "stat", "counter", "timeline", "map",
    "image", "portrait", "logo", "broll", "company", "default",
}


def validate_shots(beats: list[Any], fps: int = 30, tolerance_frames: int = 1) -> list[str]:
    """Return hard-gate errors for shot plans.

    Shot timing is intentionally checked at frame precision: tiny floating point
    differences are harmless, but real gaps/overlaps would desynchronise the edit.
    """
    errors: list[str] = []
    tolerance = max(1, tolerance_frames) / max(1, fps)
    for beat in beats:
        shots = getattr(beat, "shots", None) or []
        if not shots:
            errors.append(f"{beat.id}: missing shot plan")
            continue
        total = 0.0
        for index, shot in enumerate(shots, 1):
            seconds = float(shot.get("seconds", 0))
            if seconds <= 0:
                errors.append(f"{beat.id}/s{index}: non-positive duration")
            visual = shot.get("visual")
            if visual not in SUPPORTED_VISUALS:
                errors.append(f"{beat.id}/s{index}: unsupported visual '{visual}'")
            mode = shot.get("mode", "hold")
            if mode not in SUPPORTED_MODES:
                errors.append(f"{beat.id}/s{index}: unsupported mode '{mode}'")
            total += seconds
        if abs(total - float(beat.seconds)) > tolerance:
            errors.append(
                f"{beat.id}: shot duration {total:.3f}s != beat {float(beat.seconds):.3f}s"
            )
    return errors


def raise_if_invalid(beats: list[Any], fps: int = 30) -> None:
    errors = validate_shots(beats, fps=fps)
    if errors:
        raise ValueError("Editorial shot gate failed:\n- " + "\n- ".join(errors))
