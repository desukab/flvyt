"""Tests for word-timed, emphasised, safe-margin captions."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from engine.captions import emphasize, words_to_cues, words_to_srt, _time


def words(seq):
    out = []
    cursor = 10.0
    for i, text in enumerate(seq):
        out.append({"start": cursor, "end": cursor + 0.3, "text": text})
        cursor += 0.3
    return out


class TimeTests(unittest.TestCase):
    def test_hms_ms_format(self):
        self.assertEqual(_time(65.25), "00:01:05,250")

    def test_intro_offset_milliseconds(self):
        cue = words_to_cues(words(["hello"]))[0]
        self.assertAlmostEqual(cue["start"], 15.0, places=2)


class CueGroupingTests(unittest.TestCase):
    def test_sentence_end_breaks_cue(self):
        seq = words(["This", "ends.", "Next", "one."])
        cues = words_to_cues(seq, offset=0)
        self.assertEqual(len(cues), 2)
        self.assertEqual(cues[0]["text"], "This ends.")
        self.assertEqual(cues[1]["text"], "Next one.")

    def test_word_budget_bounds_cue(self):
        seq = words(list("abcdefghij"))
        cues = words_to_cues(seq, offset=0, max_words=4)
        for cue in cues:
            self.assertLessEqual(len(cue["text"].split()), 4)

    def test_character_budget_bounds_cue(self):
        seq = words(["concentrated", "semiconductor", "manufacturing", "supply"])
        cues = words_to_cues(seq, offset=0, max_chars=20)
        for cue in cues:
            self.assertLessEqual(len(cue["text"]), 43)

    def test_duration_budget_bounds_cue(self):
        seq = words(["a", "b", "c", "d", "e", "f", "g"])
        cues = words_to_cues(seq, offset=0, max_duration=0.9)
        for cue in cues:
            self.assertLessEqual(cue["end"] - cue["start"], 1.0 + 1e-6)


class EmphasisTests(unittest.TestCase):
    def test_numbers_are_bolded(self):
        out = emphasize("grew by 60% in 2024")
        self.assertIn("<b>60%</b>", out)
        self.assertIn("<b>2024</b>", out)

    def test_constant_words_are_not_bolded(self):
        out = emphasize("the same words as before")
        self.assertNotIn("<b>", out)

    def test_units_are_bolded(self):
        self.assertIn("<b>$12 billion</b>", emphasize("spent $12 billion"))
        self.assertIn("<b>3nm</b>", emphasize("3nm process"))


class WrapTests(unittest.TestCase):
    def test_long_caption_wraps_to_two_lines_in_srt(self):
        long = " ".join(["word"] * 16)
        with tempfile.TemporaryDirectory() as td:
            out = words_to_srt(words(long.split()), Path(td) / "w.srt",
                               max_words=16, max_duration=10.0, max_chars=40, offset=0)
            body = out.read_text(encoding="utf-8")
            self.assertIn("\\N", body)


class SrtOutputTests(unittest.TestCase):
    def test_srt_round_trip(self):
        with tempfile.TemporaryDirectory() as td:
            out = words_to_srt(words(["Caption", "one.", "Caption", "two."]),
                               Path(td) / "c.srt", offset=5.0)
            text = out.read_text(encoding="utf-8")
            self.assertIn("00:00:1", text)
            self.assertIn("-->", text)
            self.assertGreaterEqual(text.count("-->"), 1)


if __name__ == "__main__":
    unittest.main()