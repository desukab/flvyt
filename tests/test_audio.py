"""Tests for the FFmpeg-driven audio assembly (pauses, timing alignment)."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from engine.audio import assemble_narration, concat_wavs, duration, mix
from engine.score import render_bed

HAVE_FFMPEG = shutil.which("ffmpeg") and shutil.which("ffprobe")


def make_tone(path: Path, seconds: float, frequency: int = 440) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        "ffmpeg", "-v", "error", "-y",
        "-f", "lavfi", "-i", f"sine=frequency={frequency}:duration={seconds:.3f}",
        "-ar", "48000", "-ac", "2", str(path),
    ], check=True)


@unittest.skipUnless(HAVE_FFMPEG, "requires local ffmpeg/ffprobe")
class AudioAssemblyTests(unittest.TestCase):
    def test_concat_without_pads_preserves_duration(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            a, b = root / "a.wav", root / "b.wav"
            make_tone(a, 0.5)
            make_tone(b, 0.5)
            out = concat_wavs([a, b], root / "master.wav")
            self.assertAlmostEqual(duration(out), 1.0, delta=0.05)

    def test_concat_inserts_pause_after_clips(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            a, b = root / "a.wav", root / "b.wav"
            make_tone(a, 0.5)
            make_tone(b, 0.5)
            out = concat_wavs([a, b], root / "master.wav", tail_pads=[0.25, 0.0])
            self.assertAlmostEqual(duration(out), 1.25, delta=0.07)

    def test_concat_duration_matches_picture_budget(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            clips = []
            pads = []
            for i in range(3):
                clip = root / f"c{i}.wav"
                make_tone(clip, 0.4, frequency=300 + i * 60)
                clips.append(clip)
                pads.append(0.2 if i % 2 else 0.1)
            out = concat_wavs(clips, root / "master.wav", tail_pads=pads)
            expected = sum(0.4 for _ in clips) + sum(pads)
            self.assertAlmostEqual(duration(out), expected, delta=0.08)

    def test_assemble_narration_uses_beat_pad_schedule(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            beats = [{"id": "b1", "pad_after": 0.2}, {"id": "b2", "pad_after": 0.0}]
            manifest = {"b1": str(root / "b1.wav"), "b2": str(root / "b2.wav")}
            make_tone(root / "b1.wav", 0.5)
            make_tone(root / "b2.wav", 0.5)
            out = assemble_narration(beats, manifest, root / "master.wav", cwd=root)
            from engine.project import INTRO_SECONDS
            self.assertAlmostEqual(duration(out), INTRO_SECONDS + 1.2, delta=0.07)

    def test_concat_lead_in_prepends_fixed_silence(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            a = root / "a.wav"
            make_tone(a, 0.5)
            out = concat_wavs([a], root / "master.wav", lead_in=5.0)
            self.assertAlmostEqual(duration(out), 5.5, delta=0.05)

    def test_empty_paths_raises(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                concat_wavs([], Path(td) / "x.wav")

    def test_mix_ducked_music_bed_succeeds(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            nar = root / "nar.wav"
            make_tone(nar, 2.0)
            bed = render_bed(2.5, [{"seconds": 1.25, "chapter": 0},
                                   {"seconds": 1.25, "chapter": 1}],
                             root / "bed.wav", work_dir=root / "w")
            out = root / "out.wav"
            mix(nar, Path(bed["wav"]), out)
            self.assertTrue(out.exists())
            self.assertAlmostEqual(duration(out), 2.0, delta=0.25)


if __name__ == "__main__":
    unittest.main()