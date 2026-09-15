"""Unit tests for the deterministic transition/cut grammar."""
from __future__ import annotations

import unittest

from engine.edit_policy import decision
from engine.editorial import make_shots
from engine.project import Beat
from engine.transitions import (
    assign_transitions,
    beat_open,
    shot_open,
    transition_frames,
)
from engine.editorial_gate import validate_shots


def beat(kind: str, visual: str = "claim", seconds: float = 6.0,
         emphasis: str = "normal", beats: list = None, text: str = "") -> Beat:
    text = text or (
        "This is a deliberately long documentary sentence written for testing "
        "so that the shot planner can split it into several structural shots."
        if emphasis == "high" else
        "A complete documentary sentence that the planner can cut into pieces."
    )
    planned = make_shots(text, seconds, visual, emphasis, kind)
    bid = f"{kind}-{len(beats or []) + 1:02d}"
    return Beat(id=bid, kind=kind, text=text, seconds=seconds, visual=visual,
                emphasis=emphasis, shots=planned)


def standard_arc() -> list[Beat]:
    kinds = ["hook", "context", "evidence", "evidence", "implication", "thesis", "close"]
    return [beat(k, seconds=5.0) for k in kinds]


class BeatOpenTests(unittest.TestCase):
    def test_first_beat_fades_in_from_intro(self):
        self.assertEqual(beat_open(beat("claim"), True, None), "fade")

    def test_chapter_kinds_dip(self):
        for kind in ("hook", "thesis", "close", "implication", "turn"):
            with self.subTest(kind=kind):
                self.assertEqual(beat_open(beat(kind), False, None), "dip")

    def test_soft_kinds_fade(self):
        for kind in ("context", "premise", "geography"):
            with self.subTest(kind=kind):
                self.assertEqual(beat_open(beat(kind), False, None), "fade")

    def test_exposition_cuts(self):
        for kind in ("evidence", "claim", "stat", "structure"):
            with self.subTest(kind=kind):
                self.assertEqual(beat_open(beat(kind), False, None), "cut")


class ShotOpenTests(unittest.TestCase):
    def test_fade_on_repeated_visual(self):
        shots = [
            {"visual": "text", "mode": "establish"},
            {"visual": "text", "mode": "punch"},
        ]
        b = beat("evidence", visual="text")
        self.assertEqual(shot_open(b, shots, 1), "fade")

    def test_settle_after_punch_fades(self):
        shots = [
            {"visual": "text", "mode": "punch"},
            {"visual": "text", "mode": "hold"},
        ]
        b = beat("evidence", visual="text")
        self.assertEqual(shot_open(b, shots, 1), "fade")

    def test_same_visual_but_already_faded_cuts(self):
        shots = [
            {"visual": "text", "mode": "establish", "transition": "fade"},
            {"visual": "text", "mode": "punch"},
            {"visual": "text", "mode": "hold"},
        ]
        b = beat("evidence", visual="text")
        self.assertEqual(shot_open(b, shots, 1), "cut")
        self.assertEqual(shot_open(b, shots, 2), "cut")

    def test_visual_change_cuts(self):
        shots = [{"visual": "map", "mode": "move"}, {"visual": "text", "mode": "hold"}]
        b = beat("evidence", visual="map")
        self.assertEqual(shot_open(b, shots, 1), "cut")

    def test_transition_frames_scale_with_fps(self):
        self.assertGreater(transition_frames("fade", 60), transition_frames("fade", 30))
        self.assertGreater(transition_frames("dip", 60), transition_frames("dip", 30))
        self.assertEqual(transition_frames("cut", 30), 0)


class AssignTransitionTests(unittest.TestCase):
    def test_every_shot_receives_transition(self):
        beats = assign_transitions(standard_arc())
        for b in beats:
            for shot in b.shots:
                self.assertIn(shot["transition"], {"cut", "fade", "dip"})
                self.assertIn("transitionFrames", shot)

    def test_default_is_cut(self):
        beats = assign_transitions(standard_arc())
        transitions = {s["transition"] for b in beats for s in b.shots}
        self.assertIn("cut", transitions)

    def test_no_identical_noncut_entrances_back_to_back(self):
        beats = assign_transitions(standard_arc())
        prev = "cut"
        for b in beats:
            for shot in b.shots:
                t = shot["transition"]
                if t != "cut":
                    self.assertNotEqual(prev, t, f"spam at {b.id}: {t} twice")
                prev = t

    def test_at_most_one_noncut_per_beat(self):
        beats = assign_transitions(standard_arc())
        for b in beats:
            noncuts = sum(1 for s in b.shots if s["transition"] != "cut")
            self.assertLessEqual(noncuts, 1, b.id)

    def test_chapter_dips_appear(self):
        beats = assign_transitions(standard_arc())
        dips = [s["transition"] for b in beats for s in b.shots if s["transition"] == "dip"]
        self.assertGreaterEqual(len(dips), 2, "hook/thesis/close should produce dips")

    def test_assign_is_deterministic(self):
        first = assign_transitions([beat(k, seconds=4.0) for k in
                                    ["hook", "evidence", "implication", "thesis"]])
        second = assign_transitions([beat(k, seconds=4.0) for k in
                                     ["hook", "evidence", "implication", "thesis"]])
        for b1, b2 in zip(first, second):
            for s1, s2 in zip(b1.shots, b2.shots):
                self.assertEqual(s1["transition"], s2["transition"])
                self.assertEqual(s1["transitionFrames"], s2["transitionFrames"])

    def test_gate_is_satisfied_after_assignment(self):
        beats = assign_transitions(standard_arc())
        self.assertEqual(validate_shots(beats, fps=30), [])

    def test_short_single_shot_beat_is_cut(self):
        opener = beat("hook", seconds=2.0)
        b = beat("evidence", seconds=2.0)
        b.shots = [{"id": "s1", "seconds": 2.0, "visual": b.visual,
                    "text": b.text, "mode": "hold"}]
        beats = assign_transitions([opener, b])
        self.assertEqual(beats[1].shots[0]["transition"], "cut")


if __name__ == "__main__":
    unittest.main()