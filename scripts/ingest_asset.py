#!/usr/bin/env python3
"""Ingest an owned/licensed local asset into public/assets and update the registry."""
from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_LICENSES = {"owned", "public-domain", "cc0", "cc-by", "cc-by-sa", "licensed"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
VIDEO_EXTS = {".mp4", ".mov", ".webm", ".mkv"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest a license-cleared local media asset")
    parser.add_argument("source")
    parser.add_argument("--id", required=True)
    parser.add_argument("--kind", choices=["image", "video", "portrait", "logo"], default="image")
    parser.add_argument("--license", required=True, choices=sorted(ALLOWED_LICENSES))
    parser.add_argument("--tags", default="", help="Comma-separated search tags")
    parser.add_argument("--attribution", default="")
    parser.add_argument("--source-url", default="")
    parser.add_argument("--registry", default="assets/registry.json")
    args = parser.parse_args()

    source = Path(args.source).expanduser().resolve()
    if not source.is_file():
        raise SystemExit(f"Asset not found: {source}")
    if source.suffix.lower() not in IMAGE_EXTS | VIDEO_EXTS:
        raise SystemExit(f"Unsupported media extension: {source.suffix}")

    asset_id = args.id.strip()
    if not asset_id or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in asset_id):
        raise SystemExit("Asset id may contain only letters, numbers, '-' and '_'")

    digest = sha256(source)
    target_dir = ROOT / "public/assets"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{asset_id}{source.suffix.lower()}"
    shutil.copy2(source, target)

    registry_path = ROOT / args.registry if not Path(args.registry).is_absolute() else Path(args.registry)
    if registry_path.exists():
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    else:
        registry = {"assets": []}
    assets = registry.setdefault("assets", [])
    if any(item.get("id") == asset_id for item in assets):
        raise SystemExit(f"Asset id already exists in registry: {asset_id}")

    rel = target.relative_to(ROOT).as_posix()
    assets.append({
        "id": asset_id,
        "path": rel,
        "kind": args.kind,
        "tags": sorted({tag.strip().lower() for tag in args.tags.split(",") if tag.strip()}),
        "license": args.license,
        "attribution": args.attribution,
        "source": args.source_url,
        "sha256": digest,
        "mime": mimetypes.guess_type(target.name)[0] or "application/octet-stream",
        "duration": 0,
    })
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(registry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"id": asset_id, "path": rel, "sha256": digest, "registry": str(registry_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
