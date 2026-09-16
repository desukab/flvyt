"""Tests for the machine-readable editorial quality engine."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.editorial_quality import analyze, report_to_path, render_text


def _shot(shot_id, seconds, text, visual="claim", transition="cut", mode="hold"):
    return {"id": shot_id, "seconds": seconds, "visual": visual, "text": text,
            "mode": mode, "transition": transition}


def _beat(beat_id, kind, seconds, text, shots=None, emphasis="normal",
          visual="claim", pad_after=0.0):
    return {"id": beat_id, "kind": kind, "text": text, "seconds": seconds,
            "visual": visual, "emphasis": emphasis, "pad_after": pad_after,
            "shots": shots or [_shot("s1", seconds, text, visual)]}


def _project(beats, fps=30):
    return {"title": "T", "subtitle": "S", "fps": fps, "width": 1920, "height": 1080,
            "beats": beats}


def _write(tmp: Path, name: str, payload) -> Path:
    path = tmp / name
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


KEYS = {
    "shot_duration_distribution", "shot_duration_buckets", "text_density",
    "near_duplicate_pairs", "visual_variety", "transition_density",
    "emphasis_distribution", "chapter_pacing", "asset_reuse",
    "narration_alignment", "caption_density",
}


class EditorialQualityTests(unittest.TestCase):
    def _analyze(self, beats, manifest=None, transcript=None):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            project = _write(td, "p.json", _project(beats))
            m = _write(td, "m.json", manifest) if manifest else None
            t = _write(td, "t.json", transcript) if transcript else None
            return analyze(project, manifest_path=m, transcript_path=t)

    def test_report_shape_and_all_metrics_present(self):
        beats = [
            _beat("b1", "hook", 4.0, "Big claim one here.", emphasis="high"),
            _beat("b2", "evidence", 4.0, "Second claim with facts."),
            _beat("b3", "thesis", 4.5, "Final thesis sentence ends."),
        ]
        report = self._analyze(beats)
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["fails"], [])
        self.assertIn("engine", report)
        for key in KEYS:
            self.assertIn(key, report["metrics"], key)
        self.assertIn("3 shots", report["metrics"]["shot_duration_distribution"]["detail"])

    def test_identical_adjacent_text_fails(self):
        beats = [
            _beat("b1", "evidence", 3.4, "The same sentence repeats."),
            _beat("b2", "evidence", 3.4, "The same sentence repeats."),
        ]
        report = self._analyze(beats)
        self.assertFalse(report["ok"])
        self.assertTrue(any("identical text repeated" in f for f in report["fails"]))

    def test_dense_text_fails(self):
        beats = [_beat("b1", "evidence", 1.0, "x" * 40)]
        report = self._analyze(beats)
        self.assertFalse(report["ok"])
        self.assertTrue(any("text density" in f for f in report["fails"]))
        self.assertFalse(report["metrics"]["text_density"]["ok"])

    def test_short_shot_fails(self):
        beats = [{"id": "b1", "kind": "claim", "text": "Too short.", "seconds": 3.0,
                  "visual": "claim", "shots": [_shot("s1", 0.4, "Too short.")]}]
        report = self._analyze([beats[0]])
        self.assertFalse(report["ok"])
        self.assertTrue(any("below 1.0s" in f for f in report["fails"]))

    def test_long_visual_run_fails(self):
        beats = [_beat(f"b{i}", "evidence", 3.4, f"Claim number {i} here.", visual="claim")
                 for i in range(5)]
        report = self._analyze(beats)
        self.assertFalse(report["ok"])
        self.assertTrue(any("same visual reason" in f for f in report["fails"]))

    def test_motif_reason_breaks_claim_run(self):
        beats = [
            {"id": "b0", "kind": "evidence", "text": "A satellite constellation orbits.",
             "seconds": 3.4, "visual": "claim", "motif": "orbit", "intent": "detail",
             "shots": [_shot("s1", 3.4, "A satellite constellation orbits.")]},
            {"id": "b1", "kind": "evidence", "text": "A ground station monitors it.",
             "seconds": 3.4, "visual": "claim", "motif": "grid", "intent": "detail",
             "shots": [_shot("s1", 3.4, "A ground station monitors it.")]},
            {"id": "b2", "kind": "evidence", "text": "Nanosecond clocks set the timing.",
             "seconds": 3.4, "visual": "claim", "motif": "wave", "intent": "detail",
             "shots": [_shot("s1", 3.4, "Nanosecond clocks set the timing.")]},
        ]
        report = self._analyze(beats)
        self.assertTrue(report["ok"], msg="\n".join(report["fails"]))
        self.assertFalse(any("same visual reason" in f for f in report["fails"]))
        self.assertFalse(any("same visual reason" in w for w in report["warns"]))

    def test_beam_shot_modes_do_not_stutter(self):
        # A single beat's establish -> move -> hold decompose is deliberate shot
        # variety, not three stale cards; the run must not count it as a stall.
        beat = {"id": "b0", "kind": "evidence",
                "text": "A constellation of satellites broadcasts precise timing.",
                "seconds": 9.0, "visual": "map", "motif": "cosmos", "intent": "punch",
                "shots": [
                    _shot("s1", 3.0, "A constellation broadcasts precise timing.", visual="map", mode="establish"),
                    _shot("s2", 3.0, "precise timing signals.", visual="map", mode="move"),
                    _shot("s3", 3.0, "precise timing signals.", visual="map", mode="hold"),
                ]}
        report = self._analyze([beat])
        self.assertTrue(report["ok"], msg="\n".join(report["fails"]))
        self.assertFalse(any("same visual reason" in f for f in report["fails"]))
        self.assertFalse(any("same visual reason" in w for w in report["warns"]))
        self.assertFalse(any("generic procedural" in f for f in report["fails"]))

    def test_identical_reason_across_beats_still_fails(self):
        beats = []
        for i in range(4):
            beats.append({"id": f"b{i}", "kind": "evidence", "text": f"Claim {i}.",
                          "seconds": 3.4, "visual": "claim", "motif": "cosmos",
                          "intent": "detail",
                          "shots": [_shot("s1", 3.4, f"Claim {i}.")]})
        beats.append({"id": "b4", "kind": "evidence", "text": "Claim 4.",
                      "seconds": 3.4, "visual": "claim", "motif": "cosmos",
                      "intent": "detail",
                      "shots": [_shot("s1", 3.4, "Claim 4.")]})
        report = self._analyze(beats)
        self.assertFalse(report["ok"], msg="\n".join(report["fails"]))
        self.assertTrue(any("same visual reason" in f for f in report["fails"]))
        self.assertTrue(any("generic procedural" in f for f in report["fails"]))

    def test_decor_run_counts_beats_not_shots(self):
        # Two consecutive content-free beats (each a deliberate establish->hold
        # decompose) are a two-beat run, not a six-shot generic stall. A healthy
        # share of the edit stays content-anchored so the share gate is green.
        beats = [
            {"id": "b0", "kind": "evidence", "text": "One point stands alone.",
             "seconds": 3.0, "visual": "claim", "motif": "cosmos",
             "shots": [_shot("s1", 1.5, "One point", mode="establish"),
                       _shot("s2", 1.5, "alone", mode="hold")]},
            {"id": "b1", "kind": "evidence", "text": "A second line follows it.",
             "seconds": 3.0, "visual": "claim", "motif": "cosmos",
             "shots": [_shot("s1", 1.5, "A second", mode="establish"),
                       _shot("s2", 1.5, "follows", mode="hold")]},
            {"id": "b2", "kind": "evidence", "text": "Orbits time the constellation.",
             "seconds": 4.0, "visual": "map", "motif": "orbit",
             "shots": [_shot("s1", 1.3, "Orbits", visual="map", mode="establish"),
                       _shot("s2", 1.4, "time the", visual="map", mode="move"),
                       _shot("s3", 1.3, "constellation", visual="map", mode="hold")]},
            {"id": "b3", "kind": "evidence", "text": "Stations monitor the fleet.",
             "seconds": 4.0, "visual": "timeline", "motif": "grid",
             "shots": [_shot("s1", 4.0, "Stations monitor the fleet.", visual="timeline", mode="move")]},
            {"id": "b4", "kind": "evidence", "text": "Billion receivers rely on it.",
             "seconds": 4.0, "visual": "stat", "motif": "accounts",
             "shots": [_shot("s1", 4.0, "Billion receivers rely.", visual="stat", mode="count")]},
        ]
        report = self._analyze(beats)
        self.assertTrue(report["ok"], msg="\n".join(report["fails"]))
        self.assertFalse(any("generic procedural" in f for f in report["fails"]))
        self.assertFalse(any("same visual reason" in f for f in report["fails"]))
        decor = report["metrics"]["decorative_only_share"]
        self.assertLessEqual(decor["value"], 0.30)

    def test_long_doc_without_sections_warns(self):
        beats = [
            _beat(f"b{i}", "evidence", 3.4, f"Evidence claim {i}.",
                  visual="claim" if i % 2 == 0 else "stat")
            for i in range(12)
        ]
        report = self._analyze(beats)
        self.assertTrue(report["ok"])
        self.assertTrue(any("no chapter/section markers" in w for w in report["warns"]))

    def test_transcript_caption_density(self):
        beats = [_beat("b1", "evidence", 60.0, "A long narration beat.")]
        transcript = {
            "words": [{"start": i, "end": i + 1, "text": "w"} for i in range(60)],
            "cues": [{"start": i, "end": i + 1.0, "text": "w"} for i in range(60)],
        }
        report = self._analyze(beats, transcript=transcript)
        metric = report["metrics"]["caption_density"]
        self.assertGreater(metric["value"]["cues_per_minute"], 14)
        self.assertFalse(metric["ok"])
        self.assertTrue(any("caption density" in w for w in report["warns"]))

    def test_narration_visual_alignment(self):
        beats = [_beat("b1", "evidence", 3.4, "Short narration.", pad_after=0.18)]
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            audio = td / "b1.wav"
            audio.write_bytes(b"\x00" * 16)
            manifest = {"b1": str(audio)}
            project = _write(td, "p.json", _project(beats))
            m = _write(td, "m.json", manifest)
            with mock.patch("engine.audio.duration", return_value=4.0):
                report = analyze(project, manifest_path=m)
            self.assertFalse(report["metrics"]["narration_alignment"]["ok"])
            self.assertTrue(any("narration longer" in w for w in report["warns"]))

    def test_report_to_path_writes_json(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            project = _write(td, "p.json", _project([
                _beat("b1", "hook", 4.0, "Opener claim sentence.", emphasis="high"),
                _beat("b2", "thesis", 4.5, "Closing thesis statement."),
            ]))
            out = td / "qa.json"
            report = report_to_path(project, out)
            self.assertTrue(report["ok"])
            written = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(written["engine"], report["engine"])
            self.assertIn("shot_duration_distribution", written["metrics"])
            text = render_text(report)
            self.assertIn("EDITORIAL QA: PASS", text)


if __name__ == "__main__":
    unittest.main()