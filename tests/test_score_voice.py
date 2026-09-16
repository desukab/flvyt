"""Tests for the TTS voice slots and deterministic procedural music bed."""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from engine.audio import duration, run
from engine.score import chapter_segments, render_bed
from engine.tts import voice_command

HAVE_FFMPEG = shutil.which("ffmpeg") and shutil.which("ffprobe")


class VoiceSlotTests(unittest.TestCase):
    def test_registered_slot_resolves_to_template(self):
        self.assertEqual(voice_command("espeak"), "espeak-ng -w {output}")
        self.assertEqual(voice_command("piper"), "piper --model {model} --output_file {output}")

    def test_unknown_value_used_as_template(self):
        self.assertEqual(voice_command("sam --out {output}"), "sam --out {output}")

    def test_empty_voice_raises(self):
        with self.assertRaises(ValueError):
            voice_command("")

    def test_bad_template_placeholders_raise(self):
        with self.assertRaises(ValueError):
            voice_command("{busted} {other}")


class ChapterSegmentTests(unittest.TestCase):
    def test_ranges_follow_chapter_zones(self):
        beats = [
            {"seconds": 2.0, "chapter": 0},
            {"seconds": 1.0, "chapter": 0},
            {"seconds": 3.0, "chapter": 1},
            {"seconds": 2.0, "chapter": 2},
            {"seconds": 1.5, "chapter": 2},
        ]
        segs = chapter_segments(beats, total=9.5)
        self.assertEqual([(0.0, 3.0), (3.0, 6.0), (6.0, 9.5)], segs)

    def test_empty_beats_fall_back_to_full_range(self):
        self.assertEqual(chapter_segments([], total=7.0), [(0.0, 7.0)])


@unittest.skipUnless(HAVE_FFMPEG, "requires local ffmpeg/ffprobe")
class ScoreBedTests(unittest.TestCase):
    def test_bed_is_deterministic_and_truthful(self):
        beats = [
            {"seconds": 1.5, "chapter": 0},
            {"seconds": 1.5, "chapter": 1},
        ]
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            first = render_bed(3.0, beats, root / "bed1.wav", work_dir=root / "w1")
            second = render_bed(3.0, beats, root / "bed2.wav", work_dir=root / "w2")
            self.assertEqual(first["sha256"], second["sha256"])
            self.assertEqual(first["chapters"], 2)
            self.assertAlmostEqual(duration(root / "bed1.wav"), 3.0, delta=0.12)
            self.assertIn("licence-free", first["note"])

    def test_bed_without_beats_covers_total(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            info = render_bed(2.0, [], root / "bed.wav", work_dir=root)
            self.assertEqual(info["chapters"], 1)
            self.assertAlmostEqual(duration(root / "bed.wav"), 2.0, delta=0.12)
            self.assertEqual(len(info["sha256"]), 64)


if __name__ == "__main__":
    unittest.main()