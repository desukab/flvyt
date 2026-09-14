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


@dataclass
class StoryPack:
    title: str
    thesis: str
    evidence: list[Evidence]

    @classmethod
    def load(cls, path: str | Path) -> "StoryPack":
        data: dict[str, Any] = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            title=data["title"],
            thesis=data.get("thesis", ""),
            evidence=[Evidence(**row) for row in data.get("evidence", [])],
        )


def build_beats(pack: StoryPack) -> list[dict[str, Any]]:
    """Create a restrained hook → context → evidence → implication → thesis arc."""
    rows = sorted(pack.evidence, key=lambda x: (x.importance != "high", x.id))
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
        visual = "quote" if ev.source_type == "interview" else ("map" if "geography" in (ev.tags or []) else "claim")
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
