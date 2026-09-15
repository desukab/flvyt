"""Guards for the verified submarine-cables documentary fixture."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.editorial import add_shots
from engine.editorial_gate import raise_if_invalid
from engine.project import Project
from engine.transitions import assign_transitions

SOURCE = ROOT / "projects" / "evidence.cables.json"
PROJECT = ROOT / "projects" / "cables.generated.json"

# Sources believed to be live at fixture creation; the evidence pack bypasses the
# live grounding gate on purpose so CI stays deterministic.
VERIFIED_SOURCES = {
    "https://en.wikipedia.org/wiki/Submarine_communications_cable",
}


class CablesFixtureTests(unittest.TestCase):
    def test_fixture_is_five_to_eight_minutes(self):
        project = Project.load(PROJECT)
        seconds = project.duration_frames() / project.fps
        self.assertGreaterEqual(seconds, 300)
        self.assertLessEqual(seconds, 480)
        self.assertGreaterEqual(len(project.beats), 30)

    def test_fixture_passes_editorial_gate(self):
        project = Project.load(PROJECT)
        add_shots(project.beats)
        assign_transitions(project.beats)
        raise_if_invalid(project.beats, fps=project.fps)

    def test_every_source_is_verified(self):
        data = json.loads(SOURCE.read_text(encoding="utf-8"))
        for item in data["evidence"]:
            self.assertIn(item["source"], VERIFIED_SOURCES, item["id"])
            self.assertTrue(item["claim"].strip())
            self.assertGreater(len(item["claim"].split()), 4)

    def test_evidence_pack_is_slotted_into_a_chapter(self):
        data = json.loads(SOURCE.read_text(encoding="utf-8"))
        for item in data["evidence"]:
            self.assertIsNotNone(item.get("slot"), item["id"])
            self.assertIsNotNone(item.get("chapter"), item["id"])
        slots = [item["slot"] for item in data["evidence"]]
        self.assertEqual(sorted(slots), list(range(1, len(slots) + 1)))
        chapters = {item["chapter"] for item in data["evidence"]}
        self.assertGreaterEqual(len(chapters), 3)

    def test_project_carries_section_beats(self):
        project = Project.load(PROJECT)
        sections = [b for b in project.beats if b.kind == "section"]
        self.assertGreaterEqual(len(sections), 3)
        self.assertEqual(project.title, "THE HIDDEN WEB")

    def test_no_shot_is_left_without_text(self):
        project = Project.load(PROJECT)
        add_shots(project.beats)
        for beat in project.beats:
            for shot in beat.shots:
                self.assertTrue(str(shot["text"]).strip(), f"{beat.id} {shot['id']}")

    def test_shot_text_is_distributed_in_readable_pieces(self):
        project = Project.load(PROJECT)
        add_shots(project.beats)
        for beat in project.beats:
            for shot in beat.shots:
                rate = len(str(shot["text"])) / max(0.1, float(shot["seconds"]))
                self.assertLess(rate, 22.0, f"{beat.id} {shot['id']} at {rate:.1f}")

    def test_fixture_passes_editorial_quality(self):
        from engine.editorial_quality import analyze
        import tempfile
        import os
        project = Project.load(PROJECT)
        add_shots(project.beats)
        props = project.props()
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(props, fh)
            tmp = fh.name
        try:
            report = analyze(tmp)
        finally:
            os.unlink(tmp)
        self.assertTrue(report["ok"], "fails: %s" % report["fails"])
        self.assertEqual(report["metrics"]["chapter_pacing"]["value"]["sections"], 5)


if __name__ == "__main__":
    unittest.main()