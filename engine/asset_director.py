"""Match documentary beats to user-supplied, license-cleared assets."""
from __future__ import annotations

from pathlib import Path
from .assets import AssetRegistry
from .project import Project


def assign_assets(project: Project, registry_path: str | Path, root: str | Path) -> Project:
    registry = AssetRegistry.load(registry_path)
    errors = registry.validate(root)
    if errors:
        raise RuntimeError("Asset registry validation failed:\n- " + "\n- ".join(errors))

    for beat in project.beats or []:
        if beat.assetSrc or beat.visual not in {"broll", "image", "portrait", "logo"}:
            continue
        kind = "image"
        if beat.visual == "portrait":
            kind = "portrait"
        elif beat.visual == "logo":
            kind = "logo"
        matches = registry.match(beat.text, kind=kind)
        if not matches:
            matches = registry.match(beat.text)
        if matches:
            beat.assetSrc = matches[0].path
    return project
