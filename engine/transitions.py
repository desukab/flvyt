"""Deterministic cut/transition grammar for documentary editing.

Documentary editing leans on the cut. Fades and dips are granted only where the
beat structure deliberately asks for one, so the final edit never turns into
transition spam. Everything here is a pure function over the shot/beat plan:
the same script always produces the same transition decisions.
"""
from __future__ import annotations

from typing import Any

SUPPORTED_TRANSITIONS = ("cut", "fade", "dip")

# Beat kinds that read as chapters and warrant a deliberate dip to black.
CHAPTER_KINDS = {"hook", "thesis", "close", "implication", "section", "turn", "conclusion"}

# Kinds that soften their entrance with a short fade instead of a chapter dip.
SOFT_KINDS = {"context", "premise", "geography"}

# Modes that should always hit with a hard cut: punches and counters are beats
# of the sentence, not breathers.
HARD_MODES = {"punch", "count"}
# Modes that read as "settle" and may accept a fade after a punch.
HOLD_MODES = {"hold", "detail", "establish"}

# Frame budgets shared by planner, gate and renderer so they can never drift.
FADE_FRAMES = 10
DIP_FRAMES = 22


def transition_frames(transition: str, fps: int = 30) -> int:
    if transition == "fade":
        return max(1, int(round(FADE_FRAMES * max(1, fps) / 30)))
    if transition == "dip":
        return max(2, int(round(DIP_FRAMES * max(1, fps) / 30)))
    return 0


def beat_open(beat: Any, is_first: bool, previous: Any | None) -> str:
    """How the first shot of a beat enters, relative to the previous beat."""
    kind = str(getattr(beat, "kind", "") or "").lower()
    if is_first:
        return "fade"
    if kind in CHAPTER_KINDS:
        return "dip"
    if kind in SOFT_KINDS:
        return "fade"
    return "cut"


def shot_open(beat: Any, shots: list[dict[str, Any]], index: int) -> str:
    """How shot *index* enters, relative to the previous shot in the same beat.

    Cuts are the default. A fade is granted only when repeating the same visual
    (a visible jump cut would be worse) or when settling into a hold after a
    punch/count. Never more than one non-cut per beat.
    """
    if index <= 0 or index >= len(shots):
        return "cut"
    previous = shots[index - 1]
    shot = shots[index]
    previous_mode = str(previous.get("mode", "hold"))
    mode = str(shot.get("mode", "hold"))
    same_visual = previous.get("visual") == shot.get("visual")
    prev_is_hard = previous_mode in HARD_MODES
    settles = mode in HOLD_MODES and prev_is_hard
    noncut_used = sum(1 for s in shots[:index] if s.get("transition", "cut") != "cut")
    if noncut_used:
        return "cut"
    if same_visual or settles:
        return "fade"
    return "cut"


def assign_transitions(beats: list[Any], fps: int = 30) -> list[Any]:
    """Attach a `transition` and `transitionFrames` to every shot.

    The grammar is adjacency-driven: the entrance of the shot immediately before
    the current one is the only history that matters. Anti-spam means the same
    non-cut transition is never applied twice in a row (fade→fade or dip→dip);
    a fade settling into a chapter dip is deliberate variety, not spam. A hard
    cut always resets the chain.
    """
    previous_beat = None
    prev_transition = "cut"
    for b_index, beat in enumerate(beats):
        shots = list(getattr(beat, "shots", None) or [])
        if not shots:
            continue
        for index in range(len(shots)):
            if index == 0:
                wanted = beat_open(beat, b_index == 0, previous_beat)
            else:
                wanted = shot_open(beat, shots, index)
            if wanted != "cut" and prev_transition == wanted:
                wanted = "cut"  # no transition spam: identical non-cut entrances
            shots[index]["transition"] = wanted
            shots[index]["transitionFrames"] = transition_frames(wanted, fps)
            prev_transition = wanted
        beat.shots = shots
        previous_beat = beat
    return beats