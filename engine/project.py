from __future__ import annotations

from dataclasses import dataclass, asdict, field
from pathlib import Path
import json
from typing import Any

INTRO_SECONDS = 5.0


@dataclass
class Beat:
    id: str
    kind: str
    text: str
    seconds: float = 3.0
    visual: str = "title"
    emphasis: str = "normal"
    assetSrc: str | None = None
    assetConfidence: float | None = None
    assetReason: str | None = None
    label: str | None = None
    value: float | None = None
    unit: str | None = None
    narration: str | None = None
    sources: list[str] = field(default_factory=list)
    shots: list[dict[str, Any]] = field(default_factory=list)
    pad_after: float = 0.0
    chapter: int | None = None
    intent: str | None = None
    motif: str | None = None
    tags: list[str] | None = None


@dataclass
class Project:
    title: str
    subtitle: str
    fps: int = 30
    width: int = 1920
    height: int = 1080
    beats: list[Beat] | None = None
    timed_by_audio: bool = False

    @classmethod
    def load(cls, path: str | Path) -> "Project":
        data: dict[str, Any] = json.loads(Path(path).read_text(encoding="utf-8"))
        allowed = set(Beat.__dataclass_fields__)
        beats = [Beat(**{k: v for k, v in b.items() if k in allowed}) for b in data.get("beats", [])]
        return cls(
            title=data["title"], subtitle=data.get("subtitle", ""),
            fps=int(data.get("fps", 30)), width=int(data.get("width", 1920)),
            height=int(data.get("height", 1080)), beats=beats,
            timed_by_audio=bool(data.get("timed_by_audio", False)),
        )

    def props(self) -> dict[str, Any]:
        return asdict(self)

    def duration_frames(self) -> int:
        beats = self.beats or []
        seconds = INTRO_SECONDS + sum(max(0.5, b.seconds) for b in beats)
        return int(round(max(1.0, seconds) * self.fps))

    def save_props(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.props(), indent=2), encoding="utf-8")
