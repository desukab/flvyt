from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine import pipeline


def _evidence() -> dict:
    return {
        "title": "Test Topic",
        "thesis": "Fabrication nodes drive advanced semiconductor economics.",
        "evidence": [
            {
                "id": "e01",
                "claim": "Leading nodes are increasingly expensive to bring up.",
                "source": "https://example.test/report",
                "source_type": "article",
                "importance": "high",
                "tags": ["semiconductor", "economics"],
                "quote": "Costs scale with node complexity.",
            }
        ],
    }


class KindTests(unittest.TestCase):
    def test_kind_detection(self):
        self.assertEqual(pipeline._kind({"beats": []}), "project")
        self.assertEqual(pipeline._kind({"evidence": []}), "evidence")
        self.assertEqual(pipeline._kind({"sources": []}), "research")

    def test_kind_rejects_unknown(self):
        with self.assertRaises(ValueError):
            pipeline._kind({})


class ProduceTests(unittest.TestCase):
    def test_produce_runs_render_from_ready_project(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "p.json"
            project.write_text(json.dumps(_evidence()), encoding="utf-8")

            from engine.story import StoryPack, save_project
            save_project(StoryPack.load(project), str(project))

            seen: list[list[str]] = []

            def fake_run(cmd, *, show=True):
                seen.append(cmd)

            result = {}
            with mock.patch.object(pipeline, "_run", side_effect=fake_run):
                result = pipeline.produce(str(project))
            self.assertIn("editorial", [s["step"] for s in result["steps"]])
            self.assertIn("render", [s["step"] for s in result["steps"]])
            self.assertTrue(result["qa"]["ok"])
            self.assertTrue(seen, "expected staged subprocess call recorded")
            self.assertIn("scripts/render.py", seen[-1])


if __name__ == "__main__":
    unittest.main()