"""Turn a structured evidence pack into a documentary beat plan.

This is deliberately deterministic. A local LLM can later replace the text-generation
layer without changing the project, visual, asset or rendering contracts.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


# A beat's narration must remain readable on screen: if the planned duration is
# too short for the sentence, no shot-splitting can rescue it, so the editor
# lengthens the beat to a comfortable reading rate before it is stored.
READABLE_CHARS_PER_SECOND = 16
PACING_MAX_SECONDS = 13.0


def read_need(text: str) -> float:
    """Minimum duration a beat needs for its sentence to be read comfortably."""
    return min(PACING_MAX_SECONDS, float(len(text)) / READABLE_CHARS_PER_SECOND)


@dataclass
class Evidence:
    id: str
    claim: str
    source: str
    source_type: str = "article"
    importance: str = "normal"
    tags: list[str] | None = None
    slot: int | None = None


@dataclass
class StoryPack:
    title: str
    thesis: str
    evidence: list[Evidence]

    @classmethod
    def load(cls, path: str | Path) -> "StoryPack":
        data: dict[str, Any] = json.loads(Path(path).read_text(encoding="utf-8"))
        allowed = set(Evidence.__dataclass_fields__)
        return cls(
            title=data["title"],
            thesis=data.get("thesis", ""),
            evidence=[Evidence(**{k: v for k, v in row.items() if k in allowed})
                      for row in data.get("evidence", [])],
        )


def _visual_for_evidence(ev: Evidence) -> str:
    """Choose a visual from explicit editorial metadata, never from incidental digits.

    A claim containing a year, percentage, model number, or dollar amount is still a
    claim unless the evidence pack explicitly marks it as a stat. This prevents the
    director from turning ordinary factual sentences into misleading counter cards.
    """
    tags = {tag.lower() for tag in (ev.tags or [])}
    if ev.source_type == "interview":
        return "quote"
    if "geography" in tags or "map" in tags:
        return "map"
    if "timeline" in tags:
        return "timeline"
    if "chart" in tags:
        return "chart"
    if "stat" in tags:
        return "stat"
    if "portrait" in tags or "person" in tags:
        return "portrait"
    if "company" in tags or "logo" in tags:
        return "logo"
    return "claim"


# Content-supported alternates per visual family: switching a geography beat to a
# timeline card (for example) is still faithful to the source material and keeps
# a long factual stretch from stalling into one monotonous visual. "claim" is the
# universal neutral card — a plain title/text never misrepresents a claim.
ALTERNATES = {
    "map": ["timeline", "chart", "stat", "claim"],
    "timeline": ["chart", "stat", "map", "claim"],
    "chart": ["stat", "timeline", "map", "claim"],
    "stat": ["chart", "timeline", "map", "claim"],
    "logo": ["claim", "stat", "chart"],
    "portrait": ["claim", "quote"],
    "quote": ["claim"],
    "claim": [],
}


def _alternates_for(ev: Evidence) -> list[str]:
    """Alternates a beat may use without misrepresenting its content."""
    tags = {tag.lower() for tag in (ev.tags or [])}
    out: list[str] = []
    for visual in ALTERNATES.get(_visual_for_evidence(ev), []):
        if visual == "claim":
            out.append(visual)
        elif visual in {"stat", "chart"} and ("stat" in tags or "chart" in tags):
            out.append(visual)
        elif visual == "map" and ("map" in tags or "geography" in tags):
            out.append(visual)
        elif visual == "timeline" and "timeline" in tags:
            out.append(visual)
        elif visual == "quote" and ev.source_type == "interview":
            out.append(visual)
        elif visual == "portrait" and ("portrait" in tags or "person" in tags):
            out.append(visual)
    return out


def _pick_visual(ev: Evidence, previous: str | None) -> str:
    """Choose this beat's visual, rotating through content-supported alternates.

    The primary visual always wins on the first occurrence; a run of identical
    visuals is broken the moment another faithful visual is available so a long
    evidence stretch never turns into one unchanging background.
    """
    primary = _visual_for_evidence(ev)
    if previous is None or primary != previous:
        return primary
    alternates = _alternates_for(ev)
    for visual in alternates:
        if visual != previous:
            return visual
    return primary


def build_beats(pack: StoryPack) -> list[dict[str, Any]]:
    """Create a restrained hook → context → evidence → implication → thesis arc.

    Evidence follows the optional explicit `slot` order when provided, so a
    long documentary can follow chapters instead of importance sorting.
    """
    rows = sorted(
        pack.evidence,
        key=lambda x: (
            x.slot if x.slot is not None else 10**9,
            x.importance != "high",
            x.id,
        ),
    )
    beats: list[dict[str, Any]] = [{
        "id": "hook", "kind": "hook", "text": pack.thesis or pack.title,
        "seconds": round(max(4.0, read_need(pack.thesis or pack.title)), 2),
        "visual": "claim", "emphasis": "high", "label": "THE QUESTION",
    }]
    if rows:
        context = "The answer sits inside a chain of specialized decisions and infrastructure."
        beats.append({
            "id": "context", "kind": "context", "text": context,
            "seconds": round(max(4.0, read_need(context)), 2),
            "visual": "broll", "emphasis": "normal", "label": "THE SYSTEM",
        })
    previous_visual: str | None = None
    for i, ev in enumerate(rows):
        visual = _pick_visual(ev, previous_visual)
        base = 4.0 if ev.importance == "high" else 3.4
        beats.append({
            "id": f"e{i+1:02d}", "kind": "evidence", "text": ev.claim,
            "seconds": round(max(base, read_need(ev.claim)), 2),
            "visual": visual, "emphasis": "high" if ev.importance == "high" else "normal",
            "label": ev.source_type.upper(), "sources": [ev.source],
        })
        previous_visual = visual
    implication = "The important detail is not any single company or machine; it is the dependency between them."
    beats.extend([
        {
            "id": "implication", "kind": "implication", "text": implication,
            "seconds": round(max(4.2, read_need(implication)), 2),
            "visual": "map", "emphasis": "normal", "label": "THE CONNECTION",
        },
        {
            "id": "thesis", "kind": "thesis", "text": pack.thesis or pack.title,
            "seconds": round(max(4.4, read_need(pack.thesis or pack.title)), 2),
            "visual": "quote", "emphasis": "high", "label": "THE THESIS",
        },
    ])
    return beats


def save_project(pack: StoryPack, output: str | Path) -> Path:
    project = {
        "title": pack.title,
        "subtitle": pack.thesis,
        "fps": 30,
        "width": 1920,
        "height": 1080,
        "beats": build_beats(pack),
    }
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(project, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
