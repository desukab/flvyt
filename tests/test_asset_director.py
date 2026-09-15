"""Tests for the semantic, confidence-aware asset director."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from engine.asset_director import assign_assets, score_assets, tokenize
from engine.assets import Asset, AssetRegistry
from engine.project import Beat, Project


def make_asset(asset_id: str, kind: str, tags, license: str = "owned") -> Asset:
    return Asset(id=asset_id, path=f"public/assets/{asset_id}.jpg", kind=kind,
                 tags=tuple(tags), license=license)


class TokenTests(unittest.TestCase):
    def test_numbers_stay_whole(self):
        self.assertIn("5nm", tokenize("advanced 5nm chips"))

    def test_short_words_dropped(self):
        self.assertNotIn("in", tokenize("in a factory"))


class ScoringTests(unittest.TestCase):
    def test_exact_tag_outranks_weak(self):
        assets = [
            make_asset("exact", "image", ["semiconductor", "factory"]),
            make_asset("weak", "image", ["nature", "field"]),
        ]
        ranked = score_assets("semiconductor factory", assets)
        self.assertEqual(ranked[0][2].id, "exact")

    def test_kind_match_is_respected(self):
        assets = [
            make_asset("img", "image", ["chip"]),
            make_asset("port", "portrait", ["chip"]),
        ]
        ranked = score_assets("chip manufacturing", assets, kind="portrait")
        self.assertEqual(ranked[0][2].id, "port")

    def test_used_asset_is_penalized(self):
        a1 = make_asset("used", "image", ["chip", "factory"])
        a2 = make_asset("fresh", "image", ["chip"])
        ranked = score_assets("chip factory", [a1, a2], used={"used"})
        self.assertEqual(ranked[0][2].id, "fresh")

    def test_confidence_bounds(self):
        ranked = score_assets("chip", [make_asset("a", "image", ["chip"])])
        self.assertGreaterEqual(ranked[0][1], 0.0)
        self.assertLessEqual(ranked[0][1], 1.0)

    def test_invalid_license_never_score(self):
        bad = make_asset("bad", "image", ["chip"], license="unknown")
        ranked = score_assets("chip", [bad])
        self.assertEqual(ranked, [])

    def test_deterministic_tie_break(self):
        a1 = make_asset("a", "image", ["chip"])
        a2 = make_asset("b", "image", ["chip"])
        first = [r[2].id for r in score_assets("chip", [a1, a2])]
        second = [r[2].id for r in score_assets("chip", [a1, a2])]
        self.assertEqual(first, second)


class AssignTests(unittest.TestCase):
    def _registry(self, root: Path, assets):
        rows = []
        for a in assets:
            path = root / a.path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"x")
            rows.append({
                "id": a.id, "path": a.path, "kind": a.kind, "tags": list(a.tags),
                "license": a.license, "attribution": "", "source": "",
                "sha256": hashlib.sha256(b"x").hexdigest(),
                "mime": "image/jpeg", "duration": 0,
            })
        reg = root / "registry.json"
        reg.write_text(json.dumps({"assets": rows}), encoding="utf-8")
        return reg

    def test_assigns_best_asset_and_records_confidence(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            reg = self._registry(root, [make_asset("fab", "image", ["semiconductor", "factory"])])
            beats = [Beat(id="b1", kind="evidence", text="A semiconductor factory line.",
                          seconds=4.0, visual="broll")]
            project = assign_assets(Project("T", "S", beats=beats), reg, root)
            beat = project.beats[0]
            self.assertEqual(beat.assetSrc, "public/assets/fab.jpg")
            self.assertGreater(beat.assetConfidence, 0.0)
            self.assertEqual(beat.assetReason, "matched")

    def test_no_match_falls_back_procedurally(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            reg = self._registry(root, [make_asset("nature", "image", ["trees"])])
            beats = [Beat(id="b1", kind="evidence", text="Quantum entanglement metrics.",
                          seconds=4.0, visual="broll")]
            project = assign_assets(Project("T", "S", beats=beats), reg, root)
            self.assertIsNone(project.beats[0].assetSrc)
            self.assertEqual(project.beats[0].assetReason, "procedural-fallback")

    def test_avoid_repeat_uses_alternative(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            reg = self._registry(root, [
                make_asset("fact_a", "image", ["semiconductor", "factory"]),
                make_asset("fact_b", "image", ["semiconductor", "factory", "lithography"]),
            ])
            beats = [
                Beat(id="b1", kind="evidence", text="Semiconductor factory lithography.",
                     seconds=4.0, visual="broll"),
                Beat(id="b2", kind="evidence", text="Semiconductor factory capacity.",
                     seconds=4.0, visual="broll"),
                Beat(id="b3", kind="evidence", text="Semiconductor factories expand.",
                     seconds=4.0, visual="broll"),
            ]
            project = assign_assets(Project("T", "S", beats=beats), reg, root)
            sources = [b.assetSrc for b in project.beats]
            self.assertEqual(len(set(sources)), 2, "should alternate, not repeat one asset 3x")

    def test_provenance_errors_raise(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            reg = self._registry(root, [make_asset("fab", "image", ["semiconductor"], license="summer-license")])
            beats = [Beat(id="b1", kind="evidence", text="semiconductor", seconds=4.0, visual="broll")]
            with self.assertRaises(RuntimeError):
                assign_assets(Project("T", "S", beats=beats), reg, root)


if __name__ == "__main__":
    unittest.main()