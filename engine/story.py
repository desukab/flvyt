"""Turn a structured evidence pack into a documentary beat plan.

This is deliberately deterministic. A local LLM can later replace the text-generation
layer without changing the project, visual, asset or rendering contracts.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


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
        "seconds": 4.0, "visual": "claim", "emphasis": "high", "label": "THE QUESTION",
    }]
    if rows:
        beats.append({
            "id": "context", "kind": "context",
            "text": "The answer sits inside a chain of specialized decisions and infrastructure.",
            "seconds": 4.0, "visual": "broll", "emphasis": "normal", "label": "THE SYSTEM",
        })
    for i, ev in enumerate(rows):
        visual = _visual_for_evidence(ev)
        beats.append({
            "id": f"e{i+1:02d}", "kind": "evidence", "text": ev.claim,
            "seconds": 4.0 if ev.importance == "high" else 3.4,
            "visual": visual, "emphasis": "high" if ev.importance == "high" else "normal",
            "label": ev.source_type.upper(), "sources": [ev.source],
        })
    beats.extend([
        {
            "id": "implication", "kind": "implication",
            "text": "The important detail is not any single company or machine; it is the dependency between them.",
            "seconds": 4.2, "visual": "map", "emphasis": "normal", "label": "THE CONNECTION",
        },
        {
            "id": "thesis", "kind": "thesis", "text": pack.thesis or pack.title,
            "seconds": 4.4, "visual": "quote", "emphasis": "high", "label": "THE THESIS",
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
