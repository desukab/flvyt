"""Tests for the kind-aware, duration-preserving editorial shot planner."""
from __future__ import annotations

import unittest

from engine.director import direct
from engine.editorial import (_clauses, _distribute_text, make_shots, add_shots)
from engine.editorial_gate import validate_shots
from engine.project import Beat, Project
from engine.transitions import assign_transitions

LONG_TEXT = (
    "Semiconductor manufacturing has become extraordinarily concentrated, "
    "and that concentration now shapes the entire technology economy; "
    "a single facility can gate the world's most advanced products."
)


class ShotDurationTests(unittest.TestCase):
    def test_durations_always_sum_to_beat_seconds(self):
        for seconds in (3.2, 4.0, 5.5, 7.2, 9.0):
            for kind in ("hook", "claim", "evidence", "context", "implication",
                         "thesis", "close"):
                with self.subTest(kind=kind, seconds=seconds):
                    shots = make_shots(LONG_TEXT, seconds, "claim", "normal", kind)
                    total = round(sum(s["seconds"] for s in shots), 3)
                    self.assertAlmostEqual(total, round(seconds, 3), places=2)

    def test_short_beats_stay_single_shot(self):
        shots = make_shots("Short sentence.", 2.0, "claim", "normal", "evidence")
        self.assertEqual(len(shots), 1)
        self.assertEqual(shots[0]["seconds"], 2.0)

    def test_short_word_count_stays_single_shot(self):
        shots = make_shots("Five words only here.", 5.0, "claim", "normal", "evidence")
        self.assertEqual(len(shots), 1)

    def test_all_shot_seconds_positive(self):
        for kind in (k for k in ("hook", "claim", "evidence", "context", "implication",
                                 "thesis", "close")):
            shots = make_shots(LONG_TEXT, 4.6, "timeline", "normal", kind)
            for shot in shots:
                self.assertGreater(shot["seconds"], 0, kind)


class KindAwareStructureTests(unittest.TestCase):
    def test_close_is_a_single_deliberate_hold(self):
        shots = make_shots(LONG_TEXT, 6.0, "claim", "normal", "close")
        self.assertEqual([s["mode"] for s in shots], ["hold"])

    def test_thesis_builds_then_holds_long(self):
        shots = make_shots(LONG_TEXT, 8.0, "claim", "normal", "thesis")
        modes = [s["mode"] for s in shots]
        self.assertGreaterEqual(len(shots), 2)
        self.assertEqual(modes[-1], "hold")
        self.assertGreater(shots[-1]["seconds"], 2.0)

    def test_hook_leads_with_a_punch(self):
        shots = make_shots(LONG_TEXT, 5.0, "claim", "high", "hook")
        self.assertEqual([s["mode"] for s in shots], ["punch", "hold"])

    def test_implication_punches(self):
        shots = make_shots(LONG_TEXT, 6.0, "claim", "high", "implication")
        self.assertIn("punch", [s["mode"] for s in shots])

    def test_stat_uses_count_modes(self):
        shots = make_shots(LONG_TEXT, 6.0, "stat", "normal", "evidence")
        modes = [s["mode"] for s in shots]
        self.assertTrue(set(modes) & {"count", "detail"})

    def test_map_uses_move_modes_not_text_punches(self):
        shots = make_shots(LONG_TEXT, 6.0, "map", "normal", "evidence")
        modes = [s["mode"] for s in shots]
        self.assertNotIn("punch", modes)
        self.assertTrue(set(modes) & {"establish", "move", "hold"})

    def test_high_emphasis_never_reduces_to_fewer_than_punch_hold_shape(self):
        shots = make_shots(LONG_TEXT, 5.0, "claim", "high", "evidence")
        modes = [s["mode"] for s in shots]
        self.assertIn("punch", modes)


class VarietyTests(unittest.TestCase):
    def test_single_clause_never_echoes_three_times(self):
        text = "This narration sentence contains no clause punctuation at all."
        for kind in ("claim", "evidence", "context"):
            with self.subTest(kind=kind):
                shots = make_shots(text, 6.0, "claim", "normal", kind)
                self.assertLessEqual(len(shots), 2, kind)

    def test_clause_text_is_distributed_but_never_empty(self):
        texts = _distribute_text(LONG_TEXT, 3)
        self.assertEqual(len(texts), 3)
        for t in texts:
            self.assertTrue(t.strip())

    def test_clause_split_does_not_break_numbers(self):
        clauses = _clauses("It cost $1,234,567 in 2024, and it rose.")
        self.assertEqual(len(clauses), 2)
        self.assertIn("$1,234,567 in 2024", clauses[0])

    def test_structure_differs_between_kinds(self):
        signatures = {}
        for kind in ("hook", "claim", "evidence", "implication", "thesis", "close"):
            shots = make_shots(LONG_TEXT, 6.0, "claim", "normal", kind)
            signatures[kind] = tuple((s["mode"], round(s["seconds"], 1)) for s in shots)
        self.assertNotEqual(signatures["hook"], signatures["claim"])
        self.assertNotEqual(signatures["evidence"], signatures["thesis"])


class DeterminismTests(unittest.TestCase):
    def test_same_input_same_plan(self):
        a = make_shots(LONG_TEXT, 6.4, "timeline", "high", "evidence")
        b = make_shots(LONG_TEXT, 6.4, "timeline", "high", "evidence")
        self.assertEqual(a, b)


class GateIntegrationTests(unittest.TestCase):
    def build_arc(self):
        kinds = ["hook", "context", "evidence", "implication", "thesis", "close"]
        return [Beat(id=f"b{i}", kind=k, text=LONG_TEXT, seconds=6.0,
                     visual="claim", emphasis="high" if i % 2 else "normal")
                for i, k in enumerate(kinds)]

    def test_assigned_arc_passes_the_gate(self):
        beats = self.build_arc()
        add_shots(beats)
        assign_transitions(beats)
        self.assertEqual(validate_shots(beats, fps=30), [])

    def test_director_produces_gate_valid_project(self):
        project = Project("T", "S", 30, 1920, 1080, self.build_arc())
        directed = direct(project)
        self.assertEqual(validate_shots(directed.beats, fps=30), [])
        total = sum(b.seconds for b in directed.beats)
        self.assertAlmostEqual(sum(s["seconds"] for b in directed.beats for s in b.shots),
                               total, places=2)


if __name__ == "__main__":
    unittest.main()