"""Production manifest: every output records its full provenance.

A manifest answers "what produced this video, from which inputs, with what
versions, and did it pass QA?" deterministically. The seed is the SHA-256 of the
canonical input project bytes, so re-running the exact same input with the same
engine yields the same seed and the same edit.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from .editorial_quality import ENGINE_VERSION


def software_versions() -> dict[str, str]:
    """Best-effort version strings for every local tool carrying one."""
    def _version(argv: list[str], label: str) -> str:
        try:
            result = subprocess.run(argv, capture_output=True, text=True, timeout=20)
            line = (result.stdout or result.stderr or "").strip().splitlines()
            return (line[0] if line else "")[:120] or "unknown"
        except Exception:
            return "unknown"

    return {
        "python": _version(["python", "--version"], "python"),
        "node": _version(["node", "--version"], "node"),
        "ffmpeg": _version(["ffmpeg", "-version"], "ffmpeg"),
        "ffprobe": _version(["ffprobe", "-version"], "ffprobe"),
        "engine": ENGINE_VERSION,
    }


def fingerprint(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def file_seed(path: str | Path) -> str:
    return fingerprint(Path(path).read_bytes())


def _registry_assets(project_path: str | Path, root: Path) -> list[dict[str, Any]]:
    """List every asset referenced by the project, with its recorded license."""
    try:
        from .assets import AssetRegistry
        data = json.loads(Path(project_path).read_text(encoding="utf-8"))
        srcs = sorted({str(b.get("assetSrc", "")) for b in data.get("beats", []) if b.get("assetSrc")})
        registry = AssetRegistry.load(root / "assets/registry.json") \
            if (root / "assets/registry.json").exists() else None
    except Exception:
        return []
    rows = []
    if registry:
        by_id = {a.id: a for a in registry.assets}
    else:
        by_id = {}
    for src in srcs:
        key = src.replace("public/assets/", "") or src
        rows.append({
            "path": src,
            **({"license": by_id[key].license,
                "attribution": by_id[key].attribution,
                "source": by_id[key].source,
                "tags": list(by_id[key].tags)} if key in by_id else {"license": "unknown"}),
        })
    return rows


def write_manifest(project_path: str | Path, out_path: str | Path,
                   delivery_qa: dict[str, Any], editorial_qa: dict[str, Any],
                   root: str | Path | None = None,
                   narration: dict[str, Any] | None = None,
                   captions: dict[str, Any] | None = None,
                   assets: dict[str, Any] | None = None,
                   frameqa: dict[str, Any] | None = None,
                   render: dict[str, Any] | None = None) -> Path:
    """Assemble and write out/manifest.json for a completed build."""
    root = Path(root) if root else Path(__file__).resolve().parents[1]
    project = json.loads(Path(project_path).read_text(encoding="utf-8"))
    manifest = {
        "title": project.get("title", ""),
        "project": str(project_path),
        "source_evidence": assets.get("evidence") if assets else None,
        "seed": file_seed(project_path),
        "engine": ENGINE_VERSION,
        "software": software_versions(),
        "render_settings": render or {
            "fps": project.get("fps"),
            "width": project.get("width"),
            "height": project.get("height"),
        },
        "assets": _registry_assets(project_path, root),
        "narration": narration or {},
        "captions": captions or {},
        "qa": {
            "delivery": delivery_qa,
            "editorial": editorial_qa,
            "frame": frameqa or {},
        },
    }
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return path