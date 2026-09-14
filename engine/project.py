from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import json
from typing import Any

@dataclass
class Beat:
    id: str
    kind: str
    text: str
    seconds: float = 3.0
    visual: str = "title"
    emphasis: str = "normal"

@dataclass
class Project:
    title: str
    subtitle: str
    fps: int = 30
    width: int = 1920
    height: int = 1080
    beats: list[Beat] | None = None

    @classmethod
    def load(cls, path: str | Path) -> "Project":
        data: dict[str, Any] = json.loads(Path(path).read_text(encoding="utf-8"))
        beats = [Beat(**b) for b in data.get("beats", [])]
        return cls(
            title=data["title"], subtitle=data.get("subtitle", ""),
            fps=int(data.get("fps", 30)), width=int(data.get("width", 1920)),
            height=int(data.get("height", 1080)), beats=beats,
        )

    def props(self) -> dict[str, Any]:
        return asdict(self)

    def duration_frames(self) -> int:
        beats = self.beats or []
        seconds = max(30.0, sum(max(0.5, b.seconds) for b in beats))
        return int(round(seconds * self.fps))

    def save_props(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.props(), indent=2), encoding="utf-8")
