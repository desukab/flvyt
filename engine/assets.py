"""Deterministic asset registry for documentary B-roll and graphics.

The registry deliberately never downloads arbitrary copyrighted media. Every asset
must carry an ownership/license record before it can be selected for a render.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

ALLOWED_LICENSES = {
    "owned", "public-domain", "cc0", "cc-by", "cc-by-sa", "licensed"
}


@dataclass(frozen=True)
class Asset:
    id: str
    path: str
    kind: str
    tags: tuple[str, ...] = ()
    license: str = "owned"
    attribution: str = ""
    source: str = ""
    duration: float = 0.0

    def valid(self) -> bool:
        return self.license.lower() in ALLOWED_LICENSES and bool(self.path)


class AssetRegistry:
    def __init__(self, assets: Iterable[Asset] = ()) -> None:
        self.assets = list(assets)

    @classmethod
    def load(cls, path: str | Path) -> "AssetRegistry":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        assets = []
        for row in data.get("assets", []):
            assets.append(Asset(
                id=str(row["id"]), path=str(row["path"]), kind=str(row.get("kind", "image")),
                tags=tuple(str(x).lower() for x in row.get("tags", [])),
                license=str(row.get("license", "owned")), attribution=str(row.get("attribution", "")),
                source=str(row.get("source", "")), duration=float(row.get("duration", 0)),
            ))
        return cls(assets)

    def validate(self, root: str | Path | None = None) -> list[str]:
        root = Path(root or ".")
        errors: list[str] = []
        for a in self.assets:
            if not a.valid():
                errors.append(f"{a.id}: unsupported/missing license")
                continue
            path = Path(a.path)
            if not path.is_absolute():
                path = root / path
            if not path.exists():
                errors.append(f"{a.id}: missing file {path}")
        return errors

    def match(self, query: str, kind: str | None = None) -> list[Asset]:
        tokens = {t.lower() for t in query.replace(",", " ").split() if t}
        scored: list[tuple[int, Asset]] = []
        for asset in self.assets:
            if not asset.valid() or (kind and asset.kind != kind):
                continue
            score = len(tokens & set(asset.tags))
            if asset.kind == kind:
                score += 1
            if score:
                scored.append((score, asset))
        scored.sort(key=lambda item: (-item[0], item[1].id))
        return [asset for _, asset in scored]

    def manifest(self) -> dict:
        return {"assets": [asdict(a) for a in self.assets]}
