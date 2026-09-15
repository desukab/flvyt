"""Match documentary beats to user-supplied, license-cleared assets.

The director scores assets semantically against the beat text, respects the
beat's visual kind (image/portrait/logo), avoids repeating the same asset while
a fresh alternative exists, and records a confidence score so downstream tools
can decide whether a procedural fallback is the honest choice. Assets are never
auto-downloaded or assumed reusable: only registry entries with explicit
licensing can ever be selected.
"""
from __future__ import annotations

import re
from pathlib import Path

from .assets import AssetRegistry
from .project import Project

# Visual kinds that open themselves to external media.
ASSET_VISUALS = {"broll", "image", "portrait", "logo"}
KIND_FOR_VISUAL = {"broll": "image", "image": "image", "portrait": "portrait", "logo": "logo"}

KIND_BONUS = 1.0
EXACT_BONUS = 2.0
SUBSTRING_BONUS = 1.5
PREFIX_BONUS = 1.0
USED_PENALTY = 0.35

STOPWORDS = {
    "the", "and", "for", "are", "was", "were", "with", "that", "this", "these",
    "those", "have", "has", "had", "from", "its", "into", "over", "under",
    "being", "been", "their", "there", "where", "when", "what", "which",
    "while", "about", "after", "before", "because", "between", "through",
    "during", "such", "each", "both", "also", "than", "then", "them", "they",
    "your", "our", "only", "even", "still", "much", "many", "more", "most",
    "but", "can", "could", "would", "should", "may", "might", "does", "did",
    "not", "will", "one", "two", "into", "onto", "within", "other", "another",
    "some", "any", "all", "or", "so", "an", "of", "to", "in", "on", "at", "by",
    "as", "is", "it", "he", "she", "we", "they",
}


def tokenize(query: str) -> list[str]:
    """Lower-cased keyword tokens; numbers stay whole ('2024', '5nm')."""
    words = re.findall(r"[a-z0-9]+(?:[.\-+][a-z0-9]+)*", query.lower())
    return [w for w in words if len(w) >= 3 and w not in STOPWORDS]


def _tag_score(token: str, tag: str) -> float:
    if token == tag:
        return EXACT_BONUS
    if len(token) >= 4 and len(tag) >= 4 and (token in tag or tag in token):
        return SUBSTRING_BONUS
    if tag.startswith(token) or token.startswith(tag):
        return PREFIX_BONUS
    return 0.0


def score_assets(query: str, assets: list, kind: str | None = None,
                 used: set[str] | None = None) -> list[tuple[float, float, object]]:
    """Return (score, confidence, asset) ranked for photographers' taste.

    Score rewards exact tag hits and subtracts for already-used assets so the
    editor does not reach for the same file twice when something fresher still
    matches. Confidence is score over the best possible score, clamped to [0,1].
    """
    tokens = tokenize(query)
    used = used or set()
    ranked: list[tuple[float, float, object]] = []
    for asset in assets:
        if not asset.valid():
            continue
        if kind and asset.kind != kind:
            continue
        if not tokens:
            continue
        best = sum(max(_tag_score(t, tag) for tag in asset.tags) for t in tokens)
        if best <= 0:
            continue  # not even a weak match; the editor should not fake it
        score = best + (KIND_BONUS if asset.kind == kind else 0.0)
        if asset.id in used:
            score *= USED_PENALTY
        max_possible = EXACT_BONUS * len(tokens) + KIND_BONUS
        confidence = min(1.0, score / max(max_possible, 1e-9))
        ranked.append((score, confidence, asset))
    ranked.sort(key=lambda row: (-row[0], -row[1], getattr(row[2], "id", "")))
    return ranked


def assign_assets(project: Project, registry_path: str | Path, root: str | Path) -> Project:
    registry = AssetRegistry.load(registry_path)
    errors = registry.validate(root)
    if errors:
        raise RuntimeError("Asset registry validation failed:\n- " + "\n- ".join(errors))

    used: set[str] = set()
    for beat in project.beats or []:
        if beat.assetSrc or beat.visual not in ASSET_VISUALS:
            continue
        kind = KIND_FOR_VISUAL.get(beat.visual, "image")
        matches = score_assets(beat.text, registry.assets, kind=kind, used=used)
        if not matches:
            matches = score_assets(beat.text, registry.assets, used=used)
        if matches:
            score, confidence, asset = matches[0]
            beat.assetSrc = asset.path
            beat.assetConfidence = round(confidence, 3)
            beat.assetReason = "matched"
            used.add(asset.id)
        else:
            # Graceful procedural fallback: the renderer keeps its documentary
            # gradient/diagram panel instead of faking a real asset. No licensing
            # risk, no fabricated visual provenance.
            beat.assetSrc = None
            beat.assetConfidence = 0.0
            beat.assetReason = "procedural-fallback"
    return project