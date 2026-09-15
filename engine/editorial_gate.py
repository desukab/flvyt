"""Validation gates for executable beat/shot editorial plans."""
from __future__ import annotations

from typing import Any

from .transitions import SUPPORTED_TRANSITIONS, transition_frames

SUPPORTED_MODES = {"establish", "punch", "hold", "count", "detail", "move"}
SUPPORTED_VISUALS = {
  "title","claim","text","quote","stat","counter","timeline",
  "map","chart","image","portrait","logo","broll","company","default",
  "chapter","section"
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
        noncuts = 0
        previous_transition = "cut"
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
            transition = str(shot.get("transition", "cut"))
            if transition not in SUPPORTED_TRANSITIONS:
                errors.append(f"{beat.id}/s{index}: unsupported transition '{transition}'")
            elif transition != "cut":
                required = transition_frames(transition, fps)
                frames = int(shot.get("transitionFrames", 0))
                if frames != required:
                    errors.append(
                        f"{beat.id}/s{index}: {transition} needs {required} frames, got {frames}"
                    )
                if previous_transition == transition:
                    errors.append(
                        f"{beat.id}/s{index}: repeated {transition} on adjacent shots "
                        f"violates the no-spam rule"
                    )
                noncuts += 1
            previous_transition = transition
            total += seconds
        if noncuts > 1:
            errors.append(f"{beat.id}: more than one non-cut transition per beat")
        if abs(total - float(beat.seconds)) > tolerance:
            errors.append(
                f"{beat.id}: shot duration {total:.3f}s != beat {float(beat.seconds):.3f}s"
            )
    for previous_beat, beat in zip(beats, beats[1:]):
        prev_shots = getattr(previous_beat, "shots", None) or []
        cur_shots = getattr(beat, "shots", None) or []
        if not prev_shots or not cur_shots:
            continue
        prev_last = str(prev_shots[-1].get("transition", "cut"))
        cur_first = str(cur_shots[0].get("transition", "cut"))
        if prev_last != "cut" and prev_last == cur_first:
            errors.append(
                f"{beat.id}: repeated {cur_first} across beat boundary "
                f"({previous_beat.id}->{beat.id}) violates the no-spam rule"
            )
    return errors


def raise_if_invalid(beats: list[Any], fps: int = 30) -> None:
    errors = validate_shots(beats, fps=fps)
    if errors:
        raise ValueError("Editorial shot gate failed:\n- " + "\n- ".join(errors))
