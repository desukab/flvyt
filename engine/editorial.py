"""Sentence-level editorial grammar for automated documentary pacing.

The planner is deterministic: the same narration text, duration, visual and
beat kind always produce the same shot plan. It varies the structure by beat
kind, uses emphasis deliberately (punches and long holds), splits long
sentences along their natural clauses instead of pure arithmetic fractions,
and always preserves the exact narration duration.
"""
from __future__ import annotations
import re
import zlib
from typing import Any
from .edit_policy import decision

# Per-kind shot *purposes*. Purpose tokens are translated into actual shot modes
# through the beat's visual family so map/timeline/stat shots never misuse modes
# that belong to text cards.
DEFAULT_SLOTS: dict[str, list[tuple[str, int]]] = {
    "hook": [("punch", 3), ("hold", 1)],
    "claim": [("establish", 2), ("punch", 2), ("hold", 1)],
    "evidence": [("establish", 2), ("detail", 2), ("hold", 1)],
    "context": [("establish", 2), ("detail", 1), ("hold", 2)],
    "implication": [("establish", 1), ("punch", 2), ("hold", 1)],
    "thesis": [("establish", 1), ("hold", 3)],
    "close": [("hold", 1)],
    "section": [("establish", 1), ("hold", 1)],
}

# Emphasis increases weight on everything that asks to be loud: punches lead,
# holds hold longer, evidence detail turns into a beat before repeating text.
HIGH_SLOTS: dict[str, list[tuple[str, int]]] = {
    "hook": [("punch", 3), ("hold", 2)],
    "claim": [("punch", 3), ("establish", 1), ("hold", 2)],
    "evidence": [("detail", 2), ("punch", 2), ("hold", 2)],
    "context": [("establish", 2), ("detail", 2), ("hold", 2)],
    "implication": [("punch", 3), ("hold", 1)],
    "thesis": [("hold", 4)],
    "close": [("hold", 2)],
    "section": [("hold", 2)],
}

PURPOSE_TO_MODE: dict[str, dict[str, str]] = {
    "stat": {"establish": "count", "punch": "count", "hold": "hold", "detail": "detail"},
    "chart": {"establish": "count", "punch": "count", "hold": "hold", "detail": "detail"},
    "counter": {"establish": "count", "punch": "count", "hold": "hold", "detail": "detail"},
    "map": {"establish": "establish", "punch": "move", "hold": "hold", "detail": "move"},
    "timeline": {"establish": "establish", "punch": "move", "hold": "hold", "detail": "move"},
    "chapter": {"establish": "establish", "punch": "hold", "hold": "hold", "detail": "hold"},
    "default": {"establish": "establish", "punch": "punch", "hold": "hold", "detail": "detail"},
}

MIN_SHOT_SECONDS = 1.0


def _tokens(text: str) -> list[str]:
    return re.findall(r"\b[\w'-]+\b", text)


def _clauses(text: str) -> list[str]:
    """Split a narration sentence on clause boundaries, never inside numbers.

    A comma followed by a digit is treated as a thousands separator and kept
    inside the number ("$1,234,567"); every other comma, semicolon, colon or
    dash is a boundary.
    """
    parts = re.split(r",(?!\d)|[;:]|[—–]|।", text)
    return [p.strip() for p in parts if p.strip()]


def _fingerprint(text: str) -> int:
    return zlib.crc32(text.encode("utf-8"))


def _mode(visual: str, purpose: str) -> str:
    table = PURPOSE_TO_MODE.get(visual, PURPOSE_TO_MODE["default"])
    return table.get(purpose, "establish")


def _pattern(kind: str, emphasis: str, visual: str, seconds: float) -> list[dict[str, Any]]:
    slots = (HIGH_SLOTS if emphasis == "high" else DEFAULT_SLOTS).get(kind, DEFAULT_SLOTS["claim"])
    max_shots = max(1, int(seconds // MIN_SHOT_SECONDS))
    while len(slots) > max_shots and len(slots) > 2:
        candidates = [i for i in range(1, len(slots) - 1) if slots[i][0] != "punch"]
        if not candidates:
            candidates = list(range(1, len(slots) - 1))
        slots = slots[:candidates[0]] + slots[candidates[0] + 1:]
    return [
        {"purpose": purpose, "weight": weight, "visual": visual, "mode": _mode(visual, purpose)}
        for purpose, weight in slots
    ]


def _word_buckets(words: list[str], n: int) -> list[str]:
    """Split a single-thought sentence into n balanced, monotonic word chunks.

    Word boundaries round to the nearest bucket so every bucket is non-empty
    whenever there are at least as many words as buckets.
    """
    buckets: list[list[str]] = [[] for _ in range(n)]
    m = len(words)
    for i, word in enumerate(words):
        buckets[min(n - 1, int(i * n / m + 0.5))].append(word)
    return [" ".join(bucket) for bucket in buckets]


def _running_text(words: list[str], n: int) -> list[str]:
    """Progressive reveal: each shot continues the sentence, the last is whole.

    This is the deliberate "build it up, then hold the full line" shape for
    thesis/close kinds: never repeats a frame, and the final card carries the
    complete sentence the way a strong closer should. A sentence too short to
    progress is held whole on every card instead.
    """
    m = len(words)
    if m < n:
        return [" ".join(words)] * n
    return [" ".join(words[:int(round(m * (i + 1) / n))]) for i in range(n)]


def _distribute_text(text: str, n: int, echo: bool = False) -> list[str]:
    """Assign sentence fragments to shots by relative character weight.

    `echo` kinds (thesis/close) *build toward* the whole sentence so the final
    shot holds the full line. Everywhere else text is partitioned along its
    natural clauses — a single-thought claim is progressed word by word — so a
    short shot never asks the viewer to read the same sentence twice and no
    shot is ever left without text.
    """
    if n <= 1:
        return [text]
    if echo:
        return _running_text(text.split(), n)
    clauses = _clauses(text)
    if len(clauses) < n:
        if len(text.split()) < n:
            return [text] * n
        return _word_buckets(text.split(), n)
    total = sum(len(c) for c in clauses)
    target = total / n
    groups: list[list[str]] = [[] for _ in range(n)]
    index = 0
    used = 0.0
    for i, clause in enumerate(clauses):
        # Later groups must each keep at least one clause: advance before taking
        # the one clause that would starve the remaining groups.
        while index < n - 1 and (len(clauses) - i) <= (n - index - 1) and used > 0:
            index += 1
            used = 0.0
        groups[index].append(clause)
        used += len(clause)
        if index < n - 1 and used >= target:
            index += 1
            used = 0.0
    return [" ".join(group) for group in groups]


def _seconds_for(weights: list[int], total: float) -> list[float]:
    """Split a beat duration across shots by editorial weight, min duration kept."""
    n = len(weights)
    mins = [MIN_SHOT_SECONDS] * n
    budget = total - sum(mins)
    if budget < 0:
        raise ValueError(f"duration {total:.2f}s too short for {n} shots")
    wsum = float(sum(weights))
    seconds = [mins[i] + budget * weights[i] / wsum for i in range(n)]
    for i in range(n - 1):
        seconds[i] = round(seconds[i], 3)
    seconds[-1] = round(total - sum(seconds[:-1]), 3)
    return seconds


def make_shots(text: str, seconds: float, visual: str, emphasis: str = "normal",
               kind: str = "claim") -> list[dict[str, Any]]:
    """Turn one narration beat into a deterministic, kind-aware shot plan."""
    duration = max(0.8, float(seconds))
    words = len(_tokens(text))
    policy = decision(kind, emphasis)
    if duration < 3.0 or words < 8:
        single_mode = "hold" if kind in {"thesis", "close"} else (
            "punch" if emphasis == "high" else "establish")
        return [{
            "id": "s1", "seconds": round(duration, 3), "visual": visual,
            "text": text, "mode": single_mode, "mode_max": policy.mode,
        }]

    pattern = _pattern(kind, emphasis, visual, duration)
    n = len(pattern)
    # Single-thought beats keep a short two-shot shape instead of a repetitive
    # three-shot echo of the same sentence: open then hold, or punch then hold.
    # Deliberate holds (thesis/close) and two-slot hooks keep their pattern.
    if len(_clauses(text)) == 1 and kind not in {"thesis", "close", "hook"} and n > 2:
        punches = [i for i, slot in enumerate(pattern) if slot["purpose"] == "punch"]
        if punches and punches[-1] < n - 1:
            pattern = [pattern[punches[-1]], pattern[-1]]
        else:
            pattern = [pattern[0], pattern[-1]]
        n = 2

    echo = kind in {"thesis", "close"}
    texts = _distribute_text(text, n, echo=echo)
    # Seconds follow the text, not the slot archetype: a shot that carried a
    # long clause gets proportionally more screen time, a punch with a short
    # phrase stays punchy. This keeps every shot within the readability budget
    # without inventing time.
    weights = [max(1, len(t)) for t in texts]
    seconds_list = _seconds_for(weights, duration)
    return [{
        "id": f"s{i + 1}",
        "seconds": seconds_list[i],
        "visual": pattern[i]["visual"],
        "text": texts[i],
        "mode": pattern[i]["mode"],
        "mode_max": policy.mode,
    } for i in range(n)]


def add_shots(beats: list[Any]) -> list[Any]:
    for beat in beats:
        beat.shots = make_shots(beat.text, beat.seconds, beat.visual, beat.emphasis, beat.kind)
    return beats