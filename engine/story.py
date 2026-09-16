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
    chapter: int | None = None
    chapter_title: str | None = None


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
# a long factual stretch from stalling into one monotonous visual.
#
# A plain "claim" intentionally has NO alternates: the moment another visual is
# not supported by the sentence's own signals, rotating to a procedural backdrop
# would just be decoration duplicating the narration. A claim stays a claim, and
# the monotony is broken by its *content-anchored motif* (orbit for satellites,
# wave for timing signals, grid for ground networks, ...) and by per-shot layout
# sub-variants — visual reasons that all come from the sentence itself.
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


# Deterministic visual motivations. A motif is a *semantic anchor*: it is chosen
# from the sentence's own domain vocabulary, so a claim about satellites renders
# orbit rings and a claim about clock errors renders a signal wave. It is an
# honest visual metaphor for what the narration is about — never fabricated data.
# Order matters: the first pattern that matches wins, so the same sentence always
# yields the same motif.
MOTIF_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("orbit", ("satellite", "orbit", "constellation", "spacecraft", "launch", "space",
               "medium earth orbit", "space force", "replacement", "spare", "degrade",
               "active unit", "geostationary", "aurora", "rocket")),
    ("wave", ("signal", "frequency", "clock", "nanosecond", "microsecond", "radio",
              "timing", "broadcast", "transmit", "interference", "bandwidth",
              "l-band", "carrier wave", "atomic", "rubidium", "cesium",
              "positioning", "navigation", "receiver", "device", "phase",
              "watt", "jamming", "clock error", "synchron")),
    ("grid", ("network", "station", "antenna", "ground", "control", "monitor",
              "uplink", "link", "substation", "grid", "infrastructure",
              "power", "utility", "electric", "base station", "cable")),
    ("routes", ("route", "airline", "vessel", "shipping", "harbor", "strait", "port",
                "traffic", "carrier", "cable", "field", "airport", "aviation",
                "flight", "lane", "navigation aids", "vessel traffic")),
    ("chip", ("semiconductor", "chip", "wafer", "fab", "transistor",
              "manufacturing process", "processor", "nanometer",
              "lithography", "foundry", "die")),
    ("accounts", ("dollar", "billion", "million", "trillion", "revenue", "market",
                  "cost", "price", "investment", "economy", "procurement",
                  "adoption", "usage", "end user", "receiver count", "economic")),
]
# Neutral fallback for sentences with no recognisable domain; combined with the
# chapter's ambient field and the shot's layout sub-variant it still has a visible
# reason to exist without inventing a domain anchor.
DEFAULT_MOTIF = "cosmos"


def _motif_for(sentence: str) -> str:
    """Deterministic domain motif derived from the sentence's own vocabulary."""
    low = (sentence or "").lower()
    for name, words in MOTIF_PATTERNS:
        if any(w in low for w in words):
            return name
    return DEFAULT_MOTIF


def _alternates_for(ev: Evidence) -> list[str]:
    """Alternates a beat may use without misrepresenting its content."""
    tags = {tag.lower() for tag in (ev.tags or [])}
    out: list[str] = []
    for visual in ALTERNATES.get(_visual_for_evidence(ev), []):
        if visual == "claim":
            out.append(visual)
        elif visual == "broll":
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
    """Create a chapter-structured arc: hook → section/evidence chapters → close.

    Fabricated filler sentences ("The answer sits inside a chain…" or
    "The important detail is not any single company…") are gone; every beat
    is drawn from real evidence or the thesis. Each chapter gets a section card,
    and every beat carries a content-anchored motif that gives it a meaningful
    visual reason to exist.
    """
    rows = sorted(
        pack.evidence,
        key=lambda x: (
            x.slot if x.slot is not None else 10**9,
            x.importance != "high",
            x.id,
        ),
    )
    thesis = pack.thesis or pack.title
    beats: list[dict[str, Any]] = [{
        "id": "hook", "kind": "hook", "text": thesis,
        "seconds": round(max(4.0, read_need(thesis)), 2),
        "visual": "claim", "emphasis": "high", "label": "THE QUESTION",
        "chapter": 0, "motif": _motif_for(thesis), "intent": "question",
    }]
    previous_visual: str | None = None
    previous_chapter: int | None = None
    for i, ev in enumerate(rows):
        chapter = ev.chapter if ev.chapter is not None else 1
        if chapter != previous_chapter:
            title = ev.chapter_title or f"Part {chapter}"
            beats.append({
                "id": f"sec{chapter:02d}", "kind": "section", "text": title,
                "seconds": round(max(3.0, read_need(title)), 2),
                "visual": "chapter", "emphasis": "normal",
                "label": f"PART {chapter}", "sources": [],
                "chapter": chapter, "motif": "chapter", "intent": "structure",
            })
            previous_chapter = chapter
        visual = _pick_visual(ev, previous_visual)
        base = 4.0 if ev.importance == "high" else 3.4
        beats.append({
            "id": f"e{i+1:02d}", "kind": "evidence", "text": ev.claim,
            "seconds": round(max(base, read_need(ev.claim)), 2),
            "visual": visual,
            "emphasis": "high" if ev.importance == "high" else "normal",
            "label": ev.source_type.upper(), "sources": [ev.source],
            "chapter": chapter, "motif": _motif_for(ev.claim),
            "intent": "punch" if ev.importance == "high" else "detail",
            "tags": list(ev.tags or []),
        })
        previous_visual = visual
    beats.append({
        "id": "thesis", "kind": "thesis", "text": thesis,
        "seconds": round(max(4.4, read_need(thesis)), 2),
        "visual": "quote", "emphasis": "high", "label": "THE THESIS",
        "chapter": previous_chapter or 0, "motif": _motif_for(thesis),
        "intent": "resolve",
    })
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
