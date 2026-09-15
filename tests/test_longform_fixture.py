"""Guards for the real, verified long-form documentary fixture."""
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

SOURCE = ROOT / "projects" / "evidence.tsmc.json"
PROJECT = ROOT / "projects" / "tsmc.generated.json"

# Sources believed to be live at fixture creation; the evidence pack bypasses the
# live grounding gate on purpose so CI stays deterministic.
VERIFIED_SOURCES = {
    "https://en.wikipedia.org/wiki/TSMC",
    "https://www.tsmc.com/english/aboutTSMC",
    "https://investor.tsmc.com/english/",
    "https://pr.tsmc.com/english/",
}


class LongFormFixtureTests(unittest.TestCase):
    def test_fixture_is_three_to_five_minutes(self):
        project = Project.load(PROJECT)
        seconds = project.duration_frames() / project.fps
        self.assertGreaterEqual(seconds, 180)
        self.assertLessEqual(seconds, 300)
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
        slots = [item["slot"] for item in data["evidence"]]
        self.assertEqual(sorted(slots), list(range(1, len(slots) + 1)))


if __name__ == "__main__":
    unittest.main()